"""
Follow-up Generator Service

Generates meeting summaries, action items, and follow-up emails
using AI based on transcription and FULL context including:
- Sales/Company profile narratives
- Research data (company info, key people, news)
- Meeting preparation (talking points, questions, strategy)
- Previous follow-ups
- Knowledge base (case studies, product info)
"""

import os
import json
import logging
from typing import Dict, Any, Optional, List
from anthropic import AsyncAnthropic  # Use async client to not block event loop
from app.i18n.utils import get_language_instruction
from app.i18n.config import DEFAULT_LANGUAGE

logger = logging.getLogger(__name__)


class FollowupGenerator:
    """Service for generating follow-up content from meeting transcriptions"""
    
    def __init__(self):
        self.client = AsyncAnthropic(api_key=os.getenv("ANTHROPIC_API_KEY"))
        self.model = "claude-sonnet-4-20250514"
    
    async def generate_summary(
        self,
        transcription: str,
        prospect_context: Optional[Dict[str, Any]] = None,
        language: str = DEFAULT_LANGUAGE,
        # Legacy params for backwards compatibility
        meeting_prep_context: Optional[str] = None,
        profile_context: Optional[str] = None,
        prospect_company: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Generate a structured summary from meeting transcription
        
        Args:
            transcription: Full meeting transcription
            prospect_context: Full prospect context (research, prep, contacts)
            language: Output language code
            meeting_prep_context: Legacy - context from meeting prep
            profile_context: Legacy - sales rep and company profile context
            prospect_company: Name of prospect company
            
        Returns:
            Dict with summary sections
        """
        
        prompt = self._build_summary_prompt(
            transcription,
            prospect_context=prospect_context,
            language=language,
            meeting_prep_context=meeting_prep_context,
            profile_context=profile_context,
            prospect_company=prospect_company
        )
        
        try:
            response = await self.client.messages.create(
                model=self.model,
                max_tokens=4000,
                messages=[{"role": "user", "content": prompt}]
            )
            
            content = response.content[0].text
            return self._parse_summary_response(content)
            
        except Exception as e:
            logger.error(f"Error generating summary: {e}")
            raise
    
    async def extract_action_items(
        self,
        transcription: str,
        summary: Optional[str] = None,
        language: str = DEFAULT_LANGUAGE
    ) -> List[Dict[str, Any]]:
        """
        Extract action items from meeting transcription
        
        Args:
            transcription: Full meeting transcription
            summary: Optional summary for additional context
            
        Returns:
            List of action items with task, assignee, due_date, priority
        """
        
        lang_instruction = get_language_instruction(language)
        
        prompt = f"""Analyze this meeting transcription and extract all action items.

TRANSCRIPTION:
{transcription[:8000]}

{f"SUMMARY: {summary}" if summary else ""}

For each action item, identify:
- task: What needs to be done
- assignee: Who is responsible (if mentioned, otherwise "TBD")
- due_date: Deadline (if mentioned, otherwise null)
- priority: high/medium/low (based on urgency in conversation)

Return ONLY a JSON array, no other text:
[
  {{"task": "...", "assignee": "...", "due_date": "...", "priority": "..."}}
]

If there are no action items, return an empty array: []

{lang_instruction}"""

        try:
            response = await self.client.messages.create(
                model=self.model,
                max_tokens=2000,
                messages=[{"role": "user", "content": prompt}]
            )
            
            content = response.content[0].text.strip()
            
            # Parse JSON response
            # Find JSON array in response
            start_idx = content.find("[")
            end_idx = content.rfind("]") + 1
            
            if start_idx != -1 and end_idx > start_idx:
                json_str = content[start_idx:end_idx]
                return json.loads(json_str)
            
            return []
            
        except Exception as e:
            logger.error(f"Error extracting action items: {e}")
            return []
    
    async def generate_email_draft(
        self,
        summary: Dict[str, Any],
        action_items: List[Dict[str, Any]],
        prospect_context: Optional[Dict[str, Any]] = None,
        language: str = DEFAULT_LANGUAGE,  # i18n: output language
        # Legacy params for backwards compatibility
        profile_context: Optional[str] = None,
        prospect_company: Optional[str] = None,
        tone: str = "professional"
    ) -> str:
        """
        Generate a follow-up email draft
        
        Args:
            summary: Meeting summary dict
            action_items: List of action items
            profile_context: Sales rep profile for personalization
            prospect_company: Name of prospect company
            tone: Email tone (professional, casual, formal)
            
        Returns:
            Email draft text
        """
        
        prompt = self._build_email_prompt(
            summary,
            action_items,
            prospect_context=prospect_context,
            language=language,
            profile_context=profile_context,
            prospect_company=prospect_company,
            tone=tone
        )
        
        try:
            response = await self.client.messages.create(
                model=self.model,
                max_tokens=2000,
                messages=[{"role": "user", "content": prompt}]
            )
            
            return response.content[0].text.strip()
            
        except Exception as e:
            logger.error(f"Error generating email: {e}")
            raise
    
    def _build_summary_prompt(
        self,
        transcription: str,
        prospect_context: Optional[Dict[str, Any]] = None,
        language: str = DEFAULT_LANGUAGE,
        meeting_prep_context: Optional[str] = None,
        profile_context: Optional[str] = None,
        prospect_company: Optional[str] = None
    ) -> str:
        """Build the summary generation prompt - concise overview that invites deeper exploration"""
        
        lang_instruction = get_language_instruction(language)

        prompt = """You are creating a high-level meeting summary designed to be read in under 60 seconds.
Write in a clear, concise and strategically sharp style.
Your tone should be factual, scannable and composed – not interpretive or emotional.
This summary gives the essentials. Deeper analysis lives in separate reports.

"""

        # Build unified context
        if prospect_context:
            company_name = prospect_context.get("prospect_company", prospect_company or "Unknown")
            prompt += f"## PROSPECT COMPANY: {company_name}\n\n"
            
            # Sales Profile (for context only - summaries are professional/standardized)
            sales = prospect_context.get("sales_profile")
            if sales:
                if sales.get("sales_narrative"):
                    prompt += f"## ABOUT YOU (SALES REP)\n{sales['sales_narrative'][:800]}\n\n"
            
            # Company Profile
            company = prospect_context.get("company_profile")
            if company and company.get("company_narrative"):
                prompt += f"## YOUR COMPANY\n{company['company_narrative'][:800]}\n\n"
            
            # Research - include full context for BANT signals, leadership, entry strategy
            research = prospect_context.get("research")
            if research:
                data = research.get("brief_content") or "Not available"
                # Use more of research - contains BANT, leadership, entry strategy (15K chars)
                prompt += f"## PROSPECT RESEARCH\n{data[:15000]}\n\n"
            
            # Meeting Prep
            preps = prospect_context.get("meeting_preps")
            if preps:
                prep = preps[0]
                prompt += f"## MEETING PREPARATION\n"
                prompt += f"**Meeting type:** {prep.get('meeting_type','N/A')}\n"
                prompt += f"**Key objectives:** {prep.get('talking_points','N/A')[:400]}\n\n"
            
            # Previous meeting summary
            prev = prospect_context.get("previous_followups")
            if prev:
                prompt += f"## PREVIOUS MEETING SUMMARY\n{prev[0].get('executive_summary','N/A')[:300]}\n\n"

        else:
            # Fallback legacy support
            if prospect_company:
                prompt += f"## PROSPECT COMPANY: {prospect_company}\n\n"
            if meeting_prep_context:
                prompt += f"## PREPARATION CONTEXT\n{meeting_prep_context[:500]}\n\n"
            if profile_context:
                prompt += f"## SALES PROFILE\n{profile_context[:500]}\n\n"

        # Transcription - use full transcript for rich summary (75K chars = ~18K tokens input)
        prompt += f"## MEETING TRANSCRIPTION\n{transcription[:75000]}\n\n---\n"

        # Summary instructions
        prompt += f"""
Generate a structured, factual summary with EXACTLY the following sections.
Do not analyse or interpret beyond what was explicitly said. Keep everything concise.

# Meeting Summary

## 🏷️ Gist
A single-line TL;DR (max 15 words) that captures: [Company] - [Core topic] - [Outcome/Next step]
Example: "Heijmans - Databricks migratie support - concrete kans, follow-up december"
This must fit in a notification or list preview.

## 📋 In One Sentence
A single precise sentence that captures what this meeting was about and its outcome or significance.  
Make it specific and grounded in what actually happened.

---

## 🎯 What Happened (3–5 sentences)
Provide a short narrative covering:
- The purpose and structure of the conversation
- The main topics discussed
- The tone, engagement level and overall dynamic
- Any shifts in clarity, interest or direction

Keep it crisp and factual.

---

## ✅ Agreements & Decisions
| What Was Agreed | Details |
|-----------------|---------|
[List explicit agreements or commitments only.]

If no agreements:  
**"No formal decisions – exploratory conversation."**

---

## ➡️ Next Steps
| Action | Owner | Timing |
|--------|-------|--------|
[List only clearly confirmed next steps with owners and timelines.]

If none were agreed:  
**"No specific next steps confirmed – follow-up required."**

---

## 💡 Noteworthy Moments
Highlight 2–3 moments that stood out:
- A revealing quote
- A moment of clarity, tension or enthusiasm
- A shift in priorities or focus

Keep these short and intriguing – use them as entry points for deeper analyses.

---

## 📊 At a Glance
| Aspect | Assessment |
|--------|------------|
| **Meeting Dynamic** | 🟢 Constructive / 🟡 Neutral / 🔴 Difficult |
| **Client Engagement** | High / Medium / Low – [one-line reason] |
| **Commercial Signals** | 🟢 Clear interest / 🟡 Mixed / 🔴 None / ⚪ Unclear |
| **Follow-Up Urgency** | 🔴 <24h / 🟡 This week / 🟢 Low – [reason] |

---

## 🔍 Explore Further
Recommend follow-up reports available in the system:

- **📄 Customer Report** – external-facing summary  
- **💰 Commercial Analysis** – deal strength, risks, buying signals  
- **📈 Sales Coaching** – behavioural performance feedback  
- **✅ Action Items** – complete task list  
- **📝 Internal Report** – CRM-ready update  
- **✉️ Share Email** – ready-to-send follow-up

---

RULES:
- Keep the entire summary under 400 words (excluding tables).
- Quote the client directly where valuable.
- Do not interpret beyond the transcript – label unclear elements as "Unclear from conversation".
- Prioritise clarity, brevity and momentum-relevant details.
- No fluff, no filler, no generic phrasing.
- Use a clean, senior-consultant tone.
- If multiple speakers are unclear, focus on the client's statements over the sales rep's.

{lang_instruction}

Generate the meeting summary now:
"""

        return prompt
    
    def _parse_summary_response(self, content: str) -> Dict[str, Any]:
        """Parse the summary response into structured sections.
        
        The new summary format is designed for markdown display.
        We extract key fields for backwards compatibility while storing
        the full content for rendering.
        """
        
        sections = {
            "meeting_gist": "",  # Ultra-short TL;DR for notifications/lists
            "executive_summary": "",
            "key_points": [],
            "concerns": [],
            "decisions": [],
            "next_steps": [],
            "sales_insights": [],
            "noteworthy_moments": [],
            "at_a_glance": {},
            # Legacy fields (kept for backwards compatibility)
            "commercial_signals": {},
            "observations": {},
            "coaching_feedback": {},
            # Full markdown content for display
            "full_content": content
        }
        
        current_section = None
        current_content = []
        
        for line in content.split("\n"):
            line_stripped = line.strip()
            
            # New format sections - Gist (ultra-short TL;DR)
            if "## 🏷️ Gist" in line or "## Gist" in line:
                current_section = "meeting_gist"
                current_content = []
            elif "## 📋 In One Sentence" in line or "In One Sentence" in line:
                # Save gist if we were collecting it
                if current_section == "meeting_gist" and current_content:
                    sections["meeting_gist"] = " ".join(current_content).strip()
                current_section = "executive_summary"
                current_content = []
            elif "## 🎯 What Happened" in line or "What Happened" in line:
                # Save previous section
                if current_section == "executive_summary" and current_content:
                    sections["executive_summary"] = " ".join(current_content).strip()
                current_section = "what_happened"
                current_content = []
            elif "## ✅ Agreements" in line or "Agreements & Decisions" in line:
                if current_section == "what_happened" and current_content:
                    sections["key_points"] = current_content
                current_section = "decisions"
                current_content = []
            elif "## ➡️ Next Steps" in line or "Next Steps" in line:
                current_section = "next_steps"
                current_content = []
            elif "## 💡 Noteworthy" in line or "Noteworthy Moments" in line:
                current_section = "noteworthy_moments"
                current_content = []
            elif "## 📊 At a Glance" in line or "At a Glance" in line:
                current_section = "at_a_glance"
                current_content = []
            elif "## 🔍 Explore Further" in line or "Explore Further" in line:
                current_section = None  # Stop parsing, this is the footer
            
            # Legacy format support (for old summaries)
            elif "## Executive Summary" in line or "## Samenvatting" in line:
                current_section = "executive_summary"
                current_content = []
            elif "## Key Discussion" in line or "## Belangrijkste" in line:
                if current_section == "executive_summary" and current_content:
                    sections["executive_summary"] = " ".join(current_content).strip()
                current_section = "key_points"
                current_content = []
            elif "## Client Concerns" in line or "## Bezwaren" in line:
                current_section = "concerns"
            elif "## Decisions" in line or "## Beslissingen" in line:
                current_section = "decisions"
            elif "## Next Steps" in line or "## Vervolgstappen" in line:
                current_section = "next_steps"
            elif "## Sales Insights" in line:
                current_section = "sales_insights"
            
            # Content parsing
            elif line_stripped and current_section:
                if current_section == "meeting_gist":
                    # Collect single line for gist (ignore example lines)
                    if not line_stripped.startswith("#") and not line_stripped.startswith("---") and not line_stripped.startswith("Example:"):
                        current_content.append(line_stripped)
                elif current_section == "executive_summary":
                    # Collect lines for executive summary
                    if not line_stripped.startswith("#") and not line_stripped.startswith("---"):
                        current_content.append(line_stripped)
                elif current_section == "what_happened":
                    # Collect narrative lines
                    if not line_stripped.startswith("#") and not line_stripped.startswith("---"):
                        current_content.append(line_stripped)
                elif current_section in ["decisions", "next_steps", "noteworthy_moments"]:
                    # Parse bullet points and table rows
                    if line_stripped.startswith("-"):
                        item = line_stripped.lstrip("- ").strip()
                        if item:
                            sections[current_section].append(item)
                    elif line_stripped.startswith("|") and not line_stripped.startswith("|-"):
                        # Table row - extract content
                        cells = [c.strip() for c in line_stripped.split("|")[1:-1]]
                        if cells and not cells[0].startswith("-"):
                            sections[current_section].append(" | ".join(cells))
                elif current_section == "at_a_glance":
                    # Parse At a Glance table
                    if line_stripped.startswith("|") and "**" in line_stripped:
                        cells = [c.strip() for c in line_stripped.split("|")[1:-1]]
                        if len(cells) >= 2:
                            key = cells[0].replace("**", "").strip().lower().replace(" ", "_")
                            value = cells[1].strip()
                            sections["at_a_glance"][key] = value
                elif current_section == "key_points":
                    if line_stripped.startswith("-"):
                        item = line_stripped.lstrip("- ").strip()
                        if item:
                            sections["key_points"].append(item)
                elif current_section in ["concerns", "sales_insights"]:
                    if line_stripped.startswith("-"):
                        item = line_stripped.lstrip("- ").strip()
                        if item:
                            sections[current_section].append(item)
        
        # Handle last section
        if current_section == "executive_summary" and current_content:
            sections["executive_summary"] = " ".join(current_content).strip()
        elif current_section == "what_happened" and current_content:
            sections["key_points"] = current_content
        
        return sections
    
    def _build_email_prompt(
        self,
        summary: Dict[str, Any],
        action_items: List[Dict[str, Any]],
        prospect_context: Optional[Dict[str, Any]] = None,
        language: str = DEFAULT_LANGUAGE,
        profile_context: Optional[str] = None,
        prospect_company: Optional[str] = None,
        tone: str = "professional"
    ) -> str:
        """Build the email generation prompt with full context"""
        
        # Tone instructions - these are guidance for the AI, not user-facing text
        tone_instructions = {
            "professional": "Write professionally but warm and personal.",
            "casual": "Write informally and friendly, as if emailing someone you know.",
            "formal": "Write formally and business-like.",
            "consultative": "Write as a trusted advisor who wants to add value."
        }
        
        prompt = f"""You are a sales professional writing a follow-up email after a meeting.
You have access to extensive context - use this for a personalized, relevant email.

"""
        
        # Use new unified context if available
        if prospect_context:
            company_name = prospect_context.get("prospect_company", prospect_company or "the prospect")
            prompt += f"PROSPECT: {company_name}\n\n"
            
            # Sales profile for personalization
            if prospect_context.get("sales_profile"):
                sales = prospect_context["sales_profile"]
                prompt += f"""ABOUT YOU:
- Name: {sales.get('full_name', 'N/A')}
- Communication style: {sales.get('communication_style', 'professional')}
- Sales methodology: {sales.get('sales_methodology', 'consultative')}

"""
            
            # Company info for value props
            if prospect_context.get("company_profile"):
                company = prospect_context["company_profile"]
                # Extract value propositions from core_value_props
                value_props = company.get('core_value_props', []) or []
                prompt += f"""YOUR COMPANY:
- Company: {company.get('company_name', 'N/A')}
- Value props: {', '.join(value_props[:3]) if value_props else 'N/A'}

"""
            
            # Research for personalization - key insights for relevant email
            if prospect_context.get("research"):
                research = prospect_context["research"]
                # Include more research for better personalization
                prompt += f"""PROSPECT CONTEXT (from research):
{research.get('brief_content', '')[:1500]}

"""
            
            # KB for case studies to mention
            if prospect_context.get("kb_chunks"):
                kb_mentions = [chunk.get('source', '') for chunk in prospect_context["kb_chunks"][:2]]
                if kb_mentions:
                    prompt += f"""RELEVANT MATERIALS TO SHARE:
{', '.join(kb_mentions)}

"""
        else:
            # Legacy fallback
            if prospect_company:
                prompt += f"PROSPECT: {prospect_company}\n\n"
            
            if profile_context:
                prompt += f"""YOUR PROFILE (for personalization):
{profile_context}

"""
        
        prompt += f"""MEETING SUMMARY:
{summary.get('executive_summary', 'No summary available')}

KEY POINTS:
{chr(10).join('- ' + p for p in summary.get('key_points', [])[:5])}

NEXT STEPS:
{chr(10).join('- ' + s for s in summary.get('next_steps', [])[:5])}

ACTION ITEMS:
{chr(10).join('- ' + item.get('task', '') for item in action_items[:5])}

TONE: {tone_instructions.get(tone, tone_instructions['professional'])}

---

IMPORTANT: Write the email from a CUSTOMER-CENTRIC PERSPECTIVE.

This means:
- Start by acknowledging THEIR situation, not "thank you for your time"
- Focus on what's relevant for THE CLIENT, not for you as seller
- Link next steps to CLIENT benefit ("This aligns with your goal to...")
- No sales language or internal jargon
- Professional but human and accessible

STRUCTURE:
1. Opening: acknowledge the conversation and their situation/challenge
2. Core: their priorities and how this aligns (not: what we sell)
3. Next step: concrete, linked to their goal
4. Closing: invitation to respond

AVOID:
- "Thank you for your time" as opening
- Too much emphasis on your products/services
- Long lists of features
- Jargon or abbreviations

Start directly with the email (no "Here is the email:" or similar intro).
Use [NAME] as placeholder for the recipient name.
{get_language_instruction(language)}"""

        return prompt
    
    # NOTE: _format_style_rules has been removed - SPEC-033
    # Style rules are only used for customer-facing outputs (share_email, customer_report)
    # and are handled by ActionGenerator using SellerContextBuilder


# Lazy singleton
_followup_generator: Optional[FollowupGenerator] = None

def get_followup_generator() -> FollowupGenerator:
    """Get or create followup generator instance"""
    global _followup_generator
    if _followup_generator is None:
        _followup_generator = FollowupGenerator()
    return _followup_generator

