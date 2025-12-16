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
        # Customer Report increased to handle longer, more detailed reports for 60+ min meetings
        max_tokens_map = {
            ActionType.COMMERCIAL_ANALYSIS: 6000,
            ActionType.SALES_COACHING: 5000,
            ActionType.ACTION_ITEMS: 5000,
            ActionType.CUSTOMER_REPORT: 6000,  # Increased for comprehensive extraction
            ActionType.INTERNAL_REPORT: 3500,
            ActionType.SHARE_EMAIL: 2000,  # Increased for 3 subject lines + personalization notes
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
            
            # Get organization_id and prospect_id from followup
            org_id = context.get("followup", {}).get("organization_id")
            prospect_id = context.get("followup", {}).get("prospect_id")
            company_name = context.get("followup", {}).get("prospect_company_name")
            
            logger.info(f"Gathering context for followup {followup_id}: org={org_id}, prospect={prospect_id}, company={company_name}")
            
            # Get sales profile
            sales_result = supabase.table("sales_profiles").select("*").eq("user_id", user_id).execute()
            if sales_result.data:
                context["sales_profile"] = sales_result.data[0]
                logger.debug("Found sales_profile")
            
            # Get company profile
            if org_id:
                company_result = supabase.table("company_profiles").select("*").eq("organization_id", org_id).execute()
                if company_result.data:
                    context["company_profile"] = company_result.data[0]
                    logger.debug("Found company_profile")
            
            # Try to find research brief - first by prospect_id (most reliable), then by company name
            if org_id:
                research_result = None
                
                # Method 1: Direct prospect_id match (most reliable)
                if prospect_id:
                    research_result = supabase.table("research_briefs").select("*").eq("organization_id", org_id).eq("prospect_id", prospect_id).eq("status", "completed").order("created_at", desc=True).limit(1).execute()
                    if research_result.data:
                        logger.info(f"Found research_brief via prospect_id: {prospect_id}")
                
                # Method 2: Exact company name match
                if not research_result or not research_result.data:
                    if company_name:
                        research_result = supabase.table("research_briefs").select("*").eq("organization_id", org_id).ilike("company_name", company_name).eq("status", "completed").order("created_at", desc=True).limit(1).execute()
                        if research_result.data:
                            logger.info(f"Found research_brief via exact company name: {company_name}")
                
                # Method 3: Fuzzy company name match (contains)
                if not research_result or not research_result.data:
                    if company_name:
                        # Try partial match - search for company name containing the search term
                        search_term = company_name.split()[0] if company_name else ""  # Use first word
                        if search_term and len(search_term) >= 3:
                            research_result = supabase.table("research_briefs").select("*").eq("organization_id", org_id).ilike("company_name", f"%{search_term}%").eq("status", "completed").order("created_at", desc=True).limit(1).execute()
                            if research_result.data:
                                logger.info(f"Found research_brief via fuzzy match on: {search_term}")
                
                if research_result and research_result.data:
                    context["research_brief"] = research_result.data[0]
                    
                    # Get contacts via prospect_id from research_brief
                    research_prospect_id = research_result.data[0].get("prospect_id")
                    if research_prospect_id:
                        contacts_result = supabase.table("prospect_contacts").select("*").eq("prospect_id", research_prospect_id).execute()
                        if contacts_result.data:
                            context["contacts"] = contacts_result.data
                            logger.info(f"Found {len(contacts_result.data)} contacts")
                else:
                    logger.warning(f"No research_brief found for company: {company_name}")
            
            # Try to find preparation brief - same multi-method approach
            if org_id:
                prep_result = None
                
                # Method 1: Direct prospect_id match
                if prospect_id:
                    prep_result = supabase.table("meeting_preps").select("*").eq("organization_id", org_id).eq("prospect_id", prospect_id).eq("status", "completed").order("created_at", desc=True).limit(1).execute()
                    if prep_result.data:
                        logger.info(f"Found preparation via prospect_id: {prospect_id}")
                
                # Method 2: Exact company name match
                if not prep_result or not prep_result.data:
                    if company_name:
                        prep_result = supabase.table("meeting_preps").select("*").eq("organization_id", org_id).ilike("prospect_company_name", company_name).eq("status", "completed").order("created_at", desc=True).limit(1).execute()
                        if prep_result.data:
                            logger.info(f"Found preparation via exact company name: {company_name}")
                
                # Method 3: Fuzzy company name match
                if not prep_result or not prep_result.data:
                    if company_name:
                        search_term = company_name.split()[0] if company_name else ""
                        if search_term and len(search_term) >= 3:
                            prep_result = supabase.table("meeting_preps").select("*").eq("organization_id", org_id).ilike("prospect_company_name", f"%{search_term}%").eq("status", "completed").order("created_at", desc=True).limit(1).execute()
                            if prep_result.data:
                                logger.info(f"Found preparation via fuzzy match on: {search_term}")
                
                if prep_result and prep_result.data:
                    context["preparation"] = prep_result.data[0]
                else:
                    logger.warning(f"No preparation found for company: {company_name}")
            
            # Get deal if linked
            deal_id = context.get("followup", {}).get("deal_id")
            if deal_id:
                deal_result = supabase.table("deals").select("*").eq("id", deal_id).execute()
                if deal_result.data:
                    context["deal"] = deal_result.data[0]
                    logger.debug("Found deal")
            
            # Log final context summary
            context_found = [k for k in ["sales_profile", "company_profile", "research_brief", "contacts", "preparation", "deal"] if k in context]
            logger.info(f"Context gathered for followup {followup_id}: {context_found}")
            
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
        
        # Followup/Transcript - use generous limit (Claude can handle 200K tokens)
        # 75K chars ≈ 18K tokens, well within Claude's capacity
        TRANSCRIPT_LIMIT = 75000
        
        followup = context.get("followup", {})
        if followup:
            transcript = followup.get('transcription_text', 'No transcript available')
            transcript_truncated = len(transcript) > TRANSCRIPT_LIMIT
            
            parts.append(f"""
## Meeting Information
- Company: {followup.get('prospect_company_name', 'Unknown')}
- Date: {followup.get('meeting_date', 'Unknown')}
- Subject: {followup.get('meeting_subject', 'Unknown')}

## Meeting Summary
{followup.get('executive_summary', 'No summary available')}

## Full Transcript{' (truncated)' if transcript_truncated else ''}
{transcript[:TRANSCRIPT_LIMIT]}
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
        # Increased limit to capture full research intelligence
        RESEARCH_LIMIT = 15000
        research = context.get("research_brief", {})
        if research:
            brief = research.get('brief_content', '')
            parts.append(f"""
## Prospect Research (Full)
{brief[:RESEARCH_LIMIT] if brief else 'No research available'}
""")
        
        # Contacts - include full profile analysis for each contact
        # Increased limits to capture full stakeholder intelligence
        CONTACT_LIMIT = 5  # More contacts for multi-stakeholder meetings
        CONTACT_BRIEF_LIMIT = 2000  # Fuller profile per contact
        contacts = context.get("contacts", [])
        if contacts:
            contact_parts = []
            for c in contacts[:CONTACT_LIMIT]:
                contact_section = f"""### {c.get('name', 'Unknown')}
- **Role**: {c.get('role', 'Unknown role')}
- **Decision Authority**: {c.get('decision_authority', 'Unknown')}
- **Communication Style**: {c.get('communication_style', 'Unknown')}
- **Key Motivations**: {c.get('probable_drivers', 'Unknown')}"""
                
                # Add profile brief if available
                if c.get('profile_brief'):
                    brief = c['profile_brief']
                    if len(brief) > CONTACT_BRIEF_LIMIT:
                        brief = brief[:CONTACT_BRIEF_LIMIT] + "..."
                    contact_section += f"\n\n**Profile Analysis**:\n{brief}"
                
                contact_parts.append(contact_section)
            
            parts.append(f"""
## Key Contacts ({len(contacts)} total, showing top {min(len(contacts), CONTACT_LIMIT)})

{chr(10).join(contact_parts)}
""")
        
        # Preparation - include full meeting prep for context
        # Increased limit to capture full preparation strategy
        PREP_LIMIT = 12000
        prep = context.get("preparation", {})
        if prep:
            brief = prep.get('brief_content', 'No preparation notes')
            parts.append(f"""
## Meeting Preparation Notes
{brief[:PREP_LIMIT] if brief else 'No preparation notes'}
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
        sales_email = context.get("user_email", "")  # From user context if available
        sales_phone = context.get("user_phone", "")  # From user context if available
        sales_title = sales_profile.get("role", "")
        
        # Get seller company info
        seller_company = context.get("company_profile", {}).get("company_name", "")
        
        # Get attendees from contacts
        contacts = context.get("contacts", [])
        attendee_names = [c.get("name", "") for c in contacts if c.get("name")]
        attendee_roles = [f"{c.get('name', '')} ({c.get('role', '')})" for c in contacts if c.get("name")]
        
        # Get style rules for customer-facing output
        style_guide = sales_profile.get("style_guide", {})
        style_rules = self._format_style_rules(style_guide) if style_guide else ""
        
        return f"""You are creating a professional customer-facing meeting report that will be sent directly to the client as an email attachment.

{style_rules}

{lang_instruction}

CRITICAL GUIDELINES:

**EXTRACTION REQUIREMENTS — Read the ENTIRE transcript carefully:**
You MUST extract and include ALL of the following from the transcript:

1. **ALL PEOPLE mentioned** — names, roles, and their organizational position
   - Extract every person mentioned by name, even if only referenced once
   - Include their role/title and relationship to the customer organization
   - These are critical for the customer to share internally

2. **ALL TECHNOLOGIES & PLATFORMS mentioned** — current state and future plans
   - Every software, platform, tool, or system discussed
   - Their status: current, planned, being replaced, under evaluation
   - Migration timelines if mentioned

3. **ALL TIMELINES & DATES** — concrete and estimated
   - Project milestones, deadlines, target dates
   - Phases and their expected durations
   - "Next year", "Q2", "by 2027" — all of these matter

4. **ALL ORGANIZATIONS mentioned** — partners, competitors, vendors
   - Companies mentioned as current partners, potential partners, or competitors
   - Their role in the customer's ecosystem

5. **ALL STRATEGIC THEMES** — not just surface topics
   - Underlying challenges and ambitions
   - Political dynamics hinted at
   - Growth plans and transformation goals

6. **ALL ACTION ITEMS & COMMITMENTS** — explicit and implicit
   - What was promised by whom
   - Follow-up meetings, introductions, deliverables

**Tone & Perspective:**
- Write entirely from the CUSTOMER's perspective — this is THEIR document
- Use warm, strategic, and mature language befitting a senior consultant
- Be diplomatic yet insightful — advisory, never directive or salesy
- Never emphasize what the seller did or offered — focus on the customer's world
- Make the customer feel understood, supported, and empowered

**Quality Standards:**
- This document represents professional excellence — it should impress
- Every sentence must add value for the customer
- Be thorough but never verbose — quality over quantity
- Use flowing prose with clear paragraph structure
- Avoid bullet points in main sections (tables are fine for actions)

**Length:**
- Adapt length to match the depth and duration of the conversation
- Short check-in (15-20 min): 400-600 words
- Standard meeting (30 min): 600-900 words
- Deep discussion (45-60 min): 900-1400 words
- Complex multi-stakeholder (60+ min): 1200-1800 words
- NEVER sacrifice quality for brevity — thoroughness is valued
- A 60+ minute conversation with rich content should result in a COMPREHENSIVE report

{context_text}

DOCUMENT STRUCTURE:

---

# Gespreksverslag

**{company_name}**

---

| | |
|---|---|
| **Datum** | {meeting_date} |
| **Onderwerp** | {meeting_subject} |
| **Deelnemers** | {', '.join(attendee_roles) if attendee_roles else '[MUST EXTRACT from transcript - see instruction below]'} |
| **Namens** | {seller_company} — {sales_name} |

**ATTENDEE EXTRACTION** (if not pre-filled above):
If "Deelnemers" shows "[MUST EXTRACT from transcript]", carefully scan the transcript to identify ALL participants:
- Look for introductions, greetings, and moments where people address each other by name
- Extract: Full name + Role/Title + Organization
- Format as: "Name (Role)", "Name (Role)"

---

## ⚡ In Één Oogopslag

*Write 2-3 sentences that capture the essence of the conversation from the customer's perspective. What was the core theme? What is the most important takeaway? This should allow a busy executive to understand the meeting in 10 seconds.*

---

## 1. Inleiding

*Begin with a warm, professional reflection on the conversation. Acknowledge their current situation and ambitions. Set the tone for a document that serves THEM. This paragraph should make the reader feel that you truly understood what matters to them.*

---

## 2. Uw Huidige Situatie

*Describe the customer's context, challenges, and priorities exactly as they expressed them. Be factual and empathetic — no judgment, no spin. Subtly connect their current reality to what is strategically important for their future. Show that you listened deeply.*

---

## 3. Wat We Bespraken

*Organize the discussion into 2-4 clear themes. For each theme:*

### [Theme 1 Title — e.g., "Schaalbaarheid en Groei"]

*Compact paragraph explaining this theme and what it means for the customer. What insights emerged? What became clearer?*

### [Theme 2 Title — e.g., "Data-Infrastructuur en Integratie"]

*Compact paragraph...*

### [Theme 3 Title — if applicable]

*Compact paragraph...*

*Only include themes that genuinely help the customer make progress. Exclude small talk or tangential topics.*

---

## 4. Wat Dit Voor U Betekent

*Explain the implications of what was discussed for their direction, choices, or risks. What opportunities emerge? What dependencies should they consider? What trade-offs might they face? Keep the tone advisory — you are a trusted consultant offering perspective, not a salesperson pushing an agenda.*

---

## 5. Afspraken en Vervolgstappen

| Actie | Eigenaar | Wanneer | Waarom Dit Ertoe Doet |
|-------|----------|---------|----------------------|
| [Specific action] | [Name] | [Date/Week] | [Why this matters to the customer] |
| [Action 2] | [Name] | [Timing] | [Customer relevance] |
| [Action 3] | [Name] | [Timing] | [Customer relevance] |

---

## 6. Vooruitblik

*Outline a possible path forward that logically builds on the customer's own goals. Do not push — guide. Be professional and constructive. Paint a picture of what success could look like and how they might get there. End with an inviting, open sentence that reinforces trust and the spirit of partnership.*

---

## 💭 Vragen Ter Overweging

*Provide 2-3 thoughtful questions that help the customer organize their thinking before the next conversation. These should be genuinely useful strategic questions — not leading questions designed to sell.*

- *[Strategic question 1 — e.g., "Welke data-initiatieven hebben voor u de hoogste prioriteit in het komende kwartaal?"]*

- *[Strategic question 2 — e.g., "Wie binnen uw organisatie zou bij een vervolggesprek betrokken moeten worden?"]*

- *[Strategic question 3 — optional, if relevant]*

---

**Dit verslag is opgesteld door:**

{sales_name}
{f'{sales_title}' if sales_title else ''}
{seller_company}
{f'📧 {sales_email}' if sales_email else ''}
{f'📞 {sales_phone}' if sales_phone else ''}

---

*Dit document is vertrouwelijk en uitsluitend bestemd voor de geadresseerde(n). Verspreiding of gebruik door anderen is niet toegestaan zonder voorafgaande toestemming.*

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
        primary_contact = contacts[0] if contacts else {}
        contact_name = primary_contact.get("name", "there")
        contact_role = primary_contact.get("role", "")
        contact_style = primary_contact.get("communication_style", "professional")
        
        # Get sales rep info for signature
        sales_profile = context.get("sales_profile", {})
        rep_name = sales_profile.get("full_name", "")
        rep_title = sales_profile.get("role", "")
        rep_email = context.get("user_email", "")
        rep_phone = context.get("user_phone", "")
        rep_linkedin = context.get("user_linkedin", "")
        rep_calendly = context.get("user_calendly", "")
        
        # Get company info
        company_profile = context.get("company_profile", {})
        company_name = company_profile.get("company_name", "")
        
        # Get prospect company
        followup = context.get("followup", {})
        prospect_company = followup.get("prospect_company_name", "your organisation")
        meeting_subject = followup.get("meeting_subject", "our conversation")
        
        # Build rich signature
        signature_lines = []
        if rep_name:
            signature_lines.append(rep_name)
        if rep_title and company_name:
            signature_lines.append(f"{rep_title} | {company_name}")
        elif rep_title:
            signature_lines.append(rep_title)
        elif company_name:
            signature_lines.append(company_name)
        if rep_email:
            signature_lines.append(f"📧 {rep_email}")
        if rep_phone:
            signature_lines.append(f"📞 {rep_phone}")
        if rep_linkedin:
            signature_lines.append(f"🔗 {rep_linkedin}")
        if rep_calendly:
            signature_lines.append(f"📅 {rep_calendly}")
        signature = "\n".join(signature_lines) if signature_lines else "[Your signature]"
        
        # Get style rules for customer-facing output
        style_guide = sales_profile.get("style_guide", {})
        style_rules = self._format_style_rules(style_guide) if style_guide else ""
        
        return f"""You are writing a follow-up email to share a meeting summary (Customer Report) with a customer.

{style_rules}

Write as if you are the salesperson who just had the conversation.
Write in clear, warm and professional language.
Use a human, personal tone. Never sound templated, robotic or salesy.
Always write from the CUSTOMER's perspective — this email is about THEM, not you.

The Customer Report is attached to this email. Make this explicit and inviting.

{lang_instruction}

{context_text}

CONTACT CONTEXT:
- Name: {contact_name}
- Role: {contact_role if contact_role else 'Unknown'}
- Communication Style: {contact_style}
- Company: {prospect_company}

PURPOSE:
Send the customer a thoughtful follow-up email together with the meeting summary (Customer Report).
Make the attachment explicit and valuable — tell them what's in it and why it helps them.
Reinforce the connection built in the conversation.
Enable them to share it internally with their team.
Confirm next steps in a natural and low-pressure way.

LENGTH:
Keep the email concise and scannable.
- Simple meeting: 80-120 words
- Standard meeting: 120-160 words  
- Complex meeting: 160-200 words max

STRUCTURE:

---

## 📬 SUBJECT LINE OPTIONS

Provide exactly 3 subject line options. The sales rep will choose the best one.

**Option 1** (Topic-focused):
[Subject line referring to main topic discussed]

**Option 2** (Next step focused):
[Subject line referring to agreed next step]

**Option 3** (Value focused):
[Subject line referring to key insight or outcome]

---

## ✉️ EMAIL

**Greeting:**
Adapt to their communication style:
- If formal/professional: "Beste {contact_name}," or "Geachte {contact_name},"
- If direct/casual: "Hoi {contact_name}," or "Hi {contact_name},"

**Opening (1-2 sentences):**
- Do NOT use: "I hope this email finds you well", "Per our conversation", "As discussed"
- DO: Reference ONE specific moment, insight, or topic that mattered to THEM
- Show you truly listened — mention something they said that stuck with you

**The Attachment (2-3 sentences) — MAKE THIS EXPLICIT:**
- Clearly state: "In de bijlage vind je het gespreksverslag" (or similar)
- Tell them what's IN the report (topics covered, agreements, next steps)
- Frame it as useful for THEM: internal alignment, sharing with colleagues, reference for decisions
- Example: "Hierin vind je een overzicht van wat we bespraken, de afspraken die we maakten, en een paar vragen die kunnen helpen bij jullie interne afstemming."

**Next Steps (1-2 sentences):**
- Confirm the agreed next step clearly
- Include timing if known
- Add a soft CTA that invites engagement:
  - "Laat gerust weten als het verslag aanvullingen nodig heeft"
  - "Ik hoor graag of dit past bij jullie planning"
  - "Voel je vrij om vragen of aanvullingen te delen"

**Closing:**
- Warm, genuine, professional
- Match their communication style
- Examples:
  - Formal: "Met vriendelijke groet,"
  - Direct: "Groet," or "Hartelijke groet,"
  - Casual: "Groetjes," or "Tot snel,"

**Signature:**
{signature}

---

## 💡 PERSONALIZATION NOTES

Provide brief notes for the sales rep:

| Aspect | Note |
|--------|------|
| **Contact's Style** | [Direct/Formal/Analytical/Relational] — adjust tone accordingly |
| **Their Primary Concern** | [The main thing on their mind from the conversation] |
| **Best Follow-up Timing** | [Suggested days to wait before following up] |
| **Internal Stakeholders** | [Who they might share this with — helps frame the report] |

---

RULES:
- Sound human, not corporate — write like a trusted advisor, not a vendor
- The attachment (Customer Report) must be explicitly mentioned and made valuable
- Reference at least one specific moment from the conversation
- Avoid ALL salesy phrases: "exciting", "game-changing", "great opportunity", "synergy"
- Do NOT use placeholder brackets in the final email — fill everything in
- Match the contact's communication style (formal/casual/direct/analytical)
- The email should make them WANT to open the attachment
- Enable internal sharing — frame the report as useful for their team

Generate the complete email with all sections now:"""
    
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
        meeting_date = context.get("followup", {}).get("meeting_date", "today")
        
        return f"""You are extracting action items from a sales conversation and creating a highly actionable task list.

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
Every action must be SMART: Specific, Measurable, with clear deadline.
Include time estimates so the rep can plan their day.
Provide ready-to-use templates for emails and calls.

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

---

## 📋 CRM QUICK COPY

Copy these tasks directly into your CRM/task manager:

| Task | Owner | Due Date | Priority | Status |
|------|-------|----------|----------|--------|
| [Task 1 - starts with verb] | You / Customer / Shared | [Specific date] | 🔴/🟡/🟢 | ⬜ Open |
| [Task 2] | ... | ... | ... | ⬜ Open |
| [Task 3] | ... | ... | ... | ⬜ Open |

---

## ⚡ DO NOW (Within 2 Hours)

**Highest impact, lowest effort tasks to do immediately after this meeting.**

| # | Task | Time Needed | Deal Impact | Why Now |
|---|------|-------------|-------------|---------|
| 1 | [Specific action starting with verb] | X min | 🔴 High / 🟡 Medium | [Why this can't wait] |

If no urgent tasks: "No immediate actions required. First priority task is [X] by [date]."

---

## 📅 CALENDAR BLOCKS

**Block these times in your calendar:**

| Task | Suggested Day | Time Block | Duration | Energy Level |
|------|---------------|------------|----------|--------------|
| [Task description] | [Day of week] | [Morning/Afternoon/End of day] | [X min] | 🧠 High Focus / ☕ Low Energy |

**Total time investment this week**: X hours

---

## 🎯 YOUR TASKS (Sales Rep)

| # | Task (SMART) | Deadline | Time Est. | Priority | Deal Impact | Evidence |
|---|--------------|----------|-----------|----------|-------------|----------|
| 1 | [Specific, measurable task starting with verb] | [Date] | [X min] | 🔴 | [How this advances deal] | "[Quote or reference]" |

**Priority Legend**: 🔴 Deal-critical (do first) | 🟡 Important (this week) | 🟢 Nice-to-have

---

## 🔗 DEPENDENCIES (Do In This Order)

If tasks have dependencies, list the correct sequence:

```
1. [First task] ──► 2. [Second task] ──► 3. [Third task]
         │
         └──► Enables: [What this unlocks]
```

If no dependencies: "All tasks can be done in parallel."

---

## 👤 CUSTOMER TASKS

| # | Task | Owner | Expected By | Follow-up Trigger | Reminder Date |
|---|------|-------|-------------|-------------------|---------------|
| 1 | [What they committed to] | [Name] | [Date] | [What to do if no response by X] | [When to set reminder] |

**Follow-up approach**: [Recommended tone and channel based on their communication style]

---

## 📧 READY-TO-SEND (Copy/Paste)

### Follow-up Email Template

**Subject**: [Suggested subject line]

```
Hi [Name],

[2-3 sentences thanking them, summarizing key points, and stating next steps]

[Specific ask or attached items]

[Closing with clear next step and date]

Best regards,
[Your name]
```

### Follow-up Call Script (if needed)

```
Opening: "[Personalized opener based on conversation]"

Purpose: "[Why you're calling]"

Ask: "[Specific question or request]"

Close: "[Suggested next step]"
```

---

## 🤝 SHARED / MEETING PREP TASKS

| # | Task | Owner | Target Date | Purpose | Prep Needed |
|---|------|-------|-------------|---------|-------------|
| 1 | [Joint task or meeting prep item] | [Who leads] | [Date] | [Why this matters] | [What to prepare] |

---

## ⏳ WAITING ON / BLOCKERS

| Item | Waiting For | Impact if Delayed | Escalation Trigger | Nudge Script |
|------|-------------|-------------------|-------------------|--------------|
| [What's blocked] | [Who/what] | [Business impact] | [When to escalate] | "[What to say]" |

**Escalation path**: If blocked for more than [X days], contact [internal resource/manager].

---

## ⏰ REMINDER SCHEDULE

Set these reminders in your calendar/CRM:

| Reminder | Date | Time | Purpose |
|----------|------|------|---------|
| Follow up on [X] | [Date] | [Time] | [Why] |
| Check if [Y] received | [Date] | [Time] | [Why] |
| Prep for next meeting | [Date] | [Time] | [Why] |

---

## 📊 SUMMARY DASHBOARD

| Metric | Count | Time |
|--------|-------|------|
| **Total action items** | X | |
| **🔴 High priority** | X | X hrs total |
| **⚡ Do Now items** | X | X min |
| **👤 Customer-owned** | X | |
| **⏳ Blocked items** | X | |
| **📅 Calendar blocks needed** | X | X hrs this week |

---

## 🎯 THE ONE THING

If you do nothing else, do THIS:

> **[Single most important action that will have the biggest impact on this deal]**

**Do it by**: [Specific date/time]
**Because**: [Why this matters most]

---

## 🚨 RISK IF NO ACTION

What happens if follow-up slips:

| Days Without Action | Risk | Likelihood |
|---------------------|------|------------|
| 2 days | [Momentum loss description] | Medium |
| 5 days | [Relationship/deal risk] | High |
| 7+ days | [What could go wrong] | Critical |

**Recommended next touchpoint**: [Date] — [Reason based on buying cycle and urgency]

---

RULES:
- Every task MUST start with a verb (Send, Schedule, Prepare, Call, Review, etc.)
- Every task MUST have a specific deadline (not "soon" or "next week")
- Every task MUST have a time estimate
- Include ready-to-use email/call templates when follow-up is needed
- If something is uncertain, flag it rather than guessing
- If a section has no items, write "None identified"
- Remove noise. Keep only commercially meaningful actions
- Prioritise tasks that influence the deal, not administrative housekeeping
- Calendar blocks should match the rep's energy levels (complex = morning, routine = afternoon)

Generate the complete action item list now:"""
    
    def _prompt_internal_report(self, context_text: str, lang_instruction: str, context: Dict) -> str:
        """Prompt for internal report generation - INTERNAL, CRM-standard format"""
        company_name = context.get("followup", {}).get("prospect_company_name", "the customer")
        deal = context.get("deal", {})
        current_stage = deal.get("stage", "Unknown")
        current_value = deal.get("value", "Unknown")
        
        return f"""You are writing an internal sales report optimized for CRM notes and team updates.

Write in clear, factual and highly scannable language.
Assume the reader has 30 seconds and needs to understand what happened, what changed, and what matters next.

Your tone should be concise, commercial and strategically sharp.
Avoid narrative storytelling – prioritise clarity, signals and implications.

{lang_instruction}

{context_text}

PURPOSE:
Create a concise internal update that a sales manager or colleague can absorb in under 60 seconds.
The CRM Quick Copy section should be directly copy-pasteable into any CRM system.
Be honest about uncertainties or gaps in information.

LENGTH GUIDELINE:
- Light check-in → 80–120 words (excluding tables)
- Substantive meeting → 120–180 words (excluding tables)
- Complex stakeholder discussion → up to 220 words (excluding tables)

STRUCTURE:

# Internal Update: {company_name}

---

## 📋 CRM QUICK COPY

Copy these fields directly into your CRM:

| Field | Value |
|-------|-------|
| **Activity Type** | Call / Meeting / Video Call / Demo / Negotiation / Check-in |
| **Subject** | [One-line meeting subject - max 60 chars] |
| **Outcome** | ✅ Positive / ⚡ Neutral / ⚠️ Negative |
| **Next Step** | [Concrete action] |
| **Next Step Owner** | [Name] |
| **Next Step Date** | [Specific date or "Within X days"] |
| **Follow-up Date** | [When to check in again] |

---

## 📌 TL;DR

> [One sentence capturing the real outcome, momentum and key implication for the deal. Make it count.]

---

## 📊 Deal Updates

Only include fields that CHANGED. If nothing changed, write "No deal updates."

| Field | Was | Is Now | Reason |
|-------|-----|--------|--------|
| **Stage** | {current_stage} | [New stage or "No change"] | [One-line reason] |
| **Close Date** | [Previous] | [New date] | [Why it changed] |
| **Probability** | [X]% | [Y]% | [Evidence-based reason] |
| **Deal Value** | {current_value} | [New value or "No change"] | [If upsell/downsell discussed] |

**Forecast Confidence**: 🟢 Increased / 🟡 Stable / 🔴 Decreased — [One-line reason]

---

## 🎯 MEDDIC Quick Status

One-line status per element. Use 🟢 Confirmed / 🟡 Partial / 🔴 Unknown.

| Element | Status | One-Line Note |
|---------|--------|---------------|
| **M**etrics | 🟢/🟡/🔴 | [What success metrics were discussed?] |
| **E**conomic Buyer | 🟢/🟡/🔴 | [Do we have access to budget holder?] |
| **D**ecision Criteria | 🟢/🟡/🔴 | [Do we know how they'll decide?] |
| **D**ecision Process | 🟢/🟡/🔴 | [Do we know the steps to signature?] |
| **I**dentified Pain | 🟢/🟡/🔴 | [Is the pain quantified and urgent?] |
| **C**hampion | 🟢/🟡/🔴 | [Do we have an internal advocate?] |

**MEDDIC Score**: X/6 elements confirmed

---

## 🏆 Champion Status

| Aspect | Status |
|--------|--------|
| **Champion** | [Name + Role] or "Not yet identified" |
| **Activity Level** | 🟢 Active / 🟡 Passive / 🔴 Silent / ❓ Unknown |
| **Last Advocacy** | [What did they do for us recently?] |
| **Risk** | [Any concern about champion engagement?] |

---

## 🎯 Key Takeaways

3-5 essential points in order of strategic importance:

1. [Most impactful insight or development]
2. [Second takeaway]
3. [Third takeaway]
4. [Fourth if relevant]

---

## 👥 Stakeholders Present

| Person | Role | Stance | Engagement | Note |
|--------|------|--------|------------|------|
| [Name] | [Title] | 👍/😐/👎/❓ | High/Med/Low | [Key observation] |

**New contacts identified**: [Names] or "None"
**Missing stakeholders**: [Who should have been there but wasn't?]

---

## ➡️ Next Steps

| # | Action | Owner | Deadline | Priority |
|---|--------|-------|----------|----------|
| 1 | [Specific action] | [Name] | [Date] | 🔴/🟡/🟢 |
| 2 | [Action] | [Name] | [Date] | 🔴/🟡/🟢 |

**Blockers**: [What could prevent these from happening?] or "None identified"

---

## 🚦 Momentum & Risks

**Momentum**: 🟢 Forward / 🟡 Stalled / 🔴 Backwards
> [One sentence explaining why]

**Risks**:
- 🔴 Critical: [If any — requires immediate attention]
- 🟡 Watch: [Emerging concern to monitor]

**Positive Signals**:
- 🟢 [Concrete evidence-based buying signal]

---

## ⚔️ Competitor Intel

| Competitor | Status | Evidence | Our Counter |
|------------|--------|----------|-------------|
| [Name or "None mentioned"] | In play / Eliminated / Unknown | "[Quote if mentioned]" | [How to position] |

If none mentioned: "No competitors discussed in this meeting."

---

## 🆘 Help Needed

Does the rep need manager or team support?

| Type | Request | Urgency |
|------|---------|---------|
| [Escalation / Resources / Expertise / Air Cover / None] | [Specific ask] | 🔴/🟡/🟢 |

If none: "No assistance needed at this time."

---

## 🚨 Escalation Flag

**Requires Management Attention?** Yes / No

If Yes:
- **Issue**: [What needs attention]
- **Why Now**: [Urgency reason]
- **Suggested Action**: [What should manager do]

---

## 💬 Notable Quote

> "[A direct quote that captures the customer's intent, concern or direction — if memorable, include it]"

---

## 🏷️ Tags

Select all that apply:

`[discovery]` `[demo]` `[negotiation]` `[closing]` `[check-in]` `[multi-stakeholder]`
`[budget-discussed]` `[timeline-confirmed]` `[competitor-mentioned]` `[objection-raised]`
`[champion-identified]` `[decision-maker-present]` `[next-step-committed]` `[at-risk]`

---

RULES:
- Lead with what matters commercially.
- CRM Quick Copy section MUST be directly pasteable.
- Keep everything scannable — bullets over paragraphs.
- Do not speculate without labelling it explicitly.
- Exclude noise, minor admin or irrelevant content.
- Write for a busy manager who needs clarity in 60 seconds.
- If a section has no content, write "None" or "N/A" — don't skip sections.
- Be honest about unknowns — "Unknown" is better than guessing.

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

