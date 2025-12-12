"""
Gemini Google Search integration for real-time market intelligence.

Uses the Google GenAI SDK with Google Search grounding.

Focus areas (complementary to Claude's 360° research):
- Real-time news and developments (last 90 days)
- Hiring signals and job market activity
- Market trends and competitive intelligence
- Social signals and sentiment
- Current date awareness for accurate news search

This service provides the "What's Happening Now" layer while Claude
provides the deep structural analysis.
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
    Research using Gemini with Google Search grounding.
    
    Focus: Real-time intelligence - news, hiring, trends, social signals.
    Complementary to Claude which focuses on company structure and depth.
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
            temperature=0.2,  # Lower temperature for factual responses
        )
    
    def _build_search_query(
        self,
        company_name: str,
        country: Optional[str],
        city: Optional[str],
        linkedin_url: Optional[str]
    ) -> str:
        """Build search query with location context."""
        query_parts = []
        
        if city and country:
            query_parts.append(f"Location: {city}, {country}")
        elif city:
            query_parts.append(f"City: {city}")
        elif country:
            query_parts.append(f"Country: {country}")
        
        if linkedin_url:
            query_parts.append(f"LinkedIn: {linkedin_url}")
        
        return "\n".join(query_parts) if query_parts else ""

    def _build_seller_context_section(self, seller_context: Dict[str, Any]) -> str:
        """
        Build seller context section for market intelligence prompt.
        
        OPTIMIZED: Uses ICP pain points to focus signal detection.
        """
        if not seller_context or not seller_context.get("has_context"):
            return ""
        
        # Products
        products_list = seller_context.get("products", [])
        products_str = ", ".join([
            p.get("name", "") for p in products_list if p.get("name")
        ]) if products_list else "not specified"
        
        # ICP pain points for signal matching
        pain_points = seller_context.get("ideal_pain_points", [])
        pain_str = ", ".join(pain_points[:5]) if pain_points else "efficiency, growth, automation"
        
        # Target decision makers
        decision_makers = seller_context.get("target_decision_makers", [])
        dm_str = ", ".join(decision_makers[:3]) if decision_makers else "executives, directors"
        
        return f"""
---
## 🎯 SELLER CONTEXT

**Seller**: {seller_context.get('company_name', 'Unknown')}
**Products**: {products_str}
**Pain Points We Solve**: {pain_str}
**Typical Buyers**: {dm_str}

**Your mission**: Find NEWS and SIGNALS indicating this company experiences these pain points.
Focus on: hiring for {dm_str} roles, news about {pain_str}, strategic shifts.
---
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
        Search for company news and market intelligence using Gemini with Google Search.
        
        Focus areas (complementary to Claude's 360° research):
        - Recent news and press coverage (last 90 days)
        - Hiring signals and job postings
        - Market trends and competitive moves
        - Social signals and sentiment
        - Financial news and funding
        
        Args:
            company_name: Name of the company
            country: Optional country for better search accuracy
            city: Optional city for better search accuracy
            linkedin_url: Optional LinkedIn URL
            seller_context: Context about what the seller offers
            language: Output language code
            
        Returns:
            Dictionary with research data
        """
        lang_instruction = get_language_instruction(language)
        current_date = datetime.now().strftime("%d %B %Y")
        current_year = datetime.now().year
        
        # Build search query with location context
        search_query = self._build_search_query(company_name, country, city, linkedin_url)
        
        # Build seller context section
        seller_section = self._build_seller_context_section(seller_context)
        
        # Build prompt focused on NEWS and SIGNALS (complementary to Claude's depth)
        prompt = f"""You are a market intelligence analyst specializing in real-time business signals.

═══════════════════════════════════════════════════════════════════════════════
                              CRITICAL CONTEXT
═══════════════════════════════════════════════════════════════════════════════

**TODAY'S DATE**: {current_date}
**CURRENT YEAR**: {current_year}

⚠️ IMPORTANT: All "recent" means relative to TODAY ({current_date}).
⚠️ Only report news from the LAST 90 DAYS.
⚠️ Always include the publication date for every news item.
⚠️ If you find news older than 90 days, note it as "older" context.

{lang_instruction}

═══════════════════════════════════════════════════════════════════════════════
                              TARGET COMPANY
═══════════════════════════════════════════════════════════════════════════════

**Company**: {company_name}
{search_query}
{seller_section}

═══════════════════════════════════════════════════════════════════════════════
                           SEARCH STRATEGY
═══════════════════════════════════════════════════════════════════════════════

Your focus is TIMING SIGNALS - information that tells us:
- What's happening RIGHT NOW at this company
- Why NOW might be a good/bad time to reach out
- What challenges or opportunities they're facing

Search Google thoroughly for:
1. "{company_name}" news (last 90 days, filter by date)
2. "{company_name}" press release announcement {current_year}
3. "{company_name}" jobs careers hiring
4. "{company_name}" CEO interview OR announcement
5. "{company_name}" funding investment acquisition {current_year}
6. "{company_name}" expansion growth OR layoffs restructuring
7. "{company_name}" partnership deal
8. "{company_name}" product launch

═══════════════════════════════════════════════════════════════════════════════
                    MARKET INTELLIGENCE REPORT: {company_name}
                    Generated: {current_date}
═══════════════════════════════════════════════════════════════════════════════


## 1. COMPANY QUICK FACTS

| Fact | Details | Source |
|------|---------|--------|
| **Industry** | [Sector] | |
| **Size** | [Employees / Revenue estimate] | |
| **HQ** | [Location] | |
| **Website** | [URL] | |
| **LinkedIn** | [URL if found] | |

---

## 2. NEWS & DEVELOPMENTS (Last 90 Days from {current_date}) 🔴 CRITICAL

### Recent Headlines

| Date | Headline | Source | URL | Sales Relevance |
|------|----------|--------|-----|-----------------|
| [DD MMM YYYY] | [Title] | [Publication] | [URL] | [Why this matters for sales] |
| [DD MMM YYYY] | [Title] | [Publication] | [URL] | |
| [DD MMM YYYY] | [Title] | [Publication] | [URL] | |

### Categorized Signals

**💰 Financial Signals**
- [Funding, revenue news, financial health indicators]
- [Investment announcements, earnings, valuations]

**📈 Growth Signals**
- [Expansion, new markets, scaling initiatives]
- [Office openings, international moves]

**👥 People Signals**
- [Leadership changes, hiring sprees, layoffs, reorgs]
- [New executives, key departures]

**🚀 Product/Strategy Signals**
- [Launches, pivots, strategic announcements]
- [New offerings, discontinued products]

**🤝 Partnership Signals**
- [New deals, integrations, vendor selections]
- [Strategic alliances, channel partnerships]

**⚠️ Challenge Signals**
- [Problems, competition issues, market pressures]
- [Negative news, controversies, setbacks]

### What This Tells Us
[2-3 sentence interpretation: What are they focused on? What pressures do they face? What does this mean for timing?]

---

## 3. HIRING SIGNALS 🔥 HIGH VALUE

### Current Job Openings

| Role | Department | Level | What It Signals | Posted Date |
|------|------------|-------|-----------------|-------------|
| [Title] | [Dept] | [Jr/Sr/Dir/VP] | [Strategic meaning] | [Date if known] |
| [Title] | [Dept] | | | |

### Hiring Patterns Analysis

| Aspect | Observation |
|--------|-------------|
| **Growing Departments** | [Which teams are scaling] |
| **New Capabilities** | [New roles that signal strategic shifts] |
| **Leadership Gaps** | [Executive searches underway] |
| **Hiring Velocity** | Aggressive / Steady / Slowing / Freezing |
| **Remote Hiring** | [Patterns in location requirements] |

### What Hiring Tells Us
[What do their job postings reveal about priorities and pain points?]

---

## 4. COMPETITIVE & MARKET CONTEXT

### Industry Pressures

| Pressure | Impact on {company_name} | Opportunity for Seller |
|----------|--------------------------|------------------------|
| [Trend/regulation/competitive move] | [How it affects them] | [How seller can help] |
| [Market change] | | |

### Competitor Mentions
- Who are they compared to in articles?
- Any competitive wins/losses mentioned?
- Market positioning discussions?

---

## 5. SOCIAL & SENTIMENT SIGNALS

### Online Presence

| Platform | Observation | Sentiment |
|----------|-------------|-----------|
| **LinkedIn** | [Employee count trend, content themes] | 📈/➡️/📉 |
| **Glassdoor** | [Rating, recent reviews] | 🟢/🟡/🔴 |
| **Social Media** | [Brand perception, engagement] | |
| **Review Sites** | [G2, Capterra if B2B software] | |

### Sentiment Summary

| Aspect | Signal |
|--------|--------|
| **Employee Sentiment** | 🟢 Positive / 🟡 Mixed / 🔴 Negative / ⚪ Unknown |
| **Market Perception** | 🟢 Leader / 🟡 Challenger / 🔴 Struggling / ⚪ Unknown |
| **Growth Trajectory** | 🟢 Growing / 🟡 Stable / 🔴 Declining / ⚪ Unknown |
| **Employer Brand** | 🟢 Strong / 🟡 Average / 🔴 Weak / ⚪ Unknown |

---

## 6. TIMING ASSESSMENT

### Why NOW?

Based on all signals found, assess the timing:

| Factor | Signal Found | Implication |
|--------|--------------|-------------|
| **Urgency** | [News/events creating pressure] | [Why they might need to act] |
| **Budget** | [Funding/growth signals] | [Likely ability to spend] |
| **Change** | [Transitions, new leaders, pivots] | [Windows of opportunity] |
| **Pain** | [Challenges being discussed] | [Problems seller can solve] |

### Timing Verdict

| Verdict | Reasoning |
|---------|-----------|
| 🟢 **Reach out NOW** | [Specific trigger or reason] |
| 🟡 **Nurture first** | [What to wait for or prepare] |
| 🔴 **Bad timing** | [Why to wait] |

### Best Opening Angle
Based on the news and signals found:
> "[Specific, timely opener referencing something discovered in research]"

---

## 7. RESEARCH METADATA

| Aspect | Details |
|--------|---------|
| **Report Date** | {current_date} |
| **News Timeframe** | Last 90 days |
| **Sources Searched** | Google News, Company Website, Job Boards, LinkedIn, Social Media |
| **Data Quality** | 🟢 Rich / 🟡 Moderate / 🔴 Limited |

### Information Gaps
- [What couldn't be found that would be valuable]
- [Areas needing manual research]

---

**RULES**:
- Focus on RECENT info (last 90 days from {current_date})
- Include source URLs for ALL news items
- Include publication dates for ALL news
- If nothing recent found, say "No recent news found" - don't invent
- Look for SIGNALS that indicate timing and need, not just facts
- Think like a sales rep: "What would make them want to talk to me NOW?"
"""

        try:
            logger.info(f"Starting Gemini market intelligence for {company_name}")
            
            # Generate response with Google Search grounding
            # Use client.aio for async to not block the event loop
            response = await self.client.aio.models.generate_content(
                model='gemini-2.0-flash',
                contents=prompt,
                config=self.config
            )
            
            logger.info(f"Gemini market intelligence completed for {company_name}")
            
            return {
                "source": "gemini",
                "query": f"{company_name} ({country or 'Unknown'})",
                "data": response.text,
                "success": True,
                "google_search_used": True,
                "research_date": current_date
            }
            
        except Exception as e:
            logger.error(f"Gemini market intelligence failed for {company_name}: {str(e)}")
            return {
                "source": "gemini",
                "query": f"{company_name} ({country or 'Unknown'})",
                "error": str(e),
                "success": False,
                "google_search_used": False
            }
