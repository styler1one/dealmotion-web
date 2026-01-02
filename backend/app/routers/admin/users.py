"""
Admin Users Router
==================

Endpoints for user management in the admin panel.
"""

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from pydantic import BaseModel
from typing import Optional, List, Any, Dict
from uuid import UUID
from datetime import datetime, timedelta

from app.deps import get_admin_user, require_admin_role, AdminContext
from app.database import get_supabase_service
from .models import CamelModel
from .utils import log_admin_action, calculate_health_score, get_health_status

router = APIRouter(prefix="/users", tags=["admin-users"])


# ============================================================
# Response Models (with camelCase serialization)
# ============================================================


class CreditUsage(CamelModel):
    """Credit usage for a user (renamed from FlowUsage)"""
    used: int
    limit: int
    pack_balance: int


# Alias for backwards compatibility
FlowUsage = CreditUsage


class AdminUserListItem(CamelModel):
    id: str
    email: str
    full_name: Optional[str] = None
    organization_id: Optional[str] = None
    organization_name: Optional[str] = None
    plan: str
    plan_name: Optional[str] = None  # Human-readable plan name
    subscription_status: Optional[str] = None
    is_suspended: bool = False
    credit_usage: CreditUsage  # Renamed from flow_usage
    health_score: int
    health_status: str
    last_active: Optional[datetime] = None
    created_at: datetime
    
    # Backwards compatibility alias
    @property
    def flow_usage(self) -> CreditUsage:
        return self.credit_usage


class CreditPackInfo(CamelModel):
    """Credit pack info (renamed from FlowPackInfo)"""
    id: str
    credits_purchased: int  # Renamed from flows_purchased
    credits_remaining: int  # Renamed from flows_remaining
    purchased_at: datetime
    status: str
    source: str = "purchased"  # 'purchased', 'bonus', 'promotional'


# Alias for backwards compatibility
FlowPackInfo = CreditPackInfo


class AdminNoteInfo(CamelModel):
    id: str
    content: str
    is_pinned: bool
    admin_name: str
    created_at: datetime


class AdminUserDetail(AdminUserListItem):
    stripe_customer_id: Optional[str] = None
    trial_ends_at: Optional[datetime] = None
    profile_completeness: int = 0
    total_researches: int = 0
    total_preps: int = 0
    total_followups: int = 0
    error_count_30d: int = 0
    credit_packs: List[CreditPackInfo] = []  # Renamed from flow_packs
    admin_notes: List[AdminNoteInfo] = []
    suspended_at: Optional[datetime] = None
    suspended_reason: Optional[str] = None
    
    # Backwards compatibility alias
    @property
    def flow_packs(self) -> List[CreditPackInfo]:
        return self.credit_packs


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
    """Reset monthly credit usage"""
    reason: str


class AddFlowsRequest(BaseModel):
    """Add bonus credits (legacy name for backwards compatibility)"""
    flows: int
    reason: str


class AddCreditsRequest(BaseModel):
    """Add bonus credits to user"""
    credits: int
    reason: str


class ExtendTrialRequest(BaseModel):
    """Extend user trial period"""
    days: int
    reason: str


class ChangePlanRequest(BaseModel):
    """Change user subscription plan"""
    plan_id: str
    reason: str


class SuspendUserRequest(BaseModel):
    """Suspend user account"""
    reason: str


class UnsuspendUserRequest(BaseModel):
    """Unsuspend user account"""
    reason: Optional[str] = None


class DeleteUserRequest(BaseModel):
    """Delete user account"""
    reason: str
    confirm: bool = False  # Must be True to proceed


# Available plans for admin to change
AVAILABLE_PLANS = [
    {"id": "free", "name": "Free", "price_cents": 0},
    {"id": "pro_monthly", "name": "Pro (Monthly)", "price_cents": 4995},
    {"id": "pro_yearly", "name": "Pro (Yearly)", "price_cents": 50900},
    {"id": "pro_plus_monthly", "name": "Pro+ (Monthly)", "price_cents": 6995},
    {"id": "pro_plus_yearly", "name": "Pro+ (Yearly)", "price_cents": 71300},
]


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
            plan_name=user_data.get("plan_name"),
            subscription_status=user_data.get("subscription_status"),
            is_suspended=user_data.get("is_suspended", False),
            credit_usage=CreditUsage(
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
    
    # Get credit packs
    packs_result = supabase.table("flow_packs") \
        .select("id, flows_purchased, flows_remaining, purchased_at, status, price_cents") \
        .eq("organization_id", user_data.get("organization_id")) \
        .order("purchased_at", desc=True) \
        .limit(10) \
        .execute()
    
    credit_packs = [
        CreditPackInfo(
            id=p["id"],
            credits_purchased=p["flows_purchased"],
            credits_remaining=p["flows_remaining"],
            purchased_at=p["purchased_at"],
            status=p["status"],
            source="bonus" if p.get("price_cents", 0) == 0 else "purchased"
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
        plan_name=user_data.get("plan_name"),
        subscription_status=user_data.get("subscription_status"),
        is_suspended=user_data.get("is_suspended", False),
        credit_usage=CreditUsage(
            used=user_data.get("flow_count", 0),
            limit=user_data.get("flow_limit", 2),
            pack_balance=user_data.get("pack_balance", 0)
        ),
        health_score=score,
        health_status=get_health_status(score),
        last_active=user_data.get("last_active"),
        created_at=user["created_at"],
        stripe_customer_id=user_data.get("stripe_customer_id"),
        trial_ends_at=user_data.get("trial_ends_at"),
        profile_completeness=health_data.get("profile_completeness", 0),
        total_researches=research_count.count or 0,
        total_preps=prep_count.count or 0,
        total_followups=followup_count.count or 0,
        error_count_30d=health_data.get("error_count_30d", 0),
        credit_packs=credit_packs,
        admin_notes=admin_notes,
        suspended_at=user_data.get("suspended_at"),
        suspended_reason=user_data.get("suspended_reason")
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
        .select("trial_end") \
        .eq("organization_id", org_id) \
        .limit(1) \
        .execute()
    
    if not sub_result.data or len(sub_result.data) == 0:
        raise HTTPException(status_code=404, detail="No subscription found")
    
    # Calculate new trial end
    current_end = sub_result.data[0].get("trial_end")
    if current_end:
        current_dt = datetime.fromisoformat(current_end.replace("Z", "+00:00"))
        new_end = current_dt + timedelta(days=data.days)
    else:
        new_end = datetime.utcnow() + timedelta(days=data.days)
    
    # Update trial end (column is 'trial_end' not 'trial_ends_at')
    supabase.table("organization_subscriptions") \
        .update({"trial_end": new_end.isoformat()}) \
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
# New Admin Actions: Plan, Suspend, Delete, Credits
# ============================================================


@router.get("/plans/available")
async def get_available_plans(
    admin: AdminContext = Depends(get_admin_user)
):
    """Get list of available subscription plans for admin to assign."""
    return {"plans": AVAILABLE_PLANS}


@router.patch("/{user_id}/plan")
async def change_user_plan(
    user_id: str,
    data: ChangePlanRequest,
    request: Request,
    admin: AdminContext = Depends(require_admin_role("super_admin", "admin"))
):
    """Change a user's subscription plan."""
    supabase = get_supabase_service()
    
    # Validate plan_id
    valid_plans = [p["id"] for p in AVAILABLE_PLANS]
    if data.plan_id not in valid_plans:
        raise HTTPException(status_code=400, detail=f"Invalid plan_id. Must be one of: {', '.join(valid_plans)}")
    
    # Get user
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
    
    # Get current plan for logging
    current_sub = supabase.table("organization_subscriptions") \
        .select("plan_id, status") \
        .eq("organization_id", org_id) \
        .maybe_single() \
        .execute()
    
    old_plan = current_sub.data.get("plan_id", "free") if current_sub.data else "free"
    
    # Update the subscription
    update_data = {
        "plan_id": data.plan_id,
        "updated_at": datetime.utcnow().isoformat()
    }
    
    # If changing from free to paid, set status to active
    if old_plan == "free" and data.plan_id != "free":
        update_data["status"] = "active"
    
    supabase.table("organization_subscriptions") \
        .update(update_data) \
        .eq("organization_id", org_id) \
        .execute()
    
    # Get new plan name for response
    new_plan_name = next((p["name"] for p in AVAILABLE_PLANS if p["id"] == data.plan_id), data.plan_id)
    old_plan_name = next((p["name"] for p in AVAILABLE_PLANS if p["id"] == old_plan), old_plan)
    
    # Log action
    await log_admin_action(
        admin_id=admin.admin_id,
        action="user.change_plan",
        target_type="user",
        target_id=UUID(user_id),
        target_identifier=user.data["email"],
        details={
            "old_plan": old_plan,
            "new_plan": data.plan_id,
            "reason": data.reason
        },
        request=request
    )
    
    return {
        "success": True, 
        "message": f"Changed plan from {old_plan_name} to {new_plan_name}",
        "old_plan": old_plan,
        "new_plan": data.plan_id
    }


@router.post("/{user_id}/add-credits")
async def add_user_credits(
    user_id: str,
    data: AddCreditsRequest,
    request: Request,
    admin: AdminContext = Depends(require_admin_role("super_admin", "admin"))
):
    """Add bonus credits to a user (creates a credit pack)."""
    supabase = get_supabase_service()
    
    if data.credits < 1 or data.credits > 1000:
        raise HTTPException(status_code=400, detail="Credits must be between 1 and 1000")
    
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
    
    # Create a bonus credit pack (stored in flow_packs table)
    supabase.table("flow_packs").insert({
        "organization_id": org_id,
        "flows_purchased": data.credits,
        "flows_remaining": data.credits,
        "price_cents": 0,  # Free bonus
        "status": "active"
    }).execute()
    
    # Log action
    await log_admin_action(
        admin_id=admin.admin_id,
        action="user.add_credits",
        target_type="user",
        target_id=UUID(user_id),
        target_identifier=user.data["email"],
        details={"credits_added": data.credits, "reason": data.reason},
        request=request
    )
    
    return {"success": True, "message": f"Added {data.credits} bonus credits"}


@router.post("/{user_id}/suspend")
async def suspend_user(
    user_id: str,
    data: SuspendUserRequest,
    request: Request,
    admin: AdminContext = Depends(require_admin_role("super_admin", "admin"))
):
    """Suspend a user account (prevents login)."""
    supabase = get_supabase_service()
    
    # Get user - try with is_suspended column, fall back to just email
    try:
        user = supabase.table("users").select("email, is_suspended").eq("id", user_id).maybe_single().execute()
    except Exception:
        # Column might not exist yet
        user = supabase.table("users").select("email").eq("id", user_id).maybe_single().execute()
    
    if not user.data:
        raise HTTPException(status_code=404, detail="User not found")
    
    if user.data.get("is_suspended"):
        raise HTTPException(status_code=400, detail="User is already suspended")
    
    # Get organization
    org_result = supabase.table("organization_members") \
        .select("organization_id") \
        .eq("user_id", user_id) \
        .maybe_single() \
        .execute()
    
    if not org_result.data:
        raise HTTPException(status_code=404, detail="User has no organization")
    
    org_id = org_result.data["organization_id"]
    
    # Update user to suspended (try with new columns, fall back to just updated_at)
    try:
        supabase.table("users") \
            .update({
                "is_suspended": True,
                "suspended_at": datetime.utcnow().isoformat(),
                "suspended_reason": data.reason,
                "updated_at": datetime.utcnow().isoformat()
            }) \
            .eq("id", user_id) \
            .execute()
    except Exception:
        # Columns might not exist yet, just update updated_at
        supabase.table("users") \
            .update({"updated_at": datetime.utcnow().isoformat()}) \
            .eq("id", user_id) \
            .execute()
    
    # Update subscription status to suspended (this always works)
    supabase.table("organization_subscriptions") \
        .update({
            "status": "suspended",
            "updated_at": datetime.utcnow().isoformat()
        }) \
        .eq("organization_id", org_id) \
        .execute()
    
    # Log action
    await log_admin_action(
        admin_id=admin.admin_id,
        action="user.suspend",
        target_type="user",
        target_id=UUID(user_id),
        target_identifier=user.data["email"],
        details={"reason": data.reason},
        request=request
    )
    
    return {"success": True, "message": f"User {user.data['email']} has been suspended"}


@router.post("/{user_id}/unsuspend")
async def unsuspend_user(
    user_id: str,
    data: UnsuspendUserRequest,
    request: Request,
    admin: AdminContext = Depends(require_admin_role("super_admin", "admin"))
):
    """Unsuspend a user account (allows login again)."""
    supabase = get_supabase_service()
    
    # Get user - try with is_suspended column, fall back to just email
    try:
        user = supabase.table("users").select("email, is_suspended").eq("id", user_id).maybe_single().execute()
    except Exception:
        # Column might not exist yet
        user = supabase.table("users").select("email").eq("id", user_id).maybe_single().execute()
    
    if not user.data:
        raise HTTPException(status_code=404, detail="User not found")
    
    # Check subscription status instead if column doesn't exist
    if not user.data.get("is_suspended"):
        # Double check via subscription status
        org_check = supabase.table("organization_members") \
            .select("organization_id") \
            .eq("user_id", user_id) \
            .maybe_single() \
            .execute()
        if org_check.data:
            sub_check = supabase.table("organization_subscriptions") \
                .select("status") \
                .eq("organization_id", org_check.data["organization_id"]) \
                .maybe_single() \
                .execute()
            if not sub_check.data or sub_check.data.get("status") != "suspended":
                raise HTTPException(status_code=400, detail="User is not suspended")
    
    # Get organization
    org_result = supabase.table("organization_members") \
        .select("organization_id") \
        .eq("user_id", user_id) \
        .maybe_single() \
        .execute()
    
    if not org_result.data:
        raise HTTPException(status_code=404, detail="User has no organization")
    
    org_id = org_result.data["organization_id"]
    
    # Update user to unsuspended (try with new columns, fall back to just updated_at)
    try:
        supabase.table("users") \
            .update({
                "is_suspended": False,
                "suspended_at": None,
                "suspended_reason": None,
                "updated_at": datetime.utcnow().isoformat()
            }) \
            .eq("id", user_id) \
            .execute()
    except Exception:
        # Columns might not exist yet, just update updated_at
        supabase.table("users") \
            .update({"updated_at": datetime.utcnow().isoformat()}) \
            .eq("id", user_id) \
            .execute()
    
    # Update subscription status back to active (this always works)
    supabase.table("organization_subscriptions") \
        .update({
            "status": "active",
            "updated_at": datetime.utcnow().isoformat()
        }) \
        .eq("organization_id", org_id) \
        .execute()
    
    # Log action
    await log_admin_action(
        admin_id=admin.admin_id,
        action="user.unsuspend",
        target_type="user",
        target_id=UUID(user_id),
        target_identifier=user.data["email"],
        details={"reason": data.reason} if data.reason else {},
        request=request
    )
    
    return {"success": True, "message": f"User {user.data['email']} has been unsuspended"}


@router.post("/{user_id}/delete")
async def delete_user(
    user_id: str,
    data: DeleteUserRequest,
    request: Request,
    admin: AdminContext = Depends(require_admin_role("super_admin"))
):
    """
    Delete a user account permanently.
    
    This is a destructive action that:
    - Deletes all user data
    - Removes organization (if sole owner)
    - Cancels any active subscriptions
    
    Only super_admin can perform this action.
    Uses POST instead of DELETE to support request body.
    """
    supabase = get_supabase_service()
    
    if not data.confirm:
        raise HTTPException(status_code=400, detail="Must confirm deletion by setting confirm=true")
    
    # Get user
    user = supabase.table("users").select("email").eq("id", user_id).maybe_single().execute()
    if not user.data:
        raise HTTPException(status_code=404, detail="User not found")
    
    user_email = user.data["email"]
    
    # Prevent deleting yourself
    if user_id == admin.user_id:
        raise HTTPException(status_code=400, detail="Cannot delete your own account")
    
    # Get organization
    org_result = supabase.table("organization_members") \
        .select("organization_id, role") \
        .eq("user_id", user_id) \
        .maybe_single() \
        .execute()
    
    org_id = org_result.data["organization_id"] if org_result.data else None
    
    # Log action BEFORE deletion
    await log_admin_action(
        admin_id=admin.admin_id,
        action="user.delete",
        target_type="user",
        target_id=UUID(user_id),
        target_identifier=user_email,
        details={
            "reason": data.reason,
            "organization_id": str(org_id) if org_id else None
        },
        request=request
    )
    
    # Delete order matters due to foreign keys:
    if org_id:
        # 1. Delete research briefs
        supabase.table("research_briefs").delete().eq("organization_id", org_id).execute()
        
        # 2. Delete meeting preps
        supabase.table("meeting_preps").delete().eq("organization_id", org_id).execute()
        
        # 3. Delete followups
        supabase.table("followups").delete().eq("organization_id", org_id).execute()
        
        # 4. Delete prospect activities
        supabase.table("prospect_activities").delete().eq("organization_id", org_id).execute()
        
        # 5. Delete prospect contacts
        supabase.table("prospect_contacts").delete().eq("organization_id", org_id).execute()
        
        # 6. Delete prospect notes
        supabase.table("prospect_notes").delete().eq("organization_id", org_id).execute()
        
        # 7. Delete prospects
        supabase.table("prospects").delete().eq("organization_id", org_id).execute()
        
        # 8. Delete flow packs
        supabase.table("flow_packs").delete().eq("organization_id", org_id).execute()
        
        # 9. Delete usage records
        supabase.table("usage_records").delete().eq("organization_id", org_id).execute()
        
        # 10. Delete subscription
        supabase.table("organization_subscriptions").delete().eq("organization_id", org_id).execute()
        
        # 11. Delete org membership
        supabase.table("organization_members").delete().eq("organization_id", org_id).execute()
        
        # 12. Delete organization
        supabase.table("organizations").delete().eq("id", org_id).execute()
    
    # Delete user-level data
    supabase.table("sales_profiles").delete().eq("user_id", user_id).execute()
    supabase.table("admin_notes").delete().eq("target_type", "user").eq("target_id", user_id).execute()
    
    # Finally, delete the user
    supabase.table("users").delete().eq("id", user_id).execute()
    
    return {
        "success": True, 
        "message": f"User {user_email} and all associated data has been deleted",
        "deleted_user_id": user_id,
        "deleted_organization_id": str(org_id) if org_id else None
    }


# ============================================================
# Helper Functions
# ============================================================

async def _enrich_user_data(supabase, user: dict) -> dict:
    """Get organization and subscription data for a user."""
    # Plan name mapping
    PLAN_NAMES = {
        "free": "Free",
        "pro_monthly": "Pro",
        "pro_yearly": "Pro (Yearly)",
        "pro_plus_monthly": "Pro+",
        "pro_plus_yearly": "Pro+ (Yearly)",
        "enterprise": "Enterprise",
        # Legacy plans
        "pro_solo": "Pro Solo",
        "unlimited_solo": "Unlimited Solo",
        "light_solo": "Light Solo",
    }
    
    result = {
        "organization_id": None,
        "organization_name": None,
        "plan": "free",
        "plan_name": "Free",
        "flow_count": 0,
        "flow_limit": 2,
        "pack_balance": 0,
        "subscription_status": None,
        "stripe_customer_id": None,
        "trial_ends_at": None,
        "last_active": None,
        "is_suspended": False,
        "suspended_at": None,
        "suspended_reason": None,
    }
    
    try:
        # Get organization - Use .limit(1) instead of .maybe_single() to avoid 204 errors
        org_result = supabase.table("organization_members") \
            .select("organization_id, organizations(name)") \
            .eq("user_id", user["id"]) \
            .limit(1) \
            .execute()
        
        if org_result and org_result.data and len(org_result.data) > 0:
            org_data = org_result.data[0]
            result["organization_id"] = org_data["organization_id"]
            result["organization_name"] = org_data["organizations"]["name"] if org_data.get("organizations") else None
            
            org_id = org_data["organization_id"]
            
            # Get subscription - Use .limit(1) instead of .maybe_single() to avoid 204 errors
            try:
                sub_result = supabase.table("organization_subscriptions") \
                    .select("plan_id, status, stripe_customer_id, trial_end, subscription_plans(id, name, features)") \
                    .eq("organization_id", org_id) \
                    .limit(1) \
                    .execute()
                
                if sub_result and sub_result.data and len(sub_result.data) > 0:
                    sub_data = sub_result.data[0]
                    plan_id = sub_data.get("plan_id", "free")
                    result["plan"] = plan_id
                    result["plan_name"] = PLAN_NAMES.get(plan_id, plan_id.replace("_", " ").title())
                    result["subscription_status"] = sub_data.get("status")
                    result["stripe_customer_id"] = sub_data.get("stripe_customer_id")
                    result["trial_ends_at"] = sub_data.get("trial_end")  # Column is 'trial_end' not 'trial_ends_at'
                    
                    # Check if subscription has suspended status
                    if sub_data.get("status") == "suspended":
                        result["is_suspended"] = True
                    
                    # Get plan features for flow limit
                    if sub_data.get("subscription_plans"):
                        features = sub_data["subscription_plans"].get("features", {})
                        if features:
                            result["flow_limit"] = features.get("flow_limit", 2)
                            # -1 means unlimited
                            if result["flow_limit"] == -1:
                                result["flow_limit"] = -1  # Keep -1 to show infinity symbol
            except Exception as e:
                print(f"Error getting subscription for org {org_id}: {e}")
            
            # Get usage from usage_records
            try:
                current_month = datetime.utcnow().replace(day=1, hour=0, minute=0, second=0, microsecond=0)
                usage_result = supabase.table("usage_records") \
                    .select("flow_count") \
                    .eq("organization_id", org_id) \
                    .gte("period_start", current_month.isoformat()) \
                    .limit(1) \
                    .execute()
                
                if usage_result and usage_result.data and len(usage_result.data) > 0:
                    result["flow_count"] = usage_result.data[0].get("flow_count", 0) or 0
            except Exception as e:
                print(f"Error getting usage for org {org_id}: {e}")
            
            # Get credit pack balance
            try:
                pack_result = supabase.table("flow_packs") \
                    .select("flows_remaining") \
                    .eq("organization_id", org_id) \
                    .eq("status", "active") \
                    .gt("flows_remaining", 0) \
                    .execute()
                
                if pack_result and pack_result.data:
                    result["pack_balance"] = sum(p.get("flows_remaining", 0) for p in pack_result.data)
            except Exception as e:
                print(f"Error getting pack balance for org {org_id}: {e}")
            
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
            except Exception as e:
                print(f"Error getting last activity for org {org_id}: {e}")
                
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
            .limit(1) \
            .execute()
        
        if not org_result or not org_result.data or len(org_result.data) == 0:
            return health_data
        
        org_id = org_result.data[0]["organization_id"]
        
        # Get plan from subscription
        try:
            sub_result = supabase.table("organization_subscriptions") \
                .select("plan_id") \
                .eq("organization_id", org_id) \
                .limit(1) \
                .execute()
            if sub_result and sub_result.data and len(sub_result.data) > 0:
                health_data["plan"] = sub_result.data[0].get("plan_id", "free")
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
                .limit(1) \
                .execute()
            
            flow_count = 0
            if usage_result and usage_result.data and len(usage_result.data) > 0:
                flow_count = usage_result.data[0].get("flow_count", 0) or 0
            
            # Get flow limit from subscription
            sub_result = supabase.table("organization_subscriptions") \
                .select("subscription_plans(features)") \
                .eq("organization_id", org_id) \
                .in_("status", ["active", "trialing"]) \
                .limit(1) \
                .execute()
            
            flow_limit = 2
            if sub_result and sub_result.data and len(sub_result.data) > 0:
                features = (sub_result.data[0].get("subscription_plans") or {}).get("features") or {}
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
                .limit(1) \
                .execute()
            
            if profile_result and profile_result.data and len(profile_result.data) > 0:
                health_data["profile_completeness"] = profile_result.data[0].get("profile_completeness", 0) or 0
            else:
                # Calculate completeness based on user data
                user_result = supabase.table("users") \
                    .select("full_name, email") \
                    .eq("id", user_id) \
                    .limit(1) \
                    .execute()
                
                completeness = 0
                if user_result and user_result.data and len(user_result.data) > 0:
                    if user_result.data[0].get("email"):
                        completeness += 20
                    if user_result.data[0].get("full_name"):
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
                .limit(1) \
                .execute()
            
            if sub_result and sub_result.data and len(sub_result.data) > 0:
                status = sub_result.data[0].get("status", "")
                health_data["has_failed_payment"] = status in ["past_due", "unpaid", "incomplete"]
        except Exception:
            pass
            
    except Exception as e:
        print(f"Error getting health data for {user_id}: {e}")
    
    return health_data

