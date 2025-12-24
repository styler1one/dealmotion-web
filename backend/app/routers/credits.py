"""
Credits Router - Credit balance and usage tracking API

Endpoints for viewing credit balance, usage history, and API usage breakdown.
This is the user-facing API for the usage dashboard.
"""

import logging
from typing import Optional, List, Dict, Any
from datetime import datetime
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

from app.deps import get_current_user, get_user_org
from app.services.credit_service import get_credit_service
from app.services.api_usage_service import get_api_usage_service

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/credits", tags=["credits"])


# =============================================================================
# Response Models
# =============================================================================

class CreditBalanceResponse(BaseModel):
    """Current credit balance."""
    subscription_credits_total: int = Field(description="Total credits included in subscription")
    subscription_credits_used: float = Field(description="Credits used this period")
    subscription_credits_remaining: float = Field(description="Subscription credits remaining")
    pack_credits_remaining: float = Field(description="Credits from purchased packs")
    total_credits_available: float = Field(description="Total credits available")
    is_unlimited: bool = Field(description="Whether this is an unlimited plan")
    is_free_plan: bool = Field(default=False, description="Whether this is a free plan (one-time credits)")
    period_start: Optional[str] = Field(None, description="Current billing period start")
    period_end: Optional[str] = Field(None, description="Current billing period end (null for free plan)")
    
    class Config:
        json_schema_extra = {
            "example": {
                "subscription_credits_total": 10,
                "subscription_credits_used": 3.5,
                "subscription_credits_remaining": 6.5,
                "pack_credits_remaining": 5.0,
                "total_credits_available": 11.5,
                "is_unlimited": False,
                "period_start": "2024-12-01T00:00:00Z",
                "period_end": "2025-01-01T00:00:00Z"
            }
        }


class CreditTransactionResponse(BaseModel):
    """A credit transaction."""
    id: str
    transaction_type: str
    credits_amount: float
    balance_after: float
    description: Optional[str] = None
    reference_type: Optional[str] = None
    user_id: Optional[str] = None
    metadata: Optional[Dict[str, Any]] = None
    created_at: str


class CreditHistoryResponse(BaseModel):
    """Credit transaction history."""
    transactions: List[CreditTransactionResponse]
    total_count: int
    has_more: bool = False


class DetailedUsageRequest(BaseModel):
    """Request for detailed usage history."""
    page: int = Field(1, ge=1, description="Page number (1-indexed)")
    page_size: int = Field(25, ge=1, le=100, description="Items per page")
    filter_type: Optional[str] = Field(None, description="Filter by transaction type: consumption, subscription_reset, pack_purchase")
    filter_action: Optional[str] = Field(None, description="Filter by action: research_flow, preparation, followup, etc.")
    start_date: Optional[str] = Field(None, description="Start date (ISO format)")
    end_date: Optional[str] = Field(None, description="End date (ISO format)")


class DetailedUsageResponse(BaseModel):
    """Detailed usage history with pagination and stats."""
    transactions: List[CreditTransactionResponse]
    total_count: int
    page: int
    page_size: int
    total_pages: int
    period_stats: Dict[str, Any]


class UsageByServiceItem(BaseModel):
    """Usage for a specific service."""
    service: str
    credits: float
    cost_cents: int
    calls: int


class UsageSummaryResponse(BaseModel):
    """Usage summary for the current period."""
    by_service: Dict[str, Dict[str, Any]]
    by_provider: Dict[str, Dict[str, Any]]
    totals: Dict[str, Any]
    period_start: str
    period_end: str
    
    class Config:
        json_schema_extra = {
            "example": {
                "by_service": {
                    "research_analysis": {"credits": 5.0, "cost_cents": 150, "calls": 5},
                    "discovery": {"credits": 2.0, "cost_cents": 50, "calls": 10}
                },
                "by_provider": {
                    "anthropic": {"tokens": 50000, "cost_cents": 120, "calls": 5},
                    "gemini": {"tokens": 100000, "cost_cents": 20, "calls": 5},
                    "exa": {"requests": 40, "cost_cents": 40, "calls": 40}
                },
                "totals": {
                    "tokens": 150000,
                    "requests": 40,
                    "cost_cents": 180,
                    "credits": 7.0,
                    "api_calls": 50
                },
                "period_start": "2024-12-01T00:00:00Z",
                "period_end": "2024-12-21T15:30:00Z"
            }
        }


class RecentApiCallResponse(BaseModel):
    """A recent API call."""
    id: str
    api_provider: str
    api_service: Optional[str] = None
    model: Optional[str] = None
    input_tokens: int = 0
    output_tokens: int = 0
    request_count: int = 0
    duration_seconds: int = 0
    estimated_cost_cents: int = 0
    credits_consumed: float = 0
    created_at: str


class RecentApiCallsResponse(BaseModel):
    """Recent API calls."""
    calls: List[RecentApiCallResponse]


# =============================================================================
# Endpoints
# =============================================================================

@router.get("/balance", response_model=CreditBalanceResponse)
async def get_credit_balance(
    user_org: tuple = Depends(get_user_org)
):
    """
    Get current credit balance for the organization.
    
    Returns:
    - Subscription credits (reset monthly)
    - Pack credits (purchased, persist until used)
    - Total available credits
    - Whether unlimited plan
    - Current billing period
    """
    user_id, organization_id = user_org
    
    credit_service = get_credit_service()
    balance = await credit_service.get_balance(organization_id)
    
    if balance.get("error"):
        # If credit system not yet initialized, return defaults
        logger.warning(f"Credit balance not found for org {organization_id}, returning defaults")
        return CreditBalanceResponse(
            subscription_credits_total=25,  # Free plan default (25 one-time credits)
            subscription_credits_used=0,
            subscription_credits_remaining=25,
            pack_credits_remaining=0,
            total_credits_available=25,
            is_unlimited=False,
            is_free_plan=True,
            period_start=None,
            period_end=None  # Free plan has no period (one-time credits)
        )
    
    return CreditBalanceResponse(
        subscription_credits_total=balance.get("subscription_credits_total", 0),
        subscription_credits_used=balance.get("subscription_credits_used", 0),
        subscription_credits_remaining=balance.get("subscription_credits_remaining", 0),
        pack_credits_remaining=balance.get("pack_credits_remaining", 0),
        total_credits_available=balance.get("total_credits_available", 0) if not balance.get("is_unlimited") else -1,
        is_unlimited=balance.get("is_unlimited", False),
        is_free_plan=balance.get("is_free_plan", False),
        period_start=balance.get("period_start"),
        period_end=balance.get("period_end")  # Will be null for free plan
    )


@router.get("/history", response_model=CreditHistoryResponse)
async def get_credit_history(
    limit: int = 50,
    user_org: tuple = Depends(get_user_org)
):
    """
    Get credit transaction history.
    
    Shows recent credit additions and consumption.
    """
    user_id, organization_id = user_org
    
    credit_service = get_credit_service()
    transactions = await credit_service.get_usage_history(organization_id, limit=limit + 1)
    
    has_more = len(transactions) > limit
    transactions = transactions[:limit]
    
    return CreditHistoryResponse(
        transactions=[
            CreditTransactionResponse(
                id=str(t.get("id", "")),
                transaction_type=t.get("transaction_type", ""),
                credits_amount=float(t.get("credits_amount", 0)),
                balance_after=float(t.get("balance_after", 0)),
                description=t.get("description"),
                reference_type=t.get("reference_type"),
                user_id=str(t.get("user_id")) if t.get("user_id") else None,
                metadata=t.get("metadata"),
                created_at=str(t.get("created_at", ""))
            )
            for t in transactions
        ],
        total_count=len(transactions),
        has_more=has_more
    )


@router.get("/history/detailed", response_model=DetailedUsageResponse)
async def get_detailed_usage_history(
    page: int = 1,
    page_size: int = 25,
    filter_type: Optional[str] = None,
    filter_action: Optional[str] = None,
    start_date: Optional[str] = None,
    end_date: Optional[str] = None,
    user_org: tuple = Depends(get_user_org)
):
    """
    Get detailed usage history with pagination and filtering.
    
    This is the main endpoint for the Credits Usage page.
    
    Filter options:
    - filter_type: consumption, subscription_reset, pack_purchase, admin_grant, refund
    - filter_action: research_flow, preparation, followup, followup_action, 
                     transcription_minute, prospect_discovery, contact_search
    - start_date/end_date: ISO format dates
    
    Returns paginated transactions with period statistics.
    """
    user_id, organization_id = user_org
    
    credit_service = get_credit_service()
    
    result = await credit_service.get_detailed_usage_history(
        organization_id=organization_id,
        page=page,
        page_size=page_size,
        filter_type=filter_type,
        filter_action=filter_action,
        start_date=start_date,
        end_date=end_date
    )
    
    transactions = result.get("transactions", [])
    total_count = result.get("total_count", 0)
    total_pages = (total_count + page_size - 1) // page_size if page_size > 0 else 1
    
    return DetailedUsageResponse(
        transactions=[
            CreditTransactionResponse(
                id=str(t.get("id", "")),
                transaction_type=t.get("transaction_type", ""),
                credits_amount=float(t.get("credits_amount", 0)),
                balance_after=float(t.get("balance_after", 0)),
                description=t.get("description"),
                reference_type=t.get("reference_type"),
                user_id=str(t.get("user_id")) if t.get("user_id") else None,
                metadata=t.get("metadata"),
                created_at=str(t.get("created_at", ""))
            )
            for t in transactions
        ],
        total_count=total_count,
        page=page,
        page_size=page_size,
        total_pages=total_pages,
        period_stats=result.get("period_stats", {})
    )


@router.get("/usage/summary", response_model=UsageSummaryResponse)
async def get_usage_summary(
    user_org: tuple = Depends(get_user_org)
):
    """
    Get usage summary for the current billing period.
    
    Returns breakdown by:
    - Service (research, discovery, transcription, etc.)
    - Provider (anthropic, gemini, exa, deepgram, etc.)
    - Totals (tokens, requests, cost, credits)
    """
    user_id, organization_id = user_org
    
    usage_service = get_api_usage_service()
    summary = await usage_service.get_usage_summary(organization_id)
    
    return UsageSummaryResponse(
        by_service=summary.get("by_service", {}),
        by_provider=summary.get("by_provider", {}),
        totals=summary.get("totals", {}),
        period_start=summary.get("period_start", ""),
        period_end=summary.get("period_end", "")
    )


@router.get("/usage/recent", response_model=RecentApiCallsResponse)
async def get_recent_api_calls(
    limit: int = 20,
    user_org: tuple = Depends(get_user_org)
):
    """
    Get recent API calls for the organization.
    
    Useful for debugging and understanding usage patterns.
    """
    user_id, organization_id = user_org
    
    usage_service = get_api_usage_service()
    calls = await usage_service.get_recent_logs(organization_id, limit=limit)
    
    return RecentApiCallsResponse(
        calls=[
            RecentApiCallResponse(
                id=str(c.get("id", "")),
                api_provider=c.get("api_provider", ""),
                api_service=c.get("api_service"),
                model=c.get("model"),
                input_tokens=c.get("input_tokens", 0) or 0,
                output_tokens=c.get("output_tokens", 0) or 0,
                request_count=c.get("request_count", 0) or 0,
                duration_seconds=c.get("duration_seconds", 0) or 0,
                estimated_cost_cents=c.get("estimated_cost_cents", 0) or 0,
                credits_consumed=float(c.get("credits_consumed", 0) or 0),
                created_at=str(c.get("created_at", ""))
            )
            for c in calls
        ]
    )


@router.get("/check/{action}")
async def check_credits_for_action(
    action: str,
    quantity: int = 1,
    user_org: tuple = Depends(get_user_org)
):
    """
    Check if organization has enough credits for a specific action.
    
    Actions (based on actual API costs with 30% margin):
    - research_flow: 3 credits (Gemini + Claude)
    - prospect_discovery: 5 credits (22 Exa + 3 Claude calls)
    - preparation: 2 credits (1 Claude call)
    - followup: 2 credits (transcript analysis)
    - followup_action: 2 credits per action (6 action types available)
    - transcription_minute: 0.15 credits per minute (Deepgram)
    - contact_search: 0.25 credits
    - followup_bundle: 19 credits (30-min meeting bundle)
    - followup_start: 3 credits (minimum for starting followup)
    
    Returns whether action is allowed and current balance.
    """
    user_id, organization_id = user_org
    
    credit_service = get_credit_service()
    allowed, balance = await credit_service.check_credits(organization_id, action, quantity)
    
    return {
        "allowed": allowed,
        "action": action,
        "quantity": quantity,
        "required_credits": balance.get("required_credits", 0),
        "available_credits": balance.get("total_credits_available", 0),
        "is_unlimited": balance.get("is_unlimited", False)
    }

