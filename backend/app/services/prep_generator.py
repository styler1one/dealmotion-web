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
                max_tokens=8000,  # Increased for complete state-of-the-art briefs with all sections
                temperature=0.5,  # Balanced: creative but consistent business output
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

## ⚡ 3-MINUTE EXECUTIVE SUMMARY

**Read this if you only have 3 minutes before the meeting.**

### 🎯 The ONE Thing
If you remember nothing else from this brief, remember this:
> [Single most critical insight or action that will determine success in this meeting]

### Quick Facts
| Element | Details |
|---------|---------|
| **Company** | [Name] — [Industry, size, location] |
| **Contacts** | [Name(s) + Role(s)] |
| **Timing** | 🟢 NOW / 🟡 Nurture / 🔴 No Focus |
| **Their #1 Pain** | [Most urgent challenge we can solve] |
| **Our Best Fit** | [Product/service that addresses their pain] |

### Your 3 Must-Do's
1. **Validate**: [The one hypothesis you must confirm]
2. **Discover**: [The critical unknown you must uncover]
3. **Advance**: [The specific next step to propose]

### Opening Line (Use This)
> "[Ready-to-use opener personalized to the contact and situation]"

### Top 3 Questions
1. [Most important discovery question]
2. [Second priority question]
3. [Third priority question]

---

## 📋 In One Sentence

A precise sentence capturing:
- who you are meeting
- why this conversation matters for them
- what you must achieve to progress the opportunity

---

## 📊 At a Glance

| Aspect | Assessment |
|--------|------------|
| **Timing** | 🟢 NOW-Opportunity / 🟡 Nurture / 🔴 No Focus — [one-line rationale] |
| **Stakeholder Readiness** | High / Medium / Low — [based on behavioural or contextual signals] |
| **Deal Complexity** | Simple / Medium / Complex — [why] |
| **Recommended Duration** | [30 / 45 / 60 min] |
| **Key Risk** | [The single factor most likely to derail this meeting] |

---

## 📊 MEDDIC Qualification Status

| Element | Status | Details | Discovery Goal |
|---------|--------|---------|----------------|
| **M**etrics | 🔴 Unknown / 🟡 Identified / 🟢 Quantified | [KPIs they want to improve] | [Question to uncover] |
| **E**conomic Buyer | 🔴 Not found / 🟡 Suspected / 🟢 Confirmed | [Name + evidence] | [Question to confirm] |
| **D**ecision Criteria | 🔴 Unknown / 🟡 Partial / 🟢 Clear | [How they'll evaluate] | [Question to clarify] |
| **D**ecision Process | 🔴 Unknown / 🟡 Partial / 🟢 Mapped | [Steps to signature] | [Question to map] |
| **I**dentified Pain | 🔴 Assumed / 🟡 Stated / 🟢 Quantified | [Pain + business impact] | [Question to deepen] |
| **C**hampion | 🔴 None / 🟡 Potential / 🟢 Active | [Name + proof of advocacy] | [Question to test] |

**MEDDIC Priority for This Meeting**: Focus on [Element] because [rationale].

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
- [Criterion 2 — commitment or statement]

---

## 💡 Value Translation (So What?)

**Don't tell them what we do. Show them what it means for THEM.**

| Our Capability | Their Situation | Concrete Impact |
|----------------|-----------------|-----------------|
| [Product/Feature 1] | [Their specific pain or goal] | [Quantified outcome: X hours saved, Y% improvement, €Z saved] |
| [Product/Feature 2] | [Their specific pain or goal] | [Quantified outcome] |
| [Product/Feature 3] | [Their specific pain or goal] | [Quantified outcome] |

**The Money Question**: If we solve [their #1 pain], what's that worth to them annually? 
- Estimate: [€ amount or time saved]

---

## ⚔️ Competitive Landscape

### Known/Suspected Alternatives

| Competitor | Likelihood | Their Strength | Our Counter | Landmine to Avoid |
|------------|------------|----------------|-------------|-------------------|
| [Name or "Status Quo"] | High / Medium / Low | [What they do well] | [Our differentiator] | [Don't say this] |
| [Name] | High / Medium / Low | [Strength] | [Counter] | [Avoid] |

### Our Unfair Advantage
[The one thing only we can offer in this specific situation — not generic features]

### If Competitor Comes Up
- **Acknowledge**: "[Respectful one-liner about competitor]"
- **Redirect**: "[Pivot to our unique value]"

---

## 👤 Personal Relevance Per Contact

For each attendee:

### [Name] — [Role]

| Aspect | Details |
|--------|---------|
| **Decision Authority** | 🟢 Decision Maker / 🔵 Influencer / 🟡 Gatekeeper / ⚪ User |
| **Communication Style** | Formal / Informal / Technical / Strategic |
| **Likely Priorities** | [What matters most to this person] |
| **Personal Stake** | [What they personally gain or avoid] |
| **Potential Concerns** | [What might make them hesitant] |

**How We Help Them Specifically**
- [Value that speaks to THEIR world, not generic benefits]

**Tailored Opening for This Person**
> "[Personalized opener based on their role, recent activity, or interests]"

**Approach Strategy**
- Engage via: [Technical depth / Business outcomes / Personal relationship]
- Avoid: [Topic or style that won't resonate]

---

## 👥 DMU Overview (Decision Making Unit)

| Name | Role | Authority | Style | Stance | Key to Win Them |
|------|------|-----------|-------|--------|-----------------|
| [Name] | [Function] | 🟢 DM / 🔵 Inf / 🟡 GK / ⚪ User | [Style] | Champion / Neutral / Skeptic | [What they need] |

### Relationship Dynamics
- [Name A] reports to [Name B] — relationship: [strong / neutral / tense]
- Key influencer: [Who shapes opinions internally]
- Potential blocker: [Who might object and why]

### Decision Dynamics
- **Process**: [Top-down / Consensus / Committee / Pragmatic]
- **Criteria**: [ROI / Risk reduction / Ease of use / Speed to value]
- **Timeline**: [Known or suspected decision timeline]
- **Budget Cycle**: [Fiscal year end, budget holder if known]

---

## 💰 Budget Intelligence

| Aspect | Status | Details |
|--------|--------|---------|
| **Budget Allocated** | Yes / No / Unknown / TBD | [Context] |
| **Budget Holder** | [Name if known] | [Relationship to contacts] |
| **Approval Threshold** | [Amount that needs higher approval] | [Process] |
| **Fiscal Year End** | [Month] | [Implication for timing] |

**Budget Question to Ask**: "[Specific question to uncover budget reality without being pushy]"

---

## ⏱️ Momentum & Timing

**Timing Score**: 🟢 / 🟡 / 🔴

**Urgency Signals**
- [Signal 1 — from research, news, internal change]
- [Signal 2 — deadlines or pressures]
- [Signal 3 — competitive dynamics]

**Window of Opportunity**
- What accelerates: [Factor that speeds up decision]
- What slows: [Factor that delays]
- Cost of waiting: [What happens if they do nothing]

---

## ⚠️ Warnings & Sensitivities

### Topics to Handle Carefully

| Topic | Why Sensitive | How to Approach |
|-------|---------------|-----------------|
| [Topic 1] | [Reason] | [Recommended framing] |
| [Topic 2] | [Reason] | [Recommended framing] |

### Likely Objections — Deep Dive

For the top 2-3 objections, provide complete rebuttals using Feel-Felt-Found:

**Objection 1**: "[Most likely objection]"

| Element | What to Say |
|---------|-------------|
| **Feel** | "I completely understand. [Acknowledge their concern genuinely]" |
| **Felt** | "Many of our clients felt the same way initially. [Normalize the concern]" |
| **Found** | "What they found was [specific outcome or realization]. [Share the transformation]" |
| **Proof** | "[Specific client or data point that proves this]" |
| **Bridge** | "[Question to move forward]: Would you be open to exploring...?" |

**Objection 2**: "[Second most likely objection]"

| Element | What to Say |
|---------|-------------|
| **Feel** | "[Acknowledgment]" |
| **Felt** | "[Normalization]" |
| **Found** | "[Transformation]" |
| **Proof** | "[Evidence]" |
| **Bridge** | "[Transition question]" |

### Red Flags to Watch
- [Behavioral sign 1 that indicates hidden blockers]
- [Behavioral sign 2]

---

## 🤔 What If They Ask...

Prepare for awkward or difficult questions:

| Question | Why They Ask | Your Response |
|----------|--------------|---------------|
| "What does this cost?" | Testing budget fit early | "That depends on scope. Let's first understand what you need, then I can give you a realistic indication. What's your budget thinking?" |
| "Can't you do this internally?" | Validating need for external help | "Absolutely you could. The question is whether that's the best use of your team's time and focus. Your core business is [their focus], not [our expertise]." |
| "Why you vs. [competitor]?" | Benchmarking | "Good question. Where we're unique is [unfair advantage]. But more importantly: what are YOUR criteria for choosing a partner?" |
| "How long does this take?" | Timeline planning | "A typical [first step] takes [X weeks]. Full implementation depends on scope, usually [Y-Z months] for significant impact." |
| "What if it doesn't work?" | Risk mitigation | "We structure our engagements with clear milestones and success criteria. If we're not seeing results by [checkpoint], we adjust or stop." |

---

## 💬 Conversation Starters

**Personal Opener** (relationship-focused)
> "[Based on LinkedIn, shared interests, or recent activity]"

**Business Opener** (company-focused)
> "[Based on recent news, announcement, or market trend]"

**Direct Opener** (for time-pressured executives)
> "[Value-forward, respect their time]"

---

## ❓ Discovery Questions (SPIN-Based + Power Questions)

### Situation (Understand their current state)
1. [Question about their current process/situation]
2. [Question about their team/resources]
3. [Question about their tools/systems]

### Problem (Uncover pain points)
1. [Question about challenges/frustrations]
2. [Question about what's not working]
3. [Question about impact on their work]

### Implication (Deepen the pain)
1. [Question about consequences if unsolved]
2. [Question about ripple effects across organization]
3. [Question about cost of the problem]

### Need-Payoff (Let them articulate the value)
1. [Question about ideal outcome]
2. [Question about what success looks like]
3. [Question about value of solving this]

### 💪 Power Questions (Use Sparingly — These Accelerate Deals)
- "What happens if this doesn't get solved in the next 6 months?"
- "If you had unlimited budget, what would you fix first?"
- "Who else in the organization feels this pain?"
- "What would it take for this to become a priority?"

### 🤝 Rapport / Human Connection
- [Thoughtful question showing genuine interest in them as a person]

---

## 🗣️ Talking Points & Flow

### Opening (5 Minutes)
- Personal connection point: [Specific thing to mention]
- Confirm agenda and time
- Set expectation: "I'd like to ask questions to understand your situation first"

**Suggested Agenda (Share at Start)**:
> "[Contact name], I was thinking we could structure our conversation like this:
> 1. (5 min) Quick introductions and understanding your current situation
> 2. (20 min) Dive deeper into your challenges and priorities
> 3. (10 min) Share how we've helped similar organizations
> 4. (10 min) Discuss if and how we might work together
> Does that work for you, or would you like to adjust?"

### Discovery Phase (20–25 Minutes)

#### Theme 1: Current Situation
- What to explore: [Specific area]
- Signal to listen for: [What indicates opportunity]

#### Theme 2: Challenges & Pain
- What to explore: [Specific challenge area]
- Pain to validate: [Hypothesis to test]

#### Theme 3: Goals & Priorities
- What to explore: [Their objectives]
- Connection to make: [How we help]

### Value Connection (10 Minutes)
- Link discovery to value: [Specific connection to make]
- Case/example to share: [Relevant proof point]
- Check-in question: "Does this resonate with what you're experiencing?"

### Close (5 Minutes)
- Summarize key insights: [What you learned]
- Propose specific next step: [Exact action]
- Confirm stakeholders: [Who else should be involved]

---

## 🎯 Meeting Strategy & Next Steps

### If the Meeting Goes Well

| Recommended Next Step | Who to Involve | Timing | Say This |
|----------------------|----------------|--------|----------|
| [Specific action] | [Names + roles] | [Within X days] | "[Exact words to propose next step]" |

### If They Are Hesitant
- **Diagnose**: Ask "[Question to understand hesitation]"
- **Fallback**: Offer [Lower-commitment next step]
- **Keep door open**: "[Message to leave them with]"

### If They Are Not Ready
- **Nurture action**: [What to send/do to stay relevant]
- **Re-engagement trigger**: [Event or timing to reach out again]
- **Value to provide**: [Helpful content or insight to share]

---

## 👂 Buying Signals to Listen For

During the meeting, watch for these signals:

### 🟢 Strong Buying Signals (Push for Next Step)
These indicate high interest — ask for commitment:
- "When could you start?" / "What's your availability?"
- "Who else should be involved in this?"
- "How does your pricing work?"
- "Can you do [specific capability]?"
- They take notes, lean forward, ask detailed follow-up questions
- They share internal challenges openly
- They mention budget or timeline specifics

### 🟡 Interest Signals (Keep Nurturing)
These show engagement — provide more value:
- "That's interesting, tell me more"
- "How do others handle this?"
- They ask for case studies or references
- They compare you to alternatives
- They share some challenges but stay guarded

### 🔴 Warning Signals (Diagnose & Adjust)
These suggest obstacles — address directly:
- Short, closed answers without elaboration
- Frequent "yes, but..." responses
- Looking at phone, checking time, distracted
- "We've tried something like this before"
- Avoiding commitment to any next step
- Suddenly involving new stakeholders

**If You See Warning Signals**: Pause and ask: "I want to make sure I'm being helpful. Is there something specific on your mind, or should we adjust our focus?"

---

## 🔔 Last-Minute Check (5 Minutes Before)

### Quick Digital Scans
Open these links and scan for 30 seconds each:

| Check | Link/Search | What to Look For |
|-------|-------------|------------------|
| **LinkedIn** | [Contact's LinkedIn profile URL] | Recent posts, job changes, shared connections |
| **Company News** | Google: "[Company Name]" news | Last 7 days announcements, press releases |
| **Google Alert** | "[Contact Name]" "[Company Name]" | Recent mentions, interviews, quotes |

### Mental Prep (Say Out Loud)
- [ ] **Opening line**: "[Your prepared opener]"
- [ ] **Top 3 questions**: [Q1], [Q2], [Q3]
- [ ] **The ONE Thing**: [Single most important insight to remember]
- [ ] **Proposed next step**: "[Exact words for next step]"

### Final Checks
- [ ] Camera/audio tested (if video call)
- [ ] Notes app open for capturing insights
- [ ] Calendar visible for scheduling next step
- [ ] Water nearby, phone on silent

---

## ✅ Full Preparation Checklist

- [ ] Research brief reviewed and key points memorized
- [ ] Contact profiles understood — know their priorities
- [ ] Top 3 discovery questions prepared
- [ ] MEDDIC gaps identified — know what to uncover
- [ ] One relevant case study or example ready
- [ ] Competitive positioning clear in your mind
- [ ] Next step options prepared (Plan A, B, C)
- [ ] Calendar open for next 2 weeks
- [ ] Opening line mentally rehearsed

---

RULES:
- Be specific to this prospect and these contacts – no generic templates.
- Always anchor in THEIR value, not our product features.
- Quantify impact wherever possible (time, money, risk).
- Write for a senior B2B sales professional who values clarity, depth, and strategic insight.
- If context is missing, note it as "[TO DISCOVER]" rather than guessing.
- Keep total brief under 1800 words (excluding tables).

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

## ⚡ 3-MINUTE EXECUTIVE SUMMARY

**Read this if you only have 3 minutes before the demo.**

### 🎯 The ONE Thing
If you remember nothing else from this brief, remember this:
> [The single most important insight or outcome that will make this demo successful]

### Quick Facts
| Element | Details |
|---------|---------|
| **Company** | [Name] — [Industry, context] |
| **Audience** | [Names + Roles] — [Technical / Executive / Mixed] |
| **Stage** | 🟢 Ready to Buy / 🟡 Evaluating / 🔴 Early Stage |
| **Their #1 Priority** | [What they most need to see solved] |
| **Show-Stopper Risk** | [Feature gap or objection that could kill the deal] |

### Your 3 Must-Do's
1. **Show**: [The feature/workflow that addresses their #1 pain]
2. **Connect**: [Link demo to their specific situation with "[their words]"]
3. **Advance**: [The specific next step to propose]

### Key Demo Moment
> When you show [feature], say: "[Ready-to-use talking point that connects to their pain]"

### Most Likely Question & Your Answer
> **Q**: "[Anticipated tough question]"
> **A**: "[Your prepared response]"

---

## 📋 In One Sentence

[Who you're demoing to] + [What they need to see] + [What must happen to progress]

---

## 📊 At a Glance

| Aspect | Assessment |
|--------|------------|
| **Demo Readiness** | 🟢 Ready to Buy / 🟡 Evaluating / 🔴 Early Stage — [rationale] |
| **Audience Profile** | Technical / Executive / Mixed — [who's in the room] |
| **Complexity** | Simple / Medium / Complex — [customization needed] |
| **Duration** | [30 / 45 / 60 min] |
| **Key Risk** | [The single factor most likely to derail this demo] |

---

## 📊 MEDDIC Status Check

| Element | Status | Implication for Demo |
|---------|--------|---------------------|
| **Metrics** | 🔴/🟡/🟢 | [Show ROI data if unclear, validate if known] |
| **Economic Buyer** | In room? Yes/No | [Adjust depth accordingly] |
| **Decision Criteria** | [Known criteria] | [Which demo segments address each] |
| **Champion** | [Name] | [Give them ammunition to sell internally] |

---

## 🎯 Demo Objectives

### Primary Goal (Must Achieve)
[One essential outcome — reaction, statement, or commitment]

### Success Signals to Watch For
- [Positive reaction 1: leaning in, nodding, taking notes]
- [Positive statement: "This would solve our problem with..."]
- [Commitment: "Can we see this with our data?"]

---

## 🔗 Discovery → Demo Connection

### Pain Points to Address

| Their Pain (Their Words) | What to Show | Say This |
|--------------------------|--------------|----------|
| "[Quote from discovery about pain 1]" | [Feature/workflow] | "[Talking point connecting feature to pain]" |
| "[Quote about pain 2]" | [Feature/workflow] | "[Talking point]" |
| "[Quote about goal]" | [Outcome to demonstrate] | "[Talking point]" |

### Echo Their Words
During the demo, reference these exact phrases they used:
- "[Their phrase 1]" — use when showing [feature]
- "[Their phrase 2]" — use when discussing [outcome]

---

## 💡 Value Translation (So What?)

| We Show | They Get | Quantified Impact |
|---------|----------|-------------------|
| [Feature 1] | [Outcome for them] | [X hours saved / €Y value / Z% improvement] |
| [Feature 2] | [Outcome for them] | [Quantified impact] |
| [Feature 3] | [Outcome for them] | [Quantified impact] |

---

## ⚔️ Competitive Positioning

### If Competitor Comes Up

| Competitor | Their Claim | Our Counter | Don't Say |
|------------|-------------|-------------|-----------|
| [Name] | "[Feature they'll mention]" | "[Our differentiation]" | [Avoid this] |
| Status Quo | "We've always done it this way" | "[Cost of inaction]" | [Don't dismiss] |

### Our Unfair Advantage to Highlight
[The one thing to emphasize that competitors can't match]

---

## 👤 Audience-Specific Demo Strategy

For each attendee:

### [Name] — [Role]

| Aspect | Details |
|--------|---------|
| **Authority** | 🟢 DM / 🔵 Inf / 🟡 GK / ⚪ User |
| **What They Care About** | [Their specific priorities] |
| **Demo Depth** | Technical / Strategic / Hands-on |
| **Likely Question** | "[What they'll ask]" |
| **Your Answer** | "[Prepared response]" |

**Their Demo Moment**: When showing [feature], address [Name] directly: "[What to say]"

---

## 👥 DMU Dynamics in the Room

| Name | Role | Stance | How to Engage |
|------|------|--------|---------------|
| [Name] | [Function] | Champion / Neutral / Skeptic | [Strategy] |

### Demo Balance Strategy
- **Impress first**: [Key person] — show [capability]
- **Win over**: [Skeptic] — address [concern]
- **Avoid**: [Action that could alienate someone]

---

## ⚠️ Demo Pitfalls & Risk Mitigation

### Features to Handle Carefully

| Feature/Topic | Why Risky | How to Navigate |
|---------------|-----------|-----------------|
| [Feature 1] | [May not match their process] | [Framing to use] |
| [Feature 2] | [Competitor is stronger here] | [Redirect strategy] |

### Anticipated Objections — Deep Dive

**Objection 1**: "[Most likely demo objection]"

| Element | What to Say |
|---------|-------------|
| **Feel** | "I understand that concern completely." |
| **Felt** | "Other [similar role] felt the same when they first saw this." |
| **Found** | "What they found after [timeframe] was [specific outcome]." |
| **Proof** | "[Client example or data point]" |
| **Bridge** | "Would you like to see how [feature] handles that?" |

**Objection 2**: "[Second likely objection]"

| Element | What to Say |
|---------|-------------|
| **Feel** | "[Acknowledgment]" |
| **Felt** | "[Normalization]" |
| **Found** | "[Transformation]" |
| **Proof** | "[Evidence]" |
| **Bridge** | "[Transition to next demo segment]" |

### Technical Backup Plan
- If [issue] happens: [What to do/say]
- If they ask about [unsupported feature]: "[Response]"

---

## 🤔 What If They Ask...

| Question | Why They Ask | Your Response |
|----------|--------------|---------------|
| "Can we customize this?" | Fit concerns | "Absolutely. Let me show you the configuration options, and we can discuss specific customizations in a follow-up." |
| "How does this integrate with [system]?" | Technical feasibility | "We have [native/API] integration with [system]. I can show you that, or arrange a technical deep-dive." |
| "What's the implementation timeline?" | Planning | "Typical implementation is [X-Y weeks]. For your scope, I'd estimate [specific timeframe]." |
| "Who else uses this?" | Social proof | "[Similar company] in [their industry] uses this for [use case]. I can connect you with them if helpful." |

---

## 🎬 Demo Flow

### Opening (5 Minutes)
- **Recap**: "Last time we discussed [pain point]. Today I'll show you how we solve that."
- **Confirm priorities**: "You mentioned [X, Y, Z] were most important. Still accurate?"
- **Set expectations**: "I'll focus on those three areas. Feel free to ask questions anytime."

**Suggested Agenda (Share at Start)**:
> "I was thinking we could structure this demo as follows:
> 1. (5 min) Quick recap of what we discussed and confirm your priorities
> 2. (25 min) Show you the three areas most relevant to your situation
> 3. (10 min) Q&A and address any concerns
> 4. (5 min) Discuss next steps if this looks like a fit
> Does that work, or would you prefer a different focus?"

### Core Demo (25–30 Minutes)

#### Segment 1: [Pain Point 1]
- **Show**: [Specific feature/workflow]
- **Connect**: "[Their words]" → "[Our solution]"
- **Talking point**: "[Key message]"
- **Check-in**: "Does this match how your team would use it?"

#### Segment 2: [Pain Point 2]
- **Show**: [Specific feature/workflow]
- **Connect**: "[Their words]" → "[Our solution]"
- **Talking point**: "[Key message]"
- **Check-in**: "Is this the kind of result you're looking for?"

#### Segment 3: [Pain Point 3 / Wow Moment]
- **Show**: [Differentiating capability]
- **Connect**: "[Unique value]"
- **Talking point**: "[Memorable statement]"
- **Check-in**: "How does this compare to your current approach?"

### Q&A (10 Minutes)
- Anticipated questions: [Top 3 with prepared answers]
- If stumped: "Great question. Let me get you a detailed answer after this call."

### Close (5 Minutes)
- **Summarize value**: "Based on what I showed you, [key benefit 1, 2, 3]"
- **Next step**: "[Specific proposal]"
- **Ask**: "[Closing question to confirm interest]"

---

## 💬 Key Messages & Proof Points

### Value Statements (Say These)
1. "[Statement connecting to their #1 priority]"
2. "[Differentiation from current approach]"
3. "[Quantified outcome or ROI]"

### Proof Points to Share
- **Case study**: [Company similar to them] achieved [result]
- **Metric**: [Specific number that resonates]
- **Reference**: [Name/company they can contact if needed]

---

## 🎯 Meeting Strategy & Next Steps

### If the Demo Goes Well

| Next Step | Who to Involve | Timing | Say This |
|-----------|----------------|--------|----------|
| [Trial / POC / Proposal] | [Names + roles] | [Within X days] | "[Exact words]" |

### If They Have Concerns
- **Acknowledge**: "[Response]"
- **Fallback**: [Lower-commitment option]

### If They're Not Ready
- **Leave-behind**: [What to send]
- **Re-engagement**: [When/how to follow up]

---

## 👂 Buying Signals During Demo

### 🟢 Strong Buying Signals (Push for Trial/POC)
- "Can we try this with our data?"
- "When could we get started?"
- "Who else should see this?"
- They take screenshots or notes
- They ask detailed "how would we..." questions
- They share specific use cases from their work

### 🟡 Interest Signals (Provide More Proof)
- "That's impressive" / Nodding and leaning in
- "How did [other company] implement this?"
- Comparing features to current solution
- Asking about training and support

### 🔴 Warning Signals (Pause and Diagnose)
- Looking at phone, multitasking
- Short responses, no follow-up questions
- "We tried something similar before"
- Focus only on limitations or edge cases

**If Warning Signals Appear**: "I want to make sure I'm showing you what's most valuable. Should we adjust our focus, or is there a concern I should address?"

---

## 🔔 Last-Minute Check (5 Minutes Before)

### Technical Prep
- [ ] Demo environment tested and loaded
- [ ] Sample data/scenarios ready
- [ ] Backup browser/device available
- [ ] Screen sharing tested

### Quick Digital Scans

| Check | What to Look For |
|-------|------------------|
| **LinkedIn** | [Contact Name(s)] — any recent posts about [topic]? |
| **Company News** | Any announcements since discovery call? |

### Mental Prep
- [ ] Opening recap: "Last time we discussed [pain point]..."
- [ ] Top 3 demo moments mapped to their pain
- [ ] Proposed next step ready: "[Trial/POC proposal]"

---

## ✅ Full Preparation Checklist

- [ ] Discovery notes reviewed — know their pain points
- [ ] Demo environment tested and clean
- [ ] Attendee priorities confirmed
- [ ] Pain → Feature mapping prepared
- [ ] Three key messages ready
- [ ] Proof point/case study selected
- [ ] Objection responses prepared
- [ ] Next step options ready (Plan A, B, C)
- [ ] Calendar open for follow-up

---

RULES:
- Be specific to this prospect — no generic demo scripts.
- ALWAYS connect features to THEIR stated needs using THEIR words.
- Quantify value wherever possible (time, money, risk).
- Write for a senior B2B sales professional who values clarity and impact.
- If context is missing, note it as "[CONFIRM WITH PROSPECT]".
- Keep total brief under 1200 words (excluding tables).

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

## ⚡ 3-MINUTE EXECUTIVE SUMMARY

**Read this if you only have 3 minutes before the closing call.**

### 🎯 The ONE Thing
If you remember nothing else from this brief, remember this:
> [The single most critical action or insight that will determine whether this deal closes]

### Deal Snapshot
| Element | Details |
|---------|---------|
| **Deal Value** | [€ amount] |
| **Close Probability** | 🟢 High / 🟡 Medium / 🔴 Low |
| **Decision Maker** | [Name] — [Their stance: Champion/Neutral/Skeptic] |
| **Biggest Blocker** | [The one thing that could kill this deal] |
| **Your Ask Today** | [Specific commitment you're seeking] |

### Your 3 Must-Do's
1. **Confirm**: [Validate final decision criteria are met]
2. **Overcome**: [Address the #1 remaining objection]
3. **Close**: "[Exact words to ask for the business]"

### If They Push Back
> **They say**: "[Most likely objection]"
> **You say**: "[Your prepared response]"

### The Close Line (Say This)
> "[Direct, confident closing statement tailored to this deal]"

---

## 📋 In One Sentence

[The deal at stake] + [What's required to close today] + [The biggest factor that will determine success]

---

## 📊 At a Glance

| Aspect | Assessment |
|--------|------------|
| **Close Probability** | 🟢 High (>70%) / 🟡 Medium (40-70%) / 🔴 Low (<40%) — [rationale] |
| **Decision Stage** | Final Approval / Negotiation / Stalled — [where they are] |
| **Deal Value** | [€ amount] |
| **Expected Close Date** | [Date] |
| **Key Risk** | [The single factor most likely to derail this deal] |

---

## 📊 MEDDIC Final Status

| Element | Status | Evidence | Action if Incomplete |
|---------|--------|----------|---------------------|
| **Metrics** | 🟢 Quantified | [Their expected ROI/outcome] | [Validate numbers] |
| **Economic Buyer** | 🟢 Confirmed | [Name + proof of authority] | [Ensure they're aligned] |
| **Decision Criteria** | 🟢 Met | [How we satisfy each criterion] | [Confirm we're chosen] |
| **Decision Process** | 🟢 Clear | [Remaining steps to signature] | [Clarify timeline] |
| **Identified Pain** | 🟢 Urgent | [Pain + cost of inaction] | [Reinforce urgency] |
| **Champion** | 🟢 Active | [Name + their role in closing] | [Give them ammunition] |

**MEDDIC Gap to Close Today**: [Element] — ask: "[Question to fill gap]"

---

## 🎯 Closing Objectives

### Primary Goal (Must Achieve)
[Specific outcome: verbal yes, signed contract, start date confirmed, or clear path to signature]

### Success Signals
- **Verbal commitment**: "[What they would say]"
- **Action commitment**: "[What they would do]"
- **Timeline commitment**: "[Specific date locked]"

---

## 💰 Deal Summary

| Element | Details |
|---------|---------|
| **Deal Value** | [€ amount] |
| **Contract Term** | [Duration: 1 year, 3 years, etc.] |
| **Products/Services** | [What's included] |
| **Start Date** | [Expected go-live] |
| **Key Terms Agreed** | [Pricing, payment terms, SLAs] |
| **Outstanding Items** | [What's still open — be specific] |

### Value Already Agreed
They've acknowledged these benefits:
- "[Benefit 1 they confirmed]"
- "[Benefit 2 they confirmed]"
- "[Outcome they're excited about]"

---

## 💎 Value Reinforcement (Use If Needed)

### ROI to Echo
| Investment | Return | Timeframe |
|------------|--------|-----------|
| [Their cost] | [Quantified benefit] | [When they'll see it] |

### Their Words to Use
Quote them back to reinforce their own reasoning:
- "[Quote about their pain]"
- "[Quote about why they chose us]"
- "[Quote about expected outcome]"

### Cost of Inaction
If they delay, they lose: [Specific cost of waiting — time, money, competitive position]

---

## ⚔️ Competitive Final Check

| Competitor | Status | Our Counter | Don't Say |
|------------|--------|-------------|-----------|
| [Name / Status Quo] | [In play / Eliminated / Unknown] | [Our advantage to emphasize] | [Avoid this] |

**If Competitor Is Mentioned Today**: "[Prepared response]"

---

## 👤 Stakeholder Closing Status

For each decision maker:

### [Name] — [Role]

| Aspect | Status |
|--------|--------|
| **Authority** | 🟢 Final Sign-off / 🔵 Recommender / 🟡 Approver |
| **Current Stance** | Champion / Supportive / Neutral / Skeptical |
| **What Closes Them** | [The one thing that tips them to yes] |
| **Remaining Concern** | [What might still make them hesitate] |
| **Your Approach** | [How to engage them in this meeting] |

**To Secure Their Yes, Say**: "[Specific statement or question for this person]"

---

## 👥 DMU Final Check

| Name | Role | Authority | Stance | What They Must Do |
|------|------|-----------|--------|-------------------|
| [Name] | [Function] | 🟢 Final / 🔵 Rec / 🟡 Approve | [Stance] | [Action required] |

### Decision Dynamics
- **Who signs**: [Name] — trigger: [What prompts signature]
- **Who can block**: [Name] — risk: [Their potential objection]
- **Process remaining**: [Steps from today to signed contract]

---

## ⚠️ Risk Mitigation

### Deal-Killers & Countermeasures

| Risk | Likelihood | Your Mitigation |
|------|------------|-----------------|
| [Risk 1] | High / Medium / Low | "[Proactive statement to neutralize]" |
| [Risk 2] | High / Medium / Low | "[Response if it comes up]" |

### Last-Minute Objections — Deep Dive

**Objection: "We need more time"**

| Element | What to Say |
|---------|-------------|
| **Feel** | "I completely understand. This is a significant decision." |
| **Felt** | "Many clients felt the same way at this stage." |
| **Found** | "What they found was that waiting [cost them X / delayed Y]." |
| **Proof** | "[Client] initially wanted to wait, but by starting in [month], they achieved [result] by [date]." |
| **Bridge** | "What specifically would you need to feel confident moving forward today?" |

**Objection: "The price is too high"**

| Element | What to Say |
|---------|-------------|
| **Feel** | "I appreciate you being direct about that." |
| **Felt** | "Other [similar companies] initially felt the same way." |
| **Found** | "What they found was that the ROI of [X] justified the investment within [timeframe]." |
| **Proof** | "[Client] saw [specific ROI metric] within [months]." |
| **Bridge** | "If we could demonstrate that same ROI for you, would the investment make sense?" |

---

## 🤔 What If They Ask...

| Question | Why They Ask | Your Response |
|----------|--------------|---------------|
| "Can we get a discount?" | Budget pressure | "Let's discuss value first. What specific outcomes would make this investment worthwhile? Then we can explore options." |
| "What if we need to cancel?" | Risk mitigation | "Our contract includes [exit terms]. We're confident you won't need them because [reason]." |
| "Can we start smaller?" | Risk reduction | "Absolutely. We can begin with [smaller scope] and expand as you see results. Here's what that would look like..." |
| "What happens after we sign?" | Implementation concerns | "Great question. [Name] from our implementation team will contact you within [X days]. Here's the typical timeline..." |

---

## 🗣️ Closing Conversation Flow

### Opening (5 Minutes)
- **Acknowledge the journey**: "We've covered a lot of ground together..."
- **Confirm current position**: "Last we spoke, you mentioned [readiness signal]. Is that still the case?"
- **State purpose directly**: "Today I'd like to finalize our agreement and discuss next steps."

**Suggested Agenda (Share at Start)**:
> "I thought we could structure our conversation as follows:
> 1. (5 min) Confirm where we stand and any changes since we last spoke
> 2. (5 min) Recap the value and ROI we've discussed
> 3. (10 min) Address any remaining questions or concerns
> 4. (10 min) Finalize the agreement and discuss next steps
> Does that work for you?"

### Value Recap (5 Minutes)
- Summarize their key pain: "[Pain they expressed]"
- Connect to solution: "[How we solve it]"
- Quantify value: "[ROI or benefit they'll see]"
- Use their words: "As you said, [their quote]"

### Address Final Concerns (10 Minutes)
- **Proactively surface**: "Before we proceed, is there anything we haven't addressed?"
- **Handle objections**: Use prepared responses
- **Confirm criteria met**: "Does this meet all your requirements?"

### The Ask (5 Minutes)
- **Direct close**: "[Confident closing statement]"
- **Specific proposal**: "Here's what I suggest as next steps..."
- **Timeline lock**: "Can we start implementation on [date]?"

### If They Say YES
- Express genuine appreciation (not surprise)
- Confirm immediate next steps: "Great. Here's what happens now..."
- Introduce implementation: "[Next person/process]"
- Lock specific dates: "[Onboarding call, kickoff meeting]"

### If They Hesitate
- **Diagnose**: "Help me understand what's holding you back."
- **Isolate**: "If we solve [concern], are you ready to move forward?"
- **Resolve or defer**: "[Solution or fallback step]"
- **Lock next action**: "Let's schedule [follow-up] for [date]."

---

## 🤝 Negotiation Readiness

### Our Position
| Element | Ideal | Acceptable | Walk-Away |
|---------|-------|------------|-----------|
| Price | [€ amount] | [€ amount] | [€ minimum] |
| Payment Terms | [Preferred] | [Acceptable] | [Minimum] |
| Contract Length | [Ideal] | [Acceptable] | [Minimum] |
| Start Date | [Ideal] | [Acceptable] | [Latest] |

### Concessions We Can Offer
| Concession | Value to Them | Cost to Us | Ask in Return |
|------------|---------------|------------|---------------|
| [Concession 1] | [Value] | [Cost] | "[What to ask for]" |
| [Concession 2] | [Value] | [Cost] | "[What to ask for]" |

### Red Lines (Do Not Cross)
- [What we cannot compromise on — price floor, terms, etc.]

---

## 🎯 Meeting Strategy & Post-Meeting

### If They Close Today
- **Immediate**: [Confirm contract signing process]
- **This week**: [Kickoff call, implementation start]
- **Introduce**: [CS, Implementation, Onboarding team]
- **Send**: [Welcome email, next steps document]

### If They Need More Time
- **Acceptable delay**: [Maximum X days]
- **Requirements**: "For me to hold this [pricing/terms], I need [commitment] by [date]"
- **Next action**: [Specific follow-up locked]

### If They Go Cold
- **Final attempt**: "[Last-resort statement to create urgency]"
- **Walk-away criteria**: [When to stop pursuing]
- **Re-engagement trigger**: "[Future event that might restart conversation]"

---

## 👂 Closing Signals to Listen For

### 🟢 Ready to Close (Ask for Signature)
- "When can we start?"
- "What's the next step to formalize this?"
- "Let me get [approver] on a call"
- They're discussing implementation details
- They ask about onboarding timeline
- They mention internal communication about the decision

### 🟡 Almost Ready (Address Final Concern)
- "I just need to confirm one thing..."
- "If we could [adjust X], we'd be ready"
- They're comparing final terms
- They want one more reference or proof point

### 🔴 Not Ready (Diagnose & Decide)
- "We need to revisit internally"
- "The timing isn't right"
- They avoid committing to any date
- New objections emerge that weren't raised before
- Key stakeholder suddenly unavailable

**If Red Signals Appear**: "I sense some hesitation. Can we talk openly about what's holding this back? I'd rather understand now than miss something important."

---

## 🔔 Last-Minute Check (5 Minutes Before)

### Documents Ready
- [ ] Contract/proposal loaded and ready to share
- [ ] Pricing summary accessible
- [ ] Implementation timeline document ready

### Quick Digital Scans

| Check | What to Look For |
|-------|------------------|
| **LinkedIn** | Any posts from [Decision Maker] about priorities or changes? |
| **Company News** | Any announcements that might affect timing? |
| **Competitor** | Any [Competitor] news that might be raised? |

### Mental Prep
- [ ] Closing statement rehearsed: "[Your exact words]"
- [ ] Negotiation boundaries clear (ideal / acceptable / walk-away)
- [ ] Fallback plan ready if they hesitate
- [ ] Calendar open for implementation kickoff date

---

## ✅ Full Preparation Checklist

- [ ] Full deal terms understood and ready to confirm
- [ ] All decision makers' positions known
- [ ] Contract/proposal finalized and ready
- [ ] Objection responses prepared and rehearsed
- [ ] Negotiation boundaries approved internally
- [ ] Implementation timeline ready to discuss
- [ ] Champion prepped and aligned
- [ ] Closing statement prepared
- [ ] Next steps mapped out for all scenarios

---

RULES:
- Be specific to THIS deal and THESE stakeholders – no generic closing scripts.
- Reinforce THEIR value, not our urgency.
- Be confident and direct without being pushy.
- Quantify everything: time, money, risk, opportunity cost.
- Write for a senior B2B sales professional closing significant deals.
- If context is missing, note it as "[MUST CONFIRM]".
- Keep total brief under 1200 words (excluding tables).

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

## ⚡ 3-MINUTE EXECUTIVE SUMMARY

**Read this if you only have 3 minutes before the meeting.**

### 🎯 The ONE Thing
If you remember nothing else from this brief, remember this:
> [The single most critical insight or action to re-establish momentum and advance the deal]

### Quick Status
| Element | Details |
|---------|---------|
| **Last Contact** | [Date + what was discussed] |
| **Momentum** | 🟢 Hot / 🟡 Warm / 🔴 Cold |
| **Open Items** | [X items — most critical: Y] |
| **Their Current Priority** | [What's on their mind now] |
| **Risk** | [What could stall this deal] |

### Your 3 Must-Do's
1. **Reconnect**: Reference [specific point from last meeting] to show continuity
2. **Update**: Share [relevant news/insight/case study]
3. **Advance**: Lock [specific next step] before ending the call

### Opening Line (Use This)
> "[Personalized opener that shows you remember and care]"

### The Ask
> "[Specific commitment or next step to propose]"

---

## 📋 In One Sentence

[What was previously discussed] + [What has changed since] + [What must happen today to progress]

---

## 📊 At a Glance

| Aspect | Assessment |
|--------|------------|
| **Momentum** | 🟢 Hot / 🟡 Warm / 🔴 Cold — [rationale] |
| **Last Contact** | [Date + type of interaction] |
| **Days Since Contact** | [X days] |
| **Open Items** | [Number + most critical item] |
| **Risk Level** | Low / Medium / High — [key risk] |
| **Approach** | Push / Nurture / Re-qualify |

---

## 📊 MEDDIC Progress Check

| Element | Last Status | Current Status | Action Needed |
|---------|-------------|----------------|---------------|
| **Metrics** | [Previous] | [Now] | [What to confirm/discover] |
| **Economic Buyer** | [Previous] | [Now] | [Action] |
| **Decision Process** | [Previous] | [Now] | [Action] |
| **Champion** | [Previous] | [Now] | [Action] |

**MEDDIC Gap to Address**: [Which element needs attention this meeting]

---

## 🎯 Meeting Objectives

### Primary Goal (Must Achieve)
[One essential outcome to meaningfully progress the opportunity]

### Secondary Goals
- [Secondary goal 1]
- [Secondary goal 2]

### Success Signals
- [Observable outcome: what they say or do]
- [Commitment: specific next step locked]

---

## 🔙 Previous Meeting Recap

### What We Discussed

| Topic | Their Position | What We Committed | Status |
|-------|----------------|-------------------|--------|
| [Topic 1] | "[What they said]" | [Our commitment] | ✅ / ⏳ / ❌ |
| [Topic 2] | "[What they said]" | [Our commitment] | ✅ / ⏳ / ❌ |

### Key Takeaways to Reference
- They said: "[Important quote to echo back]"
- They wanted: [Outcome or action]
- We promised: [What we committed to deliver]

### Open Action Items

| Item | Owner | Status | Impact |
|------|-------|--------|--------|
| [Item 1] | Us / Them | ✅ Done / ⏳ Pending / ❌ Overdue | [Why it matters] |
| [Item 2] | Us / Them | ✅ Done / ⏳ Pending / ❌ Overdue | [Why it matters] |

### Unresolved Questions
- [Question they asked that we need to address]
- [Concern that wasn't fully resolved]

---

## 🌍 What's Changed Since Last Contact

### At the Prospect

| Development | Impact on Our Deal | Your Response |
|-------------|-------------------|---------------|
| [News/announcement/change] | [How it affects opportunity] | [How to acknowledge or leverage] |
| [Personnel/restructure] | [Impact] | [Response] |

### At Our End
- [New feature, case study, pricing] — use to add value
- [Resource update] — if relevant

### Market/Competitive
- [Industry development] — if relevant to them
- [Competitor movement] — if we need to address

---

## 💡 Value to Bring Today

### Relevant Update to Share

| What | Why It Matters to Them | How to Present |
|------|------------------------|----------------|
| [New case study / feature / insight] | [Connects to their priority] | "[Talking point]" |

### Value Translation

| Their Situation | Our Value | Quantified Impact |
|-----------------|-----------|-------------------|
| [Pain they mentioned] | [How we help] | [Time/money/risk saved] |

---

## ⚔️ Competitive Status

| Competitor | Current Status | Our Counter |
|------------|----------------|-------------|
| [Name / Status Quo] | [In play / Eliminated / Unknown] | [How to position] |

**If Competitor Comes Up**: "[Prepared response]"

---

## 👤 Contact Status Update

For each attendee:

### [Name] — [Role]

| Aspect | Status |
|--------|--------|
| **Engagement** | 🟢 Active / 🟡 Passive / 🔴 Disengaged |
| **Recent Activity** | [LinkedIn posts, news, company updates] |
| **Current Priorities** | [What's likely on their mind now] |
| **Stance Shift** | More positive / Same / More cautious |

**Re-engagement Approach**
- Lead with: [Topic or insight that will resonate now]
- Avoid: [Topic that could derail]

**Personalized Opening for [Name]**
> "[Opener based on their recent activity or previous conversation]"

---

## ⏱️ Momentum Analysis

**Momentum Score**: 🟢 / 🟡 / 🔴

### Positive Signals
- [Signal 1 — engagement, response time, internal advocacy]
- [Signal 2 — budget confirmation, timeline movement]

### Warning Signs
- [Signal 1 — delayed responses, stakeholder changes]
- [Signal 2 — competitor activity, priority shift]

### Cost of Waiting
If we don't advance today: [What's at risk — timing, competitive, budget cycle]

---

## ⚠️ Sensitivities & Risk Mitigation

### Changed Circumstances to Acknowledge
- [What's different that we must recognize]
- [Sensitivity to handle carefully]

### Potential Objections — Deep Dive

**Objection: "Things have changed internally"**

| Element | What to Say |
|---------|-------------|
| **Feel** | "I appreciate you sharing that. Change is constant in organizations." |
| **Felt** | "Other clients have experienced similar shifts mid-process." |
| **Found** | "What they found was that [our solution] actually helped them navigate the change more effectively." |
| **Proof** | "[Client example] went through a restructure and still saw [result]." |
| **Bridge** | "What specifically has changed, and how might that affect what we discussed?" |

**Objection: "We need to revisit priorities"**

| Element | What to Say |
|---------|-------------|
| **Feel** | "That makes complete sense." |
| **Felt** | "Many organizations go through priority reviews." |
| **Found** | "What we've found is that our solution often supports multiple priorities because [reason]." |
| **Proof** | "[Evidence from similar client]" |
| **Bridge** | "Which priorities are rising in importance? Let me see if we can support those." |

### Topics to Avoid
- [Subject that could derail the conversation]

---

## 🤔 What If They Ask...

| Question | Why They Ask | Your Response |
|----------|--------------|---------------|
| "Why are you following up now?" | Testing your intentions | "I wanted to check in on [specific item we discussed] and share a relevant update I thought you'd find valuable." |
| "Has anything changed on your end?" | Exploring new leverage | "Yes, [relevant update]. I thought it might be interesting for your situation because..." |
| "We're talking to others now" | Creating competition | "That's smart. What criteria are most important as you evaluate? I want to make sure I'm helping you compare fairly." |
| "Can you send me a summary?" | Delaying or genuinely useful | "Absolutely. I'll send that today. When would be a good time to discuss it together?" |

---

## 🗣️ Conversation Flow

### Opening (5 Minutes)
- **Acknowledge gap**: "It's been [X weeks] since we last spoke. How have things been?"
- **Show continuity**: "Last time, you mentioned [specific point]. I wanted to follow up on that."
- **Confirm agenda**: "I have about [X] minutes. Here's what I thought we could cover..."

**Suggested Agenda (Share at Start)**:
> "I thought we could use our time as follows:
> 1. (5 min) Quick check-in on what's happened since we last spoke
> 2. (10 min) Status update on the items we discussed
> 3. (10 min) Share something relevant I've come across
> 4. (10 min) Discuss next steps and timeline
> Does that work, or is there something more pressing?"

### Status Update (10 Minutes)
- **Their side**: "What's happened since we last spoke?"
- **Our side**: "[Update on open items we owed them]"
- **Reality check**: "Are your priorities or timeline still the same?"

### Value Reinforcement (10 Minutes)
- **Share update**: "[Case study, feature, or insight]"
- **Connect to them**: "I thought of you because [connection to their priority]"
- **Check resonance**: "Does this still align with what you're trying to achieve?"

### Path Forward (10 Minutes)
- **Remaining steps**: "Based on what we've discussed, here's what I see as next steps..."
- **Timeline**: "What's a realistic timeline on your end?"
- **Stakeholders**: "Is there anyone else we should involve?"

### Close (5 Minutes)
- **Summarize**: "So we've agreed that [key points]..."
- **Lock next step**: "[Specific action with date]"
- **Express commitment**: "I'm here to help you succeed with this."

---

## ❓ Questions to Ask

### Progress Check
- "What's happened since we last spoke?"
- "Have your priorities or timeline changed?"
- "Where does this sit in your current focus areas?"

### Blocker Discovery
- "Is there anything holding this up internally?"
- "Are there new stakeholders we should involve?"
- "What would need to happen for you to move forward?"

### Commitment
- "What would help you make a decision?"
- "Can we lock in [specific next step] for [date]?"

### Power Question
- "If nothing changes in the next 6 months, what's the cost to your team?"

---

## 🎯 Meeting Strategy & Next Steps

### If Momentum Is Strong

| Next Step | Who to Involve | Timing | Say This |
|-----------|----------------|--------|----------|
| [Specific action] | [Names] | [Within X days] | "[Exact words]" |

### If They've Gone Quiet
- **Re-qualify gently**: "I want to make sure I'm not wasting your time. Is this still a priority?"
- **Offer value**: "[Insight or help without pressure]"
- **Lower commitment option**: "[Smaller next step]"

### If Circumstances Have Changed
- **Acknowledge**: "Things change. Help me understand where things stand now."
- **Adapt**: "[New value proposition or approach]"
- **Reset expectations**: "[Adjusted timeline or scope]"

---

## 👂 Re-engagement Signals to Listen For

### 🟢 Momentum Restored (Push Forward)
- They share new developments or internal changes
- They ask about timeline or next steps
- They mention speaking with colleagues about our solution
- Higher engagement than before (longer responses, more questions)
- They apologize for the delay and explain why

### 🟡 Interested but Stuck (Diagnose Blockers)
- "We're still figuring things out internally"
- They want to meet but can't commit to action
- Positive tone but vague on specifics
- They ask for updated materials or proposals

### 🔴 Dead or Dying (Qualify Out or Reset)
- Short, delayed responses
- Avoiding meetings or rescheduling repeatedly
- "Not a priority right now" without alternative timing
- Key champion has left or changed role

**If Red Signals Appear**: "I want to be respectful of your time. Would it make more sense to reconnect in [timeframe], or has this moved off the table?"

---

## 🔔 Last-Minute Check (5 Minutes Before)

### Quick Digital Scans

| Check | What to Look For |
|-------|------------------|
| **LinkedIn** | [Contact Name(s)] — any posts, job changes, or activity since last contact? |
| **Company News** | [Company] news last 7 days — announcements, press releases, leadership changes? |
| **Previous Notes** | Review what was discussed and promised last time |

### Mental Prep
- [ ] Opening line: "It's been [X] since we last spoke. Last time, you mentioned..."
- [ ] Open items status clear (what you delivered, what's pending)
- [ ] Value update ready to share
- [ ] Next step proposal ready
- [ ] Calendar open for follow-up dates

---

## ✅ Full Preparation Checklist

- [ ] Previous meeting notes reviewed — know what was discussed
- [ ] Open items status confirmed — what you delivered, what's pending
- [ ] New developments researched — their news, industry changes
- [ ] Contact LinkedIn profiles checked for recent activity
- [ ] Relevant update to share prepared — case study, insight, feature
- [ ] MEDDIC gaps identified — what to uncover
- [ ] Next step options prepared (Plan A, B, C)
- [ ] Calendar open for follow-up

---

RULES:
- Be specific to this prospect and the previous conversation – show continuity.
- Always reference what was discussed before — never start cold.
- Be warm and persistent without desperation.
- Bring value every time — never just "checking in".
- Write for a senior B2B sales professional who values relationship continuity.
- If context is missing, note it as "[TO CONFIRM]".
- Keep total brief under 1100 words (excluding tables).

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

## ⚡ 3-MINUTE EXECUTIVE SUMMARY

**Read this if you only have 3 minutes before the meeting.**

### 🎯 The ONE Thing
If you remember nothing else from this brief, remember this:
> [The single most critical insight or action for this meeting]

### Quick Facts
| Element | Details |
|---------|---------|
| **Company** | [Name] — [Context] |
| **Contacts** | [Name(s) + Role(s)] |
| **Meeting Purpose** | [Why this meeting is happening] |
| **Their Priority** | [What matters most to them right now] |
| **Key Risk** | [What could go wrong] |

### Your 3 Must-Do's
1. **Understand**: [What to discover or confirm]
2. **Deliver**: [Value to provide]
3. **Advance**: [Next step to lock]

### Opening Line (Use This)
> "[Ready-to-use opener personalized to the contact and situation]"

### Top Question to Ask
> "[Most important question for this meeting]"

---

## 📋 In One Sentence

[Who you're meeting] + [Why this matters] + [What you must achieve]

---

## 📊 At a Glance

| Aspect | Assessment |
|--------|------------|
| **Meeting Type** | Relationship / Technical / Strategic / Operational |
| **Priority** | High / Medium / Low — [rationale] |
| **Stakeholder Level** | Executive / Manager / Practitioner |
| **Duration** | [30 / 45 / 60 min] |
| **Key Risk** | [The single factor most likely to derail this meeting] |

---

## 🎯 Meeting Objectives

### Primary Goal (Must Achieve)
[One essential outcome required from this meeting]

### Secondary Goals
- [Secondary goal 1]
- [Secondary goal 2]

### Success Signals
- [Observable outcome: what they say or do]
- [Commitment: action or next step]

---

## 🌍 Context & Relevance

### What's Happening in Their World

| Development | Impact on Them | Relevance to Us |
|-------------|----------------|-----------------|
| [Trend/change 1] | [Effect] | [How we connect] |
| [Trend/change 2] | [Effect] | [How we connect] |

### Why This Matters Now
[2-3 sentences on timing and situational relevance for THEM]

---

## 💡 Value Translation

| Our Offering | Their Need | Concrete Benefit |
|--------------|------------|------------------|
| [What we provide] | [Their pain/goal] | [Quantified outcome] |

---

## 👤 Personal Relevance Per Contact

For each attendee:

### [Name] — [Role]

| Aspect | Details |
|--------|---------|
| **Authority** | 🟢 Decision Maker / 🔵 Influencer / 🟡 Gatekeeper / ⚪ User |
| **Communication Style** | Formal / Informal / Technical / Strategic |
| **Likely Priorities** | [What matters most to this person] |
| **Personal Stake** | [What they personally gain or avoid] |

**How We Help Them**
- [Specific value for their situation]

**Tailored Opening**
> "[Personalized opener for this person]"

**Approach Strategy**
- Engage via: [Technical depth / Business outcomes / Relationship]
- Avoid: [Topic or approach that won't resonate]

---

## ⚠️ Warnings & Sensitivities

### Topics to Handle Carefully

| Topic | Why Sensitive | How to Navigate |
|-------|---------------|-----------------|
| [Topic 1] | [Reason] | [Approach] |

### Potential Objections — Deep Dive

**Objection 1**: "[Most likely objection]"

| Element | What to Say |
|---------|-------------|
| **Feel** | "I completely understand that concern." |
| **Felt** | "Others in your position have felt similarly." |
| **Found** | "What they found was [specific outcome that resolved the concern]." |
| **Proof** | "[Client example or data point]" |
| **Bridge** | "Would it help if [offer to address]?" |

### Points of Attention
- [Anything unusual to be aware of]
- [Recent changes that might affect the conversation]

---

## 🤔 What If They Ask...

| Question | Why They Ask | Your Response |
|----------|--------------|---------------|
| "What are you looking to achieve today?" | Testing your preparation | "I wanted to [specific goal] and understand [their priority]. What would make this meeting valuable for you?" |
| "Who else is involved on your side?" | Evaluating our commitment | "Depending on what we discuss, I can involve [relevant expert]. For now, I wanted to have an initial conversation to understand your needs." |
| "What's different about your approach?" | Benchmarking | "[Concise differentiator] — but more importantly, I'd like to understand what you're looking for in a partner." |

---

## 🗣️ Conversation Flow

### Opening (5 Minutes)
- [Personalized opener]
- Confirm agenda and time
- Set expectations

**Suggested Agenda (Share at Start)**:
> "I was thinking we could structure our time as follows:
> 1. (5 min) Quick introductions and confirm what you'd like to cover
> 2. (20-30 min) [Main topic based on meeting purpose]
> 3. (5-10 min) Discuss next steps if relevant
> Does that work for you, or would you prefer a different focus?"

### Core Discussion (20-40 Minutes)
- **Topic 1**: [What to cover + key message]
- **Topic 2**: [What to cover + key message]
- **Topic 3**: [What to cover + key message]

### Close (5 Minutes)
- Summarize key points
- Propose specific next step
- Confirm timeline

---

## 💬 Key Messages

1. [Message tied to their priorities]
2. [Our value proposition in their context]
3. [Differentiator or proof point]

---

## ❓ Questions to Ask

### Discovery
1. [Understanding their situation]
2. [Uncovering priorities or pain]

### Validation
3. [Confirming understanding]
4. [Testing resonance]

### Advancement
5. [Moving toward next step]

### Power Question
- "[Question that accelerates the conversation]"

---

## 🎯 Meeting Strategy

### If It Goes Well

| Next Step | Who to Involve | Timing |
|-----------|----------------|--------|
| [Specific action] | [Names] | [Timeline] |

### If They Are Hesitant
- **Diagnose**: "[Question to understand]"
- **Fallback**: [Lower-commitment option]

---

## 👂 Signals to Listen For

### 🟢 Positive Signals (Advance the Conversation)
- Open, detailed answers with elaboration
- They share challenges or internal context freely
- They ask about your approach or capabilities
- They mention other stakeholders to involve
- They lean forward, take notes, ask follow-ups

### 🟡 Neutral Signals (Probe Deeper)
- Polite but surface-level responses
- Interest without commitment
- "That's interesting, I'll think about it"
- Comparing to other options

### 🔴 Warning Signals (Adjust Approach)
- Short, closed answers
- Checking phone or clock frequently
- "We're not really looking at this right now"
- Avoiding specifics about next steps

**If Warning Signals Appear**: "I want to make sure this is valuable for you. Is there a different angle we should explore, or a more pressing topic?"

---

## 🔔 Last-Minute Check (5 Minutes Before)

### Quick Digital Scans

| Check | What to Look For |
|-------|------------------|
| **LinkedIn** | [Contact Name(s)] — recent posts, job changes, shared connections? |
| **Company News** | [Company] news last 7 days — any relevant announcements? |

### Mental Prep
- [ ] Opening line ready: "[Personalized opener]"
- [ ] Top 2-3 questions prepared
- [ ] Key message clear in your mind
- [ ] Next step proposal ready
- [ ] Calendar open for scheduling

---

## ✅ Preparation Checklist

- [ ] Research reviewed
- [ ] Contact profiles understood
- [ ] Key messages prepared
- [ ] Questions ready
- [ ] Value to bring identified
- [ ] Next step options prepared
- [ ] Calendar open

---

RULES:
- Be specific to this prospect and these contacts – no generic templates.
- Always anchor in THEIR value, not our features.
- Keep tone professional and adaptable.
- Write for a senior B2B sales professional who values clarity and strategic insight.
- If context is missing, note it as "[TO CONFIRM]".
- Keep total brief under 900 words (excluding tables).

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
