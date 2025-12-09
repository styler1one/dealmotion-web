"""
Research Agent Inngest Function.

Handles company research workflow with full observability and automatic retries.

Events:
- dealmotion/research.requested: Triggers new research
- dealmotion/research.completed: Emitted when research is done
"""

import logging
from typing import Optional
import inngest
from inngest import NonRetriableError, TriggerEvent

from app.inngest.client import inngest_client
from app.database import get_supabase_service
from app.services.claude_researcher import ClaudeResearcher
from app.services.gemini_researcher import GeminiResearcher
from app.services.kvk_api import KVKApi
from app.services.website_scraper import get_website_scraper
from app.i18n.config import DEFAULT_LANGUAGE

logger = logging.getLogger(__name__)

# Initialize services (will be created once)
claude_researcher = ClaudeResearcher()
gemini_researcher = GeminiResearcher()
kvk_api = KVKApi()
website_scraper = get_website_scraper()

# Database client
supabase = get_supabase_service()


@inngest_client.create_function(
    fn_id="research-company",
    trigger=TriggerEvent(event="dealmotion/research.requested"),
    retries=2,  # Total attempts = 3 (1 initial + 2 retries)
)
async def research_company_fn(ctx, step):
    """
    Multi-step company research with full observability.
    
    Steps:
    1. Update status to 'researching'
    2. Claude AI research
    3. Gemini AI research
    4. KVK lookup (if Dutch company)
    5. Website scraping (if URL provided)
    6. Merge results and generate brief
    7. Save to database
    8. Emit completion event
    """
    # Extract event data
    event_data = ctx.event.data
    research_id = event_data["research_id"]
    company_name = event_data["company_name"]
    country = event_data.get("country")
    city = event_data.get("city")
    linkedin_url = event_data.get("linkedin_url")
    website_url = event_data.get("website_url")
    organization_id = event_data.get("organization_id")
    user_id = event_data.get("user_id")
    language = event_data.get("language", DEFAULT_LANGUAGE)
    
    logger.info(f"Starting Inngest research for {company_name} (id={research_id})")
    
    # Step 1: Update status to researching
    await step.run("update-status-researching", update_research_status, research_id, "researching")
    
    # Step 2: Get seller context (for personalized research)
    seller_context = await step.run("get-seller-context", get_seller_context, organization_id, user_id)
    
    # Step 3: Claude research with retry
    claude_result = await step.run(
        "claude-research",
        run_claude_research,
        company_name, country, city, linkedin_url, seller_context, language
    )
    
    # Step 4: Gemini research with retry
    gemini_result = await step.run(
        "gemini-research",
        run_gemini_research,
        company_name, country, city, linkedin_url, seller_context, language
    )
    
    # Step 5: KVK lookup (conditional - only for Dutch companies)
    kvk_result = None
    if kvk_api.is_dutch_company(country):
        kvk_result = await step.run("kvk-lookup", run_kvk_lookup, company_name, city)
    
    # Step 6: Website scraping (conditional - if URL provided)
    website_result = None
    if website_url:
        website_result = await step.run("website-scrape", run_website_scrape, website_url)
    
    # Step 7: Merge results and generate brief
    brief_content = await step.run(
        "generate-brief",
        merge_and_generate_brief,
        company_name, country, city, claude_result, gemini_result, kvk_result, website_result, seller_context, language
    )
    
    # Step 8: Save results to database
    await step.run(
        "save-results",
        save_research_results,
        research_id, claude_result, gemini_result, kvk_result, website_result, brief_content
    )
    
    # Step 9: Emit completion event
    await step.send_event(
        "emit-completion",
        inngest.Event(
            name="dealmotion/research.completed",
            data={
                "research_id": research_id,
                "company_name": company_name,
                "organization_id": organization_id,
                "user_id": user_id,
                "success": True
            }
        )
    )
    
    logger.info(f"Research completed for {company_name} (id={research_id})")
    
    return {
        "research_id": research_id,
        "status": "completed",
        "company_name": company_name
    }


# =============================================================================
# Step Functions (each is a discrete, retriable unit of work)
# =============================================================================

async def update_research_status(research_id: str, status: str) -> dict:
    """Update research status in database."""
    result = supabase.table("research_briefs").update({
        "status": status
    }).eq("id", research_id).execute()
    return {"updated": True, "status": status}


async def get_seller_context(organization_id: Optional[str], user_id: Optional[str]) -> dict:
    """
    Get seller context for personalized research.
    
    Extracts and flattens relevant fields from company_profile and sales_profile
    so they can be directly used in research prompts.
    """
    if not organization_id:
        return {"has_context": False}
    
    try:
        # Get company profile
        company_response = supabase.table("company_profiles").select("*").eq(
            "organization_id", organization_id
        ).limit(1).execute()
        company_profile = company_response.data[0] if company_response.data else None
        
        # Get sales profile
        sales_profile = None
        if user_id:
            profile_response = supabase.table("sales_profiles").select("*").eq(
                "user_id", user_id
            ).limit(1).execute()
            sales_profile = profile_response.data[0] if profile_response.data else None
        
        # Build flattened context with extracted fields
        context = {
            "has_context": bool(company_profile or sales_profile),
            # Keep raw profiles for debugging/logging
            "company_profile": company_profile,
            "sales_profile": sales_profile,
            # Initialize extracted fields
            "company_name": None,
            "products_services": [],
            "value_propositions": [],
            "target_industries": [],
            "target_market": "B2B",
        }
        
        # Extract from company_profile (primary source)
        if company_profile:
            context["company_name"] = company_profile.get("company_name")
            
            # Products: extract names from products array
            products = company_profile.get("products", []) or []
            context["products_services"] = [
                p.get("name") for p in products 
                if isinstance(p, dict) and p.get("name")
            ]
            
            # Value propositions from core_value_props
            context["value_propositions"] = company_profile.get("core_value_props", []) or []
            
            # Add differentiators to value props if available
            differentiators = company_profile.get("differentiators", []) or []
            if differentiators:
                context["value_propositions"] = context["value_propositions"] + differentiators
            
            # Target industries from Ideal Customer Profile
            icp = company_profile.get("ideal_customer_profile", {}) or {}
            context["target_industries"] = icp.get("industries", []) or []
            
            logger.info(f"Seller context from company_profile: company={context['company_name']}, products={len(context['products_services'])}")
        
        # Fallback/supplement from sales_profile
        if sales_profile:
            # Company name fallback: extract from role "Sales Director at Cmotions"
            if not context.get("company_name"):
                role = sales_profile.get("role", "") or ""
                if " at " in role:
                    context["company_name"] = role.split(" at ")[-1].strip()
                    logger.info(f"Extracted company name from sales_profile role: {context['company_name']}")
            
            # Target industries fallback
            if not context.get("target_industries"):
                context["target_industries"] = sales_profile.get("target_industries", []) or []
            
            # If still no products, try to derive from ai_summary or role
            if not context.get("products_services"):
                ai_summary = sales_profile.get("ai_summary", "") or ""
                # Look for common patterns in the summary
                if "data" in ai_summary.lower() and "ai" in ai_summary.lower():
                    context["products_services"] = ["data and AI solutions"]
                elif "crm" in ai_summary.lower():
                    context["products_services"] = ["CRM solutions"]
                logger.info(f"Derived products from ai_summary: {context['products_services']}")
        
        return context
        
    except Exception as e:
        logger.warning(f"Failed to get seller context: {e}")
        return {"has_context": False}


async def run_claude_research(
    company_name: str,
    country: Optional[str],
    city: Optional[str],
    linkedin_url: Optional[str],
    seller_context: dict,
    language: str
) -> dict:
    """Run Claude AI research."""
    try:
        result = await claude_researcher.search_company(
            company_name=company_name,
            country=country,
            city=city,
            linkedin_url=linkedin_url,
            seller_context=seller_context,
            language=language
        )
        return result
    except Exception as e:
        logger.error(f"Claude research failed: {e}")
        # Return error result but don't fail the entire workflow
        return {"success": False, "error": str(e), "source": "claude"}


async def run_gemini_research(
    company_name: str,
    country: Optional[str],
    city: Optional[str],
    linkedin_url: Optional[str],
    seller_context: dict,
    language: str
) -> dict:
    """Run Gemini AI research."""
    try:
        result = await gemini_researcher.search_company(
            company_name=company_name,
            country=country,
            city=city,
            linkedin_url=linkedin_url,
            seller_context=seller_context,
            language=language
        )
        return result
    except Exception as e:
        logger.error(f"Gemini research failed: {e}")
        return {"success": False, "error": str(e), "source": "gemini"}


async def run_kvk_lookup(company_name: str, city: Optional[str]) -> dict:
    """Run KVK lookup for Dutch companies."""
    try:
        result = await kvk_api.search_company(company_name, city)
        return result
    except Exception as e:
        logger.warning(f"KVK lookup failed: {e}")
        return {"success": False, "error": str(e), "source": "kvk"}


async def run_website_scrape(website_url: str) -> dict:
    """Scrape company website."""
    try:
        result = await website_scraper.scrape_website(website_url)
        return result
    except Exception as e:
        logger.warning(f"Website scrape failed: {e}")
        return {"success": False, "error": str(e), "source": "website"}


async def merge_and_generate_brief(
    company_name: str,
    country: Optional[str],
    city: Optional[str],
    claude_result: dict,
    gemini_result: dict,
    kvk_result: Optional[dict],
    website_result: Optional[dict],
    seller_context: dict,
    language: str
) -> str:
    """Merge all research results and generate unified brief."""
    from app.services.research_orchestrator import ResearchOrchestrator
    
    # Create orchestrator instance for brief generation
    orchestrator = ResearchOrchestrator()
    
    # Combine sources
    sources = {
        "claude": claude_result,
        "gemini": gemini_result
    }
    if kvk_result:
        sources["kvk"] = kvk_result
    if website_result:
        sources["website"] = website_result
    
    # Count successes
    success_count = sum(1 for s in sources.values() if s.get("success"))
    
    # Generate unified brief
    try:
        brief = await orchestrator._generate_unified_brief(
            company_name=company_name,
            country=country,
            city=city,
            sources=sources,
            seller_context=seller_context,
            language=language
        )
        return brief
    except Exception as e:
        logger.error(f"Brief generation failed: {e}")
        # Return a basic brief on failure
        return f"# {company_name}\n\nResearch completed with {success_count} sources."


async def save_research_results(
    research_id: str,
    claude_result: dict,
    gemini_result: dict,
    kvk_result: Optional[dict],
    website_result: Optional[dict],
    brief_content: str
) -> dict:
    """Save all research results to database."""
    
    # Map source names to allowed source_type values
    source_type_map = {
        "claude": "claude",
        "gemini": "gemini",
        "kvk": "kvk",
        "website": "web"
    }
    
    # Save source data
    sources = {
        "claude": claude_result,
        "gemini": gemini_result
    }
    if kvk_result:
        sources["kvk"] = kvk_result
    if website_result:
        sources["website"] = website_result
    
    for source_name, source_result in sources.items():
        source_type = source_type_map.get(source_name, "web")
        supabase.table("research_sources").insert({
            "research_id": research_id,
            "source_type": source_type,
            "source_name": source_name,
            "data": source_result
        }).execute()
    
    # Update research record with results
    research_data = {
        "sources": sources,
        "success_count": sum(1 for s in sources.values() if s.get("success")),
        "total_sources": len(sources)
    }
    
    supabase.table("research_briefs").update({
        "status": "completed",
        "research_data": research_data,
        "brief_content": brief_content,
        "completed_at": "now()"
    }).eq("id", research_id).execute()
    
    return {"saved": True, "sources_count": len(sources)}

