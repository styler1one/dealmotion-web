"""
Claude Web Search integration for 360° prospect research.

OPTIMIZED TWO-PHASE APPROACH:
- Phase 1: Web search with minimal prompt (~500 tokens per search)
- Phase 2: Analysis with full 360° template + all results (~45k tokens)

This reduces total token usage by ~80% compared to sending the full prompt with every search.

Previous approach: 262,000 tokens (~$1.05 per research)
New approach: ~50,000 tokens (~$0.20 per research)
"""
import os
import logging
from datetime import datetime
from typing import Dict, Any, Optional, List
from anthropic import AsyncAnthropic
from app.i18n.utils import get_language_instruction, get_country_iso_code
from app.i18n.config import DEFAULT_LANGUAGE

logger = logging.getLogger(__name__)


class ClaudeResearcher:
    """Research using Claude with optimized two-phase web search."""
    
    def __init__(self):
        """Initialize Claude API."""
        api_key = os.getenv("ANTHROPIC_API_KEY")
        if not api_key:
            raise ValueError("ANTHROPIC_API_KEY environment variable not set")
        
        self.client = AsyncAnthropic(api_key=api_key)
        
        # Pre-build static prompt template for analysis phase
        self._analysis_template = self._build_analysis_template()
        
        # Cache seller context per organization for efficiency
        self._seller_context_cache: Dict[str, str] = {}
    
    def _build_search_prompt(
        self,
        company_name: str,
        country: Optional[str],
        city: Optional[str],
        current_date: str
    ) -> str:
        """
        Build MINIMAL prompt for web search phase (~500 tokens).
        
        This prompt is sent with EVERY web search call, so keeping it small
        saves significant tokens. The detailed analysis comes in Phase 2.
        """
        location = f" in {city}, {country}" if city and country else f" in {country}" if country else ""
        
        return f"""You are a B2B sales research assistant. Search thoroughly for information about "{company_name}"{location}.

TODAY'S DATE: {current_date}

SEARCH STRATEGY - Execute these searches systematically:

1. COMPANY BASICS:
   - "{company_name}" official website about
   - "{company_name}" Wikipedia OR Crunchbase
   - site:linkedin.com/company/ "{company_name}"

2. FINANCIALS & SIZE:
   - "{company_name}" revenue funding investment
   - "{company_name}" employees OR headcount

3. LEADERSHIP (CRITICAL - search extensively):
   - "{company_name}" CEO founder "managing director"
   - "{company_name}" CFO CTO COO CMO
   - site:linkedin.com/in "{company_name}" CEO director
   - "{company_name}" management team leadership

4. RECENT NEWS (last 90 days from {current_date}):
   - "{company_name}" news announcement {datetime.now().year}
   - "{company_name}" partnership expansion hiring

5. MARKET POSITION:
   - "{company_name}" competitors comparison
   - "{company_name}" customers clients

INSTRUCTIONS:
- Execute ALL search categories above
- Collect as much information as possible
- Include full LinkedIn URLs for all people found
- Note the source/URL for each piece of information
- Focus on FACTS, not opinions

Return all findings in a structured format with clear source attribution."""

    def _build_analysis_template(self) -> str:
        """
        Build the FULL analysis template (~3,500 tokens).
        
        This is only sent ONCE in Phase 2, with all search results.
        Contains the complete 360° prospect intelligence structure.
        """
        return '''You are an elite B2B sales intelligence analyst. Your research saves sales professionals DAYS of manual work.

Based on the web search results provided below, generate a comprehensive 360° PROSPECT INTELLIGENCE REPORT.

═══════════════════════════════════════════════════════════════════════════════
                    360° PROSPECT INTELLIGENCE REPORT
═══════════════════════════════════════════════════════════════════════════════


━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
SECTION 1: EXECUTIVE SNAPSHOT
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

## 1.1 In One Sentence
[A sharp, insight-packed sentence: WHO they are + WHAT makes them interesting + WHY timing might be right]

## 1.2 At a Glance

| Dimension | Assessment | Evidence |
|-----------|------------|----------|
| **Opportunity Fit** | 🟢 High / 🟡 Medium / 🔴 Low | [One-line reasoning based on what seller offers] |
| **Timing Signal** | 🟢 Act Now / 🟡 Nurture / 🔴 Wait | [Trigger or reason] |
| **Company Stage** | 🚀 Startup / 📈 Scale-up / 🏢 SMB / 🏛️ Enterprise | [Employee count, maturity] |
| **Financial Health** | 🟢 Strong / 🟡 Stable / 🔴 Challenged / ⚪ Unknown | [Signals] |
| **Industry Match** | 🟢 Core Target / 🟡 Adjacent / 🔴 Outside Focus | [Based on seller context] |
| **Decision Complexity** | Simple / Medium / Complex | [Org size, stakeholders] |
| **Primary Risk** | [Single biggest obstacle to deal success] | |

## 1.3 Why This Company Matters
[2-3 sentences connecting their situation to what the seller offers. Be specific about the opportunity.]


━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
SECTION 2: COMPANY DEEP DIVE
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

## 2.1 Company Identity

| Element | Details | Source |
|---------|---------|--------|
| **Legal Name** | [Full registered name] | |
| **Trading Name** | [If different from legal] | |
| **Tagline/Slogan** | [Their positioning statement] | |
| **Industry** | [Primary] → [Sub-sector] | |
| **Founded** | [Year] | |
| **Headquarters** | [City, Country] | |
| **Other Locations** | [Offices, countries] | |
| **Website** | [URL] | |
| **LinkedIn** | [Company page URL] | |

## 2.2 Corporate Structure

| Element | Details |
|---------|---------|
| **Ownership Type** | Private / Public / PE-backed / VC-backed / Family / Government |
| **Parent Company** | [If subsidiary - who owns them] |
| **Subsidiaries** | [Companies they own] |
| **Key Investors** | [VC/PE firms, notable investors] |

## 2.3 Company Size & Scale

| Metric | Current | Trend | Source |
|--------|---------|-------|--------|
| **Employees** | [Number] | 📈 Growing / ➡️ Stable / 📉 Shrinking | |
| **Revenue** | [Amount or range] | [If known] | |
| **Funding Raised** | [Total if known] | [Latest round] | |

## 2.4 Business Model

### What They Do
[3-4 sentences explaining their core business. Be specific - what problem do they solve for whom?]

### How They Make Money
| Revenue Stream | Description | Importance |
|----------------|-------------|------------|
| [Stream 1] | [How it works] | Primary / Secondary |

### Their Customers
| Aspect | Details |
|--------|---------|
| **Business Model** | B2B / B2C / B2B2C / Marketplace / SaaS / Services |
| **Customer Segment** | Enterprise / Mid-market / SMB / Consumer |
| **Key Verticals** | [Industries they sell to] |
| **Named Customers** | [Logos, testimonials found] |


━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
SECTION 3: PEOPLE & POWER (Decision Making Unit) 🔴 CRITICAL
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

## 3.1 Executive Leadership (C-Suite)

| Name | Title | Background | LinkedIn | Tenure | Notes |
|------|-------|------------|----------|--------|-------|
| [Full Name] | CEO / Managing Director / Founder | [Previous roles, education] | [Full URL] | [Years] | [Founder? New?] |
| [Full Name] | CFO / Finance Director | [Background] | [URL] | | 💰 Budget authority |
| [Full Name] | CTO / CIO | [Background] | [URL] | | 🔧 Tech decisions |
| [Full Name] | COO / Operations | [Background] | [URL] | | ⚙️ Process owner |
| [Full Name] | CMO / Marketing | [Background] | [URL] | | 📣 Brand/demand |
| [Full Name] | CHRO / People | [Background] | [URL] | | 👥 People decisions |

## 3.2 Senior Leadership (VPs, Directors, Heads)

| Name | Title | Department | LinkedIn | Potential Relevance |
|------|-------|------------|----------|---------------------|
| [Name] | VP of [X] | [Dept] | [URL] | [Why might they care?] |
| [Name] | Director of [X] | [Dept] | [URL] | |

## 3.3 Board of Directors / Supervisory Board

| Name | Role | Affiliation | Background |
|------|------|-------------|------------|
| [Name] | Chairman | [Company/Fund] | [Background] |
| [Name] | Board Member | | |

## 3.4 Decision-Making Dynamics

| Aspect | Assessment | Evidence |
|--------|------------|----------|
| **Decision Culture** | Top-down / Consensus / Committee / Founder-led | [Signals] |
| **Budget Authority** | [Who controls spend] | |
| **Likely Champions** | [Roles most aligned with your value] | |
| **Potential Blockers** | [Roles that might resist] | |

## 3.5 Recent Leadership Changes (Last 12 months)

| Date | Change | Name | From → To | Implication |
|------|--------|------|-----------|-------------|
| [Date] | New Hire / Departure | [Name] | [Context] | [What this means] |

**⚠️ COVERAGE NOTE**: If leadership information is limited, state clearly: "Limited leadership data available via web search. Recommend LinkedIn Sales Navigator for complete org mapping."


━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
SECTION 4: WHAT'S HAPPENING NOW (Triggers & Signals)
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

## 4.1 Recent News & Announcements (Last 90 Days)

| Date | Headline | Type | Source | Sales Relevance |
|------|----------|------|--------|-----------------|
| [DD MMM YYYY] | [What happened] | 💰/📈/👥/🚀/🤝/⚠️ | [Publication] | [Why this matters] |

**Event Types**: 💰 Funding | 📈 Growth | 👥 People | 🚀 Product | 🤝 Partnership | ⚠️ Challenge

## 4.2 Funding & Investment History

| Date | Round | Amount | Lead Investor(s) | What It Signals |
|------|-------|--------|------------------|-----------------|
| [Date] | [Series X] | [Amount] | [Investors] | [Growth mode?] |

## 4.3 Hiring Signals 🔥 HIGH VALUE

| Department | # of Roles | What This Signals |
|------------|------------|-------------------|
| [Engineering] | [X] | [Scaling product?] |
| [Sales] | [X] | [Expansion?] |

### Key Hiring Observations
- **Fastest Growing Teams**: [Which departments are scaling]
- **Strategic Hires**: [Executive/leadership searches]
- **Hiring Velocity**: [Aggressive / Steady / Slowing / Freezing]

## 4.4 Strategic Initiatives
- [Initiative 1: e.g., "Digital Transformation Program"]
- [Initiative 2: e.g., "International Expansion"]

## 4.5 Interpretation: What's Really Going On
[3-4 sentences synthesizing the signals: What are their priorities? What pressure are they under?]


━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
SECTION 5: MARKET & COMPETITIVE POSITION
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

## 5.1 Market Position

| Aspect | Assessment |
|--------|------------|
| **Market Role** | 🥇 Leader / 🥈 Challenger / 🥉 Niche / 🆕 Newcomer |
| **Market Trajectory** | 📈 Growing / ➡️ Stable / 📉 Declining |

## 5.2 Competitive Landscape

| Competitor | Positioning | vs. This Company | Threat Level |
|------------|-------------|------------------|--------------|
| [Competitor 1] | [Their position] | [How they compare] | High/Med/Low |
| [Competitor 2] | | | |

## 5.3 Technology Stack & Vendors

| Category | Known Tools/Vendors | Source |
|----------|---------------------|--------|
| CRM | [Salesforce, HubSpot, etc.] | |
| ERP/Finance | [SAP, Oracle, etc.] | |
| Cloud/Infra | [AWS, Azure, GCP] | |


━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
SECTION 6: COMMERCIAL OPPORTUNITY ASSESSMENT
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

## 6.1 BANT Qualification

| Signal | Evidence | Score | Confidence |
|--------|----------|-------|------------|
| **Budget** | [Funding, revenue signals] | 🟢/🟡/🔴/⚪ | High/Med/Low |
| **Authority** | [Decision makers identified] | 🟢/🟡/🔴/⚪ | |
| **Need** | [Pain points, challenges] | 🟢/🟡/🔴/⚪ | |
| **Timeline** | [Urgency signals] | 🟢/🟡/🔴/⚪ | |

**BANT Summary**: [X/4 strong signals] - [One sentence interpretation]

## 6.2 Potential Pain Points

| Pain Point | Evidence/Signal | Connection to Seller's Offering |
|------------|-----------------|--------------------------------|
| [Pain 1] | [What suggests this] | [How seller could help] |
| [Pain 2] | | |

## 6.3 Opportunity Triggers

| Trigger | Type | Timing | Why It Matters |
|---------|------|--------|----------------|
| [Trigger 1] | 💰/📈/👥/🚀 | [Recent/Imminent] | [Creates urgency for...] |

## 6.4 Relevant Use Cases

| Use Case | Their Situation | How Seller Helps |
|----------|-----------------|------------------|
| [Use Case 1] | [Specific to them] | [Specific value] |


━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
SECTION 7: STRATEGIC APPROACH
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

## 7.1 Priority Targets

| Priority | Name | Role | Why Target Them | Entry Angle |
|----------|------|------|-----------------|-------------|
| 1️⃣ | [Name] | [Title] | [Role relevance] | [Topic to lead with] |
| 2️⃣ | [Name] | [Title] | [Why second] | |

## 7.2 Entry Strategy

| Aspect | Recommendation |
|--------|----------------|
| **Primary Entry Point** | [Department/role to target first] |
| **Why This Entry** | [Strategic reasoning] |
| **Avoid Starting With** | [Who NOT to approach first] |

## 7.3 Key Topics to Explore
1. [Topic aligned with recent news/trigger]
2. [Topic aligned with pain point]
3. [Topic that differentiates seller]

## 7.4 Validation Questions

| Category | Question | Why Ask This |
|----------|----------|--------------|
| **Situation** | [Question to confirm current state] | [What you're validating] |
| **Problem** | [Question to explore challenges] | |
| **Priority** | [Question about importance/timing] | |


━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
SECTION 8: RISKS, OBSTACLES & WATCHOUTS
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

## 8.1 Potential Obstacles

| Obstacle | Likelihood | Mitigation |
|----------|------------|------------|
| [Budget constraints] | High/Med/Low | [How to navigate] |
| [Complex decision process] | | |

## 8.2 Things to AVOID ⚠️

| Topic/Approach | Why Avoid | Instead Do |
|----------------|-----------|------------|
| [Sensitive topic 1] | [Reason] | [Better approach] |

## 8.3 Information Gaps (Must Verify)
- [ ] [Gap 1 - e.g., "Current vendor for X"]
- [ ] [Gap 2 - e.g., "Budget cycle timing"]


━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
SECTION 9: RESEARCH QUALITY & METADATA
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

## 9.1 Source Coverage

| Source Type | Status | Quality |
|-------------|--------|---------|
| Company Website | ✅/❌ | Rich/Basic/Poor |
| LinkedIn Company | ✅/❌ | |
| LinkedIn People | ✅/❌ | [X people found] |
| Recent News | ✅/❌ | [X articles] |
| Job Postings | ✅/❌ | [X listings] |

## 9.2 Research Confidence

| Section | Confidence |
|---------|------------|
| Company Basics | 🟢/🟡/🔴 |
| Leadership Mapping | 🟢/🟡/🔴 |
| Recent Developments | 🟢/🟡/🔴 |
| Commercial Fit | 🟢/🟡/🔴 |

**Overall Confidence**: 🟢 High / 🟡 Medium / 🔴 Low


═══════════════════════════════════════════════════════════════════════════════
                              END OF REPORT
═══════════════════════════════════════════════════════════════════════════════


**QUALITY RULES - STRICTLY FOLLOW**:
1. Include FULL LinkedIn URLs for every person found
2. Be factual - if not found, say "Not found" not invented data
3. Include source URLs for key claims
4. This is RESEARCH, not meeting preparation - no conversation scripts
5. Focus on commercially actionable intelligence
6. When data is limited, be explicit about gaps
7. Quality over completeness - accurate partial data beats speculative full data'''

    def _build_seller_context_section(self, seller_context: Dict[str, Any]) -> str:
        """
        Build seller context section for analysis phase.
        
        OPTIMIZED for research quality and token efficiency (~235 tokens):
        - Products with benefits for use case matching
        - ICP pain points for pain matching
        - Target decision makers for right targeting
        """
        if not seller_context or not seller_context.get("has_context"):
            return ""
        
        # Products with benefits
        products_list = seller_context.get("products", [])
        if products_list:
            products_str = ", ".join([
                p.get("name", "") for p in products_list if p.get("name")
            ]) or "not specified"
            # Get benefits from first few products
            all_benefits = []
            for p in products_list[:3]:
                all_benefits.extend(p.get("benefits", [])[:2])
            benefits_str = ", ".join(all_benefits[:5]) if all_benefits else "not specified"
        else:
            products_str = "not specified"
            benefits_str = "not specified"
        
        values = ", ".join(seller_context.get("value_propositions", [])[:3]) or "not specified"
        diffs = ", ".join(seller_context.get("differentiators", [])[:3]) or "not specified"
        
        # ICP details (CRITICAL for quality)
        industries = ", ".join(seller_context.get("target_industries", [])[:3]) or "any"
        company_sizes = ", ".join(seller_context.get("target_company_sizes", [])[:3]) or "any size"
        pain_points = ", ".join(seller_context.get("ideal_pain_points", [])[:5]) or "not specified"
        decision_makers = ", ".join(seller_context.get("target_decision_makers", [])[:5]) or "not specified"
        
        return f"""
═══════════════════════════════════════════════════════════════════════════════
                           SELLER CONTEXT
═══════════════════════════════════════════════════════════════════════════════

Use this to assess FIT and personalize the research.

**SELLER**: {seller_context.get('company_name', 'Unknown')}

| What We Sell | Details |
|--------------|---------|
| **Products** | {products_str} |
| **Key Benefits** | {benefits_str} |
| **Value Props** | {values} |
| **Differentiators** | {diffs} |

| Ideal Customer Profile | Details |
|------------------------|---------|
| **Target Industries** | {industries} |
| **Company Sizes** | {company_sizes} |
| **Pain Points We Solve** | {pain_points} |
| **Typical Decision Makers** | {decision_makers} |

**YOUR MISSION**:
1. Assess if this prospect FITS our ICP (industry, size, likely pains)
2. Find evidence of the pain points we solve
3. Identify decision makers matching our typical buyers
4. Suggest use cases based on their situation + our benefits
"""

    async def _execute_web_searches(
        self,
        company_name: str,
        country: Optional[str],
        city: Optional[str],
        current_date: str
    ) -> Dict[str, Any]:
        """
        Phase 1: Execute web searches with MINIMAL prompt.
        
        This phase uses a small ~500 token prompt instead of the full 3,500 token
        analysis template. Since each web search iteration sends the full prompt,
        this saves ~3,000 tokens × ~8 iterations = ~24,000 tokens per research.
        
        Returns:
            Dictionary with search results and token statistics
        """
        search_prompt = self._build_search_prompt(company_name, country, city, current_date)
        
        # Build web search tool with location context
        tools = [{
            "type": "web_search_20250305",
            "name": "web_search",
            "max_uses": 10,  # Allow thorough research
        }]
        
        # Add user location for localized results
        if country:
            from app.i18n.utils import get_country_iso_code
            country_iso = get_country_iso_code(country)
            if country_iso:
                user_location = {"type": "approximate", "country": country_iso}
                if city:
                    user_location["city"] = city
                tools[0]["user_location"] = user_location
        
        logger.info(f"Phase 1: Starting web search for {company_name}")
        
        try:
            response = await self.client.messages.create(
                model="claude-sonnet-4-20250514",
                max_tokens=4096,  # Enough for structured search results
                temperature=0.1,  # Very low for consistent searches
                tools=tools,
                messages=[{
                    "role": "user",
                    "content": search_prompt
                }]
            )
            
            # Extract the collected information from the response
            search_results = ""
            for block in response.content:
                if hasattr(block, 'text'):
                    search_results += block.text
            
            usage = response.usage
            logger.info(
                f"Phase 1 completed for {company_name}. "
                f"Tokens - Input: {usage.input_tokens}, Output: {usage.output_tokens}. "
                f"Stop reason: {response.stop_reason}"
            )
            
            return {
                "success": True,
                "search_results": search_results,
                "stop_reason": response.stop_reason,
                "token_stats": {
                    "input_tokens": usage.input_tokens,
                    "output_tokens": usage.output_tokens
                }
            }
            
        except Exception as e:
            logger.error(f"Phase 1 web search failed for {company_name}: {str(e)}")
            return {
                "success": False,
                "error": str(e),
                "search_results": "",
                "token_stats": {"input_tokens": 0, "output_tokens": 0}
            }

    async def _analyze_search_results(
        self,
        company_name: str,
        country: Optional[str],
        city: Optional[str],
        search_results: str,
        seller_context: Optional[Dict[str, Any]],
        language: str,
        current_date: str
    ) -> Dict[str, Any]:
        """
        Phase 2: Analyze search results with FULL 360° template.
        
        This phase takes all the collected search results and generates the
        comprehensive intelligence report. The full template is only sent ONCE,
        not with every search iteration.
        
        Args:
            company_name: Target company
            country: Optional country
            city: Optional city
            search_results: Raw results from Phase 1
            seller_context: Context about seller's offering
            language: Output language code
            current_date: Current date string
            
        Returns:
            Dictionary with analysis results and token statistics
        """
        lang_instruction = get_language_instruction(language)
        current_year = datetime.now().year
        
        # Build seller context section
        org_id = seller_context.get("organization_id") if seller_context else None
        if org_id and org_id in self._seller_context_cache:
            seller_section = self._seller_context_cache[org_id]
        else:
            seller_section = self._build_seller_context_section(seller_context)
            if org_id:
                self._seller_context_cache[org_id] = seller_section
        
        # Build location context
        location_str = ""
        if city and country:
            location_str = f"**LOCATION**: {city}, {country}"
        elif country:
            location_str = f"**COUNTRY**: {country}"
        
        # Build the analysis prompt with all components
        analysis_prompt = f"""{self._analysis_template}

{seller_section}

═══════════════════════════════════════════════════════════════════════════════
                              RESEARCH TARGET
═══════════════════════════════════════════════════════════════════════════════

**TODAY'S DATE**: {current_date}
**CURRENT YEAR**: {current_year}
**TARGET COMPANY**: {company_name}
{location_str}

⚠️ IMPORTANT: All "recent" means relative to TODAY ({current_date}).
⚠️ Verify dates on all news items - do not report old news as recent.

═══════════════════════════════════════════════════════════════════════════════
                           WEB SEARCH RESULTS
═══════════════════════════════════════════════════════════════════════════════

The following information was collected via web search:

{search_results}

═══════════════════════════════════════════════════════════════════════════════
                           GENERATE REPORT
═══════════════════════════════════════════════════════════════════════════════

Based on ALL the search results above, generate the complete 360° PROSPECT INTELLIGENCE REPORT for {company_name}.

{lang_instruction}

Generate the report now:"""

        logger.info(f"Phase 2: Analyzing search results for {company_name}")
        
        try:
            response = await self.client.messages.create(
                model="claude-sonnet-4-20250514",
                max_tokens=8192,  # Large output for comprehensive report
                temperature=0.2,  # Low for factual accuracy
                messages=[{
                    "role": "user",
                    "content": analysis_prompt
                }]
            )
            
            result_text = ""
            for block in response.content:
                if hasattr(block, 'text'):
                    result_text += block.text
            
            usage = response.usage
            logger.info(
                f"Phase 2 completed for {company_name}. "
                f"Tokens - Input: {usage.input_tokens}, Output: {usage.output_tokens}. "
                f"Stop reason: {response.stop_reason}"
            )
            
            return {
                "success": True,
                "report": result_text,
                "stop_reason": response.stop_reason,
                "token_stats": {
                    "input_tokens": usage.input_tokens,
                    "output_tokens": usage.output_tokens
                }
            }
            
        except Exception as e:
            logger.error(f"Phase 2 analysis failed for {company_name}: {str(e)}")
            return {
                "success": False,
                "error": str(e),
                "report": "",
                "token_stats": {"input_tokens": 0, "output_tokens": 0}
            }

    async def search_company(
        self,
        company_name: str,
        country: Optional[str] = None,
        city: Optional[str] = None,
        linkedin_url: Optional[str] = None,
        seller_context: Optional[Dict[str, Any]] = None,
        language: str = DEFAULT_LANGUAGE
    ) -> Dict[str, Any]:
        """
        Search for company information using optimized two-phase approach.
        
        OPTIMIZATION STRATEGY:
        - Phase 1: Web search with minimal prompt (~500 tokens × N searches)
        - Phase 2: Analysis with full template (~40k tokens × 1 call)
        
        Previous: ~262,000 tokens (~$1.05 per research)
        New: ~50,000 tokens (~$0.20 per research)
        Savings: ~80%
        
        Args:
            company_name: Name of the company to research
            country: Optional country for better search accuracy
            city: Optional city for better search accuracy
            linkedin_url: Optional LinkedIn company URL (added to context)
            seller_context: Context about what the seller offers
            language: Output language code (default from config)
            
        Returns:
            Dictionary with research data, success status, and token statistics
        """
        current_date = datetime.now().strftime("%d %B %Y")
        
        logger.info(f"Starting two-phase 360° research for {company_name}")
        
        # ═══════════════════════════════════════════════════════════════════
        # PHASE 1: Web Search (minimal prompt)
        # ═══════════════════════════════════════════════════════════════════
        
        search_result = await self._execute_web_searches(
            company_name, country, city, current_date
        )
        
        if not search_result.get("success"):
            return {
                "source": "claude",
                "query": f"{company_name} ({country or 'Unknown'})",
                "error": search_result.get("error", "Web search failed"),
                "success": False,
                "web_search_used": True,
                "token_stats": search_result.get("token_stats", {})
            }
        
        # Add LinkedIn URL to search results if provided
        search_results = search_result.get("search_results", "")
        if linkedin_url:
            search_results += f"\n\n**Company LinkedIn URL provided**: {linkedin_url}"
        
        # ═══════════════════════════════════════════════════════════════════
        # PHASE 2: Analysis (full template)
        # ═══════════════════════════════════════════════════════════════════
        
        analysis_result = await self._analyze_search_results(
            company_name=company_name,
            country=country,
            city=city,
            search_results=search_results,
            seller_context=seller_context,
            language=language,
            current_date=current_date
        )
        
        if not analysis_result.get("success"):
            # Fallback: return raw search results if analysis fails
            return {
                "source": "claude",
                "query": f"{company_name} ({country or 'Unknown'})",
                "data": f"# Raw Search Results for {company_name}\n\n{search_results}",
                "success": True,
                "web_search_used": True,
                "analysis_failed": True,
                "token_stats": {
                    "phase1_input": search_result.get("token_stats", {}).get("input_tokens", 0),
                    "phase1_output": search_result.get("token_stats", {}).get("output_tokens", 0),
                    "phase2_input": analysis_result.get("token_stats", {}).get("input_tokens", 0),
                    "phase2_output": analysis_result.get("token_stats", {}).get("output_tokens", 0),
                    "total_input": (
                        search_result.get("token_stats", {}).get("input_tokens", 0) +
                        analysis_result.get("token_stats", {}).get("input_tokens", 0)
                    ),
                    "total_output": (
                        search_result.get("token_stats", {}).get("output_tokens", 0) +
                        analysis_result.get("token_stats", {}).get("output_tokens", 0)
                    )
                }
            }
        
        # Calculate total token usage
        total_input = (
            search_result.get("token_stats", {}).get("input_tokens", 0) +
            analysis_result.get("token_stats", {}).get("input_tokens", 0)
        )
        total_output = (
            search_result.get("token_stats", {}).get("output_tokens", 0) +
            analysis_result.get("token_stats", {}).get("output_tokens", 0)
        )
        
        logger.info(
            f"Two-phase research completed for {company_name}. "
            f"Total tokens - Input: {total_input}, Output: {total_output}"
        )
        
        return {
            "source": "claude",
            "query": f"{company_name} ({country or 'Unknown'})",
            "data": analysis_result.get("report", ""),
            "success": True,
            "web_search_used": True,
            "stop_reason": analysis_result.get("stop_reason"),
            "token_stats": {
                "phase1_input": search_result.get("token_stats", {}).get("input_tokens", 0),
                "phase1_output": search_result.get("token_stats", {}).get("output_tokens", 0),
                "phase2_input": analysis_result.get("token_stats", {}).get("input_tokens", 0),
                "phase2_output": analysis_result.get("token_stats", {}).get("output_tokens", 0),
                "total_input": total_input,
                "total_output": total_output
            }
        }
    
    def clear_seller_cache(self, organization_id: Optional[str] = None) -> None:
        """
        Clear cached seller context.
        
        Call this when organization's company profile is updated.
        
        Args:
            organization_id: Specific org to clear, or None to clear all
        """
        if organization_id:
            self._seller_context_cache.pop(organization_id, None)
            logger.info(f"Cleared seller context cache for org {organization_id}")
        else:
            self._seller_context_cache.clear()
            logger.info("Cleared all seller context caches")
