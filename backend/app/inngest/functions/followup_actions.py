"""
Follow-up Actions Inngest Function.

Handles on-demand generation of follow-up action documents with observability.

Events:
- dealmotion/followup.action.requested: Triggers action generation
- dealmotion/followup.action.completed: Emitted when generation is complete

Action Types:
- customer_report: Professional report to share with customer
- share_email: Ready-to-send email
- commercial_analysis: Buying signals, risks, deal assessment
- sales_coaching: Feedback on sales performance
- action_items: Structured tasks with owners/deadlines
- internal_report: Short summary for CRM/team
"""

import logging
from typing import Optional, Dict, Any
import inngest
from inngest import NonRetriableError, TriggerEvent

from app.inngest.client import inngest_client
from app.database import get_supabase_service
from app.models.followup_actions import ActionType

logger = logging.getLogger(__name__)

# Database client
supabase = get_supabase_service()


@inngest_client.create_function(
    fn_id="followup-action-generate",
    trigger=TriggerEvent(event="dealmotion/followup.action.requested"),
    retries=2,
)
async def generate_followup_action_fn(ctx, step):
    """
    Generate a follow-up action document with full observability.
    
    Steps:
    1. Get followup context (transcript, summary, etc.)
    2. Get seller context (profiles)
    3. Get prospect context
    4. Generate action content with AI
    5. Save results
    6. Emit completion event
    """
    event_data = ctx.event.data
    action_id = event_data["action_id"]
    followup_id = event_data["followup_id"]
    action_type = event_data["action_type"]
    user_id = event_data["user_id"]
    language = event_data.get("language", "en")
    
    logger.info(f"Starting Inngest action generation: {action_type} for followup {followup_id}")
    
    # Step 1: Get followup context
    followup_context = await step.run(
        "get-followup-context",
        get_followup_context,
        followup_id
    )
    
    # Step 2: Get seller context
    seller_context = await step.run(
        "get-seller-context",
        get_seller_context,
        followup_context.get("organization_id"), user_id
    )
    
    # Step 3: Get prospect context
    prospect_context = await step.run(
        "get-prospect-context",
        get_prospect_context,
        followup_context.get("prospect_company_name"),
        followup_context.get("organization_id"),
        user_id
    )
    
    # Step 4: Generate action content
    result = await step.run(
        "generate-action-content",
        generate_action_content,
        action_id, followup_id, action_type, user_id, language,
        followup_context, seller_context, prospect_context
    )
    
    # Step 5: Save results
    await step.run(
        "save-results",
        save_action_results,
        action_id, result["content"], result["metadata"]
    )
    
    # Step 6: Emit completion event
    await step.send_event(
        "emit-completion",
        inngest.Event(
            name="dealmotion/followup.action.completed",
            data={
                "action_id": action_id,
                "followup_id": followup_id,
                "action_type": action_type,
                "user_id": user_id,
                "success": True
            }
        )
    )
    
    logger.info(f"Action generation completed: {action_type} (id={action_id})")
    
    return {
        "action_id": action_id,
        "action_type": action_type,
        "status": "completed"
    }


# =============================================================================
# Step Functions
# =============================================================================

async def get_followup_context(followup_id: str) -> dict:
    """Get followup data including transcript and summary."""
    try:
        result = supabase.table("followups").select(
            "id, organization_id, user_id, prospect_company_name, "
            "transcription_text, executive_summary, key_points, "
            "concerns, decisions, next_steps, action_items, "
            "commercial_signals, observations, contact_ids"
        ).eq("id", followup_id).single().execute()
        
        if not result.data:
            raise NonRetriableError(f"Followup {followup_id} not found")
        
        logger.info(f"Got followup context for {followup_id}")
        return result.data
    except Exception as e:
        logger.error(f"Failed to get followup context: {e}")
        raise NonRetriableError(f"Failed to get followup: {e}")


async def get_seller_context(organization_id: str, user_id: str) -> dict:
    """Get seller profiles (company and sales rep)."""
    try:
        context = {}
        
        # Get company profile
        company_result = supabase.table("company_profiles").select("*")\
            .eq("organization_id", organization_id).limit(1).execute()
        if company_result.data:
            context["company_profile"] = company_result.data[0]
        
        # Get sales profile
        sales_result = supabase.table("sales_profiles").select("*")\
            .eq("user_id", user_id).limit(1).execute()
        if sales_result.data:
            context["sales_profile"] = sales_result.data[0]
        
        logger.info(f"Got seller context for user {user_id}")
        return context
    except Exception as e:
        logger.warning(f"Could not get seller context: {e}")
        return {}


async def get_prospect_context(
    prospect_company: Optional[str],
    organization_id: str,
    user_id: str
) -> dict:
    """Get prospect context including research data."""
    try:
        if not prospect_company:
            return {}
        
        # Get prospect
        prospect_result = supabase.table("prospects").select("id, company_name")\
            .eq("organization_id", organization_id)\
            .ilike("company_name", f"%{prospect_company}%")\
            .limit(1).execute()
        
        if not prospect_result.data:
            return {"company_name": prospect_company}
        
        prospect_id = prospect_result.data[0]["id"]
        
        # Get research brief if available
        research_result = supabase.table("research_briefs").select(
            "brief_content, company_name"
        ).eq("prospect_id", prospect_id)\
            .eq("status", "completed")\
            .order("created_at", desc=True)\
            .limit(1).execute()
        
        context = {
            "prospect_id": prospect_id,
            "company_name": prospect_company
        }
        
        if research_result.data:
            context["research_brief"] = research_result.data[0].get("brief_content")
        
        logger.info(f"Got prospect context for {prospect_company}")
        return context
    except Exception as e:
        logger.warning(f"Could not get prospect context: {e}")
        return {"company_name": prospect_company}


async def generate_action_content(
    action_id: str,
    followup_id: str,
    action_type: str,
    user_id: str,
    language: str,
    followup_context: dict,
    seller_context: dict,
    prospect_context: dict
) -> dict:
    """Generate action content using AI."""
    try:
        from app.services.action_generator import ActionGeneratorService
        
        generator = ActionGeneratorService()
        
        # Convert string to ActionType enum
        action_type_enum = ActionType(action_type)
        
        # Generate content
        content, metadata = await generator.generate(
            action_id=action_id,
            followup_id=followup_id,
            action_type=action_type_enum,
            user_id=user_id,
            language=language,
        )
        
        logger.info(f"Generated {action_type} content for {followup_id}")
        return {"content": content, "metadata": metadata}
    except Exception as e:
        logger.error(f"Action content generation failed: {e}")
        raise NonRetriableError(f"Generation failed: {e}")


async def save_action_results(
    action_id: str,
    content: str,
    metadata: dict
) -> dict:
    """Save generated action content to database."""
    try:
        supabase.table("followup_actions").update({
            "content": content,
            "metadata": metadata,
        }).eq("id", action_id).execute()
        
        logger.info(f"Saved action results for {action_id}")
        return {"saved": True}
    except Exception as e:
        logger.error(f"Failed to save action results: {e}")
        # Update with error state
        supabase.table("followup_actions").update({
            "metadata": {"status": "error", "error": str(e)},
        }).eq("id", action_id).execute()
        raise NonRetriableError(f"Failed to save: {e}")

