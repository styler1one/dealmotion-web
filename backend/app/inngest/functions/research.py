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
from app.services.website_content_provider import get_website_content_provider
from app.services.research_enricher import get_research_enricher
from app.services.exa_research_service import get_exa_research_service
from app.i18n.config import DEFAULT_LANGUAGE

logger = logging.getLogger(__name__)

# Initialize services (created once)
gemini_researcher = GeminiResearcher()
claude_researcher = ClaudeResearcher()
kvk_api = KVKApi()
website_content_provider = get_website_content_provider()
research_enricher = get_research_enricher()
exa_research_service = get_exa_research_service()

# Log service availability at module load
if exa_research_service.is_available:
    logger.info("[INNGEST_RESEARCH] Exa Comprehensive Researcher available - 30 parallel search architecture enabled")
else:
    logger.info("[INNGEST_RESEARCH] Exa Comprehensive Researcher not available - using Gemini-first")

if research_enricher.is_available:
    logger.info("[INNGEST_RESEARCH] Research enricher available - enhanced executive discovery enabled")
else:
    logger.info("[INNGEST_RESEARCH] Research enricher not available - using Gemini only")

if website_content_provider.is_neural_available:
    logger.info("[INNGEST_RESEARCH] Neural website content extraction available")
else:
    logger.info("[INNGEST_RESEARCH] Using fallback website scraper")

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
    
    # Step 5: Website content extraction (conditional - if URL provided)
    website_result = None
    if website_url:
        website_result = await step.run("website-scrape", run_website_scrape, website_url, company_name)
    
    # Step 5b: Research enrichment (executives, funding) - runs if enricher is available
    enrichment_result = None
    if research_enricher.is_available:
        enrichment_result = await step.run(
            "research-enrichment",
            run_research_enrichment,
            company_name, website_url, linkedin_url, country
        )
    
    # Step 6: Claude analysis (NO web search - just analyzes Gemini data + enrichment)
    brief_content = await step.run(
        "claude-analysis",
        run_claude_analysis,
        company_name, country, city, gemini_result, kvk_result, website_result, enrichment_result, seller_context, language
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


async def run_website_scrape(website_url: str, company_name: Optional[str] = None) -> dict:
    """Extract content from company website using neural provider or fallback scraper."""
    try:
        result = await website_content_provider.get_website_content(
            website_url=website_url,
            company_name=company_name,
            include_subpages=True,
            max_subpages=5
        )
        return result
    except Exception as e:
        logger.warning(f"Website content extraction failed: {e}")
        return {"success": False, "error": str(e), "source": "website"}


async def run_research_enrichment(
    company_name: str,
    website_url: Optional[str],
    linkedin_url: Optional[str],
    country: Optional[str]
) -> dict:
    """
    Run research enrichment for executives and funding data.
    
    Uses specialized neural search for:
    - Executive discovery with LinkedIn profiles
    - Funding/investor data from quality sources
    - Similar company discovery
    """
    try:
        logger.info(f"[INNGEST_RESEARCH] Starting enrichment for {company_name}")
        
        result = await research_enricher.enrich_company(
            company_name=company_name,
            website_url=website_url,
            linkedin_url=linkedin_url,
            country=country
        )
        
        if result.success:
            # Format as markdown for Claude
            markdown = research_enricher.format_for_claude(result, company_name)
            logger.info(
                f"[INNGEST_RESEARCH] Enrichment complete: "
                f"{len(result.executives)} executives, "
                f"{'funding found' if result.funding else 'no funding'}"
            )
            return {
                "success": True,
                "source": "enricher",
                "executives_count": len(result.executives),
                "has_funding": result.funding is not None,
                "similar_companies_count": len(result.similar_companies),
                "markdown": markdown
            }
        else:
            logger.warning(f"[INNGEST_RESEARCH] Enrichment failed: {result.errors}")
            return {"success": False, "error": str(result.errors), "source": "enricher"}
            
    except Exception as e:
        logger.error(f"[INNGEST_RESEARCH] Enrichment error: {e}")
        return {"success": False, "error": str(e), "source": "enricher"}


async def run_claude_analysis(
    company_name: str,
    country: Optional[str],
    city: Optional[str],
    gemini_result: dict,
    kvk_result: Optional[dict],
    website_result: Optional[dict],
    enrichment_result: Optional[dict],
    seller_context: dict,
    language: str
) -> str:
    """
    Run Claude analysis on collected data.
    
    This step does NOT perform web searches - Claude only analyzes
    the data collected by Gemini + enrichment and generates the final report.
    
    Much cheaper than Claude with web_search tool.
    """
    # Check if Gemini succeeded
    if not gemini_result.get("success"):
        logger.error(f"Cannot analyze - Gemini research failed: {gemini_result.get('error')}")
        return f"# Research Failed: {company_name}\n\nGemini research failed. Unable to generate report."
    
    gemini_data = gemini_result.get("data", "")
    
    if not gemini_data:
        return f"# Research Failed: {company_name}\n\nNo research data available."
    
    # Merge enrichment data into gemini_data if available
    if enrichment_result and enrichment_result.get("success"):
        enrichment_markdown = enrichment_result.get("markdown", "")
        if enrichment_markdown:
            gemini_data = gemini_data + "\n\n" + enrichment_markdown
            logger.info(f"[INNGEST_RESEARCH] Merged enrichment data ({len(enrichment_markdown)} chars)")
    
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


# =============================================================================
# Exa-First Research Function (V2)
# =============================================================================

@inngest_client.create_function(
    fn_id="research-company-v2",
    trigger=TriggerEvent(event="dealmotion/research.requested.v2"),
    retries=2,
    throttle=Throttle(
        limit=5,
        period=timedelta(minutes=1),
        key="event.data.user_id",
    ),
)
async def research_company_v2_fn(ctx, step):
    """
    Exa Comprehensive company research with 30 parallel searches.
    
    Architecture (V2 - Exa Comprehensive):
    1. Update status to 'researching'
    2. Get seller context
    3. Exa Comprehensive Research: 30 parallel searches (PRIMARY)
       - COMPANY (4): identity, business model, products, financials
       - PEOPLE (6): CEO, C-suite, senior leadership, board, changes
       - MARKET (5): news, partnerships, hiring, tech stack, competition
       - DEEP INSIGHTS (7): reviews, events, awards, media, challenges
       - STRATEGIC (6): customers, risks, roadmap, ESG, patents, vendors
       - LOCAL (2): country-specific media and rankings
    4. KVK lookup (if Dutch company)
    5. Claude: Synthesize data and generate 360° report
    6. Save to database
    7. Emit completion event
    
    Fallback: If Exa fails, falls back to Gemini-first (V1)
    """
    # Extract event data
    event_data = ctx.event.data
    research_id = event_data["research_id"]
    company_name = event_data["company_name"]
    country = event_data.get("country")
    city = event_data.get("city")
    linkedin_url = event_data.get("linkedin_url")
    website_url = event_data.get("website_url")
    custom_intel = event_data.get("custom_intel")
    organization_id = event_data.get("organization_id")
    user_id = event_data.get("user_id")
    language = event_data.get("language", DEFAULT_LANGUAGE)
    
    logger.info(f"[V2] Starting Exa-first research for {company_name} (id={research_id})")
    
    # Step 1: Update status to researching
    await step.run(
        "update-status-researching",
        update_research_status,
        research_id, "researching"
    )
    
    # Step 2: Get seller context
    seller_context = await step.run(
        "get-seller-context",
        get_seller_context,
        organization_id,
        user_id
    )
    
    # Add organization_id and custom_intel to seller_context (same as V1)
    if seller_context:
        seller_context["organization_id"] = organization_id
        if custom_intel:
            seller_context["custom_intel"] = custom_intel
    
    # Step 3: Exa Research (PRIMARY)
    exa_result = await step.run(
        "exa-research",
        run_exa_research,
        company_name, country, city, linkedin_url, website_url
    )
    
    # Step 4: KVK lookup (if Dutch company)
    kvk_result = None
    if country and country.lower() in ["netherlands", "nederland", "nl", "the netherlands"]:
        kvk_result = await step.run(
            "kvk-lookup",
            run_kvk_lookup,
            company_name, city
        )
    
    # Step 5: Check if Exa succeeded, fallback if not
    if not exa_result.get("success"):
        logger.warning(f"[V2] Exa research failed, falling back to Gemini-first")
        
        # Fallback to Gemini
        gemini_result = await step.run(
            "gemini-research-fallback",
            run_gemini_research,
            company_name, country, city, linkedin_url, seller_context, language
        )
        
        # Website scraping as fallback
        website_result = None
        if website_url:
            website_result = await step.run(
                "website-scrape-fallback",
                run_website_scrape,
                website_url, company_name
            )
        
        # Claude analysis (full, like V1)
        brief_content = await step.run(
            "claude-analysis-fallback",
            run_claude_analysis,
            company_name, country, city, gemini_result, kvk_result, website_result, None, seller_context, language
        )
        
        architecture = "gemini-first-fallback"
    else:
        # Step 6: Claude Synthesis (smaller role - structured input)
        brief_content = await step.run(
            "claude-synthesis",
            run_claude_synthesis,
            company_name, country, city, exa_result, kvk_result, seller_context, language
        )
        
        architecture = "exa-first"
    
    # Step 7: Save results to database
    await step.run(
        "save-results",
        save_research_results_v2,
        research_id, exa_result, kvk_result, brief_content, architecture
    )
    
    # Step 8: Get prospect_id for Autopilot detection
    prospect_id = await step.run(
        "get-prospect-id",
        get_research_prospect_id,
        research_id
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
                "prospect_id": prospect_id,
                "architecture": architecture,
                "success": True
            }
        )
    )
    
    logger.info(f"[V2] Research completed for {company_name} using {architecture}")
    
    return {
        "research_id": research_id,
        "status": "completed",
        "company_name": company_name,
        "architecture": architecture
    }


async def run_exa_research(
    company_name: str,
    country: Optional[str],
    city: Optional[str],
    linkedin_url: Optional[str],
    website_url: Optional[str]
) -> dict:
    """
    Run Exa Comprehensive Research with 30 parallel searches.
    
    Uses ExaComprehensiveResearcher which mirrors the Gemini-first architecture
    but uses Exa's APIs (Search, Contents, People category, domain filters).
    
    Returns comprehensive markdown data for Claude synthesis.
    """
    if not exa_research_service.is_available:
        return {"success": False, "error": "Exa Research Service not available"}
    
    try:
        logger.info(f"[V2] Starting Exa comprehensive research for {company_name}")
        
        result = await exa_research_service.research_company(
            company_name=company_name,
            country=country,
            city=city,
            linkedin_url=linkedin_url,
            website_url=website_url
        )
        
        if result.success:
            # Get markdown output for Claude synthesis
            markdown = exa_research_service.format_for_claude(result)
            
            logger.info(
                f"[V2] Exa comprehensive research complete: "
                f"{result.topics_completed}/{result.topics_completed + result.topics_failed} topics, "
                f"{result.total_results} total results, "
                f"{result.execution_time_seconds:.1f}s"
            )
            
            return {
                "success": True,
                "source": "exa-comprehensive",
                "markdown": markdown,
                "stats": {
                    "topics_completed": result.topics_completed,
                    "topics_failed": result.topics_failed,
                    "total_results": result.total_results,
                    "execution_time_seconds": result.execution_time_seconds
                }
            }
        else:
            error_msg = ", ".join(result.errors) if result.errors else "Unknown error"
            logger.warning(f"[V2] Exa comprehensive research failed: {error_msg}")
            return {"success": False, "error": error_msg, "source": "exa-comprehensive"}
            
    except Exception as e:
        logger.error(f"[V2] Exa comprehensive research error: {e}")
        return {"success": False, "error": str(e), "source": "exa-comprehensive"}


async def run_claude_synthesis(
    company_name: str,
    country: Optional[str],
    city: Optional[str],
    exa_result: dict,
    kvk_result: Optional[dict],
    seller_context: dict,
    language: str
) -> str:
    """
    Claude synthesis of Exa research data.
    
    DIRECT API CALL - No nested prompts!
    
    Unlike V1 which passes data through analyze_research_data() (adding another
    350-line template on top), V2 calls Claude directly with ONE clean prompt.
    This prevents the "lost in the middle" effect from nested templates.
    """
    from datetime import datetime
    from anthropic import AsyncAnthropic
    import os
    
    exa_markdown = exa_result.get("markdown", "")
    
    if not exa_markdown:
        return f"# Research Failed: {company_name}\n\nNo research data available."
    
    # Build KVK section
    kvk_section = ""
    if kvk_result and kvk_result.get("success"):
        kvk = kvk_result.get("data", {})
        kvk_section = f"""

## OFFICIAL REGISTRATION DATA (Dutch Chamber of Commerce)

| Field | Value |
|-------|-------|
| **KVK Number** | {kvk.get('kvk_number', 'Unknown')} |
| **Legal Form** | {kvk.get('legal_form', 'Unknown')} |
| **Registration Date** | {kvk.get('registration_date', 'Unknown')} |
| **Address** | {kvk.get('address', 'Unknown')} |
"""
    
    # Build seller context section (detailed, like V1)
    seller_section = ""
    if seller_context and seller_context.get("has_context"):
        # Products with benefits
        products_list = seller_context.get("products", [])
        if products_list:
            products_str = ", ".join([
                p.get("name", "") for p in products_list if p.get("name")
            ]) or "not specified"
            all_benefits = []
            for p in products_list[:3]:
                all_benefits.extend(p.get("benefits", [])[:2])
            benefits_str = ", ".join(all_benefits[:5]) if all_benefits else "not specified"
        else:
            products_str = "not specified"
            benefits_str = "not specified"
        
        values = ", ".join(seller_context.get("value_propositions", [])[:3]) or "not specified"
        diffs = ", ".join(seller_context.get("differentiators", [])[:3]) or "not specified"
        industries = ", ".join(seller_context.get("target_industries", [])[:3]) or "any"
        company_sizes = ", ".join(seller_context.get("target_company_sizes", [])[:3]) or "any size"
        pain_points = ", ".join(seller_context.get("ideal_pain_points", [])[:5]) or "not specified"
        decision_makers = ", ".join(seller_context.get("target_decision_makers", [])[:5]) or "not specified"
        
        seller_section = f"""
## SELLER CONTEXT

Use this to assess FIT and personalize the analysis.

**Seller**: {seller_context.get('company_name', 'Unknown')}

| What We Sell | Details |
|--------------|---------|
| Products | {products_str} |
| Key Benefits | {benefits_str} |
| Value Props | {values} |
| Differentiators | {diffs} |

| Ideal Customer Profile | Details |
|------------------------|---------|
| Target Industries | {industries} |
| Company Sizes | {company_sizes} |
| Pain Points We Solve | {pain_points} |
| Typical Decision Makers | {decision_makers} |

**YOUR MISSION**:
1. Assess if this prospect FITS our ICP
2. Find evidence of the pain points we solve
3. Identify decision makers matching our typical buyers
4. Suggest use cases based on their situation + our benefits
"""
    
    current_date = datetime.now().strftime("%d %B %Y")
    current_year = datetime.now().year
    lang_instruction = "Generate the report in Dutch." if language == "nl" else "Generate the report in English."
    
    # Location context
    location_str = ""
    if city and country:
        location_str = f"**Location**: {city}, {country}"
    elif country:
        location_str = f"**Country**: {country}"
    
    # Single, clean prompt - NO nesting!
    synthesis_prompt = f"""You are an elite B2B sales intelligence analyst. Your analysis saves sales professionals DAYS of work.

## CRITICAL CONTEXT

**TODAY'S DATE**: {current_date}
**CURRENT YEAR**: {current_year}
**TARGET COMPANY**: {company_name}
{location_str}

{seller_section}

## RESEARCH DATA TO ANALYZE

The following data was collected via comprehensive web research (Exa AI - 30+ parallel searches):

{exa_markdown}

{kvk_section}

## YOUR TASK

Analyze ALL the research data above and generate a comprehensive 360° PROSPECT INTELLIGENCE REPORT.

{lang_instruction}

## OUTPUT FORMAT REQUIREMENTS

**CRITICAL**: Use standard Markdown headers (# ## ###) - NOT decorative characters.
- Use `#` for main title
- Use `##` for section headers (Section 1, Section 2, etc.)
- Use `###` for subsection headers
- Use tables for structured data
- Use bullet points for lists

Generate the report in this EXACT structure:

# 360° Prospect Intelligence Report: {company_name}

**Research Date**: {current_date}

---

## Section 1: Executive Summary

### 1.1 In One Sentence
[A sharp, insight-packed sentence: WHO they are + WHAT makes them interesting + WHY timing might be right]

### 1.2 At a Glance

| Dimension | Assessment | Evidence |
|-----------|------------|----------|
| **Opportunity Fit** | 🟢 High / 🟡 Medium / 🔴 Low | [One-line reasoning] |
| **Timing Signal** | 🟢 Act Now / 🟡 Nurture / 🔴 Wait | [Trigger or reason] |
| **Company Stage** | 🚀 Startup / 📈 Scale-up / 🏢 SMB / 🏛️ Enterprise | [Evidence] |
| **Financial Health** | 🟢 Strong / 🟡 Stable / 🔴 Challenged / ⚪ Unknown | [Signals] |
| **Industry Match** | 🟢 Core Target / 🟡 Adjacent / 🔴 Outside Focus | [Based on seller context] |
| **Decision Complexity** | Simple / Medium / Complex | [Org size, stakeholders] |
| **Primary Risk** | [Single biggest obstacle] | |

### 1.3 Why This Company Matters
[2-3 sentences connecting their situation to what the seller offers]

### 1.4 Quick Actions (Top 3)

| Priority | Action | Why Now | Contact |
|----------|--------|---------|---------|
| 1 | [Specific action: Call/Email/Connect with X] | [Trigger that creates urgency] | [Name + best contact method] |
| 2 | [Second priority action] | [Supporting reason] | [Name if applicable] |
| 3 | [Third priority action] | [Context for action] | [Resource/preparation needed] |

**Recommended Opening**: [One compelling sentence to start the conversation based on their current situation]

---

## Section 2: Company Deep Dive

### 2.1 Company Identity

| Element | Details | Source |
|---------|---------|--------|
| **Legal Name** | [Name] | |
| **Trading Name** | [If different] | |
| **Industry** | [Primary - Sub-sector] | |
| **Founded** | [Year] | |
| **Headquarters** | [City, Country] | |
| **Other Locations** | [List] | |
| **Website** | [URL] | |
| **LinkedIn** | [URL] | |

### 2.2 Corporate Structure

| Element | Details |
|---------|---------|
| **Ownership Type** | [Private / Public / PE / VC / Family] |
| **Parent Company** | [If applicable] |
| **Subsidiaries** | [If any] |
| **Key Investors** | [If known] |

### 2.3 Company Size & Scale

| Metric | Value | Trend | Source |
|--------|-------|-------|--------|
| **Employees** | [Number] | [up/stable/down] | |
| **Revenue** | [Amount or range] | | |
| **Funding Raised** | [Total] | | |

### 2.4 Business Model

**What They Do**: [3-4 sentences explaining core business]

**How They Make Money**:

| Revenue Stream | Description | Importance |
|----------------|-------------|------------|
| [Stream 1] | [Details] | Primary/Secondary |

**Their Customers**:

| Aspect | Details |
|--------|---------|
| **Business Model** | B2B / B2C / B2B2C / SaaS / Services |
| **Customer Segment** | Enterprise / Mid-market / SMB |
| **Key Verticals** | [Industries] |
| **Named Customers** | [If found] |

---

## Section 3: People & Power (Decision Making Unit)

### 3.1 Executive Leadership (C-Suite)

| Name | Title | LinkedIn | Background | Notes |
|------|-------|----------|------------|-------|
| [Name] | CEO/MD | [Full URL] | [Background] | [Founder? New?] |
| [Name] | CFO | [Full URL] | | Budget authority |
| [Name] | CTO/CIO | [Full URL] | | Tech decisions |
| [Name] | COO | [Full URL] | | Operations |
| [Name] | CMO | [Full URL] | | Marketing |

### 3.2 Senior Leadership (VPs, Directors)

| Name | Title | LinkedIn | Potential Relevance |
|------|-------|----------|---------------------|
| [Name] | [Title] | [URL] | [Why relevant] |

### 3.3 Board of Directors

| Name | Role | Affiliation |
|------|------|-------------|
| [Name] | [Role] | [Company/Fund] |

### 3.4 Decision-Making Dynamics

| Aspect | Assessment | Evidence |
|--------|------------|----------|
| **Decision Culture** | Top-down / Consensus / Founder-led | [Signals] |
| **Budget Authority** | [Who controls spend] | |
| **Likely Champions** | [Roles aligned with seller's value] | |
| **Potential Blockers** | [Roles that might resist] | |

### 3.5 Recent Leadership Changes

| Date | Change | Name | Implication |
|------|--------|------|-------------|
| [Date] | [New/Departure] | [Name] | [What it means] |

**Coverage Note**: [State if leadership data is limited]

---

## Section 4: What's Happening Now (Triggers & Signals)

### 4.1 Recent News (Last 90 Days)

| Date | Headline | Type | Source |
|------|----------|------|--------|
| [Date] | [Title] | [Funding/Growth/People/Product/Partnership/Challenge] | [Publication] |

### 4.2 Funding History

| Date | Round | Amount | Investors |
|------|-------|--------|-----------|
| [Date] | [Series] | [Amount] | [Names] |

### 4.3 Hiring Signals

| Department | Roles | What It Signals |
|------------|-------|-----------------|
| [Dept] | [Count] | [Meaning] |

**Hiring Velocity**: Aggressive / Steady / Slowing / Freeze

### 4.4 Strategic Initiatives
- [Initiative 1]
- [Initiative 2]

### 4.5 Interpretation
[2-3 sentences: What's really going on? What are their priorities?]

---

## Section 5: Market & Competitive Position

### 5.1 Market Position

| Aspect | Assessment |
|--------|------------|
| **Market Role** | Leader / Challenger / Niche / Newcomer |
| **Trajectory** | Growing / Stable / Declining |

### 5.2 Competitive Landscape

| Competitor | Positioning | vs. This Company |
|------------|-------------|------------------|
| [Name] | [Position] | [Comparison] |

### 5.3 Technology Stack

| Category | Tools/Vendors |
|----------|---------------|
| CRM | [Tools] |
| ERP | [Tools] |
| Cloud | [AWS/Azure/GCP] |

---

## Section 6: Commercial Opportunity Assessment

### 6.1 BANT Qualification

| Signal | Evidence | Score | Confidence |
|--------|----------|-------|------------|
| **Budget** | [Signals] | [Green/Yellow/Red/Unknown] | High/Med/Low |
| **Authority** | [Decision makers found] | [Green/Yellow/Red/Unknown] | |
| **Need** | [Pain points identified] | [Green/Yellow/Red/Unknown] | |
| **Timeline** | [Urgency signals] | [Green/Yellow/Red/Unknown] | |

**BANT Summary**: [X/4 strong signals] - [Interpretation]

### 6.2 Potential Pain Points

| Pain Point | Evidence | Connection to Seller |
|------------|----------|---------------------|
| [Pain 1] | [Signal] | [How seller helps] |

### 6.3 Opportunity Triggers

| Trigger | Type | Timing |
|---------|------|--------|
| [Trigger] | [Category] | [Recent/Imminent] |

### 6.4 Relevant Use Cases

| Use Case | Their Situation | How Seller Helps |
|----------|-----------------|------------------|
| [Case 1] | [Context] | [Value] |

---

## Section 7: Strategic Approach

### 7.1 Priority Targets

| Priority | Name | Role | Entry Angle |
|----------|------|------|-------------|
| 1 | [Name] | [Title] | [Topic to lead with] |
| 2 | [Name] | [Title] | [Alternative angle] |

### 7.2 Entry Strategy

| Aspect | Recommendation |
|--------|----------------|
| **Primary Entry Point** | [Role/Department] |
| **Why This Entry** | [Reasoning] |
| **Avoid Starting With** | [Who NOT to approach] |

### 7.3 Key Topics to Explore
1. [Topic aligned with trigger/news]
2. [Topic aligned with pain point]
3. [Topic that differentiates seller]

### 7.4 Validation Questions

| Category | Question | Why Ask |
|----------|----------|---------|
| **Situation** | [Question] | [What you're validating] |
| **Problem** | [Question] | |
| **Priority** | [Question] | |

---

## Section 8: Risks, Obstacles & Watchouts

### 8.1 Potential Obstacles

| Obstacle | Likelihood | Mitigation |
|----------|------------|------------|
| [Obstacle] | High/Med/Low | [Strategy] |

### 8.2 Things to Avoid

| Topic/Approach | Why Avoid | Instead Do |
|----------------|-----------|------------|
| [Topic] | [Reason] | [Alternative] |

### 8.3 Information Gaps (Must Verify)
- [ ] [Gap 1]
- [ ] [Gap 2]

---

## Section 9: Research Quality & Metadata

### 9.1 Source Coverage

| Source | Status | Quality |
|--------|--------|---------|
| Company Website | [Yes/No] | Rich/Basic/Poor |
| LinkedIn Company | [Yes/No] | |
| LinkedIn People | [Yes/No] | [X found] |
| Recent News | [Yes/No] | |
| Job Postings | [Yes/No] | |

### 9.2 Research Confidence

| Section | Confidence |
|---------|------------|
| Company Basics | [High/Medium/Low] |
| Leadership Mapping | [High/Medium/Low] |
| Recent Developments | [High/Medium/Low] |
| Commercial Fit | [High/Medium/Low] |

**Overall Confidence**: High / Medium / Low

### 9.3 Key Recommendations
1. **Priority Contact**: [Name] - [LinkedIn URL]
2. **Primary Value Prop**: [What to lead with]
3. **Timing Verdict**: [Act Now / Nurture / Wait]
4. **Next Steps**: [Recommended actions]

---

*Report generated: {current_date}*

## QUALITY RULES

1. Include FULL LinkedIn URLs for every person found in the research
2. Be factual - "Not found" is better than speculation
3. Use the seller context to assess fit (if provided)
4. Focus on commercially actionable intelligence
5. Use standard Markdown (# ## ###) - NO decorative characters like ═══ or ───
6. PRESERVE all data from the research - do not skip or summarize away details
"""

    try:
        # Direct Claude API call - NO nested prompts!
        api_key = os.getenv("ANTHROPIC_API_KEY")
        if not api_key:
            raise ValueError("ANTHROPIC_API_KEY not set")
        
        client = AsyncAnthropic(api_key=api_key)
        
        logger.info(f"[V2] Starting Claude synthesis for {company_name} (direct API call)")
        
        response = await client.messages.create(
            model="claude-sonnet-4-20250514",
            max_tokens=12000,  # Increased from 8192 for longer reports
            temperature=0.2,
            messages=[{
                "role": "user",
                "content": synthesis_prompt
            }]
        )
        
        result_text = ""
        for block in response.content:
            if hasattr(block, 'text'):
                result_text += block.text
        
        usage = response.usage
        logger.info(
            f"[V2] Claude synthesis completed for {company_name}. "
            f"Tokens - Input: {usage.input_tokens}, Output: {usage.output_tokens}"
        )
        
        return result_text
        
    except Exception as e:
        logger.error(f"[V2] Claude synthesis error: {e}")
        return f"# Research Brief: {company_name}\n\n**Note**: Synthesis failed.\n\n{exa_markdown}"


async def save_research_results_v2(
    research_id: str,
    exa_result: dict,
    kvk_result: Optional[dict],
    brief_content: str,
    architecture: str
) -> dict:
    """Save V2 research results to database."""
    sources = {
        "exa_research": exa_result,
    }
    
    if kvk_result:
        sources["kvk"] = kvk_result
    
    # Map source names to allowed source_type values (same as V1)
    source_type_map = {
        "exa_research": "web",  # Exa is web-based research
        "kvk": "api",           # KVK is an API source
    }
    
    # Save individual sources
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
            logger.warning(f"[V2] Failed to save source {source_name}: {e}")
    
    # Calculate metrics
    success_count = sum(1 for s in sources.values() if s and s.get("success"))
    
    # Get Exa stats if available
    exa_stats = exa_result.get("stats", {}) if exa_result else {}
    
    research_data = {
        "sources": sources,
        "success_count": success_count,
        "total_sources": len(sources),
        "architecture": architecture,
        "exa_stats": exa_stats
    }
    
    supabase.table("research_briefs").update({
        "status": "completed",
        "research_data": research_data,
        "brief_content": brief_content,
        "completed_at": "now()"
    }).eq("id", research_id).execute()
    
    logger.info(f"[V2] Saved research results: architecture={architecture}")
    
    return {"saved": True, "architecture": architecture}
