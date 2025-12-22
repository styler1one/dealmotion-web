"""
Magic Onboarding Inngest Functions.

Handles AI-powered sales and company profile creation with full observability
and automatic retries.

Events:
- dealmotion/magic-onboarding.sales.requested: Triggers sales profile enrichment
- dealmotion/magic-onboarding.sales.completed: Emitted when complete
- dealmotion/magic-onboarding.company.requested: Triggers company profile enrichment
- dealmotion/magic-onboarding.company.completed: Emitted when complete

Throttling:
- Per-user: Max 3 magic onboarding requests per minute (heavy AI operation)

This is designed for scalability with thousands of users:
- Rate-limited to prevent API exhaustion
- Automatic retries on transient failures
- Full observability in Inngest dashboard
"""

import logging
from typing import Optional, Dict, Any
from datetime import datetime, timedelta
import inngest
from inngest import NonRetriableError, TriggerEvent, Throttle

from app.inngest.client import inngest_client
from app.database import get_supabase_service
from app.services.magic_onboarding_service import get_magic_onboarding_service

logger = logging.getLogger(__name__)

# Database client
supabase = get_supabase_service()


# =============================================================================
# Sales Profile Magic Onboarding
# =============================================================================

@inngest_client.create_function(
    fn_id="magic-onboarding-sales",
    trigger=TriggerEvent(event="dealmotion/magic-onboarding.sales.requested"),
    retries=2,
    # Throttle: Max 3 magic onboarding requests per minute per user
    # This is a heavy operation (LinkedIn enrichment + AI synthesis)
    throttle=Throttle(
        limit=3,
        period=timedelta(minutes=1),
        key="event.data.user_id",
    ),
)
async def magic_onboard_sales_fn(ctx, step):
    """
    AI-powered sales profile creation with full observability.
    
    Steps:
    1. Update session status to 'processing'
    2. Enrich LinkedIn profile via Exa
    3. Synthesize profile with Claude
    4. Save result to session
    5. Emit completion event
    """
    event_data = ctx.event.data
    session_id = event_data["session_id"]
    user_id = event_data["user_id"]
    organization_id = event_data["organization_id"]
    linkedin_url = event_data.get("linkedin_url")
    user_name = event_data.get("user_name")
    company_name = event_data.get("company_name")
    
    logger.info(f"Starting magic onboarding for sales profile (session={session_id})")
    
    # Step 1: Update session status
    await step.run(
        "update-status-processing",
        update_session_status,
        session_id, "processing"
    )
    
    # Step 2: Run magic onboarding
    try:
        result = await step.run(
            "enrich-and-synthesize",
            run_sales_magic_onboarding,
            linkedin_url, user_name, company_name
        )
        
        # Step 3: Save successful result
        await step.run(
            "save-result",
            save_session_result,
            session_id, "completed", result
        )
        
        # Step 4: Emit completion event
        await step.send_event(
            "emit-completion",
            inngest.Event(
                name="dealmotion/magic-onboarding.sales.completed",
                data={
                    "session_id": session_id,
                    "user_id": user_id,
                    "organization_id": organization_id,
                    "success": True
                }
            )
        )
        
        logger.info(f"Magic onboarding completed for sales profile (session={session_id})")
        return {"session_id": session_id, "status": "completed"}
        
    except Exception as e:
        logger.error(f"Magic onboarding failed: {e}")
        
        # Save failure
        await step.run(
            "save-failure",
            save_session_result,
            session_id, "failed", None, str(e)
        )
        
        # Emit failure event
        await step.send_event(
            "emit-failure",
            inngest.Event(
                name="dealmotion/magic-onboarding.sales.failed",
                data={
                    "session_id": session_id,
                    "user_id": user_id,
                    "organization_id": organization_id,
                    "error": str(e)
                }
            )
        )
        
        raise NonRetriableError(f"Magic onboarding failed: {e}")


# =============================================================================
# Company Profile Magic Onboarding
# =============================================================================

@inngest_client.create_function(
    fn_id="magic-onboarding-company",
    trigger=TriggerEvent(event="dealmotion/magic-onboarding.company.requested"),
    retries=2,
    # Throttle: Max 3 per minute per user
    throttle=Throttle(
        limit=3,
        period=timedelta(minutes=1),
        key="event.data.user_id",
    ),
)
async def magic_onboard_company_fn(ctx, step):
    """
    AI-powered company profile creation with full observability.
    """
    event_data = ctx.event.data
    session_id = event_data["session_id"]
    user_id = event_data["user_id"]
    organization_id = event_data["organization_id"]
    company_name = event_data["company_name"]
    website = event_data.get("website")
    linkedin_url = event_data.get("linkedin_url")
    country = event_data.get("country")
    
    logger.info(f"Starting magic onboarding for company profile (session={session_id})")
    
    # Step 1: Update session status
    await step.run(
        "update-status-processing",
        update_session_status,
        session_id, "processing"
    )
    
    # Step 2: Run magic onboarding
    try:
        result = await step.run(
            "research-and-synthesize",
            run_company_magic_onboarding,
            company_name, website, linkedin_url, country
        )
        
        # Step 3: Save successful result
        await step.run(
            "save-result",
            save_session_result,
            session_id, "completed", result
        )
        
        # Step 4: Emit completion event
        await step.send_event(
            "emit-completion",
            inngest.Event(
                name="dealmotion/magic-onboarding.company.completed",
                data={
                    "session_id": session_id,
                    "user_id": user_id,
                    "organization_id": organization_id,
                    "success": True
                }
            )
        )
        
        logger.info(f"Magic onboarding completed for company profile (session={session_id})")
        return {"session_id": session_id, "status": "completed"}
        
    except Exception as e:
        logger.error(f"Company magic onboarding failed: {e}")
        
        await step.run(
            "save-failure",
            save_session_result,
            session_id, "failed", None, str(e)
        )
        
        await step.send_event(
            "emit-failure",
            inngest.Event(
                name="dealmotion/magic-onboarding.company.failed",
                data={
                    "session_id": session_id,
                    "user_id": user_id,
                    "organization_id": organization_id,
                    "error": str(e)
                }
            )
        )
        
        raise NonRetriableError(f"Company magic onboarding failed: {e}")


# =============================================================================
# Step Functions
# =============================================================================

async def update_session_status(session_id: str, status: str) -> dict:
    """Update magic onboarding session status."""
    try:
        supabase.table("magic_onboarding_sessions")\
            .update({
                "status": status,
                "updated_at": datetime.utcnow().isoformat()
            })\
            .eq("id", session_id)\
            .execute()
        
        logger.info(f"Updated session {session_id} status to {status}")
        return {"updated": True}
    except Exception as e:
        logger.error(f"Failed to update session status: {e}")
        raise


async def run_sales_magic_onboarding(
    linkedin_url: Optional[str],
    user_name: Optional[str],
    company_name: Optional[str]
) -> dict:
    """Run sales profile magic onboarding."""
    try:
        service = get_magic_onboarding_service()
        result = await service.magic_onboard_sales_profile(
            linkedin_url=linkedin_url,
            user_name=user_name,
            company_name=company_name
        )
        return result
    except Exception as e:
        logger.error(f"Sales magic onboarding failed: {e}")
        raise NonRetriableError(f"Sales magic onboarding failed: {e}")


async def run_company_magic_onboarding(
    company_name: str,
    website: Optional[str],
    linkedin_url: Optional[str],
    country: Optional[str]
) -> dict:
    """Run company profile magic onboarding."""
    try:
        service = get_magic_onboarding_service()
        result = await service.magic_onboard_company_profile(
            company_name=company_name,
            website=website,
            linkedin_url=linkedin_url,
            country=country
        )
        return result
    except Exception as e:
        logger.error(f"Company magic onboarding failed: {e}")
        raise NonRetriableError(f"Company magic onboarding failed: {e}")


async def save_session_result(
    session_id: str,
    status: str,
    result: Optional[dict],
    error_message: Optional[str] = None
) -> dict:
    """Save magic onboarding result to session."""
    try:
        update_data = {
            "status": status,
            "updated_at": datetime.utcnow().isoformat()
        }
        
        if result:
            update_data["result_data"] = result
            update_data["completed_at"] = datetime.utcnow().isoformat()
        
        if error_message:
            update_data["error_message"] = error_message
        
        supabase.table("magic_onboarding_sessions")\
            .update(update_data)\
            .eq("id", session_id)\
            .execute()
        
        logger.info(f"Saved session {session_id} result (status={status})")
        return {"saved": True}
    except Exception as e:
        logger.error(f"Failed to save session result: {e}")
        raise

