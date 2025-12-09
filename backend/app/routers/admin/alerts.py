"""
Admin Alerts Router
===================

Endpoints for managing system alerts.
"""

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from pydantic import BaseModel
from typing import Optional, List, Dict, Any
from uuid import UUID
from datetime import datetime

from app.deps import get_admin_user, require_admin_role, AdminContext
from app.database import get_supabase_service
from .models import CamelModel
from .utils import log_admin_action

router = APIRouter(prefix="/alerts", tags=["admin-alerts"])


# ============================================================
# Models (with camelCase serialization)
# ============================================================

class AlertResponse(CamelModel):
    id: str
    alert_type: str
    severity: str  # 'info', 'warning', 'error', 'critical'
    target_type: Optional[str] = None
    target_id: Optional[str] = None
    target_name: Optional[str] = None
    title: str
    description: Optional[str] = None
    context: Optional[Dict[str, Any]] = None
    status: str  # 'active', 'acknowledged', 'resolved'
    acknowledged_by: Optional[str] = None
    acknowledged_at: Optional[datetime] = None
    resolved_by: Optional[str] = None
    resolved_at: Optional[datetime] = None
    resolution_notes: Optional[str] = None
    created_at: datetime


class AlertListResponse(CamelModel):
    alerts: List[AlertResponse]
    total: int
    active_count: int


class AcknowledgeRequest(BaseModel):
    pass  # No body needed


class ResolveRequest(BaseModel):
    notes: Optional[str] = None


# ============================================================
# Endpoints
# ============================================================

@router.get("", response_model=AlertListResponse)
async def list_alerts(
    status: Optional[str] = Query(None, description="Filter by status"),
    severity: Optional[str] = Query(None, description="Filter by severity"),
    alert_type: Optional[str] = Query(None, description="Filter by type"),
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
    admin: AdminContext = Depends(get_admin_user)
):
    """
    List system alerts with filtering.
    
    Query params:
    - status: 'active', 'acknowledged', 'resolved'
    - severity: 'info', 'warning', 'error', 'critical'
    - alert_type: 'error_spike', 'churn_risk', 'payment_failed', 'usage_limit'
    """
    supabase = get_supabase_service()
    
    query = supabase.table("admin_alerts") \
        .select("*", count="exact")
    
    if status:
        query = query.eq("status", status)
    
    if severity:
        query = query.eq("severity", severity)
    
    if alert_type:
        query = query.eq("alert_type", alert_type)
    
    result = query \
        .order("status") \
        .order("severity", desc=True) \
        .order("created_at", desc=True) \
        .range(offset, offset + limit - 1) \
        .execute()
    
    # Get active count
    active_result = supabase.table("admin_alerts") \
        .select("id", count="exact") \
        .eq("status", "active") \
        .execute()
    
    alerts = [
        AlertResponse(
            id=a["id"],
            alert_type=a["alert_type"],
            severity=a["severity"],
            target_type=a.get("target_type"),
            target_id=a.get("target_id"),
            target_name=a.get("target_name"),
            title=a["title"],
            description=a.get("description"),
            context=a.get("context"),
            status=a["status"],
            acknowledged_by=a.get("acknowledged_by"),
            acknowledged_at=a.get("acknowledged_at"),
            resolved_by=a.get("resolved_by"),
            resolved_at=a.get("resolved_at"),
            resolution_notes=a.get("resolution_notes"),
            created_at=a["created_at"]
        ) for a in (result.data or [])
    ]
    
    return AlertListResponse(
        alerts=alerts,
        total=result.count or len(alerts),
        active_count=active_result.count or 0
    )


@router.get("/{alert_id}", response_model=AlertResponse)
async def get_alert(
    alert_id: str,
    admin: AdminContext = Depends(get_admin_user)
):
    """Get a specific alert by ID."""
    supabase = get_supabase_service()
    
    result = supabase.table("admin_alerts") \
        .select("*") \
        .eq("id", alert_id) \
        .maybe_single() \
        .execute()
    
    if not result.data:
        raise HTTPException(status_code=404, detail="Alert not found")
    
    a = result.data
    return AlertResponse(
        id=a["id"],
        alert_type=a["alert_type"],
        severity=a["severity"],
        target_type=a.get("target_type"),
        target_id=a.get("target_id"),
        target_name=a.get("target_name"),
        title=a["title"],
        description=a.get("description"),
        context=a.get("context"),
        status=a["status"],
        acknowledged_by=a.get("acknowledged_by"),
        acknowledged_at=a.get("acknowledged_at"),
        resolved_by=a.get("resolved_by"),
        resolved_at=a.get("resolved_at"),
        resolution_notes=a.get("resolution_notes"),
        created_at=a["created_at"]
    )


@router.post("/{alert_id}/acknowledge")
async def acknowledge_alert(
    alert_id: str,
    request: Request,
    admin: AdminContext = Depends(require_admin_role("super_admin", "admin", "support"))
):
    """Acknowledge an alert (marks as 'acknowledged')."""
    supabase = get_supabase_service()
    
    # Get existing alert
    existing = supabase.table("admin_alerts") \
        .select("*") \
        .eq("id", alert_id) \
        .maybe_single() \
        .execute()
    
    if not existing.data:
        raise HTTPException(status_code=404, detail="Alert not found")
    
    if existing.data["status"] != "active":
        raise HTTPException(status_code=400, detail="Alert is not active")
    
    # Update alert
    result = supabase.table("admin_alerts") \
        .update({
            "status": "acknowledged",
            "acknowledged_by": admin.admin_id,
            "acknowledged_at": datetime.utcnow().isoformat()
        }) \
        .eq("id", alert_id) \
        .execute()
    
    if not result.data:
        raise HTTPException(status_code=500, detail="Failed to acknowledge alert")
    
    # Log action
    await log_admin_action(
        admin_id=admin.admin_id,
        action="alert.acknowledge",
        target_type="alert",
        target_id=UUID(alert_id),
        target_identifier=existing.data["title"],
        request=request
    )
    
    return {"success": True, "message": "Alert acknowledged"}


@router.post("/{alert_id}/resolve")
async def resolve_alert(
    alert_id: str,
    data: ResolveRequest,
    request: Request,
    admin: AdminContext = Depends(require_admin_role("super_admin", "admin", "support"))
):
    """Resolve an alert with optional notes."""
    supabase = get_supabase_service()
    
    # Get existing alert
    existing = supabase.table("admin_alerts") \
        .select("*") \
        .eq("id", alert_id) \
        .maybe_single() \
        .execute()
    
    if not existing.data:
        raise HTTPException(status_code=404, detail="Alert not found")
    
    if existing.data["status"] == "resolved":
        raise HTTPException(status_code=400, detail="Alert is already resolved")
    
    # Update alert
    result = supabase.table("admin_alerts") \
        .update({
            "status": "resolved",
            "resolved_by": admin.admin_id,
            "resolved_at": datetime.utcnow().isoformat(),
            "resolution_notes": data.notes
        }) \
        .eq("id", alert_id) \
        .execute()
    
    if not result.data:
        raise HTTPException(status_code=500, detail="Failed to resolve alert")
    
    # Log action
    await log_admin_action(
        admin_id=admin.admin_id,
        action="alert.resolve",
        target_type="alert",
        target_id=UUID(alert_id),
        target_identifier=existing.data["title"],
        details={"notes": data.notes} if data.notes else None,
        request=request
    )
    
    return {"success": True, "message": "Alert resolved"}


@router.post("/bulk-acknowledge")
async def bulk_acknowledge_alerts(
    alert_ids: List[str],
    request: Request,
    admin: AdminContext = Depends(require_admin_role("super_admin", "admin", "support"))
):
    """Acknowledge multiple alerts at once."""
    supabase = get_supabase_service()
    
    if not alert_ids or len(alert_ids) > 50:
        raise HTTPException(status_code=400, detail="Provide 1-50 alert IDs")
    
    # Update all alerts
    result = supabase.table("admin_alerts") \
        .update({
            "status": "acknowledged",
            "acknowledged_by": admin.admin_id,
            "acknowledged_at": datetime.utcnow().isoformat()
        }) \
        .in_("id", alert_ids) \
        .eq("status", "active") \
        .execute()
    
    count = len(result.data) if result.data else 0
    
    # Log action
    await log_admin_action(
        admin_id=admin.admin_id,
        action="alert.bulk_acknowledge",
        details={"alert_ids": alert_ids, "count": count},
        request=request
    )
    
    return {"success": True, "acknowledged_count": count}

