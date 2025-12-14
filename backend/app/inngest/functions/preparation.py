"""
Preparation Agent Inngest Function.

Handles meeting preparation workflow with full observability and automatic retries.

Events:
- dealmotion/prep.requested: Triggers new preparation
- dealmotion/prep.completed: Emitted when preparation is done

Throttling:
- Per-user: Max 5 preparations per minute (heavy AI operation)
"""

import logging
from typing import Optional, List
from datetime import datetime, timedelta
import inngest
from inngest import NonRetriableError, TriggerEvent, Throttle

from app.inngest.client import inngest_client
from app.database import get_supabase_service
from app.services.rag_service import rag_service
from app.services.prep_generator import prep_generator

logger = logging.getLogger(__name__)

# Database client
supabase = get_supabase_service()


@inngest_client.create_function(
    fn_id="preparation-meeting",
    trigger=TriggerEvent(event="dealmotion/prep.requested"),
    retries=2,  # Total attempts = 3 (1 initial + 2 retries)
    # Throttle: Max 5 preparations per minute per user
    # Preparation uses Claude for comprehensive brief generation
    throttle=Throttle(
        limit=5,
        period=timedelta(minutes=1),
        key="event.data.user_id",
    ),
)
async def preparation_meeting_fn(ctx, step):
    """
    Multi-step meeting preparation with full observability.
    
    Steps:
    1. Update status to 'generating'
    2. Build context using RAG service
    3. Fetch contact persons if specified
    4. Generate meeting brief with AI
    5. Save results to database
    6. Emit completion event
    """
    # Extract event data
    event_data = ctx.event.data
    prep_id = event_data["prep_id"]
    prospect_company = event_data["prospect_company"]
    meeting_type = event_data["meeting_type"]
    organization_id = event_data["organization_id"]
    user_id = event_data["user_id"]
    custom_notes = event_data.get("custom_notes")
    contact_ids = event_data.get("contact_ids", [])
    language = event_data.get("language", "en")
    
    logger.info(f"Starting Inngest preparation for {prospect_company} (id={prep_id})")
    
    # Step 1: Update status to generating
    await step.run("update-status-generating", update_prep_status, prep_id, "generating")
    
    # Step 2: Build context using RAG service
    context = await step.run(
        "build-rag-context",
        build_rag_context,
        prospect_company, meeting_type, organization_id, user_id, custom_notes
    )
    
    # Step 3: Fetch contact persons if specified
    contacts_data = []
    if contact_ids:
        contacts_data = await step.run(
            "fetch-contacts",
            fetch_contacts,
            contact_ids, organization_id
        )
    
    # Step 4: Generate meeting brief with AI
    result = await step.run(
        "generate-meeting-brief",
        generate_meeting_brief,
        context, contacts_data, language
    )
    
    # Step 5: Save results to database
    await step.run(
        "save-results",
        save_prep_results,
        prep_id, result
    )
    
    # Step 6: Emit completion event
    await step.send_event(
        "emit-completion",
        inngest.Event(
            name="dealmotion/prep.completed",
            data={
                "prep_id": prep_id,
                "prospect_company": prospect_company,
                "meeting_type": meeting_type,
                "organization_id": organization_id,
                "user_id": user_id,
                "success": True
            }
        )
    )
    
    logger.info(f"Preparation completed for {prospect_company} (id={prep_id})")
    
    return {
        "prep_id": prep_id,
        "status": "completed",
        "prospect_company": prospect_company
    }


# =============================================================================
# Step Functions (each is a discrete, retriable unit of work)
# =============================================================================

async def update_prep_status(prep_id: str, status: str) -> dict:
    """Update preparation status in database."""
    result = supabase.table("meeting_preps").update({
        "status": status
    }).eq("id", prep_id).execute()
    return {"updated": True, "status": status}


async def build_rag_context(
    prospect_company: str,
    meeting_type: str,
    organization_id: str,
    user_id: str,
    custom_notes: Optional[str]
) -> dict:
    """Build context using RAG service (includes profile context)."""
    try:
        context = await rag_service.build_context_for_ai(
            prospect_company=prospect_company,
            meeting_type=meeting_type,
            organization_id=organization_id,
            user_id=user_id,
            custom_notes=custom_notes
        )
        logger.info(f"Built RAG context for {prospect_company}")
        return context
    except Exception as e:
        logger.error(f"Failed to build RAG context: {e}")
        # Return minimal context on failure
        return {
            "prospect_company": prospect_company,
            "meeting_type": meeting_type,
            "custom_notes": custom_notes,
            "error": str(e)
        }


async def fetch_contacts(contact_ids: List[str], organization_id: str) -> List[dict]:
    """Fetch contact persons for the meeting."""
    try:
        logger.info(f"Fetching {len(contact_ids)} contacts for prep")
        contacts_response = supabase.table("prospect_contacts")\
            .select("*")\
            .in_("id", contact_ids)\
            .eq("organization_id", organization_id)\
            .execute()
        
        if contacts_response.data:
            logger.info(f"Found {len(contacts_response.data)} contacts with analysis")
            return contacts_response.data
        return []
    except Exception as e:
        logger.warning(f"Failed to fetch contacts: {e}")
        return []


async def generate_meeting_brief(
    context: dict,
    contacts_data: List[dict],
    language: str
) -> dict:
    """Generate meeting brief with AI."""
    try:
        # Add contacts to context
        context["contacts"] = contacts_data
        context["has_contacts"] = len(contacts_data) > 0
        
        # Generate brief with AI
        result = await prep_generator.generate_meeting_brief(context, language=language)
        logger.info(f"Generated meeting brief for {context.get('prospect_company', 'unknown')}")
        return result
    except Exception as e:
        logger.error(f"Brief generation failed: {e}")
        raise NonRetriableError(f"Brief generation failed: {e}")


async def save_prep_results(prep_id: str, result: dict) -> dict:
    """Save preparation results to database."""
    try:
        supabase.table("meeting_preps").update({
            "status": "completed",
            "brief_content": result.get("brief_content"),
            "talking_points": result.get("talking_points"),
            "questions": result.get("questions"),
            "strategy": result.get("strategy"),
            "rag_sources": result.get("rag_sources"),
            "completed_at": datetime.utcnow().isoformat()
        }).eq("id", prep_id).execute()
        
        logger.info(f"Saved prep results for {prep_id}")
        return {"saved": True}
    except Exception as e:
        logger.error(f"Failed to save prep results: {e}")
        # Mark as failed
        supabase.table("meeting_preps").update({
            "status": "failed",
            "error_message": str(e)
        }).eq("id", prep_id).execute()
        raise NonRetriableError(f"Failed to save results: {e}")

