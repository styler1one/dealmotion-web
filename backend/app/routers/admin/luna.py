"""
Admin Luna Router
==================

Admin endpoints for Luna shadow mode monitoring and comparison.
SPEC-046-Luna-Unified-AI-Assistant
"""

from fastapi import APIRouter, Depends
from typing import Optional, List, Dict, Any
from datetime import datetime, timedelta
import logging

from app.deps import get_admin_user, AdminContext
from app.database import get_supabase_service
from .models import CamelModel

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/luna", tags=["admin-luna"])


# ============================================================
# Response Models
# ============================================================

class LunaMessageSummary(CamelModel):
    """Summary of a Luna message for admin view."""
    id: str
    user_id: str
    user_email: Optional[str] = None
    message_type: str
    status: str
    priority: int
    title: str
    created_at: str
    viewed_at: Optional[str] = None
    acted_at: Optional[str] = None


class LunaShadowStats(CamelModel):
    """Luna shadow mode statistics."""
    total_messages_created: int
    messages_by_status: Dict[str, int]
    messages_by_type: Dict[str, int]
    unique_users_reached: int
    shadow_mode_enabled: bool
    luna_enabled: bool
    widget_enabled: bool
    period_days: int


class LunaComparisonStats(CamelModel):
    """Comparison between Luna and Autopilot."""
    luna_messages_created: int
    autopilot_proposals_created: int
    luna_acceptance_rate: float
    autopilot_acceptance_rate: float
    luna_active_users: int
    autopilot_active_users: int
    period_days: int


class LunaRecentMessagesResponse(CamelModel):
    """Response with recent Luna messages."""
    messages: List[LunaMessageSummary]
    total_count: int


# ============================================================
# Endpoints
# ============================================================

@router.get("/stats", response_model=LunaShadowStats)
async def get_luna_shadow_stats(
    days: int = 7,
    admin_ctx: AdminContext = Depends(get_admin_user)
):
    """
    Get Luna shadow mode statistics.
    
    Shows message creation stats to validate Luna is working correctly
    before enabling it for users.
    """
    supabase = get_supabase_service()
    
    try:
        # Get date range
        start_date = datetime.utcnow() - timedelta(days=days)
        start_str = start_date.isoformat()
        
        # Get all Luna messages in period
        messages_result = supabase.table("luna_messages") \
            .select("id, status, message_type, user_id") \
            .gte("created_at", start_str) \
            .execute()
        
        messages = messages_result.data or []
        
        # Calculate stats
        messages_by_status: Dict[str, int] = {}
        messages_by_type: Dict[str, int] = {}
        unique_users = set()
        
        for msg in messages:
            status = msg.get("status", "unknown")
            msg_type = msg.get("message_type", "unknown")
            user_id = msg.get("user_id")
            
            messages_by_status[status] = messages_by_status.get(status, 0) + 1
            messages_by_type[msg_type] = messages_by_type.get(msg_type, 0) + 1
            if user_id:
                unique_users.add(user_id)
        
        # Get feature flags
        flags_result = supabase.table("luna_feature_flags") \
            .select("flag_name, flag_value") \
            .execute()
        
        flags = {f["flag_name"]: f["flag_value"] for f in (flags_result.data or [])}
        
        return LunaShadowStats(
            total_messages_created=len(messages),
            messages_by_status=messages_by_status,
            messages_by_type=messages_by_type,
            unique_users_reached=len(unique_users),
            shadow_mode_enabled=flags.get("luna_shadow_mode", False),
            luna_enabled=flags.get("luna_enabled", False),
            widget_enabled=flags.get("luna_widget_enabled", False),
            period_days=days
        )
        
    except Exception as e:
        logger.error(f"Error getting Luna shadow stats: {e}")
        return LunaShadowStats(
            total_messages_created=0,
            messages_by_status={},
            messages_by_type={},
            unique_users_reached=0,
            shadow_mode_enabled=False,
            luna_enabled=False,
            widget_enabled=False,
            period_days=days
        )


@router.get("/comparison", response_model=LunaComparisonStats)
async def get_luna_autopilot_comparison(
    days: int = 7,
    admin_ctx: AdminContext = Depends(get_admin_user)
):
    """
    Compare Luna performance with existing Autopilot.
    
    Useful during shadow mode to validate Luna is creating
    similar or better suggestions than Autopilot.
    """
    supabase = get_supabase_service()
    
    try:
        start_date = datetime.utcnow() - timedelta(days=days)
        start_str = start_date.isoformat()
        
        # Get Luna stats
        luna_result = supabase.table("luna_messages") \
            .select("id, status, user_id") \
            .gte("created_at", start_str) \
            .execute()
        
        luna_messages = luna_result.data or []
        luna_total = len(luna_messages)
        luna_accepted = sum(1 for m in luna_messages if m.get("status") == "completed")
        luna_users = set(m.get("user_id") for m in luna_messages if m.get("user_id"))
        
        # Get Autopilot stats
        autopilot_result = supabase.table("autopilot_proposals") \
            .select("id, status, user_id") \
            .gte("created_at", start_str) \
            .execute()
        
        autopilot_proposals = autopilot_result.data or []
        autopilot_total = len(autopilot_proposals)
        autopilot_accepted = sum(1 for p in autopilot_proposals if p.get("status") in ["completed", "accepted"])
        autopilot_users = set(p.get("user_id") for p in autopilot_proposals if p.get("user_id"))
        
        return LunaComparisonStats(
            luna_messages_created=luna_total,
            autopilot_proposals_created=autopilot_total,
            luna_acceptance_rate=luna_accepted / luna_total if luna_total > 0 else 0.0,
            autopilot_acceptance_rate=autopilot_accepted / autopilot_total if autopilot_total > 0 else 0.0,
            luna_active_users=len(luna_users),
            autopilot_active_users=len(autopilot_users),
            period_days=days
        )
        
    except Exception as e:
        logger.error(f"Error getting comparison stats: {e}")
        return LunaComparisonStats(
            luna_messages_created=0,
            autopilot_proposals_created=0,
            luna_acceptance_rate=0.0,
            autopilot_acceptance_rate=0.0,
            luna_active_users=0,
            autopilot_active_users=0,
            period_days=days
        )


@router.get("/messages", response_model=LunaRecentMessagesResponse)
async def get_recent_luna_messages(
    limit: int = 50,
    status: Optional[str] = None,
    message_type: Optional[str] = None,
    user_id: Optional[str] = None,
    admin_ctx: AdminContext = Depends(get_admin_user)
):
    """
    Get recent Luna messages for admin inspection.
    
    Allows filtering by status, type, and user to debug
    detection and execution issues.
    """
    supabase = get_supabase_service()
    
    try:
        # Build query
        query = supabase.table("luna_messages") \
            .select("id, user_id, message_type, status, priority, title, created_at, viewed_at, acted_at")
        
        if status:
            query = query.eq("status", status)
        if message_type:
            query = query.eq("message_type", message_type)
        if user_id:
            query = query.eq("user_id", user_id)
        
        result = query \
            .order("created_at", desc=True) \
            .limit(limit) \
            .execute()
        
        messages = []
        for msg in (result.data or []):
            # Try to get user email
            user_email = None
            if msg.get("user_id"):
                user_result = supabase.table("users") \
                    .select("email") \
                    .eq("id", msg["user_id"]) \
                    .limit(1) \
                    .execute()
                if user_result.data:
                    user_email = user_result.data[0].get("email")
            
            messages.append(LunaMessageSummary(
                id=msg["id"],
                user_id=msg.get("user_id", ""),
                user_email=user_email,
                message_type=msg.get("message_type", ""),
                status=msg.get("status", ""),
                priority=msg.get("priority", 50),
                title=msg.get("title", ""),
                created_at=msg.get("created_at", ""),
                viewed_at=msg.get("viewed_at"),
                acted_at=msg.get("acted_at")
            ))
        
        # Get total count
        count_query = supabase.table("luna_messages").select("id", count="exact")
        if status:
            count_query = count_query.eq("status", status)
        if message_type:
            count_query = count_query.eq("message_type", message_type)
        if user_id:
            count_query = count_query.eq("user_id", user_id)
        
        count_result = count_query.execute()
        total_count = count_result.count or len(messages)
        
        return LunaRecentMessagesResponse(
            messages=messages,
            total_count=total_count
        )
        
    except Exception as e:
        logger.error(f"Error getting recent messages: {e}")
        return LunaRecentMessagesResponse(
            messages=[],
            total_count=0
        )


@router.post("/flags/{flag_name}")
async def update_luna_flag(
    flag_name: str,
    enabled: bool,
    admin_ctx: AdminContext = Depends(get_admin_user)
):
    """
    Update a Luna feature flag.
    
    Available flags:
    - luna_enabled: Master switch for Luna UI
    - luna_shadow_mode: Detection runs but UI hidden
    - luna_widget_enabled: Floating widget visibility
    - luna_p1_features: P1 features (deal analysis, coaching)
    """
    supabase = get_supabase_service()
    
    valid_flags = ["luna_enabled", "luna_shadow_mode", "luna_widget_enabled", "luna_p1_features"]
    if flag_name not in valid_flags:
        return {"success": False, "error": f"Invalid flag. Valid flags: {valid_flags}"}
    
    try:
        result = supabase.table("luna_feature_flags") \
            .update({"flag_value": enabled}) \
            .eq("flag_name", flag_name) \
            .execute()
        
        if not result.data:
            return {"success": False, "error": "Flag not found"}
        
        logger.info(f"Admin {admin_ctx.admin_id} set {flag_name} to {enabled}")
        
        return {"success": True, "flag_name": flag_name, "enabled": enabled}
        
    except Exception as e:
        logger.error(f"Error updating flag: {e}")
        return {"success": False, "error": str(e)}


@router.post("/detect/{user_id}")
async def trigger_detection_for_user(
    user_id: str,
    admin_ctx: AdminContext = Depends(get_admin_user)
):
    """
    Manually trigger Luna detection for a specific user.
    
    Useful for testing and debugging detection rules.
    """
    try:
        from app.inngest.client import inngest_client
        
        # Get organization_id
        supabase = get_supabase_service()
        org_result = supabase.table("organization_members") \
            .select("organization_id") \
            .eq("user_id", user_id) \
            .limit(1) \
            .execute()
        
        org_id = org_result.data[0]["organization_id"] if org_result.data else None
        
        # Send event
        await inngest_client.send({
            "name": "dealmotion/luna.detect.user",
            "data": {
                "user_id": user_id,
                "organization_id": org_id,
                "trigger_source": "admin_manual"
            }
        })
        
        logger.info(f"Admin {admin_ctx.admin_id} triggered detection for user {user_id}")
        
        return {"success": True, "user_id": user_id}
        
    except Exception as e:
        logger.error(f"Error triggering detection: {e}")
        return {"success": False, "error": str(e)}
