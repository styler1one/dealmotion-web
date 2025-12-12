"""
Research orchestrator - coordinates multiple research sources for 360° prospect intelligence.

Enhanced with full context awareness:
- Sales profile context (who is selling)
- Company profile context (what are we selling)
- Knowledge Base integration (case studies, product info)
- Prompt caching for cost optimization
- Current date awareness for accurate news search
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
from app.database import get_supabase_service
from app.i18n.utils import get_language_instruction
from app.i18n.config import DEFAULT_LANGUAGE
from app.utils.timeout import with_timeout, AITimeoutError

logger = logging.getLogger(__name__)

# Timeout settings for research operations (in seconds)
RESEARCH_TASK_TIMEOUT = 90  # Individual AI task timeout (increased for comprehensive research)
RESEARCH_TOTAL_TIMEOUT = 240  # Total research timeout (4 minutes for thorough research)


class ResearchOrchestrator:
    """Orchestrate research from multiple sources with full context."""
    
    def __init__(self):
        """Initialize all research services."""
        self.claude = ClaudeResearcher()
        self.gemini = GeminiResearcher()
        self.kvk = KVKApi()
        self.website_scraper = get_website_scraper()
        
        # Initialize Supabase using centralized module
        self.supabase: Client = get_supabase_service()
    
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
        Research company using multiple sources in parallel for 360° intelligence.
        
        Sources:
        - Claude: Comprehensive 360° prospect research (with caching)
        - Gemini: Real-time news and market signals
        - KVK: Official Dutch company data (NL only)
        - Website Scraper: Direct website content
        - Knowledge Base: Relevant case studies (for merge)
        
        Args:
            company_name: Name of the company
            country: Optional country
            city: Optional city
            linkedin_url: Optional LinkedIn URL
            website_url: Optional website URL for direct scraping
            organization_id: Organization ID for context retrieval
            user_id: User ID for sales profile context
            language: Output language code (default from config)
            
        Returns:
            Dictionary with combined research data and unified brief
        """
        current_date = datetime.now().strftime("%d %B %Y")
        logger.info(f"Starting 360° research for {company_name} on {current_date}")
        
        # Get seller context for personalized research
        seller_context = await self._get_seller_context(organization_id, user_id)
        
        # Add organization_id to seller context for caching
        if seller_context and organization_id:
            seller_context["organization_id"] = organization_id
        
        # Determine which sources to use
        tasks = []
        source_names = []
        
        # Always use Claude (360° research with caching) and Gemini (real-time signals)
        tasks.append(self.claude.search_company(
            company_name, country, city, linkedin_url,
            seller_context=seller_context,
            language=language
        ))
        source_names.append("claude")
        
        tasks.append(self.gemini.search_company(
            company_name, country, city, linkedin_url,
            seller_context=seller_context,
            language=language
        ))
        source_names.append("gemini")
        
        # Use KVK only for Dutch companies
        if self.kvk.is_dutch_company(country):
            tasks.append(self.kvk.search_company(company_name, city))
            source_names.append("kvk")
        
        # Use website scraper if URL provided
        if website_url:
            tasks.append(self.website_scraper.scrape_website(website_url))
            source_names.append("website")
        
        # Execute all searches in parallel with timeout
        try:
            results = await with_timeout(
                asyncio.gather(*tasks, return_exceptions=True),
                timeout_seconds=RESEARCH_TOTAL_TIMEOUT,
                operation_name="Research parallel tasks"
            )
        except AITimeoutError:
            logger.error(f"Research timed out after {RESEARCH_TOTAL_TIMEOUT}s for {company_name}")
            results = [asyncio.TimeoutError("Research timed out")] * len(tasks)
        
        # Combine results
        combined_data = {
            "sources": {},
            "success_count": 0,
            "total_sources": len(tasks),
            "research_date": current_date
        }
        
        for source_name, result in zip(source_names, results):
            if isinstance(result, Exception):
                combined_data["sources"][source_name] = {
                    "success": False,
                    "error": str(result)
                }
                logger.warning(f"Source {source_name} failed: {result}")
            else:
                combined_data["sources"][source_name] = result
                if result.get("success"):
                    combined_data["success_count"] += 1
                    
                    # Log cache statistics for Claude
                    if source_name == "claude" and result.get("cache_stats"):
                        cache = result["cache_stats"]
                        logger.info(
                            f"Claude cache stats: hit={cache.get('cache_hit')}, "
                            f"read={cache.get('cache_read_tokens', 0)}, "
                            f"write={cache.get('cache_write_tokens', 0)}"
                        )
        
        # Get relevant KB chunks for case studies
        kb_chunks = []
        if organization_id:
            kb_chunks = await self._get_relevant_kb_chunks(
                company_name, organization_id, seller_context
            )
            if kb_chunks:
                combined_data["sources"]["knowledge_base"] = {
                    "success": True,
                    "data": kb_chunks
                }
                combined_data["success_count"] += 1
        
        # Generate unified brief by merging all sources
        combined_data["brief"] = await self._generate_unified_brief(
            combined_data["sources"],
            company_name,
            country,
            city,
            seller_context=seller_context,
            kb_chunks=kb_chunks,
            language=language
        )
        
        logger.info(
            f"360° research completed for {company_name}: "
            f"{combined_data['success_count']}/{combined_data['total_sources']} sources successful"
        )
        
        return combined_data
    
    async def _get_seller_context(
        self,
        organization_id: Optional[str],
        user_id: Optional[str]
    ) -> Dict[str, Any]:
        """
        Get seller context: who is selling, what are they selling.
        
        This context makes research prompts highly personalized.
        Extracts and flattens fields from company_profile and sales_profile.
        """
        context = {
            "has_context": False,
            "company_name": None,
            "industry": None,
            "products_services": [],
            "value_propositions": [],
            "target_market": "B2B",
            "target_industries": [],
            "differentiators": [],
            "sales_person": None,
            "sales_strengths": [],
            "company_narrative": None,
            "sales_narrative": None
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
                context["industry"] = company.get("industry")
                
                # Products: extract names from products array
                products = company.get("products", []) or []
                context["products_services"] = [
                    p.get("name") for p in products 
                    if isinstance(p, dict) and p.get("name")
                ]
                
                # Value propositions from core_value_props
                context["value_propositions"] = company.get("core_value_props", []) or []
                
                # Differentiators (this field exists directly)
                context["differentiators"] = company.get("differentiators", []) or []
                
                # Target industries from Ideal Customer Profile
                icp = company.get("ideal_customer_profile", {}) or {}
                context["target_industries"] = icp.get("industries", []) or []
                
                context["company_narrative"] = company.get("company_narrative")
                
                logger.info(f"Seller context loaded: {context['company_name']}, products={len(context['products_services'])}")
            
            # Get sales profile
            if user_id:
                sales_response = self.supabase.table("sales_profiles")\
                    .select("*")\
                    .eq("user_id", user_id)\
                    .limit(1)\
                    .execute()
                
                if sales_response.data:
                    sales = sales_response.data[0]
                    context["sales_person"] = sales.get("full_name")
                    context["sales_strengths"] = sales.get("strengths", []) or []
                    context["sales_narrative"] = sales.get("sales_narrative")
                    
                    # Fallback: extract company name from role if not set
                    if not context.get("company_name"):
                        role = sales.get("role", "") or ""
                        if " at " in role:
                            context["company_name"] = role.split(" at ")[-1].strip()
                            context["has_context"] = True
                    
                    # Fallback: target industries from sales profile
                    if not context.get("target_industries"):
                        context["target_industries"] = sales.get("target_industries", []) or []
            
            logger.debug(f"Full seller context: {context['company_name']}, has_context={context['has_context']}")
            
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
            products = ", ".join(seller_context.get("products_services", [])[:3])
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
                if match.score > 0.5:  # Only include relevant chunks
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
        Generate unified research brief by merging all sources.
        
        Strategy:
        - Claude's 360° research is the primary structure
        - Gemini's market intelligence adds real-time news depth
        - KVK adds official registration data
        - Website scraper adds direct content
        - KB chunks add relevant case studies
        
        The merge prompt is simpler now because Claude already provides
        a complete structured output.
        """
        lang_instruction = get_language_instruction(language)
        current_date = datetime.now().strftime("%d %B %Y")
        
        # Collect successful source data
        source_sections = []
        
        # Claude's 360° research is the primary content
        if sources.get("claude", {}).get("success"):
            source_sections.append(f"""
## PRIMARY RESEARCH (Claude 360° Analysis)
{sources['claude']['data']}
""")
        
        # Gemini adds real-time market intelligence
        if sources.get("gemini", {}).get("success"):
            source_sections.append(f"""
## SUPPLEMENTARY: REAL-TIME MARKET INTELLIGENCE (Gemini)
{sources['gemini']['data']}
""")
        
        # KVK adds official Dutch company data
        if sources.get("kvk", {}).get("success"):
            kvk_data = sources['kvk']['data']
            kvk_text = f"""
## SUPPLEMENTARY: OFFICIAL REGISTRATION DATA (Dutch Chamber of Commerce)

| Field | Value |
|-------|-------|
| **KVK Number** | {kvk_data.get('kvk_number', 'Not found')} |
| **Legal Form** | {kvk_data.get('legal_form', 'Not found')} |
| **Trade Name** | {kvk_data.get('trade_name', 'Not found')} |
| **Address** | {kvk_data.get('address', {}).get('street', '')} {kvk_data.get('address', {}).get('house_number', '')}, {kvk_data.get('address', {}).get('postal_code', '')} {kvk_data.get('address', {}).get('city', '')} |
| **Established** | {kvk_data.get('establishment_date', 'Not found')} |
| **Employees** | {kvk_data.get('employees', 'Not found')} |
| **Website** | {kvk_data.get('website', 'Not found')} |
"""
            source_sections.append(kvk_text)
        
        # Website scraper adds direct content
        if sources.get("website", {}).get("success"):
            website_data = sources['website']
            website_text = f"""
## SUPPLEMENTARY: COMPANY WEBSITE CONTENT

**URL**: {website_data.get('url', 'Unknown')}
**Pages Scraped**: {website_data.get('pages_scraped', 0)}

{website_data.get('summary', 'No summary available')}
"""
            source_sections.append(website_text)
        
        # If no sources succeeded, return error
        if not source_sections:
            return f"""# Research Failed: {company_name}

**Date**: {current_date}

No data could be retrieved from any source. Please try again or verify the company name.
"""
        
        # Build KB context section
        kb_section = ""
        if kb_chunks:
            kb_texts = "\n".join([
                f"- **{chunk['source']}** (relevance: {chunk['score']:.0%}): {chunk['text'][:200]}..."
                for chunk in kb_chunks
            ])
            kb_section = f"""
## YOUR KNOWLEDGE BASE MATCHES

The following documents from your knowledge base may be relevant:

{kb_texts}
"""
        
        # Build seller context reminder
        seller_section = ""
        if seller_context and seller_context.get("has_context"):
            products = ", ".join(seller_context.get("products_services", [])[:3]) or "Not specified"
            seller_section = f"""
## SELLER CONTEXT REMINDER

You are {seller_context.get('company_name', 'Unknown')} selling {products}.
"""
        
        # Calculate source statistics
        claude_status = "✅" if sources.get("claude", {}).get("success") else "❌"
        gemini_status = "✅" if sources.get("gemini", {}).get("success") else "❌"
        kvk_status = "✅" if sources.get("kvk", {}).get("success") else ("N/A" if "kvk" not in sources else "❌")
        website_status = "✅" if sources.get("website", {}).get("success") else ("N/A" if "website" not in sources else "❌")
        kb_status = f"✅ {len(kb_chunks)} matches" if kb_chunks else "No matches"
        
        # Build the merge prompt
        # This is simpler now because Claude provides a complete structure
        merge_prompt = f"""You are merging multiple research sources into one comprehensive 360° prospect intelligence report.

**TODAY'S DATE**: {current_date}
**TARGET COMPANY**: {company_name}
{f"**LOCATION**: {city}, {country}" if city and country else f"**COUNTRY**: {country}" if country else ""}

{seller_section}
{kb_section}

═══════════════════════════════════════════════════════════════════════════════
                           SOURCE DATA TO MERGE
═══════════════════════════════════════════════════════════════════════════════

{chr(10).join(source_sections)}

═══════════════════════════════════════════════════════════════════════════════
                           MERGE INSTRUCTIONS
═══════════════════════════════════════════════════════════════════════════════

Create a SINGLE, unified 360° prospect intelligence report by:

1. **Use Claude's structure as the base** - it provides the complete framework
2. **Enhance with Gemini's news** - add any additional recent news/signals not in Claude's report
3. **Add KVK official data** - incorporate registration details into Company Identity section
4. **Include website insights** - add any unique content from direct scraping
5. **Reference KB matches** - note relevant case studies in the Commercial Opportunity section

**DEDUPLICATION RULES**:
- If the same information appears in multiple sources, include it ONCE
- Prefer official sources (KVK) for registration data
- Prefer more recent news items
- Combine leadership information from all sources

**OUTPUT REQUIREMENTS**:
- Maintain the 9-section structure from Claude's report
- Add a Research Sources section at the end showing what was used
- Keep the professional, intelligence-focused tone
- Do NOT add conversation scripts or meeting preparation content
- {lang_instruction}

**SOURCE STATUS**:
| Source | Status |
|--------|--------|
| Claude 360° Research | {claude_status} |
| Gemini Market Intelligence | {gemini_status} |
| Dutch Chamber of Commerce | {kvk_status} |
| Website Scraper | {website_status} |
| Knowledge Base | {kb_status} |

Generate the unified 360° prospect intelligence report now:"""

        try:
            # Use Claude to merge the sources
            response = await self.claude.client.messages.create(
                model="claude-sonnet-4-20250514",
                max_tokens=8192,
                temperature=0.2,
                messages=[{
                    "role": "user",
                    "content": merge_prompt
                }]
            )
            
            merged_brief = response.content[0].text
            logger.info(f"Successfully merged research sources for {company_name}")
            return merged_brief
            
        except Exception as e:
            # Fallback: If merge fails, return Claude's research if available
            logger.error(f"Error merging research sources: {e}")
            
            if sources.get("claude", {}).get("success"):
                logger.info("Falling back to Claude's raw research output")
                return sources["claude"]["data"]
            
            # Last resort: concatenate all sources
            return f"""# Research Brief: {company_name}

**Date**: {current_date}
**Note**: Merge failed, showing raw source data.

{"".join(source_sections)}
"""
    
    def clear_caches(self, organization_id: Optional[str] = None) -> None:
        """
        Clear research caches.
        
        Call this when organization's company profile is updated to ensure
        fresh seller context is used in next research.
        
        Args:
            organization_id: Specific org to clear, or None to clear all
        """
        self.claude.clear_seller_cache(organization_id)
        logger.info(f"Cleared research caches for org: {organization_id or 'all'}")
