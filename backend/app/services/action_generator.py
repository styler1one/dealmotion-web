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
        
        # Generate content
        content = await self._generate_with_claude(prompt)
        
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
        
        return f"""You are a seasoned commercial strategist analyzing a sales conversation.

Write in clear, direct and strategic language.
Be honest, pragmatic and psychologically sharp.
Your analysis is for internal use only.
It should reveal what is really going on in this deal.
Not the optimistic version, but the evidence-based one.

{lang_instruction}

Purpose: Provide actionable commercial intelligence that clarifies the true state of this opportunity, the political dynamics inside the customer organisation, and what the sales team should do next.

Every insight must be supported by concrete evidence from the conversation.

{context_text}

STRUCTURE & INSTRUCTIONS:

# Commercial Analysis – {company_name}

## Executive Summary
In 2-3 sentences, summarise the real situation:
Is this opportunity viable, fragile or misaligned?
What single factor will determine whether this deal moves forward or stalls?

## Momentum Assessment
Describe the current momentum of the deal.
Classify as: 🟢 Forward Momentum, 🟡 Neutral / Stalled, 🔴 Regressive.
Explain *why*, using evidence and behavioural signals from the prospect.

---

## BANT Analysis

Analyse each dimension using the structure below. Always separate:
- What the customer *explicitly said*
- What we *infer*
- What is still *unknown*

### Budget
- **Evidence**: [Direct quotes or statements]
- **Assessment**: 🟢 Confirmed / 🟡 Unclear / 🔴 Concern
- **Interpretation**: [What this means for deal viability]
- **Unknowns**: [What remains unverified]

### Authority
- **Decision Makers Identified**: [Names and roles]
- **Decision Process**: [How decisions are made, formal vs informal]
- **Assessment**: 🟢 Full access / 🟡 Partial access / 🔴 Missing key personas
- **Political Dynamics**: [Who influences whom]
- **Gap**: [Who we still need access to]

### Need
- **Stated Needs**: [Verbatim customer statements]
- **Underlying Drivers**: [Motivations, pain, pressure, risk avoidance]
- **Urgency Level**: 🔴 Urgent / 🟡 Important / 🟢 Nice-to-have
- **Strategic Fit**: [How well our solution aligns to their core goals]

### Timeline
- **Stated Timeline**: [Any explicit deadlines]
- **Trigger Events**: [Renewals, compliance deadlines, growth plans]
- **Assessment**: 🟢 Clear / 🟡 Vague / 🔴 No urgency
- **Implications**: [What accelerates or delays this deal]

---

## Buying Signals & Interest Indicators
List only signals grounded in evidence, not hope.

| Signal | Quote / Evidence | Strength |
|--------|------------------|----------|
| [type] | "[exact quote]" | 🟢 / 🟡 / 🔴 |

---

## Objections & Concerns
Identify both explicit and implicit objections.

| Concern | Quote / Evidence | Recommended Approach |
|---------|------------------|----------------------|
| [concern] | "[quote]" | [How to neutralise or reframe] |

---

## Competitive Landscape
- **Competitors Mentioned**: [Names or "None mentioned"]
- **Prospect's Comparison Criteria**: [What matters to them]
- **Our Position**: [Where we stand based on evidence]
- **Differentiation Angle**: [The sharpest lever we can use]

---

## Risk Assessment
Provide a sober view of actual deal risks.

| Risk | Probability | Impact | Mitigation Strategy |
|------|-------------|--------|---------------------|
| [risk] | High/Med/Low | High/Med/Low | [action] |

---

## Deal Health Score
Score each dimension 1-5 based strictly on evidence.

| Dimension | Score | Evidence |
|-----------|-------|----------|
| Need Fit | /5 | [why] |
| Stakeholder Access | /5 | [why] |
| Budget Alignment | /5 | [why] |
| Timeline Clarity | /5 | [why] |
| Competitive Position | /5 | [why] |

**Overall Deal Score**: X/25 → Strong / Moderate / At Risk

---

## Information Gaps
Consolidate all unknowns from the analysis above:

| Area | What We Don't Know | How to Find Out | Priority |
|------|-------------------|-----------------|----------|
| [BANT area] | [the unknown] | [discovery action] | 🔴 / 🟡 / 🟢 |

---

## Win Probability & Strategic Recommendation

- **Win Probability**: X%
- **Confidence Level**: High / Medium / Low
- **Reasoning**: In 2-3 sentences: what drives this probability? What could change it?

### Overall Strategy Guidance
Provide one sharp paragraph:
Should we push forward, nurture, requalify, escalate internally, or deprioritise?
Base this advice strictly on evidence, political dynamics and deal momentum.

---

## Recommended Actions

### Immediate (This Week)
The 1-3 most critical actions that influence deal momentum.

### Before Next Meeting
Information we need, stakeholders to involve, preparation needed.

### Deal Strategy
A concise advisory paragraph outlining the strategic playbook for this opportunity.

---

RULES:
- Every insight must be evidence-based.
- Distinguish facts from interpretation.
- Flag assumptions explicitly.
- Be concise but deep.
- Prioritise clarity over completeness.
- Deliver commercial intelligence that can change action, not just document reality.

Generate the complete Commercial Analysis now:"""
    
    def _prompt_sales_coaching(self, context_text: str, lang_instruction: str, context: Dict) -> str:
        """Prompt for sales coaching generation - INTERNAL, from app/Luna persona"""
        company_name = context.get("followup", {}).get("prospect_company_name", "the company")
        
        # Build sales profile context for personalized coaching
        sales_profile = context.get("sales_profile", {})
        sales_profile_context = self._build_sales_profile_context(sales_profile)
        
        return f"""You are a senior sales mentor providing developmental feedback on a sales conversation.

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

Consider the salesperson's profile when giving feedback:
{sales_profile_context}

{context_text}

STRUCTURE & INSTRUCTIONS:

# Sales Coaching – {company_name} Meeting

## Performance Snapshot

**Overall Score**: X/10

Give a quick, fair overall view of how effectively the salesperson guided the conversation.

| Dimension | Score | Quick Assessment |
|-----------|-------|------------------|
| Rapport Building | /10 | [one line] |
| Discovery & Questioning | /10 | [one line] |
| Active Listening | /10 | [one line] |
| Value Articulation | /10 | [one line] |
| Objection Handling | /10 | [one line] |
| Conversation Control | /10 | [one line] |
| Next Step Commitment | /10 | [one line] |

**In one sentence**: Summarise the dominant performance pattern.

---

## Strengths to Amplify

Identify 2-3 strengths. For each:

- **What you did**: Describe the behaviour clearly.
- **The moment**: Include an exact quote or timestamp.
- **Why it worked**: Explain the impact on the prospect's trust, clarity or engagement.
- **How this supports deal momentum**: Link it to commercial outcomes.
- **Keep doing this because**: Reinforce the long-term value of the behaviour.

---

## Growth Opportunities

Identify 2-3 opportunities for improvement, each structured as follows:

### Opportunity: [Name the specific skill]

- **The moment**: Provide a concrete quote or interaction.
- **What happened**: Objective description, no judgement.
- **Impact on the prospect**: What they likely felt or inferred.
- **Alternative approach**: Offer a rewritten version of what could have been said.
- **Guiding principle**: The underlying skill or mental model to strengthen.
- **Commercial relevance**: Why sharpening this matters for closing future deals.

---

## Patterns Observed

Highlight recurring behavioural tendencies.

### Serving You Well
- [Pattern]: [Evidence + explanation]

### Holding You Back
- [Pattern]: [Evidence + what shifts would improve impact]

---

## Missed Buying Signals or Opportunities

Identify moments the salesperson did not fully leverage.

| Moment | What Was Said | Missed Opportunity | Suggested Question or Move | Why It Matters |
|--------|---------------|--------------------|-----------------------------|----------------|
| [context] | "[quote]" | [what was missed] | "[suggestion]" | [importance] |

---

## Objection Handling Review

If relevant, analyse how objections were handled:

- What the objection really meant
- How the salesperson responded
- A sharper alternative response
- The psychological effect on the prospect

---

## Technique Spotlight

Recommend **one technique** that would have meaningfully elevated the conversation.

**Technique**: [Name]
**What it is**: Brief explanation.
**When to use it**: Situational trigger.
**How it would have helped here**: Directly connect to the meeting.
**Practice exercise**: One realistic exercise the salesperson can repeat.

---

## Your Focus for Next Time

Define the single most impactful improvement area.

**Focus Area**: [One behavioural priority]
**Why it matters**: Clear explanation tied to growth and commercial success.
**Micro-commitment**: One small, specific behaviour to try in the next conversation.

---

## Encouragement

Close with 2-3 sentences of genuine encouragement:
- Reference a real moment that shows potential.
- Reinforce belief in their capability.
- Leave them feeling motivated, not judged.

---

RULES:
- Be specific. Generic coaching is not helpful.
- Quote exact lines from the transcript.
- Keep the balance: roughly 50 percent affirmation, 50 percent challenge.
- Describe behaviours, not personality traits.
- Never shame. Always empower.
- Make every recommendation actionable and realistic.
- Write as a mentor who genuinely wants this salesperson to grow and succeed.

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
    
    async def _generate_with_claude(self, prompt: str) -> str:
        """Call Claude API to generate content (async to not block event loop)"""
        try:
            # Use await with AsyncAnthropic - this is non-blocking!
            response = await self.client.messages.create(
                model=self.model,
                max_tokens=4000,
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

