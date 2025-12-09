"""
Admin Audit Log Router
======================

Endpoints for viewing and exporting the admin audit log.
"""

from fastapi import APIRouter, Depends, Query, Response
from typing import Optional, List, Dict, Any
from datetime import datetime
import csv
import io

from app.deps import get_admin_user, require_admin_role, AdminContext
from app.database import get_supabase_service
from .models import CamelModel

router = APIRouter(prefix="/audit", tags=["admin-audit"])


# ============================================================
# Models (with camelCase serialization)
# ============================================================

class AuditLogEntry(CamelModel):
    id: str
    admin_id: str
    admin_email: str
    action: str
    target_type: Optional[str] = None
    target_id: Optional[str] = None
    target_identifier: Optional[str] = None
    details: Optional[Dict[str, Any]] = None
    ip_address: Optional[str] = None
    user_agent: Optional[str] = None
    created_at: datetime


class AuditLogResponse(CamelModel):
    entries: List[AuditLogEntry]
    total: int
    has_more: bool
    next_cursor: Optional[str] = None


# ============================================================
# Endpoints
# ============================================================

@router.get("", response_model=AuditLogResponse)
async def get_audit_log(
    action: Optional[str] = Query(None, description="Filter by action type"),
    target_type: Optional[str] = Query(None, description="Filter by target type"),
    admin_id: Optional[str] = Query(None, description="Filter by admin"),
    date_from: Optional[datetime] = Query(None, description="Filter from date"),
    date_to: Optional[datetime] = Query(None, description="Filter to date"),
    search: Optional[str] = Query(None, description="Search in target_identifier"),
    limit: int = Query(50, ge=1, le=200),
    cursor: Optional[str] = Query(None, description="Cursor for pagination"),
    admin: AdminContext = Depends(get_admin_user)
):
    """
    Get audit log entries with filtering.
    
    Uses cursor-based pagination for efficient scrolling.
    
    Query params:
    - action: Filter by action (e.g., 'user.view', 'user.reset_flows')
    - target_type: Filter by target type ('user', 'organization', 'alert')
    - admin_id: Filter by specific admin
    - date_from/date_to: Date range filter
    - search: Search in target_identifier
    """
    supabase = get_supabase_service()
    
    query = supabase.table("admin_audit_log") \
        .select("*, admin_users(user_id)", count="exact")
    
    # Apply filters
    if action:
        query = query.eq("action", action)
    
    if target_type:
        query = query.eq("target_type", target_type)
    
    if admin_id:
        query = query.eq("admin_user_id", admin_id)
    
    if date_from:
        query = query.gte("created_at", date_from.isoformat())
    
    if date_to:
        query = query.lte("created_at", date_to.isoformat())
    
    if search:
        query = query.ilike("target_identifier", f"%{search}%")
    
    # Cursor pagination
    if cursor:
        query = query.lt("created_at", cursor)
    
    result = query \
        .order("created_at", desc=True) \
        .limit(limit + 1) \
        .execute()
    
    entries = []
    has_more = False
    next_cursor = None
    
    data = result.data or []
    if len(data) > limit:
        has_more = True
        data = data[:limit]
        next_cursor = data[-1]["created_at"] if data else None
    
    # Batch fetch admin emails to avoid N+1 queries
    admin_user_ids = set()
    for entry in data:
        if entry.get("admin_users") and entry["admin_users"].get("user_id"):
            admin_user_ids.add(entry["admin_users"]["user_id"])
    
    admin_emails = {}
    if admin_user_ids:
        emails_result = supabase.table("users") \
            .select("id, email") \
            .in_("id", list(admin_user_ids)) \
            .execute()
        for user in (emails_result.data or []):
            admin_emails[user["id"]] = user["email"]
    
    for entry in data:
        admin_user_id = entry["admin_users"]["user_id"] if entry.get("admin_users") else None
        admin_email = admin_emails.get(admin_user_id, "Unknown")
        
        entries.append(AuditLogEntry(
            id=entry["id"],
            admin_id=entry["admin_user_id"],
            admin_email=admin_email,
            action=entry["action"],
            target_type=entry.get("target_type"),
            target_id=entry.get("target_id"),
            target_identifier=entry.get("target_identifier"),
            details=entry.get("details"),
            ip_address=entry.get("ip_address"),
            user_agent=entry.get("user_agent"),
            created_at=entry["created_at"]
        ))
    
    return AuditLogResponse(
        entries=entries,
        total=result.count or len(entries),
        has_more=has_more,
        next_cursor=next_cursor
    )


@router.get("/export")
async def export_audit_log(
    action: Optional[str] = Query(None),
    target_type: Optional[str] = Query(None),
    date_from: Optional[datetime] = Query(None),
    date_to: Optional[datetime] = Query(None),
    limit: int = Query(1000, ge=1, le=10000),
    admin: AdminContext = Depends(require_admin_role("super_admin", "admin"))
):
    """
    Export audit log as CSV.
    
    Maximum 10,000 entries per export.
    """
    supabase = get_supabase_service()
    
    query = supabase.table("admin_audit_log") \
        .select("*, admin_users(user_id)")
    
    # Apply filters
    if action:
        query = query.eq("action", action)
    
    if target_type:
        query = query.eq("target_type", target_type)
    
    if date_from:
        query = query.gte("created_at", date_from.isoformat())
    
    if date_to:
        query = query.lte("created_at", date_to.isoformat())
    
    result = query \
        .order("created_at", desc=True) \
        .limit(limit) \
        .execute()
    
    # Create CSV
    output = io.StringIO()
    writer = csv.writer(output)
    
    # Header
    writer.writerow([
        "Timestamp",
        "Admin ID",
        "Action",
        "Target Type",
        "Target ID",
        "Target Identifier",
        "Details",
        "IP Address"
    ])
    
    # Get admin emails in bulk
    admin_ids = set()
    for entry in (result.data or []):
        if entry.get("admin_users") and entry["admin_users"].get("user_id"):
            admin_ids.add(entry["admin_users"]["user_id"])
    
    admin_emails = {}
    if admin_ids:
        emails_result = supabase.table("users") \
            .select("id, email") \
            .in_("id", list(admin_ids)) \
            .execute()
        
        for user in (emails_result.data or []):
            admin_emails[user["id"]] = user["email"]
    
    # Data rows
    for entry in (result.data or []):
        admin_user_id = entry["admin_users"]["user_id"] if entry.get("admin_users") else None
        admin_email = admin_emails.get(admin_user_id, "Unknown")
        
        writer.writerow([
            entry["created_at"],
            admin_email,
            entry["action"],
            entry.get("target_type", ""),
            entry.get("target_id", ""),
            entry.get("target_identifier", ""),
            str(entry.get("details", "")),
            entry.get("ip_address", "")
        ])
    
    # Return CSV response
    csv_content = output.getvalue()
    output.close()
    
    filename = f"audit_log_{datetime.utcnow().strftime('%Y%m%d_%H%M%S')}.csv"
    
    return Response(
        content=csv_content,
        media_type="text/csv",
        headers={
            "Content-Disposition": f"attachment; filename={filename}"
        }
    )


@router.get("/actions")
async def get_action_types(
    admin: AdminContext = Depends(get_admin_user)
):
    """
    Get list of unique action types in the audit log.
    
    Useful for populating filter dropdowns.
    """
    supabase = get_supabase_service()
    
    result = supabase.table("admin_audit_log") \
        .select("action") \
        .execute()
    
    actions = set()
    for entry in (result.data or []):
        actions.add(entry["action"])
    
    return {"actions": sorted(list(actions))}

