"""
Email Invite Inngest Functions.

Handles processing of inbound email invites to notes@dealmotion.ai.

SPEC-043 Phase 2: Email-based AI Notetaker Invite

Events:
- dealmotion/ai-notetaker.email.received: Triggered when email arrives

Flow:
1. Parse email and extract ICS attachment
2. Match organizer email to DealMotion user
3. Use ProspectMatcher for smart prospect/contact matching
4. Schedule AI Notetaker via Recall.ai
5. Send confirmation email
"""

import logging
import base64
import re
from datetime import datetime, timedelta, timezone
from inngest import TriggerEvent

from app.inngest.client import inngest_client
from app.database import get_supabase_service
from app.services.ics_parser import ics_parser
from app.services.recall_service import recall_service, RecallBotConfig
from app.services.prospect_matcher import ProspectMatcher

logger = logging.getLogger(__name__)


# Our notetaker email addresses to filter out from attendees
NOTETAKER_EMAILS = {"notes@dealmotion.ai", "notes@parse.dealmotion.ai"}


def parse_emails_from_header(header_value: str) -> list[str]:
    """
    Parse email addresses from email header (To, Cc, From).
    
    Handles formats like:
    - "Name" <email@example.com>
    - <email@example.com>
    - email@example.com
    - Multiple comma-separated addresses
    
    Returns list of lowercase email addresses.
    """
    if not header_value:
        return []
    
    emails = []
    # Find all email addresses using regex
    pattern = r'[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}'
    matches = re.findall(pattern, header_value)
    
    for email in matches:
        email_lower = email.lower()
        # Filter out our notetaker emails
        if email_lower not in NOTETAKER_EMAILS:
            emails.append(email_lower)
    
    return emails


def parse_attendees_from_header(header_value: str) -> list[dict]:
    """
    Parse attendees with name AND email from email header.
    
    This is needed for ProspectMatcher which uses name-based matching.
    
    Handles formats like:
    - "Geert Menting" <geert.menting@hoobr.nl>
    - <geert.menting@hoobr.nl>
    - geert.menting@hoobr.nl
    - Multiple comma-separated addresses
    
    Returns list of {"email": str, "name": str} dicts.
    """
    if not header_value:
        return []
    
    attendees = []
    
    # Pattern to match "Name" <email> or just <email> or just email
    # Group 1: quoted name, Group 2: unquoted name, Group 3: email in brackets, Group 4: plain email
    pattern = r'(?:"([^"]+)"|([^<,]+?))?\s*<([^>]+)>|([a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,})'
    
    for match in re.finditer(pattern, header_value):
        quoted_name = match.group(1)
        unquoted_name = match.group(2)
        bracketed_email = match.group(3)
        plain_email = match.group(4)
        
        email = (bracketed_email or plain_email or "").lower().strip()
        name = (quoted_name or unquoted_name or "").strip()
        
        if email and email not in NOTETAKER_EMAILS:
            attendees.append({
                "email": email,
                "name": name
            })
            if name:
                logger.debug(f"Parsed attendee: {name} <{email}>")
    
    return attendees


# =============================================================================
# Helper Functions
# =============================================================================

def match_user_by_email(organizer_email: str) -> dict | None:
    """
    Match organizer email to a DealMotion user.
    
    Returns user info dict or None if not found.
    """
    supabase = get_supabase_service()
    
    # First, find the user by email in organization_members (joined with organization)
    # The users table syncs with auth.users and has id, email
    result = supabase.table("users").select(
        "id, email"
    ).eq("email", organizer_email.lower()).limit(1).execute()
    
    if not result.data or len(result.data) == 0:
        logger.warning(f"No user found for email: {organizer_email}")
        return None
    
    user_id = result.data[0]["id"]
    user_email = result.data[0]["email"]
    
    # Get organization_id from organization_members
    org_result = supabase.table("organization_members").select(
        "organization_id"
    ).eq("user_id", user_id).limit(1).execute()
    
    if not org_result.data or len(org_result.data) == 0:
        logger.warning(f"User {user_id} not in any organization")
        return None
    
    organization_id = org_result.data[0]["organization_id"]
    
    # Try to get name from sales_profiles
    name = None
    profile_result = supabase.table("sales_profiles").select(
        "full_name"
    ).eq("user_id", user_id).limit(1).execute()
    
    if profile_result.data and len(profile_result.data) > 0:
        name = profile_result.data[0].get("full_name")
    
    user = {
        "id": user_id,
        "email": user_email,
        "name": name,
        "organization_id": organization_id
    }
    
    logger.info(f"Matched email {organizer_email} to user {user_id} in org {organization_id}")
    return user


async def find_prospect_and_contacts(
    organization_id: str, 
    meeting_title: str,
    attendees: list[dict],
    organizer_email: str | None = None,
    calendar_meeting_id: str | None = None
) -> tuple[str | None, list[str]]:
    """
    Use ProspectMatcher for smart prospect and contact matching.
    
    Uses the same logic as auto-record/calendar-sync:
    - Contact name matching (92% confidence) - HIGHEST PRIORITY
    - Email exact match (95% confidence)
    - Email domain match (85% confidence)
    
    Args:
        attendees: List of {"email": str, "name": str} dicts (same format as calendar sync)
    
    If calendar_meeting_id is provided, ProspectMatcher will auto-link
    the meeting to the matched prospect and contacts (same as calendar sync).
    
    Returns (prospect_id, contact_ids) tuple.
    """
    logger.info(f"[EMAIL-INVITE] Finding prospect/contacts for org={organization_id}, title='{meeting_title}', attendees={attendees}, meeting_id={calendar_meeting_id}")
    
    if not attendees:
        logger.warning("[EMAIL-INVITE] No attendees provided for matching!")
        return None, []
    
    supabase = get_supabase_service()
    matcher = ProspectMatcher(supabase)
    
    # Log attendee details for debugging
    for a in attendees:
        logger.info(f"[EMAIL-INVITE] Attendee: name='{a.get('name')}', email='{a.get('email')}'")
    
    logger.info(f"[EMAIL-INVITE] Calling ProspectMatcher with {len(attendees)} attendees")
    
    # Use ProspectMatcher for intelligent matching
    # Note: match_meeting returns a MatchResult dataclass
    # If calendar_meeting_id is provided, ProspectMatcher will auto-link when confidence >= 80%
    # Attendees format: [{"email": "...", "name": "..."}] - same as calendar sync
    result = await matcher.match_meeting(
        meeting_id=calendar_meeting_id or "skip-auto-link",  # Real ID enables auto-linking!
        meeting_title=meeting_title,
        attendees=attendees,  # Now includes names for name-based matching!
        organization_id=organization_id,
        organizer_email=organizer_email
    )
    
    # Extract results from MatchResult dataclass
    prospect_id = result.best_match.prospect_id if result.best_match else None
    contact_ids = result.matched_contact_ids or []
    confidence = result.best_match.confidence if result.best_match else 0
    auto_linked = result.auto_linked
    
    if prospect_id:
        link_status = "auto-linked" if auto_linked else "matched (not auto-linked)"
        logger.info(f"[EMAIL-INVITE] ProspectMatcher {link_status} prospect {prospect_id} with {confidence:.0%} confidence, contacts: {contact_ids}")
    else:
        logger.info(f"[EMAIL-INVITE] ProspectMatcher found no prospect match for meeting '{meeting_title}' with attendees {attendee_emails}")
    
    return prospect_id, contact_ids


def get_user_output_language(user_id: str) -> str:
    """Get user's preferred output language from settings."""
    supabase = get_supabase_service()
    
    result = supabase.table("user_settings").select(
        "default_output_language"
    ).eq("user_id", user_id).limit(1).execute()
    
    if result.data and len(result.data) > 0:
        return result.data[0].get("default_output_language") or "en"
    
    return "en"


def create_calendar_meeting(
    organization_id: str,
    user_id: str,
    meeting_url: str,
    meeting_title: str,
    meeting_platform: str,
    start_time: datetime,
    end_time: datetime | None,
    attendees: list[dict],
    prospect_id: str | None = None,
    contact_ids: list[str] | None = None,
    ics_uid: str | None = None,
    description: str | None = None,
    location: str | None = None,
) -> str:
    """
    Create a calendar_meetings record for email invites.
    
    This ensures email invites appear on /dashboard/meetings alongside
    calendar-synced meetings for consistent user experience.
    
    Args:
        attendees: List of {"email": str, "name": str} dicts (same format as calendar sync)
    """
    supabase = get_supabase_service()
    
    # Attendees already in correct format: [{"email": "...", "name": "..."}]
    attendees_json = attendees if attendees else []
    
    record = {
        "organization_id": organization_id,
        "user_id": user_id,
        # No calendar_connection_id for email invites (NULL)
        "calendar_connection_id": None,
        "external_event_id": ics_uid or f"email-invite-{datetime.now(timezone.utc).timestamp()}",
        "title": meeting_title,
        "description": description,
        "start_time": start_time.isoformat(),
        "end_time": (end_time or start_time + timedelta(hours=1)).isoformat(),
        "location": location,
        "meeting_url": meeting_url,
        "is_online": True,
        "platform": meeting_platform,
        "status": "confirmed",
        "attendees": attendees_json,
        "prospect_id": prospect_id,
        "contact_ids": contact_ids or [],
        "source": "email_invite",  # Mark origin
        "prospect_link_type": "auto" if prospect_id else None,
    }
    
    result = supabase.table("calendar_meetings").insert(record).execute()
    
    if not result.data:
        raise Exception("Failed to create calendar meeting record")
    
    meeting_id = result.data[0]["id"]
    logger.info(f"Created calendar_meeting: {meeting_id} (source=email_invite)")
    return meeting_id


def create_scheduled_recording(
    organization_id: str,
    user_id: str,
    meeting_url: str,
    meeting_title: str,
    meeting_platform: str,
    scheduled_time: datetime,
    recall_bot_id: str | None = None,
    prospect_id: str | None = None,
    contact_ids: list[str] | None = None,
    calendar_meeting_id: str | None = None,
) -> str:
    """Create a scheduled recording record in the database."""
    supabase = get_supabase_service()
    
    record = {
        "organization_id": organization_id,
        "user_id": user_id,
        "meeting_url": meeting_url,
        "meeting_title": meeting_title,
        "meeting_platform": meeting_platform,
        "scheduled_time": scheduled_time.isoformat(),
        "recall_bot_id": recall_bot_id,
        "prospect_id": prospect_id,
        "contact_ids": contact_ids or [],
        "calendar_meeting_id": calendar_meeting_id,
        "status": "scheduled" if recall_bot_id else "error",
        "source": "email_invite",  # Mark as coming from email
    }
    
    result = supabase.table("scheduled_recordings").insert(record).execute()
    
    if not result.data:
        raise Exception("Failed to create scheduled recording")
    
    recording_id = result.data[0]["id"]
    logger.info(f"Created scheduled recording: {recording_id} with prospect={prospect_id}, contacts={contact_ids}, calendar_meeting={calendar_meeting_id}")
    return recording_id


async def send_confirmation_email(
    user_email: str,
    user_name: str | None,
    meeting_title: str,
    meeting_time: datetime,
    meeting_platform: str,
):
    """
    Send confirmation email to user that AI Notetaker will join their meeting.
    
    TODO: Implement actual email sending via SendGrid/Resend
    """
    logger.info(f"[TODO] Send confirmation email to {user_email}: AI Notetaker scheduled for '{meeting_title}' at {meeting_time}")
    
    # Placeholder for email implementation
    # This would use SendGrid, Resend, or similar service
    # 
    # email_content = f"""
    # Hi {user_name or 'there'},
    # 
    # DealMotion AI Notes will join your meeting:
    # 
    # 📅 {meeting_title}
    # 🕐 {meeting_time.strftime('%B %d, %Y at %H:%M')}
    # 📍 {meeting_platform.title()}
    # 
    # After the meeting, your transcript and analysis will be available in DealMotion.
    # 
    # Best,
    # DealMotion Team
    # """
    
    return True


# =============================================================================
# Main Inngest Function
# =============================================================================

@inngest_client.create_function(
    fn_id="ai-notetaker-process-email-invite",
    trigger=TriggerEvent(event="dealmotion/ai-notetaker.email.received"),
    retries=3,
)
async def process_email_invite_fn(ctx, step):
    """
    Process an inbound email invite for AI Notetaker.
    
    Steps:
    1. Parse email and extract meeting details from ICS
    2. Match organizer email to DealMotion user
    3. Use ProspectMatcher for smart prospect/contact matching
    4. Schedule AI Notetaker via Recall.ai
    5. Create calendar_meeting record (appears on /dashboard/meetings)
    6. Save scheduled recording linked to calendar_meeting
    7. Send confirmation email
    """
    event_data = ctx.event.data
    raw_email_b64 = event_data["raw_email_b64"]
    sender = event_data.get("sender", "")
    subject = event_data.get("subject", "")
    to_address = event_data.get("to_address", "")
    
    logger.info(f"Processing email invite from: {sender}, subject: {subject}, to: {to_address}")
    
    # Step 1: Parse email and extract meeting details
    def parse_email():
        raw_email = base64.b64decode(raw_email_b64)
        invite = ics_parser.parse_email_for_ics(raw_email)
        
        if not invite:
            raise Exception("No valid meeting invite found in email")
        
        if not invite.meeting_url:
            raise Exception(f"No meeting URL found in invite. Title: {invite.title}")
        
        if not invite.organizer_email:
            raise Exception("No organizer email found in invite")
        
        # Debug logging for datetime parsing
        logger.info(f"[EMAIL-INVITE] Parsed ICS: title='{invite.title}', start_time={invite.start_time}, end_time={invite.end_time}")
        
        return invite.to_dict()
    
    invite_data = await step.run("parse-email", parse_email)
    
    meeting_url = invite_data["meeting_url"]
    meeting_platform = invite_data["meeting_platform"]
    meeting_title = invite_data["title"] or subject or "Meeting"
    organizer_email = invite_data["organizer_email"]
    start_time_str = invite_data["start_time"]
    
    # Get attendees: prefer ICS attendees, fallback to email To/Cc headers
    attendees = invite_data.get("attendees", [])
    if not attendees:
        # Microsoft Teams invites often don't include ATTENDEE fields in ICS
        # Parse recipients from email headers as fallback - WITH NAMES for ProspectMatcher!
        header_attendees = parse_attendees_from_header(to_address)
        
        # Filter out organizer (they're the meeting owner, not attendee)
        if organizer_email:
            org_email_lower = organizer_email.lower()
            header_attendees = [a for a in header_attendees if a["email"] != org_email_lower]
        
        attendees = header_attendees
        logger.info(f"[EMAIL-INVITE] No ICS attendees found, extracted from email headers: {attendees}")
    
    # Parse start time (timezone-aware)
    if start_time_str:
        start_time = datetime.fromisoformat(start_time_str)
        if start_time.tzinfo is None:
            start_time = start_time.replace(tzinfo=timezone.utc)
    else:
        start_time = datetime.now(timezone.utc) + timedelta(minutes=5)
    
    logger.info(f"Parsed invite: {meeting_title} on {meeting_platform}, starts at {start_time}")
    
    # Step 2: Match organizer to DealMotion user
    def match_user():
        user = match_user_by_email(organizer_email)
        if not user:
            raise Exception(f"No DealMotion account found for email: {organizer_email}")
        return user
    
    user = await step.run("match-user", match_user)
    user_id = user["id"]
    organization_id = user["organization_id"]
    user_name = user.get("name")
    user_email = user.get("email", organizer_email)
    
    # Step 3: Schedule AI Notetaker via Recall.ai
    async def schedule_bot():
        if not recall_service.is_configured():
            raise Exception("Recall.ai is not configured")
        
        now = datetime.now(timezone.utc)
        
        # Log for debugging
        logger.info(f"[EMAIL-INVITE] Scheduling bot: start_time={start_time}, now={now}, start_time > now = {start_time > now}")
        
        # Only schedule for future if meeting is more than 1 minute away
        if start_time > now + timedelta(minutes=1):
            join_at = start_time
            logger.info(f"[EMAIL-INVITE] Bot will join at scheduled time: {join_at}")
        else:
            join_at = None
            logger.info(f"[EMAIL-INVITE] Meeting is now or in past, bot will join immediately")
        
        config = RecallBotConfig(
            meeting_url=meeting_url,
            join_at=join_at
        )
        
        result = await recall_service.create_bot(config)
        
        if not result.get("success"):
            raise Exception(f"Failed to create Recall.ai bot: {result.get('error')}")
        
        return result["bot_id"]
    
    recall_bot_id = await step.run("schedule-bot", schedule_bot)
    
    # Step 4: Create calendar_meeting record FIRST (so we have a valid ID)
    # This enables ProspectMatcher to properly auto-link
    def save_calendar_meeting():
        # Get additional data from invite
        end_time_str = invite_data.get("end_time")
        end_time = None
        if end_time_str:
            end_time = datetime.fromisoformat(end_time_str)
            if end_time.tzinfo is None:
                end_time = end_time.replace(tzinfo=timezone.utc)
        
        # Create WITHOUT prospect/contact - ProspectMatcher will update these
        return create_calendar_meeting(
            organization_id=organization_id,
            user_id=user_id,
            meeting_url=meeting_url,
            meeting_title=meeting_title,
            meeting_platform=meeting_platform,
            start_time=start_time,
            end_time=end_time,
            attendees=attendees,
            prospect_id=None,  # Will be set by ProspectMatcher
            contact_ids=None,  # Will be set by ProspectMatcher
            ics_uid=invite_data.get("uid"),
            description=invite_data.get("description"),
            location=invite_data.get("location"),
        )
    
    calendar_meeting_id = await step.run("save-calendar-meeting", save_calendar_meeting)
    
    # Step 5: Use ProspectMatcher for smart prospect and contact matching
    # Now we have a real calendar_meeting_id, so ProspectMatcher can auto-link
    # This uses the same logic as calendar sync: email, domain, NAME matching
    async def find_prospect_contacts():
        prospect_id, contact_ids = await find_prospect_and_contacts(
            organization_id=organization_id,
            meeting_title=meeting_title,
            attendees=attendees,  # Now includes names from email headers!
            organizer_email=organizer_email,
            calendar_meeting_id=calendar_meeting_id,  # Pass real ID for auto-linking!
        )
        # Return as serializable dict (UUIDs as strings)
        return {
            "prospect_id": str(prospect_id) if prospect_id else None,
            "contact_ids": [str(cid) for cid in contact_ids] if contact_ids else []
        }
    
    match_result = await step.run("find-prospect-contacts", find_prospect_contacts)
    prospect_id = match_result.get("prospect_id")
    contact_ids = match_result.get("contact_ids", [])
    
    # Step 6: Save scheduled recording linked to calendar_meeting
    def save_recording():
        return create_scheduled_recording(
            organization_id=organization_id,
            user_id=user_id,
            meeting_url=meeting_url,
            meeting_title=meeting_title,
            meeting_platform=meeting_platform,
            scheduled_time=start_time,
            recall_bot_id=recall_bot_id,
            prospect_id=prospect_id,
            contact_ids=contact_ids,
            calendar_meeting_id=calendar_meeting_id,
        )
    
    recording_id = await step.run("save-recording", save_recording)
    
    # Step 7: Send confirmation email
    async def send_confirmation():
        await send_confirmation_email(
            user_email=user_email,
            user_name=user_name,
            meeting_title=meeting_title,
            meeting_time=start_time,
            meeting_platform=meeting_platform,
        )
        return True
    
    await step.run("send-confirmation", send_confirmation)
    
    logger.info(f"Email invite processed successfully: recording={recording_id}, bot={recall_bot_id}, calendar_meeting={calendar_meeting_id}")
    
    return {
        "recording_id": recording_id,
        "recall_bot_id": recall_bot_id,
        "calendar_meeting_id": calendar_meeting_id,
        "user_id": user_id,
        "meeting_title": meeting_title,
        "meeting_time": start_time.isoformat(),
        "status": "scheduled"
    }

