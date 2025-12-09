"""
Gemini Google Search integration for research.
Uses the new Google GenAI SDK with Google Search grounding.

Enhanced for:
- Real-time news and developments
- Hiring signals and job postings  
- Market trends and competitive intelligence
- Complementary focus to Claude (news vs. depth)
"""
import os
import logging
from typing import Dict, Any, Optional
from google import genai
from google.genai import types
from app.i18n.utils import get_language_instruction
from app.i18n.config import DEFAULT_LANGUAGE

logger = logging.getLogger(__name__)


class GeminiResearcher:
    """Research using Gemini with Google Search grounding.
    
    Focus: Real-time intelligence - news, hiring, trends, social signals.
    Complementary to Claude which focuses on company structure and depth.
    """
    
    def __init__(self):
        """Initialize Gemini API with new Google GenAI SDK."""
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
        
        Focus areas (complementary to Claude):
        - Recent news and press coverage
        - Hiring signals and job postings
        - Market trends and competitive moves
        - Social signals and sentiment
        
        Args:
            company_name: Name of the company
            country: Optional country for better search accuracy
            city: Optional city for better search accuracy
            linkedin_url: Optional LinkedIn URL
            seller_context: Context about what the user sells
            language: Output language code
            
        Returns:
            Dictionary with research data
        """
        lang_instruction = get_language_instruction(language)
        
        # Build search query with location context
        search_query = self._build_search_query(
            company_name, country, city, linkedin_url
        )
        
        # Build seller context section if available
        seller_section = ""
        products_list = ""
        if seller_context and seller_context.get("has_context"):
            products_list = ", ".join(seller_context.get("products_services", [])[:5]) or "not specified"
            value_props = ", ".join(seller_context.get("value_propositions", [])[:3]) or "not specified"
            
            seller_section = f"""
---
## 🎯 SELLER CONTEXT (Focus your research on relevance to what I sell)

| Aspect | Details |
|--------|---------|
| **My Company** | {seller_context.get('company_name', 'Unknown')} |
| **What I Sell** | {products_list} |
| **Our Value Props** | {value_props} |

**Your mission**: Find NEWS and SIGNALS that indicate {company_name} might need {products_list}.
Look for: pain points, growth challenges, hiring in relevant areas, competitor mentions.
---
"""
        
        # Build prompt for Gemini - focused on NEWS and SIGNALS (complementary to Claude's depth)
        prompt = f"""You are a market intelligence analyst specializing in real-time business signals. {lang_instruction}

Your task: Find CURRENT news, hiring signals, and market intelligence about **{company_name}**.

{search_query}
{seller_section}

## YOUR FOCUS (Different from company profile research!)

You are looking for **TIMING SIGNALS** - information that tells us:
- What's happening RIGHT NOW at this company
- Why NOW might be a good/bad time to reach out
- What challenges or opportunities they're facing

Search Google for:
1. "{company_name}" news (last 90 days)
2. "{company_name}" jobs careers hiring
3. "{company_name}" CEO interview OR announcement
4. "{company_name}" funding investment acquisition
5. "{company_name}" expansion growth OR layoffs restructuring

---

# MARKET INTELLIGENCE: {company_name}

## 1. COMPANY QUICK FACTS

| Fact | Details |
|------|---------|
| **Industry** | [Sector] |
| **Size** | [Employees / Revenue estimate] |
| **HQ** | [Location] |
| **Website** | [URL] |

## 2. NEWS & DEVELOPMENTS (Last 90 Days) ⚠️ CRITICAL SECTION

**Search Google News thoroughly!**

### Recent Headlines
| Date | Headline | Source | URL | Sales Relevance |
|------|----------|--------|-----|-----------------|
| [Date] | [Title] | [Publication] | [URL] | [Why this matters for sales] |

### Categorized Events

**💰 Financial Signals**
- [Funding, revenue news, financial health indicators]

**📈 Growth Signals**
- [Expansion, new markets, scaling initiatives]

**👥 People Signals**
- [Leadership changes, hiring sprees, layoffs, reorgs]

**🚀 Product/Strategy Signals**
- [Launches, pivots, strategic announcements]

**🤝 Partnership Signals**
- [New deals, integrations, vendor selections]

**⚠️ Challenge Signals**
- [Problems, competition issues, market pressures]

### What This Tells Us
[2-3 sentence interpretation: What are they focused on? What pressures do they face? What does this mean for timing?]

## 3. HIRING SIGNALS 🔥 HIGH VALUE

**Search job boards: "{company_name}" careers/jobs**

### Current Job Openings
| Role | Department | Level | What It Signals | Relevance to Us |
|------|------------|-------|-----------------|-----------------|
| [Title] | [Dept] | [Jr/Sr/Dir/VP] | [Strategic meaning] | [Relevant to what we sell?] |

### Hiring Patterns
- **Growing departments**: [Which teams are scaling]
- **New capabilities**: [New roles that signal strategic shifts]
- **Leadership gaps**: [Executive searches underway]

### What Hiring Tells Us
[What do their job postings reveal about priorities and pain points?]

## 4. COMPETITIVE & MARKET CONTEXT

### Industry Pressures
| Pressure | Impact on {company_name} | Opportunity for Us |
|----------|--------------------------|---------------------|
| [Trend/regulation/competitive move] | [How it affects them] | [How we can help] |

### Competitor Mentions
- Who are they compared to in articles?
- Any competitive wins/losses mentioned?
- Market positioning discussions?

## 5. SOCIAL & SENTIMENT SIGNALS

### Online Presence
- **LinkedIn**: Employee count trend, content themes, engagement
- **Glassdoor**: Employee sentiment, growth perception
- **Social Media**: Brand perception, customer feedback

### Sentiment Summary
| Aspect | Signal |
|--------|--------|
| **Employee sentiment** | 🟢 Positive / 🟡 Mixed / 🔴 Negative / ⚪ Unknown |
| **Market perception** | 🟢 Leader / 🟡 Challenger / 🔴 Struggling / ⚪ Unknown |
| **Growth trajectory** | 🟢 Growing / 🟡 Stable / 🔴 Declining / ⚪ Unknown |

## 6. TIMING ASSESSMENT

### Why NOW?
Based on all signals found, assess the timing:

| Factor | Signal | Implication |
|--------|--------|-------------|
| **Urgency** | [News/events creating pressure] | [Why they might need to act] |
| **Budget** | [Funding/growth signals] | [Likely ability to spend] |
| **Change** | [Transitions, new leaders, pivots] | [Windows of opportunity] |
| **Pain** | [Challenges being discussed] | [Problems we can solve] |

### Timing Verdict
| Verdict | Reasoning |
|---------|-----------|
| 🟢 **Reach out NOW** | [Specific trigger or reason] |
| 🟡 **Nurture first** | [What to wait for or prepare] |
| 🔴 **Bad timing** | [Why to wait] |

### Best Opening Angle
Based on the news and signals found:
> "[Specific, timely opener referencing something you found]"

---

**RULES**:
- Focus on RECENT info (last 90 days preferred)
- Include source URLs for ALL news items
- Include publication dates
- If nothing found, say "No recent news found" - don't make things up
- Look for SIGNALS that indicate timing and need, not just facts
- Think like a sales rep: "What would make them want to talk to me NOW?"
"""
        
        try:
            logger.info(f"Starting Gemini research for {company_name} with Google Search grounding")
            
            # Generate response with Google Search grounding using new SDK
            # Use gemini-2.0-flash (stable, free tier available)
            # Use client.aio for async to not block the event loop!
            response = await self.client.aio.models.generate_content(
                model='gemini-2.0-flash',
                contents=prompt,
                config=self.config
            )
            
            logger.info(f"Gemini research completed for {company_name}")
            
            return {
                "source": "gemini",
                "query": search_query,
                "data": response.text,
                "success": True,
                "google_search_used": True
            }
            
        except Exception as e:
            logger.error(f"Gemini research failed for {company_name}: {str(e)}")
            return {
                "source": "gemini",
                "query": search_query,
                "error": str(e),
                "success": False,
                "google_search_used": False
            }
    
    def _build_search_query(
        self,
        company_name: str,
        country: Optional[str],
        city: Optional[str],
        linkedin_url: Optional[str]
    ) -> str:
        """Build search query with location context."""
        query_parts = [f"Company: {company_name}"]
        
        if city and country:
            query_parts.append(f"Location: {city}, {country}")
        elif city:
            query_parts.append(f"City: {city}")
        elif country:
            query_parts.append(f"Country: {country}")
        
        if linkedin_url:
            query_parts.append(f"LinkedIn: {linkedin_url}")
        
        return "\n".join(query_parts)
