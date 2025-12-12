"""
Gemini Google Search integration for comprehensive B2B prospect research.

ARCHITECTURE (Cost-Optimized + High Quality):
- Gemini does ALL web searching (30x cheaper than Claude)
- Uses MULTIPLE PARALLEL calls for thorough coverage
- Each call focuses on ONE specific research area
- Output: Comprehensive structured raw data for Claude to analyze

Gemini 2.0 Flash pricing: $0.10/1M input, $0.40/1M output
Claude Sonnet 4 pricing: $3.00/1M input, $15.00/1M output

7 parallel calls × ~$0.002 = ~$0.014 total (still 98% cheaper than Claude web search)
"""
import os
import logging
import asyncio
from datetime import datetime
from typing import Dict, Any, Optional, List
from google import genai
from google.genai import types
from app.i18n.utils import get_language_instruction
from app.i18n.config import DEFAULT_LANGUAGE

logger = logging.getLogger(__name__)


class GeminiResearcher:
    """
    Comprehensive B2B research using Gemini with Google Search grounding.
    
    Uses MULTIPLE PARALLEL CALLS for thorough coverage:
    1. Company Basics - Identity, founding, locations
    2. Financials - Revenue, funding, investors
    3. CEO/Founder - Primary decision maker + LinkedIn
    4. C-Suite Leadership - CFO, CTO, COO + LinkedIns
    5. Senior Leadership - VPs, Directors + LinkedIns
    6. Recent News - Last 90 days
    7. Hiring & Tech Stack - Vacatures, tools, growth signals
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
        """
        Execute a single focused search topic.
        
        Args:
            topic_name: Name of the research topic (for logging)
            prompt: The search prompt
            company_name: Company being researched
            
        Returns:
            Dictionary with topic results
        """
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
        
        return f"""You are an elite B2B sales intelligence researcher.

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
        Build focused search prompts for each research area.
        
        Returns a dictionary of topic -> prompt.
        """
        # Build seller hint if available
        seller_hint = ""
        if seller_context and seller_context.get("has_context"):
            pain_points = seller_context.get("ideal_pain_points", [])
            if pain_points:
                seller_hint = f"\n\n**Sales Focus**: Look for signals related to: {', '.join(pain_points[:3])}"
        
        prompts = {}
        
        # 1. COMPANY BASICS - Identity, structure, locations
        prompts["company_basics"] = base_context + f"""
**RESEARCH FOCUS**: Company Identity & Basics

Search for the following about "{company_name}":
1. "{company_name}" official website about
2. "{company_name}" Wikipedia OR Crunchbase OR company profile
3. "{company_name}" founded history headquarters
4. "{company_name}" offices locations branches

**REQUIRED OUTPUT FORMAT** (use tables):

## Company Identity

| Field | Value | Source URL |
|-------|-------|------------|
| Legal Name | [Full registered name] | [URL] |
| Trading Name | [If different] | [URL] |
| Industry | [Sector → Sub-sector] | |
| Founded | [Year] | [URL] |
| Headquarters | [City, Country] | |
| Other Locations | [List all offices/branches] | |
| Website | [URL] | |
| LinkedIn Company Page | [URL if found] | |

## Company Description
[3-4 sentences: What they do, their core business, value proposition]

## Business Model

| Aspect | Details |
|--------|---------|
| Type | B2B / B2C / B2B2C / Marketplace / SaaS / Services |
| Customer Segment | Enterprise / Mid-market / SMB / Consumer |
| Key Verticals | [Industries they serve] |
| Named Customers | [Any logos/testimonials found] |

Be thorough - search multiple sources to verify information.
"""

        # 2. FINANCIALS - Revenue, funding, size
        prompts["financials"] = base_context + f"""
**RESEARCH FOCUS**: Financial Information & Company Size

Search extensively for financial data about "{company_name}":
1. "{company_name}" revenue OR turnover OR omzet
2. "{company_name}" funding investment raised series
3. "{company_name}" valuation
4. "{company_name}" employees headcount FTE
5. "{company_name}" acquisition OR merger
6. "{company_name}" investors shareholders

**REQUIRED OUTPUT FORMAT**:

## Company Size & Financials

| Metric | Value | Trend | Source URL |
|--------|-------|-------|------------|
| Employees | [Number or range e.g. 50-100] | 📈 Growing / ➡️ Stable / 📉 Shrinking | [URL] |
| Revenue | [Amount with currency, or estimate] | | [URL] |
| Valuation | [If known] | | [URL] |

## Funding History

| Date | Round | Amount | Lead Investors | Source URL |
|------|-------|--------|----------------|------------|
| [Date] | [Seed/Series A/B/etc] | [Amount] | [Names] | [URL] |

## Ownership & Investors

| Type | Details |
|------|---------|
| Ownership | Private / Public / PE-backed / VC-backed / Family |
| Key Investors | [Names and affiliations] |
| Parent Company | [If applicable] |

If no financial data found, state "No public financial data available" - don't invent numbers.
"""

        # 3. CEO/FOUNDER - Primary decision maker
        prompts["ceo_founder"] = base_context + f"""
**RESEARCH FOCUS**: CEO & Founder(s) - CRITICAL for sales targeting

Search extensively for the CEO and founders of "{company_name}":
1. "{company_name}" CEO founder managing director
2. site:linkedin.com/in "{company_name}" CEO
3. site:linkedin.com/in "{company_name}" founder
4. "{company_name}" oprichter directeur (Dutch term)
5. "{company_name}" leadership management team

**CRITICAL: Include FULL LinkedIn URLs for each person!**

**REQUIRED OUTPUT FORMAT**:

## CEO / Founder(s)

| Name | Title | LinkedIn URL | Background |
|------|-------|--------------|------------|
| [Full Name] | CEO / Managing Director | https://linkedin.com/in/[exact-url] | [Previous roles, education, notable achievements] |
| [Full Name] | Founder / Co-Founder | https://linkedin.com/in/[exact-url] | [Background] |

## Detailed Profile: CEO

### [Full Name]
- **Current Role**: [Title] at {company_name}
- **LinkedIn**: [FULL URL]
- **Background**: [2-3 sentences about their career path]
- **Education**: [Degrees, institutions if found]
- **Previous Companies**: [List]
- **Notable**: [Awards, speaking engagements, publications]
- **Tenure at Company**: [When they joined/founded]

## Founder Story
[If available: How/when was the company founded? What problem were they solving?]

**IMPORTANT**: If you cannot find the LinkedIn URL, search specifically:
- site:linkedin.com/in [person's full name] {company_name}
- [person's name] linkedin
"""

        # 4. C-SUITE LEADERSHIP - CFO, CTO, COO, CMO, etc.
        prompts["c_suite"] = base_context + f"""
**RESEARCH FOCUS**: C-Suite Executive Team (excluding CEO)

Search for ALL C-level executives at "{company_name}":
1. "{company_name}" CFO "chief financial officer"
2. "{company_name}" CTO "chief technology officer" OR "chief technical officer"
3. "{company_name}" COO "chief operating officer"
4. "{company_name}" CMO "chief marketing officer"
5. "{company_name}" CHRO "chief human resources" OR "chief people officer"
6. "{company_name}" CRO "chief revenue officer" OR "chief commercial officer"
7. site:linkedin.com/in "{company_name}" chief
8. "{company_name}" management team executive team

**CRITICAL: Include FULL LinkedIn URLs for EVERY person found!**

**REQUIRED OUTPUT FORMAT**:

## C-Suite Executives

| Name | Title | LinkedIn URL | Background | Sales Relevance |
|------|-------|--------------|------------|-----------------|
| [Full Name] | CFO | https://linkedin.com/in/[url] | [Previous roles] | 💰 Budget authority |
| [Full Name] | CTO/CIO | https://linkedin.com/in/[url] | | 🔧 Tech decisions |
| [Full Name] | COO | https://linkedin.com/in/[url] | | ⚙️ Operations |
| [Full Name] | CMO | https://linkedin.com/in/[url] | | 📣 Marketing |
| [Full Name] | CHRO/CPO | https://linkedin.com/in/[url] | | 👥 People |
| [Full Name] | CRO/CCO | https://linkedin.com/in/[url] | | 🤝 Revenue/Sales |

## Executive Details

For each C-suite member found, include:
- Full name and exact title
- LinkedIn URL (REQUIRED - search specifically if needed)
- Brief background (previous roles, expertise)
- How long they've been in the role (if known)
- Recent moves (new hires are important signals!)

## Coverage Assessment
- **C-Suite Coverage**: 🟢 Comprehensive / 🟡 Partial / 🔴 Limited
- **Missing Roles**: [List any standard C-suite roles not found]
"""

        # 5. SENIOR LEADERSHIP - VPs, Directors, Heads
        prompts["senior_leadership"] = base_context + f"""
**RESEARCH FOCUS**: Senior Leadership (VPs, Directors, Heads of Department)

Search for senior leaders at "{company_name}":
1. site:linkedin.com/in "{company_name}" VP "vice president"
2. site:linkedin.com/in "{company_name}" director
3. site:linkedin.com/in "{company_name}" "head of"
4. "{company_name}" leadership team management
5. "{company_name}" senior management

**CRITICAL: Include FULL LinkedIn URLs for EVERY person found!**

**REQUIRED OUTPUT FORMAT**:

## Senior Leadership (VPs, Directors, Heads)

| Name | Title | Department | LinkedIn URL | Potential Relevance |
|------|-------|------------|--------------|---------------------|
| [Full Name] | VP of [X] | [Dept] | https://linkedin.com/in/[url] | [Why might they be relevant] |
| [Full Name] | Director of [X] | [Dept] | https://linkedin.com/in/[url] | |
| [Full Name] | Head of [X] | [Dept] | https://linkedin.com/in/[url] | |

## Board of Directors / Advisors

| Name | Role | LinkedIn URL | Affiliation |
|------|------|--------------|-------------|
| [Name] | Chairman | https://linkedin.com/in/[url] | [Company/Fund] |
| [Name] | Board Member | https://linkedin.com/in/[url] | |

## Organizational Insights
- **Company Size Estimate** (based on leadership found): [X-Y employees]
- **Leadership Depth**: [Deep/Medium/Shallow hierarchy]
- **Recent Leadership Changes**: [Any new hires or departures noted]

{seller_hint}
"""

        # 6. RECENT NEWS - Last 90 days
        prompts["recent_news"] = base_context + f"""
**RESEARCH FOCUS**: Recent News & Developments (Last 90 Days)

Today is {current_date}. Search for recent news about "{company_name}":
1. "{company_name}" news {current_year}
2. "{company_name}" press release announcement {current_year}
3. "{company_name}" partnership deal signed
4. "{company_name}" expansion growth acquisition
5. "{company_name}" funding investment raised
6. "{company_name}" award winner
7. "{company_name}" new product launch
8. "{company_name}" executive hire appoints

**CRITICAL**: Only include news from the LAST 90 DAYS (since {current_date}).

**REQUIRED OUTPUT FORMAT**:

## Recent News (Last 90 Days from {current_date})

| Date | Headline | Type | Source | URL |
|------|----------|------|--------|-----|
| [DD MMM YYYY] | [Headline] | 💰/📈/👥/🚀/🤝/⚠️ | [Publication] | [URL] |

**News Types**:
- 💰 Funding/Financial
- 📈 Growth/Expansion  
- 👥 People/Leadership Change
- 🚀 Product/Launch
- 🤝 Partnership/Deal
- ⚠️ Challenge/Setback

## News Summary
[2-3 sentences: What's the overall narrative? What are they focused on? Any patterns?]

## Key Signals for Sales
- **Positive Signals**: [Growth indicators, expansion, new initiatives]
- **Potential Challenges**: [Any difficulties mentioned]
- **Timing Opportunities**: [Events that create urgency]

If no recent news found, state: "No news found in the last 90 days from {current_date}. The company may be in a quiet operational phase."
"""

        # 7. HIRING & TECH STACK - Growth signals, tools
        prompts["hiring_tech"] = base_context + f"""
**RESEARCH FOCUS**: Hiring Signals & Technology Stack

Search for hiring activity and technology at "{company_name}":
1. "{company_name}" jobs careers hiring vacatures
2. site:linkedin.com/jobs "{company_name}"
3. "{company_name}" job openings
4. "{company_name}" technology stack tools software
5. "{company_name}" uses Salesforce OR HubSpot OR SAP OR Microsoft
6. "{company_name}" AWS OR Azure OR Google Cloud
7. "{company_name}" digital transformation technology

**REQUIRED OUTPUT FORMAT**:

## Current Job Openings

| Role | Department | Level | Location | Posted | Source URL |
|------|------------|-------|----------|--------|------------|
| [Title] | [Dept] | Jr/Sr/Director/VP | [Location] | [Date] | [URL] |

## Hiring Analysis

| Metric | Observation |
|--------|-------------|
| **Total Open Roles** | [Number found] |
| **Fastest Growing Teams** | [Which departments are scaling] |
| **Senior Hires** | [Executive/leadership searches] |
| **New Capabilities** | [Roles suggesting new directions] |
| **Hiring Velocity** | 🔥 Aggressive / ➡️ Steady / ❄️ Slow / 🛑 Freeze |
| **Remote/Hybrid** | [Patterns observed] |

## Technology Stack

| Category | Known Tools/Vendors | Source |
|----------|---------------------|--------|
| CRM | [Salesforce, HubSpot, Pipedrive, etc.] | |
| Marketing | [Marketo, Mailchimp, etc.] | |
| ERP/Finance | [SAP, Oracle, NetSuite, Exact, etc.] | |
| Cloud Infrastructure | [AWS, Azure, GCP] | |
| Collaboration | [Slack, Teams, Zoom] | |
| HR/People | [Workday, BambooHR, etc.] | |
| Industry-Specific | [Specialized tools] | |

## Growth Signals
- **Scaling Teams**: [Evidence of growth]
- **New Capabilities**: [New roles/tech suggesting new directions]
- **Investment Areas**: [Where they're spending]

{seller_hint}
"""

        # 8. COMPETITIVE LANDSCAPE
        prompts["competition"] = base_context + f"""
**RESEARCH FOCUS**: Competitive Landscape & Market Position

Search for competitive information about "{company_name}":
1. "{company_name}" competitors comparison vs
2. "{company_name}" alternative to
3. "{company_name}" market share position
4. "{company_name}" industry analysis
5. companies like "{company_name}"
6. "{company_name}" vs [competitor names if any found]

**REQUIRED OUTPUT FORMAT**:

## Competitive Landscape

### Direct Competitors

| Competitor | Positioning | How They Compare | Source |
|------------|-------------|------------------|--------|
| [Company 1] | [What they do] | [Strengths/weaknesses vs target] | [URL] |
| [Company 2] | | | |
| [Company 3] | | | |

### Market Position

| Aspect | Assessment |
|--------|------------|
| **Market Role** | 🥇 Leader / 🥈 Challenger / 🥉 Niche Player / 🆕 Newcomer |
| **Market Trajectory** | 📈 Growing / ➡️ Stable / 📉 Declining |
| **Geographic Strength** | [Regions where they're strong] |
| **Vertical Strength** | [Industries where they dominate] |

### Competitive Differentiation
- **Key Differentiators**: [What makes them unique]
- **Competitive Advantages**: [Strengths]
- **Competitive Weaknesses**: [Vulnerabilities]

### Industry Context
[2-3 sentences about the overall industry/market they operate in]
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
        Comprehensive company research using MULTIPLE PARALLEL Gemini calls.
        
        Executes 8 focused research topics in parallel for thorough coverage:
        1. Company Basics
        2. Financials
        3. CEO/Founder
        4. C-Suite Leadership
        5. Senior Leadership
        6. Recent News
        7. Hiring & Tech Stack
        8. Competition
        
        Args:
            company_name: Name of the company
            country: Optional country for better search accuracy
            city: Optional city for better search accuracy
            linkedin_url: Optional LinkedIn URL
            seller_context: Context about what the seller offers
            language: Output language code
            
        Returns:
            Dictionary with comprehensive research data from all topics
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
        
        # Build all search prompts
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

{''.join(combined_data)}

---

## RESEARCH METADATA

| Metric | Value |
|--------|-------|
| Total Topics Searched | {len(prompts)} |
| Successful Searches | {successful_topics} |
| Failed Searches | {len(failed_topics)} |
| Failed Topics | {', '.join(failed_topics) if failed_topics else 'None'} |
| Total Input Tokens | {total_input_tokens} |
| Total Output Tokens | {total_output_tokens} |
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
