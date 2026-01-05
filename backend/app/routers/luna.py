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

from fastapi import APIRouter, Depends, HTTPException, status as http_status, BackgroundTasks, Query
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
    user_input = request.get("userInput")  # Optional user input for customization
    language = request.get("language")  # Optional language override
    
    if not prospect_id or not contact_id or not channel:
        raise HTTPException(
            status_code=http_status.HTTP_400_BAD_REQUEST,
            detail="prospectId, contactId, and channel are required"
        )
    
    # Get context from database
    supabase = get_supabase_service()
    
    # Get organization_id for the user
    org_result = supabase.table("organization_members") \
        .select("organization_id") \
        .eq("user_id", user_id) \
        .limit(1) \
        .execute()
    
    if not org_result.data:
        raise HTTPException(
            status_code=http_status.HTTP_404_NOT_FOUND,
            detail="Organization not found"
        )
    
    org_id = org_result.data[0]["organization_id"]
    
    # Check credits BEFORE generating (v4: credit-based system)
    from app.services.credit_service import get_credit_service
    credit_service = get_credit_service()
    has_credits, credit_balance = await credit_service.check_credits(
        organization_id=org_id,
        action="outreach_generate"
    )
    if not has_credits:
        raise HTTPException(
            status_code=402,
            detail={
                "error": "insufficient_credits",
                "message": "Not enough credits for outreach generation",
                "required": credit_balance.get("required_credits", 1),
                "available": credit_balance.get("total_credits_available", 0),
                "action": "outreach_generate"
            }
        )
    
    # Get prospect
    prospect_result = supabase.table("prospects") \
        .select("*, research_briefs(*)") \
        .eq("id", prospect_id) \
        .eq("organization_id", org_id) \
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
    
    # Get user's preferred output language from settings (if not provided)
    if not language:
        language = "en"  # Default to English
        try:
            settings_response = supabase.table("user_settings")\
                .select("output_language")\
                .eq("user_id", user_id)\
                .maybe_single()\
                .execute()
            if settings_response.data and settings_response.data.get("output_language"):
                language = settings_response.data["output_language"]
                logger.info(f"Using user's output language for outreach: {language}")
        except Exception as e:
            logger.warning(f"Could not get user settings, using default language: {e}")
    
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
    
    # Get sales profile and company profile context (efficiently)
    profile_context = ""
    try:
        from app.services.rag_service import get_context_service
        ctx_service = get_context_service()
        # Get compact context (max 800 tokens for outreach - shorter than prep/research)
        profile_context = ctx_service.get_context_for_prompt(
            user_id, org_id, max_tokens=800
        )
        if profile_context:
            logger.info("Added sales/company profile context to outreach prompt")
    except Exception as e:
        logger.warning(f"Could not load profile context for outreach: {e}")
    
    # Generate content using LLM
    try:
        import os
        from anthropic import Anthropic
        
        api_key = os.getenv("ANTHROPIC_API_KEY")
        if not api_key:
            raise HTTPException(
                status_code=http_status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="ANTHROPIC_API_KEY not configured"
            )
        
        client = Anthropic(api_key=api_key)
        
        # Get language instruction
        from app.i18n.utils import get_language_instruction
        language_instruction = get_language_instruction(language)
        
        # Build context
        company_name = prospect.get("company_name", "the company")
        contact_name = contact.get("name", "the contact")
        contact_role = contact.get("role", "")
        
        # Extract key research insights (compact)
        research_summary = ""
        if research:
            # Use executive summary, but limit to most relevant parts
            exec_summary = research.get("executive_summary", "")
            if exec_summary:
                # For short messages (LinkedIn/WhatsApp), use less context
                if channel in ["linkedin_connect", "linkedin_message", "whatsapp"]:
                    research_summary = exec_summary[:300]  # Very compact for short messages
                else:
                    research_summary = exec_summary[:800]  # More context for emails
        
        # Build user input section if provided
        user_input_section = ""
        if user_input and user_input.strip():
            user_input_section = f"\n\nAdditional instructions from user:\n{user_input.strip()}\n\nIncorporate these instructions into the message."
        
        # Build profile context section (only if available and for longer messages)
        profile_section = ""
        if profile_context and channel == "email":  # Only for emails to save tokens
            profile_section = f"\n\nAbout you and your company:\n{profile_context[:400]}\n\nUse this to personalize the message and show relevant expertise."
        
        # Channel-specific prompts
        channel_prompts = {
            "linkedin_connect": f"""{language_instruction}

Write a short LinkedIn connection request note (max 300 characters) to {contact_name}, {contact_role} at {company_name}.
Make it personal and professional. Don't be salesy. Reference something specific about the company or their role.

Company research: {research_summary if research_summary else 'Not available'}{user_input_section}

Return ONLY the connection note text.""",
            
            "linkedin_message": f"""{language_instruction}

Write a LinkedIn message to {contact_name}, {contact_role} at {company_name}.
Keep it concise (max 500 characters). Be conversational and value-focused. Include a soft call-to-action.

Company research: {research_summary if research_summary else 'Not available'}{user_input_section}

Return ONLY the message text.""",
            
            "email": f"""{language_instruction}

Write a cold outreach email to {contact_name}, {contact_role} at {company_name}.

Company research: {research_summary if research_summary else 'Not available'}{profile_section}{user_input_section}

Include:
- A compelling subject line
- Personalized opening that references specific research insights
- Value proposition aligned with their needs
- Clear but soft call-to-action

Return in format:
SUBJECT: [subject line]
BODY: [email body]""",
            
            "whatsapp": f"""{language_instruction}

Write a short WhatsApp message to {contact_name}, {contact_role} at {company_name}.
Keep it very brief (max 200 characters). Be friendly but professional.

Company research: {research_summary if research_summary else 'Not available'}{user_input_section}

Return ONLY the message text."""
        }
        
        prompt = channel_prompts.get(channel, channel_prompts["email"])
        
        response = client.messages.create(
            model="claude-sonnet-4-20250514",
            max_tokens=500,
            messages=[{"role": "user", "content": prompt}]
        )
        
        generated_text = response.content[0].text.strip()
        
        # Parse email format
        result = {}
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
            
            result = {
                "subject": subject_line,
                "body": "\n".join(body_lines).strip(),
                "channel": channel
            }
        else:
            result = {
                "body": generated_text,
                "channel": channel
            }
        
        # Consume credits after successful generation
        try:
            await credit_service.consume_credits(
                organization_id=org_id,
                action="outreach_generate",
                user_id=user_id,
                metadata={
                    "prospect_id": prospect_id,
                    "contact_id": contact_id,
                    "channel": channel
                }
            )
            logger.info(f"Consumed outreach generation credits for {contact_id}")
        except Exception as credit_err:
            logger.warning(f"Failed to consume outreach generation credits: {credit_err}")
            # Don't fail the request if credit logging fails - generation already succeeded
        
        return result
        
    except HTTPException:
        # Re-raise HTTP exceptions (like 402 for insufficient credits)
        raise
    except Exception as e:
        logger.error(f"Error generating outreach: {e}")
        raise HTTPException(
            status_code=http_status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to generate outreach content"
        )


@router.get("/outreach")
async def get_outreach(
    contact_id: Optional[str] = Query(None, description="Filter by contact ID"),
    status: Optional[str] = Query(None, description="Filter by status (draft, sent, skipped)"),
    current_user: dict = Depends(get_current_user)
):
    """
    Get outreach messages (drafts, sent, etc.)
    
    Args:
        contact_id: Filter by contact ID
        status: Filter by status (draft, sent, skipped)
    """
    user_id = current_user["sub"]
    supabase = get_supabase_service()
    
    query = supabase.table("outreach_messages").select("*").eq("user_id", user_id)
    
    if contact_id:
        query = query.eq("contact_id", contact_id)
    if status:
        query = query.eq("status", status)
    
    query = query.order("created_at", desc=True).limit(10)
    
    result = query.execute()
    
    if not result.data:
        return []
    
    return result.data


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
    
    # Check if draft already exists for this contact + channel + user
    # If so, update it instead of creating new one
    existing_draft = None
    if status == "draft" and contact_id:
        existing_result = supabase.table("outreach_messages") \
            .select("id") \
            .eq("user_id", user_id) \
            .eq("contact_id", contact_id) \
            .eq("channel", channel) \
            .eq("status", "draft") \
            .limit(1) \
            .execute()
        
        if existing_result.data:
            existing_draft = existing_result.data[0]
    
    # Prepare outreach data
    outreach_data = {
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
    
    # Update existing draft or create new one
    if existing_draft:
        # Update existing draft
        result = supabase.table("outreach_messages") \
            .update(outreach_data) \
            .eq("id", existing_draft["id"]) \
            .eq("user_id", user_id) \
            .execute()
        
        if not result.data:
            raise HTTPException(
                status_code=http_status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Failed to update outreach draft"
            )
        
        return {"id": existing_draft["id"], "status": status}
    else:
        # Create new outreach record
        outreach_data["user_id"] = user_id
        outreach_data["organization_id"] = org_id
        
        result = supabase.table("outreach_messages").insert(outreach_data).execute()
        
        if not result.data:
            raise HTTPException(
                status_code=http_status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Failed to create outreach"
            )
        
        return {"id": result.data[0]["id"], "status": status}


@router.patch("/outreach/{outreach_id}")
async def update_outreach(
    outreach_id: str,
    request: dict,
    current_user: dict = Depends(get_current_user)
):
    """Update an outreach message (e.g., update draft)."""
    user_id = current_user["sub"]
    supabase = get_supabase_service()
    
    # Get update fields
    update_data = {}
    if "subject" in request:
        update_data["subject"] = request.get("subject")
    if "body" in request:
        update_data["body"] = request.get("body")
    if "channel" in request:
        update_data["channel"] = request.get("channel")
    
    if not update_data:
        raise HTTPException(
            status_code=http_status.HTTP_400_BAD_REQUEST,
            detail="No fields to update"
        )
    
    result = supabase.table("outreach_messages") \
        .update(update_data) \
        .eq("id", outreach_id) \
        .eq("user_id", user_id) \
        .execute()
    
    if not result.data:
        raise HTTPException(
            status_code=http_status.HTTP_404_NOT_FOUND,
            detail="Outreach not found"
        )
    
    return {"id": outreach_id, **update_data}


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
