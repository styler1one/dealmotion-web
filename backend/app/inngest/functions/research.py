"""
Research Agent Inngest Function - Gemini-First Architecture.

Cost-optimized workflow:
- Gemini: ALL web searching (cheap, $0.10/1M tokens)
- Claude: ONLY analysis (no web search, one call)

Savings: ~85% reduction in token costs.

Events:
- dealmotion/research.requested: Triggers new research
- dealmotion/research.completed: Emitted when research is done

Throttling:
- Per-user: Max 5 researches per minute (heavy AI operation)
"""

import logging
from datetime import timedelta
from typing import Optional
import inngest
from inngest import NonRetriableError, TriggerEvent, Throttle

from app.inngest.client import inngest_client
from app.database import get_supabase_service
from app.services.gemini_researcher import GeminiResearcher
from app.services.claude_researcher import ClaudeResearcher
from app.services.kvk_api import KVKApi
from app.services.website_scraper import get_website_scraper
from app.i18n.config import DEFAULT_LANGUAGE

logger = logging.getLogger(__name__)

# Initialize services (created once)
gemini_researcher = GeminiResearcher()
claude_researcher = ClaudeResearcher()
kvk_api = KVKApi()
website_scraper = get_website_scraper()

# Database client
supabase = get_supabase_service()


@inngest_client.create_function(
    fn_id="research-company",
    trigger=TriggerEvent(event="dealmotion/research.requested"),
    retries=2,
    # Throttle: Max 5 researches per minute per user
    # Research is heavy (Gemini + Claude), so we limit more strictly
    throttle=Throttle(
        limit=5,
        period=timedelta(minutes=1),
        key="event.data.user_id",
    ),
)
async def research_company_fn(ctx, step):
    """
    Gemini-first company research with full observability.
    
    Architecture (Cost-Optimized):
    1. Update status to 'researching'
    2. Get seller context
    3. Gemini: Comprehensive web search (PRIMARY - does all searching)
    4. KVK lookup (if Dutch company)
    5. Website scraping (if URL provided)
    6. Claude: Analyze data and generate report (NO web search)
    7. Save to database
    8. Emit completion event
    
    Cost: ~$0.15-0.20 per research (was ~$0.50-1.00)
    """
    # Extract event data
    event_data = ctx.event.data
    research_id = event_data["research_id"]
    company_name = event_data["company_name"]
    country = event_data.get("country")
    city = event_data.get("city")
    linkedin_url = event_data.get("linkedin_url")
    website_url = event_data.get("website_url")
    custom_intel = event_data.get("custom_intel")  # User's own knowledge about prospect
    organization_id = event_data.get("organization_id")
    user_id = event_data.get("user_id")
    language = event_data.get("language", DEFAULT_LANGUAGE)
    
    logger.info(f"Starting Gemini-first research for {company_name} (id={research_id})")
    
    # Step 1: Update status to researching
    await step.run("update-status-researching", update_research_status, research_id, "researching")
    
    # Step 2: Get seller context (for personalized research)
    seller_context = await step.run("get-seller-context", get_seller_context, organization_id, user_id)
    
    # Add organization_id and custom_intel to seller_context
    if seller_context:
        seller_context["organization_id"] = organization_id
        if custom_intel:
            seller_context["custom_intel"] = custom_intel
    
    # Step 3: Gemini comprehensive research (PRIMARY - does all web searching)
    gemini_result = await step.run(
        "gemini-comprehensive-research",
        run_gemini_research,
        company_name, country, city, linkedin_url, seller_context, language
    )
    
    # Step 4: KVK lookup (conditional - only for Dutch companies)
    kvk_result = None
    if kvk_api.is_dutch_company(country):
        kvk_result = await step.run("kvk-lookup", run_kvk_lookup, company_name, city)
    
    # Step 5: Website scraping (conditional - if URL provided)
    website_result = None
    if website_url:
        website_result = await step.run("website-scrape", run_website_scrape, website_url)
    
    # Step 6: Claude analysis (NO web search - just analyzes Gemini data)
    brief_content = await step.run(
        "claude-analysis",
        run_claude_analysis,
        company_name, country, city, gemini_result, kvk_result, website_result, seller_context, language
    )
    
    # Step 7: Save results to database
    await step.run(
        "save-results",
        save_research_results,
        research_id, gemini_result, kvk_result, website_result, brief_content
    )
    
    # Step 7b: Get prospect_id for Autopilot detection
    prospect_id = await step.run(
        "get-prospect-id",
        get_research_prospect_id,
        research_id
    )
    
    # Step 8: Emit completion event (with prospect_id for Autopilot)
    await step.send_event(
        "emit-completion",
        inngest.Event(
            name="dealmotion/research.completed",
            data={
                "research_id": research_id,
                "company_name": company_name,
                "organization_id": organization_id,
                "user_id": user_id,
                "prospect_id": prospect_id,  # Added for Autopilot detection
                "success": True
            }
        )
    )
    
    logger.info(f"Gemini-first research completed for {company_name} (id={research_id})")
    
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


async def get_research_prospect_id(research_id: str) -> Optional[str]:
    """Get prospect_id from research_briefs for Autopilot detection."""
    try:
        result = supabase.table("research_briefs").select("prospect_id").eq(
            "id", research_id
        ).limit(1).execute()
        if result.data and result.data[0].get("prospect_id"):
            return result.data[0]["prospect_id"]
        return None
    except Exception as e:
        logger.warning(f"Failed to get prospect_id for research {research_id}: {e}")
        return None


async def get_seller_context(organization_id: Optional[str], user_id: Optional[str]) -> dict:
    """
    Get seller context for personalized research.
    
    Includes:
    - Products with benefits
    - ICP (pain points, decision makers, company sizes)
    - Differentiators and value propositions
    """
    if not organization_id:
        return {"has_context": False}
    
    try:
        # Get company profile
        company_response = supabase.table("company_profiles").select("*").eq(
            "organization_id", organization_id
        ).limit(1).execute()
        company_profile = company_response.data[0] if company_response.data else None
        
        # Build context
        context = {
            "has_context": bool(company_profile),
            "company_name": None,
            "products": [],
            "value_propositions": [],
            "differentiators": [],
            "target_industries": [],
            "target_company_sizes": [],
            "ideal_pain_points": [],
            "target_decision_makers": [],
        }
        
        if company_profile:
            context["company_name"] = company_profile.get("company_name")
            
            # Products with benefits
            products = company_profile.get("products", []) or []
            for p in products[:5]:
                if isinstance(p, dict) and p.get("name"):
                    context["products"].append({
                        "name": p.get("name"),
                        "benefits": p.get("benefits", [])[:3] if p.get("benefits") else []
                    })
            
            # Value propositions and differentiators
            context["value_propositions"] = (company_profile.get("core_value_props", []) or [])[:5]
            context["differentiators"] = (company_profile.get("differentiators", []) or [])[:3]
            
            # ICP details
            icp = company_profile.get("ideal_customer_profile", {}) or {}
            context["target_industries"] = (icp.get("industries", []) or [])[:5]
            context["target_company_sizes"] = (icp.get("company_sizes", []) or [])[:3]
            context["ideal_pain_points"] = (icp.get("pain_points", []) or [])[:5]
            context["target_decision_makers"] = (icp.get("decision_makers", []) or [])[:5]
            
            logger.info(
                f"Seller context loaded: {context['company_name']}, "
                f"products={len(context['products'])}, "
                f"pain_points={len(context['ideal_pain_points'])}"
            )
        
        # Fallback: get company name from sales profile
        if not context.get("company_name") and user_id:
            profile_response = supabase.table("sales_profiles").select("role").eq(
                "user_id", user_id
            ).limit(1).execute()
            if profile_response.data:
                role = profile_response.data[0].get("role", "") or ""
                if " at " in role:
                    context["company_name"] = role.split(" at ")[-1].strip()
                    context["has_context"] = True
        
        return context
        
    except Exception as e:
        logger.warning(f"Failed to get seller context: {e}")
        return {"has_context": False}


async def run_gemini_research(
    company_name: str,
    country: Optional[str],
    city: Optional[str],
    linkedin_url: Optional[str],
    seller_context: dict,
    language: str
) -> dict:
    """
    Run Gemini comprehensive research.
    
    This is the PRIMARY research step - Gemini does ALL web searching.
    Much cheaper than Claude web search (~30x less per token).
    """
    try:
        result = await gemini_researcher.search_company(
            company_name=company_name,
            country=country,
            city=city,
            linkedin_url=linkedin_url,
            seller_context=seller_context,
            language=language
        )
        
        # Log token usage
        if result.get("token_stats"):
            stats = result["token_stats"]
            logger.info(
                f"Gemini research tokens: {stats.get('input_tokens', 'N/A')} in, "
                f"{stats.get('output_tokens', 'N/A')} out"
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


async def run_claude_analysis(
    company_name: str,
    country: Optional[str],
    city: Optional[str],
    gemini_result: dict,
    kvk_result: Optional[dict],
    website_result: Optional[dict],
    seller_context: dict,
    language: str
) -> str:
    """
    Run Claude analysis on collected data.
    
    This step does NOT perform web searches - Claude only analyzes
    the data collected by Gemini and generates the final report.
    
    Much cheaper than Claude with web_search tool.
    """
    # Check if Gemini succeeded
    if not gemini_result.get("success"):
        logger.error(f"Cannot analyze - Gemini research failed: {gemini_result.get('error')}")
        return f"# Research Failed: {company_name}\n\nGemini research failed. Unable to generate report."
    
    gemini_data = gemini_result.get("data", "")
    
    if not gemini_data:
        return f"# Research Failed: {company_name}\n\nNo research data available."
    
    try:
        result = await claude_researcher.analyze_research_data(
            company_name=company_name,
            gemini_data=gemini_data,
            country=country,
            city=city,
            kvk_data=kvk_result,
            website_data=website_result,
            kb_chunks=None,  # KB chunks can be added later if needed
            seller_context=seller_context,
            language=language
        )
        
        # Log token usage
        if result.get("token_stats"):
            stats = result["token_stats"]
            logger.info(
                f"Claude analysis tokens: {stats.get('input_tokens', 0)} in, "
                f"{stats.get('output_tokens', 0)} out"
            )
        
        if result.get("success"):
            return result.get("data", "")
        else:
            logger.error(f"Claude analysis failed: {result.get('error')}")
            # Fallback: return raw Gemini data
            return f"# Research Brief: {company_name}\n\n**Note**: Analysis failed, showing raw data.\n\n{gemini_data}"
            
    except Exception as e:
        logger.error(f"Claude analysis failed: {e}")
        return f"# Research Brief: {company_name}\n\n**Note**: Analysis failed, showing raw data.\n\n{gemini_data}"


async def save_research_results(
    research_id: str,
    gemini_result: dict,
    kvk_result: Optional[dict],
    website_result: Optional[dict],
    brief_content: str
) -> dict:
    """Save all research results to database."""
    
    # Map source names to allowed source_type values
    source_type_map = {
        "gemini": "gemini",
        "kvk": "kvk",
        "website": "web"
    }
    
    # Build sources dict
    sources = {"gemini": gemini_result}
    if kvk_result:
        sources["kvk"] = kvk_result
    if website_result:
        sources["website"] = website_result
    
    # Save each source to research_sources table
    for source_name, source_result in sources.items():
        source_type = source_type_map.get(source_name, "web")
        try:
            supabase.table("research_sources").insert({
                "research_id": research_id,
                "source_type": source_type,
                "source_name": source_name,
                "data": source_result
            }).execute()
        except Exception as e:
            logger.warning(f"Failed to save source {source_name}: {e}")
    
    # Calculate success metrics
    success_count = sum(1 for s in sources.values() if s.get("success"))
    
    # Update research record
    research_data = {
        "sources": sources,
        "success_count": success_count,
        "total_sources": len(sources),
        "architecture": "gemini-first"  # Track which architecture was used
    }
    
    supabase.table("research_briefs").update({
        "status": "completed",
        "research_data": research_data,
        "brief_content": brief_content,
        "completed_at": "now()"
    }).eq("id", research_id).execute()
    
    logger.info(f"Saved research results: {success_count}/{len(sources)} sources successful")
    
    return {"saved": True, "sources_count": len(sources), "success_count": success_count}
