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
    
    # Primary source (best quality source - company website preferred)
    source_url: str = ""
    source_title: Optional[str] = None
    source_snippet: Optional[str] = None
    source_published_date: Optional[str] = None
    matched_query: Optional[str] = None
    source_type: Optional[str] = None  # company, similar, direct, news
    
    # Additional signals from other sources (merged during deduplication)
    # Each signal is a dict with: {source_type, title, snippet, url, date}
    additional_signals: List[Dict[str, Any]] = field(default_factory=list)


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
# Sector-Specific Trigger Library
# =============================================================================
# This library provides sector-specific knowledge to improve query generation.
# Each sector has:
# - decision_makers: Roles that typically buy solutions in this sector
# - regulations: Relevant compliance/regulatory triggers
# - events: Common trigger events that create buying need
# - pain_points: Typical challenges that signal opportunity

SECTOR_TRIGGERS = {
    # Financial Services
    "insurance": {
        "decision_makers": ["Chief Claims Officer", "Chief Underwriting Officer", "Chief Digital Officer", "CIO", "Chief Risk Officer"],
        "regulations": ["Solvency II", "IFRS 17", "PSD2", "DORA", "ESG reporting"],
        "events": ["fusie", "overname", "claims processing optimization", "digitalisering", "InsurTech partnership"],
        "pain_points": ["schade-afhandeling", "legacy systems", "customer experience", "fraude detectie", "operational efficiency"],
    },
    "verzekeraars": {
        "decision_makers": ["Chief Claims Officer", "Chief Underwriting Officer", "Chief Digital Officer", "CIO"],
        "regulations": ["Solvency II", "IFRS 17", "DNB regelgeving", "AFM toezicht"],
        "events": ["fusie", "overname", "digitale transformatie", "nieuwe directie"],
        "pain_points": ["claims verwerking", "legacy systemen", "klantervaring", "fraude"],
    },
    "schadeverzekeraars": {
        "decision_makers": ["Chief Claims Officer", "Directeur Schade", "CIO", "COO"],
        "regulations": ["Solvency II", "Wft", "GDPR/AVG", "Kifid klachten"],
        "events": ["schade-optimalisatie", "automatisering", "AI implementatie", "nieuwe CEO"],
        "pain_points": ["doorlooptijd schades", "handmatige processen", "klachten AFM", "concurrentie InsurTech"],
    },
    "banking": {
        "decision_makers": ["CIO", "Chief Digital Officer", "Chief Risk Officer", "CFO"],
        "regulations": ["Basel IV", "PSD2", "AML/KYC", "DORA"],
        "events": ["digital banking", "fintech partnership", "core banking replacement"],
        "pain_points": ["legacy systems", "customer onboarding", "compliance costs"],
    },
    
    # Professional Services
    "accountancy": {
        "decision_makers": ["Managing Partner", "Head of Audit", "IT Director", "Partner"],
        "regulations": ["NBA", "AFM toezicht", "ESG rapportage", "CSRD"],
        "events": ["private equity investering", "fusie", "kantoor overname", "partner uittreding"],
        "pain_points": ["Big Four concurrentie", "talent shortage", "audit automation", "digitalisering"],
    },
    "accounting": {
        "decision_makers": ["Managing Partner", "CFO", "Head of Tax", "IT Director"],
        "regulations": ["SOX compliance", "ESG reporting", "CSRD", "audit requirements"],
        "events": ["merger", "PE investment", "digital transformation", "new leadership"],
        "pain_points": ["talent retention", "automation", "competition", "efficiency"],
    },
    "legal": {
        "decision_makers": ["Managing Partner", "CIO", "COO", "Head of Innovation"],
        "regulations": ["GDPR", "legal tech regulations", "billing compliance"],
        "events": ["merger", "new practice area", "office expansion", "leadership change"],
        "pain_points": ["matter management", "document review", "billing efficiency", "client portals"],
    },
    "consultancy": {
        "decision_makers": ["Managing Director", "Partner", "Head of Digital", "CTO"],
        "regulations": ["industry certifications", "compliance frameworks"],
        "events": ["market expansion", "new service line", "acquisition", "leadership"],
        "pain_points": ["knowledge management", "resource planning", "competitive positioning"],
    },
    
    # Healthcare
    "healthcare": {
        "decision_makers": ["Medical Director", "CIO", "CFO", "Chief Nursing Officer"],
        "regulations": ["HIPAA", "FDA", "EPD requirements", "Zorgverzekeringswet"],
        "events": ["EMR implementation", "hospital merger", "new facility", "digital health initiative"],
        "pain_points": ["patient experience", "staff shortage", "interoperability", "costs"],
    },
    "zorg": {
        "decision_makers": ["Bestuurder", "CIO", "Medisch Directeur", "Hoofd ICT"],
        "regulations": ["NEN 7510", "AVG", "Wkkgz", "Wmcz"],
        "events": ["fusie ziekenhuizen", "EPD implementatie", "digitale zorg", "nieuwe bestuurder"],
        "pain_points": ["personeelstekort", "wachtlijsten", "administratieve last", "EPD frustratie"],
    },
    
    # Manufacturing & Logistics
    "manufacturing": {
        "decision_makers": ["COO", "VP Operations", "Plant Manager", "CIO"],
        "regulations": ["ISO certifications", "environmental", "safety"],
        "events": ["factory expansion", "automation project", "supply chain disruption", "new CEO"],
        "pain_points": ["supply chain", "quality control", "operational efficiency", "sustainability"],
    },
    "logistics": {
        "decision_makers": ["COO", "VP Supply Chain", "CIO", "Head of Operations"],
        "regulations": ["customs", "transport regulations", "sustainability mandates"],
        "events": ["warehouse expansion", "fleet modernization", "M&A", "new contracts"],
        "pain_points": ["visibility", "last mile", "capacity planning", "driver shortage"],
    },
    
    # Technology
    "technology": {
        "decision_makers": ["CTO", "VP Engineering", "CIO", "Head of Product"],
        "regulations": ["SOC 2", "GDPR", "industry-specific"],
        "events": ["funding round", "product launch", "international expansion", "new CTO"],
        "pain_points": ["scaling", "technical debt", "talent", "security"],
    },
    "saas": {
        "decision_makers": ["CTO", "VP Engineering", "Head of Product", "CEO"],
        "regulations": ["SOC 2", "GDPR", "ISO 27001"],
        "events": ["Series A/B/C", "international launch", "enterprise pivot", "new leadership"],
        "pain_points": ["churn", "scaling infrastructure", "enterprise readiness", "integration"],
    },
    
    # Retail & E-commerce
    "retail": {
        "decision_makers": ["CDO", "CIO", "Head of E-commerce", "CMO"],
        "regulations": ["consumer protection", "GDPR", "accessibility"],
        "events": ["omnichannel initiative", "store closures", "new CEO", "PE acquisition"],
        "pain_points": ["online competition", "inventory", "customer experience", "personalization"],
    },
    "ecommerce": {
        "decision_makers": ["CTO", "Head of Operations", "CMO", "CEO"],
        "regulations": ["consumer law", "GDPR", "payment regulations"],
        "events": ["marketplace launch", "international expansion", "funding", "acquisition"],
        "pain_points": ["conversion", "fulfillment", "returns", "customer acquisition cost"],
    },
}

def get_sector_context(sector: str) -> Optional[Dict[str, Any]]:
    """
    Get sector-specific trigger context for query generation.
    
    Returns None if sector not found - query generation will use generic approach.
    """
    if not sector:
        return None
    
    sector_lower = sector.lower().strip()
    
    # Direct match
    if sector_lower in SECTOR_TRIGGERS:
        return SECTOR_TRIGGERS[sector_lower]
    
    # Partial match (e.g., "non-life insurance" matches "insurance")
    for key, value in SECTOR_TRIGGERS.items():
        if key in sector_lower or sector_lower in key:
            return value
    
    return None


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
{sector_context_section}

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

Generate exactly 7 semantic search queries for {region} / {sector} / {company_size} companies.

**QUERY TYPES TO GENERATE:**

**Queries 1-5: TRIGGER-BASED DISCOVERY**
- Each targets a DIFFERENT trigger category from Step 2
- Focus on events that CREATE need for {proposition}
- Include {region} for geographic relevance
- Add "{current_year}" to at least one query for recency

**Queries 6-7: MARKET LEADERS DISCOVERY**
- These find the TOP PLAYERS in {sector} in {region}
- Query 6: "biggest/largest/top [local sector term] in [region]"
- Query 7: "[local sector term] [region] overview list major players"
- These ensure we don't miss established companies without recent trigger signals

**LANGUAGE RULE - CRITICAL:**
- Use the LOCAL LANGUAGE of the target region for ALL queries!
- YOU must figure out the correct local terminology for the sector
- Examples:
  * Netherlands "accountancy" → "accountantskantoor", "registeraccountant", "accountantsfirma"
  * Netherlands "insurance" → "verzekeraar", "verzekeraars", "verzekeringsmaatschappij"
  * Germany "accountancy" → "Wirtschaftsprüfer", "Steuerberater", "Steuerkanzlei"
  * Germany "consulting" → "Unternehmensberatung", "Beratung"
  * Belgium may use Dutch OR French depending on region
- Think: "What do locals call this sector? What terms would be on their website?"
- Local language queries find LOCAL companies that don't rank for English terms

**BAD Queries:**
- "companies seeking [solution type]" ❌ (already buying)
- "organizations implementing [technology]" ❌ (already decided)
- English terms for non-English regions ❌ (e.g., "accountancy Netherlands" instead of "accountantskantoor Nederland")
- Generic queries that ignore the specific sector ❌

**GOOD Queries find TRIGGER EVENTS and MARKET LEADERS in the LOCAL LANGUAGE.**

## OUTPUT FORMAT

Return ONLY a JSON array with exactly 7 query strings:
["trigger query 1", "trigger query 2", "trigger query 3", "trigger query 4", "trigger query 5", "market leaders query 6", "market leaders query 7"]

Queries 1-5 target different trigger categories. Queries 6-7 find top players. No explanation, no markdown, just the JSON array.
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

## DATA STRUCTURE

Each company has:
- **primary_source**: The main source (company website preferred)
- **additional_signals** (optional): Other sources where this company was found (news articles, etc.)

When scoring, consider ALL signals for a company. Multiple signals = stronger evidence.
- A company found via their own website + a news article about their new CTO = VERY strong (2 signals)
- A company only found via a generic directory listing = weaker (1 weak signal)

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

**CRITICAL: Is this a potential BUYER?**

Ask yourself: "Would this organization actually BUY {proposition}?"

Score 0-15 if the result is:
- A news article or blog POST about companies (not the company itself)
- A case study or whitepaper FROM a vendor (the vendor is not the prospect)
- A regulatory body or government agency (unless {sector} is government)
- An academic paper or research publication
- A job posting or career page

The key question is: Does the URL represent the company's OWN website/content, or is it content ABOUT them from a third party?

Examples:
- "achmea.nl/nieuws/..." = ✅ Achmea's own site = potential prospect
- "consultancy.nl/nieuws/achmea-..." = ❌ News article ABOUT Achmea = score 0-15
- "mckinsey.com/case-study/insurance..." = ❌ Consultancy content = score 0-15 (unless selling TO consultancies)

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

# =============================================================================
# Query Cache for Market Leader Queries
# =============================================================================
# Cache Exa search results for frequently-used queries like "leading [sector] companies in [region]"
# These queries are identical across users with the same sector/region, so caching saves API calls.

import hashlib
from datetime import datetime as dt
from typing import TypedDict

class CacheEntry(TypedDict):
    results: List[Dict[str, Any]]
    timestamp: float
    query: str

# Module-level cache (persists across requests in same process)
_QUERY_CACHE: Dict[str, CacheEntry] = {}
_CACHE_TTL_SECONDS = 3600 * 24  # 24 hours - market leaders don't change daily


def _get_cache_key(query: str, search_type: str = "company") -> str:
    """Generate cache key for a query."""
    normalized = query.lower().strip()
    return hashlib.md5(f"{search_type}:{normalized}".encode()).hexdigest()


def _get_cached_results(query: str, search_type: str = "company") -> Optional[List[Dict[str, Any]]]:
    """Get cached results if available and not expired."""
    key = _get_cache_key(query, search_type)
    
    if key not in _QUERY_CACHE:
        return None
    
    entry = _QUERY_CACHE[key]
    age = dt.now().timestamp() - entry["timestamp"]
    
    if age > _CACHE_TTL_SECONDS:
        # Expired, remove from cache
        del _QUERY_CACHE[key]
        return None
    
    return entry["results"]


def _cache_results(query: str, results: List[Dict[str, Any]], search_type: str = "company") -> None:
    """Cache query results."""
    key = _get_cache_key(query, search_type)
    _QUERY_CACHE[key] = {
        "results": results,
        "timestamp": dt.now().timestamp(),
        "query": query
    }


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
                print(f"[PROSPECT_DISCOVERY] 📚 Reference customers provided: {input.reference_customers}", flush=True)
                logger.info(f"[PROSPECT_DISCOVERY] Processing {len(input.reference_customers)} reference customers")
                reference_context = await self._extract_reference_context(
                    reference_customers=input.reference_customers
                )
                if reference_context:
                    print(f"[PROSPECT_DISCOVERY] 📚 Reference context extracted: {reference_context[:150]}...", flush=True)
                    logger.info(f"[PROSPECT_DISCOVERY] Extracted reference context: {reference_context[:100]}...")
                else:
                    print(f"[PROSPECT_DISCOVERY] ⚠️ No reference context could be extracted", flush=True)
            else:
                print(f"[PROSPECT_DISCOVERY] 📚 No reference customers provided", flush=True)
            
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
            
            # Note: Market leaders queries are now generated by Claude as part of the 7 queries
            # (queries 6-7 are market leaders, queries 1-5 are trigger-based)
            
            print(f"[PROSPECT_DISCOVERY] 📝 TOTAL {len(queries)} QUERIES (including 2 market leaders):", flush=True)
            for i, q in enumerate(queries, 1):
                query_type = "MARKET LEADER" if i > 5 else "TRIGGER"
                print(f"  Query {i} [{query_type}]: {q[:80]}...", flush=True)
            
            # Step 3: Execute Exa searches (multi-layer)
            raw_results = await self._execute_discovery_searches(
                queries=queries,
                region=input.region,
                reference_customers=input.reference_customers
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
            print(f"[PROSPECT_DISCOVERY] 📊 Normalized to {len(normalized)} unique companies", flush=True)
            
            # Step 4.5: Filter by region if specified
            if input.region:
                before_region_filter = len(normalized)
                normalized = self._filter_by_region(normalized, input.region)
                region_filtered = before_region_filter - len(normalized)
                if region_filtered > 0:
                    print(f"[PROSPECT_DISCOVERY] 🌍 Filtered out {region_filtered} non-{input.region} results", flush=True)
            
            # Step 5: Score and analyze
            # Score fewer prospects to avoid truncation (was 50, now 30)
            scoring_limit = min(len(normalized), max(max_results + 10, 30))
            print(f"[PROSPECT_DISCOVERY] 🎯 Scoring {scoring_limit} prospects (requested: {max_results})", flush=True)
            
            scored = await self._score_prospects(
                prospects=normalized[:scoring_limit],  # Score more, filter later
                input=input,
                seller_context=seller_context
            )
            
            # Check how many prospects actually got scored
            scored_count = sum(1 for p in scored if p.fit_score > 0)
            print(f"[PROSPECT_DISCOVERY] 📊 Scored {scored_count}/{len(scored)} prospects", flush=True)
            
            # If most prospects weren't scored (scoring failed), give them default score
            # so they're not all filtered out
            if scored_count < len(scored) // 2:
                DEFAULT_SCORE = 50  # Neutral score for unscored prospects
                print(f"[PROSPECT_DISCOVERY] ⚠️ Many prospects unscored, applying default score {DEFAULT_SCORE}", flush=True)
                for p in scored:
                    if p.fit_score == 0:
                        p.fit_score = DEFAULT_SCORE
                        p.fit_reason = "Potential prospect - scoring incomplete"
            
            # Sort by fit score
            scored.sort(key=lambda p: p.fit_score, reverse=True)
            
            # Filter out low-scoring results (non-prospects)
            MIN_FIT_SCORE = 25  # Lowered further to be less aggressive
            before_filter = len(scored)
            scored = [p for p in scored if p.fit_score >= MIN_FIT_SCORE]
            filtered_out = before_filter - len(scored)
            
            if filtered_out > 0:
                print(f"[PROSPECT_DISCOVERY] 🗑️ Filtered out {filtered_out} low-scoring results (< {MIN_FIT_SCORE})", flush=True)
            
            # Apply max_results limit AFTER quality filtering
            if len(scored) > max_results:
                print(f"[PROSPECT_DISCOVERY] 📉 Limiting to top {max_results} results (had {len(scored)})", flush=True)
                scored = scored[:max_results]
            
            execution_time = (datetime.now() - start_time).total_seconds()
            
            logger.info(
                f"[PROSPECT_DISCOVERY] Completed: {len(scored)} prospects (filtered {filtered_out}), "
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
        
        # Build sector-specific context section (triggers, decision makers, etc.)
        # Note: Local language sector terms are NO LONGER hardcoded - Claude figures these out
        sector_context_section = ""
        sector_data = get_sector_context(input.sector)
        
        if sector_data:
            sector_context_section = f"""
**Sector-Specific Intelligence (for {input.sector}):**
- Key Decision Makers: {', '.join(sector_data.get('decision_makers', [])[:4])}
- Relevant Regulations/Triggers: {', '.join(sector_data.get('regulations', [])[:4])}
- Common Events: {', '.join(sector_data.get('events', [])[:4])}
- Typical Pain Points: {', '.join(sector_data.get('pain_points', [])[:4])}

USE these sector-specific terms in your queries instead of generic tech terms!
"""
            print(f"[PROSPECT_DISCOVERY] 📚 Using sector-specific context for '{input.sector}'", flush=True)
        
        prompt = QUERY_GENERATION_PROMPT.format(
            seller_context=seller_context,
            region=input.region or "Not specified",
            sector=input.sector or "Not specified",
            company_size=input.company_size or "Not specified",
            proposition=input.proposition or "Not specified",
            target_role=input.target_role or "Not specified",
            pain_point=input.pain_point or "Not specified",
            reference_section=reference_section,
            sector_context_section=sector_context_section,
            current_year=datetime.now().year
        )
        
        try:
            response = self._anthropic.messages.create(
                model="claude-sonnet-4-20250514",
                max_tokens=1024,
                messages=[{"role": "user", "content": prompt}]
            )
            
            content = response.content[0].text.strip()
            print(f"[PROSPECT_DISCOVERY] 📝 Raw Claude response: {content[:300]}...", flush=True)
            
            # Strip markdown code blocks if present (```json ... ```)
            if content.startswith("```"):
                lines = content.split("\n")
                # Remove first line (```json) and last line (```)
                lines = [l for l in lines if not l.startswith("```")]
                content = "\n".join(lines).strip()
            
            # Also handle case where response starts with [ but has trailing text
            if "[" in content:
                start = content.index("[")
                end = content.rindex("]") + 1
                content = content[start:end]
            
            # Parse JSON array
            import json
            queries = json.loads(content)
            
            if isinstance(queries, list) and len(queries) > 0:
                print(f"[PROSPECT_DISCOVERY] ✅ Generated {len(queries)} queries", flush=True)
                return queries[:7]  # Max 7 queries (5 trigger + 2 market leaders)
            
            logger.warning(f"[PROSPECT_DISCOVERY] No valid queries in response")
            return []
            
        except json.JSONDecodeError as e:
            logger.error(f"[PROSPECT_DISCOVERY] Query generation JSON parse failed: {e}")
            logger.error(f"[PROSPECT_DISCOVERY] Raw content was: {content[:500] if content else 'EMPTY'}")
            print(f"[PROSPECT_DISCOVERY] ❌ JSON parse failed: {content[:200] if content else 'EMPTY'}", flush=True)
            return []
        except Exception as e:
            logger.error(f"[PROSPECT_DISCOVERY] Query generation failed: {e}")
            print(f"[PROSPECT_DISCOVERY] ❌ Query generation error: {e}", flush=True)
            return []
    
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
    
    # Universal domains to exclude - only truly universal non-prospects
    # NOTE: We keep this minimal because:
    # - Consultancies CAN be prospects (if selling to them)
    # - Country-specific media should be handled by scoring, not hardcoded
    EXCLUDE_DOMAINS = [
        # Job/Career sites (never prospects, just noise)
        "indeed.com", "glassdoor.com", "monster.com", "ziprecruiter.com",
        # Academic aggregators (not companies)
        "researchgate.net", "academia.edu", "sciencedirect.com", "springer.com",
        # Wikipedia and general reference
        "wikipedia.org", "wikimedia.org",
        # Social media (use category="company" instead)
        "twitter.com", "facebook.com", "instagram.com", "tiktok.com",
        # Generic news aggregators
        "news.google.com", "apple.news",
    ]
    
    # Text patterns to EXCLUDE from search results (filters noise at API level)
    # Exa supports only 1 string up to 5 words, so we use most common job-related term
    EXCLUDE_TEXT_PATTERNS = ["vacature"]  # Dutch for "vacancy/job posting"
    
    # Common job-related terms to detect in content (for additional filtering)
    JOB_POSTING_INDICATORS = [
        "vacature", "vacatures", "job opening", "careers", "we're hiring",
        "join our team", "solliciteer", "apply now", "open positions"
    ]
    
    async def _execute_discovery_searches(
        self,
        queries: List[str],
        region: Optional[str] = None,
        reference_customers: Optional[List[str]] = None
    ) -> List[Dict[str, Any]]:
        """
        Execute multi-layer discovery searches using Exa.
        
        STRATEGY: Use multiple search approaches for best coverage:
        
        Layer 1: Find Similar (if reference customers provided)
                 → Uses /findSimilar to find companies similar to references
                 
        Layer 2: News Search (with date filters)
                 → Uses category="news" to find articles about companies with triggers
                 
        Layer 3: Direct Search (no category, broad)
                 → Uses type="auto" for general discovery
        """
        if not self._exa:
            return []
        
        all_results = []
        loop = asyncio.get_event_loop()
        
        # Date filter for news search (last 18 months)
        start_date = (datetime.now() - timedelta(days=540)).strftime("%Y-%m-%dT00:00:00.000Z")
        
        # =====================================================================
        # LAYER 1: Find Similar (Reference-Based Discovery)
        # =====================================================================
        if reference_customers and len(reference_customers) > 0:
            print(f"[PROSPECT_DISCOVERY] 🎯 LAYER 1: Finding similar to {len(reference_customers)} reference customers", flush=True)
            
            for ref_company in reference_customers[:3]:  # Max 3 references
                try:
                    # First, find the reference company's website
                    ref_url = await self._find_company_website(ref_company, loop)
                    
                    if ref_url:
                        print(f"[PROSPECT_DISCOVERY] 🔗 Found {ref_company} at {ref_url}", flush=True)
                        
                        # Use findSimilar to get companies in same semantic space
                        similar_results = await self._find_similar_companies(ref_url, loop)
                        all_results.extend(similar_results)
                        print(f"[PROSPECT_DISCOVERY] ✅ findSimilar returned {len(similar_results)} results for {ref_company}", flush=True)
                    else:
                        print(f"[PROSPECT_DISCOVERY] ⚠️ Could not find website for {ref_company}", flush=True)
                        
                except Exception as e:
                    logger.warning(f"[PROSPECT_DISCOVERY] Layer 1 failed for {ref_company}: {e}")
                
                await asyncio.sleep(0.3)
        
        # =====================================================================
        # LAYER 2: News Search (Trigger-Based Discovery)
        # =====================================================================
        print(f"[PROSPECT_DISCOVERY] 📰 LAYER 2: News search for triggers", flush=True)
        
        for query in queries[:4]:  # Use first 4 queries for news
            try:
                def do_news_search():
                    return self._exa.search_and_contents(
                        query=query,
                        type="auto",
                        category="news",  # News articles with date support
                        num_results=20,  # Increased from 10
                        start_published_date=start_date,
                        exclude_domains=self.EXCLUDE_DOMAINS,
                        exclude_text=self.EXCLUDE_TEXT_PATTERNS,  # Filter job postings
                        text={"max_characters": 1200},
                        # Request highlights for better signal extraction
                        # Focus on trigger events like appointments, changes, announcements
                        highlights={
                            "num_sentences": 2,
                            "highlights_per_url": 2,
                            "query": "announcement appointment change new strategy"
                        }
                    )
                
                print(f"[PROSPECT_DISCOVERY] 🔍 NEWS: {query[:60]}...", flush=True)
                response = await loop.run_in_executor(None, do_news_search)
                
                for r in response.results:
                    # Get highlights if available (better signal extraction)
                    highlights = getattr(r, 'highlights', None) or []
                    highlight_text = " | ".join(highlights) if highlights else ""
                    
                    # Prefer highlights over raw text for news (more relevant snippets)
                    text_content = getattr(r, 'text', '') or ""
                    best_snippet = highlight_text if highlight_text else text_content
                    
                    all_results.append({
                        "url": getattr(r, 'url', ''),
                        "title": getattr(r, 'title', ''),
                        "text": best_snippet,
                        "full_text": text_content,  # Keep full text for backup
                        "highlights": highlights,
                        "published_date": getattr(r, 'published_date', None) or getattr(r, 'publishedDate', ''),
                        "matched_query": query,
                        "source_type": "news"
                    })
                
                print(f"[PROSPECT_DISCOVERY] ✅ NEWS returned {len(response.results)} results", flush=True)
                
            except Exception as e:
                logger.warning(f"[PROSPECT_DISCOVERY] Layer 2 news search failed: {e}")
            
            await asyncio.sleep(0.3)
        
        # =====================================================================
        # LAYER 3: Direct Search (Broad Discovery) - PARALLELIZED
        # =====================================================================
        # Run direct searches in parallel with rate limiting for better performance
        print(f"[PROSPECT_DISCOVERY] 🌐 LAYER 3: Direct search (broad) - {len(queries)} queries parallel", flush=True)
        
        # Semaphore to limit concurrent requests (Exa rate limiting)
        MAX_CONCURRENT = 4
        semaphore = asyncio.Semaphore(MAX_CONCURRENT)
        
        async def do_direct_search_parallel(query: str, idx: int) -> List[Dict[str, Any]]:
            """Execute a single direct search with rate limiting."""
            async with semaphore:
                try:
                    def do_search():
                        return self._exa.search_and_contents(
                            query=query,
                            type="auto",
                            num_results=15,
                            start_published_date=start_date,
                            exclude_domains=self.EXCLUDE_DOMAINS,
                            exclude_text=self.EXCLUDE_TEXT_PATTERNS,
                            text={"max_characters": 1200}
                        )
                    
                    response = await loop.run_in_executor(None, do_search)
                    
                    results = []
                    for r in response.results:
                        results.append({
                            "url": getattr(r, 'url', ''),
                            "title": getattr(r, 'title', ''),
                            "text": getattr(r, 'text', ''),
                            "published_date": getattr(r, 'published_date', None) or getattr(r, 'publishedDate', ''),
                            "matched_query": query,
                            "source_type": "direct"
                        })
                    
                    return results
                    
                except Exception as e:
                    logger.warning(f"[PROSPECT_DISCOVERY] Direct search {idx} failed: {e}")
                    return []
        
        # Execute all direct searches in parallel
        direct_tasks = [
            do_direct_search_parallel(query, idx) 
            for idx, query in enumerate(queries)
        ]
        direct_results_lists = await asyncio.gather(*direct_tasks)
        
        # Flatten and add to all_results
        direct_count = 0
        for results_list in direct_results_lists:
            all_results.extend(results_list)
            direct_count += len(results_list)
        
        print(f"[PROSPECT_DISCOVERY] ✅ DIRECT returned {direct_count} total results from {len(queries)} parallel queries", flush=True)
        
        # =====================================================================
        # LAYER 4: Company Search (Market Leaders with category="company")
        # =====================================================================
        # This finds actual company websites, not news articles about them
        # Note: category="company" doesn't support date filters, but that's OK
        # for market leaders - we want established companies
        # 
        # CACHING: These queries are identical for all users with same sector/region
        # so we cache results to save API calls and improve response time
        market_leader_queries = [q for q in queries if any(
            term in q.lower() for term in ['leading', 'prominent', 'top', 'biggest', 'largest', 'major']
        )]
        
        if market_leader_queries:
            print(f"[PROSPECT_DISCOVERY] 🏢 LAYER 4: Company search for {len(market_leader_queries)} market leader queries", flush=True)
            
            cache_hits = 0
            for query in market_leader_queries:
                try:
                    # Check cache first
                    cached = _get_cached_results(query, "company")
                    if cached is not None:
                        all_results.extend(cached)
                        cache_hits += 1
                        print(f"[PROSPECT_DISCOVERY] 💾 CACHE HIT: {query[:60]}... ({len(cached)} results)", flush=True)
                        continue
                    
                    # Not in cache, fetch from Exa
                    def do_company_search():
                        return self._exa.search_and_contents(
                            query=query,
                            type="auto",
                            category="company",  # Find actual company websites!
                            num_results=20,
                            # Note: no date filter - not supported with category="company"
                            text={"max_characters": 1000}
                        )
                    
                    print(f"[PROSPECT_DISCOVERY] 🔍 COMPANY: {query[:60]}...", flush=True)
                    response = await loop.run_in_executor(None, do_company_search)
                    
                    # Process and cache results
                    query_results = []
                    for r in response.results:
                        result = {
                            "url": getattr(r, 'url', ''),
                            "title": getattr(r, 'title', ''),
                            "text": getattr(r, 'text', ''),
                            "published_date": None,  # Company category doesn't return dates
                            "matched_query": query,
                            "source_type": "company"  # Mark as company result
                        }
                        query_results.append(result)
                        all_results.append(result)
                    
                    # Cache the results for future queries
                    _cache_results(query, query_results, "company")
                    
                    print(f"[PROSPECT_DISCOVERY] ✅ COMPANY returned {len(response.results)} results (cached)", flush=True)
                    
                except Exception as e:
                    logger.warning(f"[PROSPECT_DISCOVERY] Layer 4 company search failed for query: {e}")
                
                await asyncio.sleep(0.3)
            
            if cache_hits > 0:
                print(f"[PROSPECT_DISCOVERY] 💾 Cache saved {cache_hits} Exa API calls", flush=True)
        
        print(f"[PROSPECT_DISCOVERY] 📊 TOTAL raw results: {len(all_results)}", flush=True)
        return all_results
    
    async def _find_company_website(self, company_name: str, loop) -> Optional[str]:
        """Find the main website URL for a company using Exa search."""
        try:
            def do_search():
                return self._exa.search(
                    query=f'"{company_name}" official website homepage',
                    type="auto",
                    num_results=3
                )
            
            response = await loop.run_in_executor(None, do_search)
            
            if response.results:
                # Return the first result's URL (most relevant)
                url = response.results[0].url
                # Extract root domain
                return self._get_root_url(url)
            
            return None
            
        except Exception as e:
            logger.warning(f"[PROSPECT_DISCOVERY] Could not find website for {company_name}: {e}")
            return None
    
    async def _find_similar_companies(self, reference_url: str, loop) -> List[Dict[str, Any]]:
        """Find companies similar to the reference URL using Exa findSimilar."""
        try:
            def do_find_similar():
                return self._exa.find_similar_and_contents(
                    url=reference_url,
                    num_results=25,  # Increased from 15 for better coverage
                    exclude_domains=self.EXCLUDE_DOMAINS,  # Works with findSimilar!
                    text={"max_characters": 1000}
                )
            
            response = await loop.run_in_executor(None, do_find_similar)
            
            results = []
            for r in response.results:
                results.append({
                    "url": getattr(r, 'url', ''),
                    "title": getattr(r, 'title', ''),
                    "text": getattr(r, 'text', ''),
                    "published_date": getattr(r, 'published_date', None) or getattr(r, 'publishedDate', ''),
                    "matched_query": f"Similar to: {reference_url}",
                    "source_type": "similar"
                })
            
            return results
            
        except Exception as e:
            logger.warning(f"[PROSPECT_DISCOVERY] findSimilar failed for {reference_url}: {e}")
            return []
    
    def _normalize_results(
        self,
        raw_results: List[Dict[str, Any]]
    ) -> List[DiscoveredProspect]:
        """
        Normalize and deduplicate raw search results.
        
        Extracts company names from URLs and content,
        deduplicates by domain/company name.
        
        IMPORTANT: 
        - Prioritizes "company" and "similar" source types over "news"
        - MERGES signals from multiple sources for the same company
          (e.g., company website + news article = richer context for scoring)
        """
        # Phase 1: Group all results by company (domain-based)
        company_groups: Dict[str, List[Dict[str, Any]]] = {}
        domain_to_company: Dict[str, str] = {}
        
        source_priority = {"company": 0, "similar": 1, "direct": 2, "news": 3}
        
        for r in raw_results:
            url = r.get("url", "")
            title = r.get("title", "")
            text = r.get("text", "")
            
            # Extract domain
            domain = self._extract_domain(url)
            if not domain:
                continue
            
            # Skip common news/aggregator sites
            if self._is_aggregator_domain(domain):
                continue
            
            # Skip job postings (additional check beyond Exa's excludeText)
            if self._is_job_posting(title, text):
                continue
            
            # Try to extract company name
            company_name = self._extract_company_name(url, title, text)
            if not company_name:
                continue
            
            # Normalize company name for grouping
            normalized_name = company_name.lower().strip()
            
            # Check if we've seen this domain or company name before
            # Use domain as primary key, company name as secondary
            group_key = domain_to_company.get(domain) or normalized_name
            
            if group_key not in company_groups:
                company_groups[group_key] = []
                domain_to_company[domain] = group_key
            
            # Add result to group with metadata
            company_groups[group_key].append({
                "url": url,
                "domain": domain,
                "title": title,
                "text": text,
                "published_date": r.get("published_date"),
                "matched_query": r.get("matched_query"),
                "source_type": r.get("source_type", "direct"),
                "company_name": company_name,
                "priority": source_priority.get(r.get("source_type", "direct"), 2)
            })
        
        # Phase 2: For each company, pick best primary source and merge signals
        prospects = []
        
        for group_key, results in company_groups.items():
            # Sort by priority (company > similar > direct > news)
            results.sort(key=lambda x: x["priority"])
            
            # Best result becomes primary source
            primary = results[0]
            
            # Extract additional signals from other sources
            additional_signals = []
            seen_snippets = {primary["text"][:200] if primary["text"] else ""}
            
            for r in results[1:]:  # Skip primary
                snippet = r["text"][:500] if r["text"] else ""
                snippet_key = snippet[:200] if snippet else ""
                
                # Skip if snippet is too similar to one we've seen
                if snippet_key and snippet_key not in seen_snippets:
                    seen_snippets.add(snippet_key)
                    additional_signals.append({
                        "source_type": r["source_type"],
                        "title": r["title"],
                        "snippet": snippet,
                        "url": r["url"],
                        "date": r["published_date"],
                        "query": r["matched_query"]
                    })
            
            # Infer region from best source
            inferred_region = self._infer_region(primary["url"], primary["text"])
            
            # Create prospect with merged signals
            prospect = DiscoveredProspect(
                company_name=primary["company_name"],
                website=f"https://{primary['domain']}" if not primary["url"].startswith("http") else self._get_root_url(primary["url"]),
                linkedin_url=self._extract_linkedin(primary["text"]),
                inferred_region=inferred_region,
                source_url=primary["url"],
                source_title=primary["title"],
                source_snippet=primary["text"][:500] if primary["text"] else None,
                source_published_date=primary["published_date"],
                matched_query=primary["matched_query"],
                source_type=primary["source_type"],
                additional_signals=additional_signals
            )
            
            prospects.append(prospect)
        
        # Log signal merging stats
        multi_signal_count = sum(1 for p in prospects if len(p.additional_signals) > 0)
        total_signals = sum(1 + len(p.additional_signals) for p in prospects)
        if multi_signal_count > 0:
            print(f"[PROSPECT_DISCOVERY] 🔗 Merged signals: {multi_signal_count}/{len(prospects)} companies have multiple signals ({total_signals} total)", flush=True)
        
        return prospects
    
    async def _score_prospects(
        self,
        prospects: List[DiscoveredProspect],
        input: DiscoveryInput,
        seller_context: str
    ) -> List[DiscoveredProspect]:
        """
        Score prospects using Claude for fit analysis.
        
        Uses batch processing to handle large sets without truncation:
        - Batch size of 25 prospects per API call
        - Parallel processing of batches for speed
        - Merges results from all batches
        """
        if not prospects or not self._anthropic:
            return prospects
        
        import json
        
        # Batch configuration
        BATCH_SIZE = 25  # Safe size to avoid response truncation
        
        # Split into batches
        batches = [
            prospects[i:i + BATCH_SIZE] 
            for i in range(0, len(prospects), BATCH_SIZE)
        ]
        
        if len(batches) > 1:
            print(f"[PROSPECT_DISCOVERY] 📦 Scoring {len(prospects)} prospects in {len(batches)} batches of {BATCH_SIZE}", flush=True)
        
        # Score each batch
        all_scored = []
        for batch_idx, batch in enumerate(batches):
            try:
                scored_batch = await self._score_batch(
                    batch, input, seller_context, batch_idx + 1, len(batches)
                )
                all_scored.extend(scored_batch)
            except Exception as e:
                logger.error(f"[PROSPECT_DISCOVERY] Batch {batch_idx + 1} scoring failed: {e}")
                # Return unscored batch items
                all_scored.extend(batch)
        
        return all_scored
    
    async def _score_batch(
        self,
        prospects: List[DiscoveredProspect],
        input: DiscoveryInput,
        seller_context: str,
        batch_num: int = 1,
        total_batches: int = 1
    ) -> List[DiscoveredProspect]:
        """Score a single batch of prospects."""
        import json
        
        # Prepare prospects for scoring - include all signals for richer context
        prospects_data = []
        for p in prospects:
            prospect_data = {
                "company_name": p.company_name,
                "website": p.website,
                "primary_source": {
                    "type": p.source_type or "unknown",
                    "title": p.source_title,
                    "snippet": p.source_snippet,
                    "date": p.source_published_date
                }
            }
            
            # Add additional signals if available (merged from multiple sources)
            if p.additional_signals:
                prospect_data["additional_signals"] = [
                    {
                        "type": s.get("source_type"),
                        "title": s.get("title"),
                        "snippet": s.get("snippet", "")[:300],  # Limit to save tokens
                        "date": s.get("date")
                    }
                    for s in p.additional_signals[:3]  # Max 3 additional signals
                ]
            
            prospects_data.append(prospect_data)
        
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
                max_tokens=8000,  # Sufficient for 25 prospects
                messages=[{"role": "user", "content": prompt}]
            )
            
            content = response.content[0].text.strip()
            
            # Strip markdown code blocks if present
            if content.startswith("```"):
                lines = content.split("\n")
                lines = [l for l in lines if not l.startswith("```")]
                content = "\n".join(lines)
            
            # Parse JSON
            scores = json.loads(content)
            
            # Apply scores to prospects
            score_map = {s["company_name"]: s for s in scores}
            
            scored_count = 0
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
                    scored_count += 1
            
            if total_batches > 1:
                print(f"[PROSPECT_DISCOVERY] ✅ Batch {batch_num}/{total_batches}: scored {scored_count}/{len(prospects)}", flush=True)
            
            return prospects
            
        except json.JSONDecodeError as e:
            logger.error(f"[PROSPECT_DISCOVERY] Batch {batch_num} JSON parse failed: {e}")
            logger.error(f"[PROSPECT_DISCOVERY] Raw content was: {content[:500] if content else 'EMPTY'}")
            
            # Try to recover partial JSON
            return self._recover_partial_scores(prospects, content)
            
        except Exception as e:
            logger.error(f"[PROSPECT_DISCOVERY] Batch {batch_num} scoring failed: {e}")
            return prospects
    
    def _recover_partial_scores(
        self,
        prospects: List[DiscoveredProspect],
        content: str
    ) -> List[DiscoveredProspect]:
        """Attempt to recover scores from truncated JSON response."""
        import json
        
        try:
            # Find all complete JSON objects in the response
            complete_objects = []
            brace_count = 0
            start_idx = None
            
            for i, char in enumerate(content):
                if char == '{':
                    if brace_count == 0:
                        start_idx = i
                    brace_count += 1
                elif char == '}':
                    brace_count -= 1
                    if brace_count == 0 and start_idx is not None:
                        obj_str = content[start_idx:i+1]
                        try:
                            obj = json.loads(obj_str)
                            if "company_name" in obj:  # Validate it's a score object
                                complete_objects.append(obj)
                        except:
                            pass
                        start_idx = None
            
            if complete_objects:
                print(f"[PROSPECT_DISCOVERY] ⚠️ Recovered {len(complete_objects)} scored prospects from truncated response", flush=True)
                score_map = {s["company_name"]: s for s in complete_objects}
                
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
                
        except Exception as recovery_error:
            logger.error(f"[PROSPECT_DISCOVERY] Recovery also failed: {recovery_error}")
        
        return prospects
    
    # =========================================================================
    # Helper Methods
    # =========================================================================
    
    def _filter_by_region(
        self,
        prospects: List[DiscoveredProspect],
        target_region: str
    ) -> List[DiscoveredProspect]:
        """
        Filter prospects to only include those matching the target region.
        
        Uses multiple signals:
        1. URL TLD (.nl, .de, etc.)
        2. Keywords in content/URL
        3. Language detection (Dutch content = likely NL company)
        4. Inferred region from LLM
        """
        # Map of region names to acceptable TLDs, keywords, and languages
        region_config = {
            # Netherlands
            "nederland": {
                "tlds": [".nl"],
                "keywords": ["netherlands", "nederland", "dutch", "amsterdam", "rotterdam", "utrecht", "eindhoven"],
                "languages": ["nl"],  # Dutch
            },
            "netherlands": {
                "tlds": [".nl"],
                "keywords": ["netherlands", "nederland", "dutch", "amsterdam", "rotterdam"],
                "languages": ["nl"],
            },
            "nl": {
                "tlds": [".nl"],
                "keywords": ["netherlands", "nederland", "dutch"],
                "languages": ["nl"],
            },
            # Germany
            "germany": {
                "tlds": [".de"],
                "keywords": ["germany", "deutschland", "german", "munich", "berlin", "hamburg"],
                "languages": ["de"],
            },
            "deutschland": {
                "tlds": [".de"],
                "keywords": ["germany", "deutschland", "german"],
                "languages": ["de"],
            },
            "dach": {
                "tlds": [".de", ".at", ".ch"],
                "keywords": ["germany", "austria", "switzerland", "deutschland", "österreich", "schweiz"],
                "languages": ["de"],
            },
            # Belgium
            "belgium": {
                "tlds": [".be"],
                "keywords": ["belgium", "belgie", "belgian", "brussels", "bruxelles"],
                "languages": ["nl", "fr"],  # Both Dutch and French
            },
            "belgie": {
                "tlds": [".be"],
                "keywords": ["belgium", "belgie", "belgian"],
                "languages": ["nl", "fr"],
            },
            # Benelux
            "benelux": {
                "tlds": [".nl", ".be", ".lu"],
                "keywords": ["netherlands", "belgium", "luxembourg", "nederland", "belgie"],
                "languages": ["nl", "fr"],
            },
            # UK
            "uk": {
                "tlds": [".uk", ".co.uk"],
                "keywords": ["united kingdom", "british", "london", "england", "scotland"],
                "languages": ["en"],  # Note: en is too broad, so we rely more on TLD/keywords
            },
            "united kingdom": {
                "tlds": [".uk", ".co.uk"],
                "keywords": ["united kingdom", "british", "london"],
                "languages": ["en"],
            },
            # France
            "france": {
                "tlds": [".fr"],
                "keywords": ["france", "french", "paris", "lyon", "marseille"],
                "languages": ["fr"],
            },
        }
        
        # Normalize target region
        target_lower = target_region.lower().strip()
        
        # Get config for this region
        config = region_config.get(target_lower)
        if not config:
            # Unknown region, be permissive
            logger.warning(f"[PROSPECT_DISCOVERY] Unknown region '{target_region}', skipping filter")
            return prospects
        
        tlds = config["tlds"]
        keywords = config["keywords"]
        expected_languages = config["languages"]
        
        # Filter prospects
        filtered = []
        for p in prospects:
            url = (p.website or p.source_url or "").lower()
            
            # Check 1: TLD match (strongest signal)
            tld_match = any(url.endswith(tld) or f"{tld}/" in url for tld in tlds)
            if tld_match:
                filtered.append(p)
                continue
            
            # Check 2: Keywords in URL or inferred_region
            keyword_match = False
            for keyword in keywords:
                if keyword in url:
                    keyword_match = True
                    break
                if p.inferred_region and keyword in p.inferred_region.lower():
                    keyword_match = True
                    break
            
            if keyword_match:
                filtered.append(p)
                continue
            
            # Check 3: Language detection (for .com domains that might be local companies)
            # Only check if we have content and didn't match by TLD/keyword
            if p.source_snippet and len(p.source_snippet) > 50:
                detected_lang = self._detect_language(p.source_snippet)
                if detected_lang and detected_lang in expected_languages:
                    # Language matches, but be careful with English (too common)
                    if detected_lang != "en":  # Non-English languages are strong signals
                        filtered.append(p)
                        continue
        
        return filtered
    
    def _detect_language(self, text: str) -> Optional[str]:
        """
        Detect the language of text content.
        
        Returns ISO 639-1 language code (e.g., 'nl', 'de', 'en', 'fr').
        Returns None if detection fails or text is too short.
        """
        if not text or len(text) < 50:
            return None
        
        try:
            from langdetect import detect, LangDetectException
            # Use first 500 chars for faster detection
            sample = text[:500]
            return detect(sample)
        except LangDetectException:
            return None
        except ImportError:
            # langdetect not installed, skip language detection
            logger.warning("[PROSPECT_DISCOVERY] langdetect not installed, skipping language detection")
            return None
        except Exception as e:
            logger.debug(f"[PROSPECT_DISCOVERY] Language detection failed: {e}")
            return None
    
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
    
    def _is_job_posting(self, title: str, text: str) -> bool:
        """
        Check if content appears to be a job posting rather than company info.
        
        Job postings are filtered because:
        1. They're not trigger events for buying
        2. They pollute results with recruitment noise
        3. The "company" is often just looking for staff, not solutions
        """
        combined = f"{title} {text}".lower()
        
        # Strong indicators this is a job posting
        job_indicators = self.JOB_POSTING_INDICATORS
        
        # URL patterns that indicate career pages
        career_url_patterns = [
            "/careers", "/jobs", "/vacatures", "/werken-bij",
            "/job/", "/vacancy/", "/solliciteer"
        ]
        
        # Check for job indicators in content
        job_matches = sum(1 for ind in job_indicators if ind in combined)
        
        # If 2+ job indicators found, likely a job posting
        if job_matches >= 2:
            return True
        
        # Check if title strongly indicates job posting
        title_lower = title.lower() if title else ""
        if any(ind in title_lower for ind in ["vacature", "job opening", "we're hiring", "join our"]):
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

