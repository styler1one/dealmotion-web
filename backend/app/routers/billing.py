"""
Billing Router - API endpoints for subscription and billing management

Handles subscription retrieval, checkout, portal access, and usage tracking.
"""

import os
import logging
from fastapi import APIRouter, HTTPException, Depends
from pydantic import BaseModel
from typing import Optional, List, Dict, Any

from app.deps import get_current_user
from app.database import get_supabase_service
from app.utils.errors import handle_exception
from app.services.subscription_service import get_subscription_service
from app.services.flow_pack_service import get_flow_pack_service

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/billing", tags=["billing"])

# Use centralized database module
supabase = get_supabase_service()

# Frontend URLs (set via environment)
FRONTEND_URL = os.getenv("FRONTEND_URL", "http://localhost:3000")


# ==========================================
# REQUEST/RESPONSE MODELS
# ==========================================

class CheckoutRequest(BaseModel):
    plan_id: str  # v2: 'light_solo' or 'unlimited_solo'
    success_url: Optional[str] = None
    cancel_url: Optional[str] = None


class DonationResponse(BaseModel):
    donation_url: str


class CheckoutResponse(BaseModel):
    checkout_url: str
    session_id: str


class PortalRequest(BaseModel):
    return_url: Optional[str] = None


class PortalResponse(BaseModel):
    portal_url: str


class CheckLimitRequest(BaseModel):
    metric: str  # v2: 'flow' is primary. Legacy: 'research', 'preparation', 'followup'
    additional_amount: Optional[int] = None  # For transcription_seconds


class UsageMetric(BaseModel):
    used: int
    limit: int
    unlimited: bool
    remaining: Optional[int] = None
    percentage: Optional[float] = None


class UsageResponse(BaseModel):
    period_start: Optional[str] = None  # None for free plan (no monthly reset)
    period_end: Optional[str] = None
    # v2: Primary metric
    flow: Optional[UsageMetric] = None
    # v1 compatibility
    research: UsageMetric
    preparation: UsageMetric
    followup: UsageMetric
    transcription_seconds: Dict[str, Any]
    kb_documents: UsageMetric


class SubscriptionResponse(BaseModel):
    id: Optional[str]
    organization_id: str
    plan_id: str
    plan_name: str
    status: str
    features: Dict[str, Any]
    price_cents: Optional[int]
    billing_interval: Optional[str]
    current_period_start: Optional[str]
    current_period_end: Optional[str]
    cancel_at_period_end: bool
    trial_start: Optional[str]
    trial_end: Optional[str]
    is_trialing: bool
    is_active: bool
    is_paid: bool


class PlanResponse(BaseModel):
    id: str
    name: str
    description: Optional[str]
    price_cents: Optional[int]
    billing_interval: Optional[str]
    features: Dict[str, Any]
    display_order: int


# ==========================================
# HELPER FUNCTIONS
# ==========================================

async def get_user_organization(user_id: str) -> str:
    """Get organization ID for a user"""
    response = supabase.table("organization_members").select(
        "organization_id"
    ).eq("user_id", user_id).limit(1).execute()
    
    if not response.data:
        raise HTTPException(status_code=404, detail="User not in any organization")
    
    return response.data[0]["organization_id"]


async def get_user_email(user_id: str) -> str:
    """Get user email from Supabase Auth"""
    try:
        response = supabase.auth.admin.get_user_by_id(user_id)
        return response.user.email if response.user else None
    except Exception:
        return None


# ==========================================
# SUBSCRIPTION ENDPOINTS
# ==========================================

@router.get("/subscription", response_model=SubscriptionResponse)
async def get_subscription(current_user: dict = Depends(get_current_user)):
    """
    Get current subscription for the user's organization
    
    Returns subscription details including plan, status, and features
    """
    try:
        user_id = current_user.get("sub") or current_user.get("id")
        if not user_id:
            raise HTTPException(status_code=401, detail="Invalid user")
        
        organization_id = await get_user_organization(user_id)
        
        subscription_service = get_subscription_service()
        subscription = await subscription_service.get_subscription(organization_id)
        
        return subscription
        
    except HTTPException:
        raise
    except Exception as e:
        raise handle_exception(e, "get_subscription", user_id=user_id, organization_id=organization_id)


@router.get("/plans", response_model=List[PlanResponse])
async def get_plans(
    include_teams: bool = False,
    current_user: dict = Depends(get_current_user)
):
    """
    Get available subscription plans
    
    Returns list of plans with features and pricing
    """
    try:
        subscription_service = get_subscription_service()
        plans = await subscription_service.get_plans(include_teams=include_teams)
        
        return plans
        
    except Exception as e:
        raise handle_exception(e, "get_plans")


# ==========================================
# CHECKOUT & PORTAL ENDPOINTS
# ==========================================

@router.post("/checkout", response_model=CheckoutResponse)
async def create_checkout(
    request: CheckoutRequest,
    current_user: dict = Depends(get_current_user)
):
    """
    Create Stripe Checkout session for subscription
    
    Returns URL to redirect user to Stripe Checkout
    """
    try:
        user_id = current_user.get("sub") or current_user.get("id")
        if not user_id:
            raise HTTPException(status_code=401, detail="Invalid user")
        
        organization_id = await get_user_organization(user_id)
        user_email = await get_user_email(user_id)
        
        if not user_email:
            raise HTTPException(status_code=400, detail="User email not found")
        
        # Default URLs
        success_url = request.success_url or f"{FRONTEND_URL}/billing/success"
        cancel_url = request.cancel_url or f"{FRONTEND_URL}/pricing"
        
        subscription_service = get_subscription_service()
        result = await subscription_service.create_checkout_session(
            organization_id=organization_id,
            plan_id=request.plan_id,
            user_email=user_email,
            success_url=success_url,
            cancel_url=cancel_url,
        )
        
        return result
        
    except HTTPException:
        raise
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise handle_exception(e, "create_checkout", user_id=user_id)


@router.post("/portal", response_model=PortalResponse)
async def create_portal(
    request: PortalRequest,
    current_user: dict = Depends(get_current_user)
):
    """
    Create Stripe Billing Portal session
    
    Returns URL to redirect user to manage their subscription
    """
    try:
        user_id = current_user.get("sub") or current_user.get("id")
        if not user_id:
            raise HTTPException(status_code=401, detail="Invalid user")
        
        organization_id = await get_user_organization(user_id)
        
        return_url = request.return_url or f"{FRONTEND_URL}/dashboard/settings"
        
        subscription_service = get_subscription_service()
        result = await subscription_service.create_portal_session(
            organization_id=organization_id,
            return_url=return_url,
        )
        
        return result
        
    except HTTPException:
        raise
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error(f"Error creating portal: {e}")
        raise HTTPException(status_code=500, detail="Failed to create billing portal. Please try again.")


# ==========================================
# SUBSCRIPTION MANAGEMENT ENDPOINTS
# ==========================================

@router.post("/cancel")
async def cancel_subscription(current_user: dict = Depends(get_current_user)):
    """
    Cancel subscription at end of billing period
    
    The subscription remains active until the current period ends
    """
    try:
        user_id = current_user.get("sub") or current_user.get("id")
        if not user_id:
            raise HTTPException(status_code=401, detail="Invalid user")
        
        organization_id = await get_user_organization(user_id)
        
        subscription_service = get_subscription_service()
        subscription = await subscription_service.cancel_subscription(organization_id)
        
        return {
            "status": "canceled",
            "message": "Subscription will be canceled at end of billing period",
            "subscription": subscription,
        }
        
    except HTTPException:
        raise
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error(f"Error canceling subscription: {e}")
        raise HTTPException(status_code=500, detail="Failed to cancel subscription. Please try again.")


@router.post("/reactivate")
async def reactivate_subscription(current_user: dict = Depends(get_current_user)):
    """
    Reactivate a canceled subscription
    
    Only works if subscription hasn't expired yet
    """
    try:
        user_id = current_user.get("sub") or current_user.get("id")
        if not user_id:
            raise HTTPException(status_code=401, detail="Invalid user")
        
        organization_id = await get_user_organization(user_id)
        
        subscription_service = get_subscription_service()
        subscription = await subscription_service.reactivate_subscription(organization_id)
        
        return {
            "status": "reactivated",
            "message": "Subscription has been reactivated",
            "subscription": subscription,
        }
        
    except HTTPException:
        raise
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error(f"Error reactivating subscription: {e}")
        raise HTTPException(status_code=500, detail="Failed to reactivate subscription. Please try again.")


# ==========================================
# USAGE ENDPOINTS
# ==========================================

@router.get("/usage", response_model=UsageResponse)
async def get_usage(current_user: dict = Depends(get_current_user)):
    """
    Get current usage statistics for the organization
    
    Returns usage counts and limits for all metrics
    """
    try:
        user_id = current_user.get("sub") or current_user.get("id")
        if not user_id:
            raise HTTPException(status_code=401, detail="Invalid user")
        
        organization_id = await get_user_organization(user_id)
        
        # v4: Return credit-based usage instead of flow-based
        from app.services.credit_service import get_credit_service
        credit_service = get_credit_service()
        balance = await credit_service.get_balance(organization_id)
        
        # Format for backward compatibility with frontend
        # Convert floats to ints to match UsageMetric model
        total = int(balance.get("subscription_credits_total", 0) or 0)
        used = int(balance.get("subscription_credits_used", 0) or 0)
        remaining_raw = balance.get("total_credits_available", 0)
        remaining = int(remaining_raw) if remaining_raw != -1 else -1
        unlimited = balance.get("is_unlimited", False)
        
        usage = {
            "period_start": balance.get("period_start"),
            "period_end": balance.get("period_end"),
            "flow": {
                "used": used,
                "limit": total,
                "unlimited": unlimited,
                "remaining": remaining,
                "percentage": 0 if unlimited else (round((used / total) * 100, 1) if total > 0 else 0),
            },
            # Legacy compatibility - all point to credits now
            "research": {"used": 0, "limit": total, "unlimited": unlimited, "remaining": remaining},
            "preparation": {"used": 0, "limit": total, "unlimited": unlimited, "remaining": remaining},
            "followup": {"used": 0, "limit": total, "unlimited": unlimited, "remaining": remaining},
            "transcription_seconds": {"used": 0, "limit": -1, "unlimited": True},
            "kb_documents": {"used": 0, "limit": -1, "unlimited": True},
        }
        
        return usage
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting usage: {e}")
        raise HTTPException(status_code=500, detail="Failed to get usage data. Please try again.")


@router.post("/check-limit")
async def check_limit(
    request: CheckLimitRequest,
    current_user: dict = Depends(get_current_user)
):
    """
    Check if an action is allowed within subscription limits
    
    v2: Use 'flow' as the primary metric (1 flow = research + prep + followup)
    
    Returns whether the action is allowed and remaining quota
    """
    try:
        user_id = current_user.get("sub") or current_user.get("id")
        if not user_id:
            raise HTTPException(status_code=401, detail="Invalid user")
        
        organization_id = await get_user_organization(user_id)
        
        # v4: Use credit-based checking (replaces flow limits)
        from app.services.credit_service import get_credit_service
        credit_service = get_credit_service()
        
        # Map legacy metric names to credit actions
        action_map = {
            "flow": "research_flow",
            "research": "research_flow",
            "preparation": "preparation",
            "followup": "followup",
            "transcription_seconds": "transcription_minute",
        }
        action = action_map.get(request.metric, request.metric)
        quantity = request.additional_amount // 60 if request.metric == "transcription_seconds" and request.additional_amount else 1
        
        allowed, balance = await credit_service.check_credits(organization_id, action, quantity)
        
        return {
            "allowed": allowed,
            "current": balance.get("subscription_credits_used", 0),
            "limit": balance.get("subscription_credits_total", 0),
            "unlimited": balance.get("is_unlimited", False),
            "remaining": balance.get("total_credits_available", 0),
            "upgrade_required": not allowed,
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error checking limit: {e}")
        raise HTTPException(status_code=500, detail="Failed to check limit. Please try again.")


# ==========================================
# DONATION ENDPOINT (v2)
# ==========================================

# Stripe Donation Link (for free users)
STRIPE_DONATION_LINK = os.getenv("STRIPE_DONATION_LINK")


@router.get("/donation-link", response_model=DonationResponse)
async def get_donation_link(current_user: dict = Depends(get_current_user)):
    """
    Get Stripe donation link for free users
    
    Returns URL to Stripe Payment Link for donations
    """
    if not STRIPE_DONATION_LINK:
        raise HTTPException(
            status_code=503, 
            detail="Donation link not configured"
        )
    
    return {"donation_url": STRIPE_DONATION_LINK}


# ==========================================
# FLOW PACK ENDPOINTS (v3)
# ==========================================

class FlowPackCheckoutRequest(BaseModel):
    pack_id: str = "boost_100"  # Default to Boost 100
    success_url: Optional[str] = None
    cancel_url: Optional[str] = None


class FlowPackBalanceResponse(BaseModel):
    total_remaining: int
    packs: List[Dict[str, Any]]


class FlowPackProductResponse(BaseModel):
    id: str
    name: str
    credits: int
    price_cents: int
    per_credit_cents: Optional[int] = None
    description: Optional[str] = None
    popular: Optional[bool] = False
    best_value: Optional[bool] = False
    # Legacy field for backwards compatibility
    flows: Optional[int] = None


@router.get("/flow-packs/balance", response_model=FlowPackBalanceResponse)
async def get_flow_pack_balance(current_user: dict = Depends(get_current_user)):
    """
    Get flow pack balance for the organization
    
    Returns total remaining flows and individual pack details
    """
    try:
        user_id = current_user.get("sub") or current_user.get("id")
        if not user_id:
            raise HTTPException(status_code=401, detail="Invalid user")
        
        organization_id = await get_user_organization(user_id)
        
        flow_pack_service = get_flow_pack_service()
        balance = await flow_pack_service.get_balance(organization_id)
        
        return balance
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting flow pack balance: {e}")
        raise HTTPException(status_code=500, detail="Failed to get credit balance. Please try again.")


@router.get("/flow-packs/products", response_model=List[FlowPackProductResponse])
async def get_flow_pack_products(current_user: dict = Depends(get_current_user)):
    """
    Get available flow pack products for purchase
    """
    try:
        flow_pack_service = get_flow_pack_service()
        products = await flow_pack_service.get_available_packs()
        
        return products
        
    except Exception as e:
        logger.error(f"Error getting flow pack products: {e}")
        raise HTTPException(status_code=500, detail="Failed to load credit packs. Please try again.")


@router.post("/flow-packs/checkout", response_model=CheckoutResponse)
async def create_flow_pack_checkout(
    request: FlowPackCheckoutRequest,
    current_user: dict = Depends(get_current_user)
):
    """
    Create Stripe Checkout session for flow pack purchase
    
    Returns URL to redirect user to Stripe Checkout for one-time payment
    
    Note: Credit packs can only be purchased by Pro or Pro+ subscribers.
    Free plan users must upgrade first.
    """
    try:
        user_id = current_user.get("sub") or current_user.get("id")
        if not user_id:
            raise HTTPException(status_code=401, detail="Invalid user")
        
        organization_id = await get_user_organization(user_id)
        user_email = await get_user_email(user_id)
        
        if not user_email:
            raise HTTPException(status_code=400, detail="User email not found")
        
        # Check subscription - credit packs are only for Pro/Pro+ subscribers
        subscription_service = get_subscription_service()
        subscription = await subscription_service.get_subscription(organization_id)
        
        plan_id = subscription.get("plan_id", "free") if subscription else "free"
        allowed_plans = ["pro_monthly", "pro_yearly", "pro_plus_monthly", "pro_plus_yearly"]
        
        if plan_id not in allowed_plans:
            raise HTTPException(
                status_code=403, 
                detail="Credit packs are only available for Pro and Pro+ subscribers. Please upgrade your plan first."
            )
        
        # Default URLs
        success_url = request.success_url or f"{FRONTEND_URL}/billing/success"
        cancel_url = request.cancel_url or f"{FRONTEND_URL}/pricing"
        
        flow_pack_service = get_flow_pack_service()
        result = await flow_pack_service.create_checkout_session(
            organization_id=organization_id,
            pack_id=request.pack_id,
            user_email=user_email,
            success_url=success_url,
            cancel_url=cancel_url,
        )
        
        return result
        
    except HTTPException:
        raise
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error(f"Error creating flow pack checkout: {e}")
        raise HTTPException(status_code=500, detail="Failed to create checkout. Please try again.")


@router.get("/flow-packs/history")
async def get_flow_pack_history(
    limit: int = 10,
    current_user: dict = Depends(get_current_user)
):
    """
    Get flow pack purchase history for the organization
    """
    try:
        user_id = current_user.get("sub") or current_user.get("id")
        if not user_id:
            raise HTTPException(status_code=401, detail="Invalid user")
        
        organization_id = await get_user_organization(user_id)
        
        flow_pack_service = get_flow_pack_service()
        history = await flow_pack_service.get_purchase_history(organization_id, limit)
        
        return {"history": history}
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting flow pack history: {e}")
        raise HTTPException(status_code=500, detail="Failed to load purchase history. Please try again.")

