"""
Gemini Google Search integration for comprehensive B2B prospect research.

ARCHITECTURE (Cost-Optimized + Maximum Quality):
- Gemini does ALL web searching (30x cheaper than Claude)
- Uses 30 PARALLEL calls for STATE-OF-THE-ART coverage
- Each call focuses on ONE specific research area
- Output: Comprehensive structured raw data for Claude to analyze

Gemini 2.0 Flash pricing: $0.10/1M input, $0.40/1M output
Claude Sonnet 4 pricing: $3.00/1M input, $15.00/1M output

31 parallel calls × ~$0.002 = ~$0.062 total (still 94% cheaper than Claude web search)
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
    
    Uses 31 PARALLEL CALLS for STATE-OF-THE-ART coverage:
    
    COMPANY INFORMATION (4):
    1. company_basics - Identity, founding, locations
    2. company_description - What they do, business model
    3. financials - Revenue, funding, investors
    4. products_services - Detailed product information
    
    PEOPLE (6):
    5. ceo_founder - CEO with LinkedIn URL
    6. ceo_linkedin_deep - Dedicated CEO LinkedIn search
    7. c_suite - CFO, CTO, COO with LinkedIns
    8. c_suite_linkedin - Dedicated C-suite LinkedIn search
    9. senior_leadership - VPs, Directors with LinkedIns
    10. board_investors - Board members, investors
    
    MARKET INTELLIGENCE (5):
    11. recent_news - Last 90 days news
    12. partnerships_deals - Partnerships, acquisitions
    13. hiring_signals - Job postings, growth signals
    14. tech_stack - Technology and tools
    15. competition - Competitors, market position
    
    DEEP INSIGHTS (7):
    16. culture_reviews - Glassdoor, Indeed, employee sentiment
    17. events_speaking - Conferences, webinars, networking
    18. awards_recognition - Industry awards, rankings
    19. media_interviews - Podcasts, interviews, thought leadership
    20. customer_reviews - G2, Capterra, product reviews
    21. challenges_priorities - Public challenges, strategic priorities
    22. certifications_compliance - Regulatory, security, standards
    
    STRATEGIC INTELLIGENCE (8):
    23. sustainability_esg - ESG scores, sustainability reports, CSR
    24. risk_signals - Lawsuits, controversies, red flags
    25. key_accounts_clients - Named customers, case studies
    26. company_history_milestones - Timeline, pivots, evolution
    27. future_plans_roadmap - Announced strategies, direction
    28. social_media_activity - Twitter, LinkedIn, Instagram presence
    29. patents_innovation - R&D, intellectual property
    30. vendor_ecosystem - Current suppliers, technology partners
    
    DUTCH MARKET (1):
    31. dutch_business_media - FD, MT500, Sprout, BNR, Dutch rankings
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
        
        # Build custom intel hint if available (user's own knowledge)
        custom_intel_hint = ""
        if seller_context and seller_context.get("custom_intel"):
            custom_intel_hint = f"""
**INSIDER INTEL (from user's own knowledge - PRIORITIZE this information)**:
{seller_context.get('custom_intel')}

Use this insider information to focus your research and verify/expand on these claims.
"""
        
        # Append custom intel to base context if available
        if custom_intel_hint:
            base_context = base_context + custom_intel_hint
        
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

        # ═══════════════════════════════════════════════════════════════════════
        # SECTION 4: DEEP INSIGHTS (7 new queries for maximum intelligence)
        # ═══════════════════════════════════════════════════════════════════════

        # 16. CULTURE & REVIEWS - Glassdoor, Indeed, employee sentiment
        prompts["culture_reviews"] = base_context + f"""
**RESEARCH FOCUS**: Company Culture & Employee Reviews

Search for employee insights about "{company_name}":
1. "{company_name}" Glassdoor reviews
2. "{company_name}" Indeed reviews
3. "{company_name}" employee reviews
4. "{company_name}" company culture
5. "{company_name}" working at
6. "{company_name}" best place to work
7. "{company_name}" employer rating

**REQUIRED OUTPUT**:

## Employee Reviews & Ratings

| Platform | Rating | # Reviews | Source URL |
|----------|--------|-----------|------------|
| Glassdoor | [X/5] | [Number] | [URL] |
| Indeed | [X/5] | [Number] | [URL] |
| Kununu | [X/5] | [Number] | [URL] |

## Culture Insights

| Aspect | Observation |
|--------|-------------|
| **Overall Sentiment** | 🟢 Positive / 🟡 Mixed / 🔴 Negative |
| **Common Praise** | [What employees like] |
| **Common Complaints** | [What employees dislike] |
| **Work-Life Balance** | [Observations] |
| **Management Style** | [Observations] |
| **Growth Opportunities** | [Observations] |

## Red Flags / Opportunities
- [Any concerning patterns for sales approach]
- [Opportunities based on internal challenges]

If no reviews found: "No employee reviews found on major platforms"
"""

        # 17. EVENTS & SPEAKING - Conferences, webinars, networking
        prompts["events_speaking"] = base_context + f"""
**RESEARCH FOCUS**: Events, Speaking Engagements & Industry Presence

Search for event participation of "{company_name}":
1. "{company_name}" conference speaker
2. "{company_name}" event sponsor
3. "{company_name}" webinar
4. "{company_name}" summit presentation
5. "{company_name}" trade show
6. "{company_name}" industry event
7. CEO or founder name + "keynote" OR "speaker"

**REQUIRED OUTPUT**:

## Speaking Engagements

| Date | Event | Speaker | Topic | Source |
|------|-------|---------|-------|--------|
| [Date] | [Event Name] | [Person] | [Topic if known] | [URL] |

## Event Sponsorships

| Event | Type | Level | Source |
|-------|------|-------|--------|
| [Event Name] | Conference/Trade Show | Gold/Silver/Sponsor | [URL] |

## Webinars & Online Events

| Date | Title | Host | Topic | Source |
|------|-------|------|-------|--------|
| [Date] | [Title] | [Person] | [Topic] | [URL] |

## Industry Presence Analysis
- **Event Activity Level**: 🔥 Very Active / ➡️ Moderate / ❄️ Low
- **Focus Areas**: [What topics do they speak about?]
- **Networking Opportunities**: [Where can we meet them?]
"""

        # 18. AWARDS & RECOGNITION - Industry awards, rankings
        prompts["awards_recognition"] = base_context + f"""
**RESEARCH FOCUS**: Awards, Recognition & Industry Rankings

Search for awards and recognition of "{company_name}":
1. "{company_name}" award winner
2. "{company_name}" recognition
3. "{company_name}" best company
4. "{company_name}" fastest growing
5. "{company_name}" top company
6. "{company_name}" innovation award
7. "{company_name}" industry leader

**REQUIRED OUTPUT**:

## Awards & Recognition

| Year | Award | Category | Issuer | Source |
|------|-------|----------|--------|--------|
| [Year] | [Award Name] | [Category] | [Organization] | [URL] |

## Rankings & Lists

| Year | List/Ranking | Position | Issuer | Source |
|------|--------------|----------|--------|--------|
| [Year] | "Fastest Growing Companies" | #[X] | [Publication] | [URL] |
| [Year] | "Best Employers" | #[X] | [Publication] | [URL] |

## Certifications & Accreditations

| Certification | Issuer | Valid Until | Source |
|---------------|--------|-------------|--------|
| [Cert Name] | [Issuer] | [Date] | [URL] |

## Recognition Analysis
- **Industry Standing**: Well-recognized / Emerging / Unknown
- **Growth Trajectory**: [What do awards suggest about their trajectory?]
- **Credibility Score**: 🟢 High / 🟡 Medium / 🔴 Low
"""

        # 19. MEDIA & INTERVIEWS - Podcasts, interviews, thought leadership
        prompts["media_interviews"] = base_context + f"""
**RESEARCH FOCUS**: Media Appearances, Podcasts & Executive Interviews

Search for media presence of "{company_name}" and its executives:
1. "{company_name}" CEO interview
2. "{company_name}" founder podcast
3. "{company_name}" executive interview
4. "{company_name}" featured in
5. "{company_name}" profile article
6. CEO or founder name + "interview" OR "podcast"
7. "{company_name}" thought leadership

**REQUIRED OUTPUT**:

## Podcast Appearances

| Date | Podcast | Guest | Topic | Link |
|------|---------|-------|-------|------|
| [Date] | [Podcast Name] | [Person] | [Topic discussed] | [URL] |

## Media Interviews

| Date | Publication | Person | Topic | Link |
|------|-------------|--------|-------|------|
| [Date] | [Media Outlet] | [Person] | [Topic] | [URL] |

## Key Quotes & Insights
[Direct quotes from executives that reveal priorities, challenges, or vision]

| Quote | Person | Context | Source |
|-------|--------|---------|--------|
| "[Quote]" | [Name] | [Context] | [URL] |

## Thought Leadership Content

| Type | Title | Author | Link |
|------|-------|--------|------|
| Blog Post | [Title] | [Person] | [URL] |
| LinkedIn Article | [Title] | [Person] | [URL] |
| White Paper | [Title] | [Company] | [URL] |

## Media Presence Analysis
- **Visibility Level**: 🔥 High / ➡️ Moderate / ❄️ Low
- **Key Themes**: [What do they talk about most?]
- **Conversation Starters**: [Topics to discuss based on their public statements]
"""

        # 20. CUSTOMER REVIEWS - G2, Capterra, product reviews
        prompts["customer_reviews"] = base_context + f"""
**RESEARCH FOCUS**: Customer Reviews & Product Ratings

Search for customer feedback about "{company_name}":
1. "{company_name}" G2 reviews
2. "{company_name}" Capterra reviews
3. "{company_name}" Trustpilot
4. "{company_name}" customer reviews
5. "{company_name}" product reviews
6. "{company_name}" testimonials
7. site:g2.com "{company_name}"

**REQUIRED OUTPUT**:

## Product/Service Reviews

| Platform | Rating | # Reviews | Source URL |
|----------|--------|-----------|------------|
| G2 | [X/5] | [Number] | [URL] |
| Capterra | [X/5] | [Number] | [URL] |
| Trustpilot | [X/5] | [Number] | [URL] |
| Google Reviews | [X/5] | [Number] | [URL] |

## Review Analysis

| Aspect | Positive Themes | Negative Themes |
|--------|-----------------|-----------------|
| Product Quality | [What customers like] | [Complaints] |
| Customer Service | [Praise] | [Issues] |
| Value for Money | [Observations] | [Concerns] |
| Ease of Use | [Positive] | [Negative] |

## Notable Customer Quotes
| Quote | Rating | Date | Source |
|-------|--------|------|--------|
| "[Quote]" | [X/5] | [Date] | [Platform] |

## Customer Satisfaction Summary
- **Overall Sentiment**: 🟢 Very Positive / 🟡 Mixed / 🔴 Concerning
- **Net Promoter Score** (if available): [Score]
- **Key Strengths**: [What customers love]
- **Key Weaknesses**: [Recurring complaints]
"""

        # 21. CHALLENGES & PRIORITIES - Public statements about challenges
        prompts["challenges_priorities"] = base_context + f"""
**RESEARCH FOCUS**: Public Challenges, Strategic Priorities & Pain Points

Search for challenges and priorities mentioned by "{company_name}":
1. "{company_name}" challenges
2. "{company_name}" strategy priorities
3. "{company_name}" transformation
4. "{company_name}" initiative
5. "{company_name}" investing in
6. "{company_name}" focus areas
7. CEO or founder name + "priorities" OR "challenges" OR "strategy"
8. "{company_name}" digital transformation
9. "{company_name}" growth strategy

**REQUIRED OUTPUT**:

## Publicly Stated Priorities

| Priority | Evidence | Source | Date |
|----------|----------|--------|------|
| [Priority 1] | [Quote or context] | [Source] | [Date] |
| [Priority 2] | | | |

## Acknowledged Challenges

| Challenge | Context | Source | Date |
|-----------|---------|--------|------|
| [Challenge 1] | [How they described it] | [Source] | [Date] |
| [Challenge 2] | | | |

## Strategic Initiatives

| Initiative | Status | Investment | Source |
|------------|--------|------------|--------|
| [Initiative Name] | Planning/In Progress/Completed | [Amount if known] | [URL] |

## Transformation & Change Signals

| Signal | Type | Implication for Sales |
|--------|------|----------------------|
| [Signal] | Tech/People/Process/Market | [How we can help] |

## Pain Point Analysis
Based on public statements, likely pain points include:
1. [Pain point with evidence]
2. [Pain point with evidence]
3. [Pain point with evidence]

{seller_hint}
"""

        # 22. CERTIFICATIONS & COMPLIANCE - Regulatory, security, standards
        prompts["certifications_compliance"] = base_context + f"""
**RESEARCH FOCUS**: Certifications, Compliance & Regulatory Status

Search for certifications and compliance of "{company_name}":
1. "{company_name}" ISO certification
2. "{company_name}" SOC 2
3. "{company_name}" GDPR compliant
4. "{company_name}" certified
5. "{company_name}" accredited
6. "{company_name}" compliance
7. "{company_name}" security certification
8. "{company_name}" industry standards

**REQUIRED OUTPUT**:

## Certifications

| Certification | Type | Status | Valid Until | Source |
|---------------|------|--------|-------------|--------|
| ISO 27001 | Security | ✅/❌/❓ | [Date] | [URL] |
| ISO 9001 | Quality | ✅/❌/❓ | [Date] | [URL] |
| SOC 2 Type II | Security | ✅/❌/❓ | [Date] | [URL] |
| GDPR | Privacy | ✅/❌/❓ | N/A | [URL] |

## Industry-Specific Certifications

| Certification | Relevance | Status | Source |
|---------------|-----------|--------|--------|
| [Cert Name] | [Why it matters] | ✅/❌/❓ | [URL] |

## Compliance Status

| Regulation | Status | Evidence |
|------------|--------|----------|
| GDPR | Compliant/Unknown | [Evidence] |
| HIPAA | Compliant/Unknown/N/A | [Evidence] |
| PCI-DSS | Compliant/Unknown/N/A | [Evidence] |

## Regulatory Environment

| Aspect | Observation |
|--------|-------------|
| **Industry Regulations** | [Key regulations they must comply with] |
| **Compliance Maturity** | 🟢 Mature / 🟡 Developing / 🔴 Basic |
| **Recent Compliance News** | [Any compliance-related news] |

## Security & Trust Signals
- **Security Page**: [URL if found]
- **Trust Center**: [URL if found]
- **Data Processing Agreement**: [Available/Not found]
"""

        # ═══════════════════════════════════════════════════════════════════════
        # SECTION 5: STRATEGIC INTELLIGENCE (8 new queries for state-of-the-art)
        # ═══════════════════════════════════════════════════════════════════════

        # 23. SUSTAINABILITY & ESG - Environmental, Social, Governance
        prompts["sustainability_esg"] = base_context + f"""
**RESEARCH FOCUS**: Sustainability, ESG & Corporate Responsibility

Search for sustainability and ESG information about "{company_name}":
1. "{company_name}" sustainability report
2. "{company_name}" ESG score rating
3. "{company_name}" carbon footprint emissions
4. "{company_name}" CSR corporate social responsibility
5. "{company_name}" duurzaamheid sustainability
6. "{company_name}" climate goals net zero
7. "{company_name}" CSRD report
8. "{company_name}" environmental impact

**REQUIRED OUTPUT**:

## ESG Ratings & Scores

| Rating Agency | Score | Date | Source |
|---------------|-------|------|--------|
| [Agency] | [Score] | [Date] | [URL] |

## Environmental Commitments

| Commitment | Target | Timeline | Status |
|------------|--------|----------|--------|
| Carbon Neutrality | [Target] | [Year] | On Track/Behind/Achieved |
| Renewable Energy | [%] | [Year] | |
| Waste Reduction | [Target] | [Year] | |

## Sustainability Reports

| Year | Title | Key Highlights | URL |
|------|-------|----------------|-----|
| [Year] | [Report Name] | [Key points] | [URL] |

## Social Responsibility

| Initiative | Focus | Impact |
|------------|-------|--------|
| [Initiative] | Community/Diversity/Education | [Description] |

## Governance

| Aspect | Details |
|--------|---------|
| **Board Diversity** | [Observations] |
| **Ethics Policy** | [Available/Not found] |
| **Whistleblower Policy** | [Available/Not found] |

## CSRD/Regulatory Compliance
- **CSRD Status**: Required/Voluntary/Not Applicable
- **Sustainability Report**: [URL if available]
- **Key ESG Challenges**: [Identified challenges]
"""

        # 24. RISK SIGNALS - Negative news, legal issues, red flags
        prompts["risk_signals"] = base_context + f"""
**RESEARCH FOCUS**: Risk Signals, Red Flags & Negative News

Search for potential risk indicators about "{company_name}":
1. "{company_name}" lawsuit legal case
2. "{company_name}" controversy scandal
3. "{company_name}" layoffs restructuring
4. "{company_name}" bankruptcy financial trouble
5. "{company_name}" fine penalty regulatory
6. "{company_name}" data breach security incident
7. "{company_name}" negative reviews complaints
8. "{company_name}" CEO fired resigned controversy
9. "{company_name}" fraud investigation

**CRITICAL**: Report factually what you find, don't speculate.

**REQUIRED OUTPUT**:

## Legal Issues & Lawsuits

| Date | Case | Type | Status | Source |
|------|------|------|--------|--------|
| [Date] | [Description] | Civil/Criminal/Regulatory | Ongoing/Settled/Dismissed | [URL] |

## Regulatory Issues

| Date | Issue | Regulator | Fine/Penalty | Source |
|------|-------|-----------|--------------|--------|
| [Date] | [Description] | [Agency] | [Amount] | [URL] |

## Workforce Issues

| Date | Event | Scale | Source |
|------|-------|-------|--------|
| [Date] | Layoffs/Restructuring | [# employees] | [URL] |

## Financial Red Flags

| Signal | Evidence | Severity |
|--------|----------|----------|
| [Signal] | [Description] | 🔴 High / 🟡 Medium / 🟢 Low |

## Reputation Issues

| Date | Issue | Impact | Source |
|------|-------|--------|--------|
| [Date] | [Description] | [Business impact] | [URL] |

## Risk Summary
- **Overall Risk Level**: 🟢 Low / 🟡 Medium / 🔴 High
- **Key Risk Areas**: [List main concerns]
- **Mitigating Factors**: [Positive counter-signals]

If no significant risks found: "No significant risk signals identified in public sources"
"""

        # 25. KEY ACCOUNTS & CLIENTS - Customer logos, references
        prompts["key_accounts_clients"] = base_context + f"""
**RESEARCH FOCUS**: Key Accounts, Named Clients & Customer References

Search for customer information about "{company_name}":
1. "{company_name}" customers clients
2. "{company_name}" case study success story
3. "{company_name}" testimonial reference
4. "{company_name}" trusted by used by
5. "{company_name}" customer logos
6. "{company_name}" partnership with [industry leader]
7. site:{company_name} case study OR customers
8. "{company_name}" klanten referenties

**REQUIRED OUTPUT**:

## Named Customers

| Customer | Industry | Relationship | Source |
|----------|----------|--------------|--------|
| [Company Name] | [Industry] | Customer/Partner/Case Study | [URL] |
| [Company Name] | [Industry] | | |
| [Company Name] | [Industry] | | |

## Case Studies

| Customer | Challenge | Solution | Results | URL |
|----------|-----------|----------|---------|-----|
| [Name] | [Problem] | [What they did] | [Outcomes] | [URL] |

## Testimonials & Quotes

| Quote | Person | Company | Role | Source |
|-------|--------|---------|------|--------|
| "[Quote]" | [Name] | [Company] | [Title] | [URL] |

## Customer Segments

| Segment | Examples | Estimated % |
|---------|----------|-------------|
| Enterprise | [Names] | |
| Mid-Market | [Names] | |
| SMB | [Names] | |

## Industry Verticals Served

| Industry | Notable Customers | Strength |
|----------|-------------------|----------|
| [Industry] | [Names] | 🟢 Strong / 🟡 Moderate / 🔴 Weak |

## Customer Concentration Risk
- **Largest Customer**: [If known]
- **Revenue Concentration**: [Observations]
"""

        # 26. COMPANY HISTORY & MILESTONES - Timeline, pivots, evolution
        prompts["company_history_milestones"] = base_context + f"""
**RESEARCH FOCUS**: Company History, Milestones & Evolution

Search for historical information about "{company_name}":
1. "{company_name}" history founded
2. "{company_name}" timeline milestones
3. "{company_name}" anniversary years
4. "{company_name}" growth story journey
5. "{company_name}" evolution pivot
6. "{company_name}" acquisition history
7. "{company_name}" original product first
8. who founded "{company_name}" story

**REQUIRED OUTPUT**:

## Founding Story

| Element | Details |
|---------|---------|
| **Founded** | [Year] |
| **Founder(s)** | [Names] |
| **Original Location** | [City, Country] |
| **Original Mission** | [Why they started] |
| **Initial Product/Service** | [What they first offered] |

## Key Milestones Timeline

| Year | Milestone | Significance |
|------|-----------|--------------|
| [Year] | Company founded | Origin |
| [Year] | [Event] | [Why it matters] |
| [Year] | [Event] | |
| [Year] | [Event] | |
| [Year] | [Event] | |

## Major Pivots & Evolutions

| Period | From | To | Trigger |
|--------|------|-----|---------|
| [Year] | [Old focus] | [New focus] | [Why they changed] |

## Acquisition History

| Year | Acquired | Purpose | Source |
|------|----------|---------|--------|
| [Year] | [Company] | [Strategic reason] | [URL] |

## Leadership Evolution

| Period | CEO/Leader | Major Changes |
|--------|------------|---------------|
| [Years] | [Name] | [What happened under their leadership] |

## Company Culture Evolution
[How has the company culture changed over time?]
"""

        # 27. FUTURE PLANS & ROADMAP - Announced strategies, direction
        prompts["future_plans_roadmap"] = base_context + f"""
**RESEARCH FOCUS**: Future Plans, Strategy & Roadmap

Search for future direction of "{company_name}":
1. "{company_name}" roadmap plans {current_year + 1}
2. "{company_name}" strategy vision future
3. "{company_name}" expansion plans
4. "{company_name}" new markets products
5. "{company_name}" investment plans
6. "{company_name}" CEO vision interview future
7. "{company_name}" annual report outlook
8. "{company_name}" investor presentation strategy

**REQUIRED OUTPUT**:

## Announced Strategic Priorities

| Priority | Timeline | Investment | Source |
|----------|----------|------------|--------|
| [Priority] | [Timeframe] | [Amount if known] | [URL] |

## Expansion Plans

| Type | Target | Timeline | Status |
|------|--------|----------|--------|
| Geographic | [Countries/Regions] | [When] | Announced/In Progress |
| Product | [New offerings] | [When] | |
| Market Segment | [New segments] | [When] | |

## Technology Roadmap

| Initiative | Description | Timeline |
|------------|-------------|----------|
| [Initiative] | [What they plan to do] | [When] |

## M&A Appetite

| Signal | Evidence |
|--------|----------|
| **Acquisition Interest** | Active/Moderate/No signals |
| **Target Types** | [What they might acquire] |
| **Recent Statements** | [Quotes about M&A] |

## Investment Priorities

| Area | Level | Evidence |
|------|-------|----------|
| Technology | 🔥 High / ➡️ Medium / ❄️ Low | [Quote/source] |
| People | 🔥 High / ➡️ Medium / ❄️ Low | |
| Geographic Expansion | 🔥 High / ➡️ Medium / ❄️ Low | |
| Sustainability | 🔥 High / ➡️ Medium / ❄️ Low | |

## CEO/Leadership Quotes on Future
| Quote | Person | Context | Source |
|-------|--------|---------|--------|
| "[Quote about future]" | [Name] | [Context] | [URL] |
"""

        # 28. SOCIAL MEDIA ACTIVITY - Twitter, LinkedIn, Instagram presence
        prompts["social_media_activity"] = base_context + f"""
**RESEARCH FOCUS**: Social Media Presence & Activity

Search for social media presence of "{company_name}":
1. "{company_name}" Twitter OR X.com
2. "{company_name}" Instagram
3. "{company_name}" YouTube channel
4. "{company_name}" Facebook page
5. "{company_name}" TikTok
6. site:twitter.com "{company_name}"
7. site:instagram.com "{company_name}"

**REQUIRED OUTPUT**:

## Social Media Accounts

| Platform | Handle/URL | Followers | Activity Level |
|----------|------------|-----------|----------------|
| LinkedIn | [URL] | [Number] | 🔥 Active / ➡️ Moderate / ❄️ Inactive |
| Twitter/X | [URL] | [Number] | |
| Instagram | [URL] | [Number] | |
| YouTube | [URL] | [Subscribers] | |
| Facebook | [URL] | [Followers] | |
| TikTok | [URL] | [Followers] | |

## Content Analysis

| Platform | Content Type | Posting Frequency | Engagement |
|----------|--------------|-------------------|------------|
| LinkedIn | [What they post] | [How often] | High/Medium/Low |
| Twitter | [Topics] | [Frequency] | |
| Instagram | [Visual style] | [Frequency] | |

## Key Themes & Messaging

| Theme | Frequency | Example |
|-------|-----------|---------|
| [Topic 1] | Often/Sometimes/Rarely | [Example post] |
| [Topic 2] | | |

## Executive Social Presence

| Name | Platform | Handle | Activity |
|------|----------|--------|----------|
| CEO | LinkedIn/Twitter | [Handle] | Active/Moderate/Low |
| [Other exec] | | | |

## Social Media Insights
- **Brand Voice**: Professional/Casual/Technical/Friendly
- **Visual Style**: Corporate/Creative/Minimal/Bold
- **Engagement Level**: High/Medium/Low
- **Key Hashtags Used**: [List]
"""

        # 29. PATENTS & INNOVATION - R&D, intellectual property
        prompts["patents_innovation"] = base_context + f"""
**RESEARCH FOCUS**: Patents, Innovation & R&D

Search for innovation indicators about "{company_name}":
1. "{company_name}" patent
2. "{company_name}" innovation R&D
3. "{company_name}" research development
4. "{company_name}" intellectual property
5. site:patents.google.com "{company_name}"
6. "{company_name}" technology breakthrough
7. "{company_name}" innovation lab
8. "{company_name}" patent application

**REQUIRED OUTPUT**:

## Patent Portfolio

| Patent | Title | Date | Category | Source |
|--------|-------|------|----------|--------|
| [Number] | [Title] | [Year] | [Technology area] | [URL] |

## Patent Statistics

| Metric | Value |
|--------|-------|
| **Total Patents** | [Number if found] |
| **Recent Patents (3 years)** | [Number] |
| **Key Technology Areas** | [List] |
| **Geographic Coverage** | [Countries] |

## R&D Investment

| Year | Investment | % of Revenue | Source |
|------|------------|--------------|--------|
| [Year] | [Amount] | [%] | [URL] |

## Innovation Initiatives

| Initiative | Focus | Status | Source |
|------------|-------|--------|--------|
| Innovation Lab | [What they're working on] | Active/Planned | [URL] |
| Research Partnership | [Partner] | | |
| Accelerator/Incubator | [Program name] | | |

## Technology Focus Areas

| Area | Investment Level | Evidence |
|------|------------------|----------|
| AI/ML | 🔥 High / ➡️ Medium / ❄️ Low | [Patents/initiatives] |
| IoT | | |
| Cloud | | |
| [Industry-specific] | | |

## Innovation Culture
- **R&D Team Size**: [If known]
- **Innovation Awards**: [List any]
- **Open Innovation**: Yes/No (collaborations, hackathons, etc.)
"""

        # 30. VENDOR ECOSYSTEM - Current suppliers, technology partners
        prompts["vendor_ecosystem"] = base_context + f"""
**RESEARCH FOCUS**: Vendor Ecosystem & Technology Partners

Search for vendor and partner relationships of "{company_name}":
1. "{company_name}" partners technology
2. "{company_name}" powered by uses
3. "{company_name}" integration with
4. "{company_name}" certified partner
5. "{company_name}" vendor supplier
6. "{company_name}" platform built on
7. site:partner.* "{company_name}"
8. "{company_name}" technology alliance

**REQUIRED OUTPUT**:

## Technology Partners

| Partner | Type | Relationship | Source |
|---------|------|--------------|--------|
| [Company] | Cloud/CRM/ERP/etc | Certified Partner/Customer/Integration | [URL] |
| [Company] | | | |

## Consulting & Services Partners

| Partner | Focus | Relationship | Source |
|---------|-------|--------------|--------|
| [Company] | Implementation/Strategy | Partner/Vendor | [URL] |

## Current Vendor Stack (Known)

| Category | Vendor | Evidence |
|----------|--------|----------|
| Cloud | AWS/Azure/GCP | [Source] |
| CRM | Salesforce/HubSpot/etc | |
| ERP | SAP/Oracle/etc | |
| BI/Analytics | [Vendor] | |
| HR | [Vendor] | |

## Integration Ecosystem

| Integration | Type | Source |
|-------------|------|--------|
| [Platform] | Native/API/iPaaS | [URL] |

## Partner Program Participation

| Program | Level | Benefits |
|---------|-------|----------|
| [Vendor] Partner Program | Gold/Silver/Certified | [Benefits received] |

## Vendor Relationship Signals
- **Technology Loyalty**: Single-vendor/Multi-vendor/Best-of-breed
- **Partnership Depth**: Strategic/Tactical/Transactional
- **Potential Displacement Opportunities**: [Areas where current vendor may be weak]

{seller_hint}
"""

        # 31. DUTCH BUSINESS MEDIA - Dutch-specific sources (for NL companies)
        prompts["dutch_business_media"] = base_context + f"""
**RESEARCH FOCUS**: Dutch Business Media & Rankings

Search for Dutch business coverage of "{company_name}":
1. "{company_name}" site:fd.nl (Financieele Dagblad)
2. "{company_name}" site:mt.nl (Management Team)
3. "{company_name}" site:sprout.nl (Startups)
4. "{company_name}" site:computable.nl (IT)
5. "{company_name}" site:emerce.nl (E-commerce/Digital)
6. "{company_name}" site:bnr.nl (BNR Nieuwsradio)
7. "{company_name}" FD Gazellen
8. "{company_name}" MT500
9. "{company_name}" MSc Best Managed Companies
10. "{company_name}" site:quotenet.nl (Quote)

**REQUIRED OUTPUT**:

## Dutch Business Rankings

| Year | Ranking | Position | Source |
|------|---------|----------|--------|
| [Year] | FD Gazellen (fastest growing) | #[X] | [URL] |
| [Year] | MT500 (largest companies) | #[X] | [URL] |
| [Year] | Best Managed Companies | Winner/Finalist | [URL] |
| [Year] | EY Entrepreneur of the Year | | [URL] |
| [Year] | MSc Best Workplaces | #[X] | [URL] |

## Dutch Media Coverage

| Date | Publication | Headline | Type | URL |
|------|-------------|----------|------|-----|
| [Date] | FD | [Title] | Interview/News/Analysis | [URL] |
| [Date] | MT | [Title] | | [URL] |
| [Date] | BNR | [Title] | Podcast/Interview | [URL] |

## Executive Interviews (Dutch Media)

| Date | Publication | Person | Topic | URL |
|------|-------------|--------|-------|-----|
| [Date] | [Media] | [CEO/CFO] | [Subject] | [URL] |

## Key Quotes from Dutch Media

| Quote | Person | Publication | Date |
|-------|--------|-------------|------|
| "[Quote]" | [Name] | [Media] | [Date] |

## Dutch Business Insights
- **Media Profile**: 🔥 High / ➡️ Moderate / ❄️ Low
- **Key Themes in Dutch Media**: [What Dutch media writes about them]
- **Perception**: [How are they perceived in Dutch business community]

If no Dutch coverage found: "No significant coverage found in major Dutch business publications"
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
        Comprehensive company research using 31 PARALLEL Gemini calls.
        
        Executes 31 focused research topics in parallel for STATE-OF-THE-ART coverage:
        
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
        
        DEEP INSIGHTS (7):
        16. culture_reviews - Glassdoor, Indeed, employee sentiment
        17. events_speaking - Conferences, webinars, networking
        18. awards_recognition - Industry awards, rankings
        19. media_interviews - Podcasts, interviews, thought leadership
        20. customer_reviews - G2, Capterra, product reviews
        21. challenges_priorities - Public challenges, strategic priorities
        22. certifications_compliance - Regulatory, security, standards
        
        STRATEGIC INTELLIGENCE (8):
        23. sustainability_esg - ESG, sustainability, CSR
        24. risk_signals - Lawsuits, controversies, red flags
        25. key_accounts_clients - Named customers, case studies
        26. company_history_milestones - Timeline, pivots
        27. future_plans_roadmap - Announced strategies
        28. social_media_activity - Twitter, LinkedIn, Instagram
        29. patents_innovation - R&D, intellectual property
        30. vendor_ecosystem - Suppliers, technology partners
        
        DUTCH MARKET (1):
        31. dutch_business_media - FD, MT500, Sprout, Dutch rankings
        
        Returns:
            Dictionary with comprehensive research data from all 31 topics
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
