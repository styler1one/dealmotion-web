"""
Profile Finalize Inngest Functions.

Handles async generation of sales narrative and AI summary after profile save.
This allows the /complete endpoint to return immediately while heavy AI work
happens in the background.

Events:
- dealmotion/profile.finalize.requested: Triggers narrative + summary generation

Throttling:
- Per-user: Max 5 per minute (narrative generation is a Claude call)
"""

import logging
from typing import Optional, Dict, Any
from datetime import datetime, timedelta
import inngest
from inngest import NonRetriableError, TriggerEvent, Throttle

from app.inngest.client import inngest_client
from app.database import get_supabase_service
from app.services.profile_chat_service import get_profile_chat_service

logger = logging.getLogger(__name__)

supabase = get_supabase_service()


# =============================================================================
# Profile Finalize Function
# =============================================================================

@inngest_client.create_function(
    fn_id="profile-finalize",
    trigger=TriggerEvent(event="dealmotion/profile.finalize.requested"),
    retries=2,
    throttle=Throttle(
        limit=5,
        period=timedelta(minutes=1),
        key="event.data.user_id",
    ),
)
async def profile_finalize_fn(ctx, step):
    """
    Generate sales narrative and AI summary asynchronously.
    
    Steps:
    1. Get profile data from chat session or database
    2. Generate sales narrative with Claude
    3. Generate AI summary with Claude
    4. Update sales_profiles with narrative and summary
    """
    event_data = ctx.event.data
    profile_id = event_data["profile_id"]
    user_id = event_data["user_id"]
    organization_id = event_data["organization_id"]
    profile_type = event_data.get("profile_type", "sales")
    profile_data = event_data.get("profile_data", {})
    linkedin_raw = event_data.get("linkedin_raw", {})
    output_language = event_data.get("output_language", "en")
    
    logger.info(f"[PROFILE_FINALIZE] Starting for profile {profile_id} (lang={output_language})")
    
    try:
        # Step 1: Generate narrative
        narrative = await step.run(
            "generate-narrative",
            generate_sales_narrative,
            profile_data, linkedin_raw, output_language
        )
        
        # Step 2: Generate AI summary
        ai_summary = await step.run(
            "generate-summary",
            generate_ai_summary,
            profile_data, output_language
        )
        
        # Step 3: Update profile in database
        await step.run(
            "update-profile",
            update_profile_with_narrative,
            profile_id, profile_type, narrative, ai_summary
        )
        
        logger.info(f"[PROFILE_FINALIZE] Completed for profile {profile_id}")
        return {"profile_id": profile_id, "status": "completed"}
        
    except Exception as e:
        logger.error(f"[PROFILE_FINALIZE] Failed: {e}")
        raise NonRetriableError(f"Profile finalize failed: {e}")


# =============================================================================
# Step Functions
# =============================================================================

async def generate_sales_narrative(
    profile_data: Dict[str, Any],
    linkedin_raw: Dict[str, Any],
    output_language: str
) -> str:
    """Generate sales narrative using Claude."""
    try:
        chat_service = get_profile_chat_service()
        narrative = await chat_service.generate_sales_narrative(
            profile_data,
            linkedin_raw,
            language=output_language
        )
        logger.info(f"[PROFILE_FINALIZE] Generated narrative ({len(narrative)} chars)")
        return narrative
    except Exception as e:
        logger.error(f"[PROFILE_FINALIZE] Narrative generation failed: {e}")
        return ""


async def generate_ai_summary(
    profile_data: Dict[str, Any],
    output_language: str
) -> str:
    """Generate AI summary using Claude."""
    try:
        chat_service = get_profile_chat_service()
        summary = await chat_service.generate_ai_summary(
            profile_data,
            language=output_language
        )
        logger.info(f"[PROFILE_FINALIZE] Generated summary ({len(summary)} chars)")
        return summary
    except Exception as e:
        logger.error(f"[PROFILE_FINALIZE] Summary generation failed: {e}")
        return ""


async def update_profile_with_narrative(
    profile_id: str,
    profile_type: str,
    narrative: str,
    ai_summary: str
) -> dict:
    """Update profile with generated narrative and summary."""
    try:
        table = "sales_profiles" if profile_type == "sales" else "company_profiles"
        narrative_field = "sales_narrative" if profile_type == "sales" else "company_narrative"
        
        update_data = {
            "updated_at": datetime.utcnow().isoformat()
        }
        
        if narrative:
            update_data[narrative_field] = narrative
        if ai_summary:
            update_data["ai_summary"] = ai_summary
        
        supabase.table(table)\
            .update(update_data)\
            .eq("id", profile_id)\
            .execute()
        
        logger.info(f"[PROFILE_FINALIZE] Updated profile {profile_id} with narrative")
        return {"updated": True}
    except Exception as e:
        logger.error(f"[PROFILE_FINALIZE] Failed to update profile: {e}")
        raise

