"""
Action Generator Service

Generates content for follow-up actions using Claude AI with full context.
"""

import os
import logging
from typing import Tuple, Dict, Any, Optional
from anthropic import AsyncAnthropic  # Use async client!

from app.database import get_supabase_service
from app.models.followup_actions import ActionType
from app.i18n.utils import get_language_instruction

logger = logging.getLogger(__name__)


class ActionGeneratorService:
    """Service for generating follow-up action content using AI"""
    
    def __init__(self):
        # Use AsyncAnthropic to prevent blocking the event loop
        self.client = AsyncAnthropic(api_key=os.getenv("ANTHROPIC_API_KEY"))
        self.model = "claude-sonnet-4-20250514"
    
    async def generate(
        self,
        action_id: str,
        followup_id: str,
        action_type: ActionType,
        user_id: str,
        language: str,
    ) -> Tuple[str, Dict[str, Any]]:
        """
        Generate content for an action.
        
        Returns: (content, metadata)
        """
        # Gather all context
        context = await self._gather_context(followup_id, user_id)
        
        # Get the appropriate prompt
        prompt = self._build_prompt(action_type, context, language)
        
        # Determine max_tokens based on action type
        # Commercial Analysis and Sales Coaching need more tokens due to comprehensive output
        max_tokens_map = {
            ActionType.COMMERCIAL_ANALYSIS: 6000,
            ActionType.SALES_COACHING: 5000,
            ActionType.CUSTOMER_REPORT: 4000,
            ActionType.ACTION_ITEMS: 4000,
            ActionType.INTERNAL_REPORT: 2500,
            ActionType.SHARE_EMAIL: 1500,
        }
        max_tokens = max_tokens_map.get(action_type, 4000)
        
        # Generate content
        content = await self._generate_with_claude(prompt, max_tokens=max_tokens)
        
        # Build metadata
        metadata = self._build_metadata(action_type, content, context)
        
        return content, metadata
    
    async def _gather_context(self, followup_id: str, user_id: str) -> Dict[str, Any]:
        """Gather all relevant context for generation"""
        supabase = get_supabase_service()
        context = {}
        
        try:
            # Get followup data
            followup_result = supabase.table("followups").select("*").eq("id", followup_id).execute()
            if followup_result.data:
                context["followup"] = followup_result.data[0]
            
            # Get organization_id from followup
            org_id = context.get("followup", {}).get("organization_id")
            
            # Get sales profile
            sales_result = supabase.table("sales_profiles").select("*").eq("user_id", user_id).execute()
            if sales_result.data:
                context["sales_profile"] = sales_result.data[0]
            
            # Get company profile
            if org_id:
                company_result = supabase.table("company_profiles").select("*").eq("organization_id", org_id).execute()
                if company_result.data:
                    context["company_profile"] = company_result.data[0]
            
            # Get prospect/company name from followup
            company_name = context.get("followup", {}).get("prospect_company_name")
            
            # Try to find research brief for this company
            if company_name and org_id:
                research_result = supabase.table("research_briefs").select("*").eq("organization_id", org_id).ilike("company_name", company_name).eq("status", "completed").order("created_at", desc=True).limit(1).execute()
                if research_result.data:
                    context["research_brief"] = research_result.data[0]
                    
                    # Get contacts via prospect_id from research_brief
                    prospect_id = research_result.data[0].get("prospect_id")
                    if prospect_id:
                        contacts_result = supabase.table("prospect_contacts").select("*").eq("prospect_id", prospect_id).execute()
                        if contacts_result.data:
                            context["contacts"] = contacts_result.data
            
            # Try to find preparation brief for this company
            if company_name and org_id:
                prep_result = supabase.table("meeting_preps").select("*").eq("organization_id", org_id).ilike("prospect_company_name", company_name).eq("status", "completed").order("created_at", desc=True).limit(1).execute()
                if prep_result.data:
                    context["preparation"] = prep_result.data[0]
            
            # Get deal if linked
            deal_id = context.get("followup", {}).get("deal_id")
            if deal_id:
                deal_result = supabase.table("deals").select("*").eq("id", deal_id).execute()
                if deal_result.data:
                    context["deal"] = deal_result.data[0]
            
        except Exception as e:
            logger.error(f"Error gathering context: {e}")
        
        return context
    
    def _build_prompt(self, action_type: ActionType, context: Dict[str, Any], language: str) -> str:
        """Build the prompt for the specific action type"""
        
        # Get language instruction using the standard i18n utility
        lang_instruction = get_language_instruction(language)
        
        # Build context section
        context_text = self._format_context(context)
        
        # Get action-specific prompt
        if action_type == ActionType.CUSTOMER_REPORT:
            return self._prompt_customer_report(context_text, lang_instruction, context)
        elif action_type == ActionType.SHARE_EMAIL:
            return self._prompt_share_email(context_text, lang_instruction, context)
        elif action_type == ActionType.COMMERCIAL_ANALYSIS:
            return self._prompt_commercial_analysis(context_text, lang_instruction, context)
        elif action_type == ActionType.SALES_COACHING:
            return self._prompt_sales_coaching(context_text, lang_instruction, context)
        elif action_type == ActionType.ACTION_ITEMS:
            return self._prompt_action_items(context_text, lang_instruction, context)
        elif action_type == ActionType.INTERNAL_REPORT:
            return self._prompt_internal_report(context_text, lang_instruction, context)
        else:
            raise ValueError(f"Unknown action type: {action_type}")
    
    def _format_context(self, context: Dict[str, Any]) -> str:
        """Format context into a readable string for the prompt"""
        parts = []
        
        # Followup/Transcript
        followup = context.get("followup", {})
        if followup:
            parts.append(f"""
## Meeting Information
- Company: {followup.get('prospect_company_name', 'Unknown')}
- Date: {followup.get('meeting_date', 'Unknown')}
- Subject: {followup.get('meeting_subject', 'Unknown')}

## Meeting Summary
{followup.get('executive_summary', 'No summary available')}

## Transcript
{followup.get('transcription_text', 'No transcript available')[:8000]}
""")
        
        # Sales Profile
        sales = context.get("sales_profile", {})
        if sales:
            parts.append(f"""
## Sales Representative Profile
- Name: {sales.get('full_name', 'Unknown')}
- Role: {sales.get('role', 'Sales Representative')}
- Experience: {sales.get('experience_years', 'Unknown')} years
- Communication Style: {sales.get('communication_style', 'Professional')}
- Sales Methodology: {sales.get('sales_methodology', 'Consultative')}
""")
        
        # Company Profile
        company = context.get("company_profile", {})
        if company:
            # Extract products from products array
            products_list = []
            for p in (company.get('products', []) or []):
                if isinstance(p, dict) and p.get('name'):
                    products_list.append(p.get('name'))
            products_str = ', '.join(products_list[:5]) or 'Not specified'
            
            # Extract value propositions
            value_props = (company.get('core_value_props', []) or [])[:3]
            value_props_str = ', '.join(value_props) or 'Not specified'
            
            parts.append(f"""
## Company Profile (Seller)
- Company: {company.get('company_name', 'Unknown')}
- Industry: {company.get('industry', 'Unknown')}
- Products/Services: {products_str}
- Value Propositions: {value_props_str}
""")
        
        # Research Brief - include full BANT, leadership, entry strategy
        research = context.get("research_brief", {})
        if research:
            brief = research.get('brief_content', '')
            # Use more of research - critical for understanding prospect
            parts.append(f"""
## Prospect Research (Full)
{brief[:5000] if brief else 'No research available'}
""")
        
        # Contacts - include full profile analysis for each
        contacts = context.get("contacts", [])
        if contacts:
            contact_parts = []
            for c in contacts[:3]:  # Top 3 contacts
                contact_section = f"""### {c.get('name', 'Unknown')}
- **Role**: {c.get('role', 'Unknown role')}
- **Decision Authority**: {c.get('decision_authority', 'Unknown')}
- **Communication Style**: {c.get('communication_style', 'Unknown')}
- **Key Motivations**: {c.get('probable_drivers', 'Unknown')}"""
                
                # Add profile brief if available (truncated but substantial)
                if c.get('profile_brief'):
                    brief = c['profile_brief']
                    if len(brief) > 800:
                        brief = brief[:800] + "..."
                    contact_section += f"\n\n**Profile Analysis**:\n{brief}"
                
                contact_parts.append(contact_section)
            
            parts.append(f"""
## Key Contacts

{chr(10).join(contact_parts)}
""")
        
        # Preparation - include full meeting prep for context
        prep = context.get("preparation", {})
        if prep:
            brief = prep.get('brief_content', 'No preparation notes')
            # Use more of prep - contains talking points, questions, strategy
            parts.append(f"""
## Meeting Preparation Notes
{brief[:4000] if brief else 'No preparation notes'}
""")
        
        # Deal
        deal = context.get("deal", {})
        if deal:
            parts.append(f"""
## Deal Information
- Deal Name: {deal.get('name', 'Unknown')}
- Stage: {deal.get('stage', 'Unknown')}
- Value: {deal.get('value', 'Unknown')}
""")
        
        return "\n".join(parts)
    
    def _prompt_customer_report(self, context_text: str, lang_instruction: str, context: Dict) -> str:
        """Prompt for customer report generation - CUSTOMER-FACING, uses style rules"""
        company_name = context.get("followup", {}).get("prospect_company_name", "the company")
        meeting_date = context.get("followup", {}).get("meeting_date", "Unknown date")
        meeting_subject = context.get("followup", {}).get("meeting_subject", "Meeting")
        
        # Get sales rep info
        sales_profile = context.get("sales_profile", {})
        sales_name = sales_profile.get("full_name", "Sales Representative")
        # Note: email/phone are not in sales_profiles, would need to come from users table
        sales_email = ""  # Not available in sales_profiles
        sales_phone = ""  # Not available in sales_profiles
        sales_title = sales_profile.get("role", "")
        
        # Get seller company info
        seller_company = context.get("company_profile", {}).get("company_name", "")
        
        # Get attendees from contacts
        contacts = context.get("contacts", [])
        attendee_names = [c.get("name", "") for c in contacts if c.get("name")]
        
        # Get style rules for customer-facing output
        style_guide = sales_profile.get("style_guide", {})
        style_rules = self._format_style_rules(style_guide) if style_guide else ""
        
        return f"""You are creating a customer-facing meeting report.
{style_rules}

{lang_instruction}

Write in clear, strategic and warm language.
Use a diplomatic and psychologically sharp tone.
Always write from the customer's perspective.
Never use salesy language.
Never emphasize what the seller did.
Focus on the client's context, goals and momentum.

Purpose: The report must feel as if written by a senior consultant who deeply understands the customer's world and supports them in gaining clarity and moving toward confident decision making.

Length: Adapt the total number of words to the depth and length of the actual conversation (typically 500-800 words for a 30-min meeting, 800-1200 for 60-min).
Style: Flowing prose, no bullet point lists unless explicitly requested.

{context_text}

STRUCTURE & INSTRUCTIONS:

# Customer Report – {company_name}

**Date:** {meeting_date}
**Subject:** {meeting_subject}
**Attendees:** {', '.join(attendee_names) if attendee_names else '[List the attendees from the transcript]'}
**Location:** [Extract from context or write "Virtual meeting" if online]

---

## Introduction
- Begin with a brief, warm and mature reflection on the conversation.
- Acknowledge the customer's current situation and their ambitions.
- Highlight the central thread of the discussion in a way that keeps their perspective at the center.

## Where the Organisation Stands Now
- Describe the customer's context, challenges and priorities as they expressed them.
- Keep it factual, empathetic and without judgement.
- Subtly connect their current situation to what is strategically important for them going forward.

## What We Discussed
- Capture the essence of the meeting in logically structured themes.
- For each theme, articulate what it means for the customer.
- Use compact paragraphs. Avoid long enumerations.
- Include only information that genuinely helps the customer make progress.

## Implications for the Customer
- Explain what the discussed themes imply for their direction, choices or risks.
- Highlight opportunities, dependencies and considerations.
- Keep the tone advisory rather than directive. Diplomatic yet sharp.

## Agreements and Next Steps

Use this exact table format:

| Action | Owner | Timeline | Relevance for the Customer |
|--------|-------|----------|----------------------------|
| [action] | [owner] | [when] | [why this matters to them] |

## Forward View
- Outline a possible path forward that logically builds on the customer's own goals.
- Avoid pushiness. Be guiding, professional and constructive.
- End with an inviting, open sentence that reinforces trust and partnership.

---

**Report prepared by:**
{sales_name}{f', {sales_title}' if sales_title else ''}
{seller_company}
{f'Email: {sales_email}' if sales_email else ''}
{f'Phone: {sales_phone}' if sales_phone else ''}

**Report date:** [Today's date]

---

GENERAL RULES:
- Always prioritise clarity over completeness.
- Avoid internal jargon, technical noise or sales-heavy framing.
- Maintain a confident, empathetic senior-consultant tone.
- Position next steps as measures that strengthen the customer's progress, not your pipeline.
- Reference specific moments or quotes from the conversation to show genuine understanding.

Generate the complete Customer Report now:"""
    
    def _prompt_share_email(self, context_text: str, lang_instruction: str, context: Dict) -> str:
        """Prompt for share email generation - CUSTOMER-FACING, uses style rules"""
        # Get primary contact
        contacts = context.get("contacts", [])
        contact_name = contacts[0].get("name", "there") if contacts else "there"
        
        # Get sales rep info for signature
        sales_profile = context.get("sales_profile", {})
        rep_name = sales_profile.get("full_name", "")
        rep_title = sales_profile.get("role", "")
        # Note: email/phone are not in sales_profiles, would need to come from users table
        rep_email = ""  # Not available in sales_profiles
        rep_phone = ""  # Not available in sales_profiles
        
        # Get company info
        company_profile = context.get("company_profile", {})
        company_name = company_profile.get("company_name", "")
        
        # Get prospect company
        followup = context.get("followup", {})
        prospect_company = followup.get("prospect_company_name", "your organisation")
        
        # Build signature (only include non-empty fields)
        signature_parts = []
        if rep_name:
            signature_parts.append(rep_name)
        if rep_title:
            signature_parts.append(rep_title)
        if company_name:
            signature_parts.append(company_name)
        if rep_email:
            signature_parts.append(rep_email)
        if rep_phone:
            signature_parts.append(rep_phone)
        signature = "\n".join(signature_parts) if signature_parts else "[Your signature]"
        
        # Get style rules for customer-facing output
        style_guide = sales_profile.get("style_guide", {})
        style_rules = self._format_style_rules(style_guide) if style_guide else ""
        
        # Get specific style preferences for email
        email_signoff = style_guide.get("signoff", "Best regards") if style_guide else "Best regards"
        uses_emoji = style_guide.get("emoji_usage", False) if style_guide else False
        
        return f"""You are writing a short follow-up email to share a meeting summary with a customer.
{style_rules}

Write as if you are the salesperson who just had the conversation.
Write in clear, warm and professional language.
Use a human, personal tone. Never sound templated, robotic or salesy.
Always write from the customer's perspective and focus on what is relevant for them.

{lang_instruction}

{context_text}

PURPOSE:
Send the customer a thoughtful follow-up email together with the meeting summary (Customer Report).
Reinforce the connection built in the conversation.
Subtly echo the value discussed without pushing.
Confirm next steps in a natural and low-pressure way.

LENGTH:
Keep the email concise and scannable.
Adapt the length to the conversation:
- Simple meeting with one clear next step → ~80-100 words
- Multiple topics discussed → ~120-150 words
- Complex next steps or several action items → up to ~180 words

Never exceed 200 words for the email body (excluding signature).
Shorter is almost always better for email.

STRUCTURE & INSTRUCTIONS:

**Subject line**
Create a subject line that:
- Refers to a concrete topic, outcome or theme from the meeting.
- Feels personal, not generic.
- Example patterns:
  - "Our conversation on [topic] at {prospect_company}"
  - "[topic] – as discussed"
  - "{prospect_company} · next steps on [topic]"

**Greeting**
Use: "Hi {contact_name},".

**Opening (1–2 sentences)**
- Do NOT use generic phrases like "I hope this email finds you well" or "Per our conversation".
- Acknowledge the conversation in a way that reflects their situation or focus.
- You may thank them, but keep it natural and specific, not formulaic.
- Reference ONE specific moment, topic or insight from the meeting that mattered to them.

**The summary (1–2 sentences)**
- Mention that you are sharing the meeting summary.
- Frame it as useful for them, for example to align internally or keep an overview of decisions and next steps.
- Example pattern:
  - "I have captured the main points and agreements in a short summary so you can easily share this with your colleagues."

**Value echo (1 sentence, optional)**
- If appropriate, briefly restate one key insight or benefit that connects to their priorities.
- Keep it subtle and customer-centric, not feature-driven.

**Next steps (1–2 sentences)**
- Confirm the agreed next step clearly and concretely.
- If there is a follow-up meeting, mention date and time if known.
- If there are action items, refer to them briefly.
- Use a soft call to action, such as:
  - asking for confirmation
  - inviting questions or additions
  - checking if the proposed next step still fits.

**Closing**
- End with a warm, genuine closing that fits a senior, professional tone.
- Avoid overly formal or stiff wording.
- Example patterns:
  - "Looking forward to hearing your thoughts."
  - "Happy to adjust if something has shifted on your side."

**Signature**
Use exactly this signature:

{signature}

RULES:
- Sound human, not corporate.
- Reference at least one specific topic or moment from the conversation.
- Avoid hype or salesy phrases like "game-changing", "exciting opportunity" or similar.
- Do not use placeholder brackets like [topic] in the final email.
- The email should make the recipient feel understood and supported in moving forward.

Generate the complete email now:"""
    
    def _prompt_commercial_analysis(self, context_text: str, lang_instruction: str, context: Dict) -> str:
        """Prompt for commercial analysis generation - INTERNAL, professional/objective style"""
        company_name = context.get("followup", {}).get("prospect_company_name", "the company")
        
        # Get deal info if available
        deal = context.get("deal", {})
        deal_value = deal.get("value", "Unknown")
        current_stage = deal.get("stage", "Unknown")
        
        return f"""You are a seasoned commercial strategist analyzing a sales conversation using enterprise-grade qualification frameworks.

Write in clear, direct and strategic language.
Be brutally honest, pragmatic and psychologically sharp.
Your analysis is for internal use only.
It should reveal what is REALLY going on in this deal.
Not the optimistic version, but the evidence-based truth.

{lang_instruction}

Purpose: Provide actionable commercial intelligence that clarifies the true state of this opportunity, the political dynamics inside the customer organisation, and what the sales team must do next to win.

Every insight must be supported by concrete evidence from the conversation.
Distinguish clearly between FACTS (what was said), INFERENCES (what we deduce), and UNKNOWNS (gaps to fill).

{context_text}

STRUCTURE & INSTRUCTIONS:

# Commercial Analysis – {company_name}

---

## ⚡ Executive Summary

In exactly 3 sentences:
1. The real situation (viable / fragile / misaligned)
2. The single factor that will determine if this deal moves forward or stalls
3. The recommended strategic posture (push / nurture / requalify / deprioritise)

---

## 📊 Deal Snapshot

| Metric | Value | Assessment |
|--------|-------|------------|
| **Deal Value** | {deal_value} | [Is this validated or assumed?] |
| **Current Stage** | {current_stage} | [Is this accurate based on evidence?] |
| **Momentum** | 🟢 Forward / 🟡 Stalled / 🔴 Regressive | [One-line evidence] |
| **Win Probability** | X% | [Confidence: High/Med/Low] |
| **Forecast Category** | Commit / Best Case / Pipeline / Omit | [Based on evidence] |
| **Recommended Stage** | [CRM stage that matches reality] | [Why] |

---

## 🎯 MEDDIC Qualification

Analyse each element. For each: Evidence → Assessment → Gap to Fill.

### M — Metrics
What quantifiable outcomes does the customer expect?

| Aspect | Details |
|--------|---------|
| **Stated Success Metrics** | [What numbers did they mention? ROI, time saved, revenue, etc.] |
| **Evidence** | "[Exact quote if available]" |
| **Assessment** | 🟢 Quantified / 🟡 Vague / 🔴 Unknown |
| **Gap** | [What metrics do we need to establish?] |

### E — Economic Buyer
Who has the final budget authority?

| Aspect | Details |
|--------|---------|
| **Identified** | [Name + Role] or "Not yet identified" |
| **Access Level** | 🟢 Direct / 🟡 Indirect / 🔴 None |
| **Evidence** | [How do we know this person decides?] |
| **Gap** | [Do we need to reach higher?] |

### D — Decision Criteria
What criteria will they use to choose?

| Criterion | Priority | Our Fit | Evidence |
|-----------|----------|---------|----------|
| [Criterion 1] | Must-have / Nice-to-have | 🟢/🟡/🔴 | "[quote]" |
| [Criterion 2] | Must-have / Nice-to-have | 🟢/🟡/🔴 | "[quote]" |

**Assessment**: 🟢 We match all must-haves / 🟡 Gaps exist / 🔴 Critical misalignment

### D — Decision Process
How will they make this decision?

| Aspect | Details |
|--------|---------|
| **Process Steps** | [What steps from interest to signature?] |
| **Who's Involved** | [Names/roles in the buying committee] |
| **Timeline** | [Stated or inferred decision date] |
| **Evidence** | "[Quote about their process]" |
| **Assessment** | 🟢 Clear / 🟡 Vague / 🔴 Unknown |

### I — Identified Pain
What pain is driving this initiative?

| Aspect | Details |
|--------|---------|
| **Stated Pain** | "[Verbatim customer statement]" |
| **Business Impact** | [Quantified if possible: €, time, risk] |
| **Emotional Impact** | [Fear, frustration, career risk, excitement?] |
| **Urgency** | 🔴 Burning / 🟡 Important / 🟢 Nice-to-solve |
| **Cost of Inaction** | [What happens if they do nothing?] |

### C — Champion
Who is actively selling for us internally?

| Aspect | Details |
|--------|---------|
| **Champion Identified** | [Name + Role] or "No clear champion yet" |
| **Champion Strength** | 🟢 Strong (influence + motivation) / 🟡 Moderate / 🔴 Weak or None |
| **Evidence of Advocacy** | [What have they done to advance the deal?] |
| **What They Need** | [How can we arm them for internal conversations?] |
| **Risk if Champion Leaves** | [Single point of failure?] |

**MEDDIC Score**: X/6 elements confirmed

---

## 🏆 Champion Deep Dive

This section determines 80% of deal outcomes.

### Champion Profile
| Aspect | Assessment |
|--------|------------|
| **Name** | [Name] |
| **Role** | [Title] |
| **Influence Level** | High / Medium / Low |
| **Personal Win** | [What do THEY gain if this succeeds?] |
| **Personal Risk** | [What do THEY lose if this fails?] |
| **Trust in Us** | 🟢 High / 🟡 Developing / 🔴 Uncertain |

### Champion Test
Answer these honestly:
- [ ] Would they return our call on a weekend? 
- [ ] Have they shared internal information with us?
- [ ] Have they introduced us to other stakeholders?
- [ ] Have they coached us on how to win?
- [ ] Would they fight for us if challenged?

**Champion Verdict**: Real Champion / Potential Champion / Friendly Contact Only / No Champion

### If No Champion
**Action Required**: [Specific steps to develop or identify a champion]

---

## 🧵 Multi-Threading Status

Single-threaded deals are 40% less likely to close.

| Contact | Role | Engagement | Relationship Depth | Last Contact |
|---------|------|------------|-------------------|--------------|
| [Name 1] | [Role] | 🟢 Active / 🟡 Passive / 🔴 Cold | Strong / Developing / New | [Date] |
| [Name 2] | [Role] | 🟢/🟡/🔴 | [Depth] | [Date] |

**Multi-threading Score**: X contacts engaged
**Risk Assessment**: 🟢 Well-threaded / 🟡 Limited / 🔴 Single-threaded (HIGH RISK)

### Threading Action
[What relationships do we need to develop?]

---

## 📋 Path to Close (Paper Process)

What must happen between "yes" and signature?

| Step | Owner | Status | Estimated Time | Blocker Risk |
|------|-------|--------|----------------|--------------|
| Verbal Agreement | [Prospect name] | ✅ Done / ⏳ Pending | — | — |
| Proposal Review | [Who] | ✅/⏳ | [X days] | [Risk] |
| Legal Review | [Who] | ✅/⏳ | [X days] | [Risk] |
| Procurement | [Who] | ✅/⏳ | [X days] | [Risk] |
| Security Review | [Who] | ✅/⏳ | [X days] | [Risk] |
| Budget Approval | [Who] | ✅/⏳ | [X days] | [Risk] |
| Contract Signature | [Who] | ✅/⏳ | [X days] | [Risk] |

**Path to Close Clarity**: 🟢 Clear / 🟡 Partial / 🔴 Unknown
**Estimated Days to Close**: [X days]
**Biggest Blocker**: [The step most likely to delay or kill the deal]

---

## 💰 BANT Validation (Quick Check)

| Element | Status | One-Line Evidence |
|---------|--------|-------------------|
| **Budget** | 🟢 Confirmed / 🟡 Unclear / 🔴 Concern | [Evidence] |
| **Authority** | 🟢 Full access / 🟡 Partial / 🔴 Missing | [Evidence] |
| **Need** | 🟢 Urgent / 🟡 Important / 🔴 Unclear | [Evidence] |
| **Timeline** | 🟢 Clear / 🟡 Vague / 🔴 None | [Evidence] |

---

## 🎭 Buying Committee Dynamics

### Stakeholder Map

| Person | Role | Stance | Influence | Priority to Engage |
|--------|------|--------|-----------|-------------------|
| [Name] | [Title] | 👍 Champion / 😐 Neutral / 👎 Skeptic / ❓ Unknown | High/Med/Low | 🔴/🟡/🟢 |

### Political Dynamics
- **Power Center**: [Who really decides?]
- **Alliances**: [Who influences whom?]
- **Conflicts**: [Any internal disagreements we can leverage or must navigate?]
- **Blocker Risk**: [Who could kill this deal and why?]

### Alignment Assessment
Are the stakeholders aligned on:
- [ ] The problem to solve?
- [ ] The priority/urgency?
- [ ] The budget?
- [ ] The vendor selection criteria?

**Alignment Score**: 🟢 Aligned / 🟡 Partially Aligned / 🔴 Misaligned (RISK)

---

## 📈 Engagement Score

Objective measurement of prospect activity.

| Signal | Evidence | Score |
|--------|----------|-------|
| Response time to emails | [Fast/Normal/Slow] | +2/+1/0 |
| Meeting attendance | [Always/Sometimes/Cancels] | +2/+1/-1 |
| Questions asked | [Many/Some/Few] | +2/+1/0 |
| Information shared | [Detailed/Basic/Minimal] | +2/+1/0 |
| Internal introductions | [Yes/Promised/No] | +3/+1/0 |
| Proactive outreach | [Yes/No] | +3/0 |

**Engagement Score**: X/14
**Interpretation**: Highly Engaged / Moderately Engaged / Passive / Disengaging

---

## 🎯 Buying Signals & Interest Indicators

List only signals grounded in evidence, not hope.

| Signal Type | Quote / Evidence | Strength |
|-------------|------------------|----------|
| [Verbal commitment] | "[exact quote]" | 🟢 Strong |
| [Process question] | "[quote]" | 🟢/🟡 |
| [Timeline mention] | "[quote]" | 🟢/🟡 |
| [Budget discussion] | "[quote]" | 🟢/🟡/🔴 |

---

## ⚠️ Objections & Concerns

| Concern | Type | Quote / Evidence | Neutralisation Strategy |
|---------|------|------------------|------------------------|
| [Concern 1] | Explicit / Implicit | "[quote]" | [How to address] |
| [Concern 2] | Explicit / Implicit | "[quote]" | [How to address] |

### Unspoken Concerns
[What objections might they have but haven't voiced?]

---

## ⚔️ Competitive Landscape

### Named Competitors
| Competitor | Mentioned By | Their Strength | Our Counter |
|------------|--------------|----------------|-------------|
| [Name] | [Who said it] | [Perceived advantage] | [Our differentiation] |

### The Real Competitor: "Do Nothing"
- **Cost of Inaction**: [What happens if they don't act?]
- **Status Quo Comfort Level**: 🟢 Uncomfortable / 🟡 Tolerable / 🔴 Comfortable (RISK)
- **Burning Platform**: [Is there urgency to change?]

---

## 🚨 Risk Assessment

| Risk | Probability | Impact | Mitigation | Owner |
|------|-------------|--------|------------|-------|
| No clear champion | High/Med/Low | High/Med/Low | [Action] | [Who] |
| Budget not confirmed | High/Med/Low | High/Med/Low | [Action] | [Who] |
| Competitor threat | High/Med/Low | High/Med/Low | [Action] | [Who] |
| Timeline slippage | High/Med/Low | High/Med/Low | [Action] | [Who] |
| Champion departure | High/Med/Low | High/Med/Low | [Action] | [Who] |

**Top Risk**: [The single biggest threat to this deal]

---

## 📊 Deal Health Dashboard

| Dimension | Score | Evidence |
|-----------|-------|----------|
| MEDDIC Complete | /6 | [X of 6 elements confirmed] |
| Champion Strength | /5 | [Reasoning] |
| Multi-threading | /5 | [X contacts, depth assessment] |
| Engagement Level | /5 | [Based on engagement score] |
| Path to Close Clear | /5 | [Process visibility] |
| Competitive Position | /5 | [Our standing] |

**Overall Deal Score**: X/31

| Score Range | Classification | Typical Action |
|-------------|----------------|----------------|
| 25-31 | 🟢 Strong | Push to close |
| 18-24 | 🟡 Moderate | Address gaps urgently |
| 11-17 | 🟠 At Risk | Requalify or escalate |
| 0-10 | 🔴 Critical | Consider deprioritising |

---

## 🎯 Win Probability & Forecast

| Metric | Assessment |
|--------|------------|
| **Win Probability** | X% |
| **Confidence Level** | High / Medium / Low |
| **Forecast Category** | Commit / Best Case / Pipeline / Omit |
| **Recommended CRM Stage** | [Stage name] |
| **Close Date Confidence** | 🟢 Realistic / 🟡 Optimistic / 🔴 Unrealistic |

**Probability Reasoning**:
[2-3 sentences: What drives this probability up or down? What would change it?]

---

## 🎬 THE ONE ACTION

If you do ONLY ONE THING this week, do this:

> **[Specific, concrete action]**
> 
> **Owner**: [Who]
> **Deadline**: [When]
> **Why**: [Direct impact on deal progression]
> **Success Looks Like**: [Observable outcome]

---

## 📋 Recommended Actions

### Immediate (Within 48 Hours)
1. [Most critical action] — [Owner]
2. [Second action] — [Owner]

### Before Next Meeting
1. [Preparation needed]
2. [Information to gather]
3. [Stakeholders to involve]

### Deal Strategy (One Paragraph)
[Concise strategic guidance: Should we push forward, nurture, requalify, escalate internally, or deprioritise? What's the playbook for the next 30 days?]

---

## 📝 Information Gaps

| Area | What We Don't Know | How to Find Out | Priority |
|------|-------------------|-----------------|----------|
| [MEDDIC element] | [The unknown] | [Discovery question/action] | 🔴/🟡/🟢 |

---

RULES:
- Every insight MUST be evidence-based — quote the transcript where possible.
- Clearly distinguish FACTS from INFERENCES from UNKNOWNS.
- Be brutally honest — this is internal, not for the customer.
- Prioritise actionability over completeness.
- The goal is to change behaviour, not just document reality.
- Score conservatively — optimism kills forecasts.
- If evidence is missing, say so explicitly.

Generate the complete Commercial Analysis now:"""
    
    def _prompt_sales_coaching(self, context_text: str, lang_instruction: str, context: Dict) -> str:
        """Prompt for sales coaching generation - INTERNAL, from app/Luna persona"""
        company_name = context.get("followup", {}).get("prospect_company_name", "the company")
        
        # Build sales profile context for personalized coaching
        sales_profile = context.get("sales_profile", {})
        sales_profile_context = self._build_sales_profile_context(sales_profile)
        
        # Get methodology for alignment check
        methodology = sales_profile.get("sales_methodology", "Consultative Selling")
        
        return f"""You are a world-class sales coach providing developmental feedback on a sales conversation.

Write in warm, supportive and psychologically intelligent language.
Be honest but never harsh.
Your tone should combine encouragement with strategic challenge.
Always ground feedback in specific, observable evidence from the conversation.
Your goal is growth, not critique.
Celebrate what works. Illuminate what could be sharper.
Help the salesperson see their own performance clearly and confidently.

{lang_instruction}

Purpose:
Provide actionable, evidence-based coaching that strengthens the salesperson's confidence, precision and deal influence.
Highlight patterns that serve them and patterns that limit them.
Frame every recommendation in a way that feels achievable and motivating.
Connect every insight to commercial outcomes and deal progression.

Consider the salesperson's profile when giving feedback:
{sales_profile_context}

{context_text}

STRUCTURE & INSTRUCTIONS:

# Sales Coaching – {company_name} Meeting

---

## ⚡ Quick Assessment

In one glance, how did this conversation go?

| Metric | Assessment |
|--------|------------|
| **Overall Score** | X/10 |
| **Verdict** | Excellent / Strong / Solid / Needs Work / Concerning |
| **Deal Impact** | 🟢 Advanced / 🟡 Neutral / 🔴 Set Back |
| **Key Strength** | [One thing they did exceptionally well] |
| **Key Growth Area** | [One thing to focus on improving] |

**In one sentence**: [Summarise the dominant performance pattern]

---

## 📊 Performance Scorecard

### Core Sales Skills

| Dimension | Score | Quick Assessment |
|-----------|-------|------------------|
| Rapport Building | /10 | [one line with evidence] |
| Discovery & Questioning | /10 | [one line with evidence] |
| Active Listening | /10 | [one line with evidence] |
| Value Articulation | /10 | [one line with evidence] |
| Objection Handling | /10 | [one line with evidence] |
| Conversation Control | /10 | [one line with evidence] |
| Next Step Commitment | /10 | [one line with evidence] |

### Advanced Metrics

| Dimension | Score | Assessment |
|-----------|-------|------------|
| Emotional Intelligence | /10 | [How well did they read emotional cues?] |
| Trust Building | /10 | [Did they build or erode trust?] |
| Strategic Patience | /10 | [Did they rush or let the prospect lead?] |
| Challenger Moments | /10 | [Did they push back constructively?] |

**Total Score**: X/110 → Elite (90+) / Strong (75-89) / Developing (60-74) / Needs Focus (<60)

---

## 📈 Conversation Analytics

### Talk/Listen Ratio

| Metric | Estimate | Assessment |
|--------|----------|------------|
| **Salesperson Talk Time** | ~X% | [Too much / Just right / Too little] |
| **Prospect Talk Time** | ~X% | [Evidence of engagement] |
| **Ideal for This Meeting Type** | X% / X% | [Discovery: 30/70, Demo: 50/50, Closing: 40/60] |

**Verdict**: 🟢 Balanced / 🟡 Slightly Off / 🔴 Needs Adjustment

**Evidence**: "[Quote showing good/poor balance]"

### Question Quality Analysis

| Question Type | Count | Quality | Examples |
|---------------|-------|---------|----------|
| Open Questions | X | 🟢/🟡/🔴 | "[example]" |
| Closed Questions | X | 🟢/🟡/🔴 | "[example]" |
| Follow-up/Deepening | X | 🟢/🟡/🔴 | "[example]" |
| Clarifying | X | 🟢/🟡/🔴 | "[example]" |
| Leading/Assumptive | X | 🟢/🟡/🔴 | "[example]" |

**Question Quality Score**: X/10
**Best Question Asked**: "[Quote]" — Why it worked: [explanation]
**Missed Question Opportunity**: "[What should have been asked]" — Why: [explanation]

### Discovery Depth

| Level | Achieved? | Evidence |
|-------|-----------|----------|
| **Surface** (What they do) | ✅/❌ | [Evidence] |
| **Situation** (Current state) | ✅/❌ | [Evidence] |
| **Problem** (Pain points) | ✅/❌ | [Evidence] |
| **Implication** (Business impact) | ✅/❌ | [Evidence] |
| **Need-Payoff** (Desired outcome) | ✅/❌ | [Evidence] |
| **Personal Stakes** (Individual motivations) | ✅/❌ | [Evidence] |

**Discovery Depth Score**: X/6 levels reached
**Verdict**: Deep Discovery / Moderate / Surface-Level Only

### Power Balance

| Aspect | Assessment |
|--------|------------|
| **Who controlled the agenda?** | Salesperson / Prospect / Balanced |
| **Who asked more questions?** | Salesperson / Prospect |
| **Confidence level** | Confident / Uncertain / Nervous |
| **Authority positioning** | Peer / Expert / Subordinate |

**Power Dynamics Verdict**: 🟢 Strong Position / 🟡 Equal / 🔴 Prospect Dominated

---

## 🎯 Methodology Alignment: {methodology}

Was this conversation consistent with the {methodology} approach?

| Element | Aligned? | Evidence |
|---------|----------|----------|
| [Key element 1 of methodology] | ✅/❌ | [Quote or observation] |
| [Key element 2 of methodology] | ✅/❌ | [Quote or observation] |
| [Key element 3 of methodology] | ✅/❌ | [Quote or observation] |
| [Key element 4 of methodology] | ✅/❌ | [Quote or observation] |

**Alignment Score**: X/4
**Where You Deviated**: [Specific moments where approach didn't match methodology]
**Recommendation**: [How to stay more aligned next time]

---

## 💼 Deal Impact Analysis

How did this conversation affect the deal?

### What Advanced the Deal
| Moment | What You Did | Impact |
|--------|--------------|--------|
| [Context] | "[Quote or action]" | [How this moved the deal forward] |
| [Context] | "[Quote or action]" | [Impact] |

### What Risked the Deal
| Moment | What Happened | Risk Created | How to Recover |
|--------|---------------|--------------|----------------|
| [Context] | "[Quote or action]" | [Potential damage] | [Recovery action] |

### Net Deal Impact
**Before this meeting**: [Deal status/momentum]
**After this meeting**: [Changed status/momentum]
**Your contribution**: 🟢 Positive / 🟡 Neutral / 🔴 Negative

---

## 🧠 Emotional Intelligence Review

### Moments You Read Well
| Moment | Prospect Signal | Your Response | Impact |
|--------|-----------------|---------------|--------|
| [Context] | [What prospect showed] | [How you responded] | [Positive outcome] |

### Moments You Missed
| Moment | Prospect Signal | What You Did | Better Response |
|--------|-----------------|--------------|-----------------|
| [Context] | [Unspoken cue] | [Your action] | [What would have worked better] |

### Prospect Psychology
| Aspect | Assessment | Evidence |
|--------|------------|----------|
| **Primary Driver** | Fear / Gain / Status / Security | [Quote showing motivation] |
| **Decision Style** | Analytical / Intuitive / Consensus / Directive | [Evidence] |
| **Risk Tolerance** | High / Medium / Low | [Evidence] |
| **Emotional State** | Engaged / Cautious / Skeptical / Enthusiastic | [Evidence] |

**Key Insight**: [One psychological insight that could unlock this deal]

---

## 🤝 Trust Building Analysis

### Trust-Building Moments ✅
| Moment | What You Did | Why It Built Trust |
|--------|--------------|-------------------|
| [Context] | "[Quote]" | [Psychological explanation] |

### Trust-Eroding Moments ⚠️
| Moment | What Happened | Trust Impact | Recovery |
|--------|---------------|--------------|----------|
| [Context] | "[Quote or action]" | [How trust was affected] | [How to rebuild] |

**Net Trust Score**: 🟢 Strengthened / 🟡 Maintained / 🔴 Weakened

---

## 💪 Strengths to Amplify

Identify 2-3 strengths. For each:

### Strength 1: [Name the skill]

| Aspect | Details |
|--------|---------|
| **What you did** | [Describe the behaviour clearly] |
| **The moment** | "[Exact quote]" |
| **Why it worked** | [Impact on prospect's trust, clarity or engagement] |
| **Deal impact** | [How this advanced the deal] |
| **Keep doing this** | [Long-term value of this behaviour] |

### Strength 2: [Name the skill]
[Same structure]

---

## 🎯 Growth Opportunities

Identify 2-3 opportunities for improvement:

### Opportunity 1: [Name the specific skill]

| Aspect | Details |
|--------|---------|
| **The moment** | "[Exact quote or interaction]" |
| **What happened** | [Objective description, no judgement] |
| **Prospect likely felt** | [Emotional/psychological impact] |
| **Better approach** | "[Rewritten version of what to say]" |
| **Guiding principle** | [The underlying skill or mental model] |
| **Commercial impact** | [Why this matters for closing deals] |

### Opportunity 2: [Name the specific skill]
[Same structure]

---

## 🔄 Patterns Observed

### Patterns Serving You Well
| Pattern | Evidence | Commercial Value |
|---------|----------|------------------|
| [Pattern name] | "[Quote or observation]" | [Why this helps close deals] |

### Patterns Holding You Back
| Pattern | Evidence | Impact | Shift Needed |
|---------|----------|--------|--------------|
| [Pattern name] | "[Quote or observation]" | [Negative effect] | [Behavioural change] |

---

## 🚨 Missed Buying Signals

| Moment | What Prospect Said | Hidden Meaning | What You Did | Better Response |
|--------|-------------------|----------------|--------------|-----------------|
| [Context] | "[Quote]" | [The buying signal] | [Your response] | "[What to say instead]" |

---

## 🛡️ Objection Handling Review

For each objection encountered:

### Objection: "[What they said]"

| Aspect | Analysis |
|--------|----------|
| **What they really meant** | [Underlying concern] |
| **Your response** | "[What you said]" |
| **Effectiveness** | 🟢 Handled Well / 🟡 Partially / 🔴 Missed |
| **Better response** | "[Sharper alternative]" |
| **Psychological effect** | [How prospect likely felt after your response] |

---

## 💡 Value Articulation Review

### What Resonated
| Value Statement | Prospect Reaction | Why It Worked |
|-----------------|-------------------|---------------|
| "[What you said]" | [Their response] | [Connection to their priorities] |

### What Fell Flat
| Value Statement | Prospect Reaction | Better Framing |
|-----------------|-------------------|----------------|
| "[What you said]" | [Their response] | "[How to reframe]" |

**Value Articulation Score**: X/10

---

## 🎓 Technique Spotlight

Recommend **one technique** that would have meaningfully elevated this conversation.

| Aspect | Details |
|--------|---------|
| **Technique** | [Name] |
| **What it is** | [Brief explanation] |
| **When to use it** | [Situational trigger] |
| **How it would have helped here** | [Direct connection to this meeting] |
| **Example in action** | "[Specific thing to say or do]" |

---

## 🏋️ Skill Practice Scenario

Here's a specific practice exercise for your next conversation:

**Scenario**: [Realistic situation based on this meeting's gaps]

**Your challenge**: [Specific skill to practice]

**Setup**: [Context for the practice]

**Practice prompt**: 
> The prospect says: "[Realistic prospect statement]"
> Your response should: [Criteria for success]

**Success looks like**: [Observable outcome]

**Try this**: In your next 3 calls, consciously [specific micro-behaviour].

---

## 🎬 THE ONE THING

If you focus on improving just ONE thing before your next sales conversation, make it this:

> **[Specific, concrete focus area]**

| Aspect | Details |
|--------|---------|
| **Why this matters most** | [Direct link to commercial success] |
| **Micro-behaviour to try** | [One small, specific action] |
| **You'll know it's working when** | [Observable signal of improvement] |
| **Impact on your deals** | [Expected outcome] |

---

## 💚 Encouragement

[2-3 sentences of genuine encouragement that:]
- References a real moment from THIS conversation that shows their potential
- Acknowledges their growth trajectory
- Reinforces belief in their capability
- Leaves them feeling motivated and energised, not judged

Remember: [Personalised closing thought based on their profile and this conversation]

---

RULES:
- Be specific. Generic coaching is worthless.
- Quote exact lines from the transcript — specificity builds credibility.
- Keep the balance: roughly 50% affirmation, 50% challenge.
- Describe behaviours, not personality traits.
- Never shame. Always empower.
- Make every recommendation actionable and realistic.
- Connect every insight to commercial outcomes.
- Write as a mentor who genuinely wants this salesperson to succeed.
- If you can't find evidence for something, say so honestly.

Generate the complete Sales Coaching feedback now:"""
    
    def _build_sales_profile_context(self, sales_profile: Dict) -> str:
        """Build context string from sales profile for personalized coaching"""
        if not sales_profile:
            return "No sales profile available - provide general coaching."
        
        parts = []
        
        name = sales_profile.get("full_name")
        if name:
            parts.append(f"- Name: {name}")
        
        experience = sales_profile.get("experience_years")
        if experience:
            parts.append(f"- Experience: {experience} years in sales")
        
        style = sales_profile.get("sales_methodology")
        if style:
            parts.append(f"- Sales methodology: {style}")
        
        comm_style = sales_profile.get("communication_style")
        if comm_style:
            parts.append(f"- Communication style: {comm_style}")
        
        strengths = sales_profile.get("strengths")
        if strengths:
            parts.append(f"- Known strengths: {strengths}")
        
        development = sales_profile.get("development_areas")
        if development:
            parts.append(f"- Development areas: {development}")
        
        if parts:
            return "\n".join(parts)
        else:
            return "Limited profile information - provide balanced coaching."
    
    def _prompt_action_items(self, context_text: str, lang_instruction: str, context: Dict) -> str:
        """Prompt for action items extraction - INTERNAL, standardized task format"""
        company_name = context.get("followup", {}).get("prospect_company_name", "the customer")
        
        return f"""You are extracting action items from a sales conversation.

Write in clear, direct and strategic language.
Be thorough but pragmatic.
Focus on actions that actually move the deal forward.

Your goal is not to document everything but to identify the tasks that influence:
- momentum
- clarity
- stakeholder alignment
- risk reduction
- decision making

Distinguish sharply between:
- **Explicit commitments** – said verbatim
- **Implicit expectations** – not said, but commercially or politically necessary

{lang_instruction}

{context_text}

PURPOSE:
Create a precise, actionable task list that the salesperson can immediately execute.
Every action must be concrete, owned by someone, and tied to a realistic timeframe.
Always explain *why* the action matters when not obvious.

IDENTIFYING ACTION ITEMS:

**Explicit items** – directly stated commitments:
- "I will send you X by Friday."
- "Please share the case study with us."
- "Let's schedule a follow-up next week."

**Implicit items** – required to unlock progress:
- A concern was raised → action to address it.
- A stakeholder was mentioned → action to involve or inform them.
- A gap in clarity emerged → action to resolve it.
- Momentum risk detected → action to stabilise.
- Buying signal surfaced → action to expand on it.
- Objection appeared → action to prepare or counter it for next time.
- Political dynamic inferred → action to secure alignment.

STRUCTURE:

# Action Items – {company_name}

## 🎯 Quick Wins (Do Today or Tomorrow)

| Task | Why It Matters | Time Needed |
|------|----------------|-------------|
[List small, high-impact steps that stabilise momentum or remove friction immediately.
Each task must be specific and start with a verb.]

---

## 📋 Your Tasks (Sales Rep)

| # | Task | Deadline | Priority | Context / Evidence |
|---|------|----------|----------|---------------------|
[Include explicit promises, implicit responsibilities, and proactive actions that change deal trajectory.
Priority scale: 🔴 High (deal-critical), 🟡 Medium (important), 🟢 Low (optional).]

---

## 👤 Customer Tasks

| # | Task | Expected By | Follow-up Strategy | Why It Matters |
|---|------|-------------|-------------------|----------------|
[Tasks the customer committed to or needs to do to move forward.
Include a light-touch, respectful follow-up strategy that fits their communication style.]

---

## 🤝 Shared Tasks / Next Meeting Preparation

| # | Task or Topic | Owner | Target Date | Purpose |
|---|---------------|-------|-------------|---------|
[Items that require coordination, joint preparation, or alignment before the next interaction.]

---

## ⏳ Waiting On / Blockers

| Item | Waiting For | Impact if Delayed | Recommended Nudge Date |
|------|-------------|-------------------|-------------------------|
[Capture anything that could stall or derail momentum.
Be explicit about potential impact and how to gently re-activate stalled items.]

---

## 📊 Summary Metrics

| Metric | Count |
|--------|-------|
| Total action items | X |
| High priority actions | X |
| Quick wins | X |
| Customer-owned items | X |
| Blocked items | X |

**Recommended next touchpoint**: [Suggested date + reason based on momentum]
**Key risk if follow-up slips**: [One sentence explaining what could deteriorate]

---

RULES:
- Every task starts with a verb.
- Every item must be tied to a real piece of evidence from the conversation.
- If something is uncertain, flag it rather than guessing.
- If a section has no items, write "None identified".
- Remove noise. Keep only commercially meaningful actions.
- Prioritise tasks that influence the deal, not administrative housekeeping.
- Maintain a professional, calm and strategic tone.

Generate the complete action item list now:"""
    
    def _prompt_internal_report(self, context_text: str, lang_instruction: str, context: Dict) -> str:
        """Prompt for internal report generation - INTERNAL, CRM-standard format"""
        company_name = context.get("followup", {}).get("prospect_company_name", "the customer")
        deal = context.get("deal", {})
        current_stage = deal.get("stage", "Unknown")
        
        return f"""You are writing an internal sales report for CRM notes and team updates.

Write in clear, factual and highly scannable language.
Assume the reader has 30 seconds and needs to understand what happened, what changed, and what matters next.

Your tone should be concise, commercial and strategically sharp.
Avoid narrative storytelling – prioritise clarity, signals and implications.

{lang_instruction}

{context_text}

PURPOSE:
Create a concise internal update that a sales manager or colleague can absorb quickly.
Highlight the essential developments, commercial relevance, risks, momentum shifts and tactical next steps.
Be honest about uncertainties or gaps in information.

LENGTH GUIDELINE:
- Light check-in → 100–150 words
- Substantive meeting → 150–250 words
- Complex stakeholder discussion → up to 300 words

STRUCTURE:

# Internal Update: {company_name}

**Date**: [meeting date]
**Attendees**: [names and roles if identifiable]
**Meeting Type**: [discovery / demo / negotiation / check-in / multi-stakeholder / etc.]

---

## 📌 TL;DR (One Sentence)
A single sentence capturing the real outcome, momentum and key implication for the deal.

---

## 🎯 Key Takeaways
List 3–5 essential points in order of strategic importance.
Include items such as: new information, validated assumptions, changed priorities, emerging risks, or opportunity expansion.

- [Takeaway 1 – most impactful]
- [Takeaway 2]
- [Takeaway 3]
- [Takeaway 4 if relevant]

---

## 👥 Stakeholder & Political Dynamics
Capture not just roles but **stance, influence and behaviour**.

| Person | Role | Influence Level | Stance | Notes |
|--------|------|-----------------|--------|-------|
[Supportive / Neutral / Resistant; decision-maker / influencer; political relationships if relevant]

---

## 📝 Decisions & Agreements
- [Decision or agreement 1]
- [Decision or agreement 2]
If none: "No formal decisions – exploratory conversation."

---

## ➡️ Required Next Steps

| Action | Owner | Deadline | Commercial Relevance |
|--------|-------|----------|----------------------|
[Link each item to its effect on momentum or risk mitigation.]

---

## 📊 Deal Status & Forecast Implications

| Aspect | Current | Recommended | Rationale |
|--------|---------|-------------|-----------|
| Stage | {current_stage} | [stage if update needed] | [why] |
| Probability | [X]% | [new probability if needed] | [evidence] |
| Timeline | [current expectation] | [updated if discussed] | [reason] |

Include a one-sentence note on whether forecast confidence should increase, remain stable or be reduced.

---

## 🚦 Momentum, Risks & Signals

### Momentum
Classify: 🟢 Forward / 🟡 Neutral-Stalled / 🔴 Backwards
Explain why in one concise sentence.

### Risks
- 🔴 Critical risk: [if any]
- 🟡 Emerging concern: [if relevant]

### Positive Signals
- 🟢 [Concrete evidence-based signal]

If none: "No significant signals."

---

## 💬 Notable Quote (Optional)
> "[A direct quote that captures the customer's intent, concern or direction]"

---

RULES:
- Lead with what matters commercially.
- Keep bullets short and informative.
- Do not speculate without labelling it explicitly.
- Exclude noise, minor admin or irrelevant content.
- Write for a busy reader who needs clarity, not prose.
- Prioritise momentum, risks and decision-driving information.

Generate the complete internal report now:"""
    
    async def _generate_with_claude(self, prompt: str, max_tokens: int = 4000) -> str:
        """Call Claude API to generate content (async to not block event loop)"""
        try:
            # Use await with AsyncAnthropic - this is non-blocking!
            response = await self.client.messages.create(
                model=self.model,
                max_tokens=max_tokens,
                messages=[
                    {"role": "user", "content": prompt}
                ]
            )
            
            return response.content[0].text
            
        except Exception as e:
            logger.error(f"Claude API error: {e}")
            raise
    
    def _build_metadata(self, action_type: ActionType, content: str, context: Dict) -> Dict[str, Any]:
        """Build metadata for the generated action"""
        metadata = {
            "status": "completed",
            "word_count": len(content.split()) if content else 0,
            "generated_with_context": [],
        }
        
        # Track which context was available
        if context.get("sales_profile"):
            metadata["generated_with_context"].append("sales_profile")
        if context.get("company_profile"):
            metadata["generated_with_context"].append("company_profile")
        if context.get("research_brief"):
            metadata["generated_with_context"].append("research_brief")
        if context.get("contacts"):
            metadata["generated_with_context"].append("contacts")
        if context.get("preparation"):
            metadata["generated_with_context"].append("preparation")
        if context.get("deal"):
            metadata["generated_with_context"].append("deal")
        
        # Action-specific metadata
        if action_type == ActionType.COMMERCIAL_ANALYSIS:
            # Try to extract probability from content
            import re
            prob_match = re.search(r'Win Probability[:\s]*(\d+)%', content)
            if prob_match:
                metadata["deal_probability"] = int(prob_match.group(1))
        
        elif action_type == ActionType.SALES_COACHING:
            # Try to extract score
            import re
            score_match = re.search(r'Overall Score[:\s]*(\d+(?:\.\d+)?)/10', content)
            if score_match:
                metadata["overall_score"] = float(score_match.group(1))
        
        return metadata
    
    def _format_style_rules(self, style_guide: Dict[str, Any]) -> str:
        """Format style guide into prompt instructions for output styling."""
        tone = style_guide.get("tone", "professional")
        formality = style_guide.get("formality", "professional")
        emoji = style_guide.get("emoji_usage", False)
        length = style_guide.get("writing_length", "concise")
        signoff = style_guide.get("signoff", "Best regards")
        
        # Tone descriptions
        tone_desc = {
            "direct": "Be straightforward and get to the point quickly",
            "warm": "Be friendly, personable, show genuine interest",
            "formal": "Be professional, structured, use proper titles",
            "casual": "Be relaxed and conversational",
            "professional": "Balance warmth with professionalism"
        }
        
        emoji_instruction = "Emoji are OK to use sparingly" if emoji else "Do NOT use emoji"
        length_instruction = "Keep content concise and scannable" if length == "concise" else "Provide detailed, thorough explanations"
        
        return f"""
## OUTPUT STYLE REQUIREMENTS

**CRITICAL**: Match the sales rep's communication style in ALL output:
- **Tone**: {tone.title()} - {tone_desc.get(tone, tone_desc['professional'])}
- **Formality**: {formality.title()}
- **Emoji**: {emoji_instruction}
- **Length**: {length_instruction}
- **Email Sign-off**: Use "{signoff}" when ending emails

The output MUST sound like the sales rep wrote it themselves - their voice, their style, their personality.
Not generic AI text. Make it personal.
"""


def get_action_generator() -> ActionGeneratorService:
    """Factory function for action generator service"""
    return ActionGeneratorService()

