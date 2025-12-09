"""
Contact Analysis Inngest Function.

Handles contact person analysis with full observability and automatic retries.

Events:
- dealmotion/contact.added: Triggers contact analysis
- dealmotion/contact.analyzed: Emitted when analysis is complete
"""

import logging
from typing import Optional, List, Dict, Any
from datetime import datetime
import inngest
from inngest import NonRetriableError, TriggerEvent

from app.inngest.client import inngest_client
from app.database import get_supabase_service
from app.services.contact_analyzer import get_contact_analyzer

logger = logging.getLogger(__name__)

# Database client
supabase = get_supabase_service()


@inngest_client.create_function(
    fn_id="contact-analyze",
    trigger=TriggerEvent(event="dealmotion/contact.added"),
    retries=2,
)
async def analyze_contact_fn(ctx, step):
    """
    Analyze a contact person with full observability.
    
    Steps:
    1. Get company context from research
    2. Get seller context (profiles)
    3. Run AI analysis
    4. Save results
    5. Emit completion event
    """
    event_data = ctx.event.data
    contact_id = event_data["contact_id"]
    contact_name = event_data["contact_name"]
    contact_role = event_data.get("contact_role")
    linkedin_url = event_data.get("linkedin_url")
    research_id = event_data["research_id"]
    organization_id = event_data["organization_id"]
    user_id = event_data["user_id"]
    linkedin_about = event_data.get("linkedin_about")
    linkedin_experience = event_data.get("linkedin_experience")
    additional_notes = event_data.get("additional_notes")
    language = event_data.get("language", "en")
    
    logger.info(f"Starting Inngest contact analysis for {contact_name} (id={contact_id})")
    
    # Step 1: Get company context from research
    company_context = await step.run(
        "get-company-context",
        get_company_context,
        research_id
    )
    
    # Step 2: Get seller context (profiles)
    seller_context = await step.run(
        "get-seller-context",
        get_seller_context,
        organization_id, user_id
    )
    
    # Step 3: Run AI analysis
    analysis = await step.run(
        "analyze-contact",
        run_contact_analysis,
        contact_name, contact_role, linkedin_url,
        company_context, seller_context, language,
        linkedin_about, linkedin_experience, additional_notes
    )
    
    # Step 4: Save results
    await step.run(
        "save-results",
        save_contact_analysis,
        contact_id, analysis, linkedin_url
    )
    
    # Step 5: Emit completion event
    await step.send_event(
        "emit-completion",
        inngest.Event(
            name="dealmotion/contact.analyzed",
            data={
                "contact_id": contact_id,
                "contact_name": contact_name,
                "organization_id": organization_id,
                "user_id": user_id,
                "success": True
            }
        )
    )
    
    logger.info(f"Contact analysis completed for {contact_name} (id={contact_id})")
    
    return {
        "contact_id": contact_id,
        "status": "completed",
        "contact_name": contact_name
    }


# =============================================================================
# Step Functions
# =============================================================================

async def get_company_context(research_id: str) -> dict:
    """Get company context from research brief."""
    try:
        analyzer = get_contact_analyzer()
        context = await analyzer.get_company_context(research_id)
        logger.info(f"Got company context from research {research_id}")
        return context
    except Exception as e:
        logger.warning(f"Could not get company context: {e}")
        return {}


async def get_seller_context(organization_id: str, user_id: str) -> dict:
    """Get seller context (company and sales profiles)."""
    try:
        analyzer = get_contact_analyzer()
        context = await analyzer.get_seller_context(organization_id, user_id)
        logger.info(f"Got seller context for user {user_id}")
        return context
    except Exception as e:
        logger.warning(f"Could not get seller context: {e}")
        return {}


async def run_contact_analysis(
    contact_name: str,
    contact_role: Optional[str],
    linkedin_url: Optional[str],
    company_context: dict,
    seller_context: dict,
    language: str,
    linkedin_about: Optional[str],
    linkedin_experience: Optional[str],
    additional_notes: Optional[str]
) -> dict:
    """Run AI analysis on contact."""
    try:
        analyzer = get_contact_analyzer()
        
        # Build user-provided context
        user_provided_context = {}
        if linkedin_about:
            user_provided_context["about"] = linkedin_about
        if linkedin_experience:
            user_provided_context["experience"] = linkedin_experience
        if additional_notes:
            user_provided_context["notes"] = additional_notes
        
        analysis = await analyzer.analyze_contact(
            contact_name=contact_name,
            contact_role=contact_role,
            linkedin_url=linkedin_url,
            company_context=company_context,
            seller_context=seller_context,
            language=language,
            user_provided_context=user_provided_context if user_provided_context else None
        )
        
        logger.info(f"Analysis completed for {contact_name}")
        return analysis
    except Exception as e:
        logger.error(f"Contact analysis failed: {e}")
        raise NonRetriableError(f"Contact analysis failed: {e}")


async def save_contact_analysis(
    contact_id: str,
    analysis: dict,
    linkedin_url: Optional[str]
) -> dict:
    """Save analysis results to database."""
    try:
        update_data = {
            "profile_brief": analysis.get("profile_brief"),
            "communication_style": analysis.get("communication_style"),
            "decision_authority": analysis.get("decision_authority"),
            "probable_drivers": analysis.get("probable_drivers"),
            "opening_suggestions": analysis.get("opening_suggestions"),
            "questions_to_ask": analysis.get("questions_to_ask"),
            "topics_to_avoid": analysis.get("topics_to_avoid"),
            "analyzed_at": datetime.utcnow().isoformat(),
            "analysis_source": "linkedin" if linkedin_url else "role_based"
        }
        
        supabase.table("prospect_contacts")\
            .update(update_data)\
            .eq("id", contact_id)\
            .execute()
        
        logger.info(f"Saved analysis for contact {contact_id}")
        return {"saved": True}
    except Exception as e:
        logger.error(f"Failed to save contact analysis: {e}")
        # Update with error
        supabase.table("prospect_contacts")\
            .update({
                "profile_brief": f"Analysis failed: {str(e)}",
                "analyzed_at": datetime.utcnow().isoformat()
            })\
            .eq("id", contact_id)\
            .execute()
        raise NonRetriableError(f"Failed to save analysis: {e}")

