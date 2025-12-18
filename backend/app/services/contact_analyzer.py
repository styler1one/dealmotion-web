"""
Contact Person Analyzer - LinkedIn profile analysis for personalized sales approach.

OPTIMIZED ARCHITECTURE (v3):
- Uses unified people search provider for LinkedIn profile discovery (semantic matching)
- Falls back to Brave Search if provider unavailable
- Uses Claude for analysis only (no web tools = ~$0.03)
- Total cost: ~$0.035 per contact (85% reduction from $0.23)

Analyzes contact persons in the context of:
1. The company they work at (from research)
2. What the seller offers (from profiles)

Generates (focused on what Preparation Brief needs):
- Decision authority classification (DMU mapping)
- Communication style assessment (tone adjustment)
- Motivation drivers (hooks for engagement)
- Role-specific challenges (pain points)
- Professional profile summary
"""

import os
import re
import json
import logging
import aiohttp
from typing import Dict, Any, Optional, List
from anthropic import AsyncAnthropic
from supabase import Client
from app.database import get_supabase_service
from app.i18n.utils import get_language_instruction, get_country_iso_code
from app.i18n.config import DEFAULT_LANGUAGE

logger = logging.getLogger(__name__)

# Import people search provider
try:
    from app.services.people_search_provider import get_people_search_provider
    HAS_PEOPLE_SEARCH_PROVIDER = True
except ImportError:
    HAS_PEOPLE_SEARCH_PROVIDER = False
    logger.warning("[CONTACT_ANALYZER] People search provider not available")

# Common name suffixes to clean before searching
NAME_CLEAN_PATTERNS = [
    r'\bRc\s*Re\b', r'\bRC\s*RE\b', r'\bRA\b', r'\bAA\b',
    r'\bMBA\b', r'\bMSc\b', r'\bBSc\b', r'\bPhD\b',
    r'\bDr\.?\b', r'\bMr\.?\b', r'\bMrs\.?\b', r'\bDrs\.?\b',
    r'\bIr\.?\b', r'\bProf\.?\b', r'\bCPA\b', r'\bCFA\b',
    r'[\(\)]+', r'[\[\]]+', r'\|.*$', r'-\s*$',
]


def _clean_name(name: str) -> str:
    """Clean name by removing degree abbreviations and garbage."""
    if not name:
        return name
    cleaned = name
    for pattern in NAME_CLEAN_PATTERNS:
        cleaned = re.sub(pattern, '', cleaned, flags=re.IGNORECASE)
    return ' '.join(cleaned.split()).strip()


class ContactAnalyzer:
    """Analyze contact persons using AI with company and seller context."""
    
    def __init__(self):
        """Initialize Claude API, people search provider, and Supabase."""
        api_key = os.getenv("ANTHROPIC_API_KEY")
        if not api_key:
            raise ValueError("ANTHROPIC_API_KEY not set")
        
        self.client = AsyncAnthropic(api_key=api_key)
        self.supabase: Client = get_supabase_service()
        self.brave_api_key = os.getenv("BRAVE_API_KEY")
        
        # Initialize people search provider
        self._people_search_provider = None
        if HAS_PEOPLE_SEARCH_PROVIDER:
            try:
                self._people_search_provider = get_people_search_provider()
                logger.info("[CONTACT_ANALYZER] People search provider initialized")
            except Exception as e:
                logger.warning(f"[CONTACT_ANALYZER] Could not init people search provider: {e}")
    
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
        
        OPTIMIZED FLOW (v2):
        1. Use Brave Search to find LinkedIn profile info (if no user-provided context)
        2. Use Claude WITHOUT web tools for pure analysis
        3. Return focused output for Preparation Brief
        
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
        company_name = company_context.get("company_name", "Unknown") if company_context else "Unknown"
        
        # STEP 1: Gather profile information
        # Priority: user-provided > research leadership > Brave search
        profile_info = await self._gather_profile_info(
            contact_name=contact_name,
            contact_role=contact_role,
            linkedin_url=linkedin_url,
            company_name=company_name,
            company_context=company_context,
            user_provided_context=user_provided_context
        )
        
        has_user_info = bool(user_provided_context)
        has_brave_info = profile_info.get("source") == "brave"
        has_research_info = profile_info.get("source") == "research"
        
        logger.info(f"[CONTACT_ANALYZER] Analyzing {contact_name} at {company_name}")
        logger.info(f"[CONTACT_ANALYZER] Info sources: user={has_user_info}, brave={has_brave_info}, research={has_research_info}")
        
        # STEP 2: Build optimized prompt (no web search needed)
        prompt = self._build_analysis_prompt(
            contact_name=contact_name,
            contact_role=contact_role,
            linkedin_url=linkedin_url,
            company_context=company_context,
            seller_context=seller_context,
            language=language,
            user_provided_context=user_provided_context,
            profile_info=profile_info  # NEW: Include gathered profile info
        )
        
        try:
            # STEP 3: Claude analysis WITHOUT web tools (85% cost reduction!)
            logger.info(f"[CONTACT_ANALYZER] Starting Claude analysis (no web tools)")
            
            response = await self.client.messages.create(
                model="claude-sonnet-4-20250514",
                max_tokens=2500,  # Reduced from 3500 - focused output
                temperature=0.3,
                messages=[{
                    "role": "user",
                    "content": prompt
                }]
                # NO tools parameter = no web search = much cheaper!
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
    
    async def _gather_profile_info(
        self,
        contact_name: str,
        contact_role: Optional[str],
        linkedin_url: Optional[str],
        company_name: str,
        company_context: Dict[str, Any],
        user_provided_context: Optional[Dict[str, str]]
    ) -> Dict[str, Any]:
        """
        Gather profile information from multiple sources.
        
        Priority:
        1. User-provided context (most reliable)
        2. Research leadership data (already researched)
        3. People search provider (semantic matching, 1B+ profiles)
        4. Brave Search fallback (keyword-based)
        
        Returns dict with: source, headline, about, experience, recent_activity
        """
        result = {
            "source": "none",
            "headline": None,
            "about": None,
            "experience": None,
            "recent_activity": None,
            "background": None,
            "location": None,
            "experience_years": None,
            "skills": [],
            "raw_profile_text": None  # Full profile text for Claude analysis
        }
        
        print(f"[CONTACT_ANALYZER] Gathering profile info for: {contact_name} at {company_name}", flush=True)
        
        # Priority 1: User-provided context
        if user_provided_context:
            result["source"] = "user_provided"
            result["about"] = user_provided_context.get("about")
            result["experience"] = user_provided_context.get("experience")
            if result["about"] or result["experience"]:
                print(f"[CONTACT_ANALYZER] ✅ Using user-provided context for {contact_name}", flush=True)
                return result
        
        # Priority 2: Check if this person is in research leadership data
        leadership = company_context.get("leadership", []) if company_context else []
        print(f"[CONTACT_ANALYZER] Research leadership has {len(leadership)} entries", flush=True)
        clean_name = _clean_name(contact_name).lower()
        
        for leader in leadership:
            leader_name = _clean_name(leader.get("name", "")).lower()
            # Check for name match (at least 2 name parts overlap)
            name_parts = set(clean_name.split())
            leader_parts = set(leader_name.split())
            common_parts = name_parts & leader_parts
            
            if len(common_parts) >= 2 or clean_name == leader_name:
                result["source"] = "research"
                result["headline"] = leader.get("title")
                result["background"] = leader.get("background")
                if leader.get("linkedin_url") and not linkedin_url:
                    result["linkedin_url"] = leader.get("linkedin_url")
                print(f"[CONTACT_ANALYZER] ✅ Found {contact_name} in research leadership", flush=True)
                return result
        
        # Priority 3: People search provider (semantic matching + full profile data)
        if self._people_search_provider:
            print(f"[CONTACT_ANALYZER] 🔍 Starting provider search for {contact_name}...", flush=True)
            try:
                provider_info = await self._people_search_provider.get_profile_info(
                    name=contact_name,
                    company_name=company_name,
                    role=contact_role
                )
                print(f"[CONTACT_ANALYZER] Provider result: found={provider_info.get('found')}", flush=True)
                
                if provider_info.get("found"):
                    result["source"] = "provider"
                    result["headline"] = provider_info.get("headline")
                    result["about"] = provider_info.get("about")  # AI-generated summary
                    result["location"] = provider_info.get("location")
                    result["experience_years"] = provider_info.get("experience_years")
                    result["skills"] = provider_info.get("skills", [])
                    result["raw_profile_text"] = provider_info.get("raw_text")  # Full text for Claude
                    if provider_info.get("linkedin_url") and not linkedin_url:
                        result["linkedin_url"] = provider_info.get("linkedin_url")
                    
                    skills_str = ", ".join(provider_info.get("skills", [])[:5]) if provider_info.get("skills") else "none found"
                    print(f"[CONTACT_ANALYZER] ✅ Found enriched profile via provider:", flush=True)
                    print(f"    - Headline: {provider_info.get('headline')}", flush=True)
                    print(f"    - Location: {provider_info.get('location')}", flush=True)
                    print(f"    - Experience: {provider_info.get('experience_years')} years", flush=True)
                    print(f"    - Skills: {skills_str}", flush=True)
                    return result
            except Exception as e:
                print(f"[CONTACT_ANALYZER] ⚠️ Provider search failed: {e}", flush=True)
                logger.warning(f"[CONTACT_ANALYZER] Provider error: {e}")
        
        # Priority 4: Brave Search fallback for LinkedIn profile info
        print(f"[CONTACT_ANALYZER] Brave API key available: {bool(self.brave_api_key)}", flush=True)
        if self.brave_api_key:
            print(f"[CONTACT_ANALYZER] 🔍 Fallback: Brave search for {contact_name}...", flush=True)
            brave_info = await self._search_linkedin_with_brave(
                contact_name=contact_name,
                contact_role=contact_role,
                company_name=company_name
            )
            print(f"[CONTACT_ANALYZER] Brave result: found={brave_info.get('found')}", flush=True)
            if brave_info.get("found"):
                result["source"] = "brave"
                result["headline"] = brave_info.get("headline")
                result["about"] = brave_info.get("about")
                result["recent_activity"] = brave_info.get("recent_activity")
                print(f"[CONTACT_ANALYZER] ✅ Found profile info via Brave: {brave_info.get('headline')}", flush=True)
                return result
        else:
            print(f"[CONTACT_ANALYZER] ⚠️ No Brave API key - skipping fallback search", flush=True)
        
        # No additional info found - will rely on role-based inference
        result["source"] = "role_inference"
        print(f"[CONTACT_ANALYZER] ⚠️ No profile info found for {contact_name}, using role-based inference", flush=True)
        return result
    
    async def _search_linkedin_with_brave(
        self,
        contact_name: str,
        contact_role: Optional[str],
        company_name: str
    ) -> Dict[str, Any]:
        """
        Search for LinkedIn profile information using Brave Search API.
        
        Cost: ~$0.003 per search (vs $0.20+ for Claude web search)
        
        Returns: dict with found, headline, about, recent_activity
        """
        result = {"found": False}
        
        if not self.brave_api_key:
            print(f"[CONTACT_ANALYZER] Brave: No API key configured", flush=True)
            return result
        
        try:
            clean_name = _clean_name(contact_name)
            
            # Build search queries - focus on finding profile snippets
            # Include role for more specific results
            queries = []
            if company_name and company_name != "Unknown":
                queries.append(f'site:linkedin.com/in "{clean_name}" "{company_name}"')
                if contact_role:
                    queries.append(f'site:linkedin.com/in "{clean_name}" "{contact_role}"')
                queries.append(f'"{clean_name}" "{company_name}" LinkedIn profile')
            # Fallback: just the name
            queries.append(f'site:linkedin.com/in "{clean_name}"')
            
            print(f"[CONTACT_ANALYZER] Brave: Trying {len(queries)} queries for {clean_name}", flush=True)
            
            async with aiohttp.ClientSession() as session:
                headers = {
                    "Accept": "application/json",
                    "X-Subscription-Token": self.brave_api_key
                }
                
                for query in queries:
                    print(f"[CONTACT_ANALYZER] Brave query: {query}", flush=True)
                    params = {"q": query, "count": 5}
                    
                    async with session.get(
                        "https://api.search.brave.com/res/v1/web/search",
                        headers=headers,
                        params=params
                    ) as response:
                        if response.status != 200:
                            print(f"[CONTACT_ANALYZER] Brave: HTTP {response.status}", flush=True)
                            continue
                        
                        data = await response.json()
                        web_results = data.get("web", {}).get("results", [])
                        print(f"[CONTACT_ANALYZER] Brave: {len(web_results)} results", flush=True)
                        
                        for web_result in web_results:
                            url = web_result.get("url", "")
                            if "linkedin.com/in/" not in url.lower():
                                continue
                            
                            # Found a LinkedIn result - extract info
                            title = web_result.get("title", "")
                            description = web_result.get("description", "")
                            
                            # Parse headline from title (usually "Name - Title | LinkedIn")
                            headline = None
                            if " - " in title:
                                parts = title.split(" - ")
                                if len(parts) > 1:
                                    headline = parts[1].split(" | ")[0].strip()
                            
                            result["found"] = True
                            result["headline"] = headline
                            result["about"] = description[:500] if description else None
                            result["linkedin_url"] = url
                            
                            print(f"[CONTACT_ANALYZER] ✅ Brave found: {clean_name} -> {headline}", flush=True)
                            return result
                
                print(f"[CONTACT_ANALYZER] Brave: No LinkedIn results found", flush=True)
            
            return result
            
        except Exception as e:
            print(f"[CONTACT_ANALYZER] ❌ Brave search error: {e}", flush=True)
            return result
    
    def _build_analysis_prompt(
        self,
        contact_name: str,
        contact_role: Optional[str],
        linkedin_url: Optional[str],
        company_context: Dict[str, Any],
        seller_context: Dict[str, Any],
        language: str = DEFAULT_LANGUAGE,
        user_provided_context: Optional[Dict[str, str]] = None,
        profile_info: Optional[Dict[str, Any]] = None
    ) -> str:
        """
        Build the OPTIMIZED prompt for contact analysis.
        
        FOCUSED on what Preparation Brief needs:
        1. Decision Authority (DMU mapping)
        2. Communication Style (tone adjustment)
        3. Motivation Drivers (engagement hooks)
        4. Role Challenges (pain points)
        5. Professional Summary
        
        NO web search - all info is pre-gathered via Brave/research.
        """
        lang_instruction = get_language_instruction(language)
        company_name = company_context.get("company_name", "Unknown") if company_context else "Unknown"
        
        # === COMPANY CONTEXT (compact) ===
        company_section = ""
        if company_context:
            industry = company_context.get("industry", "")
            # Use shorter brief excerpt - we don't need the full thing
            brief = company_context.get("brief_content", "")[:1500] if company_context.get("brief_content") else ""
            
            company_section = f"""## COMPANY CONTEXT
**Company**: {company_name}
**Industry**: {industry}

**Key Research Insights**:
{brief}
"""
        
        # === SELLER CONTEXT (compact) ===
        seller_section = ""
        products_list = "Not specified"
        if seller_context and seller_context.get("has_context"):
            products_list = ", ".join(seller_context.get("products_services", [])[:5]) or "Not specified"
            pain_points = ", ".join(seller_context.get("ideal_customer_pain_points", [])[:3]) if seller_context.get("ideal_customer_pain_points") else "Not specified"
            
            seller_section = f"""## SELLER CONTEXT
**We Sell**: {products_list}
**We Solve**: {pain_points}
**Our Company**: {seller_context.get('company_name', 'Unknown')}
"""
        
        # === PROFILE INFORMATION (from search provider/research) ===
        profile_section = ""
        if profile_info and profile_info.get("source") != "none":
            source = profile_info.get("source", "unknown")
            profile_section = f"\n## PROFILE INFORMATION (Source: {source})\n"
            
            if profile_info.get("headline"):
                profile_section += f"**Headline**: {profile_info['headline']}\n"
            if profile_info.get("about"):
                profile_section += f"**About**: {profile_info['about'][:500]}\n"
            if profile_info.get("experience"):
                profile_section += f"**Experience**: {profile_info['experience'][:500]}\n"
            if profile_info.get("background"):
                profile_section += f"**Background**: {profile_info['background']}\n"
            if profile_info.get("recent_activity"):
                profile_section += f"**Recent Activity**: {profile_info['recent_activity']}\n"
            
            # Add skills if available
            skills = profile_info.get("skills", [])
            if skills:
                profile_section += f"**Skills**: {', '.join(skills[:10])}\n"
            
            # Add experience years if available
            if profile_info.get("experience_years"):
                profile_section += f"**Years of Experience**: {profile_info['experience_years']}\n"
            
            # Add location if available
            if profile_info.get("location"):
                profile_section += f"**Location**: {profile_info['location']}\n"
            
            # Include raw LinkedIn profile text for comprehensive analysis
            # This gives Claude full context about the person
            raw_text = profile_info.get("raw_profile_text")
            if raw_text:
                profile_section += f"\n**Full LinkedIn Profile Content**:\n```\n{raw_text[:2500]}\n```\n"
        
        # === USER-PROVIDED INFO (highest priority) ===
        user_info_section = ""
        if user_provided_context:
            user_info_section = "\n## USER-PROVIDED INFORMATION (USE AS PRIMARY SOURCE)\n"
            if user_provided_context.get("about"):
                user_info_section += f"**LinkedIn About**: {user_provided_context['about']}\n"
            if user_provided_context.get("experience"):
                user_info_section += f"**Experience**: {user_provided_context['experience']}\n"
            if user_provided_context.get("notes"):
                user_info_section += f"**Sales Rep Notes**: {user_provided_context['notes']}\n"
        
        # === BUILD FINAL PROMPT ===
        prompt = f"""You are a senior sales intelligence analyst. Analyze this contact person.

{lang_instruction}

**YOUR TASK**: Create a focused analysis to help prepare for meetings with this person.
Focus on WHO they are, their decision-making role, and how to communicate with them.

**CRITICAL RULES**:
- Use ONLY the information provided below (no web searches needed)
- If information is missing, use role-based inference (clearly marked)
- Output the structured format exactly as shown
- Start IMMEDIATELY with "## 1. QUICK ASSESSMENT"

{company_section}
{seller_section}
{profile_section}
{user_info_section}

## CONTACT TO ANALYZE
**Name**: {contact_name}
**Role**: {contact_role or 'Not specified'}
**LinkedIn**: {linkedin_url or 'Not available'}

---

# Contact Analysis: {contact_name}
*{contact_role or 'Role not specified'}*

---

## 1. QUICK ASSESSMENT

| Dimension | Rating | Evidence |
|-----------|--------|----------|
| **Decision Power** | 🟢 High / 🟡 Medium / 🔴 Low | [Based on role title] |
| **Relevance** | 🟢 Direct Buyer / 🟡 Influencer / 🔴 Tangential | [For: {products_list}] |
| **Priority** | 1-5 | [1 = contact first] |

**Bottom Line**: [One sentence verdict - prioritize this contact? Why?]

---

## 2. PROFESSIONAL PROFILE

- **Background**: [Career trajectory based on role/info]
- **Current Focus**: [What occupies their daily work]
- **Expertise**: [Key domains and skills]

---

## 3. COMMUNICATION STYLE

**Primary Style** (choose ONE):
- **FORMAL**: Structured, professional, respects hierarchy
- **INFORMAL**: Direct, casual, relationship-first
- **TECHNICAL**: Data-driven, wants proof points
- **STRATEGIC**: Big-picture, ROI-focused

**How to Adapt**: [Specific guidance for engaging this style]

---

## 4. DECISION AUTHORITY

**DMU Role** (choose ONE):
- **DECISION MAKER**: Controls budget, signs off
- **INFLUENCER**: Shapes decision, doesn't finalize
- **GATEKEEPER**: Controls access
- **CHAMPION**: Uses solution, advocates internally

**Implications**: [What this means for our approach]

---

## 5. MOTIVATION DRIVERS

**What Drives Them** (choose 1-2):
- **PROGRESS**: Innovation, modernization, staying ahead
- **PROBLEM-SOLVING**: Fixing pain points
- **RECOGNITION**: Standing out, career growth
- **STABILITY**: Risk aversion, proven solutions

**Evidence**: [What suggests these drivers]

---

## 6. ROLE CHALLENGES

| Challenge | Business Impact | Our Relevance |
|-----------|----------------|---------------|
| [Typical for this role] | [Why it matters] | [How we help] |
| [Typical for this role] | [Why it matters] | [How we help] |

---

## 7. CONFIDENCE LEVEL

| Information | Status |
|-------------|--------|
| **Quality** | 🟢 Rich / 🟡 Basic / 🔴 Minimal |
| **Source** | {profile_info.get('source', 'Role inference') if profile_info else 'Role inference'} |
| **Gaps** | [What to verify in first conversation] |

---

*This analysis feeds into Meeting Preparation where specific talking points and questions will be generated.*"""

        return prompt
    
    def _parse_analysis(
        self,
        analysis_text: str,
        contact_name: str,
        contact_role: Optional[str],
        linkedin_url: Optional[str]
    ) -> Dict[str, Any]:
        """
        Parse the AI analysis into structured data.
        
        Extracts key fields for Preparation Brief:
        - communication_style
        - decision_authority
        - probable_drivers
        - relevance_score
        - priority
        - research_confidence
        """
        
        result = {
            "name": contact_name,
            "role": contact_role,
            "linkedin_url": linkedin_url,
            "profile_brief": analysis_text,
            "analysis_failed": False
        }
        
        text_lower = analysis_text.lower()
        
        # Extract communication style (matching new prompt format)
        # Format: "**FORMAL**:", "**INFORMAL**:", etc.
        if "**formal**" in text_lower or "formal:" in text_lower or "primary style**: formal" in text_lower:
            result["communication_style"] = "formal"
        elif "**informal**" in text_lower or "informal:" in text_lower or "primary style**: informal" in text_lower:
            result["communication_style"] = "informal"
        elif "**technical**" in text_lower or "technical:" in text_lower or "primary style**: technical" in text_lower:
            result["communication_style"] = "technical"
        elif "**strategic**" in text_lower or "strategic:" in text_lower or "primary style**: strategic" in text_lower:
            result["communication_style"] = "strategic"
        
        # Extract decision authority (matching new prompt format)
        # Format: "**DECISION MAKER**:", "**INFLUENCER**:", etc.
        if "**decision maker**" in text_lower or "dmu role**: decision maker" in text_lower:
            result["decision_authority"] = "decision_maker"
        elif "**influencer**" in text_lower or "dmu role**: influencer" in text_lower:
            result["decision_authority"] = "influencer"
        elif "**gatekeeper**" in text_lower or "dmu role**: gatekeeper" in text_lower:
            result["decision_authority"] = "gatekeeper"
        elif "**champion**" in text_lower or "dmu role**: champion" in text_lower:
            result["decision_authority"] = "user"
        
        # Extract drivers (matching new prompt format)
        # Format: "**PROGRESS**:", "**PROBLEM-SOLVING**:", etc.
        drivers = []
        if "**progress**" in text_lower or "progress:" in text_lower or "innovation" in text_lower:
            drivers.append("progress")
        if "**problem-solving**" in text_lower or "problem-solving:" in text_lower or "fixing pain" in text_lower:
            drivers.append("problem_solving")
        if "**recognition**" in text_lower or "recognition:" in text_lower or "standing out" in text_lower or "career growth" in text_lower:
            drivers.append("recognition")
        if "**stability**" in text_lower or "stability:" in text_lower or "risk aversion" in text_lower:
            drivers.append("stability")
        result["probable_drivers"] = ", ".join(drivers) if drivers else None
        
        # Extract relevance score from the assessment table
        # Format: "🟢 High", "🟡 Medium", "🔴 Low"
        if "🟢 high" in text_lower or "decision power** | 🟢" in text_lower:
            result["relevance_score"] = "high"
        elif "🟡 medium" in text_lower:
            result["relevance_score"] = "medium"
        elif "🔴 low" in text_lower:
            result["relevance_score"] = "low"
        
        # Extract priority (1-5)
        priority_match = re.search(r'priority[^\d]*(\d)', text_lower)
        if priority_match:
            result["priority"] = int(priority_match.group(1))
        
        # Extract research confidence (matching new prompt format)
        # Format: "**Quality** | 🟢 Rich", etc.
        if "🟢 rich" in text_lower or "quality** | 🟢" in text_lower:
            result["research_confidence"] = "rich"
        elif "🟡 basic" in text_lower or "quality** | 🟡" in text_lower:
            result["research_confidence"] = "basic"
        elif "🔴 minimal" in text_lower or "quality** | 🔴" in text_lower:
            result["research_confidence"] = "minimal"
        
        # Note: Opening lines, discovery questions, and things to avoid
        # are now generated in the Preparation phase, not in contact research
        result["opening_suggestions"] = None
        result["questions_to_ask"] = None
        result["topics_to_avoid"] = None
        
        logger.info(f"[CONTACT_ANALYZER] Parsed: style={result.get('communication_style')}, "
                   f"authority={result.get('decision_authority')}, drivers={result.get('probable_drivers')}")
        
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
        """
        Get company context from a research brief.
        
        Includes leadership data extracted from the research to reduce
        the need for additional web searches during contact analysis.
        """
        try:
            response = self.supabase.table("research_briefs")\
                .select("company_name, country, city, brief_content, research_data")\
                .eq("id", research_id)\
                .single()\
                .execute()
            
            if response.data:
                data = response.data
                research_data = data.get("research_data", {}) or {}
                brief_content = data.get("brief_content", "") or ""
                
                # Extract leadership info from research for context
                leadership_info = self._extract_leadership_from_research(
                    research_data, 
                    brief_content
                )
                
                return {
                    "company_name": data.get("company_name"),
                    "country": data.get("country"),
                    "city": data.get("city"),
                    "brief_content": brief_content,
                    "industry": research_data.get("industry"),
                    "leadership": leadership_info  # Add leadership context
                }
            return {}
        except Exception as e:
            logger.error(f"Error getting company context: {e}")
            return {}
    
    def _extract_leadership_from_research(
        self,
        research_data: Dict[str, Any],
        brief_content: str
    ) -> List[Dict[str, str]]:
        """
        Extract leadership information from research data and brief content.
        
        This provides pre-researched context about company leaders to reduce
        the need for web searches during contact analysis.
        """
        import re
        
        leaders = []
        seen_names = set()
        
        # Method 1: Extract from structured research_data
        for key in ["executives", "leadership", "team", "people"]:
            if key in research_data and isinstance(research_data[key], list):
                for person in research_data[key]:
                    if isinstance(person, dict) and person.get("name"):
                        name = person["name"]
                        if name.lower() not in seen_names:
                            seen_names.add(name.lower())
                            leaders.append({
                                "name": name,
                                "title": person.get("title") or person.get("role"),
                                "linkedin_url": person.get("linkedin_url"),
                                "background": person.get("background")
                            })
        
        # Method 2: Parse leadership section from brief_content markdown
        if brief_content and len(leaders) < 3:
            # Look for leadership tables in the brief
            # Pattern: | Name | Title | LinkedIn | ...
            table_pattern = r'\|\s*([^|]+?)\s*\|\s*([^|]+?)\s*\|\s*([^|]*?)\s*\|'
            
            in_leadership_section = False
            for line in brief_content.split('\n'):
                # Check if we're entering a leadership section
                if any(marker in line.lower() for marker in [
                    'leadership', 'executive', 'c-suite', 'mensen & macht',
                    'people & power', 'leiderschap'
                ]):
                    in_leadership_section = True
                    continue
                
                # Check if we're leaving the section
                if in_leadership_section and line.startswith('##'):
                    if not any(marker in line.lower() for marker in [
                        'leadership', 'executive', 'mensen', 'people'
                    ]):
                        in_leadership_section = False
                        continue
                
                # Parse table rows in leadership section
                if in_leadership_section:
                    match = re.match(table_pattern, line)
                    if match:
                        col1, col2, col3 = [c.strip() for c in match.groups()]
                        
                        # Skip headers
                        if any(h in col1.lower() for h in ['naam', 'name', '---', 'titel']):
                            continue
                        
                        # Determine name, title, linkedin
                        name = None
                        title = None
                        linkedin = None
                        
                        for col in [col1, col2, col3]:
                            if 'linkedin.com/in/' in col.lower():
                                linkedin = col
                            elif not name and len(col) > 2 and not col.startswith('http'):
                                name = col.strip('*')
                            elif name and not title and len(col) > 2:
                                title = col.strip('*')
                        
                        if name and name.lower() not in seen_names:
                            seen_names.add(name.lower())
                            leaders.append({
                                "name": name,
                                "title": title,
                                "linkedin_url": linkedin
                            })
        
        logger.info(f"Extracted {len(leaders)} leaders from research for contact context")
        return leaders[:10]  # Limit to top 10
    
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

