"""
Gemini Google Search integration for comprehensive B2B prospect research.

ARCHITECTURE (Cost-Optimized):
- Gemini does ALL web searching (30x cheaper than Claude)
- Collects: company info, leadership, news, hiring, competitive, market
- Output: Structured raw data for Claude to analyze

Gemini 2.0 Flash pricing: $0.10/1M input, $0.40/1M output
Claude Sonnet 4 pricing: $3.00/1M input, $15.00/1M output

This approach saves ~85% on research costs.
"""
import os
import logging
from datetime import datetime
from typing import Dict, Any, Optional
from google import genai
from google.genai import types
from app.i18n.utils import get_language_instruction
from app.i18n.config import DEFAULT_LANGUAGE

logger = logging.getLogger(__name__)


class GeminiResearcher:
    """
    Comprehensive B2B research using Gemini with Google Search grounding.
    
    This is the PRIMARY research engine - collects all data that Claude will analyze.
    """
    
    def __init__(self):
        """Initialize Gemini API with Google GenAI SDK."""
        api_key = os.getenv("GOOGLE_AI_API_KEY")
        if not api_key:
            raise ValueError("GOOGLE_AI_API_KEY environment variable not set")
        
        # Initialize client with explicit API key
        self.client = genai.Client(api_key=api_key)
        
        # Configure Google Search tool for grounding
        self.search_tool = types.Tool(
            google_search=types.GoogleSearch()
        )
        
        self.config = types.GenerateContentConfig(
            tools=[self.search_tool],
            temperature=0.1,  # Very low for factual accuracy
        )
    
    def _build_seller_context_section(self, seller_context: Dict[str, Any]) -> str:
        """
        Build seller context section to guide research focus.
        
        Helps Gemini prioritize information relevant to the seller's offering.
        """
        if not seller_context or not seller_context.get("has_context"):
            return ""
        
        # Products
        products_list = seller_context.get("products", [])
        products_str = ", ".join([
            p.get("name", "") for p in products_list if p.get("name")
        ]) if products_list else "not specified"
        
        # ICP pain points
        pain_points = seller_context.get("ideal_pain_points", [])
        pain_str = ", ".join(pain_points[:5]) if pain_points else "efficiency, growth, automation"
        
        # Target decision makers
        decision_makers = seller_context.get("target_decision_makers", [])
        dm_str = ", ".join(decision_makers[:3]) if decision_makers else "executives, directors"
        
        # Target industries
        industries = seller_context.get("target_industries", [])
        ind_str = ", ".join(industries[:3]) if industries else "various"
        
        return f"""
## SELLER CONTEXT (Use this to focus research)

**Seller Company**: {seller_context.get('company_name', 'Unknown')}
**Products/Services**: {products_str}
**Pain Points We Solve**: {pain_str}
**Typical Decision Makers**: {dm_str}
**Target Industries**: {ind_str}

When researching, pay special attention to:
- Signals that indicate the prospect has these pain points
- People in {dm_str} roles (include LinkedIn URLs!)
- News about {pain_str}
- Whether they're in or adjacent to {ind_str}
"""

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
        Comprehensive company research using Gemini with Google Search.
        
        This is the PRIMARY research function - searches for EVERYTHING:
        - Company basics (identity, structure, size)
        - Leadership team (C-suite, directors, with LinkedIn URLs)
        - Recent news (last 90 days)
        - Hiring signals
        - Financial information
        - Competitive landscape
        - Technology stack
        
        Args:
            company_name: Name of the company
            country: Optional country for better search accuracy
            city: Optional city for better search accuracy
            linkedin_url: Optional LinkedIn URL
            seller_context: Context about what the seller offers
            language: Output language code
            
        Returns:
            Dictionary with comprehensive research data
        """
        lang_instruction = get_language_instruction(language)
        current_date = datetime.now().strftime("%d %B %Y")
        current_year = datetime.now().year
        
        # Build location context
        location_context = ""
        if city and country:
            location_context = f"Location: {city}, {country}"
        elif country:
            location_context = f"Country: {country}"
        
        # Build seller context section
        seller_section = self._build_seller_context_section(seller_context)
        
        # Build comprehensive research prompt
        prompt = f"""You are an elite B2B sales intelligence researcher. Your research saves sales professionals DAYS of manual work.

══════════════════════════════════════════════════════════════════════════════
                              CRITICAL CONTEXT
══════════════════════════════════════════════════════════════════════════════

**TODAY'S DATE**: {current_date}
**CURRENT YEAR**: {current_year}

⚠️ IMPORTANT DATE RULES:
- All "recent" means relative to TODAY ({current_date})
- For news, focus on the LAST 90 DAYS
- Always include publication dates for news items
- If you find news older than 90 days, label it as "older context"

{lang_instruction}

══════════════════════════════════════════════════════════════════════════════
                              TARGET COMPANY
══════════════════════════════════════════════════════════════════════════════

**Company Name**: {company_name}
{location_context}
{f"**LinkedIn URL**: {linkedin_url}" if linkedin_url else ""}

{seller_section}

══════════════════════════════════════════════════════════════════════════════
                           SEARCH STRATEGY
══════════════════════════════════════════════════════════════════════════════

Execute these Google searches THOROUGHLY. Quality over speed.

**PHASE 1 - Company Foundation:**
□ "{company_name}" official website about us
□ "{company_name}" Wikipedia OR Crunchbase
□ site:linkedin.com/company/ "{company_name}"
□ "{company_name}" founded history

**PHASE 2 - Financial & Size:**
□ "{company_name}" revenue OR omzet OR turnover
□ "{company_name}" funding investment series
□ "{company_name}" employees headcount FTE
□ "{company_name}" valuation acquisition

**PHASE 3 - Leadership (CRITICAL - search extensively!):**
□ "{company_name}" CEO founder "managing director"
□ "{company_name}" CFO CTO COO CMO CHRO
□ site:linkedin.com/in "{company_name}" CEO
□ site:linkedin.com/in "{company_name}" director
□ site:linkedin.com/in "{company_name}" VP "vice president"
□ "{company_name}" management team leadership
□ "{company_name}" board of directors

**PHASE 4 - Recent News (Last 90 Days):**
□ "{company_name}" news {current_year}
□ "{company_name}" press release announcement
□ "{company_name}" partnership deal signed
□ "{company_name}" expansion growth new office
□ "{company_name}" award winner recognition

**PHASE 5 - Hiring Signals:**
□ "{company_name}" jobs careers hiring
□ "{company_name}" job openings vacancies
□ site:linkedin.com/jobs "{company_name}"

**PHASE 6 - Market & Competition:**
□ "{company_name}" competitors comparison vs
□ "{company_name}" market share position
□ "{company_name}" customers clients case study

**PHASE 7 - Technology:**
□ "{company_name}" technology stack tools software
□ "{company_name}" uses Salesforce OR HubSpot OR SAP OR Oracle

══════════════════════════════════════════════════════════════════════════════
                    COMPREHENSIVE RESEARCH OUTPUT
══════════════════════════════════════════════════════════════════════════════

Compile ALL findings into this structured format. Include SOURCE URLs for verification.


## SECTION 1: COMPANY IDENTITY

| Field | Value | Source URL |
|-------|-------|------------|
| Legal Name | [Full registered name] | |
| Trading Name | [If different] | |
| Industry | [Sector → Sub-sector] | |
| Founded | [Year] | |
| Headquarters | [City, Country] | |
| Other Locations | [List] | |
| Website | [URL] | |
| LinkedIn | [Company page URL] | |
| Description | [What they do in 2-3 sentences] | |


## SECTION 2: COMPANY SIZE & FINANCIALS

| Metric | Value | Source URL |
|--------|-------|------------|
| Employees | [Number or range] | |
| Employee Trend | 📈 Growing / ➡️ Stable / 📉 Shrinking | |
| Revenue | [Amount or estimate] | |
| Funding Raised | [Total] | |
| Latest Funding Round | [Series X, Amount, Date] | |
| Key Investors | [Names] | |
| Ownership Type | Private / Public / PE / VC / Family | |


## SECTION 3: LEADERSHIP TEAM 🔴 CRITICAL

For EACH person found, include their FULL LinkedIn URL.

### C-Suite / Executive Leadership

| Name | Title | LinkedIn URL | Background | Notes |
|------|-------|--------------|------------|-------|
| [Full Name] | CEO/MD/Founder | [https://linkedin.com/in/...] | [Previous roles, education] | [Founder? New hire?] |
| [Full Name] | CFO | [URL] | | 💰 Budget authority |
| [Full Name] | CTO/CIO | [URL] | | 🔧 Tech decisions |
| [Full Name] | COO | [URL] | | ⚙️ Operations |
| [Full Name] | CMO | [URL] | | 📣 Marketing |
| [Full Name] | CHRO | [URL] | | 👥 People |
| [Full Name] | CSO/CRO | [URL] | | 🤝 Sales |

### Senior Leadership (VPs, Directors, Heads)

| Name | Title | LinkedIn URL | Department | Potential Relevance |
|------|-------|--------------|------------|---------------------|
| [Name] | VP of [X] | [URL] | | [Why might they care?] |
| [Name] | Director of [X] | [URL] | | |
| [Name] | Head of [X] | [URL] | | |

### Board of Directors / Investors

| Name | Role | LinkedIn URL | Affiliation |
|------|------|--------------|-------------|
| [Name] | Chairman | [URL] | [Company/Fund] |
| [Name] | Board Member | [URL] | |

**Leadership Coverage Assessment**: 🟢 Comprehensive / 🟡 Partial / 🔴 Limited
**Note**: [Any gaps or limitations in leadership data]


## SECTION 4: RECENT NEWS & DEVELOPMENTS (Last 90 Days)

| Date | Headline | Type | Source | URL |
|------|----------|------|--------|-----|
| [DD MMM YYYY] | [Title] | 💰/📈/👥/🚀/🤝/⚠️ | [Publication] | [URL] |
| [DD MMM YYYY] | [Title] | | [Publication] | [URL] |
| [DD MMM YYYY] | [Title] | | [Publication] | [URL] |
| [DD MMM YYYY] | [Title] | | [Publication] | [URL] |
| [DD MMM YYYY] | [Title] | | [Publication] | [URL] |

**News Types**: 💰 Funding/Financial | 📈 Growth/Expansion | 👥 People/Leadership | 🚀 Product/Launch | 🤝 Partnership | ⚠️ Challenge

**If no recent news found**: State "No news found in the last 90 days from {current_date}"

### News Summary
[2-3 sentences: What's the overall narrative? What are they focused on?]


## SECTION 5: HIRING SIGNALS

### Current Job Openings

| Role | Department | Level | Location | Posted | Source URL |
|------|------------|-------|----------|--------|------------|
| [Title] | [Dept] | Jr/Sr/Director/VP | [Location] | [Date] | [URL] |
| [Title] | [Dept] | | | | |

### Hiring Analysis

| Metric | Observation |
|--------|-------------|
| **Total Open Roles** | [Number found] |
| **Fastest Growing Departments** | [Which teams are scaling] |
| **Senior Hires** | [Executive/leadership searches] |
| **New Capabilities** | [Roles suggesting new directions] |
| **Hiring Velocity** | 🔥 Aggressive / ➡️ Steady / ❄️ Slowing / 🛑 Freeze |
| **Remote Hiring** | [Patterns observed] |


## SECTION 6: BUSINESS MODEL & CUSTOMERS

### What They Do
[3-4 sentences explaining their core business, value proposition, and how they make money]

### Customer Profile

| Aspect | Details |
|--------|---------|
| **Business Model** | B2B / B2C / B2B2C / Marketplace / SaaS / Services |
| **Customer Segment** | Enterprise / Mid-market / SMB / Consumer |
| **Key Verticals** | [Industries they sell to] |
| **Geographic Focus** | [Regions/countries] |
| **Named Customers** | [Logos/testimonials found] |


## SECTION 7: COMPETITIVE LANDSCAPE

### Competitors

| Competitor | Positioning | Source |
|------------|-------------|--------|
| [Company 1] | [How they compare] | [URL] |
| [Company 2] | | |
| [Company 3] | | |

### Market Position
- **Market Role**: 🥇 Leader / 🥈 Challenger / 🥉 Niche / 🆕 Newcomer
- **Key Differentiators**: [What makes them unique]


## SECTION 8: TECHNOLOGY STACK

| Category | Known Tools/Vendors | Source |
|----------|---------------------|--------|
| CRM | [Salesforce, HubSpot, etc.] | |
| Marketing | | |
| ERP/Finance | [SAP, Oracle, NetSuite, etc.] | |
| Cloud/Infra | [AWS, Azure, GCP] | |
| Collaboration | [Slack, Teams, etc.] | |
| Industry-Specific | | |


## SECTION 9: RESEARCH METADATA

| Aspect | Value |
|--------|-------|
| **Research Date** | {current_date} |
| **Company Found** | Yes / Partial / No |
| **Website Accessible** | Yes / No |
| **LinkedIn Found** | Yes / No |
| **News Coverage** | Rich / Moderate / Limited / None |
| **Leadership Coverage** | Comprehensive / Partial / Limited |
| **Overall Data Quality** | 🟢 High / 🟡 Medium / 🔴 Low |

### Sources Used
- [List all URLs that provided valuable information]

### Information Gaps
- [What couldn't be found that would be valuable]


══════════════════════════════════════════════════════════════════════════════
                              QUALITY RULES
══════════════════════════════════════════════════════════════════════════════

1. **Include FULL LinkedIn URLs** for EVERY person found (critical!)
2. **Include source URLs** for all major claims
3. **Be factual** - if not found, say "Not found" (don't invent data)
4. **Date accuracy** - verify dates are relative to {current_date}
5. **Search thoroughly** - execute ALL search phases
6. **Quality over speed** - accurate partial data beats speculative complete data
7. **Structure strictly** - follow the exact format above

Begin your comprehensive research now:
"""

        try:
            logger.info(f"Starting Gemini comprehensive research for {company_name}")
            
            # Generate response with Google Search grounding
            response = await self.client.aio.models.generate_content(
                model='gemini-2.0-flash',
                contents=prompt,
                config=self.config
            )
            
            # Get token usage if available
            usage_metadata = getattr(response, 'usage_metadata', None)
            token_stats = {}
            if usage_metadata:
                token_stats = {
                    "input_tokens": getattr(usage_metadata, 'prompt_token_count', 0),
                    "output_tokens": getattr(usage_metadata, 'candidates_token_count', 0),
                }
            
            logger.info(
                f"Gemini comprehensive research completed for {company_name}. "
                f"Tokens: {token_stats.get('input_tokens', 'N/A')} in, {token_stats.get('output_tokens', 'N/A')} out"
            )
            
            return {
                "source": "gemini",
                "query": f"{company_name} ({country or 'Unknown'})",
                "data": response.text,
                "success": True,
                "google_search_used": True,
                "research_date": current_date,
                "token_stats": token_stats
            }
            
        except Exception as e:
            logger.error(f"Gemini comprehensive research failed for {company_name}: {str(e)}")
            return {
                "source": "gemini",
                "query": f"{company_name} ({country or 'Unknown'})",
                "error": str(e),
                "success": False,
                "google_search_used": False,
                "token_stats": {}
            }
