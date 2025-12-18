"""
Research orchestrator - Gemini-first architecture for cost-optimized 360° prospect intelligence.

ARCHITECTURE:
1. Gemini (cheap): Does ALL web searching via Google Search
2. Research Enricher: Specialized executive/funding discovery (parallel)
3. KVK/Website: Supplementary data sources
4. Claude (expensive): ONLY analyzes data, generates final report

COST COMPARISON:
- Old (Claude web_search): ~$0.50-1.00 per research
- New (Gemini-first): ~$0.15-0.20 per research
- With Enrichment: ~$0.18-0.25 per research (higher quality executives)
- Savings: ~75-85%

ENRICHMENT BENEFITS:
- ~90%+ LinkedIn success rate for executives (vs ~60-70% with Google Search)
- Structured funding data from quality sources
- Similar company discovery for competitive intelligence
"""
import asyncio
import logging
from datetime import datetime
from typing import Dict, Any, Optional, List
from supabase import Client
from .claude_researcher import ClaudeResearcher
from .gemini_researcher import GeminiResearcher
from .kvk_api import KVKApi
from .website_scraper import get_website_scraper
from .research_enricher import get_research_enricher, ResearchEnricher
from app.database import get_supabase_service
from app.i18n.config import DEFAULT_LANGUAGE
from app.utils.timeout import with_timeout, AITimeoutError

logger = logging.getLogger(__name__)

# Timeout settings for research operations (in seconds)
GEMINI_TIMEOUT = 120  # Gemini comprehensive research
CLAUDE_TIMEOUT = 90   # Claude analysis
SUPPLEMENTARY_TIMEOUT = 30  # KVK, website scraping
TOTAL_TIMEOUT = 240   # Total research timeout


class ResearchOrchestrator:
    """
    Orchestrate research with Gemini-first architecture + specialized enrichment.
    
    Flow:
    1. Gemini searches for ALL company data (cheap, broad coverage)
    2. Research Enricher finds executives with LinkedIn profiles (parallel, high accuracy)
    3. KVK/Website scraper add supplementary data
    4. Claude analyzes everything and generates report (one call, no web search)
    
    Enrichment benefits:
    - ~90%+ LinkedIn success rate for executives
    - Structured funding/investor data
    - Similar company discovery for competitive intelligence
    """
    
    def __init__(self):
        """Initialize all research services."""
        self.claude = ClaudeResearcher()
        self.gemini = GeminiResearcher()
        self.kvk = KVKApi()
        self.website_scraper = get_website_scraper()
        self.enricher: ResearchEnricher = get_research_enricher()
        
        # Initialize Supabase using centralized module
        self.supabase: Client = get_supabase_service()
        
        # Log enricher availability
        if self.enricher.is_available:
            logger.info("[RESEARCH_ORCHESTRATOR] Research enricher available - enhanced executive discovery enabled")
        else:
            logger.info("[RESEARCH_ORCHESTRATOR] Research enricher not available - using Gemini only")
    
    async def research_company(
        self,
        company_name: str,
        country: Optional[str] = None,
        city: Optional[str] = None,
        linkedin_url: Optional[str] = None,
        website_url: Optional[str] = None,
        organization_id: Optional[str] = None,
        user_id: Optional[str] = None,
        language: str = DEFAULT_LANGUAGE
    ) -> Dict[str, Any]:
        """
        Research company using Gemini-first architecture for 360° intelligence.
        
        Architecture:
        1. Gemini: Comprehensive web search (cheap, ~$0.02)
        2. KVK: Official Dutch company data (NL only)
        3. Website: Direct content scraping
        4. KB: Relevant knowledge base chunks
        5. Claude: Analysis and report generation (no web search, ~$0.12)
        
        Total cost: ~$0.15-0.20 per research (was ~$0.50-1.00)
        
        Args:
            company_name: Name of the company
            country: Optional country
            city: Optional city
            linkedin_url: Optional LinkedIn URL
            website_url: Optional website URL
            organization_id: Organization ID for context
            user_id: User ID for sales profile
            language: Output language code
            
        Returns:
            Dictionary with research data and unified brief
        """
        current_date = datetime.now().strftime("%d %B %Y")
        logger.info(f"Starting Gemini-first 360° research for {company_name} on {current_date}")
        
        # Get seller context for personalized research
        seller_context = await self._get_seller_context(organization_id, user_id)
        
        # Add organization_id to seller context for caching
        if seller_context and organization_id:
            seller_context["organization_id"] = organization_id
        
        # ═══════════════════════════════════════════════════════════════════
        # PHASE 1: Data Collection (Parallel)
        # ═══════════════════════════════════════════════════════════════════
        
        # Build task list
        tasks = []
        task_names = []
        
        # Primary: Gemini comprehensive research (REQUIRED)
        tasks.append(self.gemini.search_company(
            company_name=company_name,
            country=country,
            city=city,
            linkedin_url=linkedin_url,
            seller_context=seller_context,
            language=language
        ))
        task_names.append("gemini")
        
        # Enrichment: Specialized executive/funding discovery (parallel)
        # This runs alongside Gemini to enhance leadership coverage
        if self.enricher.is_available:
            tasks.append(self.enricher.enrich_company(
                company_name=company_name,
                website_url=website_url,
                linkedin_url=linkedin_url,
                country=country
            ))
            task_names.append("enricher")
            logger.info(f"[RESEARCH_ORCHESTRATOR] Enrichment enabled for {company_name}")
        
        # Supplementary: KVK for Dutch companies
        if self.kvk.is_dutch_company(country):
            tasks.append(self.kvk.search_company(company_name, city))
            task_names.append("kvk")
        
        # Supplementary: Website scraper if URL provided
        if website_url:
            tasks.append(self.website_scraper.scrape_website(website_url))
            task_names.append("website")
        
        # Execute all data collection in parallel
        try:
            results = await with_timeout(
                asyncio.gather(*tasks, return_exceptions=True),
                timeout_seconds=TOTAL_TIMEOUT,
                operation_name="Data collection"
            )
        except AITimeoutError:
            logger.error(f"Data collection timed out for {company_name}")
            results = [asyncio.TimeoutError("Timed out")] * len(tasks)
        
        # Process results
        sources = {}
        gemini_data = None
        kvk_data = None
        website_data = None
        enrichment_data = None
        
        for name, result in zip(task_names, results):
            if isinstance(result, Exception):
                sources[name] = {"success": False, "error": str(result)}
                logger.warning(f"Source {name} failed: {result}")
            else:
                # Handle enricher result (it's a dataclass, not a dict)
                if name == "enricher":
                    from .research_enricher import EnrichmentResult
                    if isinstance(result, EnrichmentResult) and result.success:
                        enrichment_data = result
                        sources[name] = {
                            "success": True,
                            "executives_found": len(result.executives),
                            "funding_found": result.funding is not None,
                            "similar_companies": len(result.similar_companies)
                        }
                        logger.info(
                            f"Enrichment: {len(result.executives)} executives, "
                            f"{'funding found' if result.funding else 'no funding'}"
                        )
                    else:
                        sources[name] = {"success": False, "error": "No enrichment data"}
                else:
                    sources[name] = result
                    if name == "gemini" and result.get("success"):
                        gemini_data = result.get("data", "")
                        # Log Gemini token stats
                        if result.get("token_stats"):
                            stats = result["token_stats"]
                            logger.info(
                                f"Gemini research: {stats.get('input_tokens', 'N/A')} in, "
                                f"{stats.get('output_tokens', 'N/A')} out"
                            )
                    elif name == "kvk" and result.get("success"):
                        kvk_data = result
                    elif name == "website" and result.get("success"):
                        website_data = result
        
        # Check if Gemini succeeded (required)
        if not gemini_data:
            logger.error(f"Gemini research failed for {company_name} - cannot proceed")
            return {
                "sources": sources,
                "success_count": 0,
                "total_sources": len(tasks),
                "research_date": current_date,
                "brief": f"# Research Failed: {company_name}\n\n**Date**: {current_date}\n\nGemini research failed. Unable to generate report.",
                "error": "Primary research source (Gemini) failed"
            }
        
        # Get relevant KB chunks
        kb_chunks = []
        if organization_id:
            kb_chunks = await self._get_relevant_kb_chunks(
                company_name, organization_id, seller_context
            )
            if kb_chunks:
                sources["knowledge_base"] = {"success": True, "data": kb_chunks}
        
        # ═══════════════════════════════════════════════════════════════════
        # PHASE 1.5: Merge Enrichment Data into Gemini Data
        # ═══════════════════════════════════════════════════════════════════
        
        # If enrichment data available, append it to Gemini data
        # This gives Claude high-confidence executive/funding data
        if enrichment_data:
            enrichment_markdown = self.enricher.format_for_claude(enrichment_data, company_name)
            if enrichment_markdown:
                gemini_data = gemini_data + "\n\n" + enrichment_markdown
                logger.info(f"Merged enrichment data into research ({len(enrichment_markdown)} chars)")
        
        # ═══════════════════════════════════════════════════════════════════
        # PHASE 2: Claude Analysis (Single Call, No Web Search)
        # ═══════════════════════════════════════════════════════════════════
        
        logger.info(f"Phase 2: Claude analysis for {company_name}")
        
        try:
            analysis_result = await with_timeout(
                self.claude.analyze_research_data(
                    company_name=company_name,
                    gemini_data=gemini_data,
                    country=country,
                    city=city,
                    kvk_data=kvk_data,
                    website_data=website_data,
                    kb_chunks=kb_chunks,
                    seller_context=seller_context,
                    language=language
                ),
                timeout_seconds=CLAUDE_TIMEOUT,
                operation_name="Claude analysis"
            )
        except AITimeoutError:
            logger.error(f"Claude analysis timed out for {company_name}")
            analysis_result = {
                "success": False,
                "error": "Analysis timed out",
                "data": ""
            }
        
        sources["claude_analysis"] = analysis_result
        
        # Get the final brief
        if analysis_result.get("success"):
            brief = analysis_result.get("data", "")
            # Log Claude token stats
            if analysis_result.get("token_stats"):
                stats = analysis_result["token_stats"]
                logger.info(
                    f"Claude analysis: {stats.get('input_tokens', 0)} in, "
                    f"{stats.get('output_tokens', 0)} out"
                )
        else:
            # Fallback: Return Gemini data directly (not ideal but better than nothing)
            logger.warning(f"Claude analysis failed, falling back to Gemini data")
            brief = f"# Research Brief: {company_name}\n\n**Date**: {current_date}\n\n**Note**: Analysis failed, showing raw research data.\n\n{gemini_data}"
        
        # Calculate success count
        success_count = sum(1 for s in sources.values() if s.get("success"))
        
        logger.info(
            f"Gemini-first research completed for {company_name}: "
            f"{success_count}/{len(sources)} sources successful"
        )
        
        return {
            "sources": sources,
            "success_count": success_count,
            "total_sources": len(sources),
            "research_date": current_date,
            "brief": brief
        }
    
    async def _get_seller_context(
        self,
        organization_id: Optional[str],
        user_id: Optional[str]
    ) -> Dict[str, Any]:
        """
        Get seller context for personalized research.
        
        Includes:
        - Products with benefits
        - ICP (pain points, decision makers, company sizes)
        - Differentiators and value propositions
        """
        context = {
            "has_context": False,
            "company_name": None,
            "products": [],
            "value_propositions": [],
            "differentiators": [],
            "target_industries": [],
            "target_company_sizes": [],
            "ideal_pain_points": [],
            "target_decision_makers": [],
        }
        
        if not organization_id:
            return context
        
        try:
            # Get company profile
            company_response = self.supabase.table("company_profiles")\
                .select("*")\
                .eq("organization_id", organization_id)\
                .limit(1)\
                .execute()
            
            if company_response.data:
                company = company_response.data[0]
                context["has_context"] = True
                context["company_name"] = company.get("company_name")
                
                # Products with benefits
                products = company.get("products", []) or []
                context["products"] = []
                for p in products[:5]:
                    if isinstance(p, dict) and p.get("name"):
                        context["products"].append({
                            "name": p.get("name"),
                            "benefits": p.get("benefits", [])[:3] if p.get("benefits") else []
                        })
                
                # Value propositions and differentiators
                context["value_propositions"] = (company.get("core_value_props", []) or [])[:5]
                context["differentiators"] = (company.get("differentiators", []) or [])[:3]
                
                # ICP details
                icp = company.get("ideal_customer_profile", {}) or {}
                context["target_industries"] = (icp.get("industries", []) or [])[:5]
                context["target_company_sizes"] = (icp.get("company_sizes", []) or [])[:3]
                context["ideal_pain_points"] = (icp.get("pain_points", []) or [])[:5]
                context["target_decision_makers"] = (icp.get("decision_makers", []) or [])[:5]
                
                logger.info(
                    f"Seller context loaded: {context['company_name']}, "
                    f"products={len(context['products'])}, "
                    f"pain_points={len(context['ideal_pain_points'])}"
                )
            
            # Fallback: Get company name from sales profile
            if user_id and not context.get("company_name"):
                sales_response = self.supabase.table("sales_profiles")\
                    .select("role")\
                    .eq("user_id", user_id)\
                    .limit(1)\
                    .execute()
                
                if sales_response.data:
                    role = sales_response.data[0].get("role", "") or ""
                    if " at " in role:
                        context["company_name"] = role.split(" at ")[-1].strip()
                        context["has_context"] = True
            
        except Exception as e:
            logger.warning(f"Could not load seller context: {e}")
        
        return context
    
    async def _get_relevant_kb_chunks(
        self,
        prospect_company: str,
        organization_id: str,
        seller_context: Dict[str, Any],
        max_chunks: int = 3
    ) -> List[Dict[str, str]]:
        """
        Get relevant KB chunks (case studies, product info) for the prospect.
        """
        try:
            from app.services.embeddings import EmbeddingsService
            from app.services.vector_store import VectorStore
            
            embeddings = EmbeddingsService()
            vector_store = VectorStore()
            
            # Build query based on prospect and what we sell
            products = ", ".join([
                p.get("name", "") for p in seller_context.get("products", [])[:3]
            ])
            query = f"{prospect_company} case study success {products}"
            
            query_embedding = await embeddings.embed_text(query)
            
            matches = vector_store.query_vectors(
                query_vector=query_embedding,
                filter={"organization_id": organization_id},
                top_k=max_chunks,
                include_metadata=True
            )
            
            chunks = []
            for match in matches:
                if match.score > 0.5:
                    chunks.append({
                        "text": match.metadata.get("text", "")[:500],
                        "source": match.metadata.get("filename", "Document"),
                        "score": match.score
                    })
            
            logger.info(f"Found {len(chunks)} relevant KB chunks for {prospect_company}")
            return chunks
            
        except Exception as e:
            logger.warning(f"Error getting KB chunks: {e}")
            return []
    
    # Legacy method for backward compatibility with Inngest functions
    async def _generate_unified_brief(
        self,
        sources: Dict[str, Any],
        company_name: str,
        country: Optional[str],
        city: Optional[str],
        seller_context: Optional[Dict[str, Any]] = None,
        kb_chunks: Optional[List[Dict[str, str]]] = None,
        language: str = DEFAULT_LANGUAGE
    ) -> str:
        """
        Legacy method - generates brief from collected sources.
        
        This method is kept for backward compatibility with Inngest functions.
        New code should use research_company which handles everything.
        """
        current_date = datetime.now().strftime("%d %B %Y")
        
        # Get Gemini data
        gemini_data = ""
        if sources.get("gemini", {}).get("success"):
            gemini_data = sources["gemini"].get("data", "")
        
        # Get supplementary data
        kvk_data = sources.get("kvk") if sources.get("kvk", {}).get("success") else None
        website_data = sources.get("website") if sources.get("website", {}).get("success") else None
        
        if not gemini_data:
            return f"# Research Failed: {company_name}\n\n**Date**: {current_date}\n\nNo research data available."
        
        # Use Claude to analyze
        try:
            result = await self.claude.analyze_research_data(
                company_name=company_name,
                gemini_data=gemini_data,
                country=country,
                city=city,
                kvk_data=kvk_data,
                website_data=website_data,
                kb_chunks=kb_chunks,
                seller_context=seller_context,
                language=language
            )
            
            if result.get("success"):
                return result.get("data", "")
            else:
                return f"# Research Brief: {company_name}\n\n**Date**: {current_date}\n\n{gemini_data}"
                
        except Exception as e:
            logger.error(f"Error generating unified brief: {e}")
            return f"# Research Brief: {company_name}\n\n**Date**: {current_date}\n\n{gemini_data}"
    
    def clear_caches(self, organization_id: Optional[str] = None) -> None:
        """
        Clear research caches.
        
        Call this when organization's company profile is updated.
        """
        self.claude.clear_seller_cache(organization_id)
        logger.info(f"Cleared research caches for org: {organization_id or 'all'}")
