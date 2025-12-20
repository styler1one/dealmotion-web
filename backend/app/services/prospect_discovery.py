"""
Prospect Discovery Service - Contextual Prospecting Engine

This service discovers NEW prospects based on seller context and proposition,
using Exa AI for semantic search. It does NOT research known companies -
it FINDS companies that match the seller's offering.

Architecture:
1. Query Generation (LLM) - Create 3-5 semantic search queries
2. Exa Search - Execute discovery searches
3. Content Extraction - Get relevant content from sources
4. Normalization - Deduplicate and normalize company info
5. Scoring - Calculate fit scores based on seller context

Key Principle:
"A prospect is not a company, but an organization where THIS seller,
with THIS proposition, is probably relevant NOW."
"""

import os
import asyncio
import logging
import re
from dataclasses import dataclass, field
from typing import Optional, List, Dict, Any, Tuple
from datetime import datetime, timedelta

import anthropic
from supabase import Client

from app.database import get_supabase_service
from app.services.seller_context_builder import get_seller_context_builder

logger = logging.getLogger(__name__)


# =============================================================================
# Data Classes
# =============================================================================

@dataclass
class DiscoveryInput:
    """User input for prospect discovery."""
    region: Optional[str] = None
    sector: Optional[str] = None
    company_size: Optional[str] = None
    proposition: Optional[str] = None
    target_role: Optional[str] = None
    pain_point: Optional[str] = None
    # Reference customers for context enrichment (NOT firmographic matching)
    reference_customers: Optional[List[str]] = None


@dataclass
class DiscoveredProspect:
    """A single discovered prospect."""
    company_name: str
    website: Optional[str] = None
    linkedin_url: Optional[str] = None
    
    # Inferred data
    inferred_sector: Optional[str] = None
    inferred_region: Optional[str] = None
    inferred_size: Optional[str] = None
    
    # Scoring (0-100)
    fit_score: int = 0
    proposition_fit: int = 0
    seller_fit: int = 0
    intent_score: int = 0
    recency_score: int = 0
    
    # Why this prospect
    fit_reason: Optional[str] = None
    key_signal: Optional[str] = None
    
    # Source
    source_url: str = ""
    source_title: Optional[str] = None
    source_snippet: Optional[str] = None
    source_published_date: Optional[str] = None
    matched_query: Optional[str] = None


@dataclass
class DiscoveryResult:
    """Complete result from a discovery search."""
    success: bool = False
    search_id: Optional[str] = None
    
    generated_queries: List[str] = field(default_factory=list)
    prospects: List[DiscoveredProspect] = field(default_factory=list)
    reference_context: Optional[str] = None  # Extracted context from reference customers
    
    execution_time_seconds: float = 0.0
    error: Optional[str] = None


# =============================================================================
# Prompt Templates
# =============================================================================

QUERY_GENERATION_PROMPT = """You are a B2B sales intelligence expert specializing in EARLY-STAGE prospect identification.

## CRITICAL INSIGHT

Companies actively "seeking solutions" or "buying products" are ALREADY in buying mode - competitors are likely engaged. We need to find companies BEFORE they start actively searching.

Your task: Generate queries that find companies experiencing TRIGGER EVENTS that CREATE the need for what the seller offers.

## CONTEXT

**Seller Profile (use as fallback if search input is incomplete):**
{seller_context}

**Search Input (user-specified for this search):**
- Region: {region}
- Sector/Domain: {sector}
- Company Size: {company_size}
- Proposition: {proposition}
- Target Role: {target_role}
- Pain Point/Urgency: {pain_point}
{reference_section}

**IMPORTANT**: If any search input field says "Not specified", use the corresponding information from the Seller Profile above. The seller profile contains their default proposition, target sectors, ideal customer profile, and typical pain points.

## STEP 1: ANALYZE THE PROPOSITION

Before generating queries, think about what "{proposition}" means:
- What PROBLEM does this solve?
- What SITUATION creates the need for this?
- WHO typically buys this? (which roles have budget/authority?)
- What EVENTS would make someone suddenly need this?

## STEP 2: IDENTIFY RELEVANT TRIGGERS (sector + proposition specific!)

Think about what creates urgency for **{proposition}** in **{sector}** specifically:

1. **Leadership Changes**: Which NEW leaders would prioritize {proposition}?
   - In {sector}, who decides on this? (NOT always CTO - could be COO, CFO, Chief Claims Officer, Medical Director, Partner, etc.)
   
2. **Regulatory/Compliance Pressure**: What regulations CREATE need for {proposition}?
   - What audits, certifications, or mandates affect {sector} that relate to what we sell?
   
3. **Operational Challenges**: What visible problems would {proposition} solve?
   - What customer complaints, delays, or inefficiencies in {sector} relate to our offering?
   
4. **Growth/Change Events**: How does growth create need for {proposition}?
   - Acquisitions, market expansion, volume increases that strain current capabilities?
   
5. **Competitive/Market Pressure**: What market forces push toward {proposition}?
   - Competitors with better capabilities, new entrants, industry benchmarks?

## STEP 3: GENERATE QUERIES

Generate exactly 5 semantic search queries for {region} / {sector} / {company_size} companies.

**CRITICAL RULES:**
1. Each query targets a trigger that creates need for **{proposition}** specifically
2. Use {sector}-specific terminology and the relevant decision makers for THIS type of purchase
3. The target role is **{target_role}** - find triggers that would concern THIS role
4. Consider the pain point: **{pain_point}**
5. Include {region} for geographic relevance
6. Add "{current_year}" to at least one query for recency

**BAD Queries (too generic or too late):**
- "companies seeking [solution type]" ❌ (already buying)
- "organizations implementing [technology]" ❌ (already decided)
- Generic queries that ignore the specific sector ❌

**GOOD Queries find TRIGGER EVENTS before the buying process starts.**

## OUTPUT FORMAT

Return ONLY a JSON array with exactly 5 query strings:
["query 1", "query 2", "query 3", "query 4", "query 5"]

Each query should target a DIFFERENT trigger category, adapted to {sector}. No explanation, no markdown, just the JSON array.
"""

REFERENCE_CONTEXT_PROMPT = """You are a B2B sales intelligence expert. Analyze these reference customers to understand what they have in common that makes them ideal customers.

## REFERENCE CUSTOMERS
{reference_customers}

## RESEARCH DATA
{research_data}

## YOUR TASK

Based on the research data, identify what these companies have in COMMON that makes them ideal customers. Focus on:

1. **Situations**: What business situations are they in? (growth phase, digital transformation, market expansion, etc.)
2. **Challenges**: What challenges or pain points do they share?
3. **Signals**: What public signals indicated they were good prospects? (hiring, news, initiatives)
4. **Decision context**: What was happening that created urgency?

DO NOT focus on firmographics (size, sector, location). Focus on SITUATIONS and SIGNALS.

## OUTPUT FORMAT

Write a 2-3 sentence summary of what these reference customers have in common, focusing on situations and signals that indicate buying intent. This will be used to find similar companies.

Example good output:
"These companies were all going through rapid international expansion while dealing with legacy ERP systems that couldn't scale. They had recently hired senior operations leaders and were publicly discussing digital transformation initiatives."

Example bad output (avoid this):
"These are mid-sized logistics companies in the Netherlands with 100-500 employees." (This is firmographic, not useful)

Return ONLY the summary text, no JSON, no markdown.
"""

SCORING_PROMPT = """You are a B2B sales intelligence expert specializing in EARLY-STAGE prospect identification.

## SELLER PROFILE
{seller_context}

## SEARCH CRITERIA (if "Not specified", use Seller Profile above)
- Proposition: {proposition}
- Target Role: {target_role}
- Pain Point: {pain_point}
- Sector: {sector}

## DISCOVERED COMPANIES

{prospects_json}

## SCORING PHILOSOPHY

We're looking for companies experiencing TRIGGER EVENTS that create the need for **{proposition}** specifically.

**First, understand what we sell:**
- Proposition: {proposition}
- This solves problems related to: {pain_point}
- Relevant decision maker: {target_role}

**High-value triggers (score higher):**
- New leadership in roles that would BUY {proposition} = new priorities coming
- Problems that {proposition} specifically solves = clear fit
- Regulatory pressure that {proposition} addresses = forced to act
- Growth challenges that {proposition} handles = scaling pain
- Competitor advantage that {proposition} would counter = urgency

**Lower-value signals (score lower):**
- Already implementing similar solutions = too late
- Triggers unrelated to what {proposition} solves = poor fit
- Generic company descriptions = no trigger visible
- Old news (>12 months) = situation may have changed

## YOUR TASK

For each company, ask: "Would they need **{proposition}** based on what we found?"

1. **fit_score** (0-100): Overall likelihood this is a good EARLY-STAGE prospect
2. **proposition_fit** (0-100): Would our offering ({proposition}) solve a problem this trigger creates?
3. **seller_fit** (0-100): Does this match the seller's target profile for {sector}?
4. **intent_score** (0-100): How strong is the TRIGGER signal? (NOT buying intent - trigger strength)
5. **recency_score** (0-100): How recent is the trigger? (<3mo=90+, 3-6mo=70-90, 6-12mo=50-70, >12mo=<50)
6. **fit_reason**: One sentence: What trigger creates the need for our offering?
7. **key_signal**: The specific trigger event found (be specific to what you found)
8. **inferred_sector**: Best guess for their industry
9. **inferred_size**: Best guess for size (startup/SMB/mid-market/enterprise)

## OUTPUT FORMAT

Return a JSON array with one object per company:
[
  {{
    "company_name": "exact name from input",
    "fit_score": 75,
    "proposition_fit": 80,
    "seller_fit": 70,
    "intent_score": 85,
    "recency_score": 90,
    "fit_reason": "Recent leadership change creates opportunity to review current approach",
    "key_signal": "Appointed new [relevant role] who announced focus on [relevant area]",
    "inferred_sector": "example sector",
    "inferred_size": "mid-market"
  }}
]

**Scoring guide:**
- 80-100: Clear, recent trigger directly relevant to our proposition
- 60-79: Visible trigger, somewhat relevant
- 40-59: Possible trigger, indirect relevance
- 20-39: Weak or old signal
- 0-19: No trigger visible, or already buying/implemented

Return ONLY the JSON array, no explanation.
"""


# =============================================================================
# Prospect Discovery Service
# =============================================================================

class ProspectDiscoveryService:
    """
    Service for discovering new prospects using contextual AI search.
    
    This is fundamentally different from company research:
    - Research: Deep dive into ONE known company
    - Discovery: Find MANY companies that might be prospects
    """
    
    def __init__(self):
        """Initialize clients."""
        self._supabase: Client = get_supabase_service()
        self._seller_context_builder = get_seller_context_builder()
        
        # Anthropic client for query generation and scoring
        self._anthropic = None
        api_key = os.getenv("ANTHROPIC_API_KEY")
        if api_key:
            self._anthropic = anthropic.Anthropic(api_key=api_key)
        
        # Exa client for discovery search
        self._exa = None
        exa_key = os.getenv("EXA_API_KEY")
        if exa_key:
            try:
                from exa_py import Exa
                self._exa = Exa(api_key=exa_key)
                logger.info("[PROSPECT_DISCOVERY] Exa client initialized")
            except ImportError:
                logger.warning("[PROSPECT_DISCOVERY] Exa SDK not available")
    
    @property
    def is_available(self) -> bool:
        """Check if service is available."""
        return self._anthropic is not None and self._exa is not None
    
    async def discover_prospects(
        self,
        user_id: str,
        organization_id: str,
        input: DiscoveryInput,
        max_results: int = 20
    ) -> DiscoveryResult:
        """
        Main entry point for prospect discovery.
        
        Args:
            user_id: User ID
            organization_id: Organization ID
            input: Discovery input parameters
            max_results: Maximum prospects to return
            
        Returns:
            DiscoveryResult with discovered prospects
        """
        if not self.is_available:
            print(f"[PROSPECT_DISCOVERY] ❌ Service not available!")
            return DiscoveryResult(
                success=False,
                error="Service not available - missing API keys"
            )
        
        start_time = datetime.now()
        
        print(f"[PROSPECT_DISCOVERY] 🚀 Starting discovery for user {user_id}")
        logger.info(f"[PROSPECT_DISCOVERY] Starting discovery for user {user_id}")
        
        reference_context = None
        
        try:
            # Step 1: Get seller context
            seller_context = self._seller_context_builder.build_unified_context(
                user_id=user_id,
                organization_id=organization_id,
                format="full",
                include_style_rules=False
            )
            
            # Step 1.5: If reference customers provided, extract context from them
            if input.reference_customers and len(input.reference_customers) > 0:
                logger.info(f"[PROSPECT_DISCOVERY] Processing {len(input.reference_customers)} reference customers")
                reference_context = await self._extract_reference_context(
                    reference_customers=input.reference_customers
                )
                if reference_context:
                    logger.info(f"[PROSPECT_DISCOVERY] Extracted reference context: {reference_context[:100]}...")
            
            # Step 2: Generate search queries
            queries = await self._generate_queries(
                input=input,
                seller_context=seller_context,
                reference_context=reference_context
            )
            
            if not queries:
                return DiscoveryResult(
                    success=False,
                    error="Failed to generate search queries"
                )
            
            # Step 2.5: Add market leaders query based on user input
            market_leader_query = self._build_market_leaders_query(input)
            if market_leader_query:
                queries.append(market_leader_query)
                print(f"[PROSPECT_DISCOVERY] 🏢 Added market leaders query: {market_leader_query[:80]}...", flush=True)
            
            print(f"[PROSPECT_DISCOVERY] 📝 TOTAL {len(queries)} QUERIES:", flush=True)
            for i, q in enumerate(queries[:4], 1):
                print(f"  Query {i}: {q[:100]}...", flush=True)
            
            # Step 3: Execute Exa searches
            raw_results = await self._execute_discovery_searches(
                queries=queries,
                region=input.region
            )
            
            if not raw_results:
                return DiscoveryResult(
                    success=True,
                    generated_queries=queries,
                    prospects=[],
                    reference_context=reference_context,
                    execution_time_seconds=(datetime.now() - start_time).total_seconds()
                )
            
            logger.info(f"[PROSPECT_DISCOVERY] Found {len(raw_results)} raw results")
            
            # Step 4: Normalize and deduplicate
            normalized = self._normalize_results(raw_results)
            logger.info(f"[PROSPECT_DISCOVERY] Normalized to {len(normalized)} unique companies")
            
            # Step 5: Score and analyze
            scored = await self._score_prospects(
                prospects=normalized[:max_results],  # Limit before scoring
                input=input,
                seller_context=seller_context
            )
            
            # Sort by fit score
            scored.sort(key=lambda p: p.fit_score, reverse=True)
            
            execution_time = (datetime.now() - start_time).total_seconds()
            
            logger.info(
                f"[PROSPECT_DISCOVERY] Completed: {len(scored)} prospects, "
                f"{execution_time:.1f}s"
            )
            
            return DiscoveryResult(
                success=True,
                generated_queries=queries,
                prospects=scored,
                reference_context=reference_context,
                execution_time_seconds=execution_time
            )
            
        except Exception as e:
            logger.error(f"[PROSPECT_DISCOVERY] Error: {e}")
            return DiscoveryResult(
                success=False,
                error=str(e)
            )
    
    async def _generate_queries(
        self,
        input: DiscoveryInput,
        seller_context: str,
        reference_context: Optional[str] = None
    ) -> List[str]:
        """Generate semantic search queries using Claude."""
        if not self._anthropic:
            return []
        
        # Build reference section if we have reference context
        reference_section = ""
        if reference_context:
            reference_section = f"""
**Reference Customer Context:**
The seller provided reference customers (companies that are 100% fit). Based on analysis, these companies have the following in common:
{reference_context}

Use these patterns to find SIMILAR companies with SIMILAR signals and situations.
"""
        
        prompt = QUERY_GENERATION_PROMPT.format(
            seller_context=seller_context,
            region=input.region or "Not specified",
            sector=input.sector or "Not specified",
            company_size=input.company_size or "Not specified",
            proposition=input.proposition or "Not specified",
            target_role=input.target_role or "Not specified",
            pain_point=input.pain_point or "Not specified",
            reference_section=reference_section,
            current_year=datetime.now().year
        )
        
        try:
            response = self._anthropic.messages.create(
                model="claude-sonnet-4-20250514",
                max_tokens=1024,
                messages=[{"role": "user", "content": prompt}]
            )
            
            content = response.content[0].text.strip()
            
            # Parse JSON array
            import json
            queries = json.loads(content)
            
            if isinstance(queries, list) and len(queries) > 0:
                return queries[:5]  # Max 5 queries
            
            return []
            
        except Exception as e:
            logger.error(f"[PROSPECT_DISCOVERY] Query generation failed: {e}")
            return []
    
    def _build_market_leaders_query(self, input: DiscoveryInput) -> Optional[str]:
        """
        Build a query to find market leaders in the specified segment.
        
        This ensures we always include the top players in the sector,
        not just companies with visible trigger signals.
        """
        if not input.sector:
            return None
        
        # Build size descriptor
        size_terms = {
            "enterprise": "largest major leading",
            "mid-market": "established prominent growing",
            "mid-sized": "established prominent growing", 
            "midmarket": "established prominent growing",
            "smb": "notable successful emerging",
            "sme": "notable successful emerging",
            "startup": "innovative fast-growing emerging",
            "scale-up": "fast-growing successful scaling",
        }
        
        size_input = (input.company_size or "").lower().strip()
        size_descriptor = "leading prominent"
        
        for key, desc in size_terms.items():
            if key in size_input:
                size_descriptor = desc
                break
        
        # Build region part
        region_part = f"in {input.region}" if input.region else ""
        
        # Build the query
        query = f"{size_descriptor} {input.sector} companies {region_part}".strip()
        
        # Clean up double spaces
        query = " ".join(query.split())
        
        return query
    
    async def _extract_reference_context(
        self,
        reference_customers: List[str]
    ) -> Optional[str]:
        """
        Extract common context from reference customers.
        
        This does quick Exa searches on each reference customer,
        then uses Claude to identify common patterns (situations, signals).
        
        NOT for firmographic matching - for understanding WHY these are good customers.
        """
        if not self._exa or not self._anthropic:
            return None
        
        if not reference_customers or len(reference_customers) == 0:
            return None
        
        logger.info(f"[PROSPECT_DISCOVERY] Researching {len(reference_customers)} reference customers")
        
        # Quick research on each reference customer
        research_results = []
        loop = asyncio.get_event_loop()
        
        for company in reference_customers[:3]:  # Max 3 references
            try:
                def do_search():
                    return self._exa.search_and_contents(
                        query=f'"{company}" company news announcement strategy',
                        type="auto",
                        num_results=5,
                        text={"max_characters": 800}
                    )
                
                response = await loop.run_in_executor(None, do_search)
                
                if response.results:
                    snippets = []
                    for r in response.results[:3]:
                        title = getattr(r, 'title', '')
                        text = getattr(r, 'text', '')[:500]
                        snippets.append(f"- {title}: {text}")
                    
                    research_results.append({
                        "company": company,
                        "data": "\n".join(snippets)
                    })
                    
            except Exception as e:
                logger.warning(f"[PROSPECT_DISCOVERY] Failed to research reference {company}: {e}")
                continue
            
            # Rate limiting
            await asyncio.sleep(0.3)
        
        if not research_results:
            return None
        
        # Format research data for Claude
        research_data = "\n\n".join([
            f"### {r['company']}\n{r['data']}"
            for r in research_results
        ])
        
        # Extract common context using Claude
        try:
            prompt = REFERENCE_CONTEXT_PROMPT.format(
                reference_customers=", ".join(reference_customers),
                research_data=research_data
            )
            
            response = self._anthropic.messages.create(
                model="claude-sonnet-4-20250514",
                max_tokens=500,
                messages=[{"role": "user", "content": prompt}]
            )
            
            context = response.content[0].text.strip()
            return context
            
        except Exception as e:
            logger.error(f"[PROSPECT_DISCOVERY] Reference context extraction failed: {e}")
            return None
    
    async def _execute_discovery_searches(
        self,
        queries: List[str],
        region: Optional[str] = None
    ) -> List[Dict[str, Any]]:
        """
        Execute discovery searches using Exa.
        
        Uses different settings than company research:
        - Focus on news and company announcements
        - Recent content only (last 12-18 months)
        - More results per query for diversity
        """
        if not self._exa:
            return []
        
        all_results = []
        
        # Date filter: last 18 months
        start_date = (datetime.now() - timedelta(days=540)).strftime("%Y-%m-%dT00:00:00.000Z")
        
        # Execute searches in parallel (with rate limiting)
        loop = asyncio.get_event_loop()
        
        async def search_query(query: str) -> List[Dict[str, Any]]:
            try:
                print(f"[PROSPECT_DISCOVERY] 🔍 EXA CALL: {query[:80]}...", flush=True)
                
                def do_search():
                    return self._exa.search_and_contents(
                        query=query,
                        type="auto",
                        num_results=15,  # More results per query
                        start_published_date=start_date,
                        text={"max_characters": 1500}
                    )
                
                response = await loop.run_in_executor(None, do_search)
                
                results = []
                for r in response.results:
                    results.append({
                        "url": getattr(r, 'url', ''),
                        "title": getattr(r, 'title', ''),
                        "text": getattr(r, 'text', ''),
                        "published_date": getattr(r, 'published_date', None) or getattr(r, 'publishedDate', ''),
                        "matched_query": query
                    })
                
                print(f"[PROSPECT_DISCOVERY] ✅ EXA RETURNED: {len(results)} results", flush=True)
                return results
                
            except Exception as e:
                logger.error(f"[PROSPECT_DISCOVERY] ❌ Exa search failed for query: {e}")
                return []
        
        # Execute with small delay between queries (rate limiting)
        print(f"[PROSPECT_DISCOVERY] 🚀 STARTING EXA with {len(queries)} queries", flush=True)
        for i, query in enumerate(queries):
            results = await search_query(query)
            all_results.extend(results)
            
            # Small delay between queries
            if i < len(queries) - 1:
                await asyncio.sleep(0.5)
        
        return all_results
    
    def _normalize_results(
        self,
        raw_results: List[Dict[str, Any]]
    ) -> List[DiscoveredProspect]:
        """
        Normalize and deduplicate raw search results.
        
        Extracts company names from URLs and content,
        deduplicates by domain/company name.
        """
        seen_domains = set()
        seen_companies = set()
        prospects = []
        
        for r in raw_results:
            url = r.get("url", "")
            title = r.get("title", "")
            text = r.get("text", "")
            
            # Extract domain
            domain = self._extract_domain(url)
            if not domain or domain in seen_domains:
                continue
            
            # Skip common news/aggregator sites
            if self._is_aggregator_domain(domain):
                continue
            
            # Try to extract company name
            company_name = self._extract_company_name(url, title, text)
            if not company_name:
                continue
            
            # Normalize company name for deduplication
            normalized_name = company_name.lower().strip()
            if normalized_name in seen_companies:
                continue
            
            seen_domains.add(domain)
            seen_companies.add(normalized_name)
            
            # Infer region from URL/content
            inferred_region = self._infer_region(url, text)
            
            prospects.append(DiscoveredProspect(
                company_name=company_name,
                website=f"https://{domain}" if not url.startswith("http") else self._get_root_url(url),
                linkedin_url=self._extract_linkedin(text),
                inferred_region=inferred_region,
                source_url=url,
                source_title=title,
                source_snippet=text[:500] if text else None,
                source_published_date=r.get("published_date"),
                matched_query=r.get("matched_query")
            ))
        
        return prospects
    
    async def _score_prospects(
        self,
        prospects: List[DiscoveredProspect],
        input: DiscoveryInput,
        seller_context: str
    ) -> List[DiscoveredProspect]:
        """Score prospects using Claude for fit analysis."""
        if not prospects or not self._anthropic:
            return prospects
        
        # Prepare prospects for scoring
        prospects_data = [
            {
                "company_name": p.company_name,
                "website": p.website,
                "source_title": p.source_title,
                "source_snippet": p.source_snippet,
                "source_published_date": p.source_published_date
            }
            for p in prospects
        ]
        
        import json
        prospects_json = json.dumps(prospects_data, indent=2)
        
        prompt = SCORING_PROMPT.format(
            seller_context=seller_context,
            proposition=input.proposition or "Not specified",
            target_role=input.target_role or "Not specified",
            pain_point=input.pain_point or "Not specified",
            sector=input.sector or "Not specified",
            prospects_json=prospects_json
        )
        
        try:
            response = self._anthropic.messages.create(
                model="claude-sonnet-4-20250514",
                max_tokens=4096,
                messages=[{"role": "user", "content": prompt}]
            )
            
            content = response.content[0].text.strip()
            
            # Strip markdown code blocks if present
            if content.startswith("```"):
                lines = content.split("\n")
                # Remove first line (```json) and last line (```)
                lines = [l for l in lines if not l.startswith("```")]
                content = "\n".join(lines)
            
            # Parse JSON
            scores = json.loads(content)
            
            # Apply scores to prospects
            score_map = {s["company_name"]: s for s in scores}
            
            for p in prospects:
                if p.company_name in score_map:
                    s = score_map[p.company_name]
                    p.fit_score = s.get("fit_score", 0)
                    p.proposition_fit = s.get("proposition_fit", 0)
                    p.seller_fit = s.get("seller_fit", 0)
                    p.intent_score = s.get("intent_score", 0)
                    p.recency_score = s.get("recency_score", 0)
                    p.fit_reason = s.get("fit_reason")
                    p.key_signal = s.get("key_signal")
                    p.inferred_sector = s.get("inferred_sector")
                    p.inferred_size = s.get("inferred_size")
            
            return prospects
            
        except json.JSONDecodeError as e:
            logger.error(f"[PROSPECT_DISCOVERY] Scoring JSON parse failed: {e}")
            logger.error(f"[PROSPECT_DISCOVERY] Raw content was: {content[:500] if content else 'EMPTY'}")
            return prospects
        except Exception as e:
            logger.error(f"[PROSPECT_DISCOVERY] Scoring failed: {e}")
            return prospects
    
    # =========================================================================
    # Helper Methods
    # =========================================================================
    
    def _extract_domain(self, url: str) -> Optional[str]:
        """Extract domain from URL."""
        try:
            from urllib.parse import urlparse
            parsed = urlparse(url)
            domain = parsed.netloc.lower()
            # Remove www prefix
            if domain.startswith("www."):
                domain = domain[4:]
            return domain if domain else None
        except Exception:
            return None
    
    def _get_root_url(self, url: str) -> str:
        """Get root URL from full URL."""
        try:
            from urllib.parse import urlparse
            parsed = urlparse(url)
            return f"{parsed.scheme}://{parsed.netloc}"
        except Exception:
            return url
    
    def _is_aggregator_domain(self, domain: str) -> bool:
        """Check if domain is a news aggregator or common site."""
        aggregators = {
            # News sites
            "reuters.com", "bloomberg.com", "ft.com", "wsj.com", "bbc.com",
            "cnn.com", "techcrunch.com", "wired.com", "forbes.com",
            # Social/Aggregators
            "linkedin.com", "twitter.com", "facebook.com", "reddit.com",
            "medium.com", "substack.com",
            # Databases
            "crunchbase.com", "pitchbook.com", "glassdoor.com", "indeed.com",
            "g2.com", "capterra.com", "trustpilot.com",
            # Other
            "wikipedia.org", "youtube.com", "github.com"
        }
        
        for agg in aggregators:
            if domain.endswith(agg):
                return True
        return False
    
    def _extract_company_name(
        self,
        url: str,
        title: str,
        text: str
    ) -> Optional[str]:
        """
        Extract company name from URL, title, or content.
        
        Strategy:
        1. Try domain name (cleaned)
        2. Look for company name patterns in title
        3. Look for "About [Company]" patterns in text
        """
        # Try domain first
        domain = self._extract_domain(url)
        if domain:
            # Clean domain to get company name
            company = domain.split('.')[0]
            # Remove common prefixes
            for prefix in ['www', 'blog', 'news', 'press', 'ir', 'investor']:
                if company.startswith(prefix):
                    company = company[len(prefix):]
            if len(company) >= 2:
                return company.title()
        
        # Try title patterns
        if title:
            # "Company X announces..." pattern
            match = re.match(r'^([A-Z][A-Za-z0-9\s&]+?)\s+(announces|launches|partners|expands|raises|acquires)', title)
            if match:
                return match.group(1).strip()
            
            # "About Company X" pattern
            match = re.search(r'(?:About|At|From)\s+([A-Z][A-Za-z0-9\s&]+?)(?:\s*[-|:]|$)', title)
            if match:
                return match.group(1).strip()
        
        return None
    
    def _extract_linkedin(self, text: str) -> Optional[str]:
        """Extract LinkedIn company URL from text."""
        if not text:
            return None
        
        match = re.search(r'linkedin\.com/company/([a-zA-Z0-9-]+)', text)
        if match:
            return f"https://www.linkedin.com/company/{match.group(1)}"
        
        return None
    
    def _infer_region(self, url: str, text: str) -> Optional[str]:
        """Infer region from URL TLD or content."""
        domain = self._extract_domain(url)
        if domain:
            # Check TLD
            tld = domain.split('.')[-1]
            tld_map = {
                "nl": "Netherlands",
                "de": "Germany",
                "be": "Belgium",
                "fr": "France",
                "uk": "United Kingdom",
                "co.uk": "United Kingdom",
                "es": "Spain",
                "it": "Italy",
                "at": "Austria",
                "ch": "Switzerland"
            }
            if tld in tld_map:
                return tld_map[tld]
        
        # Check text for country mentions
        if text:
            text_lower = text.lower()
            for country in ["netherlands", "germany", "belgium", "france", "united kingdom", "spain", "italy"]:
                if country in text_lower:
                    return country.title()
        
        return None
    
    # =========================================================================
    # Database Operations
    # =========================================================================
    
    async def save_search(
        self,
        user_id: str,
        organization_id: str,
        input: DiscoveryInput,
        result: DiscoveryResult
    ) -> Optional[str]:
        """Save search and results to database."""
        try:
            import json
            
            # Create search record
            search_data = {
                "organization_id": organization_id,
                "user_id": user_id,
                "region": input.region,
                "sector": input.sector,
                "company_size": input.company_size,
                "proposition": input.proposition,
                "target_role": input.target_role,
                "pain_point": input.pain_point,
                "reference_customers": input.reference_customers,
                "reference_context": result.reference_context,
                "generated_queries": result.generated_queries,
                "status": "completed" if result.success else "failed",
                "results_count": len(result.prospects),
                "error_message": result.error,
                "execution_time_seconds": result.execution_time_seconds,
                "completed_at": datetime.now().isoformat()
            }
            
            response = self._supabase.table("prospecting_searches")\
                .insert(search_data)\
                .execute()
            
            if not response.data:
                return None
            
            search_id = response.data[0]["id"]
            
            # Save results
            if result.prospects:
                results_data = [
                    {
                        "search_id": search_id,
                        "organization_id": organization_id,
                        "company_name": p.company_name,
                        "website": p.website,
                        "linkedin_url": p.linkedin_url,
                        "inferred_sector": p.inferred_sector,
                        "inferred_region": p.inferred_region,
                        "inferred_size": p.inferred_size,
                        "fit_score": p.fit_score,
                        "proposition_fit": p.proposition_fit,
                        "seller_fit": p.seller_fit,
                        "intent_score": p.intent_score,
                        "recency_score": p.recency_score,
                        "fit_reason": p.fit_reason,
                        "key_signal": p.key_signal,
                        "source_url": p.source_url,
                        "source_title": p.source_title,
                        "source_snippet": p.source_snippet,
                        "source_published_date": p.source_published_date if p.source_published_date else None,
                        "matched_query": p.matched_query
                    }
                    for p in result.prospects
                ]
                
                self._supabase.table("prospecting_results")\
                    .insert(results_data)\
                    .execute()
            
            return search_id
            
        except Exception as e:
            logger.error(f"[PROSPECT_DISCOVERY] Failed to save search: {e}")
            return None
    
    async def get_search_history(
        self,
        organization_id: str,
        limit: int = 10
    ) -> List[Dict[str, Any]]:
        """Get recent searches for organization."""
        try:
            response = self._supabase.table("prospecting_searches")\
                .select("*")\
                .eq("organization_id", organization_id)\
                .order("created_at", desc=True)\
                .limit(limit)\
                .execute()
            
            return response.data or []
            
        except Exception as e:
            logger.error(f"[PROSPECT_DISCOVERY] Failed to get history: {e}")
            return []
    
    async def get_search_results(
        self,
        search_id: str,
        min_score: int = 0
    ) -> List[Dict[str, Any]]:
        """Get results for a specific search."""
        try:
            query = self._supabase.table("prospecting_results")\
                .select("*")\
                .eq("search_id", search_id)\
                .eq("is_duplicate", False)\
                .gte("fit_score", min_score)\
                .order("fit_score", desc=True)
            
            response = query.execute()
            return response.data or []
            
        except Exception as e:
            logger.error(f"[PROSPECT_DISCOVERY] Failed to get results: {e}")
            return []
    
    async def import_to_prospects(
        self,
        result_id: str,
        organization_id: str
    ) -> Optional[str]:
        """Import a discovered prospect to the prospects table."""
        try:
            # Get the result
            response = self._supabase.table("prospecting_results")\
                .select("*")\
                .eq("id", result_id)\
                .single()\
                .execute()
            
            if not response.data:
                return None
            
            result = response.data
            
            # Check if already imported
            if result.get("prospect_id"):
                return result["prospect_id"]
            
            # Create prospect
            prospect_data = {
                "organization_id": organization_id,
                "company_name": result["company_name"],
                "website": result.get("website"),
                "linkedin_url": result.get("linkedin_url"),
                "industry": result.get("inferred_sector"),
                "country": result.get("inferred_region"),
                "company_size": result.get("inferred_size"),
                "status": "new",
                "notes": f"Discovered via prospecting search. Fit score: {result.get('fit_score', 0)}. {result.get('fit_reason', '')}"
            }
            
            prospect_response = self._supabase.table("prospects")\
                .insert(prospect_data)\
                .execute()
            
            if prospect_response.data:
                prospect_id = prospect_response.data[0]["id"]
                
                # Update result with link
                self._supabase.table("prospecting_results")\
                    .update({
                        "prospect_id": prospect_id,
                        "imported_at": datetime.now().isoformat()
                    })\
                    .eq("id", result_id)\
                    .execute()
                
                return prospect_id
            
            return None
            
        except Exception as e:
            logger.error(f"[PROSPECT_DISCOVERY] Failed to import prospect: {e}")
            return None


# =============================================================================
# Singleton
# =============================================================================

_prospect_discovery_service: Optional[ProspectDiscoveryService] = None


def get_prospect_discovery_service() -> ProspectDiscoveryService:
    """Get or create the prospect discovery service singleton."""
    global _prospect_discovery_service
    if _prospect_discovery_service is None:
        _prospect_discovery_service = ProspectDiscoveryService()
    return _prospect_discovery_service

