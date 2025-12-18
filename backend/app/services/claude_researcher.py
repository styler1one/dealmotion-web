"""
Claude Analysis Service for 360° prospect intelligence reports.

ARCHITECTURE (Cost-Optimized):
- Gemini does ALL web searching (30x cheaper)
- Claude ONLY analyzes the data and generates the report
- No web_search tool = no agentic loop = predictable costs

This approach saves ~85% on research costs:
- Old: Claude web_search ~$0.50-1.00 per research
- New: Claude analysis only ~$0.12-0.15 per research
"""
import os
import logging
from datetime import datetime
from typing import Dict, Any, Optional
from anthropic import AsyncAnthropic
from app.i18n.utils import get_language_instruction
from app.i18n.config import DEFAULT_LANGUAGE

logger = logging.getLogger(__name__)


class ClaudeResearcher:
    """
    Claude-based analysis service for 360° prospect intelligence.
    
    This service ONLY analyzes data - it does NOT perform web searches.
    Web searching is done by Gemini (much cheaper).
    """
    
    def __init__(self):
        """Initialize Claude API."""
        api_key = os.getenv("ANTHROPIC_API_KEY")
        if not api_key:
            raise ValueError("ANTHROPIC_API_KEY environment variable not set")
        
        self.client = AsyncAnthropic(api_key=api_key)
        
        # Cache seller context per organization for efficiency
        self._seller_context_cache: Dict[str, str] = {}
    
    def _build_seller_context_section(self, seller_context: Dict[str, Any]) -> str:
        """
        Build seller context section for analysis.
        
        This helps Claude assess fit and personalize the report.
        """
        if not seller_context or not seller_context.get("has_context"):
            return ""
        
        # Products with benefits
        products_list = seller_context.get("products", [])
        if products_list:
            products_str = ", ".join([
                p.get("name", "") for p in products_list if p.get("name")
            ]) or "not specified"
            all_benefits = []
            for p in products_list[:3]:
                all_benefits.extend(p.get("benefits", [])[:2])
            benefits_str = ", ".join(all_benefits[:5]) if all_benefits else "not specified"
        else:
            products_str = "not specified"
            benefits_str = "not specified"
        
        values = ", ".join(seller_context.get("value_propositions", [])[:3]) or "not specified"
        diffs = ", ".join(seller_context.get("differentiators", [])[:3]) or "not specified"
        
        # ICP details
        industries = ", ".join(seller_context.get("target_industries", [])[:3]) or "any"
        company_sizes = ", ".join(seller_context.get("target_company_sizes", [])[:3]) or "any size"
        pain_points = ", ".join(seller_context.get("ideal_pain_points", [])[:5]) or "not specified"
        decision_makers = ", ".join(seller_context.get("target_decision_makers", [])[:5]) or "not specified"
        
        return f"""
## SELLER CONTEXT

Use this to assess FIT and personalize the analysis.

**Seller**: {seller_context.get('company_name', 'Unknown')}

| What We Sell | Details |
|--------------|---------|
| Products | {products_str} |
| Key Benefits | {benefits_str} |
| Value Props | {values} |
| Differentiators | {diffs} |

| Ideal Customer Profile | Details |
|------------------------|---------|
| Target Industries | {industries} |
| Company Sizes | {company_sizes} |
| Pain Points We Solve | {pain_points} |
| Typical Decision Makers | {decision_makers} |

**YOUR MISSION**:
1. Assess if this prospect FITS our ICP
2. Find evidence of the pain points we solve
3. Identify decision makers matching our typical buyers
4. Suggest use cases based on their situation + our benefits
"""

    async def analyze_research_data(
        self,
        company_name: str,
        gemini_data: str,
        country: Optional[str] = None,
        city: Optional[str] = None,
        kvk_data: Optional[Dict[str, Any]] = None,
        website_data: Optional[Dict[str, Any]] = None,
        kb_chunks: Optional[list] = None,
        seller_context: Optional[Dict[str, Any]] = None,
        language: str = DEFAULT_LANGUAGE
    ) -> Dict[str, Any]:
        """
        Analyze research data and generate 360° prospect intelligence report.
        
        This method does NOT perform web searches. It analyzes data collected
        by Gemini and other sources, then generates the final report.
        
        Args:
            company_name: Name of the company
            gemini_data: Comprehensive research data from Gemini
            country: Optional country
            city: Optional city
            kvk_data: Optional Dutch Chamber of Commerce data
            website_data: Optional scraped website data
            kb_chunks: Optional relevant knowledge base chunks
            seller_context: Context about seller's offering
            language: Output language code
            
        Returns:
            Dictionary with analysis results
        """
        lang_instruction = get_language_instruction(language)
        current_date = datetime.now().strftime("%d %B %Y")
        current_year = datetime.now().year
        
        # Build seller context section
        org_id = seller_context.get("organization_id") if seller_context else None
        if org_id and org_id in self._seller_context_cache:
            seller_section = self._seller_context_cache[org_id]
        else:
            seller_section = self._build_seller_context_section(seller_context)
            if org_id:
                self._seller_context_cache[org_id] = seller_section
        
        # Build supplementary data sections
        supplementary_sections = ""
        
        if kvk_data and kvk_data.get("success"):
            kvk = kvk_data.get("data", {})
            supplementary_sections += f"""

## OFFICIAL REGISTRATION DATA (Dutch Chamber of Commerce)

| Field | Value |
|-------|-------|
| KVK Number | {kvk.get('kvk_number', 'Not found')} |
| Legal Form | {kvk.get('legal_form', 'Not found')} |
| Trade Name | {kvk.get('trade_name', 'Not found')} |
| Address | {kvk.get('address', {}).get('street', '')} {kvk.get('address', {}).get('house_number', '')}, {kvk.get('address', {}).get('postal_code', '')} {kvk.get('address', {}).get('city', '')} |
| Established | {kvk.get('establishment_date', 'Not found')} |
| Employees | {kvk.get('employees', 'Not found')} |
"""
        
        if website_data and website_data.get("success"):
            supplementary_sections += f"""

## COMPANY WEBSITE CONTENT

**URL**: {website_data.get('url', 'Unknown')}
**Pages Scraped**: {website_data.get('pages_scraped', 0)}

{website_data.get('summary', 'No summary available')}
"""
        
        if kb_chunks:
            kb_texts = "\n".join([
                f"- **{chunk.get('source', 'Document')}** (relevance: {chunk.get('score', 0):.0%}): {chunk.get('text', '')[:200]}..."
                for chunk in kb_chunks
            ])
            supplementary_sections += f"""

## RELEVANT KNOWLEDGE BASE DOCUMENTS

{kb_texts}
"""
        
        # Build location context
        location_str = ""
        if city and country:
            location_str = f"**Location**: {city}, {country}"
        elif country:
            location_str = f"**Country**: {country}"
        
        # Build the analysis prompt
        analysis_prompt = f"""You are an elite B2B sales intelligence analyst. Your analysis saves sales professionals DAYS of work.

## CRITICAL CONTEXT

**TODAY'S DATE**: {current_date}
**CURRENT YEAR**: {current_year}
**TARGET COMPANY**: {company_name}
{location_str}

{seller_section}

## RESEARCH DATA TO ANALYZE

The following data was collected via comprehensive web research:

{gemini_data}

{supplementary_sections}

## YOUR TASK

Analyze ALL the research data above and generate a comprehensive 360° PROSPECT INTELLIGENCE REPORT.

{lang_instruction}

## OUTPUT FORMAT REQUIREMENTS

**CRITICAL**: Use standard Markdown headers (# ## ###) - NOT decorative characters.
- Use `#` for main title
- Use `##` for section headers (Section 1, Section 2, etc.)
- Use `###` for subsection headers
- Use tables for structured data
- Use bullet points for lists

Generate the report in this EXACT structure:

# 360° Prospect Intelligence Report: {company_name}

**Research Date**: {current_date}

---

## Section 1: Executive Summary

### 1.1 In One Sentence
[A sharp, insight-packed sentence: WHO they are + WHAT makes them interesting + WHY timing might be right]

### 1.2 At a Glance

| Dimension | Assessment | Evidence |
|-----------|------------|----------|
| **Opportunity Fit** | 🟢 High / 🟡 Medium / 🔴 Low | [One-line reasoning] |
| **Timing Signal** | 🟢 Act Now / 🟡 Nurture / 🔴 Wait | [Trigger or reason] |
| **Company Stage** | 🚀 Startup / 📈 Scale-up / 🏢 SMB / 🏛️ Enterprise | [Evidence] |
| **Financial Health** | 🟢 Strong / 🟡 Stable / 🔴 Challenged / ⚪ Unknown | [Signals] |
| **Industry Match** | 🟢 Core Target / 🟡 Adjacent / 🔴 Outside Focus | [Based on seller context] |
| **Decision Complexity** | Simple / Medium / Complex | [Org size, stakeholders] |
| **Primary Risk** | [Single biggest obstacle] | |

### 1.3 Why This Company Matters
[2-3 sentences connecting their situation to what the seller offers]

### 1.4 ⚡ Quick Actions (Top 3)

Based on the research, these are the 3 most important immediate actions:

| Priority | Action | Why Now | Contact |
|----------|--------|---------|---------|
| 1️⃣ | [Specific action: Call/Email/Connect with X] | [Trigger that creates urgency] | [Name + best contact method] |
| 2️⃣ | [Second priority action] | [Supporting reason] | [Name if applicable] |
| 3️⃣ | [Third priority action] | [Context for action] | [Resource/preparation needed] |

**Recommended Opening**: [One compelling sentence to start the conversation based on their current situation]

---

## Section 2: Company Deep Dive

### 2.1 Company Identity

| Element | Details | Source |
|---------|---------|--------|
| **Legal Name** | [Name] | |
| **Trading Name** | [If different] | |
| **Industry** | [Primary → Sub-sector] | |
| **Founded** | [Year] | |
| **Headquarters** | [City, Country] | |
| **Other Locations** | [List] | |
| **Website** | [URL] | |
| **LinkedIn** | [URL] | |

### 2.2 Corporate Structure

| Element | Details |
|---------|---------|
| **Ownership Type** | [Private / Public / PE / VC / Family] |
| **Parent Company** | [If applicable] |
| **Subsidiaries** | [If any] |
| **Key Investors** | [If known] |

### 2.3 Company Size & Scale

| Metric | Value | Trend | Source |
|--------|-------|-------|--------|
| **Employees** | [Number] | 📈/➡️/📉 | |
| **Revenue** | [Amount or range] | | |
| **Funding Raised** | [Total] | | |

### 2.4 Business Model

**What They Do**: [3-4 sentences explaining core business]

**How They Make Money**:

| Revenue Stream | Description | Importance |
|----------------|-------------|------------|
| [Stream 1] | [Details] | Primary/Secondary |

**Their Customers**:

| Aspect | Details |
|--------|---------|
| **Business Model** | B2B / B2C / B2B2C / SaaS / Services |
| **Customer Segment** | Enterprise / Mid-market / SMB |
| **Key Verticals** | [Industries] |
| **Named Customers** | [If found] |

---

## Section 3: People & Power (Decision Making Unit)

### 3.1 Executive Leadership (C-Suite)

| Name | Title | LinkedIn | Background | Notes |
|------|-------|----------|------------|-------|
| [Name] | CEO/MD | [Full URL] | [Background] | [Founder? New?] |
| [Name] | CFO | [Full URL] | | 💰 Budget authority |
| [Name] | CTO/CIO | [Full URL] | | 🔧 Tech decisions |
| [Name] | COO | [Full URL] | | ⚙️ Operations |
| [Name] | CMO | [Full URL] | | 📣 Marketing |

### 3.2 Senior Leadership (VPs, Directors)

| Name | Title | LinkedIn | Potential Relevance |
|------|-------|----------|---------------------|
| [Name] | [Title] | [URL] | [Why relevant] |

### 3.3 Board of Directors

| Name | Role | Affiliation |
|------|------|-------------|
| [Name] | [Role] | [Company/Fund] |

### 3.4 Decision-Making Dynamics

| Aspect | Assessment | Evidence |
|--------|------------|----------|
| **Decision Culture** | Top-down / Consensus / Founder-led | [Signals] |
| **Budget Authority** | [Who controls spend] | |
| **Likely Champions** | [Roles aligned with seller's value] | |
| **Potential Blockers** | [Roles that might resist] | |

### 3.5 Recent Leadership Changes

| Date | Change | Name | Implication |
|------|--------|------|-------------|
| [Date] | [New/Departure] | [Name] | [What it means] |

**⚠️ Coverage Note**: [State if leadership data is limited]

---

## Section 4: What's Happening Now (Triggers & Signals)

### 4.1 Recent News (Last 90 Days)

| Date | Headline | Type | Source |
|------|----------|------|--------|
| [Date] | [Title](URL) | 💰/📈/👥/🚀/🤝/⚠️ | [Publication] |

**IMPORTANT**: Make headlines clickable links! Format: `[Headline text](https://url)`

**Types**: 💰 Funding | 📈 Growth | 👥 People | 🚀 Product | 🤝 Partnership | ⚠️ Challenge

### 4.2 Funding History

| Date | Round | Amount | Investors |
|------|-------|--------|-----------|
| [Date] | [Series] | [Amount] | [Names] |

### 4.3 Hiring Signals

| Department | Roles | What It Signals |
|------------|-------|-----------------|
| [Dept] | [Count] | [Meaning] |

**Hiring Velocity**: 🔥 Aggressive / ➡️ Steady / ❄️ Slowing / 🛑 Freeze

### 4.4 Strategic Initiatives
- [Initiative 1]
- [Initiative 2]

### 4.5 Interpretation
[2-3 sentences: What's really going on? What are their priorities?]

---

## Section 5: Market & Competitive Position

### 5.1 Market Position

| Aspect | Assessment |
|--------|------------|
| **Market Role** | 🥇 Leader / 🥈 Challenger / 🥉 Niche / 🆕 Newcomer |
| **Trajectory** | 📈 Growing / ➡️ Stable / 📉 Declining |

### 5.2 Competitive Landscape

| Competitor | Positioning | vs. This Company |
|------------|-------------|------------------|
| [Name] | [Position] | [Comparison] |

### 5.3 Technology Stack

| Category | Tools/Vendors |
|----------|---------------|
| CRM | [Tools] |
| ERP | [Tools] |
| Cloud | [AWS/Azure/GCP] |

---

## Section 6: Commercial Opportunity Assessment

### 6.1 BANT Qualification

| Signal | Evidence | Score | Confidence |
|--------|----------|-------|------------|
| **Budget** | [Signals] | 🟢/🟡/🔴/⚪ | High/Med/Low |
| **Authority** | [Decision makers found] | 🟢/🟡/🔴/⚪ | |
| **Need** | [Pain points identified] | 🟢/🟡/🔴/⚪ | |
| **Timeline** | [Urgency signals] | 🟢/🟡/🔴/⚪ | |

**BANT Summary**: [X/4 strong signals] - [Interpretation]

### 6.2 Potential Pain Points

| Pain Point | Evidence | Connection to Seller |
|------------|----------|---------------------|
| [Pain 1] | [Signal] | [How seller helps] |

### 6.3 Opportunity Triggers

| Trigger | Type | Timing |
|---------|------|--------|
| [Trigger] | [Icon] | [Recent/Imminent] |

### 6.4 Relevant Use Cases

| Use Case | Their Situation | How Seller Helps |
|----------|-----------------|------------------|
| [Case 1] | [Context] | [Value] |

---

## Section 7: Strategic Approach

### 7.1 Priority Targets

| Priority | Name | Role | Entry Angle |
|----------|------|------|-------------|
| 1️⃣ | [Name] | [Title] | [Topic to lead with] |
| 2️⃣ | [Name] | [Title] | [Alternative angle] |

### 7.2 Entry Strategy

| Aspect | Recommendation |
|--------|----------------|
| **Primary Entry Point** | [Role/Department] |
| **Why This Entry** | [Reasoning] |
| **Avoid Starting With** | [Who NOT to approach] |

### 7.3 Key Topics to Explore
1. [Topic aligned with trigger/news]
2. [Topic aligned with pain point]
3. [Topic that differentiates seller]

### 7.4 Validation Questions

| Category | Question | Why Ask |
|----------|----------|---------|
| **Situation** | [Question] | [What you're validating] |
| **Problem** | [Question] | |
| **Priority** | [Question] | |

---

## Section 8: Risks, Obstacles & Watchouts

### 8.1 Potential Obstacles

| Obstacle | Likelihood | Mitigation |
|----------|------------|------------|
| [Obstacle] | High/Med/Low | [Strategy] |

### 8.2 Things to Avoid

| Topic/Approach | Why Avoid | Instead Do |
|----------------|-----------|------------|
| [Topic] | [Reason] | [Alternative] |

### 8.3 Information Gaps (Must Verify)
- [ ] [Gap 1]
- [ ] [Gap 2]

---

## Section 9: Research Quality & Metadata

### 9.1 Source Coverage

| Source | Status | Quality |
|--------|--------|---------|
| Company Website | ✅/❌ | Rich/Basic/Poor |
| LinkedIn Company | ✅/❌ | |
| LinkedIn People | ✅/❌ | [X found] |
| Recent News | ✅/❌ | |
| Job Postings | ✅/❌ | |

### 9.2 Research Confidence

| Section | Confidence |
|---------|------------|
| Company Basics | 🟢/🟡/🔴 |
| Leadership Mapping | 🟢/🟡/🔴 |
| Recent Developments | 🟢/🟡/🔴 |
| Commercial Fit | 🟢/🟡/🔴 |

**Overall Confidence**: 🟢 High / 🟡 Medium / 🔴 Low

### 9.3 Key Recommendations
1. **Priority Contact**: [Name] - [LinkedIn URL]
2. **Primary Value Prop**: [What to lead with]
3. **Timing Verdict**: [🟢 Act Now / 🟡 Nurture / 🔴 Wait]
4. **Next Steps**: [Recommended actions]

---

*Report generated: {current_date}*

## QUALITY RULES

1. Include FULL LinkedIn URLs for every person
2. Be factual - "Not found" is better than speculation
3. Use the seller context to assess fit
4. Focus on commercially actionable intelligence
5. Use standard Markdown (# ## ###) - NO decorative characters
"""

        try:
            logger.info(f"Starting Claude analysis for {company_name}")
            
            response = await self.client.messages.create(
                model="claude-sonnet-4-20250514",
                max_tokens=8192,
                temperature=0.2,
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
                f"Claude analysis completed for {company_name}. "
                f"Tokens - Input: {usage.input_tokens}, Output: {usage.output_tokens}"
            )
            
            return {
                "source": "claude_analysis",
                "query": f"{company_name} ({country or 'Unknown'})",
                "data": result_text,
                "success": True,
                "token_stats": {
                    "input_tokens": usage.input_tokens,
                    "output_tokens": usage.output_tokens
                }
            }
            
        except Exception as e:
            logger.error(f"Claude analysis failed for {company_name}: {str(e)}")
            return {
                "source": "claude_analysis",
                "query": f"{company_name} ({country or 'Unknown'})",
                "error": str(e),
                "success": False,
                "token_stats": {}
            }
    
    # Legacy method for backward compatibility
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
        Legacy method - redirects to Gemini-first architecture.
        
        This method is kept for backward compatibility but should not be used
        for new implementations. Use the orchestrator's research_company instead.
        """
        logger.warning(
            f"Legacy search_company called for {company_name}. "
            "This method is deprecated. Use orchestrator.research_company instead."
        )
        
        # Return an error to force migration to new architecture
        return {
            "source": "claude",
            "query": f"{company_name} ({country or 'Unknown'})",
            "data": "",
            "success": False,
            "error": "Legacy method deprecated. Use new Gemini-first architecture.",
            "token_stats": {}
        }
    
    def clear_seller_cache(self, organization_id: Optional[str] = None) -> None:
        """
        Clear cached seller context.
        
        Call this when organization's company profile is updated.
        """
        if organization_id:
            self._seller_context_cache.pop(organization_id, None)
            logger.info(f"Cleared seller context cache for org {organization_id}")
        else:
            self._seller_context_cache.clear()
            logger.info("Cleared all seller context caches")
