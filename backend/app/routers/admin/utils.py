"""
Admin Panel Utilities
=====================

Shared utilities for admin panel endpoints including:
- Audit logging
- Health score calculation
- Common queries
"""

from typing import Optional, Dict, Any
from uuid import UUID
from datetime import datetime, timedelta
from fastapi import Request

from app.database import get_supabase_service


# ============================================================
# Audit Logging
# ============================================================

async def log_admin_action(
    admin_id: str,
    action: str,
    target_type: Optional[str] = None,
    target_id: Optional[UUID] = None,
    target_identifier: Optional[str] = None,
    details: Optional[Dict[str, Any]] = None,
    request: Optional[Request] = None
) -> None:
    """
    Log an admin action to the audit log.
    
    Args:
        admin_id: The admin_users.id of the acting admin
        action: Action identifier (e.g., 'user.view', 'user.reset_flows')
        target_type: Type of target ('user', 'organization', 'alert', etc.)
        target_id: UUID of the target entity
        target_identifier: Human-readable identifier (email, name)
        details: Additional context as JSON
        request: FastAPI request for IP/user-agent extraction
    """
    supabase = get_supabase_service()
    
    ip_address = None
    user_agent = None
    
    if request:
        # Get real IP from X-Forwarded-For header (Railway/Cloudflare)
        forwarded = request.headers.get("x-forwarded-for")
        if forwarded:
            ip_address = forwarded.split(",")[0].strip()
        else:
            ip_address = request.client.host if request.client else None
        
        user_agent = request.headers.get("user-agent")
    
    try:
        supabase.table("admin_audit_log").insert({
            "admin_user_id": admin_id,
            "action": action,
            "target_type": target_type,
            "target_id": str(target_id) if target_id else None,
            "target_identifier": target_identifier,
            "details": details,
            "ip_address": ip_address,
            "user_agent": user_agent
        }).execute()
    except Exception as e:
        # Don't fail the request if audit logging fails
        # In production, this should go to error monitoring
        print(f"Failed to log admin action: {e}")


# ============================================================
# Health Score Calculation
# ============================================================

def calculate_health_score(user_data: Dict[str, Any]) -> int:
    """
    Calculate user health score based on activity and success metrics.
    
    Scoring:
    - Base: 100 points
    - Deductions for various issues
    - Minimum: 0, Maximum: 100
    
    Args:
        user_data: Dict with keys:
            - plan: Subscription plan
            - days_since_last_activity: Days since last activity
            - error_count_30d: Errors in last 30 days
            - flow_usage_percent: Usage as percentage (0-1)
            - profile_completeness: Profile completeness (0-100)
            - has_failed_payment: Whether payment has failed
    
    Returns:
        Health score from 0-100
    """
    score = 100
    
    # Inactivity penalty (max -30)
    days_inactive = user_data.get("days_since_last_activity", 0)
    if days_inactive > 30:
        score -= 30
    elif days_inactive > 14:
        score -= 20
    elif days_inactive > 7:
        score -= 10
    
    # Error rate penalty (max -25)
    error_count = user_data.get("error_count_30d", 0)
    if error_count > 10:
        score -= 25
    elif error_count > 5:
        score -= 15
    elif error_count > 2:
        score -= 10
    
    # Low usage penalty (max -15) - only for paid plans
    plan = user_data.get("plan", "free")
    if plan != "free":
        usage_percent = user_data.get("flow_usage_percent", 0)
        if usage_percent < 0.1:
            score -= 15
        elif usage_percent < 0.3:
            score -= 10
    
    # Incomplete profile penalty (max -10)
    profile_completeness = user_data.get("profile_completeness", 0)
    if profile_completeness < 50:
        score -= 10
    elif profile_completeness < 80:
        score -= 5
    
    # Payment issues penalty (max -20)
    if user_data.get("has_failed_payment"):
        score -= 20
    
    return max(0, min(100, score))


def get_health_status(score: int) -> str:
    """
    Get health status label from score.
    
    Returns:
        'healthy' (80-100), 'at_risk' (50-79), or 'critical' (0-49)
    """
    if score >= 80:
        return "healthy"
    elif score >= 50:
        return "at_risk"
    else:
        return "critical"


# ============================================================
# Common Queries
# ============================================================

async def get_user_with_details(user_id: str) -> Optional[Dict[str, Any]]:
    """
    Get user details with organization and subscription info.
    
    Returns comprehensive user data for admin view.
    """
    supabase = get_supabase_service()
    
    # Get user basic info
    user_result = supabase.table("users") \
        .select("id, email, full_name, created_at") \
        .eq("id", user_id) \
        .maybe_single() \
        .execute()
    
    if not user_result.data:
        return None
    
    user = user_result.data
    
    # Get organization membership
    org_result = supabase.table("organization_members") \
        .select("organization_id, role, organizations(id, name)") \
        .eq("user_id", user_id) \
        .maybe_single() \
        .execute()
    
    organization = None
    if org_result.data:
        org_data = org_result.data
        organization = {
            "id": org_data["organization_id"],
            "name": org_data["organizations"]["name"] if org_data["organizations"] else None,
            "role": org_data["role"]
        }
    
    # Get subscription info
    subscription = None
    if organization:
        sub_result = supabase.table("organization_subscriptions") \
            .select("plan_id, status, stripe_customer_id, trial_ends_at, subscription_plans(name, price_cents, features)") \
            .eq("organization_id", organization["id"]) \
            .maybe_single() \
            .execute()
        
        if sub_result.data:
            sub_data = sub_result.data
            subscription = {
                "plan_id": sub_data["plan_id"],
                "plan_name": sub_data["subscription_plans"]["name"] if sub_data["subscription_plans"] else None,
                "status": sub_data["status"],
                "stripe_customer_id": sub_data["stripe_customer_id"],
                "trial_ends_at": sub_data["trial_ends_at"],
                "features": sub_data["subscription_plans"]["features"] if sub_data["subscription_plans"] else {}
            }
    
    # Get usage records for current month
    usage = None
    if organization:
        usage_result = supabase.table("usage_records") \
            .select("*") \
            .eq("organization_id", organization["id"]) \
            .gte("period_start", datetime.utcnow().replace(day=1).isoformat()) \
            .maybe_single() \
            .execute()
        
        if usage_result.data:
            usage = usage_result.data
    
    # Get flow pack balance
    flow_pack_balance = 0
    if organization:
        pack_result = supabase.table("flow_packs") \
            .select("flows_remaining") \
            .eq("organization_id", organization["id"]) \
            .eq("status", "active") \
            .execute()
        
        if pack_result.data:
            flow_pack_balance = sum(p["flows_remaining"] for p in pack_result.data)
    
    return {
        "user": user,
        "organization": organization,
        "subscription": subscription,
        "usage": usage,
        "flow_pack_balance": flow_pack_balance
    }


async def get_organization_activity_count(organization_id: str, days: int = 30) -> int:
    """Get count of activities for organization in last N days."""
    supabase = get_supabase_service()
    
    cutoff = datetime.utcnow() - timedelta(days=days)
    cutoff = cutoff.replace(hour=0, minute=0, second=0, microsecond=0)
    
    result = supabase.table("prospect_activities") \
        .select("id", count="exact") \
        .eq("organization_id", organization_id) \
        .gte("created_at", cutoff.isoformat()) \
        .execute()
    
    return result.count or 0

