"""
Contact Person Analyzer - LinkedIn profile analysis for personalized sales approach.

Analyzes contact persons in the context of:
1. The company they work at (from research)
2. What the seller offers (from profiles)

Generates:
- Communication style assessment
- Decision authority classification
- Role-specific pain points
- Conversation suggestions
- Relevance score (how relevant this contact is for what we sell)
"""

import os
import logging
from typing import Dict, Any, Optional, List
from anthropic import AsyncAnthropic
from supabase import Client
from app.database import get_supabase_service
from app.i18n.utils import get_language_instruction, get_country_iso_code
from app.i18n.config import DEFAULT_LANGUAGE

logger = logging.getLogger(__name__)


class ContactAnalyzer:
    """Analyze contact persons using AI with company and seller context."""
    
    def __init__(self):
        """Initialize Claude API and Supabase."""
        api_key = os.getenv("ANTHROPIC_API_KEY")
        if not api_key:
            raise ValueError("ANTHROPIC_API_KEY not set")
        
        self.client = AsyncAnthropic(api_key=api_key)
        self.supabase: Client = get_supabase_service()
    
    async def analyze_contact(
        self,
        contact_name: str,
        contact_role: Optional[str],
        linkedin_url: Optional[str],
        company_context: Dict[str, Any],
        seller_context: Dict[str, Any],
        language: str = DEFAULT_LANGUAGE,
        user_provided_context: Optional[Dict[str, str]] = None
    ) -> Dict[str, Any]:
        """
        Analyze a contact person with full context.
        
        Args:
            contact_name: Name of the contact
            contact_role: Job title/function
            linkedin_url: LinkedIn profile URL (optional)
            company_context: Research data about the company
            seller_context: What the seller offers
            language: Output language code
            user_provided_context: User-provided LinkedIn info (about, experience, notes)
            
        Returns:
            Analysis dict with all insights
        """
        # Build the analysis prompt
        prompt = self._build_analysis_prompt(
            contact_name,
            contact_role,
            linkedin_url,
            company_context,
            seller_context,
            language,
            user_provided_context
        )
        
        try:
            # Build web search tool config with location context
            country = company_context.get("country") if company_context else None
            user_location = None
            if country:
                iso_country = get_country_iso_code(country)
                if iso_country:
                    user_location = {
                        "type": "approximate",
                        "country": iso_country,
                    }
                    city = company_context.get("city") if company_context else None
                    if city:
                        user_location["city"] = city
            
            # Build tools list with web search (same format as claude_researcher)
            tools = [{
                "type": "web_search_20250305",
                "name": "web_search",
                "max_uses": 5,
            }]
            if user_location:
                tools[0]["user_location"] = user_location
            
            has_user_info = bool(user_provided_context)
            logger.info(f"[CONTACT_ANALYZER] Analyzing {contact_name} - user-provided info: {has_user_info}")
            
            response = await self.client.messages.create(
                model="claude-sonnet-4-20250514",
                max_tokens=3500,
                temperature=0.3,
                messages=[{
                    "role": "user",
                    "content": prompt
                }],
                tools=tools
            )
            
            # Extract text from all text blocks
            analysis_text = ""
            for block in response.content:
                if hasattr(block, 'text'):
                    analysis_text += block.text
            
            # Parse the analysis into structured data
            return self._parse_analysis(analysis_text, contact_name, contact_role, linkedin_url)
            
        except Exception as e:
            logger.error(f"Contact analysis failed: {e}")
            # Return basic info without analysis
            return {
                "name": contact_name,
                "role": contact_role,
                "linkedin_url": linkedin_url,
                "profile_brief": f"# {contact_name}\n\nAnalysis could not be completed: {str(e)}",
                "analysis_failed": True
            }
    
    def _build_analysis_prompt(
        self,
        contact_name: str,
        contact_role: Optional[str],
        linkedin_url: Optional[str],
        company_context: Dict[str, Any],
        seller_context: Dict[str, Any],
        language: str = DEFAULT_LANGUAGE,
        user_provided_context: Optional[Dict[str, str]] = None
    ) -> str:
        """Build the prompt for contact analysis."""
        lang_instruction = get_language_instruction(language)
        company_name = company_context.get("company_name", "Unknown") if company_context else "Unknown"
        
        # Company context section - include research insights
        company_section = ""
        if company_context:
            industry = company_context.get("industry", "")
            brief = company_context.get("brief_content", "")[:2500] if company_context.get("brief_content") else ""
            
            company_section = f"""
## COMPANY CONTEXT (from our research)
**Company**: {company_name}
**Industry**: {industry}

**Research Insights** (use these to personalize your analysis):
{brief}
"""
        
        # Enhanced seller context section
        seller_section = ""
        products_list = ""
        if seller_context and seller_context.get("has_context"):
            products_list = ", ".join(seller_context.get("products_services", [])[:5]) or "Not specified"
            values = ", ".join(seller_context.get("value_propositions", [])[:3]) or "Not specified"
            target = seller_context.get("target_market", "Not specified")
            target_industries = ", ".join(seller_context.get("target_industries", [])[:3]) if seller_context.get("target_industries") else "Any"
            pain_points = ", ".join(seller_context.get("ideal_customer_pain_points", [])[:3]) if seller_context.get("ideal_customer_pain_points") else "Not specified"
            
            seller_section = f"""
## 🎯 SELLER CONTEXT (Use this to assess relevance!)

| Aspect | Details |
|--------|---------|
| **My Company** | {seller_context.get('company_name', 'Unknown')} |
| **Products/Services** | {products_list} |
| **Value Propositions** | {values} |
| **Target Market** | {target} |
| **Target Industries** | {target_industries} |
| **Ideal Customer Pain Points** | {pain_points} |

**Use this to determine how relevant this contact is for what we sell.**
"""
        
        # User-provided LinkedIn info section
        user_info_section = ""
        if user_provided_context:
            user_info_section = "\n## USER-PROVIDED PROFILE INFORMATION (VERIFIED - USE AS PRIMARY SOURCE)\n"
            if user_provided_context.get("about"):
                user_info_section += f"""
### LinkedIn About/Summary:
{user_provided_context.get('about')}
"""
            if user_provided_context.get("experience"):
                user_info_section += f"""
### Experience/Background:
{user_provided_context.get('experience')}
"""
            if user_provided_context.get("notes"):
                user_info_section += f"""
### Additional Notes from Sales Rep:
{user_provided_context.get('notes')}
"""
        
        # Research instruction - improved search strategies
        research_instruction = f"""
## RESEARCH TASK

Search for information about **{contact_name}** at **{company_name}**.

**SEARCH STRATEGY** (LinkedIn is usually blocked, use alternatives):

| Priority | Search Query | What to Find |
|----------|--------------|--------------|
| 1 | "{company_name} team" OR "{company_name} leadership" | Company about/team page |
| 2 | "{contact_name}" "{company_name}" | News, press releases, interviews |
| 3 | "{contact_name}" speaker OR conference OR webinar | Speaking engagements |
| 4 | "{contact_name}" podcast OR interview | Podcast appearances |
| 5 | site:twitter.com OR site:x.com "{contact_name}" | Social media presence |

**What to extract:**
- Career path and achievements
- Communication style from public content (formal/casual/technical)
- Areas of expertise and interests
- Recent activities or announcements
- Quotes that reveal priorities or concerns

**LinkedIn URL** (for reference): {linkedin_url or 'Not provided'}
"""
        
        prompt = f"""You are a senior sales intelligence analyst creating a contact research profile.

{lang_instruction}

**YOUR GOAL**: Help the sales rep truly UNDERSTAND this person - their background, motivations, 
communication preferences, and role in decision-making. This is RESEARCH, not meeting preparation.

**CRITICAL OUTPUT RULES:**
- Output ONLY the structured analysis below
- Do NOT explain your search process
- Do NOT include "I'll search...", "Let me...", "Based on..."
- Start IMMEDIATELY with "## 1. RELEVANCE ASSESSMENT"
- Focus on WHO this person is, not on WHAT TO SAY to them
- Ground every insight in evidence or clearly mark as inference
- Do NOT include opening lines, discovery questions, or scripts (those come later in meeting prep)

{company_section}
{seller_section}
{user_info_section}
{research_instruction}

## CONTACT TO ANALYZE
**Name**: {contact_name}
**Role**: {contact_role or 'Not specified'}

---

# Contact Analysis: {contact_name}
{contact_role or ''}

---

## 1. RELEVANCE ASSESSMENT

| Dimension | Rating | Justification |
|-----------|--------|---------------|
| **Decision Power** | 🟢 High / 🟡 Medium / 🔴 Low | [Based on role and seniority] |
| **Relevance to Our Solution** | 🟢 Direct Buyer / 🟡 Influencer / 🔴 Tangential | [Based on what we sell: {products_list}] |
| **Engagement Priority** | 1-5 (1=contact first) | [Overall priority ranking] |

**Bottom Line**: [One sentence: Should we prioritize this contact? Why?]

---

## 2. PROFILE SUMMARY
- **Background**: [Career path if found, otherwise role-based inference]
- **Current Focus**: [What this person likely spends their day on]
- **Expertise Areas**: [Key skills and knowledge domains]
- **Recent Activity**: [Any news, posts, or appearances found]

---

## 3. COMMUNICATION STYLE

**Style**: Choose ONE and justify:
- **Formal**: Prefers structured, professional communication
- **Informal**: Direct, casual, relationship-focused  
- **Technical**: Wants data, specs, proof points
- **Strategic**: Big-picture, ROI-focused, business outcomes

**Evidence**: [What signals led to this assessment?]

---

## 4. DECISION AUTHORITY

**Role**: Choose ONE and justify:
- **Decision Maker**: Controls budget and final decision
- **Influencer**: Shapes decision but doesn't finalize
- **Gatekeeper**: Controls access to decision makers
- **User/Champion**: Uses the solution, advocates internally

**Evidence**: [Based on title, company size, or research findings]

---

## 5. PROBABLE DRIVERS

What motivates this person? Choose 1-2:
- **Making Progress**: Innovation, modernization, staying ahead
- **Solving Problems**: Fixing what's broken
- **Standing Out**: Recognition, career advancement
- **Avoiding Risk**: Stability, proven solutions

**Evidence**: [Concrete signals if available]

---

## 6. ROLE-SPECIFIC CHALLENGES

What challenges does someone in this role typically face?

| Challenge | Why It Matters | Connection to Our Solution |
|-----------|----------------|---------------------------|
| [Typical challenge for this role] | [Business impact] | [How we can help - if relevant] |
| [Typical challenge for this role] | [Business impact] | [How we can help - if relevant] |
| [Typical challenge for this role] | [Business impact] | [How we can help - if relevant] |

---

## 7. PERSONALITY & WORKING STYLE

Based on available information:

- **Preferred Communication**: [Email / Phone / In-person / Video]
- **Meeting Style**: [Prefers agendas / Likes to explore / Time-conscious / Detail-oriented]
- **Decision Making**: [Data-driven / Relationship-driven / Consensus-builder / Quick decider]
- **What They Value**: [Innovation / Stability / Efficiency / Relationships / Results]

**Key Insight**: [One sentence about what makes this person tick]

---

## 8. RESEARCH CONFIDENCE

| Aspect | Status |
|--------|--------|
| **Information Found** | 🟢 Rich / 🟡 Basic / 🔴 Minimal |
| **Primary Source** | [Where did info come from?] |
| **Gaps to Validate** | [What should be confirmed in first conversation?] |

---

**NOTE: This is a research profile to understand the contact. Specific talking points, opening lines, and discovery questions will be generated in the Meeting Preparation phase when there is a specific meeting context.**"""

        return prompt
    
    def _parse_analysis(
        self,
        analysis_text: str,
        contact_name: str,
        contact_role: Optional[str],
        linkedin_url: Optional[str]
    ) -> Dict[str, Any]:
        """Parse the AI analysis into structured data."""
        
        result = {
            "name": contact_name,
            "role": contact_role,
            "linkedin_url": linkedin_url,
            "profile_brief": analysis_text,
            "analysis_failed": False
        }
        
        text_lower = analysis_text.lower()
        
        # Extract communication style (English keywords)
        if "**formal**" in text_lower or "formal:" in text_lower or "style**: formal" in text_lower:
            result["communication_style"] = "formal"
        elif "**informal**" in text_lower or "informal:" in text_lower or "style**: informal" in text_lower:
            result["communication_style"] = "informal"
        elif "**technical**" in text_lower or "technical:" in text_lower or "style**: technical" in text_lower:
            result["communication_style"] = "technical"
        elif "**strategic**" in text_lower or "strategic:" in text_lower or "style**: strategic" in text_lower:
            result["communication_style"] = "strategic"
        
        # Extract decision authority (English keywords)
        if "**decision maker**" in text_lower or "role**: decision maker" in text_lower:
            result["decision_authority"] = "decision_maker"
        elif "**influencer**" in text_lower or "role**: influencer" in text_lower:
            result["decision_authority"] = "influencer"
        elif "**gatekeeper**" in text_lower or "role**: gatekeeper" in text_lower:
            result["decision_authority"] = "gatekeeper"
        elif "**user**" in text_lower or "**champion**" in text_lower or "role**: user" in text_lower:
            result["decision_authority"] = "user"
        
        # Extract drivers (English keywords)
        drivers = []
        if "making progress" in text_lower or "innovation" in text_lower or "modernization" in text_lower:
            drivers.append("progress")
        if "solving problems" in text_lower or "fixing" in text_lower:
            drivers.append("fixing")
        if "standing out" in text_lower or "recognition" in text_lower or "career advancement" in text_lower:
            drivers.append("standing_out")
        if "avoiding risk" in text_lower or "stability" in text_lower or "proven solutions" in text_lower:
            drivers.append("risk_averse")
        result["probable_drivers"] = ", ".join(drivers) if drivers else None
        
        # Extract relevance score from the assessment table
        if "🟢 high" in text_lower or "decision power** | 🟢" in text_lower:
            result["relevance_score"] = "high"
        elif "🟡 medium" in text_lower:
            result["relevance_score"] = "medium"
        elif "🔴 low" in text_lower:
            result["relevance_score"] = "low"
        
        # Extract priority (1-5)
        import re
        priority_match = re.search(r'priority[^\d]*(\d)', text_lower)
        if priority_match:
            result["priority"] = int(priority_match.group(1))
        
        # Extract research confidence
        if "🟢 rich" in text_lower or "information found** | 🟢" in text_lower:
            result["research_confidence"] = "rich"
        elif "🟡 basic" in text_lower:
            result["research_confidence"] = "basic"
        elif "🔴 minimal" in text_lower:
            result["research_confidence"] = "minimal"
        
        # Note: Opening lines, discovery questions, and things to avoid
        # are now generated in the Preparation phase, not in contact research
        result["opening_suggestions"] = None
        result["questions_to_ask"] = None
        result["topics_to_avoid"] = None
        
        return result
    
    def _extract_list_items(self, text: str, section_name: str, max_items: int) -> List[str]:
        """Extract list items from a section of the analysis."""
        items = []
        
        # Find the section
        section_lower = section_name.lower()
        text_lower = text.lower()
        
        start_idx = text_lower.find(section_lower)
        if start_idx == -1:
            return items
        
        # Find the next section (starts with ##)
        remaining = text[start_idx:]
        lines = remaining.split('\n')
        
        in_section = False
        for line in lines:
            line = line.strip()
            
            # Skip the section header
            if section_lower in line.lower():
                in_section = True
                continue
            
            # Stop at next section
            if line.startswith('##') or line.startswith('###'):
                if in_section:
                    break
            
            # Extract numbered or bulleted items
            if in_section and line:
                # Remove common prefixes
                cleaned = line
                for prefix in ['1.', '2.', '3.', '4.', '5.', '-', '*', '•']:
                    if cleaned.startswith(prefix):
                        cleaned = cleaned[len(prefix):].strip()
                        break
                
                # Remove brackets if present
                if cleaned.startswith('[') and ']' in cleaned:
                    cleaned = cleaned[1:cleaned.index(']')]
                
                if cleaned and len(cleaned) > 10:  # Minimum length
                    items.append(cleaned)
                    if len(items) >= max_items:
                        break
        
        return items
    
    async def get_company_context(self, research_id: str) -> Dict[str, Any]:
        """Get company context from a research brief."""
        try:
            response = self.supabase.table("research_briefs")\
                .select("company_name, country, city, brief_content, research_data")\
                .eq("id", research_id)\
                .single()\
                .execute()
            
            if response.data:
                data = response.data
                return {
                    "company_name": data.get("company_name"),
                    "country": data.get("country"),
                    "city": data.get("city"),
                    "brief_content": data.get("brief_content"),
                    "industry": data.get("research_data", {}).get("industry")
                }
            return {}
        except Exception as e:
            logger.error(f"Error getting company context: {e}")
            return {}
    
    async def get_seller_context(
        self,
        organization_id: str,
        user_id: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Get seller context from profiles.
        
        Extracts and flattens relevant fields from company_profile.
        """
        context = {
            "has_context": False,
            "company_name": None,
            "products_services": [],
            "value_propositions": [],
            "target_market": "B2B",
            "target_industries": [],
            "ideal_customer_pain_points": []
        }
        
        try:
            # Get company profile
            company_response = self.supabase.table("company_profiles")\
                .select("*")\
                .eq("organization_id", organization_id)\
                .limit(1)\
                .execute()
            
            if company_response.data:
                company = company_response.data[0]
                context["has_context"] = True
                context["company_name"] = company.get("company_name")
                
                # Products: extract names from products array
                products = company.get("products", []) or []
                context["products_services"] = [
                    p.get("name") for p in products 
                    if isinstance(p, dict) and p.get("name")
                ]
                
                # Value propositions from core_value_props + differentiators
                context["value_propositions"] = (company.get("core_value_props", []) or []) + \
                                                (company.get("differentiators", []) or [])
                
                # Target industries from ideal_customer_profile
                icp = company.get("ideal_customer_profile", {}) or {}
                context["target_industries"] = icp.get("industries", []) or []
                context["ideal_customer_pain_points"] = icp.get("pain_points", []) or []
                
                logger.info(f"Seller context loaded: {context['company_name']}, products={len(context['products_services'])}")
            
            return context
        except Exception as e:
            logger.warning(f"Could not load seller context: {e}")
            return context


# Singleton instance
_contact_analyzer: Optional[ContactAnalyzer] = None


def get_contact_analyzer() -> ContactAnalyzer:
    """Get or create contact analyzer instance."""
    global _contact_analyzer
    if _contact_analyzer is None:
        _contact_analyzer = ContactAnalyzer()
    return _contact_analyzer

