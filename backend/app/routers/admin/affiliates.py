"""
Admin Affiliates Router - Affiliate Management for Admins

Endpoints for viewing, managing, and moderating affiliates.

Access Levels:
- super_admin, admin: Full access including approval/rejection
- support: View and notes
- viewer: Read-only access
"""

import logging
from typing import Optional, List
from datetime import datetime
from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field

from app.deps import get_admin_user, AdminContext, require_admin_role
from app.database import get_supabase_service
from app.services.affiliate_service import get_affiliate_service

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/affiliates", tags=["admin-affiliates"])


# =============================================================================
# Response Models
# =============================================================================

class AffiliateListItem(BaseModel):
    """Affiliate summary for list view."""
    id: str
    user_id: str
    organization_id: str
    affiliate_code: str
    status: str
    stripe_connect_status: str
    stripe_payouts_enabled: bool
    total_clicks: int
    total_signups: int
    total_conversions: int
    total_earned_cents: int
    total_paid_cents: int
    current_balance_cents: int
    created_at: str
    activated_at: Optional[str] = None
    # Joined user info
    user_email: Optional[str] = None
    user_name: Optional[str] = None


class AffiliateListResponse(BaseModel):
    """Paginated affiliate list."""
    affiliates: List[AffiliateListItem]
    total: int
    page: int
    page_size: int


class AffiliateDetailResponse(BaseModel):
    """Full affiliate details."""
    affiliate: dict
    user: dict
    organization: dict
    recent_referrals: list
    recent_commissions: list
    recent_payouts: list
    stats: dict


class UpdateStatusRequest(BaseModel):
    """Request to update affiliate status."""
    status: str = Field(..., description="New status: active, paused, suspended, rejected")
    reason: Optional[str] = Field(None, description="Reason for status change")


class UpdateCommissionRatesRequest(BaseModel):
    """Request to update affiliate commission rates."""
    commission_rate_subscription: Optional[float] = Field(None, ge=0, le=1)
    commission_rate_credits: Optional[float] = Field(None, ge=0, le=1)


class AffiliateStatsResponse(BaseModel):
    """Overall affiliate program statistics."""
    total_affiliates: int
    active_affiliates: int
    pending_affiliates: int
    total_referrals: int
    total_conversions: int
    total_revenue_cents: int
    total_commissions_cents: int
    total_paid_cents: int
    pending_payouts_cents: int


# =============================================================================
# LIST & STATS ENDPOINTS
# =============================================================================

@router.get("", response_model=AffiliateListResponse)
async def list_affiliates(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    status: Optional[str] = Query(None),
    search: Optional[str] = Query(None),
    admin: AdminContext = Depends(get_admin_user)
):
    """
    List all affiliates with pagination and filtering.
    """
    supabase = get_supabase_service()
    
    # Build query - fetch affiliates first
    query = supabase.table("affiliates").select("*", count="exact")
    
    if status:
        query = query.eq("status", status)
    
    if search:
        # Search by affiliate code
        query = query.ilike("affiliate_code", f"%{search}%")
    
    offset = (page - 1) * page_size
    response = query.order(
        "created_at", desc=True
    ).range(offset, offset + page_size - 1).execute()
    
    affiliates = []
    for a in (response.data or []):
        # Fetch user data separately
        user_email = None
        user_name = None
        try:
            user_response = supabase.table("users").select(
                "email, full_name"
            ).eq("id", a["user_id"]).maybe_single().execute()
            if user_response.data:
                user_email = user_response.data.get("email")
                user_name = user_response.data.get("full_name")
            
            # If no name in users table, check sales_profiles
            if not user_name:
                profile_response = supabase.table("sales_profiles").select(
                    "full_name"
                ).eq("user_id", a["user_id"]).maybe_single().execute()
                if profile_response.data:
                    user_name = profile_response.data.get("full_name")
        except Exception as e:
            logger.warning(f"Failed to fetch user for affiliate {a['id']}: {e}")
        
        affiliates.append(AffiliateListItem(
            id=a["id"],
            user_id=a["user_id"],
            organization_id=a["organization_id"],
            affiliate_code=a["affiliate_code"],
            status=a["status"],
            stripe_connect_status=a.get("stripe_connect_status", "not_connected"),
            stripe_payouts_enabled=a.get("stripe_payouts_enabled", False),
            total_clicks=a.get("total_clicks", 0) or 0,
            total_signups=a.get("total_signups", 0) or 0,
            total_conversions=a.get("total_conversions", 0) or 0,
            total_earned_cents=a.get("total_earned_cents", 0) or 0,
            total_paid_cents=a.get("total_paid_cents", 0) or 0,
            current_balance_cents=a.get("current_balance_cents", 0) or 0,
            created_at=a["created_at"],
            activated_at=a.get("activated_at"),
            user_email=user_email,
            user_name=user_name,
        ))
    
    return AffiliateListResponse(
        affiliates=affiliates,
        total=response.count or 0,
        page=page,
        page_size=page_size
    )


@router.get("/stats", response_model=AffiliateStatsResponse)
async def get_program_stats(
    admin: AdminContext = Depends(get_admin_user)
):
    """
    Get overall affiliate program statistics.
    """
    supabase = get_supabase_service()
    
    # Get affiliate counts
    all_affiliates = supabase.table("affiliates").select("id, status", count="exact").execute()
    
    total = all_affiliates.count or 0
    active = sum(1 for a in (all_affiliates.data or []) if a["status"] == "active")
    pending = sum(1 for a in (all_affiliates.data or []) if a["status"] == "pending")
    
    # Get referral counts
    referrals = supabase.table("affiliate_referrals").select("id, converted", count="exact").execute()
    total_referrals = referrals.count or 0
    total_conversions = sum(1 for r in (referrals.data or []) if r["converted"])
    
    # Get commission totals
    commissions = supabase.table("affiliate_commissions").select(
        "payment_amount_cents, commission_amount_cents, status"
    ).execute()
    
    total_revenue = sum(c.get("payment_amount_cents", 0) or 0 for c in (commissions.data or []))
    total_commissions = sum(c.get("commission_amount_cents", 0) or 0 for c in (commissions.data or []))
    
    # Get payout totals
    payouts = supabase.table("affiliate_payouts").select("amount_cents, status").execute()
    total_paid = sum(
        p.get("amount_cents", 0) or 0 
        for p in (payouts.data or []) 
        if p["status"] == "succeeded"
    )
    pending_payouts = sum(
        p.get("amount_cents", 0) or 0 
        for p in (payouts.data or []) 
        if p["status"] in ("pending", "processing")
    )
    
    return AffiliateStatsResponse(
        total_affiliates=total,
        active_affiliates=active,
        pending_affiliates=pending,
        total_referrals=total_referrals,
        total_conversions=total_conversions,
        total_revenue_cents=total_revenue,
        total_commissions_cents=total_commissions,
        total_paid_cents=total_paid,
        pending_payouts_cents=pending_payouts
    )


# =============================================================================
# DETAIL ENDPOINT
# =============================================================================

@router.get("/{affiliate_id}", response_model=AffiliateDetailResponse)
async def get_affiliate_detail(
    affiliate_id: str,
    admin: AdminContext = Depends(get_admin_user)
):
    """
    Get detailed information about a specific affiliate.
    """
    supabase = get_supabase_service()
    affiliate_service = get_affiliate_service()
    
    # Get affiliate
    affiliate_response = supabase.table("affiliates").select("*").eq(
        "id", affiliate_id
    ).single().execute()
    
    if not affiliate_response.data:
        raise HTTPException(status_code=404, detail="Affiliate not found")
    
    affiliate = affiliate_response.data
    
    # Get user
    user_response = supabase.table("users").select(
        "id, email, full_name, created_at"
    ).eq("id", affiliate["user_id"]).single().execute()
    
    # If no name in users table, check sales_profiles
    user_data = user_response.data or {}
    if not user_data.get("full_name"):
        profile_response = supabase.table("sales_profiles").select(
            "full_name"
        ).eq("user_id", affiliate["user_id"]).maybe_single().execute()
        if profile_response.data and profile_response.data.get("full_name"):
            user_data["full_name"] = profile_response.data.get("full_name")
    
    # Get organization
    org_response = supabase.table("organizations").select(
        "id, name, created_at"
    ).eq("id", affiliate["organization_id"]).single().execute()
    
    # Get recent referrals
    referrals_response = supabase.table("affiliate_referrals").select("*").eq(
        "affiliate_id", affiliate_id
    ).order("signup_at", desc=True).limit(10).execute()
    
    # Get recent commissions
    commissions_response = supabase.table("affiliate_commissions").select("*").eq(
        "affiliate_id", affiliate_id
    ).order("payment_at", desc=True).limit(10).execute()
    
    # Get recent payouts
    payouts_response = supabase.table("affiliate_payouts").select("*").eq(
        "affiliate_id", affiliate_id
    ).order("created_at", desc=True).limit(5).execute()
    
    # Calculate stats
    pending_commissions = supabase.table("affiliate_commissions").select(
        "commission_amount_cents"
    ).eq("affiliate_id", affiliate_id).eq("status", "pending").execute()
    
    pending_amount = sum(
        c.get("commission_amount_cents", 0) or 0 
        for c in (pending_commissions.data or [])
    )
    
    stats = {
        "total_clicks": affiliate.get("total_clicks", 0) or 0,
        "total_signups": affiliate.get("total_signups", 0) or 0,
        "total_conversions": affiliate.get("total_conversions", 0) or 0,
        "conversion_rate": round(
            ((affiliate.get("total_conversions", 0) or 0) / 
             (affiliate.get("total_signups", 0) or 1)) * 100, 1
        ) if affiliate.get("total_signups", 0) else 0,
        "total_earned_cents": affiliate.get("total_earned_cents", 0) or 0,
        "total_paid_cents": affiliate.get("total_paid_cents", 0) or 0,
        "current_balance_cents": affiliate.get("current_balance_cents", 0) or 0,
        "pending_commissions_cents": pending_amount,
    }
    
    return AffiliateDetailResponse(
        affiliate=affiliate,
        user=user_data,
        organization=org_response.data or {},
        recent_referrals=referrals_response.data or [],
        recent_commissions=commissions_response.data or [],
        recent_payouts=payouts_response.data or [],
        stats=stats
    )


# =============================================================================
# ACTION ENDPOINTS
# =============================================================================

@router.patch("/{affiliate_id}/status")
async def update_affiliate_status(
    affiliate_id: str,
    request: UpdateStatusRequest,
    admin: AdminContext = Depends(require_admin_role("super_admin", "admin"))
):
    """
    Update affiliate status (approve, pause, suspend, reject).
    """
    if request.status not in ("active", "paused", "suspended", "rejected"):
        raise HTTPException(status_code=400, detail="Invalid status")
    
    affiliate_service = get_affiliate_service()
    
    success = await affiliate_service.update_affiliate_status(
        affiliate_id=affiliate_id,
        status=request.status,
        reason=request.reason,
        admin_id=admin.user_id
    )
    
    if not success:
        raise HTTPException(status_code=500, detail="Failed to update status")
    
    # Log admin action
    supabase = get_supabase_service()
    supabase.table("admin_audit_log").insert({
        "admin_id": admin.admin_id,
        "action": f"affiliate_status_updated",
        "entity_type": "affiliate",
        "entity_id": affiliate_id,
        "details": {
            "new_status": request.status,
            "reason": request.reason
        }
    }).execute()
    
    return {"success": True, "status": request.status}


@router.patch("/{affiliate_id}/commission-rates")
async def update_commission_rates(
    affiliate_id: str,
    request: UpdateCommissionRatesRequest,
    admin: AdminContext = Depends(require_admin_role("super_admin", "admin"))
):
    """
    Update affiliate commission rates (custom rates per affiliate).
    """
    supabase = get_supabase_service()
    
    update_data = {}
    if request.commission_rate_subscription is not None:
        update_data["commission_rate_subscription"] = request.commission_rate_subscription
    if request.commission_rate_credits is not None:
        update_data["commission_rate_credits"] = request.commission_rate_credits
    
    if not update_data:
        raise HTTPException(status_code=400, detail="No rates to update")
    
    supabase.table("affiliates").update(update_data).eq(
        "id", affiliate_id
    ).execute()
    
    # Log admin action
    supabase.table("admin_audit_log").insert({
        "admin_id": admin.admin_id,
        "action": f"affiliate_rates_updated",
        "entity_type": "affiliate",
        "entity_id": affiliate_id,
        "details": update_data
    }).execute()
    
    return {"success": True, "updated": update_data}


@router.post("/{affiliate_id}/trigger-payout")
async def trigger_manual_payout(
    affiliate_id: str,
    admin: AdminContext = Depends(require_admin_role("super_admin"))
):
    """
    Manually trigger a payout for an affiliate (super_admin only).
    """
    affiliate_service = get_affiliate_service()
    
    payout = await affiliate_service.process_payout(affiliate_id)
    
    if not payout:
        raise HTTPException(
            status_code=400, 
            detail="Could not process payout. Check balance and Connect status."
        )
    
    # Log admin action
    supabase = get_supabase_service()
    supabase.table("admin_audit_log").insert({
        "admin_id": admin.admin_id,
        "action": f"affiliate_payout_triggered",
        "entity_type": "affiliate",
        "entity_id": affiliate_id,
        "details": {
            "payout_id": payout["id"],
            "amount_cents": payout["amount_cents"]
        }
    }).execute()
    
    return {"success": True, "payout": payout}


@router.post("/{affiliate_id}/sync-connect")
async def sync_connect_status(
    affiliate_id: str,
    admin: AdminContext = Depends(get_admin_user)
):
    """
    Manually sync Stripe Connect account status.
    """
    affiliate_service = get_affiliate_service()
    
    success = await affiliate_service.sync_connect_account_status(affiliate_id)
    
    if not success:
        raise HTTPException(status_code=500, detail="Failed to sync Connect status")
    
    return {"success": True, "message": "Connect status synced"}

