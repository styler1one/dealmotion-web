"""
Luna Execution Inngest Function.
SPEC-046-Luna-Unified-AI-Assistant

Executes Luna message actions (for action_type="execute"):
- Start research
- Create prep
- etc.
"""

import logging
from datetime import datetime
import inngest
from inngest import TriggerEvent

from app.inngest.client import inngest_client
from app.database import get_supabase_service

logger = logging.getLogger(__name__)


@inngest_client.create_function(
    fn_id="luna-execute-action",
    trigger=TriggerEvent(event="dealmotion/luna.execute.action"),
    retries=2,
)
async def luna_execute_action_fn(ctx, step):
    """
    Execute a Luna message action.
    
    Triggered when user accepts a message with action_type="execute".
    """
    from app.services.luna_service import LunaService
    
    event_data = ctx.event.data
    message_id = event_data.get("message_id")
    user_id = event_data.get("user_id")
    organization_id = event_data.get("organization_id")
    message_type = event_data.get("message_type")
    action_data = event_data.get("action_data", {})
    
    if not message_id or not user_id:
        logger.error("Missing required data for Luna action execution")
        return {"success": False, "error": "Missing required data"}
    
    logger.info(f"Executing Luna action: {message_type} for message {message_id[:8]}")
    
    service = LunaService()
    supabase = get_supabase_service()
    
    try:
        # Route to appropriate handler based on message_type
        if message_type == "start_research":
            result = await _execute_start_research(step, user_id, organization_id, action_data, supabase)
        elif message_type == "create_prep":
            result = await _execute_create_prep(step, user_id, organization_id, action_data, supabase)
        elif message_type in ["send_followup_email", "create_action_items"]:
            result = await _execute_followup_action(step, user_id, message_type, action_data, supabase)
        else:
            # Generic completion for navigate/inline types
            result = {"success": True, "type": "completed"}
        
        # Mark message as completed
        if result.get("success"):
            await service.mark_completed(message_id, user_id, result)
            logger.info(f"Luna action completed: {message_type}")
        else:
            await service.mark_failed(
                message_id, user_id,
                error_code=result.get("error_code", "EXECUTION_ERROR"),
                error_message=result.get("error", "Unknown error"),
                retryable=result.get("retryable", False)
            )
            logger.error(f"Luna action failed: {message_type} - {result.get('error')}")
        
        return result
        
    except Exception as e:
        logger.error(f"Error executing Luna action: {e}")
        await service.mark_failed(
            message_id, user_id,
            error_code="EXCEPTION",
            error_message=str(e),
            retryable=True
        )
        return {"success": False, "error": str(e)}


async def _execute_start_research(step, user_id, organization_id, action_data, supabase):
    """Execute start_research action."""
    prospect_id = action_data.get("prospect_id")
    company_name = action_data.get("company_name")
    
    if not prospect_id:
        return {"success": False, "error": "Missing prospect_id", "error_code": "MISSING_DATA"}
    
    async def start_research():
        # Check if research already exists
        existing = supabase.table("research_briefs") \
            .select("id") \
            .eq("prospect_id", prospect_id) \
            .limit(1) \
            .execute()
        
        if existing.data:
            return {"already_exists": True, "research_id": existing.data[0]["id"]}
        
        # Create research request
        result = supabase.table("research_briefs").insert({
            "user_id": user_id,
            "organization_id": organization_id,
            "prospect_id": prospect_id,
            "company_name": company_name,
            "status": "pending",
            "created_at": datetime.utcnow().isoformat()
        }).execute()
        
        if result.data:
            return {"created": True, "research_id": result.data[0]["id"]}
        return {"created": False}
    
    research_result = await step.run("start-research", start_research)
    
    if research_result.get("created") or research_result.get("already_exists"):
        research_id = research_result.get("research_id")
        
        # Trigger research job
        from app.inngest.client import inngest_client
        await inngest_client.send({
            "name": "dealmotion/research.start",
            "data": {
                "research_id": research_id,
                "user_id": user_id,
                "organization_id": organization_id
            }
        })
        
        return {
            "success": True,
            "type": "research",
            "id": research_id,
            "already_exists": research_result.get("already_exists", False)
        }
    
    return {"success": False, "error": "Failed to create research", "error_code": "CREATE_FAILED"}


async def _execute_create_prep(step, user_id, organization_id, action_data, supabase):
    """Execute create_prep action."""
    meeting_id = action_data.get("meeting_id")
    prospect_id = action_data.get("prospect_id")
    
    if not meeting_id:
        return {"success": False, "error": "Missing meeting_id", "error_code": "MISSING_DATA"}
    
    async def create_prep():
        # Check if prep already exists
        existing = supabase.table("meeting_preps") \
            .select("id") \
            .eq("meeting_id", meeting_id) \
            .limit(1) \
            .execute()
        
        if existing.data:
            return {"already_exists": True, "prep_id": existing.data[0]["id"]}
        
        # Get meeting details
        meeting = supabase.table("calendar_meetings") \
            .select("title, prospect_id, start_time") \
            .eq("id", meeting_id) \
            .single() \
            .execute()
        
        meeting_data = meeting.data or {}
        prospect_id_from_meeting = meeting_data.get("prospect_id") or prospect_id
        
        # Get company name
        company_name = "Meeting"
        if prospect_id_from_meeting:
            prospect = supabase.table("prospects") \
                .select("company_name") \
                .eq("id", prospect_id_from_meeting) \
                .single() \
                .execute()
            if prospect.data:
                company_name = prospect.data.get("company_name", "Meeting")
        
        # Create prep
        result = supabase.table("meeting_preps").insert({
            "user_id": user_id,
            "organization_id": organization_id,
            "meeting_id": meeting_id,
            "prospect_id": prospect_id_from_meeting,
            "prospect_company_name": company_name,
            "meeting_type": "general",
            "status": "pending",
            "created_at": datetime.utcnow().isoformat()
        }).execute()
        
        if result.data:
            return {"created": True, "prep_id": result.data[0]["id"]}
        return {"created": False}
    
    prep_result = await step.run("create-prep", create_prep)
    
    if prep_result.get("created") or prep_result.get("already_exists"):
        prep_id = prep_result.get("prep_id")
        
        # Trigger prep generation job
        from app.inngest.client import inngest_client
        await inngest_client.send({
            "name": "dealmotion/preparation.start",
            "data": {
                "prep_id": prep_id,
                "user_id": user_id,
                "organization_id": organization_id
            }
        })
        
        return {
            "success": True,
            "type": "prep",
            "id": prep_id,
            "already_exists": prep_result.get("already_exists", False)
        }
    
    return {"success": False, "error": "Failed to create prep", "error_code": "CREATE_FAILED"}


async def _execute_followup_action(step, user_id, message_type, action_data, supabase):
    """Execute followup-related actions."""
    followup_id = action_data.get("followup_id")
    
    if not followup_id:
        return {"success": False, "error": "Missing followup_id", "error_code": "MISSING_DATA"}
    
    async def trigger_action():
        # Trigger the appropriate followup action generation
        from app.inngest.client import inngest_client
        
        action_type_map = {
            "send_followup_email": "email_draft",
            "create_action_items": "action_items"
        }
        
        action_type = action_type_map.get(message_type)
        if not action_type:
            return {"success": False}
        
        await inngest_client.send({
            "name": "dealmotion/followup.generate_action",
            "data": {
                "followup_id": followup_id,
                "action_type": action_type,
                "user_id": user_id
            }
        })
        
        return {"triggered": True, "action_type": action_type}
    
    result = await step.run("trigger-followup-action", trigger_action)
    
    if result.get("triggered"):
        return {
            "success": True,
            "type": result["action_type"],
            "followup_id": followup_id
        }
    
    return {"success": False, "error": "Failed to trigger action", "error_code": "TRIGGER_FAILED"}


# =============================================================================
# FIRST TOUCH SENT HANDLER
# =============================================================================

@inngest_client.create_function(
    fn_id="luna-handle-outreach-sent",
    trigger=TriggerEvent(event="dealmotion/outreach.sent"),
    retries=1,
)
async def luna_handle_outreach_sent_fn(ctx, step):
    """
    Create first_touch_sent progress message when outreach is marked as sent.
    """
    from app.services.luna_detection import LunaDetectionEngine
    from app.services.luna_service import LunaService
    from app.models.luna import (
        MessageType, ActionType, LunaMessageCreate, MESSAGE_PRIORITIES
    )
    
    event_data = ctx.event.data
    outreach_id = event_data.get("outreach_id")
    user_id = event_data.get("user_id")
    organization_id = event_data.get("organization_id")
    
    if not outreach_id or not user_id:
        logger.warning("Missing data for outreach sent handler")
        return {"created": False}
    
    supabase = get_supabase_service()
    
    async def check_and_create():
        engine = LunaDetectionEngine()
        
        # Check if we should create the message
        should_create = await engine.should_create_first_touch_sent(user_id, outreach_id)
        if not should_create:
            return {"should_create": False}
        
        # Get outreach details
        outreach = supabase.table("outreach_messages") \
            .select("prospect_id, contact_id, channel, prospects(company_name), prospect_contacts(name)") \
            .eq("id", outreach_id) \
            .single() \
            .execute()
        
        if not outreach.data:
            return {"should_create": False}
        
        data = outreach.data
        prospect_id = data["prospect_id"]
        contact_id = data.get("contact_id")
        channel = data.get("channel", "message")
        company = data.get("prospects", {}).get("company_name", "Prospect") if data.get("prospects") else "Prospect"
        contact_name = data.get("prospect_contacts", {}).get("name", "Contact") if data.get("prospect_contacts") else "Contact"
        
        channel_label = {
            "linkedin_connect": "LinkedIn connect",
            "linkedin_message": "LinkedIn bericht",
            "email": "email",
            "whatsapp": "WhatsApp"
        }.get(channel, channel)
        
        # Create message
        service = LunaService()
        msg = LunaMessageCreate(
            user_id=user_id,
            organization_id=organization_id,
            dedupe_key=f"first_touch_sent:{prospect_id}:{outreach_id}",
            message_type=MessageType.FIRST_TOUCH_SENT.value,
            title=f"Bericht verstuurd naar {contact_name}",
            description=f"Je {channel_label} is onderweg",
            luna_message=f"Goed bezig! Je hebt contact gelegd met {contact_name} bij {company}.",
            action_type=ActionType.NAVIGATE.value,
            action_route=f"/dashboard/prospects/{prospect_id}",
            action_data={"outreach_id": outreach_id, "prospect_id": prospect_id},
            priority=MESSAGE_PRIORITIES.get(MessageType.FIRST_TOUCH_SENT, 40),
            prospect_id=prospect_id,
            contact_id=contact_id,
            outreach_id=outreach_id
        )
        
        result = await service.create_message(msg)
        return {"created": result is not None}
    
    result = await step.run("check-and-create", check_and_create)
    
    if result.get("created"):
        logger.info(f"Created first_touch_sent message for outreach {outreach_id[:8]}")
    
    return result
