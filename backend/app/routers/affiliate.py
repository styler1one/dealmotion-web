"""
Affiliate Router - Affiliate Program API

Endpoints for affiliate registration, dashboard, referral tracking,
and Stripe Connect onboarding.

Public endpoints (no auth):
- POST /affiliate/clicks - Track affiliate link clicks
- GET /affiliate/validate/{code} - Validate affiliate code

Authenticated endpoints:
- GET /affiliate/status - Check if current user is an affiliate
- POST /affiliate/apply - Apply to become an affiliate
- GET /affiliate/dashboard - Get affiliate dashboard data
- GET /affiliate/referrals - List referrals with pagination
- GET /affiliate/commissions - List commissions with pagination
- GET /affiliate/payouts - List payouts with pagination
- POST /affiliate/connect/onboarding - Get Stripe Connect onboarding URL
- GET /affiliate/connect/status - Get Stripe Connect status
- PATCH /affiliate/settings - Update affiliate settings
"""

import logging
from typing import Optional, List, Dict, Any
from datetime import datetime
from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel, Field

from app.deps import get_current_user, get_user_org
from app.services.affiliate_service import get_affiliate_service

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/affiliate", tags=["affiliate"])


# =============================================================================
# Request/Response Models
# =============================================================================

class TrackClickRequest(BaseModel):
    """Request to track an affiliate click."""
    affiliate_code: str = Field(..., description="Affiliate referral code (e.g., AFF_X7K2M9)")
    click_id: str = Field(..., description="Client-generated UUID for this click")
    landing_page: Optional[str] = Field(None, description="Page they landed on")
    referrer_url: Optional[str] = Field(None, description="Where they came from")
    utm_source: Optional[str] = Field(None)
    utm_medium: Optional[str] = Field(None)
    utm_campaign: Optional[str] = Field(None)


class TrackClickResponse(BaseModel):
    """Response for click tracking."""
    success: bool
    message: Optional[str] = None


class ValidateCodeResponse(BaseModel):
    """Response for affiliate code validation."""
    valid: bool
    affiliate_name: Optional[str] = None


class AffiliateApplicationRequest(BaseModel):
    """Request to apply as affiliate."""
    application_notes: Optional[str] = Field(
        None, 
        description="Why you want to join and how you'll promote DealMotion",
        max_length=2000
    )


class AffiliateStatusResponse(BaseModel):
    """Response for affiliate status check."""
    is_affiliate: bool
    affiliate: Optional[Dict[str, Any]] = None


class AffiliateStatsResponse(BaseModel):
    """Affiliate statistics."""
    total_clicks: int
    total_signups: int
    total_conversions: int
    conversion_rate: float
    total_earned_cents: int
    total_paid_cents: int
    current_balance_cents: int
    pending_commissions_cents: int


class AffiliateDashboardResponse(BaseModel):
    """Full affiliate dashboard data."""
    affiliate: Dict[str, Any]
    stats: AffiliateStatsResponse
    recent_referrals: List[Dict[str, Any]]
    recent_commissions: List[Dict[str, Any]]
    recent_payouts: List[Dict[str, Any]]


class ReferralResponse(BaseModel):
    """A referral record."""
    id: str
    referred_email: str
    signup_at: str
    converted: bool
    first_payment_at: Optional[str] = None
    lifetime_revenue_cents: int
    lifetime_commission_cents: int
    status: str


class ReferralsListResponse(BaseModel):
    """Paginated referrals list."""
    referrals: List[ReferralResponse]
    total: int
    page: int
    page_size: int
    has_more: bool


class CommissionResponse(BaseModel):
    """A commission record."""
    id: str
    payment_type: str
    payment_amount_cents: int
    commission_amount_cents: int
    status: str
    payment_at: str


class CommissionsListResponse(BaseModel):
    """Paginated commissions list."""
    commissions: List[CommissionResponse]
    total: int
    page: int
    page_size: int
    has_more: bool


class PayoutResponse(BaseModel):
    """A payout record."""
    id: str
    amount_cents: int
    commission_count: int
    status: str
    created_at: str
    completed_at: Optional[str] = None


class PayoutsListResponse(BaseModel):
    """Paginated payouts list."""
    payouts: List[PayoutResponse]
    total: int
    page: int
    page_size: int
    has_more: bool


class ConnectOnboardingRequest(BaseModel):
    """Request for Stripe Connect onboarding URL."""
    return_url: str = Field(..., description="URL to redirect after completion")
    refresh_url: str = Field(..., description="URL if link expires")


class ConnectOnboardingResponse(BaseModel):
    """Response with Stripe Connect onboarding URL."""
    url: str
    expires_in_seconds: int = 300  # Links expire after 5 minutes


class ConnectStatusResponse(BaseModel):
    """Stripe Connect account status."""
    status: str
    payouts_enabled: bool
    charges_enabled: bool
    requirements: Optional[Dict[str, Any]] = None


class UpdateSettingsRequest(BaseModel):
    """Request to update affiliate settings."""
    minimum_payout_cents: Optional[int] = Field(None, ge=1000, le=100000)  # €10-€1000
    payout_frequency: Optional[str] = Field(None)


class UpdateSettingsResponse(BaseModel):
    """Response for settings update."""
    success: bool
    settings: Dict[str, Any]


# =============================================================================
# PUBLIC ENDPOINTS (No Auth)
# =============================================================================

@router.post("/clicks", response_model=TrackClickResponse)
async def track_click(
    request: TrackClickRequest,
    http_request: Request
):
    """
    Track an affiliate link click.
    
    Called from frontend when user lands with ?ref= parameter.
    No authentication required.
    """
    affiliate_service = get_affiliate_service()
    
    # Get IP and user agent for fraud detection
    ip_address = http_request.client.host if http_request.client else None
    user_agent = http_request.headers.get("user-agent")
    
    success = await affiliate_service.track_click(
        affiliate_code=request.affiliate_code,
        click_id=request.click_id,
        landing_page=request.landing_page,
        referrer_url=request.referrer_url,
        ip_address=ip_address,
        user_agent=user_agent,
        utm_source=request.utm_source,
        utm_medium=request.utm_medium,
        utm_campaign=request.utm_campaign
    )
    
    if success:
        return TrackClickResponse(success=True)
    else:
        return TrackClickResponse(
            success=False, 
            message="Invalid affiliate code or rate limit exceeded"
        )


@router.get("/validate/{code}", response_model=ValidateCodeResponse)
async def validate_affiliate_code(code: str):
    """
    Validate if an affiliate code exists and is active.
    
    Used by frontend to show affiliate name on signup page.
    No authentication required.
    """
    affiliate_service = get_affiliate_service()
    
    is_valid, affiliate_name = await affiliate_service.validate_affiliate_code(code)
    
    return ValidateCodeResponse(
        valid=is_valid,
        affiliate_name=affiliate_name
    )


# =============================================================================
# AUTHENTICATED ENDPOINTS
# =============================================================================

class LinkAfterOAuthRequest(BaseModel):
    """Request to link affiliate after OAuth signup."""
    affiliate_code: str = Field(..., description="Affiliate code from localStorage/cookie")
    click_id: Optional[str] = Field(None, description="Click ID if available")


class LinkAfterOAuthResponse(BaseModel):
    """Response for affiliate linking after OAuth."""
    success: bool
    error: Optional[str] = None


@router.post("/link-after-oauth", response_model=LinkAfterOAuthResponse)
async def link_affiliate_after_oauth(
    request: LinkAfterOAuthRequest,
    user_org: tuple = Depends(get_user_org)
):
    """
    Link affiliate referral after OAuth signup.
    
    Called by frontend after successful OAuth login to ensure
    affiliate tracking works even though OAuth can't pass custom metadata.
    
    This endpoint:
    1. Checks if user was already referred (prevents double attribution)
    2. Creates affiliate_referrals record if valid
    3. Updates affiliate stats
    """
    user_id, organization_id = user_org
    affiliate_service = get_affiliate_service()
    
    try:
        # Check if already referred
        from app.database import get_supabase_service
        supabase = get_supabase_service()
        
        existing = supabase.table("affiliate_referrals").select("id").eq(
            "referred_user_id", user_id
        ).maybe_single().execute()
        
        if existing.data:
            return LinkAfterOAuthResponse(
                success=False,
                error="already_referred"
            )
        
        # Validate affiliate code
        is_valid, affiliate_name = await affiliate_service.validate_affiliate_code(
            request.affiliate_code
        )
        
        if not is_valid:
            return LinkAfterOAuthResponse(
                success=False,
                error="invalid_affiliate_code"
            )
        
        # Get affiliate by code
        affiliate = supabase.table("affiliates").select("id, user_id").eq(
            "affiliate_code", request.affiliate_code.upper()
        ).eq("status", "active").maybe_single().execute()
        
        if not affiliate.data:
            return LinkAfterOAuthResponse(
                success=False,
                error="affiliate_not_found"
            )
        
        # Prevent self-referral
        if affiliate.data["user_id"] == user_id:
            return LinkAfterOAuthResponse(
                success=False,
                error="self_referral"
            )
        
        # Get user email for the referral record
        user = supabase.table("users").select("email").eq(
            "id", user_id
        ).maybe_single().execute()
        
        user_email = user.data.get("email") if user.data else None
        
        # Create referral record
        referral_data = {
            "affiliate_id": affiliate.data["id"],
            "referred_user_id": user_id,
            "referred_organization_id": organization_id,
            "referred_email": user_email,
            "signup_at": datetime.utcnow().isoformat(),
            "status": "pending",
        }
        
        # Add click_id if provided
        if request.click_id:
            # Try to find and link the click
            click = supabase.table("affiliate_clicks").select("id").eq(
                "click_id", request.click_id
            ).eq("affiliate_id", affiliate.data["id"]).maybe_single().execute()
            
            if click.data:
                referral_data["click_id"] = click.data["id"]
                # Mark click as converted
                supabase.table("affiliate_clicks").update({
                    "converted_to_signup": True,
                    "signup_user_id": user_id,
                    "converted_at": datetime.utcnow().isoformat()
                }).eq("id", click.data["id"]).execute()
        
        # Insert referral
        supabase.table("affiliate_referrals").insert(referral_data).execute()
        
        # Update affiliate stats
        supabase.table("affiliates").update({
            "total_signups": supabase.table("affiliates").select("total_signups").eq(
                "id", affiliate.data["id"]
            ).single().execute().data.get("total_signups", 0) + 1
        }).eq("id", affiliate.data["id"]).execute()
        
        logger.info(f"Linked affiliate {request.affiliate_code} to user {user_id} via OAuth")
        
        return LinkAfterOAuthResponse(success=True)
        
    except Exception as e:
        logger.error(f"Error linking affiliate after OAuth: {e}")
        return LinkAfterOAuthResponse(
            success=False,
            error="internal_error"
        )


@router.get("/status", response_model=AffiliateStatusResponse)
async def get_affiliate_status(
    user_org: tuple = Depends(get_user_org)
):
    """
    Check if the current user is an affiliate.
    
    Returns affiliate record if they are one, otherwise is_affiliate=False.
    """
    user_id, organization_id = user_org
    affiliate_service = get_affiliate_service()
    
    affiliate = await affiliate_service.get_affiliate_by_user(user_id)
    
    if affiliate:
        return AffiliateStatusResponse(
            is_affiliate=True,
            affiliate={
                "id": affiliate["id"],
                "affiliate_code": affiliate["affiliate_code"],
                "referral_url": f"https://www.dealmotion.ai/signup?ref={affiliate['affiliate_code']}",
                "status": affiliate["status"],
                "stripe_connect_status": affiliate.get("stripe_connect_status", "not_connected"),
                "created_at": affiliate["created_at"],
            }
        )
    else:
        return AffiliateStatusResponse(is_affiliate=False)


@router.post("/apply", response_model=AffiliateStatusResponse)
async def apply_to_become_affiliate(
    request: AffiliateApplicationRequest,
    user_org: tuple = Depends(get_user_org)
):
    """
    Apply to become an affiliate.
    
    Creates a new affiliate record. Depending on configuration,
    the affiliate may be auto-approved or require manual review.
    """
    user_id, organization_id = user_org
    affiliate_service = get_affiliate_service()
    
    try:
        affiliate = await affiliate_service.apply_to_become_affiliate(
            user_id=user_id,
            organization_id=organization_id,
            application_notes=request.application_notes
        )
        
        return AffiliateStatusResponse(
            is_affiliate=True,
            affiliate={
                "id": affiliate["id"],
                "affiliate_code": affiliate["affiliate_code"],
                "referral_url": f"https://www.dealmotion.ai/signup?ref={affiliate['affiliate_code']}",
                "status": affiliate["status"],
                "stripe_connect_status": affiliate.get("stripe_connect_status", "not_connected"),
                "created_at": affiliate["created_at"],
            }
        )
        
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error(f"Error applying as affiliate: {e}")
        raise HTTPException(status_code=500, detail="Could not process application")


@router.get("/dashboard", response_model=AffiliateDashboardResponse)
async def get_dashboard(
    user_org: tuple = Depends(get_user_org)
):
    """
    Get affiliate dashboard data.
    
    Returns stats, recent referrals, commissions, and payouts.
    """
    user_id, organization_id = user_org
    affiliate_service = get_affiliate_service()
    
    # Get affiliate record
    affiliate = await affiliate_service.get_affiliate_by_user(user_id)
    if not affiliate:
        raise HTTPException(status_code=404, detail="Not an affiliate")
    
    # Get dashboard data
    dashboard = await affiliate_service.get_dashboard_data(affiliate["id"])
    
    if not dashboard:
        raise HTTPException(status_code=500, detail="Could not load dashboard")
    
    return AffiliateDashboardResponse(
        affiliate=dashboard["affiliate"],
        stats=AffiliateStatsResponse(**dashboard["stats"]),
        recent_referrals=dashboard["recent_referrals"],
        recent_commissions=dashboard["recent_commissions"],
        recent_payouts=dashboard["recent_payouts"]
    )


@router.get("/referrals", response_model=ReferralsListResponse)
async def get_referrals(
    page: int = 1,
    page_size: int = 20,
    status: Optional[str] = None,
    user_org: tuple = Depends(get_user_org)
):
    """
    Get paginated list of referrals.
    """
    user_id, organization_id = user_org
    affiliate_service = get_affiliate_service()
    
    affiliate = await affiliate_service.get_affiliate_by_user(user_id)
    if not affiliate:
        raise HTTPException(status_code=404, detail="Not an affiliate")
    
    referrals, total = await affiliate_service.get_referrals(
        affiliate_id=affiliate["id"],
        page=page,
        page_size=page_size,
        status=status
    )
    
    return ReferralsListResponse(
        referrals=[ReferralResponse(
            id=r["id"],
            referred_email=r["referred_email"],
            signup_at=r["signup_at"],
            converted=r["converted"],
            first_payment_at=r.get("first_payment_at"),
            lifetime_revenue_cents=r.get("lifetime_revenue_cents", 0) or 0,
            lifetime_commission_cents=r.get("lifetime_commission_cents", 0) or 0,
            status=r["status"]
        ) for r in referrals],
        total=total,
        page=page,
        page_size=page_size,
        has_more=(page * page_size) < total
    )


@router.get("/commissions", response_model=CommissionsListResponse)
async def get_commissions(
    page: int = 1,
    page_size: int = 20,
    status: Optional[str] = None,
    user_org: tuple = Depends(get_user_org)
):
    """
    Get paginated list of commissions.
    """
    user_id, organization_id = user_org
    affiliate_service = get_affiliate_service()
    
    affiliate = await affiliate_service.get_affiliate_by_user(user_id)
    if not affiliate:
        raise HTTPException(status_code=404, detail="Not an affiliate")
    
    commissions, total = await affiliate_service.get_commissions(
        affiliate_id=affiliate["id"],
        page=page,
        page_size=page_size,
        status=status
    )
    
    return CommissionsListResponse(
        commissions=[CommissionResponse(
            id=c["id"],
            payment_type=c["payment_type"],
            payment_amount_cents=c["payment_amount_cents"],
            commission_amount_cents=c["commission_amount_cents"],
            status=c["status"],
            payment_at=c["payment_at"]
        ) for c in commissions],
        total=total,
        page=page,
        page_size=page_size,
        has_more=(page * page_size) < total
    )


@router.get("/payouts", response_model=PayoutsListResponse)
async def get_payouts(
    page: int = 1,
    page_size: int = 20,
    user_org: tuple = Depends(get_user_org)
):
    """
    Get paginated list of payouts.
    """
    user_id, organization_id = user_org
    affiliate_service = get_affiliate_service()
    
    affiliate = await affiliate_service.get_affiliate_by_user(user_id)
    if not affiliate:
        raise HTTPException(status_code=404, detail="Not an affiliate")
    
    payouts, total = await affiliate_service.get_payouts(
        affiliate_id=affiliate["id"],
        page=page,
        page_size=page_size
    )
    
    return PayoutsListResponse(
        payouts=[PayoutResponse(
            id=p["id"],
            amount_cents=p["amount_cents"],
            commission_count=p["commission_count"],
            status=p["status"],
            created_at=p["created_at"],
            completed_at=p.get("completed_at")
        ) for p in payouts],
        total=total,
        page=page,
        page_size=page_size,
        has_more=(page * page_size) < total
    )


# =============================================================================
# STRIPE CONNECT ENDPOINTS
# =============================================================================

@router.post("/connect/onboarding", response_model=ConnectOnboardingResponse)
async def get_connect_onboarding(
    request: ConnectOnboardingRequest,
    user_org: tuple = Depends(get_user_org)
):
    """
    Get Stripe Connect onboarding URL.
    
    Creates a Connect Express account if one doesn't exist,
    then returns the onboarding link.
    """
    user_id, organization_id = user_org
    affiliate_service = get_affiliate_service()
    
    affiliate = await affiliate_service.get_affiliate_by_user(user_id)
    if not affiliate:
        raise HTTPException(status_code=404, detail="Not an affiliate")
    
    if affiliate["status"] != "active":
        raise HTTPException(
            status_code=400, 
            detail="Affiliate account must be active to set up payments"
        )
    
    url = await affiliate_service.get_connect_onboarding_url(
        affiliate_id=affiliate["id"],
        return_url=request.return_url,
        refresh_url=request.refresh_url
    )
    
    if not url:
        raise HTTPException(status_code=500, detail="Could not generate onboarding link")
    
    return ConnectOnboardingResponse(url=url)


@router.get("/connect/status", response_model=ConnectStatusResponse)
async def get_connect_status(
    user_org: tuple = Depends(get_user_org)
):
    """
    Get Stripe Connect account status.
    """
    user_id, organization_id = user_org
    affiliate_service = get_affiliate_service()
    
    affiliate = await affiliate_service.get_affiliate_by_user(user_id)
    if not affiliate:
        raise HTTPException(status_code=404, detail="Not an affiliate")
    
    # Sync status from Stripe
    await affiliate_service.sync_connect_account_status(affiliate["id"])
    
    # Refresh affiliate data
    affiliate = await affiliate_service.get_affiliate_by_user(user_id)
    
    return ConnectStatusResponse(
        status=affiliate.get("stripe_connect_status", "not_connected"),
        payouts_enabled=affiliate.get("stripe_payouts_enabled", False),
        charges_enabled=affiliate.get("stripe_charges_enabled", False),
        requirements=None  # Could add Stripe requirements here if needed
    )


class ExpressDashboardResponse(BaseModel):
    """Response with Stripe Express Dashboard URL."""
    url: str


@router.get("/connect/dashboard", response_model=ExpressDashboardResponse)
async def get_express_dashboard_link(
    user_org: tuple = Depends(get_user_org)
):
    """
    Get Stripe Express Dashboard login link.
    
    Allows affiliates to access their Stripe dashboard to view
    transfers, payout history, manage bank details, etc.
    """
    user_id, organization_id = user_org
    affiliate_service = get_affiliate_service()
    
    affiliate = await affiliate_service.get_affiliate_by_user(user_id)
    if not affiliate:
        raise HTTPException(status_code=404, detail="Not an affiliate")
    
    if not affiliate.get("stripe_payouts_enabled"):
        raise HTTPException(
            status_code=400, 
            detail="Stripe Connect must be fully set up first"
        )
    
    url = await affiliate_service.get_express_dashboard_url(affiliate["id"])
    
    if not url:
        raise HTTPException(status_code=500, detail="Could not generate dashboard link")
    
    return ExpressDashboardResponse(url=url)


# =============================================================================
# SETTINGS ENDPOINTS
# =============================================================================

@router.patch("/settings", response_model=UpdateSettingsResponse)
async def update_settings(
    request: UpdateSettingsRequest,
    user_org: tuple = Depends(get_user_org)
):
    """
    Update affiliate settings.
    """
    user_id, organization_id = user_org
    affiliate_service = get_affiliate_service()
    
    affiliate = await affiliate_service.get_affiliate_by_user(user_id)
    if not affiliate:
        raise HTTPException(status_code=404, detail="Not an affiliate")
    
    # Build update data
    update_data = {}
    
    if request.minimum_payout_cents is not None:
        update_data["minimum_payout_cents"] = request.minimum_payout_cents
    
    if request.payout_frequency is not None:
        if request.payout_frequency not in ("weekly", "biweekly", "monthly"):
            raise HTTPException(
                status_code=400, 
                detail="Invalid payout frequency. Must be weekly, biweekly, or monthly"
            )
        update_data["payout_frequency"] = request.payout_frequency
    
    if not update_data:
        raise HTTPException(status_code=400, detail="No settings to update")
    
    # Update via supabase directly (service doesn't have a general update method)
    from app.database import get_supabase_service
    supabase = get_supabase_service()
    
    supabase.table("affiliates").update(update_data).eq(
        "id", affiliate["id"]
    ).execute()
    
    # Get updated settings
    affiliate = await affiliate_service.get_affiliate_by_user(user_id)
    
    return UpdateSettingsResponse(
        success=True,
        settings={
            "minimum_payout_cents": affiliate.get("minimum_payout_cents", 5000),
            "payout_frequency": affiliate.get("payout_frequency", "monthly"),
            "commission_rate_subscription": affiliate.get("commission_rate_subscription", 0.15),
            "commission_rate_credits": affiliate.get("commission_rate_credits", 0.10),
        }
    )

