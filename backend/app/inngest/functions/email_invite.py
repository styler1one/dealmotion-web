"""
Email Invite Inngest Functions.

Handles processing of inbound email invites to notes@dealmotion.ai.

SPEC-043 Phase 2: Email-based AI Notetaker Invite

Events:
- dealmotion/ai-notetaker.email.received: Triggered when email arrives

Flow:
1. Parse email and extract ICS attachment
2. Match organizer email to DealMotion user
3. Schedule AI Notetaker via Recall.ai
4. Send confirmation email
"""

import logging
import base64
from datetime import datetime, timedelta
from inngest import TriggerEvent

from app.inngest.client import inngest_client
from app.database import get_supabase_service
from app.services.ics_parser import ics_parser
from app.services.recall_service import recall_service, RecallBotConfig

logger = logging.getLogger(__name__)


# =============================================================================
# Helper Functions
# =============================================================================

def match_user_by_email(organizer_email: str) -> dict | None:
    """
    Match organizer email to a DealMotion user.
    
    Returns user info dict or None if not found.
    """
    supabase = get_supabase_service()
    
    # Search in users table by email
    result = supabase.table("users").select(
        "id, email, name, organization_id"
    ).eq("email", organizer_email.lower()).limit(1).execute()
    
    if result.data and len(result.data) > 0:
        user = result.data[0]
        logger.info(f"Matched email {organizer_email} to user {user['id']}")
        return user
    
    # Try with auth.users (if users table is separate)
    # Supabase auth users might be in a different location
    logger.warning(f"No user found for email: {organizer_email}")
    return None


def find_prospect_by_attendees(organization_id: str, attendee_emails: list[str]) -> str | None:
    """
    Try to match meeting attendees to a prospect's contacts.
    
    Returns prospect_id or None.
    """
    if not attendee_emails:
        return None
    
    supabase = get_supabase_service()
    
    # Search contacts by email
    for email in attendee_emails:
        if not email or "@" not in email:
            continue
            
        result = supabase.table("prospect_contacts").select(
            "prospect_id"
        ).eq("organization_id", organization_id).eq("email", email.lower()).limit(1).execute()
        
        if result.data and len(result.data) > 0:
            prospect_id = result.data[0]["prospect_id"]
            logger.info(f"Matched attendee {email} to prospect {prospect_id}")
            return prospect_id
    
    return None


def create_scheduled_recording(
    organization_id: str,
    user_id: str,
    meeting_url: str,
    meeting_title: str,
    meeting_platform: str,
    scheduled_time: datetime,
    recall_bot_id: str | None = None,
    prospect_id: str | None = None,
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
        "status": "scheduled" if recall_bot_id else "error",
        "source": "email_invite",  # Mark as coming from email
    }
    
    result = supabase.table("scheduled_recordings").insert(record).execute()
    
    if not result.data:
        raise Exception("Failed to create scheduled recording")
    
    recording_id = result.data[0]["id"]
    logger.info(f"Created scheduled recording: {recording_id}")
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
    3. Schedule AI Notetaker via Recall.ai
    4. Save scheduled recording
    5. Send confirmation email
    """
    event_data = ctx.event.data
    raw_email_b64 = event_data["raw_email_b64"]
    sender = event_data.get("sender", "")
    subject = event_data.get("subject", "")
    
    logger.info(f"Processing email invite from: {sender}, subject: {subject}")
    
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
        
        return invite.to_dict()
    
    invite_data = await step.run("parse-email", parse_email)
    
    meeting_url = invite_data["meeting_url"]
    meeting_platform = invite_data["meeting_platform"]
    meeting_title = invite_data["title"] or subject or "Meeting"
    organizer_email = invite_data["organizer_email"]
    start_time_str = invite_data["start_time"]
    attendees = invite_data.get("attendees", [])
    
    # Parse start time
    start_time = datetime.fromisoformat(start_time_str) if start_time_str else datetime.utcnow() + timedelta(minutes=5)
    
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
    
    # Step 3: Try to match attendees to a prospect (optional)
    def find_prospect():
        return find_prospect_by_attendees(organization_id, attendees)
    
    prospect_id = await step.run("find-prospect", find_prospect)
    
    # Step 4: Schedule AI Notetaker via Recall.ai
    async def schedule_bot():
        if not recall_service.is_configured():
            raise Exception("Recall.ai is not configured")
        
        config = RecallBotConfig(
            meeting_url=meeting_url,
            join_at=start_time if start_time > datetime.utcnow() else None
        )
        
        result = await recall_service.create_bot(config)
        
        if not result.get("success"):
            raise Exception(f"Failed to create Recall.ai bot: {result.get('error')}")
        
        return result["bot_id"]
    
    recall_bot_id = await step.run("schedule-bot", schedule_bot)
    
    # Step 5: Save scheduled recording to database
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
        )
    
    recording_id = await step.run("save-recording", save_recording)
    
    # Step 6: Send confirmation email
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
    
    logger.info(f"Email invite processed successfully: recording={recording_id}, bot={recall_bot_id}")
    
    return {
        "recording_id": recording_id,
        "recall_bot_id": recall_bot_id,
        "user_id": user_id,
        "meeting_title": meeting_title,
        "meeting_time": start_time.isoformat(),
        "status": "scheduled"
    }

