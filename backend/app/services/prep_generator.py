"""
Meeting Prep Generator Service

Generates AI-powered meeting briefs using Claude/GPT-4 with context from RAG.
"""

from typing import Dict, Any, List, Optional
import logging
import os
import json
from anthropic import AsyncAnthropic  # Use async client to not block event loop
from app.i18n.utils import get_language_instruction
from app.i18n.config import DEFAULT_LANGUAGE

logger = logging.getLogger(__name__)


class PrepGeneratorService:
    """Service for generating meeting preparation briefs"""
    
    def __init__(self):
        self.anthropic = AsyncAnthropic(api_key=os.getenv("ANTHROPIC_API_KEY"))
        self.model = "claude-sonnet-4-20250514"
    
    async def generate_meeting_brief(
        self,
        context: Dict[str, Any],
        language: str = DEFAULT_LANGUAGE
    ) -> Dict[str, Any]:
        """
        Generate comprehensive meeting brief using AI
        
        Args:
            context: RAG context with KB and Research data
            language: Output language code (default: nl)
            
        Returns:
            Structured brief with talking points, questions, strategy
        """
        try:
            # Build prompt based on meeting type
            prompt = self._build_prompt(context, language)
            
            # Call Claude API
            logger.info(f"Generating brief for {context['prospect_company']} ({context['meeting_type']})")
            
            response = await self.anthropic.messages.create(
                model=self.model,
                max_tokens=4096,
                temperature=0.7,
                messages=[{
                    "role": "user",
                    "content": prompt
                }]
            )
            
            # Extract content
            brief_text = response.content[0].text
            
            # Parse structured output
            parsed = self._parse_brief(brief_text, context['meeting_type'])
            
            logger.info(f"Successfully generated brief ({len(brief_text)} chars)")
            
            return {
                "brief_content": brief_text,
                "talking_points": parsed["talking_points"],
                "questions": parsed["questions"],
                "strategy": parsed["strategy"],
                "rag_sources": self._extract_sources(context)
            }
            
        except Exception as e:
            logger.error(f"Error generating brief: {e}")
            raise
    
    def _build_prompt(self, context: Dict[str, Any], language: str = DEFAULT_LANGUAGE) -> str:
        """Build AI prompt based on context and meeting type"""
        
        meeting_type = context["meeting_type"]
        prospect = context["prospect_company"]
        custom_notes = context.get("custom_notes", "")
        lang_instruction = get_language_instruction(language)
        
        # Base prompt
        meeting_type_labels = {
            "discovery": "Discovery Call",
            "demo": "Product Demo", 
            "closing": "Closing Call",
            "follow_up": "Follow-up Meeting",
            "other": "Meeting"
        }
        meeting_label = meeting_type_labels.get(meeting_type, meeting_type)
        
        prompt = f"""You are a smart, experienced sales preparation expert. You deliver commercial intelligence – not sales pitches.

Your goal: a sharp, strategically relevant and to-the-point briefing for an upcoming client meeting.

**Prospect Company**: {prospect}
**Meeting Type**: {meeting_label}

IMPORTANT:
- Translate technology into customer value: faster work, better insights, less manual work, higher quality, more control
- Focus on what's happening at the prospect AND how it's relevant to what we offer
- Make it personal: what's at stake for the specific contact persons?
- Be businesslike, concise and strategic
- {lang_instruction}
"""
        
        if custom_notes:
            prompt += f"**Custom Context**: {custom_notes}\n"
        
        prompt += "\n"
        
        # Add sales rep & company profile context (PERSONALIZATION)
        # Note: Meeting briefs are internal preparation materials, so we use seller context
        # for content relevance (methodology, products, target market) but NOT style rules.
        # Style rules are only applied to customer-facing outputs like emails and reports.
        if context.get("has_profile_context") and context.get("formatted_profile_context"):
            prompt += "## PERSONALIZATION CONTEXT (Use this to tailor the brief):\n"
            prompt += context["formatted_profile_context"] + "\n\n"
            prompt += """**IMPORTANT**: Use the above profile context to:
- Match the sales rep's methodology and communication style
- Leverage their strengths in talking points
- Focus on industries and regions they target
- Include relevant value propositions from their company
- Reference case studies if available

"""
        
        # Add company context from KB
        if context["has_kb_data"]:
            prompt += context["company_info"]["formatted_context"] + "\n"
        else:
            prompt += "## Your Company Information:\nNo specific knowledge base data available. Use general sales best practices.\n\n"
        
        # Add prospect context from research
        if context["has_research_data"]:
            prompt += context["prospect_info"]["formatted_context"] + "\n"
        else:
            prompt += "## Prospect Intelligence:\nNo prior research available. Focus on discovery questions to learn about the prospect.\n\n"
        
        # Add contact persons context (NEW - personalized approach per person)
        if context.get("has_contacts") and context.get("contacts"):
            prompt += self._format_contacts_context(context["contacts"])
        
        # Add meeting type-specific instructions
        prompt += self._get_meeting_type_instructions(meeting_type, language)
        
        return prompt
    
    def _format_contacts_context(self, contacts: list) -> str:
        """Format contact persons into prompt context"""
        if not contacts:
            return ""
        
        context = "## Contact Persons for This Meeting\n\n"
        context += "**CRITICAL**: You MUST personalize the meeting brief for these specific people.\n"
        context += "Use their full profile analysis to create tailored opening lines, discovery questions, and approach strategy.\n\n"
        
        for i, contact in enumerate(contacts, 1):
            context += f"### Contact {i}: {contact.get('name', 'Unknown')}\n"
            
            if contact.get('role'):
                context += f"**Role**: {contact['role']}\n"
            
            if contact.get('decision_authority'):
                authority_labels = {
                    'decision_maker': '🟢 Decision Maker - Controls budget and final decision',
                    'influencer': '🔵 Influencer - Shapes decision but doesn\'t finalize',
                    'gatekeeper': '🟡 Gatekeeper - Controls access to decision makers',
                    'user': '⚪ End User/Champion - Uses the solution, advocates internally'
                }
                context += f"**Decision Authority**: {authority_labels.get(contact['decision_authority'], contact['decision_authority'])}\n"
            
            if contact.get('communication_style'):
                style_labels = {
                    'formal': 'Formal - Prefers structured, professional communication',
                    'informal': 'Informal - Direct, casual, relationship-focused',
                    'technical': 'Technical - Wants data, specs, proof points',
                    'strategic': 'Strategic - Big-picture, ROI-focused, business outcomes'
                }
                context += f"**Communication Style**: {style_labels.get(contact['communication_style'], contact['communication_style'])}\n"
            
            if contact.get('probable_drivers'):
                context += f"**Key Motivations**: {contact['probable_drivers']}\n"
            
            if contact.get('profile_brief'):
                # Include the FULL profile brief - this contains rich analysis
                # (Relevance Assessment, Profile Summary, Role Challenges, Personality)
                brief = contact['profile_brief']
                # Increase limit to capture the rich analysis
                if len(brief) > 2000:
                    brief = brief[:2000] + "\n\n[Profile continues with additional insights...]"
                context += f"\n**Full Contact Profile**:\n{brief}\n"
            
            context += "\n---\n\n"
        
        context += """
## YOUR TASKS FOR THESE CONTACTS:

Since contact research provides WHO they are (not WHAT to say), you MUST generate:

1. **Personalized Opening Lines** for each contact based on:
   - Their role and responsibilities
   - Their communication style preference
   - Recent company news or developments
   - Their probable motivations

2. **Tailored Discovery Questions** based on:
   - Their role-specific challenges
   - Their decision authority (different questions for DM vs Influencer)
   - What they personally care about

3. **Approach Strategy** for each person:
   - How to engage them based on their style
   - Topics that will resonate with their motivations
   - Potential sensitivities to avoid

4. **DMU (Decision Making Unit) Analysis**:
   - Map the contacts by their authority
   - Identify who to prioritize
   - Understand the decision dynamics

"""
        return context
    
    def _format_style_rules(self, style_guide: Dict[str, Any]) -> str:
        """Format style guide into prompt instructions for output styling."""
        tone = style_guide.get("tone", "professional")
        formality = style_guide.get("formality", "professional")
        emoji = style_guide.get("emoji_usage", False)
        length = style_guide.get("writing_length", "concise")
        
        # Tone descriptions
        tone_desc = {
            "direct": "Be straightforward and get to the point",
            "warm": "Be friendly and personable",
            "formal": "Be professional and structured",
            "casual": "Be relaxed and conversational",
            "professional": "Balance warmth with professionalism"
        }
        
        emoji_instruction = "Emoji are OK to use sparingly" if emoji else "Do NOT use emoji"
        length_instruction = "Keep content concise and scannable" if length == "concise" else "Provide detailed explanations"
        
        return f"""## OUTPUT STYLE REQUIREMENTS

Match the sales rep's communication style:
- **Tone**: {tone.title()} - {tone_desc.get(tone, tone_desc['professional'])}
- **Formality**: {formality.title()}
- **Emoji**: {emoji_instruction}
- **Length**: {length_instruction}

The brief must sound like the sales rep wrote it themselves - their voice, their style."""
    
    def _get_meeting_type_instructions(self, meeting_type: str, language: str = DEFAULT_LANGUAGE) -> str:
        """Get specific instructions based on meeting type"""
        
        lang_instruction = get_language_instruction(language)
        
        instructions = {
            "discovery": f"""
You are preparing a strategic, high-value discovery call briefing designed for quick assimilation and confident execution.

Write in clear, sharp and customer-centric language.

Your tone should reflect strategic intelligence, calm authority and psychological awareness.

Every insight must be grounded in the provided context.

This brief should enable the sales rep to walk into the meeting fully prepared in 5 minutes of reading.

# Meeting Brief: Discovery Call

---

## 📋 In One Sentence

A precise sentence capturing:
- who you are meeting
- why this conversation matters for them
- what you must achieve to progress the opportunity

Keep it specific and outcome-oriented.

---

## 📊 At a Glance

| Aspect | Assessment |
|--------|------------|
| **Timing** | 🟢 NOW-Opportunity / 🟡 Nurture / 🔴 No Focus — [one-line rationale] |
| **Stakeholder Readiness** | High / Medium / Low — [based on behavioural or contextual signals] |
| **Complexity** | Simple / Medium / Complex — [why] |
| **Recommended Duration** | [30 / 45 / 60 min] |
| **Key Risk** | [The single factor most likely to derail this meeting] |

Use this section as the rep's snapshot before entering the room.

---

## 🎯 Meeting Objectives

### Primary Goal (Must Achieve)
One essential outcome required to meaningfully progress the opportunity.

### Secondary Goals (Supportive)
- [Secondary goal 1]
- [Secondary goal 2]

(Be specific, not generic.)

### Success Criteria
How you know this meeting truly succeeded:
- [Criterion 1 — observable outcome]
- [Criterion 2]

---

## 🌍 Market Context & Relevance

### What's Happening in Their World

| Trend / Development | Impact on Them | Relevance to Us |
|---------------------|----------------|------------------|
| [Trend 1] | [Effect on their operations, risk or strategy] | [How we help] |
| [Trend 2] | [Effect] | [Relevance] |
| [Trend 3] | [Effect] | [Relevance] |

### Why This Matters Now
Explain in 2–3 tight sentences:
- the timing
- the opportunity window
- the situational relevance for THEM, not us

---

## 👤 Personal Relevance Per Contact

For each attendee:

### [Name] — [Role]

| Aspect | Details |
|--------|---------|
| **Decision Authority** | 🟢 Decision Maker / 🔵 Influencer / 🟡 Gatekeeper / ⚪ User |
| **Communication Style** | [Formal / Informal / Technical / Strategic] |
| **Likely Priorities** | [What matters most to this person] |
| **Personal Stake** | [What they personally gain or avoid] |

**How We Can Help Them**
- [Specific, situational value that speaks to their world]
- [How it reduces friction, improves outcomes, or supports their goals]

**Recommended Approach**
Strategic guidance on how to engage them based on their style and drivers.

---

## 👥 DMU Overview (Decision Making Unit)

| Name | Role | Position | Style | Stance |
|------|------|----------|-------|--------|
| [Name] | [Function] | 🟢 DM / 🔵 Inf / 🟡 GK | [Style] | [Champion / Neutral / Skeptic] |

**Decision Dynamics**
- **Process**: [Top-down / Consensus / Committee / Pragmatic]
- **Likely Criteria**: [ROI / Risk reduction / Operational fit / Adoption ease]
- **Key Stakeholder to Convince**: [Who matters most right now and why]
- **Potential Blockers**: [Who might object, and on what grounds]

---

## ⏱️ Momentum & Timing

**Timing Score**: 🟢 / 🟡 / 🔴

**Urgency Signals**
- [Signal 1 — from research, news, internal change]
- [Signal 2 — deadlines or pressures]
- [Signal 3 — competitive dynamics]

**Window of Opportunity**
Explain:
- the optimal timing
- what accelerates movement
- what slows it
- what happens if you wait

---

## ⚠️ Warnings & Sensitivities

### Topics to Handle Carefully

| Topic | Why Sensitive | How to Approach |
|-------|---------------|-----------------|
| ...   | ...           | ...             |

### Likely Objections

| Objection | Root Cause | Recommended Response |
|-----------|------------|----------------------|
| ...       | ...        | ...                  |

### Red Flags
List the 1–2 behavioural signs that indicate risk or hidden blockers.

---

## 💬 Conversation Starters

Rooted in research and contact insight.

**Personal Opener**
> "[Opener based on recent activity or shared context]"

**Business Opener**
> "[Opener tied to a specific trend or company development]"

**Direct Opener** (for time-pressured execs)
> "[Succinct value-context opener]"

---

## 🗣️ Talking Points

### Opening (First 5 Minutes)
- Personal connection
- Confirm agenda and time
- Set expectation that you'll ask questions to understand their situation

### Discovery Phase (Core 20–25 Minutes)

#### Theme 1: Current Situation
- What to explore
- What signals to listen for

#### Theme 2: Challenges & Frustrations
- What to explore
- What pitfalls or pains to validate

#### Theme 3: Priorities & Goals
- What to explore
- What matters to leadership, operations or clients

### Value Connection (10 Minutes)
- Link findings to relevant value
- Share one well-chosen case
- Gauge resonance and reaction

### Close (5 Minutes)
- Summarise insights
- Propose next step
- Confirm stakeholders to involve

---

## ❓ Discovery Questions (SPIN-Based)

### Situation
1. [Question]
2. [Question]
3. [Question]

### Problem
1. [Question]
2. [Question]
3. [Question]

### Implication
1. [Question]
2. [Question]
3. [Question]

### Need-Payoff
1. [Question]
2. [Question]
3. [Question]

### Human / Rapport
- [Thoughtful, context-aware question]

---

## 🎯 Meeting Strategy

### If the Meeting Goes Well
- [Recommended next step]
- [Who to involve]
- [Suggested timing]

### If They Are Hesitant
- [Fallback step]
- [Message to keep conversation open]

### If They Are Not Ready
- [Nurture motion]
- [Trigger to re-engage]

---

## ✅ Before You Go (Checklist)

- [ ] Research brief reviewed
- [ ] Contact profiles understood
- [ ] Top 3 discovery questions prepared
- [ ] One relevant example or case readied
- [ ] Calendar open for next steps
- [ ] LinkedIn profile of contacts reviewed
- [ ] Opening line mentally rehearsed

---

RULES:
- Be specific to this prospect and these contacts – no generic templates.
- Always anchor in customer value, not product features.
- Keep tone professional, calm and confident.
- Write for a senior sales professional who values clarity and strategic depth.
- If context is missing or unclear, note it rather than guessing.
- Keep total brief under 1200 words (excluding tables).

{lang_instruction}

Generate the complete discovery call brief now:
""",
            "demo": f"""
You are preparing a strategic product demo briefing designed for maximum impact and confident execution.

Write in clear, sharp and customer-centric language.

Your tone should reflect strategic intelligence, calm authority and demonstration mastery.

Every insight must be grounded in the provided context.

This brief should enable the sales rep to deliver a compelling, tailored demo in 5 minutes of reading.

# Meeting Brief: Product Demo

---

## 📋 In One Sentence

A precise sentence capturing:
- who you are demoing to
- what specific outcomes they need to see
- what must happen to progress the opportunity

Keep it specific and outcome-oriented.

---

## 📊 At a Glance

| Aspect | Assessment |
|--------|------------|
| **Demo Readiness** | 🟢 Ready to Buy / 🟡 Evaluating / 🔴 Early Stage — [rationale] |
| **Audience Profile** | Technical / Executive / Mixed — [who's in the room] |
| **Complexity** | Simple / Medium / Complex — [customization needed] |
| **Recommended Duration** | [30 / 45 / 60 min] |
| **Key Risk** | [The single factor most likely to derail this demo] |

Use this section as the rep's snapshot before entering the room.

---

## 🎯 Demo Objectives

### Primary Goal (Must Achieve)
One essential outcome required to meaningfully progress the opportunity.

### Secondary Goals (Supportive)
- [Secondary goal 1]
- [Secondary goal 2]

### Success Criteria
How you know this demo truly succeeded:
- [Criterion 1 — observable reaction or statement]
- [Criterion 2 — next step commitment]

---

## 🔗 Connecting Discovery to Demo

### Key Insights from Discovery

| Discovery Finding | Demo Response |
|-------------------|---------------|
| [Pain point 1] | [Feature/capability to show] |
| [Pain point 2] | [Feature/capability to show] |
| [Desired outcome] | [How we deliver it] |

### Their Words to Echo
Direct quotes or paraphrased statements from discovery to reference during demo:
- "[Quote about their challenge]"
- "[Quote about their goal]"

---

## 👤 Personal Relevance Per Attendee

For each attendee:

### [Name] — [Role]

| Aspect | Details |
|--------|---------|
| **Decision Authority** | 🟢 Decision Maker / 🔵 Influencer / 🟡 Gatekeeper / ⚪ User |
| **Demo Interest** | [What they specifically want to see] |
| **Communication Style** | [Technical depth / Executive summary / Hands-on] |
| **Likely Questions** | [What they'll probably ask] |

**Tailored Demo Moment**
One specific feature or workflow to show that speaks directly to their priorities.

---

## 👥 DMU Overview

| Name | Role | Position | Focus | Stance |
|------|------|----------|-------|--------|
| [Name] | [Function] | 🟢 DM / 🔵 Inf / 🟡 GK | [Their focus] | [Champion / Neutral / Skeptic] |

**Demo Dynamics**
- **Who to impress most**: [Key person and why]
- **Who might challenge**: [Skeptic and their likely objection]
- **How to balance**: [Strategy for mixed audience]

---

## ⚠️ Warnings & Sensitivities

### Topics to Handle Carefully

| Topic | Why Sensitive | How to Approach |
|-------|---------------|-----------------|
| ...   | ...           | ...             |

### Likely Technical Objections

| Objection | Root Cause | Recommended Response |
|-----------|------------|----------------------|
| ...       | ...        | ...                  |

### Demo Pitfalls to Avoid
- [Feature that might confuse them]
- [Workflow that doesn't match their process]
- [Comparison trap with competitor]

---

## 🎬 Demo Flow

### Opening (5 Minutes)
- Recap discovery insights (show you listened)
- Confirm agenda and their priorities
- Set expectation: "I'll show you X, Y, Z based on what you told me"

### Core Demo (25–30 Minutes)

#### Segment 1: [Pain Point / Use Case 1]
- **What to show**: [Specific feature/workflow]
- **Why it matters to them**: [Connect to their stated need]
- **Talking point**: "[Key message]"
- **Check-in question**: "[Gauge resonance]"

#### Segment 2: [Pain Point / Use Case 2]
- **What to show**: [Specific feature/workflow]
- **Why it matters to them**: [Connect to their stated need]
- **Talking point**: "[Key message]"
- **Check-in question**: "[Gauge resonance]"

#### Segment 3: [Pain Point / Use Case 3]
- **What to show**: [Specific feature/workflow]
- **Why it matters to them**: [Connect to their stated need]
- **Talking point**: "[Key message]"
- **Check-in question**: "[Gauge resonance]"

### Q&A (10 Minutes)
- Anticipated questions and prepared answers
- Technical deep-dives if requested
- Redirect off-topic questions gracefully

### Close (5 Minutes)
- Summarise key value demonstrated
- Propose concrete next step (trial, POC, proposal)
- Confirm timeline and stakeholders

---

## 💬 Key Messages

### Value Statements (Use These Words)
1. [Value statement tied to their specific situation]
2. [Differentiator vs. their current approach]
3. [ROI or outcome they can expect]

### Proof Points
- [Relevant case study or metric]
- [Similar customer reference]

---

## ❓ Questions to Ask During Demo

### Validation Questions
1. [Confirm understanding: "Does this match how you'd use it?"]
2. [Gauge interest: "Is this the kind of result you're looking for?"]

### Progression Questions
1. [Identify blockers: "What would need to be true for this to work for you?"]
2. [Next step: "Who else should see this?"]

---

## 🎯 Meeting Strategy

### If the Demo Goes Well
- [Recommended next step: trial, POC, proposal]
- [Who to involve]
- [Suggested timing]

### If They Have Concerns
- [How to address]
- [Fallback step]

### If They Need More Time
- [Nurture motion]
- [What to send after]

---

## ✅ Before You Go (Checklist)

- [ ] Discovery notes reviewed
- [ ] Demo environment tested and ready
- [ ] Attendee priorities confirmed
- [ ] Three key messages prepared
- [ ] One proof point ready to share
- [ ] Calendar open for next steps
- [ ] Backup plan if technical issues arise

---

RULES:
- Be specific to this prospect and these contacts – no generic demo scripts.
- Always connect features to their stated needs.
- Keep tone professional, calm and confident.
- Write for a senior sales professional who values clarity and strategic depth.
- If context is missing or unclear, note it rather than guessing.
- Keep total brief under 1000 words (excluding tables).

{lang_instruction}

Generate the complete demo brief now:
""",
            "closing": f"""
You are preparing a strategic closing call briefing designed for decisive execution and deal completion.

Write in clear, sharp and commercially astute language.

Your tone should reflect strategic confidence, negotiation awareness and psychological precision.

Every insight must be grounded in the provided context.

This brief should enable the sales rep to close with confidence in 5 minutes of reading.

# Meeting Brief: Closing Call

---

## 📋 In One Sentence

A precise sentence capturing:
- the deal at stake
- what's required to close
- the single biggest factor that will determine success or failure

Keep it specific and outcome-oriented.

---

## 📊 At a Glance

| Aspect | Assessment |
|--------|------------|
| **Close Probability** | 🟢 High (>70%) / 🟡 Medium (40-70%) / 🔴 Low (<40%) — [rationale] |
| **Decision Stage** | Final Approval / Negotiation / Stalled — [where they are] |
| **Deal Value** | [Amount or range] |
| **Timeline** | [Expected close date] |
| **Key Risk** | [The single factor most likely to derail this deal] |

Use this section as the rep's snapshot before entering the room.

---

## 🎯 Closing Objectives

### Primary Goal (Must Achieve)
One essential outcome: verbal commitment, signed contract, or clear next step to signature.

### Secondary Goals (Supportive)
- [Secondary goal 1]
- [Secondary goal 2]

### Success Criteria
How you know this meeting truly succeeded:
- [Criterion 1 — observable commitment]
- [Criterion 2 — timeline locked]

---

## 💰 Deal Summary

| Element | Details |
|---------|---------|
| **Deal Value** | [Amount] |
| **Contract Term** | [Duration] |
| **Products/Services** | [What's included] |
| **Implementation Timeline** | [Start date, milestones] |
| **Key Terms Agreed** | [Pricing, payment terms, SLAs] |
| **Outstanding Items** | [What's still open] |

---

## 👤 Stakeholder Readiness

For each decision maker:

### [Name] — [Role]

| Aspect | Details |
|--------|---------|
| **Decision Authority** | 🟢 Final Sign-off / 🔵 Recommender / 🟡 Approver |
| **Current Stance** | Champion / Supportive / Neutral / Skeptical |
| **Personal Stake** | [What they gain from this deal closing] |
| **Concerns** | [What might make them hesitate] |

**How to Secure Their Yes**
- [Specific action or message that will convince them]
- [What they need to hear or see]

---

## 👥 DMU Final Check

| Name | Role | Authority | Stance | Required Action |
|------|------|-----------|--------|-----------------|
| [Name] | [Function] | 🟢 Final / 🔵 Rec / 🟡 Approve | [Stance] | [What they must do] |

**Decision Dynamics**
- **Who signs**: [Name and what triggers signature]
- **Who can block**: [Name and their potential objection]
- **Consensus required**: Yes / No — [process]

---

## ⚠️ Risks & Blockers

### Deal-Killers to Watch

| Risk | Likelihood | Mitigation |
|------|------------|------------|
| [Risk 1] | High / Medium / Low | [How to address] |
| [Risk 2] | High / Medium / Low | [How to address] |

### Competitive Threat
- [Competitor status]
- [Their likely counter-move]
- [Our differentiation to emphasize]

### Internal Blockers
- [Procurement, legal, budget holder concerns]
- [How to navigate]

---

## 💎 Value Reinforcement

### ROI Summary
| Investment | Return | Timeframe |
|------------|--------|-----------|
| [Cost] | [Benefit / savings] | [When realized] |

### Why Us (vs. Alternatives)
1. [Key differentiator relevant to their priorities]
2. [Proof point or reference]
3. [Risk reduction we offer]

### Their Words to Echo
Direct quotes from the process to reinforce their own reasoning:
- "[Quote about their pain]"
- "[Quote about desired outcome]"
- "[Quote about why they chose us]"

---

## 🗣️ Closing Conversation Flow

### Opening (5 Minutes)
- Thank them for the journey
- Confirm understanding of where we are
- State purpose: "Today I'd like to finalize our agreement"

### Value Recap (10 Minutes)
- Summarise the business case
- Reference their stated needs and how we address them
- Share one final proof point

### Address Remaining Concerns (10 Minutes)
- Proactively surface any lingering doubts
- Handle objections with prepared responses
- Confirm all decision criteria are met

### The Ask (5 Minutes)
- Direct, confident close
- Propose specific next step (signature, contract review, start date)
- Confirm timeline and stakeholders

### If They Say Yes
- Express appreciation (not surprise)
- Confirm immediate next steps
- Introduce implementation/onboarding

### If They Hesitate
- Diagnose the blocker
- Propose path to resolution
- Agree on follow-up action and date

---

## ❓ Closing Questions

### Confirmation Questions
1. [Have we addressed all your requirements?]
2. [Is there anything else you need to make a decision?]

### Commitment Questions
1. [Are you ready to move forward?]
2. [What would you need to see to sign this week?]

### Blocker Questions
1. [Is there anyone else who needs to weigh in?]
2. [Are there any concerns we haven't discussed?]

---

## 🤝 Negotiation Readiness

### Our Position
| Element | Ideal | Acceptable | Walk-Away |
|---------|-------|------------|-----------|
| Price | [Amount] | [Amount] | [Amount] |
| Terms | [Preferred] | [Acceptable] | [Minimum] |
| Timeline | [Ideal] | [Acceptable] | [Latest] |

### Concessions We Can Offer
- [Concession 1 — value and cost to us]
- [Concession 2 — value and cost to us]

### Concessions to Request in Return
- [If we give X, ask for Y]

### Red Lines
- [What we cannot compromise on]

---

## 🎯 Meeting Strategy

### If They Close
- [Immediate next steps]
- [Who to introduce: implementation, CS]
- [Celebration message to send]

### If They Need More Time
- [Acceptable delay]
- [What must happen in that time]
- [Deadline to set]

### If They Go Cold
- [Re-engagement strategy]
- [Trigger to try]
- [When to walk away]

---

## ✅ Before You Go (Checklist)

- [ ] Full deal terms understood
- [ ] All decision makers' positions confirmed
- [ ] Contract/proposal ready to share
- [ ] Objection responses prepared
- [ ] Negotiation boundaries clear
- [ ] Implementation timeline ready to discuss
- [ ] Calendar open for immediate next steps

---

RULES:
- Be specific to this deal and these stakeholders – no generic closing scripts.
- Always reinforce customer value, not our urgency.
- Keep tone professional, confident and assertive without pressure.
- Write for a senior sales professional who values strategic closure.
- If context is missing or unclear, note it rather than guessing.
- Keep total brief under 1000 words (excluding tables).

{lang_instruction}

Generate the complete closing call brief now:
""",
            "follow_up": f"""
You are preparing a strategic follow-up meeting briefing designed for momentum maintenance and deal progression.

Write in clear, sharp and relationship-aware language.

Your tone should reflect strategic continuity, attentive follow-through and commercial awareness.

Every insight must be grounded in the provided context.

This brief should enable the sales rep to re-engage with confidence in 5 minutes of reading.

# Meeting Brief: Follow-up Meeting

---

## 📋 In One Sentence

A precise sentence capturing:
- what was previously discussed
- what has changed since
- what must happen in this meeting to progress the opportunity

Keep it specific and outcome-oriented.

---

## 📊 At a Glance

| Aspect | Assessment |
|--------|------------|
| **Momentum** | 🟢 Hot / 🟡 Warm / 🔴 Cold — [rationale] |
| **Last Contact** | [Date and type of interaction] |
| **Open Items** | [Number and nature of unresolved items] |
| **Risk Level** | Low / Medium / High — [key risk] |
| **Recommended Approach** | Push / Nurture / Re-qualify |

Use this section as the rep's snapshot before entering the room.

---

## 🎯 Meeting Objectives

### Primary Goal (Must Achieve)
One essential outcome required to meaningfully progress the opportunity.

### Secondary Goals (Supportive)
- [Secondary goal 1]
- [Secondary goal 2]

### Success Criteria
How you know this meeting truly succeeded:
- [Criterion 1 — observable outcome]
- [Criterion 2 — next step locked]

---

## 🔙 Previous Meeting Recap

### What Was Discussed
| Topic | Their Position | Our Response |
|-------|----------------|--------------|
| [Topic 1] | [What they said] | [What we committed] |
| [Topic 2] | [What they said] | [What we committed] |

### Agreements Made
- [Agreement 1]
- [Agreement 2]

### Open Items / Action Points

| Item | Owner | Status | Due |
|------|-------|--------|-----|
| [Item 1] | [Us / Them] | ✅ Done / ⏳ Pending / ❌ Overdue | [Date] |
| [Item 2] | [Us / Them] | ✅ Done / ⏳ Pending / ❌ Overdue | [Date] |

### Unresolved Questions
- [Question they had that we need to address]
- [Concern that wasn't fully resolved]

---

## 🌍 What's Changed Since Last Contact

### At the Prospect

| Development | Impact on Opportunity |
|-------------|----------------------|
| [News, announcement, change] | [How it affects our deal] |
| [Personnel change, restructure] | [How it affects our deal] |

### At Our End
- [Relevant update: new feature, case study, pricing]
- [Resource availability, timing change]

### Market Context
- [Industry development that's relevant]
- [Competitive movement to be aware of]

---

## 👤 Contact Status Update

For each attendee:

### [Name] — [Role]

| Aspect | Current Status |
|--------|----------------|
| **Engagement Level** | 🟢 Active / 🟡 Passive / 🔴 Disengaged |
| **Recent Activity** | [LinkedIn post, news mention, company change] |
| **Likely Priorities Now** | [What's on their mind] |
| **Stance Shift** | [More positive / Same / More cautious] |

**Re-engagement Approach**
- [How to reconnect based on their current situation]
- [Topic or insight to lead with]

---

## ⏱️ Momentum Analysis

**Momentum Score**: 🟢 / 🟡 / 🔴

### Positive Signals
- [Signal 1 — engagement, response, internal advocacy]
- [Signal 2 — timeline confirmation, budget movement]

### Warning Signs
- [Signal 1 — delayed response, stakeholder change]
- [Signal 2 — competitor activity, priority shift]

### What Must Happen to Advance
- [Action 1 — on their side]
- [Action 2 — on our side]

---

## ⚠️ Warnings & Sensitivities

### Changed Circumstances
- [What's different that we must acknowledge]
- [Sensitivity to handle carefully]

### Potential Obstacles
- [Blocker that may have emerged]
- [Stakeholder who may have concerns]

### Topics to Avoid
- [Subject that could derail the conversation]

---

## 🗣️ Conversation Flow

### Opening (5 Minutes)
- Acknowledge time since last contact
- Reference specific point from previous meeting (show continuity)
- Confirm agenda and time available

### Status Update (10 Minutes)
- Summarise where we left off
- Address any open items we owed them
- Ask about progress on their side

### Value Reinforcement (10 Minutes)
- Share relevant update (case study, feature, insight)
- Connect to their priorities
- Gauge continued resonance

### Path Forward (10 Minutes)
- Identify remaining steps
- Confirm timeline and stakeholders
- Propose concrete next action

### Close (5 Minutes)
- Summarise agreements
- Lock next step
- Express continued commitment

---

## ❓ Questions to Ask

### Progress Check
1. [What's happened since we last spoke?]
2. [Have your priorities or timeline changed?]

### Blocker Discovery
1. [Is there anything holding this up internally?]
2. [Are there new stakeholders we should include?]

### Commitment
1. [What would help you move forward?]
2. [Can we lock in our next step now?]

---

## 🎯 Meeting Strategy

### If Momentum Is Strong
- [Push for next concrete step]
- [Propose accelerated timeline]

### If They've Gone Quiet
- [Re-qualify interest]
- [Offer value without pressure]

### If Circumstances Have Changed
- [Adapt approach]
- [Reframe value proposition]

---

## ✅ Before You Go (Checklist)

- [ ] Previous meeting notes reviewed
- [ ] Open items status confirmed
- [ ] New developments researched
- [ ] Contact LinkedIn profiles checked
- [ ] Relevant update to share prepared
- [ ] Calendar open for next steps

---

RULES:
- Be specific to this prospect and the previous conversation – no generic follow-up templates.
- Always show continuity and attentiveness.
- Keep tone professional, warm and persistent without desperation.
- Write for a senior sales professional who values relationship continuity.
- If context is missing or unclear, note it rather than guessing.
- Keep total brief under 900 words (excluding tables).

{lang_instruction}

Generate the complete follow-up meeting brief now:
""",
            "other": f"""
You are preparing a strategic meeting briefing designed for any customer-facing interaction.

Write in clear, sharp and customer-centric language.

Your tone should reflect strategic intelligence and professional adaptability.

Every insight must be grounded in the provided context.

This brief should enable the sales rep to engage with confidence in 5 minutes of reading.

# Meeting Brief

---

## 📋 In One Sentence

A precise sentence capturing:
- who you are meeting
- why this conversation matters
- what you must achieve

Keep it specific and outcome-oriented.

---

## 📊 At a Glance

| Aspect | Assessment |
|--------|------------|
| **Meeting Type** | [Relationship / Technical / Strategic / Operational] |
| **Priority** | High / Medium / Low — [rationale] |
| **Stakeholder Level** | [Executive / Manager / Practitioner] |
| **Recommended Duration** | [30 / 45 / 60 min] |
| **Key Risk** | [The single factor most likely to derail this meeting] |

---

## 🎯 Meeting Objectives

### Primary Goal (Must Achieve)
One essential outcome required from this meeting.

### Secondary Goals (Supportive)
- [Secondary goal 1]
- [Secondary goal 2]

### Success Criteria
How you know this meeting truly succeeded:
- [Criterion 1 — observable outcome]
- [Criterion 2]

---

## 🌍 Context & Relevance

### What's Happening in Their World

| Development | Impact | Relevance to Us |
|-------------|--------|-----------------|
| [Trend / change 1] | [Effect on them] | [How we connect] |
| [Trend / change 2] | [Effect on them] | [How we connect] |

### Why This Matters Now
2–3 sentences on timing and situational relevance.

---

## 👤 Personal Relevance Per Contact

For each attendee:

### [Name] — [Role]

| Aspect | Details |
|--------|---------|
| **Authority** | 🟢 Decision Maker / 🔵 Influencer / 🟡 Gatekeeper / ⚪ User |
| **Communication Style** | [Formal / Informal / Technical / Strategic] |
| **Likely Priorities** | [What matters most to this person] |
| **Personal Stake** | [What they gain or avoid] |

**How We Can Help Them**
- [Specific value for their situation]

**Recommended Approach**
How to engage them based on their style.

---

## ⚠️ Warnings & Sensitivities

### Topics to Handle Carefully

| Topic | Why Sensitive | How to Approach |
|-------|---------------|-----------------|
| ...   | ...           | ...             |

### Points of Attention
- [Anything unusual to be aware of]
- [Recent changes that might affect the conversation]

---

## 🗣️ Talking Points

### Key Messages
1. [Message 1 — tied to their priorities]
2. [Message 2 — our value proposition]
3. [Message 3 — differentiator or proof point]

### Conversation Flow
- **Opening**: [How to start]
- **Core discussion**: [Main topics to cover]
- **Close**: [How to wrap up and next steps]

---

## ❓ Questions to Ask

1. [Discovery or validation question]
2. [Understanding their priorities]
3. [Identifying blockers or concerns]
4. [Next step confirmation]

---

## 🎯 Meeting Strategy

### If It Goes Well
- [Recommended next step]
- [Who to involve]

### If They Are Hesitant
- [Fallback approach]
- [How to keep momentum]

---

## ✅ Before You Go (Checklist)

- [ ] Research reviewed
- [ ] Contact profiles understood
- [ ] Key messages prepared
- [ ] Questions ready
- [ ] Calendar open for next steps

---

RULES:
- Be specific to this prospect and these contacts – no generic templates.
- Always anchor in customer value.
- Keep tone professional and adaptable.
- Write for a senior sales professional who values clarity.
- If context is missing or unclear, note it rather than guessing.
- Keep total brief under 700 words (excluding tables).

{lang_instruction}

Generate the complete meeting brief now:
"""
        }
        
        template = instructions.get(meeting_type, instructions["other"])
        # Replace placeholder with actual language instruction
        return template.replace("{lang_instruction}", lang_instruction)
    
    def _parse_brief(self, brief_text: str, meeting_type: str) -> Dict[str, Any]:
        """Parse structured data from brief text"""
        
        # Extract talking points
        talking_points = self._extract_section(brief_text, "Talking Points", "Questions")
        
        # Extract questions
        questions = self._extract_questions(brief_text)
        
        # Extract strategy
        strategy = self._extract_section(brief_text, "Strategy", "---")
        
        return {
            "talking_points": self._structure_talking_points(talking_points),
            "questions": questions,
            "strategy": strategy
        }
    
    def _extract_section(self, text: str, start_marker: str, end_marker: str) -> str:
        """Extract text between two markers"""
        try:
            start_idx = text.find(start_marker)
            if start_idx == -1:
                return ""
            
            end_idx = text.find(end_marker, start_idx)
            if end_idx == -1:
                end_idx = len(text)
            
            return text[start_idx:end_idx].strip()
        except:
            return ""
    
    def _extract_questions(self, text: str) -> List[str]:
        """Extract questions from brief"""
        questions = []
        lines = text.split("\n")
        
        in_questions_section = False
        for line in lines:
            if "Questions" in line or "Discovery Questions" in line:
                in_questions_section = True
                continue
            
            if in_questions_section:
                if line.startswith("#") and "Questions" not in line:
                    break
                
                # Extract numbered questions
                if line.strip() and (line.strip()[0].isdigit() or line.strip().startswith("-")):
                    question = line.strip().lstrip("0123456789.-) ").strip()
                    if question and "?" in question:
                        questions.append(question)
        
        return questions[:15]  # Limit to 15 questions
    
    def _structure_talking_points(self, talking_points_text: str) -> List[Dict[str, Any]]:
        """Structure talking points into categories"""
        # Simple parsing - can be enhanced
        return [{
            "category": "Talking Points",
            "points": [p.strip() for p in talking_points_text.split("\n") if p.strip() and not p.strip().startswith("#")][:10]
        }]
    
    def _extract_sources(self, context: Dict[str, Any]) -> List[Dict[str, str]]:
        """Extract sources used in RAG"""
        sources = []
        
        # Add KB sources
        for chunk in context.get("company_info", {}).get("kb_chunks", [])[:5]:
            sources.append({
                "type": "knowledge_base",
                "source": chunk.get("source", "Unknown"),
                "score": chunk.get("score", 0)
            })
        
        # Add research source
        if context.get("has_research_data"):
            research = context.get("prospect_info", {}).get("research_data", {})
            sources.append({
                "type": "research_brief",
                "source": research.get("company_name", "Unknown"),
                "created_at": research.get("created_at", "")
            })
        
        return sources


# Singleton instance
prep_generator = PrepGeneratorService()
