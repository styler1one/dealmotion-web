"""
Admin Costs Router
==================

API cost tracking and analytics based on api_usage_logs.
Provides detailed cost breakdowns by service, action, and time period.

Tracks:
- Anthropic (Claude) - token costs
- Deepgram - transcription minutes
- Pinecone - vector operations
- Voyage AI - embeddings
- Exa - web searches
- Recall.ai - meeting bots
- Google AI - Gemini usage
"""

from fastapi import APIRouter, Depends, Query
from typing import Optional, List, Dict, Any
from datetime import datetime, timedelta
from decimal import Decimal
import logging

from app.deps import get_admin_user, AdminContext
from app.database import get_supabase_service
from .models import CamelModel

router = APIRouter(prefix="/costs", tags=["admin-costs"])
logger = logging.getLogger(__name__)


# ============================================================
# Models (with camelCase serialization)
# ============================================================

class CostSummary(CamelModel):
    """High-level cost summary."""
    total_cost_cents: int
    total_cost_formatted: str
    period_start: datetime
    period_end: datetime
    comparison_period_cost_cents: int
    change_percent: float  # % change vs comparison period
    projected_monthly_cost_cents: int


class ServiceCost(CamelModel):
    """Cost breakdown for a single service."""
    service_name: str
    display_name: str
    cost_cents: int
    cost_formatted: str
    percent_of_total: float
    request_count: int
    # Service-specific metrics
    tokens_used: Optional[int] = None  # For LLMs
    minutes_used: Optional[float] = None  # For audio
    queries_used: Optional[int] = None  # For search/vector


class CostsByService(CamelModel):
    """Cost breakdown by service."""
    services: List[ServiceCost]
    total_cost_cents: int
    period_start: datetime
    period_end: datetime


class ActionCost(CamelModel):
    """Cost breakdown for a single action type."""
    action_name: str
    display_name: str
    cost_cents: int
    cost_formatted: str
    count: int
    avg_cost_cents: float


class CostsByAction(CamelModel):
    """Cost breakdown by action/service type."""
    actions: List[ActionCost]
    total_cost_cents: int


class DailyCost(CamelModel):
    """Daily cost data point."""
    date: str  # YYYY-MM-DD
    cost_cents: int
    request_count: int


class CostTrend(CamelModel):
    """Cost trend over time."""
    data: List[DailyCost]
    total_cost_cents: int
    avg_daily_cost_cents: int
    period_days: int


class ServiceDailyCost(CamelModel):
    """Daily cost for a specific service."""
    service_name: str
    display_name: str
    daily_costs: List[DailyCost]
    total_cost_cents: int


class CostTrendByService(CamelModel):
    """Cost trends broken down by service."""
    services: List[ServiceDailyCost]
    period_days: int


class TopUser(CamelModel):
    """User with highest cost."""
    user_id: str
    email: Optional[str] = None
    organization_name: Optional[str] = None
    cost_cents: int
    cost_formatted: str
    request_count: int


class CostsByUser(CamelModel):
    """Top users by cost."""
    users: List[TopUser]
    total_users: int


class CostProjection(CamelModel):
    """Cost projection for current month."""
    current_month_actual_cents: int
    current_month_projected_cents: int
    days_elapsed: int
    days_remaining: int
    daily_average_cents: int
    budget_cents: Optional[int] = None
    budget_percent_used: Optional[float] = None


# ============================================================
# Service Display Names & Config
# ============================================================

SERVICE_DISPLAY_NAMES = {
    "anthropic": "Anthropic (Claude)",
    "gemini": "Google (Gemini)",
    "deepgram": "Deepgram",
    "pinecone": "Pinecone",
    "voyage": "Voyage AI",
    "exa": "Exa",
    "recall": "Recall.ai",
    "brave": "Brave Search",
    "google": "Google AI",
}

ACTION_DISPLAY_NAMES = {
    "research": "Research Briefs",
    "research_analysis": "Research Analysis",
    "discovery": "Prospect Discovery",
    "preparation": "Meeting Prep",
    "prep_generation": "Prep Generation",
    "followup": "Follow-ups",
    "followup_generation": "Follow-up Generation",
    "transcription": "Transcription",
    "embedding": "Embeddings",
    "knowledge_base": "Knowledge Base",
    "contact_search": "Contact Search",
    "contact_analysis": "Contact Analysis",
    "coach": "Sales Coach",
    "interview": "Profile Interview",
}


# ============================================================
# Endpoints
# ============================================================

@router.get("/summary", response_model=CostSummary)
async def get_cost_summary(
    days: int = Query(30, ge=1, le=90, description="Number of days"),
    admin: AdminContext = Depends(get_admin_user)
):
    """
    Get high-level cost summary for the specified period.
    Includes comparison to previous period of same length.
    """
    supabase = get_supabase_service()
    now = datetime.utcnow()
    
    period_end = now
    period_start = now - timedelta(days=days)
    comparison_start = period_start - timedelta(days=days)
    comparison_end = period_start
    
    # Current period
    current_result = supabase.table("api_usage_logs") \
        .select("estimated_cost_cents") \
        .gte("created_at", period_start.isoformat()) \
        .lte("created_at", period_end.isoformat()) \
        .execute()
    
    current_total = sum(r.get("estimated_cost_cents", 0) or 0 for r in (current_result.data or []))
    
    # Comparison period
    comparison_result = supabase.table("api_usage_logs") \
        .select("estimated_cost_cents") \
        .gte("created_at", comparison_start.isoformat()) \
        .lt("created_at", comparison_end.isoformat()) \
        .execute()
    
    comparison_total = sum(r.get("estimated_cost_cents", 0) or 0 for r in (comparison_result.data or []))
    
    # Calculate change
    if comparison_total > 0:
        change_percent = ((current_total - comparison_total) / comparison_total) * 100
    else:
        change_percent = 0 if current_total == 0 else 100
    
    # Project monthly cost
    days_elapsed = days
    daily_avg = current_total / days_elapsed if days_elapsed > 0 else 0
    projected_monthly = int(daily_avg * 30)
    
    return CostSummary(
        total_cost_cents=current_total,
        total_cost_formatted=_format_cents(current_total),
        period_start=period_start,
        period_end=period_end,
        comparison_period_cost_cents=comparison_total,
        change_percent=round(change_percent, 1),
        projected_monthly_cost_cents=projected_monthly
    )


@router.get("/by-service", response_model=CostsByService)
async def get_costs_by_service(
    days: int = Query(30, ge=1, le=90),
    admin: AdminContext = Depends(get_admin_user)
):
    """
    Get cost breakdown by external service.
    """
    supabase = get_supabase_service()
    now = datetime.utcnow()
    period_start = now - timedelta(days=days)
    
    result = supabase.table("api_usage_logs") \
        .select("api_provider, estimated_cost_cents, input_tokens, output_tokens, duration_seconds, request_count") \
        .gte("created_at", period_start.isoformat()) \
        .execute()
    
    # Aggregate by provider
    by_provider: Dict[str, Dict] = {}
    total_cost = 0
    
    for row in (result.data or []):
        provider = row.get("api_provider", "unknown")
        cost = row.get("estimated_cost_cents", 0) or 0
        
        if provider not in by_provider:
            by_provider[provider] = {
                "cost_cents": 0,
                "request_count": 0,
                "tokens": 0,
                "duration_seconds": 0
            }
        
        by_provider[provider]["cost_cents"] += cost
        by_provider[provider]["request_count"] += row.get("request_count", 1) or 1
        by_provider[provider]["tokens"] += (row.get("input_tokens", 0) or 0) + (row.get("output_tokens", 0) or 0)
        by_provider[provider]["duration_seconds"] += row.get("duration_seconds", 0) or 0
        total_cost += cost
    
    # Build response
    services = []
    for provider, data in sorted(by_provider.items(), key=lambda x: x[1]["cost_cents"], reverse=True):
        pct = (data["cost_cents"] / total_cost * 100) if total_cost > 0 else 0
        
        service = ServiceCost(
            service_name=provider,
            display_name=SERVICE_DISPLAY_NAMES.get(provider, provider.title()),
            cost_cents=data["cost_cents"],
            cost_formatted=_format_cents(data["cost_cents"]),
            percent_of_total=round(pct, 1),
            request_count=data["request_count"],
            tokens_used=data["tokens"] if data["tokens"] > 0 else None,
            minutes_used=round(data["duration_seconds"] / 60, 2) if data["duration_seconds"] > 0 else None
        )
        services.append(service)
    
    return CostsByService(
        services=services,
        total_cost_cents=total_cost,
        period_start=period_start,
        period_end=now
    )


@router.get("/by-action", response_model=CostsByAction)
async def get_costs_by_action(
    days: int = Query(30, ge=1, le=90),
    admin: AdminContext = Depends(get_admin_user)
):
    """
    Get cost breakdown by action/service type (research, prep, followup, etc.).
    """
    supabase = get_supabase_service()
    now = datetime.utcnow()
    period_start = now - timedelta(days=days)
    
    result = supabase.table("api_usage_logs") \
        .select("api_service, estimated_cost_cents") \
        .gte("created_at", period_start.isoformat()) \
        .execute()
    
    # Aggregate by action
    by_action: Dict[str, Dict] = {}
    total_cost = 0
    
    for row in (result.data or []):
        action = row.get("api_service") or "other"
        cost = row.get("estimated_cost_cents", 0) or 0
        
        if action not in by_action:
            by_action[action] = {"cost_cents": 0, "count": 0}
        
        by_action[action]["cost_cents"] += cost
        by_action[action]["count"] += 1
        total_cost += cost
    
    # Build response
    actions = []
    for action, data in sorted(by_action.items(), key=lambda x: x[1]["cost_cents"], reverse=True):
        avg_cost = data["cost_cents"] / data["count"] if data["count"] > 0 else 0
        
        actions.append(ActionCost(
            action_name=action,
            display_name=ACTION_DISPLAY_NAMES.get(action, action.replace("_", " ").title()),
            cost_cents=data["cost_cents"],
            cost_formatted=_format_cents(data["cost_cents"]),
            count=data["count"],
            avg_cost_cents=round(avg_cost, 2)
        ))
    
    return CostsByAction(
        actions=actions,
        total_cost_cents=total_cost
    )


@router.get("/trend", response_model=CostTrend)
async def get_cost_trend(
    days: int = Query(30, ge=1, le=90),
    admin: AdminContext = Depends(get_admin_user)
):
    """
    Get daily cost trend for the specified period.
    """
    supabase = get_supabase_service()
    now = datetime.utcnow()
    period_start = now - timedelta(days=days)
    
    result = supabase.table("api_usage_logs") \
        .select("created_at, estimated_cost_cents, request_count") \
        .gte("created_at", period_start.isoformat()) \
        .order("created_at") \
        .execute()
    
    # Group by date
    daily_data: Dict[str, Dict] = {}
    total_cost = 0
    
    for row in (result.data or []):
        date = row["created_at"][:10]  # YYYY-MM-DD
        cost = row.get("estimated_cost_cents", 0) or 0
        
        if date not in daily_data:
            daily_data[date] = {"cost_cents": 0, "request_count": 0}
        
        daily_data[date]["cost_cents"] += cost
        daily_data[date]["request_count"] += row.get("request_count", 1) or 1
        total_cost += cost
    
    # Build response
    data = []
    for date in sorted(daily_data.keys()):
        data.append(DailyCost(
            date=date,
            cost_cents=daily_data[date]["cost_cents"],
            request_count=daily_data[date]["request_count"]
        ))
    
    avg_daily = total_cost // len(daily_data) if daily_data else 0
    
    return CostTrend(
        data=data,
        total_cost_cents=total_cost,
        avg_daily_cost_cents=avg_daily,
        period_days=days
    )


@router.get("/trend-by-service", response_model=CostTrendByService)
async def get_cost_trend_by_service(
    days: int = Query(30, ge=1, le=90),
    admin: AdminContext = Depends(get_admin_user)
):
    """
    Get daily cost trend broken down by service.
    """
    supabase = get_supabase_service()
    now = datetime.utcnow()
    period_start = now - timedelta(days=days)
    
    result = supabase.table("api_usage_logs") \
        .select("created_at, api_provider, estimated_cost_cents, request_count") \
        .gte("created_at", period_start.isoformat()) \
        .order("created_at") \
        .execute()
    
    # Group by service and date
    by_service: Dict[str, Dict[str, Dict]] = {}
    
    for row in (result.data or []):
        provider = row.get("api_provider", "unknown")
        date = row["created_at"][:10]
        cost = row.get("estimated_cost_cents", 0) or 0
        
        if provider not in by_service:
            by_service[provider] = {}
        
        if date not in by_service[provider]:
            by_service[provider][date] = {"cost_cents": 0, "request_count": 0}
        
        by_service[provider][date]["cost_cents"] += cost
        by_service[provider][date]["request_count"] += row.get("request_count", 1) or 1
    
    # Build response
    services = []
    for provider in sorted(by_service.keys()):
        daily_costs = []
        total_cost = 0
        
        for date in sorted(by_service[provider].keys()):
            data = by_service[provider][date]
            daily_costs.append(DailyCost(
                date=date,
                cost_cents=data["cost_cents"],
                request_count=data["request_count"]
            ))
            total_cost += data["cost_cents"]
        
        services.append(ServiceDailyCost(
            service_name=provider,
            display_name=SERVICE_DISPLAY_NAMES.get(provider, provider.title()),
            daily_costs=daily_costs,
            total_cost_cents=total_cost
        ))
    
    # Sort by total cost
    services.sort(key=lambda s: s.total_cost_cents, reverse=True)
    
    return CostTrendByService(
        services=services,
        period_days=days
    )


@router.get("/top-users", response_model=CostsByUser)
async def get_top_users_by_cost(
    days: int = Query(30, ge=1, le=90),
    limit: int = Query(20, ge=1, le=100),
    admin: AdminContext = Depends(get_admin_user)
):
    """
    Get users with highest API costs.
    """
    supabase = get_supabase_service()
    now = datetime.utcnow()
    period_start = now - timedelta(days=days)
    
    # Get usage grouped by user
    result = supabase.table("api_usage_logs") \
        .select("user_id, estimated_cost_cents, request_count") \
        .gte("created_at", period_start.isoformat()) \
        .not_.is_("user_id", "null") \
        .execute()
    
    # Aggregate by user
    by_user: Dict[str, Dict] = {}
    
    for row in (result.data or []):
        user_id = row.get("user_id")
        if not user_id:
            continue
        
        if user_id not in by_user:
            by_user[user_id] = {"cost_cents": 0, "request_count": 0}
        
        by_user[user_id]["cost_cents"] += row.get("estimated_cost_cents", 0) or 0
        by_user[user_id]["request_count"] += row.get("request_count", 1) or 1
    
    # Sort and limit
    sorted_users = sorted(by_user.items(), key=lambda x: x[1]["cost_cents"], reverse=True)[:limit]
    
    # Get user details
    user_ids = [u[0] for u in sorted_users]
    users_result = supabase.table("users") \
        .select("id, email") \
        .in_("id", user_ids) \
        .execute() if user_ids else None
    
    user_emails = {u["id"]: u["email"] for u in (users_result.data or [])} if users_result else {}
    
    # Get organization names
    org_result = supabase.table("organization_members") \
        .select("user_id, organizations(name)") \
        .in_("user_id", user_ids) \
        .execute() if user_ids else None
    
    user_orgs = {}
    for row in (org_result.data or []):
        if row.get("organizations"):
            user_orgs[row["user_id"]] = row["organizations"].get("name")
    
    # Build response
    users = []
    for user_id, data in sorted_users:
        users.append(TopUser(
            user_id=user_id,
            email=user_emails.get(user_id),
            organization_name=user_orgs.get(user_id),
            cost_cents=data["cost_cents"],
            cost_formatted=_format_cents(data["cost_cents"]),
            request_count=data["request_count"]
        ))
    
    return CostsByUser(
        users=users,
        total_users=len(by_user)
    )


@router.get("/projection", response_model=CostProjection)
async def get_cost_projection(
    admin: AdminContext = Depends(get_admin_user)
):
    """
    Get cost projection for the current month.
    """
    supabase = get_supabase_service()
    now = datetime.utcnow()
    
    # Current month start
    month_start = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
    
    # Days elapsed and remaining
    days_elapsed = now.day
    days_in_month = (month_start.replace(month=month_start.month % 12 + 1) - month_start).days if month_start.month < 12 else 31
    days_remaining = days_in_month - days_elapsed
    
    # Get current month costs
    result = supabase.table("api_usage_logs") \
        .select("estimated_cost_cents") \
        .gte("created_at", month_start.isoformat()) \
        .execute()
    
    current_cost = sum(r.get("estimated_cost_cents", 0) or 0 for r in (result.data or []))
    
    # Calculate projection
    daily_avg = current_cost / days_elapsed if days_elapsed > 0 else 0
    projected = int(current_cost + (daily_avg * days_remaining))
    
    return CostProjection(
        current_month_actual_cents=current_cost,
        current_month_projected_cents=projected,
        days_elapsed=days_elapsed,
        days_remaining=days_remaining,
        daily_average_cents=int(daily_avg)
    )


@router.get("/service/{service_name}", response_model=ServiceCost)
async def get_service_cost_detail(
    service_name: str,
    days: int = Query(30, ge=1, le=90),
    admin: AdminContext = Depends(get_admin_user)
):
    """
    Get detailed cost info for a specific service.
    """
    supabase = get_supabase_service()
    now = datetime.utcnow()
    period_start = now - timedelta(days=days)
    
    result = supabase.table("api_usage_logs") \
        .select("estimated_cost_cents, input_tokens, output_tokens, duration_seconds, request_count") \
        .eq("api_provider", service_name) \
        .gte("created_at", period_start.isoformat()) \
        .execute()
    
    total_cost = 0
    total_tokens = 0
    total_duration = 0
    total_requests = 0
    
    for row in (result.data or []):
        total_cost += row.get("estimated_cost_cents", 0) or 0
        total_tokens += (row.get("input_tokens", 0) or 0) + (row.get("output_tokens", 0) or 0)
        total_duration += row.get("duration_seconds", 0) or 0
        total_requests += row.get("request_count", 1) or 1
    
    return ServiceCost(
        service_name=service_name,
        display_name=SERVICE_DISPLAY_NAMES.get(service_name, service_name.title()),
        cost_cents=total_cost,
        cost_formatted=_format_cents(total_cost),
        percent_of_total=100,  # Single service = 100%
        request_count=total_requests,
        tokens_used=total_tokens if total_tokens > 0 else None,
        minutes_used=round(total_duration / 60, 2) if total_duration > 0 else None
    )


# ============================================================
# Helper Functions
# ============================================================

def _format_cents(cents: int) -> str:
    """Format cents as currency string (EUR)."""
    euros = cents / 100
    if euros >= 1000:
        return f"€{euros:,.0f}"
    elif euros >= 100:
        return f"€{euros:.0f}"
    elif euros >= 10:
        return f"€{euros:.1f}"
    else:
        return f"€{euros:.2f}"


