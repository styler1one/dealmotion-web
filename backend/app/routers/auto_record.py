"""
Auto-Record Settings Router - API endpoints for AI Notetaker auto-recording
SPEC-043: Calendar Integration with Auto-Record

Note: All features are now available to everyone. Credits determine usage.
"""
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from typing import Optional, List, Tuple
import logging

from app.deps import get_user_org
from app.database import get_supabase_service

supabase = get_supabase_service()
logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1/auto-record", tags=["auto-record"])


# =============================================================================
# Pydantic Models
# =============================================================================

class AutoRecordSettings(BaseModel):
    """Auto-record settings for a user."""
    enabled: bool = Field(default=False, description="Master toggle for auto-recording")
    mode: str = Field(default="filtered", description="Mode: 'all', 'filtered', 'none'")
    external_only: bool = Field(default=True, description="Only record meetings with external attendees")
    min_duration_minutes: int = Field(default=15, ge=0, le=480, description="Minimum meeting duration to record")
    include_keywords: List[str] = Field(default=[], description="Keywords that trigger recording")
    exclude_keywords: List[str] = Field(default=[], description="Keywords that prevent recording")
    notify_before_join: bool = Field(default=True, description="Notify user before bot joins")
    notify_minutes_before: int = Field(default=2, ge=1, le=30, description="Minutes before join to notify")


class AutoRecordSettingsResponse(BaseModel):
    """Response containing auto-record settings."""
    id: Optional[str] = None
    enabled: bool
    mode: str
    external_only: bool
    min_duration_minutes: int
    include_keywords: List[str]
    exclude_keywords: List[str]
    notify_before_join: bool
    notify_minutes_before: int


class UpdateAutoRecordRequest(BaseModel):
    """Request to update auto-record settings."""
    enabled: Optional[bool] = None
    mode: Optional[str] = None
    external_only: Optional[bool] = None
    min_duration_minutes: Optional[int] = None
    include_keywords: Optional[List[str]] = None
    exclude_keywords: Optional[List[str]] = None
    notify_before_join: Optional[bool] = None
    notify_minutes_before: Optional[int] = None


# =============================================================================
# Default Keywords (localized for Dutch/English)
# =============================================================================

DEFAULT_INCLUDE_KEYWORDS = [
    # English
    "demo", "sales", "prospect", "client", "presentation", "discovery", 
    "closing", "proposal", "pitch", "intro", "call", "meeting",
    # Dutch
    "klant", "presentatie", "offerte", "kennismaking", "gesprek"
]

DEFAULT_EXCLUDE_KEYWORDS = [
    # English
    "standup", "daily", "weekly", "sync", "1:1", "one-on-one", "1-on-1",
    "internal", "lunch", "retro", "planning", "sprint", "refinement",
    "team meeting", "interview", "hr", "performance", "personal",
    # Dutch
    "intern", "teamoverleg", "sollicitatie", "prive", "privé", "dokter", "tandarts"
]


# =============================================================================
# Endpoints
# =============================================================================

@router.get("/settings", response_model=AutoRecordSettingsResponse)
async def get_settings(
    user_org: Tuple[str, str] = Depends(get_user_org)
):
    """
    Get auto-record settings for the current user.
    Returns defaults if no settings exist yet.
    
    Note: All features available to everyone - credits determine usage
    """
    user_id, organization_id = user_org
    
    try:
        result = supabase.table("auto_record_settings").select("*").eq(
            "user_id", user_id
        ).limit(1).execute()
        
        if result.data and len(result.data) > 0:
            settings = result.data[0]
            return AutoRecordSettingsResponse(
                id=settings["id"],
                enabled=settings.get("enabled", False),
                mode=settings.get("mode", "filtered"),
                external_only=settings.get("external_only", True),
                min_duration_minutes=settings.get("min_duration_minutes", 15),
                include_keywords=settings.get("include_keywords") or DEFAULT_INCLUDE_KEYWORDS,
                exclude_keywords=settings.get("exclude_keywords") or DEFAULT_EXCLUDE_KEYWORDS,
                notify_before_join=settings.get("notify_before_join", True),
                notify_minutes_before=settings.get("notify_minutes_before", 2)
            )
        
        # Return defaults if no settings exist
        return AutoRecordSettingsResponse(
            enabled=False,
            mode="filtered",
            external_only=True,
            min_duration_minutes=15,
            include_keywords=DEFAULT_INCLUDE_KEYWORDS,
            exclude_keywords=DEFAULT_EXCLUDE_KEYWORDS,
            notify_before_join=True,
            notify_minutes_before=2
        )
        
    except Exception as e:
        logger.error(f"Failed to get auto-record settings: {e}")
        raise HTTPException(status_code=500, detail="Failed to get settings")


@router.put("/settings", response_model=AutoRecordSettingsResponse)
async def update_settings(
    request: UpdateAutoRecordRequest,
    user_org: Tuple[str, str] = Depends(get_user_org)
):
    """
    Update auto-record settings for the current user.
    Creates settings if they don't exist (upsert).
    
    Note: All features available to everyone - credits determine usage
    """
    user_id, organization_id = user_org
    
    # Validate mode
    if request.mode and request.mode not in ["all", "filtered", "none"]:
        raise HTTPException(status_code=400, detail="Invalid mode. Must be 'all', 'filtered', or 'none'")
    
    try:
        # Check if settings exist
        existing = supabase.table("auto_record_settings").select("id").eq(
            "user_id", user_id
        ).limit(1).execute()
        
        # Build update data (only include non-None fields)
        update_data = {}
        if request.enabled is not None:
            update_data["enabled"] = request.enabled
        if request.mode is not None:
            update_data["mode"] = request.mode
        if request.external_only is not None:
            update_data["external_only"] = request.external_only
        if request.min_duration_minutes is not None:
            update_data["min_duration_minutes"] = request.min_duration_minutes
        if request.include_keywords is not None:
            update_data["include_keywords"] = request.include_keywords
        if request.exclude_keywords is not None:
            update_data["exclude_keywords"] = request.exclude_keywords
        if request.notify_before_join is not None:
            update_data["notify_before_join"] = request.notify_before_join
        if request.notify_minutes_before is not None:
            update_data["notify_minutes_before"] = request.notify_minutes_before
        
        if existing.data and len(existing.data) > 0:
            # Update existing
            result = supabase.table("auto_record_settings").update(
                update_data
            ).eq("id", existing.data[0]["id"]).execute()
        else:
            # Create new with defaults + updates
            insert_data = {
                "organization_id": organization_id,
                "user_id": user_id,
                "enabled": False,
                "mode": "filtered",
                "external_only": True,
                "min_duration_minutes": 15,
                "include_keywords": DEFAULT_INCLUDE_KEYWORDS,
                "exclude_keywords": DEFAULT_EXCLUDE_KEYWORDS,
                "notify_before_join": True,
                "notify_minutes_before": 2,
                **update_data
            }
            result = supabase.table("auto_record_settings").insert(insert_data).execute()
        
        if not result.data:
            raise HTTPException(status_code=500, detail="Failed to save settings")
        
        settings = result.data[0]
        
        logger.info(f"Updated auto-record settings for user {user_id[:8]}..., enabled={settings.get('enabled')}")
        
        return AutoRecordSettingsResponse(
            id=settings["id"],
            enabled=settings.get("enabled", False),
            mode=settings.get("mode", "filtered"),
            external_only=settings.get("external_only", True),
            min_duration_minutes=settings.get("min_duration_minutes", 15),
            include_keywords=settings.get("include_keywords") or DEFAULT_INCLUDE_KEYWORDS,
            exclude_keywords=settings.get("exclude_keywords") or DEFAULT_EXCLUDE_KEYWORDS,
            notify_before_join=settings.get("notify_before_join", True),
            notify_minutes_before=settings.get("notify_minutes_before", 2)
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to update auto-record settings: {e}")
        raise HTTPException(status_code=500, detail="Failed to save settings")


@router.post("/settings/reset-keywords")
async def reset_keywords(
    user_org: Tuple[str, str] = Depends(get_user_org)
):
    """
    Reset keywords to defaults.
    
    Note: All features available to everyone - credits determine usage
    """
    user_id, organization_id = user_org
    
    try:
        # Check if settings exist
        existing = supabase.table("auto_record_settings").select("id").eq(
            "user_id", user_id
        ).limit(1).execute()
        
        if existing.data and len(existing.data) > 0:
            result = supabase.table("auto_record_settings").update({
                "include_keywords": DEFAULT_INCLUDE_KEYWORDS,
                "exclude_keywords": DEFAULT_EXCLUDE_KEYWORDS
            }).eq("id", existing.data[0]["id"]).execute()
        else:
            # Create with defaults
            result = supabase.table("auto_record_settings").insert({
                "organization_id": organization_id,
                "user_id": user_id,
                "include_keywords": DEFAULT_INCLUDE_KEYWORDS,
                "exclude_keywords": DEFAULT_EXCLUDE_KEYWORDS
            }).execute()
        
        return {
            "success": True,
            "include_keywords": DEFAULT_INCLUDE_KEYWORDS,
            "exclude_keywords": DEFAULT_EXCLUDE_KEYWORDS
        }
        
    except Exception as e:
        logger.error(f"Failed to reset keywords: {e}")
        raise HTTPException(status_code=500, detail="Failed to reset keywords")


@router.get("/preview")
async def preview_auto_record(
    user_org: Tuple[str, str] = Depends(get_user_org)
):
    """
    Preview which upcoming meetings would be auto-recorded based on current settings.
    Useful for users to test their keyword configuration.
    
    Note: All features available to everyone - credits determine usage
    """
    user_id, organization_id = user_org
    
    try:
        # Get settings
        settings_result = supabase.table("auto_record_settings").select("*").eq(
            "user_id", user_id
        ).limit(1).execute()
        
        settings = settings_result.data[0] if settings_result.data else None
        
        if not settings or not settings.get("enabled"):
            return {
                "enabled": False,
                "meetings": [],
                "message": "Auto-record is disabled"
            }
        
        # Get upcoming calendar meetings
        from datetime import datetime, timedelta
        now = datetime.utcnow()
        future = now + timedelta(days=7)
        
        meetings_result = supabase.table("calendar_meetings").select(
            "id, title, start_time, end_time, is_online, meeting_url, attendees, status"
        ).eq(
            "user_id", user_id
        ).eq(
            "status", "confirmed"
        ).gte(
            "start_time", now.isoformat()
        ).lte(
            "start_time", future.isoformat()
        ).order("start_time").execute()
        
        meetings = meetings_result.data or []
        
        # Evaluate each meeting
        from app.services.auto_record_matcher import should_auto_record
        
        preview = []
        for meeting in meetings:
            result = should_auto_record(meeting, settings, organization_id)
            preview.append({
                "id": meeting["id"],
                "title": meeting["title"],
                "start_time": meeting["start_time"],
                "is_online": meeting.get("is_online", False),
                "will_record": result["should_record"],
                "reason": result["reason"],
                "matched_keyword": result.get("matched_keyword")
            })
        
        will_record_count = sum(1 for m in preview if m["will_record"])
        
        return {
            "enabled": True,
            "total_meetings": len(preview),
            "will_record": will_record_count,
            "will_skip": len(preview) - will_record_count,
            "meetings": preview
        }
        
    except Exception as e:
        logger.error(f"Failed to preview auto-record: {e}")
        raise HTTPException(status_code=500, detail="Failed to generate preview")


@router.post("/trigger")
async def trigger_auto_record(
    user_org: Tuple[str, str] = Depends(get_user_org)
):
    """
    Manually trigger auto-record processing for the current user.
    Useful for testing and debugging.
    
    Note: All features available to everyone - credits determine usage
    """
    user_id, organization_id = user_org
    
    try:
        from app.services.auto_record_matcher import process_calendar_for_auto_record
        
        result = await process_calendar_for_auto_record(user_id, organization_id)
        
        return {
            "success": True,
            "result": result
        }
        
    except Exception as e:
        logger.error(f"Failed to trigger auto-record: {e}")
        raise HTTPException(status_code=500, detail="Failed to trigger auto-record. Please try again.")


@router.get("/debug/meetings")
async def debug_meetings(
    user_org: Tuple[str, str] = Depends(get_user_org)
):
    """
    Debug endpoint: Show all upcoming calendar meetings with their auto-record eligibility.
    Shows why meetings might not be eligible for auto-recording.
    
    Note: All features available to everyone - credits determine usage
    """
    user_id, organization_id = user_org
    
    try:
        from datetime import datetime, timedelta
        
        now = datetime.utcnow()
        future = now + timedelta(days=14)
        
        # Get ALL upcoming meetings (no filters)
        meetings_result = supabase.table("calendar_meetings").select(
            "id, title, start_time, end_time, is_online, meeting_url, status, attendees"
        ).eq(
            "user_id", user_id
        ).gte(
            "start_time", now.isoformat()
        ).lte(
            "start_time", future.isoformat()
        ).order("start_time").execute()
        
        meetings = meetings_result.data or []
        
        # Check for existing scheduled recordings
        meeting_ids = [m["id"] for m in meetings]
        scheduled_result = supabase.table("scheduled_recordings").select(
            "calendar_meeting_id, status"
        ).in_("calendar_meeting_id", meeting_ids).execute() if meeting_ids else type('obj', (object,), {'data': []})()
        
        scheduled_map = {s["calendar_meeting_id"]: s["status"] for s in (scheduled_result.data or [])}
        
        debug_info = []
        for m in meetings:
            issues = []
            
            if not m.get("is_online"):
                issues.append("not_online")
            if not m.get("meeting_url"):
                issues.append("no_meeting_url")
            if m.get("status") != "confirmed":
                issues.append(f"status_is_{m.get('status')}")
            
            scheduled_status = scheduled_map.get(m["id"])
            
            debug_info.append({
                "id": m["id"],
                "title": m["title"],
                "start_time": m["start_time"],
                "is_online": m.get("is_online", False),
                "has_meeting_url": bool(m.get("meeting_url")),
                "meeting_url_preview": m.get("meeting_url", "")[:50] + "..." if m.get("meeting_url") and len(m.get("meeting_url", "")) > 50 else m.get("meeting_url"),
                "status": m.get("status"),
                "attendee_count": len(m.get("attendees") or []),
                "issues": issues,
                "eligible": len(issues) == 0,
                "already_scheduled": scheduled_status
            })
        
        eligible_count = sum(1 for d in debug_info if d["eligible"])
        
        return {
            "total_meetings": len(debug_info),
            "eligible_for_auto_record": eligible_count,
            "not_eligible": len(debug_info) - eligible_count,
            "meetings": debug_info
        }
        
    except Exception as e:
        logger.error(f"Failed to get debug meetings: {e}")
        raise HTTPException(status_code=500, detail="Failed to fetch meeting data. Please try again.")
