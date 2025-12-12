"""
Claude Web Search integration for 360° prospect research.

Enhanced with:
- Complete prospect intelligence (leadership, news, competitive, BANT)
- Prompt caching for cost optimization (~10-15% savings)
- Seller context for personalized research output
- Current date awareness for accurate news search
- Structured output template for consistent quality
"""
import os
import logging
from datetime import datetime
from typing import Dict, Any, Optional
from anthropic import AsyncAnthropic
from app.i18n.utils import get_language_instruction, get_country_iso_code
from app.i18n.config import DEFAULT_LANGUAGE

logger = logging.getLogger(__name__)


class ClaudeResearcher:
    """Research using Claude with web search and prompt caching."""
    
    def __init__(self):
        """Initialize Claude API with caching support."""
        api_key = os.getenv("ANTHROPIC_API_KEY")
        if not api_key:
            raise ValueError("ANTHROPIC_API_KEY environment variable not set")
        
        self.client = AsyncAnthropic(api_key=api_key)
        
        # Pre-build static prompt template (cached across all calls)
        self._static_template = self._build_static_template()
        
        # Cache seller context per organization for efficiency
        self._seller_context_cache: Dict[str, str] = {}
    
    def _build_static_template(self) -> str:
        """
        Build the static part of the prompt (cacheable).
        
        This template is ~3,500 tokens and remains constant across all research calls.
        With Anthropic's prompt caching, subsequent calls get 90% discount on these tokens.
        """
        return '''You are an elite B2B sales intelligence analyst. Your research saves sales professionals DAYS of manual work.

═══════════════════════════════════════════════════════════════════════════════
                           SEARCH STRATEGY
═══════════════════════════════════════════════════════════════════════════════

Execute these searches THOROUGHLY. Quality over speed.

**PHASE 1 - Company Foundation:**
□ "[company]" official website
□ "[company]" about us team
□ "site:linkedin.com/company/[company]"
□ "[company]" Wikipedia OR Crunchbase

**PHASE 2 - Financial & Growth Intelligence:**
□ "[company]" revenue OR omzet OR turnover
□ "[company]" funding OR investment OR series
□ "[company]" acquisition OR merger OR acquired
□ "[company]" IPO OR valuation
□ "[company]" employee count OR employees OR FTE

**PHASE 3 - Leadership Deep Mapping (CRITICAL!):**
□ "[company]" CEO founder managing director
□ "[company]" CFO finance director
□ "[company]" CTO CIO technology director
□ "[company]" COO operations director
□ "[company]" CMO marketing director
□ "[company]" CHRO HR director people
□ "[company]" VP vice president
□ "[company]" director head of
□ "site:linkedin.com/in" "[company]" CEO
□ "site:linkedin.com/in" "[company]" director
□ "site:linkedin.com/in" "[company]" VP
□ "[company]" board of directors supervisory
□ "[company]" investor shareholder

**PHASE 4 - What's Happening Now:**
□ "[company]" news (last 3 months)
□ "[company]" press release announcement
□ "[company]" partnership deal signed
□ "[company]" expansion growth new office
□ "[company]" hiring OR jobs OR careers
□ "[company]" layoffs OR restructuring (if any)
□ "[company]" new product launch
□ "[company]" award winner recognition

**PHASE 5 - Market & Competition:**
□ "[company]" competitors comparison vs
□ "[company]" market share position
□ "[company]" industry analysis
□ "[company]" customers clients case study

**PHASE 6 - Technology & Operations:**
□ "[company]" technology stack tools software
□ "[company]" digital transformation
□ "[company]" careers jobs (for tech clues)
□ "[company]" platform system uses

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
| **Registration** | [Chamber of Commerce / Company ID] | |

## 2.2 Corporate Structure

| Element | Details |
|---------|---------|
| **Ownership Type** | Private / Public / PE-backed / VC-backed / Family / Government |
| **Parent Company** | [If subsidiary - who owns them] |
| **Subsidiaries** | [Companies they own] |
| **Key Investors** | [VC/PE firms, notable investors] |
| **Stock Ticker** | [If public] |

## 2.3 Company Size & Scale

| Metric | Current | Trend | Source |
|--------|---------|-------|--------|
| **Employees** | [Number] | 📈 Growing / ➡️ Stable / 📉 Shrinking | [LinkedIn, website, news] |
| **Revenue** | [Amount or range] | [If known] | |
| **Funding Raised** | [Total if known] | [Latest round] | |
| **Valuation** | [If known] | | |
| **Offices/Locations** | [Count] | | |
| **Countries Active** | [List or count] | | |

## 2.4 Business Model

### What They Do
[3-4 sentences explaining their core business. Be specific - what problem do they solve for whom?]

### How They Make Money

| Revenue Stream | Description | Importance |
|----------------|-------------|------------|
| [Stream 1] | [How it works] | Primary / Secondary |
| [Stream 2] | | |
| [Stream 3] | | |

### Their Customers

| Aspect | Details |
|--------|---------|
| **Business Model** | B2B / B2C / B2B2C / Marketplace / SaaS / Services |
| **Customer Segment** | Enterprise / Mid-market / SMB / Consumer |
| **Key Verticals** | [Industries they sell to] |
| **Geographic Focus** | [Where they sell] |
| **Named Customers** | [Logos, testimonials, case studies found] |
| **Customer Count** | [If mentioned anywhere] |

### Their Value Proposition
- **Core Promise**: [What they promise customers]
- **Key Differentiator**: [Why choose them over alternatives]
- **Proof Points**: [Awards, stats, recognition they mention]

## 2.5 Company Culture & Values

| Signal | Observation |
|--------|-------------|
| **Stated Values** | [From website/careers page] |
| **Culture Keywords** | [Innovation, stability, growth, etc.] |
| **Glassdoor Rating** | [If found] |
| **Employee Sentiment** | [Any signals about culture] |
| **Work Model** | Remote / Hybrid / Office-first |
| **Notable Perks** | [If mentioned in job postings] |

## 2.6 Awards & Recognition
- [Award 1 - Year]
- [Award 2 - Year]
- [Industry recognition]


━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
SECTION 3: PEOPLE & POWER (Decision Making Unit) 🔴 CRITICAL
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

## 3.1 Executive Leadership (C-Suite)

| Name | Title | Background | LinkedIn | Tenure | Notes |
|------|-------|------------|----------|--------|-------|
| [Full Name] | CEO / Managing Director / Founder | [Previous roles, education, expertise] | [Full URL] | [Years in role] | [Founder? New hire? Public speaker?] |
| [Full Name] | CFO / Finance Director | [Background] | [URL] | | 💰 Budget authority |
| [Full Name] | CTO / CIO | [Background] | [URL] | | 🔧 Tech decisions |
| [Full Name] | COO / Operations | [Background] | [URL] | | ⚙️ Process owner |
| [Full Name] | CMO / Marketing | [Background] | [URL] | | 📣 Brand/demand |
| [Full Name] | CHRO / People | [Background] | [URL] | | 👥 People decisions |
| [Full Name] | CSO / Sales | [Background] | [URL] | | 🤝 Revenue owner |

## 3.2 Senior Leadership (VPs, Directors, Heads)

| Name | Title | Department | LinkedIn | Potential Relevance |
|------|-------|------------|----------|---------------------|
| [Name] | VP of [X] | [Dept] | [URL] | [Why might they care?] |
| [Name] | Director of [X] | [Dept] | [URL] | |
| [Name] | Head of [X] | [Dept] | [URL] | |

## 3.3 Board of Directors / Supervisory Board

| Name | Role | Affiliation | Background | Influence |
|------|------|-------------|------------|-----------|
| [Name] | Chairman | [Company/Fund] | [Background] | [High/Medium] |
| [Name] | Board Member | | | |
| [Name] | Investor Rep | [VC/PE] | | |

## 3.4 Organization Structure

[If discoverable, sketch the org structure]

## 3.5 Decision-Making Dynamics

| Aspect | Assessment | Evidence |
|--------|------------|----------|
| **Decision Culture** | Top-down / Consensus / Committee / Founder-led | [Signals] |
| **Speed of Decisions** | Fast / Moderate / Slow / Bureaucratic | [Company size, culture] |
| **Budget Authority** | [Who controls spend for solutions like yours] | |
| **Technical Evaluators** | [Who validates solutions technically] | |
| **Likely Champions** | [Roles most aligned with your value] | |
| **Potential Blockers** | [Roles that might resist or slow down] | |

## 3.6 Recent Leadership Changes (Last 12 months)

| Date | Change | Name | From → To | Implication |
|------|--------|------|-----------|-------------|
| [Date] | New Hire / Promotion / Departure | [Name] | [Context] | [What this might mean] |

## 3.7 Leadership Gaps & Observations
- [Open executive searches?]
- [Recently departed roles not yet filled?]
- [Unusual structure observations?]

**⚠️ COVERAGE NOTE**: If leadership information is limited, state clearly: "Limited leadership data available via web search. Recommend LinkedIn Sales Navigator for complete org mapping."


━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
SECTION 4: WHAT'S HAPPENING NOW (Triggers & Signals)
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

## 4.1 Recent News & Announcements (Last 90 Days)

| Date | Headline | Type | Source | URL | Sales Relevance |
|------|----------|------|--------|-----|-----------------|
| [DD MMM YYYY] | [What happened] | 💰/📈/👥/🚀/🤝/⚠️ | [Publication] | [URL] | [Why this matters for outreach] |
| | | | | | |

**Event Types**: 💰 Funding/Financial | 📈 Growth/Expansion | 👥 People/Leadership | 🚀 Product/Launch | 🤝 Partnership/Deal | ⚠️ Challenge/Restructure

## 4.2 Funding & Investment History

| Date | Round | Amount | Lead Investor(s) | What It Signals |
|------|-------|--------|------------------|-----------------|
| [Date] | [Series X / PE / Acquisition] | [Amount] | [Investors] | [Growth mode? Pressure?] |

**Total Raised**: [If known]
**Latest Valuation**: [If known]

## 4.3 Hiring Signals 🔥 HIGH VALUE

### Current Job Openings Analysis

| Department | # of Roles | Levels | What This Signals |
|------------|------------|--------|-------------------|
| [Engineering] | [X] | Jr/Sr/Lead | [Scaling product?] |
| [Sales] | [X] | | [Expansion?] |
| [Marketing] | [X] | | [Brand investment?] |
| [Operations] | [X] | | [Process improvement?] |
| [Finance] | [X] | | [IPO prep? M&A?] |

### Key Hiring Observations
- **Fastest Growing Teams**: [Which departments are scaling]
- **Strategic Hires**: [Executive/leadership searches]
- **New Capabilities**: [Roles that suggest new directions]
- **Hiring Velocity**: [Aggressive / Steady / Slowing / Freezing]

## 4.4 Strategic Initiatives (from job posts, news, website)
- [Initiative 1: e.g., "Digital Transformation Program"]
- [Initiative 2: e.g., "International Expansion to DACH"]
- [Initiative 3: e.g., "New Product Line Launch"]

## 4.5 Acquisitions & Partnerships

| Date | Type | Partner/Target | Details | Relevance |
|------|------|----------------|---------|-----------|
| [Date] | Acquired / Was Acquired / Partnership | [Company] | [Details] | |

## 4.6 Interpretation: What's Really Going On
[3-4 sentences synthesizing the signals: What are their priorities? What pressure are they under? Where are they investing? What's changing?]


━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
SECTION 5: MARKET & COMPETITIVE POSITION
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

## 5.1 Market Position

| Aspect | Assessment |
|--------|------------|
| **Market Role** | 🥇 Leader / 🥈 Strong Challenger / 🥉 Niche Player / 🆕 Newcomer |
| **Market Trajectory** | 📈 Growing / ➡️ Stable / 📉 Declining / 🔄 Pivoting |
| **Geographic Strength** | [Where they're strongest] |
| **Vertical Strength** | [Industries where they dominate] |

## 5.2 Competitive Landscape

| Competitor | Positioning | vs. This Company | Threat Level |
|------------|-------------|------------------|--------------|
| [Competitor 1] | [Their position] | [How they compare] | High/Med/Low |
| [Competitor 2] | | | |
| [Competitor 3] | | | |

## 5.3 Their Differentiation
What makes this company stand out:
1. [Differentiator 1]
2. [Differentiator 2]
3. [Differentiator 3]

## 5.4 Technology Stack & Vendors

| Category | Known Tools/Vendors | Source |
|----------|---------------------|--------|
| CRM | [Salesforce, HubSpot, etc.] | [Job posting, article, etc.] |
| Marketing | [Tools] | |
| ERP/Finance | [SAP, Oracle, etc.] | |
| Cloud/Infra | [AWS, Azure, GCP] | |
| Collaboration | [Slack, Teams, etc.] | |
| Industry-Specific | [Vertical tools] | |
| **Potential Competitors to Seller** | [Existing vendors in seller's space] | |

## 5.5 Similar Companies
Companies with similar profile (for reference, case studies):
- [Similar Company 1] - [Why similar]
- [Similar Company 2] - [Why similar]

## 5.6 Industry Context & External Pressures

| Pressure Type | What's Happening | Impact on This Company |
|---------------|------------------|------------------------|
| **Regulation** | [New laws, compliance requirements] | [How it affects them] |
| **Technology Shift** | [AI, cloud, automation trends] | |
| **Economic** | [Market conditions, sector health] | |
| **Competitive** | [Market consolidation, new entrants] | |
| **Customer** | [Changing buyer expectations] | |


━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
SECTION 6: COMMERCIAL OPPORTUNITY ASSESSMENT
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

## 6.1 BANT Qualification

| Signal | Evidence | Score | Confidence |
|--------|----------|-------|------------|
| **Budget** | [Funding, revenue, growth signals, investment appetite] | 🟢/🟡/🔴/⚪ | High/Med/Low |
| **Authority** | [Decision makers identified, structure understood] | 🟢/🟡/🔴/⚪ | |
| **Need** | [Pain points, challenges, gaps identified] | 🟢/🟡/🔴/⚪ | |
| **Timeline** | [Urgency signals, triggers, planning cycles] | 🟢/🟡/🔴/⚪ | |

**BANT Summary**: [X/4 strong signals] - [One sentence interpretation]

## 6.2 Potential Pain Points (Company-Level)

| Pain Point | Evidence/Signal | Severity | Connection to Seller's Offering |
|------------|-----------------|----------|--------------------------------|
| [Pain 1] | [What suggests this pain exists] | High/Med/Low | [How seller could help] |
| [Pain 2] | | | |
| [Pain 3] | | | |

## 6.3 Opportunity Triggers

| Trigger | Type | Timing | Why It Matters |
|---------|------|--------|----------------|
| [Trigger 1] | 💰/📈/👥/🚀/🤝/⚠️ | [Recent/Imminent/Planned] | [Creates urgency/need for...] |
| [Trigger 2] | | | |

## 6.4 Timing Assessment

| Factor | Analysis |
|--------|----------|
| **Urgency Level** | 🔴 High (act now) / 🟡 Medium (this quarter) / 🟢 Low (nurture) |
| **Urgency Drivers** | [What's creating time pressure] |
| **Budget Cycle Clues** | [Fiscal year, planning cycle, when budgets set] |
| **Window of Opportunity** | [Is there a closing window?] |
| **What Would Accelerate** | [Event or change that would increase urgency] |
| **What Would Delay** | [Potential blockers to timing] |

## 6.5 Relevant Use Cases

Based on their situation, here's how the seller's offering could apply:

| Use Case | Their Situation | How Seller Helps | Priority |
|----------|-----------------|------------------|----------|
| [Use Case 1] | [Specific to their business] | [Specific value] | High/Med/Low |
| [Use Case 2] | | | |
| [Use Case 3] | | | |


━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
SECTION 7: STRATEGIC APPROACH
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

## 7.1 Priority Targets

| Priority | Name | Role | Why Target Them | Entry Angle |
|----------|------|------|-----------------|-------------|
| 1️⃣ | [Name] | [Title] | [Role relevance + signals] | [What topic to lead with] |
| 2️⃣ | [Name] | [Title] | [Why second priority] | |
| 3️⃣ | [Name] | [Title] | [Alternative path] | |

## 7.2 Entry Strategy

| Aspect | Recommendation |
|--------|----------------|
| **Primary Entry Point** | [Department/role to target first] |
| **Why This Entry** | [Strategic reasoning] |
| **Alternative Path** | [If primary blocked] |
| **Avoid Starting With** | [Who NOT to approach first and why] |

## 7.3 Key Topics to Explore
Based on research signals, these topics will resonate:
1. [Topic aligned with recent news/trigger]
2. [Topic aligned with pain point]
3. [Topic aligned with strategic initiative]
4. [Topic that differentiates seller]

## 7.4 Validation Questions
Questions to confirm or explore in first conversation:

| Category | Question | Why Ask This |
|----------|----------|--------------|
| **Situation** | [Question to confirm current state] | [What you're validating] |
| **Problem** | [Question to explore challenges] | |
| **Priority** | [Question about importance/timing] | |
| **Process** | [Question about decision process] | |
| **Success** | [Question about desired outcomes] | |


━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
SECTION 8: RISKS, OBSTACLES & WATCHOUTS
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

## 8.1 Competitive Threats

| Competitor/Vendor | Their Position | Risk Level | How to Handle |
|-------------------|----------------|------------|---------------|
| [Existing vendor in seller's space] | [Incumbent? Recently won?] | High/Med/Low | [Differentiation strategy] |
| [Alternative approach] | | | |

## 8.2 Potential Obstacles

| Obstacle | Likelihood | Impact | Mitigation |
|----------|------------|--------|------------|
| [Budget constraints] | High/Med/Low | | [How to navigate] |
| [Complex decision process] | | | |
| [Competing priorities] | | | |
| [Recent bad experience] | | | |

## 8.3 Things to AVOID ⚠️

| Topic/Approach | Why Avoid | Instead Do |
|----------------|-----------|------------|
| [Sensitive topic 1] | [Reason based on research] | [Better approach] |
| [Sensitive topic 2] | | |
| [Wrong assumption] | | |

## 8.4 Red Flags Detected
- [Any concerning signals from research]
- [Signs of financial distress]
- [Negative news or controversies]
- [High leadership turnover without explanation]

## 8.5 Information Gaps (Must Verify)
Information that could not be confirmed and should be validated:
- [ ] [Gap 1 - e.g., "Current vendor for X"]
- [ ] [Gap 2 - e.g., "Budget cycle timing"]
- [ ] [Gap 3 - e.g., "Decision maker for Y"]
- [ ] [Gap 4 - e.g., "Status of Initiative Z"]


━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
SECTION 9: RESEARCH QUALITY & METADATA
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

## 9.1 Source Coverage

| Source Type | Status | Quality | Notes |
|-------------|--------|---------|-------|
| Company Website | ✅/❌ | Rich/Basic/Poor | |
| LinkedIn Company | ✅/❌ | | |
| LinkedIn People | ✅/❌ | [X people found] | |
| Recent News | ✅/❌ | [X articles, how recent] | |
| Job Postings | ✅/❌ | [X listings analyzed] | |
| Funding Data | ✅/❌ | | |
| Reviews (Glassdoor/G2) | ✅/❌ | | |

## 9.2 Research Confidence

| Section | Confidence | Why |
|---------|------------|-----|
| Company Basics | 🟢/🟡/🔴 | |
| Leadership Mapping | 🟢/🟡/🔴 | |
| Recent Developments | 🟢/🟡/🔴 | |
| Competitive Position | 🟢/🟡/🔴 | |
| Commercial Fit | 🟢/🟡/🔴 | |

**Overall Confidence**: 🟢 High / 🟡 Medium / 🔴 Low

## 9.3 Recommended Follow-Up Research
To complete the picture, consider:
- [ ] [Specific research recommendation 1]
- [ ] [Specific research recommendation 2]


═══════════════════════════════════════════════════════════════════════════════
                              END OF REPORT
═══════════════════════════════════════════════════════════════════════════════


**QUALITY RULES - STRICTLY FOLLOW**:
1. Execute ALL search phases thoroughly - this report should save DAYS of work
2. Include FULL LinkedIn URLs for every person found
3. Be factual - if not found, say "Not found" not invented data
4. Include source URLs for key claims
5. This is RESEARCH, not meeting preparation - no conversation scripts
6. Focus on commercially actionable intelligence
7. When data is limited, be explicit about gaps
8. Quality over completeness - accurate partial data beats speculative full data'''

    def _build_seller_context_section(self, seller_context: Dict[str, Any]) -> str:
        """
        Build seller context section (semi-static, cacheable per organization).
        
        This section changes only when the organization's profile changes,
        so it can be cached per organization_id.
        """
        if not seller_context or not seller_context.get("has_context"):
            return ""
        
        products = ", ".join(seller_context.get("products_services", [])[:5]) or "not specified"
        values = ", ".join(seller_context.get("value_propositions", [])[:3]) or "not specified"
        industries = ", ".join(seller_context.get("target_industries", [])[:3]) or "any"
        diffs = ", ".join(seller_context.get("differentiators", [])[:3]) or "not specified"
        
        return f"""
═══════════════════════════════════════════════════════════════════════════════
                           SELLER CONTEXT
═══════════════════════════════════════════════════════════════════════════════

Use this context to assess commercial relevance and personalize the research.

| Aspect | Details |
|--------|---------|
| **Seller Company** | {seller_context.get('company_name', 'Unknown')} |
| **Products/Services** | {products} |
| **Value Propositions** | {values} |
| **Differentiators** | {diffs} |
| **Target Industries** | {industries} |
| **Target Market** | {seller_context.get('target_market', 'B2B')} |

**Mission**: Build intelligence that helps understand if and how this prospect could benefit from what the seller offers.
"""

    def _build_search_context(
        self,
        company_name: str,
        country: Optional[str],
        city: Optional[str],
        linkedin_url: Optional[str]
    ) -> str:
        """Build search context with location information."""
        context_parts = []
        
        if city and country:
            context_parts.append(f"Location: {city}, {country}")
        elif city:
            context_parts.append(f"City: {city}")
        elif country:
            context_parts.append(f"Country: {country}")
        
        if linkedin_url:
            context_parts.append(f"LinkedIn: {linkedin_url}")
        
        return "\n".join(context_parts) if context_parts else ""

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
        Search for company information using Claude with web search and prompt caching.
        
        Caching strategy:
        - Static template (~3,500 tokens): Cached across ALL calls (90% discount)
        - Seller context (~200 tokens): Cached per organization
        - Dynamic content (~100 tokens): Not cached (company name, date, location)
        
        Args:
            company_name: Name of the company to research
            country: Optional country for better search accuracy
            city: Optional city for better search accuracy
            linkedin_url: Optional LinkedIn company URL
            seller_context: Context about what the seller offers
            language: Output language code (default from config)
            
        Returns:
            Dictionary with research data, success status, and cache statistics
        """
        # Get language instruction and current date
        lang_instruction = get_language_instruction(language)
        current_date = datetime.now().strftime("%d %B %Y")
        current_year = datetime.now().year
        
        # Build search context (dynamic)
        search_context = self._build_search_context(company_name, country, city, linkedin_url)
        
        # Build or retrieve cached seller context
        org_id = seller_context.get("organization_id") if seller_context else None
        if org_id and org_id in self._seller_context_cache:
            seller_section = self._seller_context_cache[org_id]
        else:
            seller_section = self._build_seller_context_section(seller_context)
            if org_id:
                self._seller_context_cache[org_id] = seller_section
        
        # ═══════════════════════════════════════════════════════════════════
        # PROMPT STRUCTURE FOR CACHING
        # ═══════════════════════════════════════════════════════════════════
        
        # PART 1: Cacheable content (static template + seller context + language)
        # This is ~3,700 tokens that get 90% discount after first call
        cacheable_content = f"""{self._static_template}

{seller_section}

{lang_instruction}"""

        # PART 2: Dynamic content (changes every call - ~100 tokens)
        # This is NOT cached - company name, date, location
        dynamic_content = f"""
═══════════════════════════════════════════════════════════════════════════════
                              RESEARCH TARGET
═══════════════════════════════════════════════════════════════════════════════

**TODAY'S DATE**: {current_date}
**CURRENT YEAR**: {current_year}

⚠️ IMPORTANT: All "recent" means relative to TODAY ({current_date}).
⚠️ Search for news from the last 90 days only.
⚠️ Verify dates on all news items - do not report old news as recent.

**TARGET COMPANY**: {company_name}
{search_context}

**Research Timestamp**: {current_date}

Replace [company] in the search strategy with "{company_name}".

Generate the complete 360° prospect intelligence report for {company_name} now:"""

        try:
            # Build web search tool with optional location context
            tools = [{
                "type": "web_search_20250305",
                "name": "web_search",
                "max_uses": 10,  # Allow multiple searches for comprehensive research
            }]
            
            # Add user location for localized search results
            if country:
                country_iso = get_country_iso_code(country)
                if country_iso:
                    user_location = {"type": "approximate", "country": country_iso}
                    if city:
                        user_location["city"] = city
                    tools[0]["user_location"] = user_location
                    logger.debug(f"Using user_location: {user_location}")
            
            logger.info(f"Starting Claude 360° research for {company_name} with caching enabled")
            
            # ═══════════════════════════════════════════════════════════════════
            # API CALL WITH PROMPT CACHING
            # ═══════════════════════════════════════════════════════════════════
            
            response = await self.client.messages.create(
                model="claude-sonnet-4-20250514",
                max_tokens=8192,  # Large output for comprehensive report
                temperature=0.2,  # Lower temperature for factual accuracy
                tools=tools,
                messages=[{
                    "role": "user",
                    "content": [
                        {
                            # CACHED CONTENT (~90% of input tokens)
                            "type": "text",
                            "text": cacheable_content,
                            "cache_control": {"type": "ephemeral"}
                        },
                        {
                            # DYNAMIC CONTENT (~10% of input tokens)
                            "type": "text",
                            "text": dynamic_content
                            # No cache_control = not cached
                        }
                    ]
                }]
            )
            
            # Extract text content from response
            result_text = ""
            for block in response.content:
                if hasattr(block, 'text'):
                    result_text += block.text
            
            # Extract cache statistics for monitoring
            usage = response.usage
            cache_read = getattr(usage, 'cache_read_input_tokens', 0)
            cache_write = getattr(usage, 'cache_creation_input_tokens', 0)
            
            logger.info(
                f"Claude 360° research completed for {company_name}. "
                f"Tokens - Input: {usage.input_tokens}, Output: {usage.output_tokens}. "
                f"Cache - Read: {cache_read}, Write: {cache_write}. "
                f"Stop reason: {response.stop_reason}"
            )
            
            return {
                "source": "claude",
                "query": f"{company_name} ({country or 'Unknown'})",
                "data": result_text,
                "success": True,
                "web_search_used": True,
                "stop_reason": response.stop_reason,
                "cache_stats": {
                    "cache_read_tokens": cache_read,
                    "cache_write_tokens": cache_write,
                    "total_input_tokens": usage.input_tokens,
                    "output_tokens": usage.output_tokens,
                    "cache_hit": cache_read > 0
                }
            }
            
        except Exception as e:
            logger.error(f"Claude 360° research failed for {company_name}: {str(e)}")
            return {
                "source": "claude",
                "query": f"{company_name} ({country or 'Unknown'})",
                "error": str(e),
                "success": False,
                "web_search_used": False,
                "cache_stats": None
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
