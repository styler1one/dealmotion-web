"""
Auto-Record Matcher Service - Determines if a meeting should be auto-recorded
SPEC-043: Calendar Integration with Auto-Record
"""
import logging
from datetime import datetime, timezone, timedelta
from typing import Dict, Any, Optional, List

from app.database import get_supabase_service

logger = logging.getLogger(__name__)


def should_auto_record(
    meeting: Dict[str, Any],
    settings: Dict[str, Any],
    organization_id: str
) -> Dict[str, Any]:
    """
    Determine if a calendar meeting should be auto-recorded.
    
    Args:
        meeting: Calendar meeting data
        settings: User's auto-record settings
        organization_id: User's organization ID
        
    Returns:
        {
            "should_record": bool,
            "reason": str,
            "matched_keyword": Optional[str]
        }
    """
    title = (meeting.get("title") or "").lower()
    
    # Check if it's an online meeting with a URL
    if not meeting.get("is_online") or not meeting.get("meeting_url"):
        return {
            "should_record": False,
            "reason": "Not an online meeting or no meeting URL"
        }
    
    # Check mode
    mode = settings.get("mode", "filtered")
    
    if mode == "none":
        return {
            "should_record": False,
            "reason": "Auto-record is disabled"
        }
    
    if mode == "all":
        return {
            "should_record": True,
            "reason": "Recording all online meetings"
        }
    
    # Mode is "filtered" - apply filters
    
    # Check minimum duration
    min_duration = settings.get("min_duration_minutes", 15)
    if min_duration > 0:
        start_time = meeting.get("start_time")
        end_time = meeting.get("end_time")
        
        if start_time and end_time:
            try:
                if isinstance(start_time, str):
                    start = datetime.fromisoformat(start_time.replace("Z", "+00:00"))
                else:
                    start = start_time
                if isinstance(end_time, str):
                    end = datetime.fromisoformat(end_time.replace("Z", "+00:00"))
                else:
                    end = end_time
                    
                duration_minutes = (end - start).total_seconds() / 60
                
                if duration_minutes < min_duration:
                    return {
                        "should_record": False,
                        "reason": f"Meeting duration ({int(duration_minutes)} min) is less than minimum ({min_duration} min)"
                    }
            except (ValueError, TypeError) as e:
                logger.warning(f"Failed to parse meeting times: {e}")
    
    # Check exclude keywords FIRST (they take priority)
    exclude_keywords = settings.get("exclude_keywords") or []
    for keyword in exclude_keywords:
        if keyword.lower() in title:
            return {
                "should_record": False,
                "reason": f"Title contains excluded keyword",
                "matched_keyword": keyword
            }
    
    # Check external attendees if required
    if settings.get("external_only", True):
        is_external = _has_external_attendees(meeting, organization_id)
        if not is_external:
            return {
                "should_record": False,
                "reason": "Meeting has no external attendees"
            }
    
    # Check include keywords
    include_keywords = settings.get("include_keywords") or []
    
    if include_keywords:
        for keyword in include_keywords:
            if keyword.lower() in title:
                return {
                    "should_record": True,
                    "reason": f"Title contains keyword",
                    "matched_keyword": keyword
                }
        
        # No include keyword matched
        return {
            "should_record": False,
            "reason": "Title does not contain any include keywords"
        }
    
    # No keywords configured, but has external attendees (if required)
    return {
        "should_record": True,
        "reason": "Online meeting with external attendees"
    }


def _has_external_attendees(meeting: Dict[str, Any], organization_id: str) -> bool:
    """
    Check if meeting has attendees from outside the organization.
    """
    attendees = meeting.get("attendees") or []
    
    if not attendees:
        # No attendee info, assume external to be safe
        return True
    
    # Get organization's email domains
    org_domains = _get_organization_domains(organization_id)
    
    if not org_domains:
        # Can't determine, assume external
        return True
    
    for attendee in attendees:
        email = attendee.get("email", "").lower()
        if not email:
            continue
        
        # Skip the organizer (they're internal)
        if attendee.get("is_organizer"):
            continue
        
        # Check if email domain is external
        domain = email.split("@")[-1] if "@" in email else ""
        
        if domain and domain not in org_domains:
            return True
    
    return False


def _get_organization_domains(organization_id: str) -> List[str]:
    """
    Get email domains associated with an organization.
    
    This checks:
    1. The organization's primary domain
    2. User email domains in the organization
    """
    try:
        supabase = get_supabase_service()
        
        # Get unique email domains from organization members
        members = supabase.table("users").select(
            "email"
        ).eq("organization_id", organization_id).execute()
        
        domains = set()
        for member in members.data or []:
            email = member.get("email", "")
            if "@" in email:
                domain = email.split("@")[-1].lower()
                domains.add(domain)
        
        # Also check organization_members for user emails
        org_members = supabase.table("organization_members").select(
            "users(email)"
        ).eq("organization_id", organization_id).execute()
        
        for om in org_members.data or []:
            user_data = om.get("users") or {}
            email = user_data.get("email", "")
            if "@" in email:
                domain = email.split("@")[-1].lower()
                domains.add(domain)
        
        return list(domains)
        
    except Exception as e:
        logger.error(f"Failed to get organization domains: {e}")
        return []


async def process_calendar_for_auto_record(user_id: str, organization_id: str):
    """
    Process a user's calendar and schedule AI Notetaker bots for matching meetings.
    
    Called after calendar sync completes.
    """
    supabase = get_supabase_service()
    
    try:
        # Get user's auto-record settings
        settings_result = supabase.table("auto_record_settings").select("*").eq(
            "user_id", user_id
        ).limit(1).execute()
        
        if not settings_result.data or not settings_result.data[0].get("enabled"):
            logger.debug(f"Auto-record disabled for user {user_id[:8]}...")
            return {"scheduled": 0, "skipped": 0}
        
        settings = settings_result.data[0]
        
        # Get upcoming online meetings that don't already have a scheduled recording
        # Use timezone-aware datetime for proper comparison with stored times
        now = datetime.now(timezone.utc)
        future = now + timedelta(days=14)  # Look ahead 14 days
        
        meetings_result = supabase.table("calendar_meetings").select(
            "id, external_event_id, title, start_time, end_time, is_online, meeting_url, attendees, status"
        ).eq(
            "user_id", user_id
        ).eq(
            "status", "confirmed"
        ).eq(
            "is_online", True
        ).not_.is_(
            "meeting_url", "null"
        ).gte(
            "start_time", now.isoformat()
        ).lte(
            "start_time", future.isoformat()
        ).execute()
        
        meetings = meetings_result.data or []
        
        scheduled_count = 0
        skipped_count = 0
        
        for meeting in meetings:
            # Check if already scheduled
            existing = supabase.table("scheduled_recordings").select("id").eq(
                "calendar_meeting_id", meeting["id"]
            ).limit(1).execute()
            
            if existing.data and len(existing.data) > 0:
                # Already scheduled
                continue
            
            # Check if should auto-record
            result = should_auto_record(meeting, settings, organization_id)
            
            if not result["should_record"]:
                skipped_count += 1
                matched_kw = result.get('matched_keyword', '')
                logger.warning(f"[AUTO-RECORD] Skipping '{meeting['title']}': {result['reason']} {f'({matched_kw})' if matched_kw else ''}")
                continue
            
            # Schedule the recording
            try:
                from app.services.recall_service import recall_service, RecallBotConfig
                from datetime import datetime as dt
                
                # Parse start time
                start_time = meeting["start_time"]
                if isinstance(start_time, str):
                    scheduled_time = dt.fromisoformat(start_time.replace("Z", "+00:00"))
                else:
                    scheduled_time = start_time
                
                # Validate meeting URL
                is_valid, platform = recall_service.validate_meeting_url(meeting["meeting_url"])
                
                if not is_valid:
                    logger.warning(f"Invalid meeting URL for '{meeting['title']}': {meeting['meeting_url']}")
                    continue
                
                # Create scheduled_recording record
                recording_data = {
                    "organization_id": organization_id,
                    "user_id": user_id,
                    "meeting_url": meeting["meeting_url"],
                    "meeting_title": meeting["title"],
                    "meeting_platform": platform,
                    "scheduled_time": scheduled_time.isoformat(),
                    "status": "scheduled",
                    "source": "calendar_sync",
                    "auto_scheduled": True,
                    "calendar_meeting_id": meeting["id"],
                    "calendar_event_id": meeting.get("external_event_id"),
                }
                
                insert_result = supabase.table("scheduled_recordings").insert(recording_data).execute()
                
                if not insert_result.data:
                    logger.error(f"Failed to create scheduled_recording for '{meeting['title']}'")
                    continue
                
                recording_id = insert_result.data[0]["id"]
                
                # Schedule with Recall.ai
                if recall_service.is_configured():
                    config = RecallBotConfig(
                        meeting_url=meeting["meeting_url"],
                        join_at=scheduled_time
                    )
                    
                    bot_result = await recall_service.create_bot(config)
                    
                    if bot_result.get("success"):
                        # Update with bot ID
                        supabase.table("scheduled_recordings").update({
                            "recall_bot_id": bot_result.get("bot_id")
                        }).eq("id", recording_id).execute()
                        
                        scheduled_count += 1
                        logger.info(
                            f"Auto-scheduled AI Notetaker for '{meeting['title']}' at {scheduled_time} "
                            f"(reason: {result['reason']})"
                        )
                    else:
                        # Failed to create bot, mark as error
                        supabase.table("scheduled_recordings").update({
                            "status": "error",
                            "error_message": f"Failed to create bot: {bot_result.get('error')}"
                        }).eq("id", recording_id).execute()
                        logger.error(f"Failed to create Recall bot for '{meeting['title']}': {bot_result.get('error')}")
                else:
                    logger.warning("Recall.ai not configured - cannot auto-schedule bot")
                
            except Exception as e:
                logger.error(f"Failed to schedule recording for '{meeting['title']}': {e}")
                continue
        
        logger.info(f"Auto-record for user {user_id[:8]}...: {scheduled_count} scheduled, {skipped_count} skipped")
        
        return {
            "scheduled": scheduled_count,
            "skipped": skipped_count
        }
        
    except Exception as e:
        logger.error(f"Failed to process calendar for auto-record: {e}")
        return {"scheduled": 0, "skipped": 0, "error": str(e)}

