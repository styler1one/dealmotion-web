"""
Luna Unified AI Assistant - API Router
SPEC-046-Luna-Unified-AI-Assistant

API endpoints for Luna:
- Message management (list, accept, dismiss, snooze)
- Settings
- Stats
- Greeting
- Tip of day
- Feature flags
"""

from fastapi import APIRouter, Depends, HTTPException, status as http_status, BackgroundTasks
from typing import Optional
from datetime import datetime
import logging

from app.deps import get_current_user
from app.database import get_supabase_service
from app.services.luna_service import LunaService
from app.models.luna import (
    MessagesResponse,
    MessageActionRequest,
    MessageActionResponse,
    MessageShowRequest,
    LunaMessage,
    LunaSettings,
    LunaSettingsUpdate,
    LunaGreeting,
    LunaStats,
    TipOfDay,
    UpcomingMeeting,
    FeatureFlagsResponse,
    SnoozeOption,
    Surface,
    MessageStatus,
)

router = APIRouter(prefix="/api/v1/luna", tags=["luna"])
logger = logging.getLogger(__name__)


def get_luna_service():
    """Get Luna service instance."""
    return LunaService()


# =============================================================================
# FEATURE FLAGS
# =============================================================================

@router.get("/flags", response_model=FeatureFlagsResponse)
async def get_feature_flags(
    current_user: dict = Depends(get_current_user)
):
    """Get Luna feature flags for the current user."""
    user_id = current_user["sub"]
    service = get_luna_service()
    return await service.get_feature_flags(user_id)


# =============================================================================
# MESSAGES
# =============================================================================

@router.get("/messages", response_model=MessagesResponse)
async def get_messages(
    message_status: Optional[str] = None,
    limit: int = 20,
    current_user: dict = Depends(get_current_user)
):
    """
    Get Luna messages for the current user.
    
    Args:
        message_status: Filter by status (pending, executing, completed, etc.)
        limit: Maximum number of messages to return
    """
    user_id = current_user["sub"]
    service = get_luna_service()
    
    try:
        return await service.get_messages(user_id, message_status, limit)
    except Exception as e:
        logger.error(f"Error getting messages: {e}")
        raise HTTPException(
            status_code=http_status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to get messages"
        )


@router.get("/messages/{message_id}", response_model=LunaMessage)
async def get_message(
    message_id: str,
    current_user: dict = Depends(get_current_user)
):
    """Get a single Luna message by ID."""
    user_id = current_user["sub"]
    service = get_luna_service()
    
    message = await service.get_message(message_id, user_id)
    if not message:
        raise HTTPException(
            status_code=http_status.HTTP_404_NOT_FOUND,
            detail="Message not found"
        )
    
    return message


@router.post("/messages/{message_id}/shown")
async def mark_message_shown(
    message_id: str,
    request: MessageShowRequest,
    current_user: dict = Depends(get_current_user)
):
    """
    Mark a message as shown (sets viewed_at once).
    
    This should be called when a message is first rendered to the user.
    """
    user_id = current_user["sub"]
    service = get_luna_service()
    
    success = await service.mark_shown(message_id, user_id, request.surface)
    
    return {"success": success}


@router.post("/messages/{message_id}/accept", response_model=MessageActionResponse)
async def accept_message(
    message_id: str,
    request: MessageActionRequest,
    background_tasks: BackgroundTasks,
    current_user: dict = Depends(get_current_user)
):
    """
    Accept a Luna message (user clicked the CTA).
    
    For execute actions, this will trigger an async job.
    """
    user_id = current_user["sub"]
    service = get_luna_service()
    
    # Get the message first to check action type
    message = await service.get_message(message_id, user_id)
    if not message:
        raise HTTPException(
            status_code=http_status.HTTP_404_NOT_FOUND,
            detail="Message not found"
        )
    
    success, error = await service.accept_message(
        message_id, user_id, request.surface
    )
    
    if not success:
        raise HTTPException(
            status_code=http_status.HTTP_400_BAD_REQUEST,
            detail=error
        )
    
    # If execute action, trigger the job
    if message.action_type == "execute":
        from app.inngest.client import inngest_client
        
        # Get organization_id
        supabase = get_supabase_service()
        org_result = supabase.table("organization_members") \
            .select("organization_id") \
            .eq("user_id", user_id) \
            .limit(1) \
            .execute()
        
        org_id = org_result.data[0]["organization_id"] if org_result.data else None
        
        # Schedule execution
        background_tasks.add_task(
            inngest_client.send,
            {
                "name": "dealmotion/luna.execute.action",
                "data": {
                    "message_id": message_id,
                    "user_id": user_id,
                    "organization_id": org_id,
                    "message_type": message.message_type,
                    "action_data": message.action_data
                }
            }
        )
    
    return MessageActionResponse(
        success=True,
        message_id=message_id,
        new_status=MessageStatus.EXECUTING if message.action_type == "execute" else MessageStatus.COMPLETED
    )


@router.post("/messages/{message_id}/dismiss", response_model=MessageActionResponse)
async def dismiss_message(
    message_id: str,
    request: MessageActionRequest,
    current_user: dict = Depends(get_current_user)
):
    """Dismiss a Luna message (user clicked X)."""
    user_id = current_user["sub"]
    service = get_luna_service()
    
    success, error = await service.dismiss_message(
        message_id, user_id, request.surface
    )
    
    if not success:
        raise HTTPException(
            status_code=http_status.HTTP_400_BAD_REQUEST,
            detail=error
        )
    
    return MessageActionResponse(
        success=True,
        message_id=message_id,
        new_status=MessageStatus.DISMISSED
    )


@router.post("/messages/{message_id}/snooze", response_model=MessageActionResponse)
async def snooze_message(
    message_id: str,
    request: MessageActionRequest,
    current_user: dict = Depends(get_current_user)
):
    """
    Snooze a Luna message (user clicked Later).
    
    Provide snooze_option to use a preset, or snooze_until for custom datetime.
    """
    user_id = current_user["sub"]
    service = get_luna_service()
    
    if not request.snooze_option and not request.snooze_until:
        raise HTTPException(
            status_code=http_status.HTTP_400_BAD_REQUEST,
            detail="Either snooze_option or snooze_until is required"
        )
    
    success, error = await service.snooze_message(
        message_id=message_id,
        user_id=user_id,
        snooze_option=request.snooze_option or SnoozeOption.LATER_TODAY,
        custom_datetime=request.snooze_until,
        surface=request.surface
    )
    
    if not success:
        raise HTTPException(
            status_code=http_status.HTTP_400_BAD_REQUEST,
            detail=error
        )
    
    return MessageActionResponse(
        success=True,
        message_id=message_id,
        new_status=MessageStatus.SNOOZED
    )


# =============================================================================
# GREETING
# =============================================================================

@router.get("/greeting", response_model=LunaGreeting)
async def get_greeting(
    current_user: dict = Depends(get_current_user)
):
    """Get contextual greeting for Luna Home."""
    user_id = current_user["sub"]
    service = get_luna_service()
    
    return await service.get_greeting(user_id)


# =============================================================================
# STATS
# =============================================================================

@router.get("/stats", response_model=LunaStats)
async def get_stats(
    current_user: dict = Depends(get_current_user)
):
    """Get Luna stats for the current user."""
    user_id = current_user["sub"]
    service = get_luna_service()
    
    # Get organization_id
    supabase = get_supabase_service()
    org_result = supabase.table("organization_members") \
        .select("organization_id") \
        .eq("user_id", user_id) \
        .limit(1) \
        .execute()
    
    org_id = org_result.data[0]["organization_id"] if org_result.data else None
    
    return await service.get_stats(user_id, org_id)


# =============================================================================
# TIP OF DAY
# =============================================================================

@router.get("/tip", response_model=TipOfDay)
async def get_tip_of_day(
    current_user: dict = Depends(get_current_user)
):
    """
    Get tip of the day - generic only, no CTA.
    
    Frontend should cache this for 24 hours.
    """
    user_id = current_user["sub"]
    service = get_luna_service()
    
    return await service.get_tip_of_day(user_id)


# =============================================================================
# SETTINGS
# =============================================================================

@router.get("/settings", response_model=LunaSettings)
async def get_settings(
    current_user: dict = Depends(get_current_user)
):
    """Get Luna settings for the current user."""
    user_id = current_user["sub"]
    service = get_luna_service()
    
    # Get organization_id
    supabase = get_supabase_service()
    org_result = supabase.table("organization_members") \
        .select("organization_id") \
        .eq("user_id", user_id) \
        .limit(1) \
        .execute()
    
    org_id = org_result.data[0]["organization_id"] if org_result.data else None
    
    return await service.get_settings(user_id, org_id)


@router.patch("/settings", response_model=LunaSettings)
async def update_settings(
    updates: LunaSettingsUpdate,
    current_user: dict = Depends(get_current_user)
):
    """Update Luna settings for the current user."""
    user_id = current_user["sub"]
    service = get_luna_service()
    
    try:
        return await service.update_settings(user_id, updates)
    except Exception as e:
        logger.error(f"Error updating settings: {e}")
        raise HTTPException(
            status_code=http_status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to update settings"
        )


# =============================================================================
# UPCOMING MEETINGS
# =============================================================================

@router.get("/meetings/upcoming", response_model=list[UpcomingMeeting])
async def get_upcoming_meetings(
    limit: int = 5,
    current_user: dict = Depends(get_current_user)
):
    """Get upcoming meetings with prep status."""
    user_id = current_user["sub"]
    service = get_luna_service()
    
    # Get organization_id
    supabase = get_supabase_service()
    org_result = supabase.table("organization_members") \
        .select("organization_id") \
        .eq("user_id", user_id) \
        .limit(1) \
        .execute()
    
    org_id = org_result.data[0]["organization_id"] if org_result.data else None
    
    return await service.get_upcoming_meetings(user_id, org_id, limit)


# =============================================================================
# OUTREACH
# =============================================================================

@router.post("/outreach/generate")
async def generate_outreach(
    request: dict,
    current_user: dict = Depends(get_current_user)
):
    """
    Generate outreach message content using AI.
    
    Args:
        prospect_id: The prospect ID
        contact_id: The contact ID
        research_id: Optional research brief ID
        channel: The outreach channel (linkedin_connect, linkedin_message, email, whatsapp)
    """
    user_id = current_user["sub"]
    
    prospect_id = request.get("prospectId")
    contact_id = request.get("contactId")
    research_id = request.get("researchId")
    channel = request.get("channel")
    
    if not prospect_id or not contact_id or not channel:
        raise HTTPException(
            status_code=http_status.HTTP_400_BAD_REQUEST,
            detail="prospectId, contactId, and channel are required"
        )
    
    # Get context from database
    supabase = get_supabase_service()
    
    # Get prospect
    prospect_result = supabase.table("prospects") \
        .select("*, research_briefs(*)") \
        .eq("id", prospect_id) \
        .eq("user_id", user_id) \
        .limit(1) \
        .execute()
    
    if not prospect_result.data:
        raise HTTPException(
            status_code=http_status.HTTP_404_NOT_FOUND,
            detail="Prospect not found"
        )
    
    prospect = prospect_result.data[0]
    
    # Get contact
    contact_result = supabase.table("prospect_contacts") \
        .select("*") \
        .eq("id", contact_id) \
        .limit(1) \
        .execute()
    
    if not contact_result.data:
        raise HTTPException(
            status_code=http_status.HTTP_404_NOT_FOUND,
            detail="Contact not found"
        )
    
    contact = contact_result.data[0]
    
    # Get research if available
    research = None
    if research_id:
        research_result = supabase.table("research_briefs") \
            .select("*") \
            .eq("id", research_id) \
            .eq("user_id", user_id) \
            .limit(1) \
            .execute()
        if research_result.data:
            research = research_result.data[0]
    elif prospect.get("research_briefs"):
        research = prospect["research_briefs"][0] if prospect["research_briefs"] else None
    
    # Generate content using LLM
    try:
        from app.services.claude_service import get_claude_client
        
        client = get_claude_client()
        
        # Build context
        company_name = prospect.get("company_name", "the company")
        contact_name = contact.get("name", "the contact")
        contact_role = contact.get("role", "")
        research_summary = research.get("executive_summary", "") if research else ""
        
        # Channel-specific prompts
        channel_prompts = {
            "linkedin_connect": f"""Write a short LinkedIn connection request note (max 300 characters) to {contact_name}, {contact_role} at {company_name}.
Make it personal and professional. Don't be salesy. Reference something specific about the company or their role.

Company research: {research_summary[:500] if research_summary else 'Not available'}

Return ONLY the connection note text.""",
            
            "linkedin_message": f"""Write a LinkedIn message to {contact_name}, {contact_role} at {company_name}.
Keep it concise (max 500 characters). Be conversational and value-focused. Include a soft call-to-action.

Company research: {research_summary[:500] if research_summary else 'Not available'}

Return ONLY the message text.""",
            
            "email": f"""Write a cold outreach email to {contact_name}, {contact_role} at {company_name}.

Company research: {research_summary[:1000] if research_summary else 'Not available'}

Include:
- A compelling subject line
- Personalized opening
- Value proposition
- Clear but soft call-to-action

Return in format:
SUBJECT: [subject line]
BODY: [email body]""",
            
            "whatsapp": f"""Write a short WhatsApp message to {contact_name}, {contact_role} at {company_name}.
Keep it very brief (max 200 characters). Be friendly but professional.

Company research: {research_summary[:300] if research_summary else 'Not available'}

Return ONLY the message text."""
        }
        
        prompt = channel_prompts.get(channel, channel_prompts["email"])
        
        response = client.messages.create(
            model="claude-3-5-sonnet-20241022",
            max_tokens=500,
            messages=[{"role": "user", "content": prompt}]
        )
        
        generated_text = response.content[0].text.strip()
        
        # Parse email format
        if channel == "email" and "SUBJECT:" in generated_text:
            lines = generated_text.split("\n")
            subject_line = ""
            body_lines = []
            in_body = False
            
            for line in lines:
                if line.startswith("SUBJECT:"):
                    subject_line = line.replace("SUBJECT:", "").strip()
                elif line.startswith("BODY:"):
                    in_body = True
                    body_content = line.replace("BODY:", "").strip()
                    if body_content:
                        body_lines.append(body_content)
                elif in_body:
                    body_lines.append(line)
            
            return {
                "subject": subject_line,
                "body": "\n".join(body_lines).strip(),
                "channel": channel
            }
        
        return {
            "body": generated_text,
            "channel": channel
        }
        
    except Exception as e:
        logger.error(f"Error generating outreach: {e}")
        raise HTTPException(
            status_code=http_status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to generate outreach content"
        )


@router.post("/outreach")
async def create_outreach(
    request: dict,
    current_user: dict = Depends(get_current_user)
):
    """
    Create or save an outreach message.
    
    Args:
        prospect_id: The prospect ID
        contact_id: The contact ID (optional)
        research_id: The research brief ID (optional)
        channel: The outreach channel
        subject: Email subject (optional)
        body: Message body
        status: 'draft' | 'sent' | 'skipped'
    """
    user_id = current_user["sub"]
    
    prospect_id = request.get("prospectId")
    contact_id = request.get("contactId")
    research_id = request.get("researchId")
    channel = request.get("channel")
    subject = request.get("subject")
    body = request.get("body", "")
    status = request.get("status", "draft")
    
    if not prospect_id or not channel:
        raise HTTPException(
            status_code=http_status.HTTP_400_BAD_REQUEST,
            detail="prospectId and channel are required"
        )
    
    # Get organization_id
    supabase = get_supabase_service()
    org_result = supabase.table("organization_members") \
        .select("organization_id") \
        .eq("user_id", user_id) \
        .limit(1) \
        .execute()
    
    org_id = org_result.data[0]["organization_id"] if org_result.data else None
    
    if not org_id:
        raise HTTPException(
            status_code=http_status.HTTP_400_BAD_REQUEST,
            detail="User has no organization"
        )
    
    # Create outreach record
    outreach_data = {
        "user_id": user_id,
        "organization_id": org_id,
        "prospect_id": prospect_id,
        "contact_id": contact_id,
        "research_id": research_id,
        "channel": channel,
        "subject": subject,
        "body": body,
        "status": status,
    }
    
    if status == "sent":
        from datetime import datetime
        outreach_data["sent_at"] = datetime.utcnow().isoformat()
    
    result = supabase.table("outreach_messages").insert(outreach_data).execute()
    
    if not result.data:
        raise HTTPException(
            status_code=http_status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to create outreach"
        )
    
    return {"id": result.data[0]["id"], "status": status}


@router.patch("/outreach/{outreach_id}/sent")
async def mark_outreach_sent(
    outreach_id: str,
    background_tasks: BackgroundTasks,
    current_user: dict = Depends(get_current_user)
):
    """Mark an outreach as sent."""
    user_id = current_user["sub"]
    supabase = get_supabase_service()
    
    # Update the outreach
    from datetime import datetime
    
    result = supabase.table("outreach_messages") \
        .update({
            "status": "sent",
            "sent_at": datetime.utcnow().isoformat()
        }) \
        .eq("id", outreach_id) \
        .eq("user_id", user_id) \
        .execute()
    
    if not result.data:
        raise HTTPException(
            status_code=http_status.HTTP_404_NOT_FOUND,
            detail="Outreach not found"
        )
    
    # Trigger event for first_touch_sent message creation
    outreach = result.data[0]
    
    from app.inngest.client import inngest_client
    
    background_tasks.add_task(
        inngest_client.send,
        {
            "name": "dealmotion/outreach.sent",
            "data": {
                "outreach_id": outreach_id,
                "user_id": user_id,
                "prospect_id": outreach.get("prospect_id"),
                "contact_id": outreach.get("contact_id"),
                "channel": outreach.get("channel")
            }
        }
    )
    
    return {"success": True}


# =============================================================================
# MANUAL DETECTION TRIGGER (Admin/Debug)
# =============================================================================

@router.post("/detect")
async def trigger_detection(
    background_tasks: BackgroundTasks,
    current_user: dict = Depends(get_current_user)
):
    """
    Manually trigger Luna detection for the current user.
    Useful for testing/debugging.
    """
    user_id = current_user["sub"]
    
    # Get organization_id
    supabase = get_supabase_service()
    org_result = supabase.table("organization_members") \
        .select("organization_id") \
        .eq("user_id", user_id) \
        .limit(1) \
        .execute()
    
    org_id = org_result.data[0]["organization_id"] if org_result.data else None
    
    # Trigger detection
    from app.inngest.client import inngest_client
    
    background_tasks.add_task(
        inngest_client.send,
        {
            "name": "dealmotion/luna.detect.user",
            "data": {
                "user_id": user_id,
                "organization_id": org_id,
                "trigger_source": "manual"
            }
        }
    )
    
    return {"success": True, "message": "Detection triggered"}
