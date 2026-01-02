"""
Admin Dashboard Router
======================

Endpoints for admin dashboard metrics and trends.
"""

from fastapi import APIRouter, Depends
from typing import Optional, List, Dict, Any
from datetime import datetime, timedelta
import logging

from app.deps import get_admin_user, AdminContext
from app.database import get_supabase_service
from .models import CamelModel

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/dashboard", tags=["admin-dashboard"])


# ============================================================
# Response Models (with camelCase serialization)
# ============================================================

class DashboardMetrics(CamelModel):
    total_users: int
    users_growth_week: int
    active_users_7d: int
    mrr_cents: int
    mrr_change_percent: float = 0.0  # % change vs last month
    paid_users: int
    active_alerts: int
    error_rate_24h: Optional[float] = 0.0


class HealthDistribution(CamelModel):
    """Health score distribution for pie chart."""
    healthy: int      # 80-100 score
    at_risk: int      # 50-79 score
    critical: int     # 0-49 score
    total: int


class RecentActivityItem(CamelModel):
    """Single activity item for the feed."""
    id: str
    type: str  # 'research', 'preparation', 'followup'
    user_name: str
    user_email: str
    user_id: str
    title: str  # Company name or description
    status: str
    created_at: str


class RecentActivityResponse(CamelModel):
    """Response for recent activities."""
    activities: List[RecentActivityItem]


class TrendDataPoint(CamelModel):
    date: str
    researches: int
    preps: int
    followups: int
    new_users: int


class DashboardTrends(CamelModel):
    trends: List[TrendDataPoint]
    period_days: int


class AdminCheckResponse(CamelModel):
    is_admin: bool
    role: str
    admin_id: str
    user_id: str


# ============================================================
# Endpoints
# ============================================================

@router.get("/check", response_model=AdminCheckResponse)
async def check_admin_access(
    admin: AdminContext = Depends(get_admin_user)
):
    """
    Verify admin access and return role information.
    
    This endpoint is called by the frontend to check if user has admin access.
    Also updates last_admin_login_at.
    """
    return AdminCheckResponse(
        is_admin=True,
        role=admin.role,
        admin_id=admin.admin_id,
        user_id=admin.user_id
    )


@router.get("/metrics", response_model=DashboardMetrics)
async def get_dashboard_metrics(
    admin: AdminContext = Depends(get_admin_user)
):
    """
    Get key metrics for the admin dashboard.
    
    Returns:
    - Total users count
    - New users this week
    - Active users (7 days)
    - MRR (Monthly Recurring Revenue)
    - Paid users count
    - Active alerts count
    - Error rate (24h)
    """
    supabase = get_supabase_service()
    
    try:
        # Use the database function for metrics
        result = supabase.rpc("get_admin_dashboard_metrics").execute()
        
        if result.data:
            metrics = result.data
            
            # Calculate error rate
            error_rate = 0.0
            research_stats = supabase.rpc("get_job_stats_24h", {"p_table_name": "research_briefs"}).execute()
            if research_stats.data and research_stats.data.get("total", 0) > 0:
                failed = research_stats.data.get("failed", 0)
                total = research_stats.data.get("total", 1)
                error_rate = round((failed / total) * 100, 1)
            
            # Calculate MRR change percent
            mrr_change = await _calculate_mrr_change(supabase)
            
            return DashboardMetrics(
                total_users=metrics.get("total_users", 0),
                users_growth_week=metrics.get("users_growth_week", 0),
                active_users_7d=metrics.get("active_users_7d", 0),
                mrr_cents=metrics.get("mrr_cents", 0),
                mrr_change_percent=mrr_change,
                paid_users=metrics.get("paid_users", 0),
                active_alerts=metrics.get("active_alerts", 0),
                error_rate_24h=error_rate
            )
        
        # Fallback to manual calculation if RPC fails
        return await _calculate_metrics_fallback(supabase)
        
    except Exception as e:
        logger.error(f"Error getting dashboard metrics: {e}")
        return await _calculate_metrics_fallback(supabase)


async def _calculate_mrr_change(supabase) -> float:
    """Calculate MRR change percentage vs previous month from REAL payment data."""
    try:
        now = datetime.utcnow()
        
        # Current month start/end
        current_month_start = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
        
        # Previous month start/end
        if now.month == 1:
            prev_month_start = current_month_start.replace(year=now.year - 1, month=12)
        else:
            prev_month_start = current_month_start.replace(month=now.month - 1)
        
        # Get current month subscriptions revenue
        current_subs = supabase.table("organization_subscriptions") \
            .select("plan_id, subscription_plans(price_cents)") \
            .in_("status", ["active", "trialing"]) \
            .execute()
        
        current_mrr = 0
        for sub in (current_subs.data or []):
            if sub.get("subscription_plans"):
                current_mrr += sub["subscription_plans"].get("price_cents", 0) or 0
        
        # Get previous month's payments total (approximation of previous MRR)
        prev_payments = supabase.table("payment_history") \
            .select("amount_cents") \
            .gte("paid_at", prev_month_start.isoformat()) \
            .lt("paid_at", current_month_start.isoformat()) \
            .eq("status", "paid") \
            .execute()
        
        prev_mrr = sum(p.get("amount_cents", 0) for p in (prev_payments.data or []))
        
        # If no previous data, check if we have active subs that existed last month
        if prev_mrr == 0:
            prev_subs = supabase.table("organization_subscriptions") \
                .select("plan_id, subscription_plans(price_cents), created_at") \
                .in_("status", ["active", "trialing", "canceled"]) \
                .lt("created_at", current_month_start.isoformat()) \
                .execute()
            
            for sub in (prev_subs.data or []):
                if sub.get("subscription_plans"):
                    prev_mrr += sub["subscription_plans"].get("price_cents", 0) or 0
        
        # Calculate percentage change
        if prev_mrr > 0:
            change_percent = ((current_mrr - prev_mrr) / prev_mrr) * 100
            return round(change_percent, 1)
        elif current_mrr > 0:
            return 100.0  # New revenue from zero
        else:
            return 0.0
            
    except Exception as e:
        logger.warning(f"Error calculating MRR change: {e}")
        return 0.0


async def _calculate_metrics_fallback(supabase) -> DashboardMetrics:
    """Fallback calculation if database function fails - uses REAL data."""
    
    # Total users
    users_result = supabase.table("users").select("id", count="exact").execute()
    total_users = users_result.count or 0
    
    # Users this week
    week_ago = datetime.utcnow() - timedelta(days=7)
    week_result = supabase.table("users") \
        .select("id", count="exact") \
        .gte("created_at", week_ago.isoformat()) \
        .execute()
    users_growth_week = week_result.count or 0
    
    # Active users (7 days) - count unique users with activity in last 7 days
    active_users_7d = 0
    try:
        # Get unique user_ids from research_briefs in last 7 days
        research_users = supabase.table("research_briefs") \
            .select("user_id") \
            .gte("created_at", week_ago.isoformat()) \
            .execute()
        
        unique_users = set()
        for r in (research_users.data or []):
            if r.get("user_id"):
                unique_users.add(r["user_id"])
        
        # Also check meeting_preps
        prep_users = supabase.table("meeting_preps") \
            .select("user_id") \
            .gte("created_at", week_ago.isoformat()) \
            .execute()
        for p in (prep_users.data or []):
            if p.get("user_id"):
                unique_users.add(p["user_id"])
        
        # Also check followups
        followup_users = supabase.table("followups") \
            .select("user_id") \
            .gte("created_at", week_ago.isoformat()) \
            .execute()
        for f in (followup_users.data or []):
            if f.get("user_id"):
                unique_users.add(f["user_id"])
        
        active_users_7d = len(unique_users)
    except Exception:
        pass
    
    # MRR (Monthly Recurring Revenue) - sum of active subscriptions
    mrr_cents = 0
    try:
        # Get active/trialing subscriptions with their plan prices
        subs_result = supabase.table("organization_subscriptions") \
            .select("plan_id, subscription_plans(price_cents)") \
            .in_("status", ["active", "trialing"]) \
            .execute()
        
        for sub in (subs_result.data or []):
            if sub.get("subscription_plans"):
                mrr_cents += sub["subscription_plans"].get("price_cents", 0) or 0
    except Exception:
        pass
    
    # Paid users - count of non-free active subscriptions
    paid_users = 0
    try:
        paid_result = supabase.table("organization_subscriptions") \
            .select("id", count="exact") \
            .in_("status", ["active", "trialing"]) \
            .neq("plan_id", "free") \
            .execute()
        paid_users = paid_result.count or 0
    except Exception:
        pass
    
    # Active alerts
    active_alerts = 0
    try:
        alerts_result = supabase.table("admin_alerts") \
            .select("id", count="exact") \
            .eq("status", "active") \
            .execute()
        active_alerts = alerts_result.count or 0
    except Exception:
        pass
    
    # Error rate (24h) - percentage of failed jobs
    error_rate_24h = 0.0
    try:
        day_ago = (datetime.utcnow() - timedelta(days=1)).isoformat()
        
        # Total research briefs in 24h
        total_result = supabase.table("research_briefs") \
            .select("id", count="exact") \
            .gte("created_at", day_ago) \
            .execute()
        total_24h = total_result.count or 0
        
        # Failed research briefs in 24h
        failed_result = supabase.table("research_briefs") \
            .select("id", count="exact") \
            .gte("created_at", day_ago) \
            .eq("status", "failed") \
            .execute()
        failed_24h = failed_result.count or 0
        
        if total_24h > 0:
            error_rate_24h = round((failed_24h / total_24h) * 100, 1)
    except Exception:
        pass
    
    # Calculate MRR change
    mrr_change = await _calculate_mrr_change(supabase)
    
    return DashboardMetrics(
        total_users=total_users,
        users_growth_week=users_growth_week,
        active_users_7d=active_users_7d,
        mrr_cents=mrr_cents,
        mrr_change_percent=mrr_change,
        paid_users=paid_users,
        active_alerts=active_alerts,
        error_rate_24h=error_rate_24h
    )


@router.get("/trends", response_model=DashboardTrends)
async def get_usage_trends(
    days: int = 7,
    admin: AdminContext = Depends(get_admin_user)
):
    """
    Get usage trends for the specified number of days.
    
    Args:
        days: Number of days to fetch (default 7, max 30)
    
    Returns:
        Daily counts of researches, preps, followups, new users
    """
    # Limit to max 30 days
    days = min(max(days, 1), 30)
    
    supabase = get_supabase_service()
    
    try:
        result = supabase.rpc("get_admin_usage_trends", {"p_days": days}).execute()
        
        if result.data:
            trends = [
                TrendDataPoint(
                    date=item["date"],
                    researches=item.get("researches", 0),
                    preps=item.get("preps", 0),
                    followups=item.get("followups", 0),
                    new_users=item.get("new_users", 0)
                )
                for item in result.data
            ]
            return DashboardTrends(trends=trends, period_days=days)
        
        # RPC returned empty, use fallback
        return await _calculate_trends_fallback(supabase, days)
        
    except Exception as e:
        logger.error(f"Error getting usage trends: {e}")
        return await _calculate_trends_fallback(supabase, days)


async def _calculate_trends_fallback(supabase, days: int) -> DashboardTrends:
    """Fallback calculation for trends if database function fails - uses REAL data."""
    trends = []
    
    for i in range(days - 1, -1, -1):
        day_start = (datetime.utcnow() - timedelta(days=i)).replace(hour=0, minute=0, second=0, microsecond=0)
        day_end = day_start + timedelta(days=1)
        date_str = day_start.strftime("%Y-%m-%d")
        
        researches = 0
        preps = 0
        followups = 0
        new_users = 0
        
        try:
            # Count researches for this day
            research_result = supabase.table("research_briefs") \
                .select("id", count="exact") \
                .gte("created_at", day_start.isoformat()) \
                .lt("created_at", day_end.isoformat()) \
                .execute()
            researches = research_result.count or 0
        except Exception:
            pass
        
        try:
            # Count meeting preps for this day
            prep_result = supabase.table("meeting_preps") \
                .select("id", count="exact") \
                .gte("created_at", day_start.isoformat()) \
                .lt("created_at", day_end.isoformat()) \
                .execute()
            preps = prep_result.count or 0
        except Exception:
            pass
        
        try:
            # Count followups for this day
            followup_result = supabase.table("followups") \
                .select("id", count="exact") \
                .gte("created_at", day_start.isoformat()) \
                .lt("created_at", day_end.isoformat()) \
                .execute()
            followups = followup_result.count or 0
        except Exception:
            pass
        
        try:
            # Count new users for this day
            users_result = supabase.table("users") \
                .select("id", count="exact") \
                .gte("created_at", day_start.isoformat()) \
                .lt("created_at", day_end.isoformat()) \
                .execute()
            new_users = users_result.count or 0
        except Exception:
            pass
        
        trends.append(TrendDataPoint(
            date=date_str,
            researches=researches,
            preps=preps,
            followups=followups,
            new_users=new_users
        ))
    
    return DashboardTrends(trends=trends, period_days=days)


@router.get("/health-distribution", response_model=HealthDistribution)
async def get_health_distribution(
    admin: AdminContext = Depends(get_admin_user)
):
    """
    Get customer health score distribution for pie chart.
    
    Calculates health scores for all users and buckets them into:
    - Healthy (80-100)
    - At Risk (50-79)
    - Critical (0-49)
    
    Uses REAL data from database with BATCH queries to avoid N+1 problem.
    """
    supabase = get_supabase_service()
    
    try:
        # Pre-fetch all data in batch queries (avoiding N+1 problem)
        user_health_data = await _batch_fetch_user_health_data(supabase)
        
        healthy = 0
        at_risk = 0
        critical = 0
        
        for user_id, data in user_health_data.items():
            health_score = _calculate_health_score_from_data(data)
            
            if health_score >= 80:
                healthy += 1
            elif health_score >= 50:
                at_risk += 1
            else:
                critical += 1
        
        total = healthy + at_risk + critical
        
        return HealthDistribution(
            healthy=healthy,
            at_risk=at_risk,
            critical=critical,
            total=total
        )
        
    except Exception as e:
        logger.error(f"Error getting health distribution: {e}")
        return HealthDistribution(healthy=0, at_risk=0, critical=0, total=0)


async def _batch_fetch_user_health_data(supabase) -> Dict[str, Dict[str, Any]]:
    """
    Fetch all user health data in batch queries.
    
    This avoids the N+1 query problem by fetching all data upfront
    and then calculating health scores in memory.
    
    Returns: Dict[user_id, {last_activity, error_count, total_count, org_id, flow_count, flow_limit, profile_completeness, has_failed_payment}]
    """
    user_data: Dict[str, Dict[str, Any]] = {}
    month_ago = datetime.utcnow() - timedelta(days=30)
    
    # 1. Get all users
    users_result = supabase.table("users").select("id").execute()
    for user in (users_result.data or []):
        user_data[user["id"]] = {
            "last_activity": None,
            "error_count": 0,
            "total_count": 0,
            "org_id": None,
            "flow_count": 0,
            "flow_limit": 0,
            "profile_completeness": 0,
            "has_failed_payment": False
        }
    
    if not user_data:
        return user_data
    
    # 2. Get last activity per user (single query)
    activities = supabase.table("research_briefs") \
        .select("user_id, created_at, status") \
        .gte("created_at", month_ago.isoformat()) \
        .order("created_at", desc=True) \
        .execute()
    
    for activity in (activities.data or []):
        uid = activity.get("user_id")
        if uid and uid in user_data:
            # Update last activity (first one we see is the most recent due to ordering)
            if user_data[uid]["last_activity"] is None:
                user_data[uid]["last_activity"] = activity.get("created_at")
            # Count totals and errors
            user_data[uid]["total_count"] += 1
            if activity.get("status") == "failed":
                user_data[uid]["error_count"] += 1
    
    # 3. Get organization membership (single query)
    org_members = supabase.table("organization_members") \
        .select("user_id, organization_id") \
        .execute()
    
    org_ids = set()
    for member in (org_members.data or []):
        uid = member.get("user_id")
        org_id = member.get("organization_id")
        if uid and uid in user_data:
            user_data[uid]["org_id"] = org_id
            if org_id:
                org_ids.add(org_id)
    
    # 4. Get organization flow data from usage_records and subscription_plans
    if org_ids:
        # Get current month's flow usage from usage_records
        current_month_start = datetime.utcnow().replace(day=1, hour=0, minute=0, second=0, microsecond=0)
        usage_records = supabase.table("usage_records") \
            .select("organization_id, flow_count") \
            .in_("organization_id", list(org_ids)) \
            .gte("period_start", current_month_start.isoformat()) \
            .execute()
        
        usage_map = {ur["organization_id"]: ur.get("flow_count", 0) or 0 for ur in (usage_records.data or [])}
        
        # Get flow limits from subscription_plans via organization_subscriptions
        subscriptions = supabase.table("organization_subscriptions") \
            .select("organization_id, subscription_plans(features)") \
            .in_("organization_id", list(org_ids)) \
            .in_("status", ["active", "trialing"]) \
            .execute()
        
        limit_map = {}
        for sub in (subscriptions.data or []):
            org_id = sub.get("organization_id")
            features = (sub.get("subscription_plans") or {}).get("features") or {}
            limit_map[org_id] = features.get("flow_limit", 2) or 2
        
        for uid, data in user_data.items():
            org_id = data.get("org_id")
            if org_id:
                user_data[uid]["flow_count"] = usage_map.get(org_id, 0)
                user_data[uid]["flow_limit"] = limit_map.get(org_id, 2)
    
    # 5. Get profile completeness (single query)
    profiles = supabase.table("sales_profiles") \
        .select("user_id, profile_completeness") \
        .execute()
    
    for profile in (profiles.data or []):
        uid = profile.get("user_id")
        if uid and uid in user_data:
            user_data[uid]["profile_completeness"] = profile.get("profile_completeness", 0) or 0
    
    # 6. Get failed payments per org (single query)
    if org_ids:
        failed_payments = supabase.table("payment_history") \
            .select("organization_id") \
            .eq("status", "failed") \
            .gte("created_at", month_ago.isoformat()) \
            .in_("organization_id", list(org_ids)) \
            .execute()
        
        orgs_with_failed = {fp.get("organization_id") for fp in (failed_payments.data or [])}
        
        for uid, data in user_data.items():
            if data.get("org_id") in orgs_with_failed:
                user_data[uid]["has_failed_payment"] = True
    
    return user_data


def _calculate_health_score_from_data(data: Dict[str, Any]) -> int:
    """
    Calculate health score from pre-fetched data.
    
    Scoring (start at 100, deduct for issues):
    - Inactivity: -10 (7d), -20 (14d), -30 (30d+)
    - Errors: -10 per 10% error rate (max -25)
    - Low usage: -15 if <10% of limit used
    - Incomplete profile: -10 if <50%, -5 if <80%
    - Payment issues: -20 if has failed payment
    """
    score = 100
    now = datetime.utcnow()
    week_ago = now - timedelta(days=7)
    two_weeks_ago = now - timedelta(days=14)
    month_ago = now - timedelta(days=30)
    
    # Activity penalty
    last_activity_str = data.get("last_activity")
    if last_activity_str:
        try:
            last_active = datetime.fromisoformat(last_activity_str.replace("Z", "+00:00")).replace(tzinfo=None)
            if last_active < month_ago:
                score -= 30
            elif last_active < two_weeks_ago:
                score -= 20
            elif last_active < week_ago:
                score -= 10
        except (ValueError, TypeError):
            score -= 30  # Can't parse = assume inactive
    else:
        score -= 30  # No activity
    
    # Error rate penalty
    total_count = data.get("total_count", 0)
    error_count = data.get("error_count", 0)
    if total_count > 0:
        error_rate = error_count / total_count
        if error_rate > 0.3:
            score -= 25
        elif error_rate > 0.2:
            score -= 15
        elif error_rate > 0.1:
            score -= 10
    
    # Usage penalty
    flow_limit = data.get("flow_limit", 0)
    flow_count = data.get("flow_count", 0)
    if flow_limit > 0:
        usage_pct = flow_count / flow_limit
        if usage_pct < 0.1:
            score -= 15
        elif usage_pct < 0.3:
            score -= 10
    
    # Profile penalty
    completeness = data.get("profile_completeness", 0)
    if completeness < 50:
        score -= 10
    elif completeness < 80:
        score -= 5
    
    # Payment penalty
    if data.get("has_failed_payment"):
        score -= 20
    
    return max(0, min(100, score))


@router.get("/recent-activity", response_model=RecentActivityResponse)
async def get_recent_activity(
    limit: int = 10,
    admin: AdminContext = Depends(get_admin_user)
):
    # Validate limit (prevent excessive queries)
    limit = min(max(limit, 1), 50)
    """
    Get recent activity feed from REAL database data.
    
    Returns the most recent researches, preparations, and follow-ups
    with user info.
    """
    supabase = get_supabase_service()
    raw_activities = []
    
    try:
        # Get recent research briefs (without user join - FK goes to auth.users not public.users)
        researches = supabase.table("research_briefs") \
            .select("id, user_id, company_name, status, created_at") \
            .order("created_at", desc=True) \
            .limit(limit) \
            .execute()
        
        for r in (researches.data or []):
            raw_activities.append({
                "id": r["id"],
                "type": "research",
                "user_id": r.get("user_id") or "",
                "title": r.get("company_name") or "Unknown Company",
                "status": r.get("status") or "unknown",
                "created_at": r.get("created_at") or ""
            })
        
        # Get recent meeting preps
        preps = supabase.table("meeting_preps") \
            .select("id, user_id, prospect_company_name, status, created_at") \
            .order("created_at", desc=True) \
            .limit(limit) \
            .execute()
        
        for p in (preps.data or []):
            raw_activities.append({
                "id": p["id"],
                "type": "preparation",
                "user_id": p.get("user_id") or "",
                "title": p.get("prospect_company_name") or "Meeting Prep",
                "status": p.get("status") or "unknown",
                "created_at": p.get("created_at") or ""
            })
        
        # Get recent followups
        followups = supabase.table("followups") \
            .select("id, user_id, prospect_company_name, status, created_at") \
            .order("created_at", desc=True) \
            .limit(limit) \
            .execute()
        
        for f in (followups.data or []):
            raw_activities.append({
                "id": f["id"],
                "type": "followup",
                "user_id": f.get("user_id") or "",
                "title": f.get("prospect_company_name") or "Follow-up",
                "status": f.get("status") or "unknown",
                "created_at": f.get("created_at") or ""
            })
        
        # Collect unique user_ids and batch query users
        user_ids = list(set(a["user_id"] for a in raw_activities if a["user_id"]))
        user_map = {}
        
        if user_ids:
            users_result = supabase.table("users") \
                .select("id, email, full_name") \
                .in_("id", user_ids) \
                .execute()
            
            for u in (users_result.data or []):
                user_map[u["id"]] = {
                    "email": u.get("email") or "",
                    "full_name": u.get("full_name") or ""
                }
        
        # Build activities with user info
        activities = []
        for a in raw_activities:
            user_data = user_map.get(a["user_id"], {})
            activities.append(RecentActivityItem(
                id=a["id"],
                type=a["type"],
                user_name=user_data.get("full_name") or "Unknown",
                user_email=user_data.get("email") or "",
                user_id=a["user_id"],
                title=a["title"],
                status=a["status"],
                created_at=a["created_at"]
            ))
        
        # Sort all by created_at and take top N
        activities.sort(key=lambda x: x.created_at, reverse=True)
        activities = activities[:limit]
        
        return RecentActivityResponse(activities=activities)
        
    except Exception as e:
        logger.error(f"Error getting recent activity: {e}")
        return RecentActivityResponse(activities=[])

