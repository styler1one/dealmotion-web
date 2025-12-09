"""
Admin Users Router
==================

Endpoints for user management in the admin panel.
"""

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from pydantic import BaseModel
from typing import Optional, List, Any, Dict
from uuid import UUID
from datetime import datetime

from app.deps import get_admin_user, require_admin_role, AdminContext
from app.database import get_supabase_service
from .models import CamelModel
from .utils import log_admin_action, calculate_health_score, get_health_status

router = APIRouter(prefix="/users", tags=["admin-users"])


# ============================================================
# Response Models (with camelCase serialization)
# ============================================================


class FlowUsage(CamelModel):
    used: int
    limit: int
    pack_balance: int


class AdminUserListItem(CamelModel):
    id: str
    email: str
    full_name: Optional[str] = None
    organization_id: Optional[str] = None
    organization_name: Optional[str] = None
    plan: str
    flow_usage: FlowUsage
    health_score: int
    health_status: str
    last_active: Optional[datetime] = None
    created_at: datetime


class FlowPackInfo(CamelModel):
    id: str
    flows_purchased: int
    flows_remaining: int
    purchased_at: datetime
    status: str


class AdminNoteInfo(CamelModel):
    id: str
    content: str
    is_pinned: bool
    admin_name: str
    created_at: datetime


class AdminUserDetail(AdminUserListItem):
    stripe_customer_id: Optional[str] = None
    subscription_status: Optional[str] = None
    trial_ends_at: Optional[datetime] = None
    profile_completeness: int = 0
    total_researches: int = 0
    total_preps: int = 0
    total_followups: int = 0
    error_count_30d: int = 0
    flow_packs: List[FlowPackInfo] = []
    admin_notes: List[AdminNoteInfo] = []


class UserListResponse(CamelModel):
    users: List[AdminUserListItem]
    total: int
    offset: int
    limit: int


class ActivityItem(CamelModel):
    id: str
    type: str
    description: str
    created_at: datetime
    metadata: Optional[Dict[str, Any]] = None


class UserActivityResponse(CamelModel):
    activities: List[ActivityItem]
    total: int


class BillingItem(CamelModel):
    id: str
    amount_cents: int
    currency: str
    status: str
    invoice_number: Optional[str] = None
    invoice_pdf_url: Optional[str] = None
    paid_at: Optional[datetime] = None
    failed_at: Optional[datetime] = None
    created_at: datetime


class UserBillingResponse(CamelModel):
    subscription_status: Optional[str] = None
    plan: str
    current_period_start: Optional[datetime] = None
    current_period_end: Optional[datetime] = None
    trial_end: Optional[datetime] = None
    cancel_at_period_end: bool = False
    payments: List[BillingItem]
    total_paid_cents: int
    total_payments: int


class ErrorItem(CamelModel):
    id: str
    type: str  # research, preparation, followup, knowledge_base
    title: str
    error_message: Optional[str] = None
    created_at: datetime


class UserErrorsResponse(CamelModel):
    errors: List[ErrorItem]
    total: int
    error_rate_7d: float
    error_rate_30d: float


class HealthBreakdown(CamelModel):
    activity_score: int  # 0-30 points
    error_score: int  # 0-25 points
    usage_score: int  # 0-15 points
    profile_score: int  # 0-10 points
    payment_score: int  # 0-20 points
    total_score: int
    status: str


# Request Models

class ResetFlowsRequest(BaseModel):
    reason: str


class AddFlowsRequest(BaseModel):
    flows: int
    reason: str


class ExtendTrialRequest(BaseModel):
    days: int
    reason: str


# ============================================================
# Endpoints
# ============================================================

@router.get("", response_model=UserListResponse)
async def list_users(
    search: Optional[str] = Query(None, description="Search by email, name, or org"),
    plan: Optional[str] = Query(None, description="Filter by plan"),
    health_status: Optional[str] = Query(None, description="Filter by health status"),
    sort_by: str = Query("created_at", description="Sort field"),
    sort_order: str = Query("desc", description="Sort order: asc or desc"),
    offset: int = Query(0, ge=0),
    limit: int = Query(25, ge=1, le=100),
    admin: AdminContext = Depends(get_admin_user)
):
    """
    List all users with pagination and filtering.
    
    Filters:
    - search: Search in email, name, organization name
    - plan: Filter by subscription plan
    - health_status: 'healthy', 'at_risk', 'critical'
    
    Sorting:
    - created_at, last_active, email
    """
    supabase = get_supabase_service()
    
    # Build base query - get all users with their org membership
    query = supabase.table("users").select(
        "id, email, full_name, created_at",
        count="exact"
    )
    
    # Get users first
    users_result = query.range(offset, offset + limit - 1).execute()
    
    if not users_result.data:
        return UserListResponse(users=[], total=0, offset=offset, limit=limit)
    
    # Enrich with organization and subscription data
    enriched_users = []
    for user in users_result.data:
        user_data = await _enrich_user_data(supabase, user)
        
        # Apply filters
        if plan and user_data.get("plan") != plan:
            continue
        
        if health_status:
            health_data = await _get_health_data(supabase, user["id"])
            score = calculate_health_score(health_data)
            status = get_health_status(score)
            if status != health_status:
                continue
            user_data["health_score"] = score
            user_data["health_status"] = status
        else:
            health_data = await _get_health_data(supabase, user["id"])
            score = calculate_health_score(health_data)
            user_data["health_score"] = score
            user_data["health_status"] = get_health_status(score)
        
        if search:
            search_lower = search.lower()
            if not (
                search_lower in user.get("email", "").lower() or
                search_lower in (user.get("full_name") or "").lower() or
                search_lower in (user_data.get("organization_name") or "").lower()
            ):
                continue
        
        enriched_users.append(AdminUserListItem(
            id=user["id"],
            email=user["email"],
            full_name=user.get("full_name"),
            organization_id=user_data.get("organization_id"),
            organization_name=user_data.get("organization_name"),
            plan=user_data.get("plan", "free"),
            flow_usage=FlowUsage(
                used=user_data.get("flow_count", 0),
                limit=user_data.get("flow_limit", 2),
                pack_balance=user_data.get("pack_balance", 0)
            ),
            health_score=user_data.get("health_score", 0),
            health_status=user_data.get("health_status", "healthy"),
            last_active=user_data.get("last_active"),
            created_at=user["created_at"]
        ))
    
    return UserListResponse(
        users=enriched_users,
        total=users_result.count or len(enriched_users),
        offset=offset,
        limit=limit
    )


@router.get("/{user_id}", response_model=AdminUserDetail)
async def get_user_detail(
    user_id: str,
    request: Request,
    admin: AdminContext = Depends(get_admin_user)
):
    """Get detailed information about a specific user."""
    supabase = get_supabase_service()
    
    # Get user
    user_result = supabase.table("users") \
        .select("*") \
        .eq("id", user_id) \
        .maybe_single() \
        .execute()
    
    if not user_result.data:
        raise HTTPException(status_code=404, detail="User not found")
    
    user = user_result.data
    
    # Log the view action
    await log_admin_action(
        admin_id=admin.admin_id,
        action="user.view",
        target_type="user",
        target_id=UUID(user_id),
        target_identifier=user["email"],
        request=request
    )
    
    # Get enriched data
    user_data = await _enrich_user_data(supabase, user)
    health_data = await _get_health_data(supabase, user_id)
    score = calculate_health_score(health_data)
    
    # Get flow packs
    packs_result = supabase.table("flow_packs") \
        .select("id, flows_purchased, flows_remaining, purchased_at, status") \
        .eq("organization_id", user_data.get("organization_id")) \
        .order("purchased_at", desc=True) \
        .limit(10) \
        .execute()
    
    flow_packs = [
        FlowPackInfo(
            id=p["id"],
            flows_purchased=p["flows_purchased"],
            flows_remaining=p["flows_remaining"],
            purchased_at=p["purchased_at"],
            status=p["status"]
        ) for p in (packs_result.data or [])
    ]
    
    # Get admin notes
    notes_result = supabase.table("admin_notes") \
        .select("id, content, is_pinned, created_at, admin_users(user_id)") \
        .eq("target_type", "user") \
        .eq("target_id", user_id) \
        .order("is_pinned", desc=True) \
        .order("created_at", desc=True) \
        .limit(20) \
        .execute()
    
    # Batch fetch admin emails to avoid N+1 queries
    admin_user_ids = set()
    for note in (notes_result.data or []):
        if note.get("admin_users") and note["admin_users"].get("user_id"):
            admin_user_ids.add(note["admin_users"]["user_id"])
    
    admin_emails = {}
    if admin_user_ids:
        emails_result = supabase.table("users") \
            .select("id, email") \
            .in_("id", list(admin_user_ids)) \
            .execute()
        for u in (emails_result.data or []):
            admin_emails[u["id"]] = u["email"]
    
    admin_notes = []
    for note in (notes_result.data or []):
        admin_user_id = note["admin_users"]["user_id"] if note.get("admin_users") else None
        admin_email = admin_emails.get(admin_user_id, "Unknown")
        
        admin_notes.append(AdminNoteInfo(
            id=note["id"],
            content=note["content"],
            is_pinned=note["is_pinned"],
            admin_name=admin_email,
            created_at=note["created_at"]
        ))
    
    # Get activity counts
    research_count = supabase.table("research_briefs") \
        .select("id", count="exact") \
        .eq("organization_id", user_data.get("organization_id")) \
        .execute()
    
    prep_count = supabase.table("meeting_preps") \
        .select("id", count="exact") \
        .eq("organization_id", user_data.get("organization_id")) \
        .execute()
    
    followup_count = supabase.table("followups") \
        .select("id", count="exact") \
        .eq("organization_id", user_data.get("organization_id")) \
        .execute()
    
    return AdminUserDetail(
        id=user["id"],
        email=user["email"],
        full_name=user.get("full_name"),
        organization_id=user_data.get("organization_id"),
        organization_name=user_data.get("organization_name"),
        plan=user_data.get("plan", "free"),
        flow_usage=FlowUsage(
            used=user_data.get("flow_count", 0),
            limit=user_data.get("flow_limit", 2),
            pack_balance=user_data.get("pack_balance", 0)
        ),
        health_score=score,
        health_status=get_health_status(score),
        last_active=user_data.get("last_active"),
        created_at=user["created_at"],
        stripe_customer_id=user_data.get("stripe_customer_id"),
        subscription_status=user_data.get("subscription_status"),
        trial_ends_at=user_data.get("trial_ends_at"),
        profile_completeness=health_data.get("profile_completeness", 0),
        total_researches=research_count.count or 0,
        total_preps=prep_count.count or 0,
        total_followups=followup_count.count or 0,
        error_count_30d=health_data.get("error_count_30d", 0),
        flow_packs=flow_packs,
        admin_notes=admin_notes
    )


@router.get("/{user_id}/activity", response_model=UserActivityResponse)
async def get_user_activity(
    user_id: str,
    limit: int = Query(50, ge=1, le=200),
    admin: AdminContext = Depends(get_admin_user)
):
    """Get activity timeline for a user."""
    supabase = get_supabase_service()
    
    # Get organization
    org_result = supabase.table("organization_members") \
        .select("organization_id") \
        .eq("user_id", user_id) \
        .maybe_single() \
        .execute()
    
    if not org_result.data:
        return UserActivityResponse(activities=[], total=0)
    
    org_id = org_result.data["organization_id"]
    
    activities = []
    
    # Get recent researches (uses 'company_name' not 'prospect_company_name')
    try:
        researches = supabase.table("research_briefs") \
            .select("id, company_name, status, created_at") \
            .eq("organization_id", org_id) \
            .order("created_at", desc=True) \
            .limit(limit // 3) \
            .execute()
        
        for r in (researches.data or []):
            company = r.get("company_name", "Unknown")
            activities.append(ActivityItem(
                id=f"research-{r['id']}",
                type="research",
                description=f"Research on {company} - {r['status']}",
                created_at=r["created_at"],
                metadata={"company": company, "status": r["status"]}
            ))
    except Exception as e:
        print(f"Error fetching researches: {e}")
    
    # Get recent preps
    try:
        preps = supabase.table("meeting_preps") \
            .select("id, prospect_company_name, status, created_at") \
            .eq("organization_id", org_id) \
            .order("created_at", desc=True) \
            .limit(limit // 3) \
            .execute()
        
        for p in (preps.data or []):
            company = p.get("prospect_company_name", "Unknown")
            activities.append(ActivityItem(
                id=f"prep-{p['id']}",
                type="preparation",
                description=f"Prep for {company} - {p['status']}",
                created_at=p["created_at"],
                metadata={"company": company, "status": p["status"]}
            ))
    except Exception as e:
        print(f"Error fetching preps: {e}")
    
    # Get recent followups
    try:
        followups = supabase.table("followups") \
            .select("id, prospect_company_name, status, created_at") \
            .eq("organization_id", org_id) \
            .order("created_at", desc=True) \
            .limit(limit // 3) \
            .execute()
        
        for f in (followups.data or []):
            company = f.get("prospect_company_name", "Unknown")
            activities.append(ActivityItem(
                id=f"followup-{f['id']}",
                type="followup",
                description=f"Follow-up for {company} - {f['status']}",
                created_at=f["created_at"],
                metadata={"company": company, "status": f["status"]}
            ))
    except Exception as e:
        print(f"Error fetching followups: {e}")
    
    # Sort by created_at
    activities.sort(key=lambda x: x.created_at, reverse=True)
    
    return UserActivityResponse(
        activities=activities[:limit],
        total=len(activities)
    )


@router.post("/{user_id}/reset-flows")
async def reset_user_flows(
    user_id: str,
    data: ResetFlowsRequest,
    request: Request,
    admin: AdminContext = Depends(require_admin_role("super_admin", "admin", "support"))
):
    """Reset a user's monthly flow count to 0."""
    supabase = get_supabase_service()
    
    # Get user email for logging
    user = supabase.table("users").select("email").eq("id", user_id).maybe_single().execute()
    if not user.data:
        raise HTTPException(status_code=404, detail="User not found")
    
    # Get organization
    org_result = supabase.table("organization_members") \
        .select("organization_id") \
        .eq("user_id", user_id) \
        .maybe_single() \
        .execute()
    
    if not org_result.data:
        raise HTTPException(status_code=404, detail="User has no organization")
    
    org_id = org_result.data["organization_id"]
    
    # Get current flow count for logging
    usage_result = supabase.table("usage_records") \
        .select("flow_count") \
        .eq("organization_id", org_id) \
        .gte("period_start", datetime.utcnow().replace(day=1).isoformat()) \
        .maybe_single() \
        .execute()
    
    old_count = usage_result.data["flow_count"] if usage_result.data else 0
    
    # Reset flows
    supabase.table("usage_records") \
        .update({"flow_count": 0, "updated_at": datetime.utcnow().isoformat()}) \
        .eq("organization_id", org_id) \
        .gte("period_start", datetime.utcnow().replace(day=1).isoformat()) \
        .execute()
    
    # Log action
    await log_admin_action(
        admin_id=admin.admin_id,
        action="user.reset_flows",
        target_type="user",
        target_id=UUID(user_id),
        target_identifier=user.data["email"],
        details={"old_count": old_count, "reason": data.reason},
        request=request
    )
    
    return {"success": True, "message": f"Reset flow count from {old_count} to 0"}


@router.post("/{user_id}/add-flows")
async def add_user_flows(
    user_id: str,
    data: AddFlowsRequest,
    request: Request,
    admin: AdminContext = Depends(require_admin_role("super_admin", "admin"))
):
    """Add bonus flows to a user (creates a flow pack)."""
    supabase = get_supabase_service()
    
    if data.flows < 1 or data.flows > 100:
        raise HTTPException(status_code=400, detail="Flows must be between 1 and 100")
    
    # Get user email for logging
    user = supabase.table("users").select("email").eq("id", user_id).maybe_single().execute()
    if not user.data:
        raise HTTPException(status_code=404, detail="User not found")
    
    # Get organization
    org_result = supabase.table("organization_members") \
        .select("organization_id") \
        .eq("user_id", user_id) \
        .maybe_single() \
        .execute()
    
    if not org_result.data:
        raise HTTPException(status_code=404, detail="User has no organization")
    
    org_id = org_result.data["organization_id"]
    
    # Create a bonus flow pack
    supabase.table("flow_packs").insert({
        "organization_id": org_id,
        "flows_purchased": data.flows,
        "flows_remaining": data.flows,
        "price_cents": 0,  # Free bonus
        "status": "active"
    }).execute()
    
    # Log action
    await log_admin_action(
        admin_id=admin.admin_id,
        action="user.add_flows",
        target_type="user",
        target_id=UUID(user_id),
        target_identifier=user.data["email"],
        details={"flows_added": data.flows, "reason": data.reason},
        request=request
    )
    
    return {"success": True, "message": f"Added {data.flows} bonus flows"}


@router.post("/{user_id}/extend-trial")
async def extend_user_trial(
    user_id: str,
    data: ExtendTrialRequest,
    request: Request,
    admin: AdminContext = Depends(require_admin_role("super_admin", "admin"))
):
    """Extend a user's trial period."""
    supabase = get_supabase_service()
    
    if data.days < 1 or data.days > 90:
        raise HTTPException(status_code=400, detail="Days must be between 1 and 90")
    
    # Get user email
    user = supabase.table("users").select("email").eq("id", user_id).maybe_single().execute()
    if not user.data:
        raise HTTPException(status_code=404, detail="User not found")
    
    # Get organization
    org_result = supabase.table("organization_members") \
        .select("organization_id") \
        .eq("user_id", user_id) \
        .maybe_single() \
        .execute()
    
    if not org_result.data:
        raise HTTPException(status_code=404, detail="User has no organization")
    
    org_id = org_result.data["organization_id"]
    
    # Get current trial end
    sub_result = supabase.table("organization_subscriptions") \
        .select("trial_ends_at") \
        .eq("organization_id", org_id) \
        .maybe_single() \
        .execute()
    
    if not sub_result.data:
        raise HTTPException(status_code=404, detail="No subscription found")
    
    # Calculate new trial end
    current_end = sub_result.data.get("trial_ends_at")
    if current_end:
        from datetime import timedelta
        current_dt = datetime.fromisoformat(current_end.replace("Z", "+00:00"))
        new_end = current_dt + timedelta(days=data.days)
    else:
        from datetime import timedelta
        new_end = datetime.utcnow() + timedelta(days=data.days)
    
    # Update trial end
    supabase.table("organization_subscriptions") \
        .update({"trial_ends_at": new_end.isoformat()}) \
        .eq("organization_id", org_id) \
        .execute()
    
    # Log action
    await log_admin_action(
        admin_id=admin.admin_id,
        action="user.extend_trial",
        target_type="user",
        target_id=UUID(user_id),
        target_identifier=user.data["email"],
        details={
            "days_added": data.days,
            "new_trial_end": new_end.isoformat(),
            "reason": data.reason
        },
        request=request
    )
    
    return {"success": True, "message": f"Extended trial by {data.days} days", "new_end": new_end.isoformat()}


@router.get("/{user_id}/export")
async def export_user_data(
    user_id: str,
    request: Request,
    admin: AdminContext = Depends(require_admin_role("super_admin", "admin"))
):
    """Export all user data as JSON."""
    supabase = get_supabase_service()
    
    # Get user
    user = supabase.table("users").select("*").eq("id", user_id).maybe_single().execute()
    if not user.data:
        raise HTTPException(status_code=404, detail="User not found")
    
    # Get organization
    org_result = supabase.table("organization_members") \
        .select("organization_id, role, organizations(*)") \
        .eq("user_id", user_id) \
        .maybe_single() \
        .execute()
    
    org_id = org_result.data["organization_id"] if org_result.data else None
    
    export_data = {
        "user": user.data,
        "organization": org_result.data if org_result.data else None,
        "exported_at": datetime.utcnow().isoformat(),
        "exported_by": admin.email
    }
    
    if org_id:
        # Get subscription
        sub = supabase.table("organization_subscriptions").select("*").eq("organization_id", org_id).maybe_single().execute()
        export_data["subscription"] = sub.data
        
        # Get usage
        usage = supabase.table("usage_records").select("*").eq("organization_id", org_id).execute()
        export_data["usage_records"] = usage.data
        
        # Get flow packs
        packs = supabase.table("flow_packs").select("*").eq("organization_id", org_id).execute()
        export_data["flow_packs"] = packs.data
        
        # Get sales profile
        profile = supabase.table("sales_profiles").select("*").eq("organization_id", org_id).maybe_single().execute()
        export_data["sales_profile"] = profile.data
    
    # Log action
    await log_admin_action(
        admin_id=admin.admin_id,
        action="user.export",
        target_type="user",
        target_id=UUID(user_id),
        target_identifier=user.data["email"],
        request=request
    )
    
    return export_data


@router.get("/{user_id}/billing", response_model=UserBillingResponse)
async def get_user_billing(
    user_id: str,
    admin: AdminContext = Depends(require_admin_role("super_admin", "admin"))
):
    """Get billing/payment history for a user."""
    supabase = get_supabase_service()
    
    # Get organization
    org_result = supabase.table("organization_members") \
        .select("organization_id") \
        .eq("user_id", user_id) \
        .maybe_single() \
        .execute()
    
    if not org_result.data:
        return UserBillingResponse(
            plan="free",
            payments=[],
            total_paid_cents=0,
            total_payments=0
        )
    
    org_id = org_result.data["organization_id"]
    
    # Get subscription details
    sub_result = supabase.table("organization_subscriptions") \
        .select("plan_id, status, current_period_start, current_period_end, trial_end, cancel_at_period_end") \
        .eq("organization_id", org_id) \
        .maybe_single() \
        .execute()
    
    subscription_status = None
    plan = "free"
    current_period_start = None
    current_period_end = None
    trial_end = None
    cancel_at_period_end = False
    
    if sub_result.data:
        subscription_status = sub_result.data.get("status")
        plan = sub_result.data.get("plan_id", "free")
        current_period_start = sub_result.data.get("current_period_start")
        current_period_end = sub_result.data.get("current_period_end")
        trial_end = sub_result.data.get("trial_end")
        cancel_at_period_end = sub_result.data.get("cancel_at_period_end", False)
    
    # Get payment history
    payments_result = supabase.table("payment_history") \
        .select("id, amount_cents, currency, status, invoice_number, invoice_pdf_url, paid_at, failed_at, created_at") \
        .eq("organization_id", org_id) \
        .order("created_at", desc=True) \
        .limit(50) \
        .execute()
    
    payments = []
    total_paid_cents = 0
    for p in (payments_result.data or []):
        payments.append(BillingItem(
            id=p["id"],
            amount_cents=p["amount_cents"],
            currency=p.get("currency", "eur"),
            status=p["status"],
            invoice_number=p.get("invoice_number"),
            invoice_pdf_url=p.get("invoice_pdf_url"),
            paid_at=p.get("paid_at"),
            failed_at=p.get("failed_at"),
            created_at=p["created_at"]
        ))
        if p["status"] == "paid":
            total_paid_cents += p["amount_cents"]
    
    return UserBillingResponse(
        subscription_status=subscription_status,
        plan=plan,
        current_period_start=current_period_start,
        current_period_end=current_period_end,
        trial_end=trial_end,
        cancel_at_period_end=cancel_at_period_end,
        payments=payments,
        total_paid_cents=total_paid_cents,
        total_payments=len(payments)
    )


@router.get("/{user_id}/errors", response_model=UserErrorsResponse)
async def get_user_errors(
    user_id: str,
    limit: int = Query(50, ge=1, le=200),
    admin: AdminContext = Depends(get_admin_user)
):
    """Get failed jobs/errors for a user."""
    supabase = get_supabase_service()
    from datetime import timedelta
    
    # Get organization
    org_result = supabase.table("organization_members") \
        .select("organization_id") \
        .eq("user_id", user_id) \
        .maybe_single() \
        .execute()
    
    if not org_result.data:
        return UserErrorsResponse(errors=[], total=0, error_rate_7d=0.0, error_rate_30d=0.0)
    
    org_id = org_result.data["organization_id"]
    errors = []
    
    # Date thresholds
    now = datetime.utcnow()
    seven_days_ago = (now - timedelta(days=7)).isoformat()
    thirty_days_ago = (now - timedelta(days=30)).isoformat()
    
    # Track counts for error rates
    total_7d = 0
    failed_7d = 0
    total_30d = 0
    failed_30d = 0
    
    # Get failed research briefs
    try:
        research_result = supabase.table("research_briefs") \
            .select("id, company_name, status, created_at") \
            .eq("organization_id", org_id) \
            .eq("status", "failed") \
            .order("created_at", desc=True) \
            .limit(limit // 4) \
            .execute()
        
        for r in (research_result.data or []):
            errors.append(ErrorItem(
                id=r["id"],
                type="research",
                title=f"Research: {r.get('company_name', 'Unknown')}",
                error_message=None,  # research_briefs doesn't have error_message column
                created_at=r["created_at"]
            ))
    except Exception as e:
        print(f"Error fetching failed research: {e}")
    
    # Get failed meeting preps
    try:
        prep_result = supabase.table("meeting_preps") \
            .select("id, prospect_company_name, status, error_message, created_at") \
            .eq("organization_id", org_id) \
            .eq("status", "failed") \
            .order("created_at", desc=True) \
            .limit(limit // 4) \
            .execute()
        
        for p in (prep_result.data or []):
            errors.append(ErrorItem(
                id=p["id"],
                type="preparation",
                title=f"Preparation: {p.get('prospect_company_name', 'Unknown')}",
                error_message=p.get("error_message"),
                created_at=p["created_at"]
            ))
    except Exception as e:
        print(f"Error fetching failed preps: {e}")
    
    # Get failed followups
    try:
        followup_result = supabase.table("followups") \
            .select("id, prospect_company_name, status, error_message, created_at") \
            .eq("organization_id", org_id) \
            .eq("status", "failed") \
            .order("created_at", desc=True) \
            .limit(limit // 4) \
            .execute()
        
        for f in (followup_result.data or []):
            errors.append(ErrorItem(
                id=f["id"],
                type="followup",
                title=f"Follow-up: {f.get('prospect_company_name', 'Unknown')}",
                error_message=f.get("error_message"),
                created_at=f["created_at"]
            ))
    except Exception as e:
        print(f"Error fetching failed followups: {e}")
    
    # Get failed knowledge base files
    try:
        kb_result = supabase.table("knowledge_base_files") \
            .select("id, file_name, status, error_message, created_at") \
            .eq("organization_id", org_id) \
            .eq("status", "failed") \
            .order("created_at", desc=True) \
            .limit(limit // 4) \
            .execute()
        
        for k in (kb_result.data or []):
            errors.append(ErrorItem(
                id=k["id"],
                type="knowledge_base",
                title=f"KB File: {k.get('file_name', 'Unknown')}",
                error_message=k.get("error_message"),
                created_at=k["created_at"]
            ))
    except Exception as e:
        print(f"Error fetching failed KB files: {e}")
    
    # Calculate error rates
    try:
        # 7 day stats
        for table in ["research_briefs", "meeting_preps", "followups"]:
            try:
                result = supabase.table(table) \
                    .select("status", count="exact") \
                    .eq("organization_id", org_id) \
                    .gte("created_at", seven_days_ago) \
                    .execute()
                total_7d += result.count or 0
                
                failed_result = supabase.table(table) \
                    .select("id", count="exact") \
                    .eq("organization_id", org_id) \
                    .eq("status", "failed") \
                    .gte("created_at", seven_days_ago) \
                    .execute()
                failed_7d += failed_result.count or 0
            except Exception:
                pass
        
        # 30 day stats
        for table in ["research_briefs", "meeting_preps", "followups"]:
            try:
                result = supabase.table(table) \
                    .select("status", count="exact") \
                    .eq("organization_id", org_id) \
                    .gte("created_at", thirty_days_ago) \
                    .execute()
                total_30d += result.count or 0
                
                failed_result = supabase.table(table) \
                    .select("id", count="exact") \
                    .eq("organization_id", org_id) \
                    .eq("status", "failed") \
                    .gte("created_at", thirty_days_ago) \
                    .execute()
                failed_30d += failed_result.count or 0
            except Exception:
                pass
    except Exception as e:
        print(f"Error calculating error rates: {e}")
    
    error_rate_7d = (failed_7d / total_7d * 100) if total_7d > 0 else 0.0
    error_rate_30d = (failed_30d / total_30d * 100) if total_30d > 0 else 0.0
    
    # Sort by created_at
    errors.sort(key=lambda x: x.created_at, reverse=True)
    
    return UserErrorsResponse(
        errors=errors[:limit],
        total=len(errors),
        error_rate_7d=round(error_rate_7d, 1),
        error_rate_30d=round(error_rate_30d, 1)
    )


@router.get("/{user_id}/health-breakdown", response_model=HealthBreakdown)
async def get_user_health_breakdown(
    user_id: str,
    admin: AdminContext = Depends(get_admin_user)
):
    """Get detailed health score breakdown for a user."""
    supabase = get_supabase_service()
    
    health_data = await _get_health_data(supabase, user_id)
    
    # Calculate individual components (same logic as calculate_health_score but separated)
    activity_score = 30  # Base: 30 points
    error_score = 25  # Base: 25 points
    usage_score = 15  # Base: 15 points
    profile_score = 10  # Base: 10 points
    payment_score = 20  # Base: 20 points
    
    # Inactivity penalty (max -30)
    days_inactive = health_data.get("days_since_last_activity", 0)
    if days_inactive > 30:
        activity_score = 0
    elif days_inactive > 14:
        activity_score = 10
    elif days_inactive > 7:
        activity_score = 20
    
    # Error rate penalty (max -25)
    error_rate = health_data.get("error_rate_30d", 0)
    if error_rate > 0.3:
        error_score = 0
    elif error_rate > 0.2:
        error_score = 10
    elif error_rate > 0.1:
        error_score = 15
    
    # Low usage penalty (max -15) - only for paid plans
    if health_data.get("plan") != "free":
        usage_percent = health_data.get("flow_usage_percent", 0)
        if usage_percent < 0.1:
            usage_score = 0
        elif usage_percent < 0.3:
            usage_score = 5
    
    # Incomplete profile penalty (max -10)
    profile_completeness = health_data.get("profile_completeness", 0)
    if profile_completeness < 50:
        profile_score = 0
    elif profile_completeness < 80:
        profile_score = 5
    
    # Payment issues penalty (max -20)
    if health_data.get("has_failed_payment"):
        payment_score = 0
    
    total_score = activity_score + error_score + usage_score + profile_score + payment_score
    
    status = "healthy" if total_score >= 80 else "at_risk" if total_score >= 50 else "critical"
    
    return HealthBreakdown(
        activity_score=activity_score,
        error_score=error_score,
        usage_score=usage_score,
        profile_score=profile_score,
        payment_score=payment_score,
        total_score=total_score,
        status=status
    )


# ============================================================
# Helper Functions
# ============================================================

async def _enrich_user_data(supabase, user: dict) -> dict:
    """Get organization and subscription data for a user."""
    result = {
        "organization_id": None,
        "organization_name": None,
        "plan": "free",
        "flow_count": 0,
        "flow_limit": 2,
        "pack_balance": 0,
        "subscription_status": None,
        "stripe_customer_id": None,
        "trial_ends_at": None,
        "last_active": None
    }
    
    try:
        # Get organization
        org_result = supabase.table("organization_members") \
            .select("organization_id, organizations(name)") \
            .eq("user_id", user["id"]) \
            .maybe_single() \
            .execute()
        
        if org_result and org_result.data:
            result["organization_id"] = org_result.data["organization_id"]
            result["organization_name"] = org_result.data["organizations"]["name"] if org_result.data.get("organizations") else None
            
            org_id = org_result.data["organization_id"]
            
            # Get subscription
            try:
                sub_result = supabase.table("organization_subscriptions") \
                    .select("plan_id, status, stripe_customer_id, trial_ends_at, subscription_plans(features)") \
                    .eq("organization_id", org_id) \
                    .maybe_single() \
                    .execute()
                
                if sub_result and sub_result.data:
                    result["plan"] = sub_result.data.get("plan_id", "free")
                    result["subscription_status"] = sub_result.data.get("status")
                    result["stripe_customer_id"] = sub_result.data.get("stripe_customer_id")
                    result["trial_ends_at"] = sub_result.data.get("trial_ends_at")
                    
                    if sub_result.data.get("subscription_plans"):
                        result["flow_limit"] = sub_result.data["subscription_plans"].get("features", {}).get("flow_limit", 2)
            except Exception:
                pass
            
            # Get usage from usage_records
            try:
                usage_result = supabase.table("usage_records") \
                    .select("flow_count") \
                    .eq("organization_id", org_id) \
                    .gte("period_start", datetime.utcnow().replace(day=1).isoformat()) \
                    .maybe_single() \
                    .execute()
                
                if usage_result and usage_result.data:
                    result["flow_count"] = usage_result.data.get("flow_count", 0)
            except Exception:
                pass
            
            # Get flow pack balance
            try:
                pack_result = supabase.table("flow_packs") \
                    .select("flows_remaining") \
                    .eq("organization_id", org_id) \
                    .eq("status", "active") \
                    .execute()
                
                if pack_result and pack_result.data:
                    result["pack_balance"] = sum(p.get("flows_remaining", 0) for p in pack_result.data)
            except Exception:
                pass
            
            # Get last activity
            try:
                activity_result = supabase.table("prospect_activities") \
                    .select("created_at") \
                    .eq("organization_id", org_id) \
                    .order("created_at", desc=True) \
                    .limit(1) \
                    .execute()
                
                if activity_result and activity_result.data:
                    result["last_active"] = activity_result.data[0].get("created_at")
            except Exception:
                pass
    except Exception as e:
        # Log but don't fail - return basic user data
        print(f"Error enriching user data for {user.get('id')}: {e}")
    
    return result


async def _get_health_data(supabase, user_id: str) -> dict:
    """Get health score data for a user."""
    # Try to use the database function first
    try:
        result = supabase.rpc("get_user_health_data", {"p_user_id": user_id}).execute()
        if result.data and "error" not in result.data:
            return result.data
    except Exception:
        pass
    
    # Fallback to manual calculation with REAL data
    health_data = {
        "plan": "free",
        "days_since_last_activity": 999,
        "error_count_30d": 0,
        "error_rate_30d": 0.0,
        "flow_usage_percent": 0,
        "profile_completeness": 0,
        "has_failed_payment": False
    }
    
    try:
        # Get organization ID
        org_result = supabase.table("organization_members") \
            .select("organization_id") \
            .eq("user_id", user_id) \
            .maybe_single() \
            .execute()
        
        if not org_result or not org_result.data:
            return health_data
        
        org_id = org_result.data["organization_id"]
        
        # Get plan from subscription
        try:
            sub_result = supabase.table("organization_subscriptions") \
                .select("plan_id") \
                .eq("organization_id", org_id) \
                .maybe_single() \
                .execute()
            if sub_result and sub_result.data:
                health_data["plan"] = sub_result.data.get("plan_id", "free")
        except Exception:
            pass
        
        # Get days since last activity
        try:
            activity_result = supabase.table("prospect_activities") \
                .select("created_at") \
                .eq("organization_id", org_id) \
                .order("created_at", desc=True) \
                .limit(1) \
                .execute()
            
            if activity_result and activity_result.data:
                from dateutil.parser import parse
                last_activity = parse(activity_result.data[0]["created_at"])
                days_diff = (datetime.utcnow() - last_activity.replace(tzinfo=None)).days
                health_data["days_since_last_activity"] = max(0, days_diff)
            else:
                # Check research_briefs as fallback
                research_result = supabase.table("research_briefs") \
                    .select("created_at") \
                    .eq("organization_id", org_id) \
                    .order("created_at", desc=True) \
                    .limit(1) \
                    .execute()
                if research_result and research_result.data:
                    from dateutil.parser import parse
                    last_activity = parse(research_result.data[0]["created_at"])
                    days_diff = (datetime.utcnow() - last_activity.replace(tzinfo=None)).days
                    health_data["days_since_last_activity"] = max(0, days_diff)
        except Exception:
            pass
        
        # Get error count and rate (failed research_briefs, meeting_preps, followups in last 30 days)
        try:
            thirty_days_ago = (datetime.utcnow() - timedelta(days=30)).isoformat()
            error_count = 0
            total_count = 0
            
            # Count research briefs (total and failed)
            research_total = supabase.table("research_briefs") \
                .select("id", count="exact") \
                .eq("organization_id", org_id) \
                .gte("created_at", thirty_days_ago) \
                .execute()
            if research_total:
                total_count += research_total.count or 0
            
            research_errors = supabase.table("research_briefs") \
                .select("id", count="exact") \
                .eq("organization_id", org_id) \
                .eq("status", "failed") \
                .gte("created_at", thirty_days_ago) \
                .execute()
            if research_errors:
                error_count += research_errors.count or 0
            
            # Count meeting preps (total and failed)
            prep_total = supabase.table("meeting_preps") \
                .select("id", count="exact") \
                .eq("organization_id", org_id) \
                .gte("created_at", thirty_days_ago) \
                .execute()
            if prep_total:
                total_count += prep_total.count or 0
            
            prep_errors = supabase.table("meeting_preps") \
                .select("id", count="exact") \
                .eq("organization_id", org_id) \
                .eq("status", "failed") \
                .gte("created_at", thirty_days_ago) \
                .execute()
            if prep_errors:
                error_count += prep_errors.count or 0
            
            # Count followups (total and failed)
            followup_total = supabase.table("followups") \
                .select("id", count="exact") \
                .eq("organization_id", org_id) \
                .gte("created_at", thirty_days_ago) \
                .execute()
            if followup_total:
                total_count += followup_total.count or 0
            
            followup_errors = supabase.table("followups") \
                .select("id", count="exact") \
                .eq("organization_id", org_id) \
                .eq("status", "failed") \
                .gte("created_at", thirty_days_ago) \
                .execute()
            if followup_errors:
                error_count += followup_errors.count or 0
            
            health_data["error_count_30d"] = error_count
            # Calculate error rate as a percentage (0-1 scale for the health calc)
            if total_count > 0:
                health_data["error_rate_30d"] = error_count / total_count
            else:
                health_data["error_rate_30d"] = 0.0
        except Exception:
            pass
        
        # Get flow usage percentage from usage_records and subscription_plans
        try:
            # Get current month's flow count
            current_month_start = datetime.utcnow().replace(day=1, hour=0, minute=0, second=0, microsecond=0)
            usage_result = supabase.table("usage_records") \
                .select("flow_count") \
                .eq("organization_id", org_id) \
                .gte("period_start", current_month_start.isoformat()) \
                .maybe_single() \
                .execute()
            
            flow_count = (usage_result.data or {}).get("flow_count", 0) or 0
            
            # Get flow limit from subscription
            sub_result = supabase.table("organization_subscriptions") \
                .select("subscription_plans(features)") \
                .eq("organization_id", org_id) \
                .in_("status", ["active", "trialing"]) \
                .maybe_single() \
                .execute()
            
            features = ((sub_result.data or {}).get("subscription_plans") or {}).get("features") or {}
            flow_limit = features.get("flow_limit", 2) or 2
            
            if flow_limit > 0:
                health_data["flow_usage_percent"] = round((flow_count / flow_limit) * 100, 1)
        except Exception:
            pass
        
        # Get profile completeness from sales_profiles
        try:
            profile_result = supabase.table("sales_profiles") \
                .select("profile_completeness") \
                .eq("user_id", user_id) \
                .maybe_single() \
                .execute()
            
            if profile_result and profile_result.data:
                health_data["profile_completeness"] = profile_result.data.get("profile_completeness", 0) or 0
            else:
                # Calculate completeness based on user data
                user_result = supabase.table("users") \
                    .select("full_name, email") \
                    .eq("id", user_id) \
                    .maybe_single() \
                    .execute()
                
                completeness = 0
                if user_result and user_result.data:
                    if user_result.data.get("email"):
                        completeness += 20
                    if user_result.data.get("full_name"):
                        completeness += 20
                    # Check if they have any organization
                    completeness += 20  # They have an org
                health_data["profile_completeness"] = completeness
        except Exception:
            pass
        
        # Check for failed payments
        try:
            sub_result = supabase.table("organization_subscriptions") \
                .select("status, stripe_customer_id") \
                .eq("organization_id", org_id) \
                .maybe_single() \
                .execute()
            
            if sub_result and sub_result.data:
                status = sub_result.data.get("status", "")
                health_data["has_failed_payment"] = status in ["past_due", "unpaid", "incomplete"]
        except Exception:
            pass
            
    except Exception as e:
        print(f"Error getting health data for {user_id}: {e}")
    
    return health_data

