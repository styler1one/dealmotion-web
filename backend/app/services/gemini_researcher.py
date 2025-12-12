"""
Gemini Google Search integration for comprehensive B2B prospect research.

ARCHITECTURE (Cost-Optimized + Maximum Quality):
- Gemini does ALL web searching (30x cheaper than Claude)
- Uses MANY PARALLEL calls for MAXIMUM coverage
- Each call focuses on ONE specific research area
- Output: Comprehensive structured raw data for Claude to analyze

Gemini 2.0 Flash pricing: $0.10/1M input, $0.40/1M output
Claude Sonnet 4 pricing: $3.00/1M input, $15.00/1M output

15 parallel calls × ~$0.002 = ~$0.03 total (still 97% cheaper than Claude web search)
Parallel execution = FASTER than fewer sequential calls!
"""
import os
import logging
import asyncio
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
    
    Uses 15 PARALLEL CALLS for MAXIMUM coverage:
    
    COMPANY INFORMATION:
    1. company_basics - Identity, founding, locations
    2. company_description - What they do, business model
    3. financials - Revenue, funding, investors
    4. products_services - Detailed product information
    
    PEOPLE (Critical for Sales):
    5. ceo_founder - CEO with LinkedIn URL
    6. ceo_linkedin_deep - Dedicated CEO LinkedIn search
    7. c_suite - CFO, CTO, COO with LinkedIns
    8. c_suite_linkedin - Dedicated C-suite LinkedIn search
    9. senior_leadership - VPs, Directors with LinkedIns
    10. board_investors - Board members, investors
    
    MARKET INTELLIGENCE:
    11. recent_news - Last 90 days news
    12. partnerships_deals - Partnerships, acquisitions
    13. hiring_signals - Job postings, growth signals
    14. tech_stack - Technology and tools
    15. competition - Competitors, market position
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

    async def _search_single_topic(
        self,
        topic_name: str,
        prompt: str,
        company_name: str
    ) -> Dict[str, Any]:
        """Execute a single focused search topic."""
        try:
            logger.info(f"Gemini searching {topic_name} for {company_name}")
            
            response = await self.client.aio.models.generate_content(
                model='gemini-2.0-flash',
                contents=prompt,
                config=self.config
            )
            
            # Get token usage
            usage_metadata = getattr(response, 'usage_metadata', None)
            token_stats = {}
            if usage_metadata:
                token_stats = {
                    "input_tokens": getattr(usage_metadata, 'prompt_token_count', 0),
                    "output_tokens": getattr(usage_metadata, 'candidates_token_count', 0),
                }
            
            logger.info(
                f"Gemini {topic_name} completed for {company_name}. "
                f"Tokens: {token_stats.get('input_tokens', 'N/A')} in, {token_stats.get('output_tokens', 'N/A')} out"
            )
            
            return {
                "topic": topic_name,
                "data": response.text,
                "success": True,
                "token_stats": token_stats
            }
            
        except Exception as e:
            logger.error(f"Gemini {topic_name} failed for {company_name}: {str(e)}")
            return {
                "topic": topic_name,
                "data": f"Error: {str(e)}",
                "success": False,
                "token_stats": {}
            }

    def _build_base_context(
        self,
        company_name: str,
        country: Optional[str],
        city: Optional[str],
        linkedin_url: Optional[str],
        current_date: str,
        current_year: int,
        language: str
    ) -> str:
        """Build common context for all search prompts."""
        lang_instruction = get_language_instruction(language)
        
        location_context = ""
        if city and country:
            location_context = f"Location: {city}, {country}"
        elif country:
            location_context = f"Country: {country}"
        
        return f"""You are an elite B2B sales intelligence researcher. Your research saves professionals DAYS of manual work.

**TODAY'S DATE**: {current_date}
**CURRENT YEAR**: {current_year}

{lang_instruction}

**TARGET COMPANY**: {company_name}
{location_context}
{f"**LinkedIn URL**: {linkedin_url}" if linkedin_url else ""}

"""

    def _build_search_prompts(
        self,
        company_name: str,
        base_context: str,
        current_date: str,
        current_year: int,
        seller_context: Optional[Dict[str, Any]] = None
    ) -> Dict[str, str]:
        """
        Build 15 focused search prompts for maximum coverage.
        """
        # Build seller hint if available
        seller_hint = ""
        if seller_context and seller_context.get("has_context"):
            pain_points = seller_context.get("ideal_pain_points", [])
            if pain_points:
                seller_hint = f"\n**Sales Focus**: Look for signals related to: {', '.join(pain_points[:3])}"
        
        prompts = {}
        
        # ═══════════════════════════════════════════════════════════════════════
        # SECTION 1: COMPANY INFORMATION (4 queries)
        # ═══════════════════════════════════════════════════════════════════════
        
        # 1. COMPANY BASICS - Identity, structure
        prompts["company_basics"] = base_context + f"""
**RESEARCH FOCUS**: Company Identity & Basic Information

Execute these Google searches for "{company_name}":
1. "{company_name}" official website
2. "{company_name}" Wikipedia
3. "{company_name}" Crunchbase
4. "{company_name}" founded year history
5. "{company_name}" headquarters location offices

**REQUIRED OUTPUT** (use tables):

## Company Identity

| Field | Value | Source URL |
|-------|-------|------------|
| Legal Name | [Full registered name] | [URL] |
| Trading Name | [If different] | |
| Industry | [Sector → Sub-sector] | |
| Founded | [Year] | |
| Headquarters | [City, Country] | |
| Other Locations | [List all offices] | |
| Website | [URL] | |
| LinkedIn Company | [https://linkedin.com/company/...] | |

Search thoroughly and include source URLs!
"""

        # 2. COMPANY DESCRIPTION - Business model, what they do
        prompts["company_description"] = base_context + f"""
**RESEARCH FOCUS**: What Does This Company Do?

Search for detailed business information about "{company_name}":
1. "{company_name}" about us what we do
2. "{company_name}" business model
3. "{company_name}" services products
4. "{company_name}" mission vision values
5. "{company_name}" company profile

**REQUIRED OUTPUT**:

## Company Description
[4-5 sentences explaining: What they do, who they serve, their value proposition]

## Business Model

| Aspect | Details |
|--------|---------|
| **Type** | B2B / B2C / B2B2C / Marketplace / SaaS / Services / Manufacturing |
| **Revenue Model** | Subscription / Transaction / License / Services / Product |
| **Customer Segment** | Enterprise / Mid-market / SMB / Consumer |
| **Key Verticals** | [Industries they serve] |
| **Geographic Focus** | [Regions/countries] |

## Value Proposition
- **Core Offering**: [Main product/service]
- **Key Differentiators**: [What makes them unique]
- **Target Problem**: [What problem they solve]
"""

        # 3. FINANCIALS - Revenue, funding, size
        prompts["financials"] = base_context + f"""
**RESEARCH FOCUS**: Financial Information & Company Size

Search extensively for "{company_name}":
1. "{company_name}" revenue turnover omzet
2. "{company_name}" funding investment raised
3. "{company_name}" series A B C funding round
4. "{company_name}" valuation
5. "{company_name}" employees headcount FTE
6. "{company_name}" annual report
7. "{company_name}" investors shareholders

**REQUIRED OUTPUT**:

## Company Size

| Metric | Value | Trend | Source URL |
|--------|-------|-------|------------|
| Employees | [Number or range] | 📈/➡️/📉 | [URL] |
| Revenue | [Amount] | | [URL] |
| Revenue Growth | [% if known] | | |

## Funding History

| Date | Round | Amount | Lead Investors | Source |
|------|-------|--------|----------------|--------|
| [Date] | [Series X] | [Amount] | [Names] | [URL] |

## Ownership

| Type | Details |
|------|---------|
| Ownership | Private / Public / PE-backed / VC-backed / Family |
| Key Investors | [Names] |
| Valuation | [If known] |

If no data found, state "No public financial data available"
"""

        # 4. PRODUCTS & SERVICES - Detailed offerings
        prompts["products_services"] = base_context + f"""
**RESEARCH FOCUS**: Products & Services Details

Search for "{company_name}":
1. "{company_name}" products services offerings
2. "{company_name}" solutions platform
3. "{company_name}" pricing plans
4. "{company_name}" features capabilities
5. "{company_name}" customers clients case study

**REQUIRED OUTPUT**:

## Products & Services

| Product/Service | Description | Target Customer |
|-----------------|-------------|-----------------|
| [Name] | [What it does] | [Who uses it] |
| [Name] | | |

## Key Features/Capabilities
- [Feature 1]
- [Feature 2]
- [Feature 3]

## Named Customers / Case Studies

| Customer | Industry | Use Case | Source |
|----------|----------|----------|--------|
| [Name] | [Industry] | [How they use it] | [URL] |

## Pricing Model
[Subscription tiers, enterprise pricing, etc. if found]
"""

        # ═══════════════════════════════════════════════════════════════════════
        # SECTION 2: PEOPLE - CRITICAL FOR SALES (6 queries)
        # ═══════════════════════════════════════════════════════════════════════

        # 5. CEO/FOUNDER - Primary decision maker
        prompts["ceo_founder"] = base_context + f"""
**RESEARCH FOCUS**: CEO & Founder(s) - CRITICAL

Search for the CEO and founders of "{company_name}":
1. "{company_name}" CEO
2. "{company_name}" founder
3. "{company_name}" managing director
4. "{company_name}" oprichter directeur
5. "{company_name}" leadership
6. who founded "{company_name}"
7. who is CEO of "{company_name}"

**CRITICAL: Find their FULL LinkedIn URL!**

**REQUIRED OUTPUT**:

## CEO / Founder Information

| Field | Value |
|-------|-------|
| **Full Name** | [First Last] |
| **Title** | [CEO / Founder / Managing Director] |
| **LinkedIn URL** | https://linkedin.com/in/[exact-url] |
| **Email** | [If found publicly] |
| **Twitter/X** | [If found] |

## Background
- **Previous Roles**: [List 2-3 previous positions]
- **Education**: [Degrees, schools]
- **Tenure at Company**: [When they joined/founded]
- **Notable**: [Awards, speaking, publications]

## Founder Story
[If available: How/when company was founded, what problem they set out to solve]

If LinkedIn URL not found in first search, search specifically:
- "[person's full name]" linkedin
- site:linkedin.com "[person's full name]"
"""

        # 6. CEO LINKEDIN DEEP SEARCH - Dedicated LinkedIn search
        prompts["ceo_linkedin_deep"] = base_context + f"""
**RESEARCH FOCUS**: Find CEO LinkedIn Profile URL - DEEP SEARCH

Your ONLY goal is to find the LinkedIn profile URL of the CEO/Founder of "{company_name}".

Execute these specific searches:
1. site:linkedin.com/in "{company_name}" CEO
2. site:linkedin.com/in "{company_name}" founder
3. site:linkedin.com/in "{company_name}" managing director
4. site:nl.linkedin.com/in "{company_name}" CEO
5. site:uk.linkedin.com/in "{company_name}" CEO
6. "{company_name}" CEO linkedin.com/in
7. "{company_name}" founder linkedin profile

**REQUIRED OUTPUT**:

## CEO/Founder LinkedIn Profile

| Person | Title | LinkedIn URL |
|--------|-------|--------------|
| [Full Name] | [CEO/Founder/MD] | https://linkedin.com/in/[exact-profile-slug] |

## Alternative Profiles Found
[List any other executives found during search with their LinkedIn URLs]

| Name | Title | LinkedIn URL |
|------|-------|--------------|
| [Name] | [Title] | [URL] |

**IMPORTANT**: 
- The LinkedIn URL must be the EXACT profile URL (e.g., https://linkedin.com/in/john-smith-123abc)
- If you find multiple possible matches, list all of them
- If truly not found, state "LinkedIn profile not found after extensive search"
"""

        # 7. C-SUITE - Other executives
        prompts["c_suite"] = base_context + f"""
**RESEARCH FOCUS**: C-Suite Executive Team

Search for ALL C-level executives at "{company_name}":
1. "{company_name}" CFO chief financial officer
2. "{company_name}" CTO chief technology officer
3. "{company_name}" COO chief operating officer
4. "{company_name}" CMO chief marketing officer
5. "{company_name}" CHRO chief people officer HR
6. "{company_name}" CRO chief revenue officer commercial
7. "{company_name}" management team executives
8. "{company_name}" leadership team

**REQUIRED OUTPUT**:

## C-Suite Executives

| Name | Title | LinkedIn URL | Background | Sales Relevance |
|------|-------|--------------|------------|-----------------|
| [Name] | CFO | [URL] | [Previous roles] | 💰 Budget authority |
| [Name] | CTO | [URL] | | 🔧 Tech decisions |
| [Name] | COO | [URL] | | ⚙️ Operations |
| [Name] | CMO | [URL] | | 📣 Marketing |
| [Name] | CHRO | [URL] | | 👥 People |
| [Name] | CRO | [URL] | | 🤝 Sales/Revenue |

## Executive Summary
- **C-Suite Coverage**: 🟢 Complete / 🟡 Partial / 🔴 Limited
- **Missing Roles**: [List standard C-suite roles not found]
- **Recent Hires**: [Any executives hired in last 12 months]
"""

        # 8. C-SUITE LINKEDIN DEEP - Dedicated search
        prompts["c_suite_linkedin"] = base_context + f"""
**RESEARCH FOCUS**: Find C-Suite LinkedIn Profiles - DEEP SEARCH

Your goal is to find LinkedIn profile URLs for the C-suite of "{company_name}".

Execute these searches:
1. site:linkedin.com/in "{company_name}" CFO
2. site:linkedin.com/in "{company_name}" CTO
3. site:linkedin.com/in "{company_name}" COO
4. site:linkedin.com/in "{company_name}" CMO
5. site:linkedin.com/in "{company_name}" "chief"
6. site:linkedin.com/in "{company_name}" director
7. site:nl.linkedin.com/in "{company_name}" directeur
8. "{company_name}" executives linkedin profiles

**REQUIRED OUTPUT**:

## C-Suite LinkedIn Profiles

| Name | Title | LinkedIn URL |
|------|-------|--------------|
| [Full Name] | CFO | https://linkedin.com/in/[profile] |
| [Full Name] | CTO | https://linkedin.com/in/[profile] |
| [Full Name] | COO | https://linkedin.com/in/[profile] |
| [Full Name] | CMO | https://linkedin.com/in/[profile] |
| [Full Name] | CHRO | https://linkedin.com/in/[profile] |

## All Executive LinkedIn Profiles Found
[List EVERY executive profile you find, even if not C-suite]

| Name | Title | LinkedIn URL |
|------|-------|--------------|
"""

        # 9. SENIOR LEADERSHIP - VPs, Directors
        prompts["senior_leadership"] = base_context + f"""
**RESEARCH FOCUS**: Senior Leadership (VPs, Directors, Heads)

Search for senior leaders at "{company_name}":
1. "{company_name}" VP vice president
2. "{company_name}" director
3. "{company_name}" head of
4. "{company_name}" senior management
5. site:linkedin.com/in "{company_name}" VP
6. site:linkedin.com/in "{company_name}" director

**REQUIRED OUTPUT**:

## Senior Leadership

| Name | Title | Department | LinkedIn URL | Relevance |
|------|-------|------------|--------------|-----------|
| [Name] | VP of Sales | Sales | [URL] | 🤝 |
| [Name] | VP of Engineering | Tech | [URL] | 🔧 |
| [Name] | Director of [X] | [Dept] | [URL] | |
| [Name] | Head of [X] | [Dept] | [URL] | |

## Organizational Insights
- **Org Size Estimate**: [Based on leadership depth]
- **Key Departments**: [Which departments have dedicated leaders]

{seller_hint}
"""

        # 10. BOARD & INVESTORS
        prompts["board_investors"] = base_context + f"""
**RESEARCH FOCUS**: Board of Directors & Investors

Search for "{company_name}":
1. "{company_name}" board of directors
2. "{company_name}" advisory board
3. "{company_name}" investors shareholders
4. "{company_name}" backed by funded by
5. site:linkedin.com/in "{company_name}" board member

**REQUIRED OUTPUT**:

## Board of Directors

| Name | Role | LinkedIn URL | Affiliation |
|------|------|--------------|-------------|
| [Name] | Chairman | [URL] | [Company/Fund] |
| [Name] | Board Member | [URL] | |
| [Name] | Independent Director | [URL] | |

## Investors & Backers

| Investor | Type | Investment | Partner Contact |
|----------|------|------------|-----------------|
| [Fund Name] | VC/PE | [Amount if known] | [Partner name] |

## Advisory Board

| Name | Role | LinkedIn URL | Expertise |
|------|------|--------------|-----------|
"""

        # ═══════════════════════════════════════════════════════════════════════
        # SECTION 3: MARKET INTELLIGENCE (5 queries)
        # ═══════════════════════════════════════════════════════════════════════

        # 11. RECENT NEWS
        prompts["recent_news"] = base_context + f"""
**RESEARCH FOCUS**: Recent News & Developments (Last 90 Days)

Today is {current_date}. Search for recent news about "{company_name}":
1. "{company_name}" news {current_year}
2. "{company_name}" press release
3. "{company_name}" announcement
4. "{company_name}" launch
5. "{company_name}" award
6. "{company_name}" interview
7. "{company_name}" media coverage

**CRITICAL**: Focus on news from the LAST 90 DAYS only!

**REQUIRED OUTPUT**:

## Recent News (Last 90 Days)

| Date | Headline | Type | Source | URL |
|------|----------|------|--------|-----|
| [DD MMM YYYY] | [Title] | 💰/📈/👥/🚀/🤝/⚠️ | [Publication] | [URL] |
| [DD MMM YYYY] | [Title] | | | |
| [DD MMM YYYY] | [Title] | | | |

**Types**: 💰 Funding | 📈 Growth | 👥 People | 🚀 Product | 🤝 Partnership | ⚠️ Challenge

## News Summary
[What's the overall narrative? What are they focused on?]

## Sales Triggers from News
- [Any urgency signals]
- [Growth indicators]
- [Change signals]

If no recent news: "No news found in last 90 days from {current_date}"
"""

        # 12. PARTNERSHIPS & DEALS
        prompts["partnerships_deals"] = base_context + f"""
**RESEARCH FOCUS**: Partnerships, Acquisitions & Strategic Deals

Search for "{company_name}":
1. "{company_name}" partnership
2. "{company_name}" strategic alliance
3. "{company_name}" acquisition acquired
4. "{company_name}" merger
5. "{company_name}" deal signed
6. "{company_name}" collaboration
7. "{company_name}" joint venture

**REQUIRED OUTPUT**:

## Partnerships & Alliances

| Date | Partner | Type | Details | Source |
|------|---------|------|---------|--------|
| [Date] | [Company] | Partnership/Integration | [What they're doing together] | [URL] |

## Acquisitions

| Date | Target/Acquirer | Direction | Amount | Source |
|------|-----------------|-----------|--------|--------|
| [Date] | [Company] | Acquired/Was Acquired | [Amount] | [URL] |

## Strategic Implications
[What do these partnerships tell us about their strategy?]
"""

        # 13. HIRING SIGNALS
        prompts["hiring_signals"] = base_context + f"""
**RESEARCH FOCUS**: Hiring Signals & Job Openings

Search for "{company_name}":
1. "{company_name}" jobs careers
2. "{company_name}" hiring vacatures
3. "{company_name}" job openings
4. site:linkedin.com/jobs "{company_name}"
5. "{company_name}" we are hiring
6. "{company_name}" join our team

**REQUIRED OUTPUT**:

## Current Job Openings

| Role | Department | Level | Location | Source |
|------|------------|-------|----------|--------|
| [Title] | [Dept] | Jr/Sr/Director/VP | [City] | [URL] |

## Hiring Analysis

| Signal | Observation |
|--------|-------------|
| **Total Open Roles** | [Number] |
| **Fastest Growing Teams** | [Departments hiring most] |
| **Senior Hires** | [Executive searches] |
| **New Capabilities** | [Roles suggesting new directions] |
| **Hiring Velocity** | 🔥 Aggressive / ➡️ Steady / ❄️ Slow / 🛑 Freeze |

## Growth Signals
[What does hiring tell us about their priorities?]
"""

        # 14. TECHNOLOGY STACK
        prompts["tech_stack"] = base_context + f"""
**RESEARCH FOCUS**: Technology Stack & Tools

Search for "{company_name}":
1. "{company_name}" technology stack
2. "{company_name}" uses Salesforce
3. "{company_name}" uses HubSpot
4. "{company_name}" AWS Azure Google Cloud
5. "{company_name}" tech tools software
6. "{company_name}" engineering blog
7. site:stackshare.io "{company_name}"
8. site:builtwith.com "{company_name}"

**REQUIRED OUTPUT**:

## Technology Stack

| Category | Tools/Vendors | Source |
|----------|---------------|--------|
| **CRM** | [Salesforce/HubSpot/Pipedrive] | |
| **Marketing** | [Marketo/Mailchimp/etc] | |
| **ERP/Finance** | [SAP/Oracle/NetSuite/Exact] | |
| **Cloud** | [AWS/Azure/GCP] | |
| **Collaboration** | [Slack/Teams/etc] | |
| **HR/People** | [Workday/BambooHR] | |
| **Data/Analytics** | [Snowflake/Databricks/etc] | |
| **Industry-Specific** | [Specialized tools] | |

## Tech Observations
- **Tech Sophistication**: High / Medium / Low
- **Potential Gaps**: [Areas where they might need help]
- **Integration Needs**: [Systems that might need connecting]
"""

        # 15. COMPETITION
        prompts["competition"] = base_context + f"""
**RESEARCH FOCUS**: Competitive Landscape & Market Position

Search for "{company_name}":
1. "{company_name}" competitors
2. "{company_name}" vs comparison
3. "{company_name}" alternative to
4. companies like "{company_name}"
5. "{company_name}" market share
6. "{company_name}" industry ranking

**REQUIRED OUTPUT**:

## Direct Competitors

| Competitor | Positioning | vs. Target Company | Source |
|------------|-------------|-------------------|--------|
| [Company 1] | [What they do] | [Strengths/weaknesses] | [URL] |
| [Company 2] | | | |
| [Company 3] | | | |

## Market Position

| Aspect | Assessment |
|--------|------------|
| **Market Role** | 🥇 Leader / 🥈 Challenger / 🥉 Niche / 🆕 Newcomer |
| **Trajectory** | 📈 Growing / ➡️ Stable / 📉 Declining |
| **Geographic Strength** | [Regions] |

## Competitive Advantages
- [What makes them unique]
- [Key differentiators]

## Competitive Weaknesses
- [Vulnerabilities]
- [Gaps vs competitors]
"""

        return prompts

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
        Comprehensive company research using 15 PARALLEL Gemini calls.
        
        Executes 15 focused research topics in parallel for MAXIMUM coverage:
        
        COMPANY (4):
        1. company_basics - Identity, structure
        2. company_description - What they do
        3. financials - Revenue, funding
        4. products_services - Offerings
        
        PEOPLE (6):
        5. ceo_founder - CEO info
        6. ceo_linkedin_deep - Dedicated LinkedIn search
        7. c_suite - Other C-level
        8. c_suite_linkedin - Dedicated LinkedIn search
        9. senior_leadership - VPs, Directors
        10. board_investors - Board, investors
        
        MARKET (5):
        11. recent_news - Last 90 days
        12. partnerships_deals - Partnerships, M&A
        13. hiring_signals - Jobs, growth
        14. tech_stack - Technology
        15. competition - Competitors
        
        Returns:
            Dictionary with comprehensive research data from all 15 topics
        """
        current_date = datetime.now().strftime("%d %B %Y")
        current_year = datetime.now().year
        
        # Build base context
        base_context = self._build_base_context(
            company_name=company_name,
            country=country,
            city=city,
            linkedin_url=linkedin_url,
            current_date=current_date,
            current_year=current_year,
            language=language
        )
        
        # Build all 15 search prompts
        prompts = self._build_search_prompts(
            company_name=company_name,
            base_context=base_context,
            current_date=current_date,
            current_year=current_year,
            seller_context=seller_context
        )
        
        logger.info(f"Starting Gemini comprehensive research for {company_name} ({len(prompts)} parallel searches)")
        
        # Execute all searches in parallel
        tasks = [
            self._search_single_topic(topic_name, prompt, company_name)
            for topic_name, prompt in prompts.items()
        ]
        
        results = await asyncio.gather(*tasks, return_exceptions=True)
        
        # Process results
        combined_data = []
        total_input_tokens = 0
        total_output_tokens = 0
        successful_topics = 0
        failed_topics = []
        
        topic_names = list(prompts.keys())
        for i, result in enumerate(results):
            topic_name = topic_names[i]
            
            if isinstance(result, Exception):
                logger.error(f"Gemini {topic_name} exception: {str(result)}")
                failed_topics.append(topic_name)
                combined_data.append(f"\n\n## {topic_name.upper().replace('_', ' ')}\n\nError: Search failed")
            elif result.get("success"):
                successful_topics += 1
                combined_data.append(f"\n\n{'='*60}\n## {topic_name.upper().replace('_', ' ')}\n{'='*60}\n\n{result.get('data', '')}")
                token_stats = result.get("token_stats", {})
                total_input_tokens += token_stats.get("input_tokens", 0)
                total_output_tokens += token_stats.get("output_tokens", 0)
            else:
                failed_topics.append(topic_name)
                combined_data.append(f"\n\n## {topic_name.upper().replace('_', ' ')}\n\nError: {result.get('data', 'Unknown error')}")
        
        logger.info(
            f"Gemini comprehensive research completed for {company_name}. "
            f"Successful: {successful_topics}/{len(prompts)} topics. "
            f"Total tokens: {total_input_tokens} in, {total_output_tokens} out"
        )
        
        # Combine all data into structured format
        full_data = f"""# COMPREHENSIVE RESEARCH DATA FOR: {company_name}
Research Date: {current_date}
Location: {city or 'Unknown'}, {country or 'Unknown'}
Total Topics Searched: {len(prompts)}
Successful Searches: {successful_topics}

{''.join(combined_data)}

---

## RESEARCH METADATA

| Metric | Value |
|--------|-------|
| Research Date | {current_date} |
| Total Topics Searched | {len(prompts)} |
| Successful Searches | {successful_topics} |
| Failed Searches | {len(failed_topics)} |
| Failed Topics | {', '.join(failed_topics) if failed_topics else 'None'} |
| Total Input Tokens | {total_input_tokens} |
| Total Output Tokens | {total_output_tokens} |
| Estimated Cost | ${(total_input_tokens * 0.10 + total_output_tokens * 0.40) / 1_000_000:.4f} |
"""

        return {
            "source": "gemini",
            "query": f"{company_name} ({country or 'Unknown'})",
            "data": full_data,
            "success": successful_topics > 0,
            "google_search_used": True,
            "research_date": current_date,
            "topics_searched": len(prompts),
            "topics_successful": successful_topics,
            "topics_failed": failed_topics,
            "token_stats": {
                "input_tokens": total_input_tokens,
                "output_tokens": total_output_tokens,
            }
        }
