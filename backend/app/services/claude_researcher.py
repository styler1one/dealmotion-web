"""
Claude Web Search integration for research.

Enhanced with:
- Proper web search tool integration
- Seller context for personalized research output
- BANT qualification signals
- Actionable recommendations
"""
import os
import logging
from typing import Dict, Any, Optional, List
from anthropic import AsyncAnthropic
from app.i18n.utils import get_language_instruction, get_country_iso_code
from app.i18n.config import DEFAULT_LANGUAGE

logger = logging.getLogger(__name__)


class ClaudeResearcher:
    """Research using Claude with web search capabilities."""
    
    def __init__(self):
        """Initialize Claude API."""
        api_key = os.getenv("ANTHROPIC_API_KEY")
        if not api_key:
            raise ValueError("ANTHROPIC_API_KEY environment variable not set")
        
        self.client = AsyncAnthropic(api_key=api_key)
        
        # Web search tool configuration
        self.web_search_tool = {
            "type": "web_search_20250305",
            "name": "web_search",
            "max_uses": 10,  # Allow multiple searches for comprehensive research
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
        Search for company information using Claude with web search.
        
        Enhanced with:
        - Real web search via Claude's web_search tool
        - Seller context for personalized research
        - BANT qualification signals
        - Actionable recommendations
        
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
        
        # Build search context
        search_context = self._build_search_context(
            company_name, country, city, linkedin_url
        )
        
        # Build user location for localized search results
        # Claude API requires ISO 3166-1 alpha-2 country codes (2 letters)
        user_location = None
        if country:
            country_iso = get_country_iso_code(country)
            if country_iso:
                user_location = {
                    "type": "approximate",
                    "country": country_iso,
                }
                if city:
                    user_location["city"] = city
                logger.debug(f"Using user_location: {user_location}")
            else:
                logger.warning(f"Could not convert country '{country}' to ISO code, skipping user_location")
        
        # Build seller context section if available
        seller_section = ""
        products_list = ""
        value_props = ""
        if seller_context and seller_context.get("has_context"):
            products_list = ", ".join(seller_context.get("products_services", [])[:5]) or "not specified"
            value_props = ", ".join(seller_context.get("value_propositions", [])[:3]) or "not specified"
            target_industries = ", ".join(seller_context.get("target_industries", [])[:3]) or "any"
            
            seller_section = f"""
---
## 🎯 SELLER CONTEXT (Use this to personalize research)

| Aspect | Details |
|--------|---------|
| **My Company** | {seller_context.get('company_name', 'Unknown')} |
| **What I Sell** | {products_list} |
| **Our Value Props** | {value_props} |
| **Target Industries** | {target_industries} |
| **Target Market** | {seller_context.get('target_market', 'B2B')} |

**Your mission**: Find intelligence that helps me sell {products_list} to {company_name}.
Focus on pain points we can solve, decision makers who would care, and timing signals.
---
"""
        
        # Build comprehensive prompt for Claude with web search
        prompt = f"""You are a senior sales intelligence analyst. {lang_instruction}

Your task: Use web search to gather comprehensive, commercially relevant intelligence about **{company_name}**.

{search_context}
{seller_section}

## SEARCH STRATEGY (IMPORTANT!)

**Execute these searches in order:**

1. **Company website**: Search "{company_name} official website about us"
2. **Leadership team**: Search "{company_name} leadership team" AND "{company_name} management team LinkedIn"
3. **LinkedIn company**: Search "site:linkedin.com/company {company_name}"
4. **Recent news**: Search "{company_name} news {country or ''}" (last 90 days)
5. **Funding/growth**: Search "{company_name} funding investment acquisition"
6. **Jobs/hiring**: Search "{company_name} careers jobs hiring"

**For leadership, specifically search:**
- "{company_name} CEO" 
- "{company_name} CFO CTO COO"
- "site:linkedin.com {company_name} CEO"
- "site:linkedin.com {company_name} director"

---

# RESEARCH REPORT: {company_name}

## 1. COMPANY PROFILE

| Element | Details |
|---------|---------|
| **Legal Name** | [Full registered name] |
| **Industry** | [Sector and sub-sector] |
| **Size** | [Employee count, revenue if available] |
| **Headquarters** | [City, Country] |
| **Founded** | [Year] |
| **Website** | [URL] |
| **LinkedIn** | [Company LinkedIn URL] |
| **Registration** | [Chamber of Commerce / Company ID if found] |
| **Ownership** | [Private / Public / PE-backed / Family-owned] |

## 2. BUSINESS MODEL

### What They Do
[2-3 sentences describing core business - be specific, not generic]

### Revenue Model
- **Primary**: [How they mainly make money]
- **Secondary**: [Additional revenue streams]

### Customer Profile
| Aspect | Details |
|--------|---------|
| **Market Type** | B2B / B2C / Both |
| **Customer Size** | Enterprise / Mid-market / SMB |
| **Key Verticals** | [Industries they serve] |
| **Geographic Focus** | [Regions they operate in] |

### Value Proposition
- **Promise**: [What they promise customers]
- **Differentiation**: [How they're different from alternatives]

## 3. LEADERSHIP & DECISION MAKERS ⚠️ CRITICAL

**Search LinkedIn and company website thoroughly for executives!**

### Executive Team
| Name | Title | Background | LinkedIn URL | Relevance to Us |
|------|-------|------------|--------------|-----------------|
| [Name] | CEO | [Background] | [Full LinkedIn URL] | [Why relevant] |
| [Name] | CFO | [Background] | [Full LinkedIn URL] | [Budget holder] |
| [Name] | CTO/CIO | [Background] | [Full LinkedIn URL] | [Tech decisions] |
| [Name] | [VP/Director relevant to what we sell] | [Background] | [Full LinkedIn URL] | [Direct buyer] |

**If leadership not found via search, note**: "Leadership team not found via web search. Recommend manual LinkedIn research."

### Decision-Making Structure
| Aspect | Assessment |
|--------|------------|
| **Decision Style** | Top-down / Consensus / Committee |
| **Buying Authority** | [Which departments have budget] |
| **Likely Stakeholders** | [Who would be involved in a purchase decision] |

## 4. RECENT DEVELOPMENTS (Last 90 Days)

### Trigger Events
| Date | Event | Type | Source URL | Sales Relevance |
|------|-------|------|------------|-----------------|
| [Date] | [What happened] | 💰/📈/👥/🚀/🤝/⚠️ | [URL] | [Why this matters for sales] |

**Event Types**: 💰 Funding | 📈 Growth | 👥 Hiring/Layoffs | 🚀 Product | 🤝 Partnership | ⚠️ Challenge

### Strategic Interpretation
[What do these events tell us about their priorities, challenges, and readiness to buy?]

## 5. COMPETITIVE LANDSCAPE

### Main Competitors
| Competitor | Position | Key Difference | Threat Level |
|------------|----------|----------------|--------------|
| [Competitor] | [Position] | [Difference] | High/Med/Low |

### Technology Stack
- **Known vendors**: [Technologies/tools they use]
- **Potential gaps**: [Areas where they might need solutions]

## 6. QUALIFICATION SIGNALS (BANT)

| Signal | Evidence | Score |
|--------|----------|-------|
| **Budget** | [Funding, growth, investment signals] | 🟢 Strong / 🟡 Possible / 🔴 Weak / ⚪ Unknown |
| **Authority** | [Decision makers identified, org structure clear] | 🟢 Strong / 🟡 Possible / 🔴 Weak / ⚪ Unknown |
| **Need** | [Pain points, challenges, gaps identified] | 🟢 Strong / 🟡 Possible / 🔴 Weak / ⚪ Unknown |
| **Timeline** | [Urgency signals, triggers, planning cycles] | 🟢 Strong / 🟡 Possible / 🔴 Weak / ⚪ Unknown |

**Overall Opportunity Score**: [1-10] - [Brief justification]

## 7. APPROACH RECOMMENDATION

### Entry Strategy
| Aspect | Recommendation |
|--------|----------------|
| **First Contact** | [Name + Role + Why this person] |
| **Entry Angle** | [What pain point or trigger to lead with] |
| **Timing** | 🟢 Reach out now / 🟡 Nurture first / 🔴 Wait for trigger |

### Conversation Starters
Based on research findings, use one of these openers:

1. **Trigger-based**: "[Based on recent news/event]..."
2. **Pain-based**: "[Based on challenge they likely have]..."  
3. **Value-based**: "[Based on what we can offer them]..."

### Things to Avoid
- [What NOT to mention or assume]
- [Sensitive topics based on research]

---

**RULES**:
- Execute multiple web searches to find comprehensive information
- For leadership: Search LinkedIn specifically, include full profile URLs
- Be factual - if not found, say "Not found via web search"
- Include source URLs for all claims
- Focus on what's commercially relevant, not just interesting
- Prioritize recent info (last 90 days) for developments"""

        try:
            # Build web search tool with optional user location
            tools = [self.web_search_tool.copy()]
            if user_location:
                tools[0]["user_location"] = user_location
            
            logger.info(f"Starting Claude research for {company_name} with web search enabled")
            
            # Call Claude with web search tool enabled
            response = await self.client.messages.create(
                model="claude-sonnet-4-20250514",
                max_tokens=8192,  # Increased for comprehensive research
                temperature=0.2,  # Lower for more factual responses
                tools=tools,
                messages=[{
                    "role": "user",
                    "content": prompt
                }]
            )
            
            # Extract text content from response
            result_text = ""
            for block in response.content:
                if hasattr(block, 'text'):
                    result_text += block.text
            
            logger.info(f"Claude research completed for {company_name}, stop_reason: {response.stop_reason}")
            
            return {
                "source": "claude",
                "query": search_context,
                "data": result_text,
                "success": True,
                "web_search_used": True,
                "stop_reason": response.stop_reason
            }
            
        except Exception as e:
            logger.error(f"Claude research failed for {company_name}: {str(e)}")
            return {
                "source": "claude",
                "query": search_context,
                "error": str(e),
                "success": False,
                "web_search_used": False
            }
    
    def _build_search_context(
        self,
        company_name: str,
        country: Optional[str],
        city: Optional[str],
        linkedin_url: Optional[str]
    ) -> str:
        """Build search context with location information."""
        context_parts = [f"Company Name: {company_name}"]
        
        if city and country:
            context_parts.append(f"Location: {city}, {country}")
        elif city:
            context_parts.append(f"City: {city}")
        elif country:
            context_parts.append(f"Country: {country}")
        
        if linkedin_url:
            context_parts.append(f"LinkedIn URL: {linkedin_url}")
        
        return "\n".join(context_parts)
