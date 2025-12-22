"""
Magic Onboarding Service - AI-powered profile generation from minimal input.

This service transforms the traditional 19-question interview into a magic experience:
1. User provides LinkedIn URL (sales) or company name (company)
2. AI automatically researches and extracts all available information
3. User reviews and confirms the generated profile
4. Gaps are clearly identified for optional user input

The output maintains full compatibility with the existing profile structure.
"""

import os
import json
import asyncio
import logging
from typing import Dict, Any, Optional, List, Tuple
from dataclasses import dataclass, field, asdict
from anthropic import AsyncAnthropic

from app.services.people_search_provider import get_people_search_provider, PeopleSearchProvider
from app.services.company_lookup import get_company_lookup, CompanyLookupService
from app.services.exa_research_service import ExaComprehensiveResearcher

logger = logging.getLogger(__name__)


@dataclass
class ProfileField:
    """Represents a field in the profile with its source and confidence."""
    value: Any
    source: str  # 'linkedin', 'website', 'ai_derived', 'user_input', 'default'
    confidence: float  # 0.0 - 1.0
    editable: bool = True
    required: bool = False


@dataclass
class MagicSalesProfileResult:
    """Result of magic sales profile generation."""
    success: bool
    profile_data: Dict[str, Any] = field(default_factory=dict)
    field_sources: Dict[str, ProfileField] = field(default_factory=dict)
    missing_fields: List[str] = field(default_factory=list)
    linkedin_data: Dict[str, Any] = field(default_factory=dict)
    error: Optional[str] = None
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to JSON-serializable dict."""
        return {
            "success": self.success,
            "profile_data": self.profile_data,
            "field_sources": {
                k: {
                    "value": v.value,
                    "source": v.source,
                    "confidence": v.confidence,
                    "editable": v.editable,
                    "required": v.required
                } for k, v in self.field_sources.items()
            },
            "missing_fields": self.missing_fields,
            "linkedin_data": self.linkedin_data,
            "error": self.error
        }


@dataclass
class MagicCompanyProfileResult:
    """Result of magic company profile generation."""
    success: bool
    profile_data: Dict[str, Any] = field(default_factory=dict)
    field_sources: Dict[str, ProfileField] = field(default_factory=dict)
    missing_fields: List[str] = field(default_factory=list)
    company_options: List[Dict[str, Any]] = field(default_factory=list)
    selected_company: Optional[Dict[str, Any]] = None
    website_data: Dict[str, Any] = field(default_factory=dict)
    error: Optional[str] = None
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to JSON-serializable dict."""
        return {
            "success": self.success,
            "profile_data": self.profile_data,
            "field_sources": {
                k: {
                    "value": v.value,
                    "source": v.source,
                    "confidence": v.confidence,
                    "editable": v.editable,
                    "required": v.required
                } for k, v in self.field_sources.items()
            },
            "missing_fields": self.missing_fields,
            "company_options": self.company_options,
            "selected_company": self.selected_company,
            "website_data": self.website_data,
            "error": self.error
        }


class MagicOnboardingService:
    """
    Magic Onboarding Service - AI-powered profile generation.
    
    Leverages existing research capabilities (LinkedIn enrichment, company lookup)
    to automatically generate high-quality profiles from minimal user input.
    """
    
    def __init__(self):
        """Initialize the service with required clients."""
        self.anthropic = AsyncAnthropic(api_key=os.getenv("ANTHROPIC_API_KEY"))
        self.model = "claude-sonnet-4-20250514"
        self.people_search: PeopleSearchProvider = get_people_search_provider()
        self.company_lookup: CompanyLookupService = get_company_lookup()
    
    # ==========================================
    # SALES PROFILE MAGIC
    # ==========================================
    
    async def generate_sales_profile_from_linkedin(
        self,
        linkedin_url: str,
        user_name: Optional[str] = None,
        company_name: Optional[str] = None
    ) -> MagicSalesProfileResult:
        """
        Generate a complete sales profile from a LinkedIn URL.
        
        Flow:
        1. Enrich LinkedIn profile (get full content)
        2. Use Claude to extract and synthesize profile data
        3. Identify fields that couldn't be extracted
        4. Return structured result with source tracking
        
        Args:
            linkedin_url: LinkedIn profile URL
            user_name: Optional name hint (if known from auth)
            company_name: Optional company hint
            
        Returns:
            MagicSalesProfileResult with profile data and metadata
        """
        logger.info(f"[MAGIC_ONBOARDING] Starting sales profile generation from: {linkedin_url}")
        
        try:
            # Step 1: Enrich LinkedIn profile
            linkedin_data = await self.people_search.enrich_profile(linkedin_url)
            
            if not linkedin_data.get("success"):
                logger.warning(f"[MAGIC_ONBOARDING] LinkedIn enrichment failed: {linkedin_data.get('error')}")
                return MagicSalesProfileResult(
                    success=False,
                    error=f"Could not retrieve LinkedIn profile: {linkedin_data.get('error', 'Unknown error')}"
                )
            
            logger.info(f"[MAGIC_ONBOARDING] LinkedIn data retrieved successfully")
            
            # Step 2: Use Claude to synthesize profile
            profile_data, field_sources = await self._synthesize_sales_profile(
                linkedin_data=linkedin_data,
                user_name_hint=user_name,
                company_name_hint=company_name
            )
            
            # Step 3: Identify missing/uncertain fields
            missing_fields = self._identify_missing_sales_fields(profile_data, field_sources)
            
            logger.info(f"[MAGIC_ONBOARDING] Sales profile generated. Missing fields: {missing_fields}")
            
            return MagicSalesProfileResult(
                success=True,
                profile_data=profile_data,
                field_sources=field_sources,
                missing_fields=missing_fields,
                linkedin_data=linkedin_data
            )
            
        except Exception as e:
            logger.error(f"[MAGIC_ONBOARDING] Error generating sales profile: {e}")
            return MagicSalesProfileResult(
                success=False,
                error=str(e)
            )
    
    async def _synthesize_sales_profile(
        self,
        linkedin_data: Dict[str, Any],
        user_name_hint: Optional[str] = None,
        company_name_hint: Optional[str] = None
    ) -> Tuple[Dict[str, Any], Dict[str, ProfileField]]:
        """
        Use Claude to synthesize a complete sales profile from LinkedIn data.
        
        Returns both the profile data and source tracking for each field.
        """
        # Prepare LinkedIn context
        about_section = linkedin_data.get("about_section", "")
        experience_section = linkedin_data.get("experience_section", "")
        skills = linkedin_data.get("skills", [])
        headline = linkedin_data.get("headline", "")
        ai_summary = linkedin_data.get("ai_summary", "")
        raw_text = linkedin_data.get("raw_text", "")
        experience_years = linkedin_data.get("experience_years")
        location = linkedin_data.get("location", "")
        
        prompt = f"""Analyze this LinkedIn profile and create a comprehensive sales profile.

LINKEDIN DATA:
- Headline: {headline}
- Location: {location}
- Experience Years: {experience_years or 'Unknown'}
- Skills: {', '.join(skills[:15]) if skills else 'None listed'}

About Section:
{about_section or 'Not available'}

Experience:
{experience_section or 'Not available'}

AI Summary (from search provider):
{ai_summary or 'Not available'}

Additional Context:
- User name hint: {user_name_hint or 'Not provided'}
- Company hint: {company_name_hint or 'Not provided'}

ANALYSIS APPROACH:
You can DERIVE insights from analyzing the LinkedIn data:

1. DIRECT EXTRACTION (confidence 0.95+):
   - Name, role, experience years, skills, location

2. SMART ANALYSIS (confidence 0.7-0.85):
   - communication_style: Analyze HOW they write their about section and experience. Formal/casual? Direct/elaborate? Data-driven/relationship-focused?
   - email_tone: Based on their writing style - formal writers likely write formal emails
   - writing_length_preference: Is their about section concise or detailed?
   - target_industries: From companies in their experience
   - target_company_sizes: From company types in their experience (startups vs enterprises)
   - sales_methodology: If explicitly mentioned, or infer from role type (Enterprise = likely consultative, SMB = likely transactional)

3. REASONABLE INFERENCE (confidence 0.5-0.7):
   - uses_emoji: Rare in professional LinkedIn → default false unless visible
   - preferred_meeting_types: Based on role seniority and sales type

4. CANNOT DETERMINE (set to null):
   - quarterly_goals: Private information
   - areas_to_improve: Nobody shares weaknesses publicly

Return ONLY valid JSON with this exact structure:
{{
    "full_name": "Extract from profile or use hint",
    "role": "Current job title",
    "experience_years": number or null,
    "sales_methodology": "Analyze from experience: SPIN, Challenger, Consultative, Solution Selling, Transactional, or null if unclear",
    "methodology_description": "Brief description based on their experience pattern",
    "communication_style": "Analyze their writing: Direct, Consultative, Relationship-focused, Data-driven, Formal, or null",
    "style_notes": "Observations about their professional style based on profile",
    "strengths": ["3-5 strengths from skills and experience"],
    "areas_to_improve": [],
    "target_industries": ["Industries from their experience history"],
    "target_regions": ["Regions from location and experience"],
    "target_company_sizes": ["Infer from company types in experience: SMB, Mid-Market, Enterprise"],
    "quarterly_goals": null,
    "preferred_meeting_types": ["Infer from role: discovery, demo, negotiation, closing"],
    "email_tone": "Analyze their writing style: direct, warm, formal, casual, professional",
    "uses_emoji": false,
    "email_signoff": "Infer from formality: Best regards, Cheers, Thanks, Kind regards",
    "writing_length_preference": "Analyze their about section length: concise or detailed",
    "ai_summary": "2-3 sentence professional summary based on profile analysis",
    "sales_narrative": "4-6 paragraph narrative about this sales professional. Write in third person, based on actual profile data.",
    
    "_field_confidence": {{
        "full_name": 0.0-1.0,
        "role": 0.0-1.0,
        "experience_years": 0.0-1.0,
        "sales_methodology": 0.0-1.0,
        "communication_style": 0.0-1.0,
        "strengths": 0.0-1.0,
        "target_industries": 0.0-1.0,
        "target_regions": 0.0-1.0,
        "target_company_sizes": 0.0-1.0,
        "email_tone": 0.0-1.0,
        "writing_length_preference": 0.0-1.0
    }}
}}

CONFIDENCE GUIDELINES:
- 0.95+ = Directly stated in profile (name, headline, skills listed)
- 0.8-0.9 = Clearly visible in experience/about (industries worked in)
- 0.6-0.8 = Reasonably analyzed from writing style and experience pattern
- 0.4-0.6 = Educated inference based on role type and seniority
- Use null if there's truly no basis for analysis"""

        try:
            response = await self.anthropic.messages.create(
                model=self.model,
                max_tokens=3000,
                messages=[{"role": "user", "content": prompt}]
            )
            
            content = response.content[0].text.strip()
            
            # Clean markdown if present
            if content.startswith("```"):
                content = content.split("```")[1]
                if content.startswith("json"):
                    content = content[4:]
            if content.endswith("```"):
                content = content[:-3]
            
            result = json.loads(content)
            
            # Extract confidence scores
            confidence_data = result.pop("_field_confidence", {})
            
            # Fields that can NEVER be derived (always null)
            never_derivable = {"quarterly_goals", "areas_to_improve"}
            
            # Build field sources with honest confidence scoring
            field_sources = {}
            for field_name, value in result.items():
                if field_name.startswith("_"):
                    continue
                
                # Get the AI-reported confidence
                confidence = confidence_data.get(field_name, 0.5)
                
                # Determine source based on confidence and field type
                if field_name in never_derivable:
                    source = "not_available"
                    confidence = 0.0
                elif value is None or value == "" or (isinstance(value, list) and len(value) == 0):
                    source = "needs_input"
                    confidence = 0.0
                elif confidence >= 0.9:
                    source = "linkedin"  # Direct extraction
                elif confidence >= 0.7:
                    source = "linkedin_analyzed"  # Analyzed from profile text
                elif confidence >= 0.5:
                    source = "ai_inferred"  # Reasonable inference
                else:
                    source = "low_confidence"  # Needs review
                
                field_sources[field_name] = ProfileField(
                    value=value,
                    source=source,
                    confidence=confidence,
                    editable=True,
                    required=field_name in ["full_name", "role"]
                )
            
            # Build style_guide from analyzed preferences
            # Calculate average confidence for style-related fields
            style_fields = ["email_tone", "communication_style", "writing_length_preference"]
            style_confidences = [confidence_data.get(f, 0.5) for f in style_fields]
            avg_style_confidence = sum(style_confidences) / len(style_confidences) if style_confidences else 0.5
            
            result["style_guide"] = {
                "tone": result.get("email_tone") or "professional",
                "formality": "professional",
                "language_style": "business",
                "persuasion_style": self._derive_persuasion_style(result.get("sales_methodology")),
                "emoji_usage": result.get("uses_emoji") if result.get("uses_emoji") is not None else False,
                "signoff": result.get("email_signoff") or "Best regards",
                "writing_length": result.get("writing_length_preference") or "concise",
                "confidence_score": round(avg_style_confidence, 2)
            }
            
            return result, field_sources
            
        except json.JSONDecodeError as e:
            logger.error(f"[MAGIC_ONBOARDING] Failed to parse Claude response: {e}")
            # Return basic profile with what we have
            return self._build_fallback_sales_profile(linkedin_data, user_name_hint), {}
        except Exception as e:
            logger.error(f"[MAGIC_ONBOARDING] Error in synthesis: {e}")
            return self._build_fallback_sales_profile(linkedin_data, user_name_hint), {}
    
    def _derive_persuasion_style(self, methodology: Optional[str]) -> str:
        """Derive persuasion style from sales methodology."""
        if not methodology:
            return "logic"
        
        methodology_lower = methodology.lower()
        
        if "challenger" in methodology_lower or "spin" in methodology_lower:
            return "logic"
        elif "story" in methodology_lower or "narrative" in methodology_lower:
            return "story"
        elif "reference" in methodology_lower or "social" in methodology_lower:
            return "reference"
        else:
            return "logic"
    
    def _build_fallback_sales_profile(
        self,
        linkedin_data: Dict[str, Any],
        user_name_hint: Optional[str] = None
    ) -> Dict[str, Any]:
        """Build a basic profile when AI synthesis fails - use available data with defaults."""
        skills = linkedin_data.get("skills", [])[:5]
        location = linkedin_data.get("location")
        headline = linkedin_data.get("headline", "")
        
        return {
            # Direct from LinkedIn
            "full_name": user_name_hint or None,
            "role": headline or None,
            "experience_years": linkedin_data.get("experience_years"),
            "strengths": skills if skills else [],
            "target_regions": [location] if location else [],
            "target_industries": [],
            
            # Needs user input or analysis
            "sales_methodology": None,
            "methodology_description": None,
            "communication_style": None,
            "style_notes": None,
            "areas_to_improve": [],
            "target_company_sizes": [],
            "quarterly_goals": None,
            "preferred_meeting_types": ["discovery", "demo"],  # Safe defaults
            "email_tone": "professional",  # Safe default
            "uses_emoji": False,  # Conservative default
            "email_signoff": "Best regards",  # Professional default
            "writing_length_preference": "concise",  # Safe default
            
            # Summary
            "ai_summary": f"Sales professional{' with expertise in ' + ', '.join(skills[:3]) if skills else ''}." if skills else f"Sales professional based in {location}." if location else "Sales professional.",
            "sales_narrative": f"This sales professional works as {headline}." if headline else None,
            
            # Style guide with safe defaults
            "style_guide": {
                "tone": "professional",
                "formality": "professional",
                "language_style": "business",
                "persuasion_style": "logic",
                "emoji_usage": False,
                "signoff": "Best regards",
                "writing_length": "concise",
                "confidence_score": 0.3  # Low confidence - needs review
            }
        }
    
    def _identify_missing_sales_fields(
        self,
        profile_data: Dict[str, Any],
        field_sources: Dict[str, ProfileField]
    ) -> List[str]:
        """
        Identify fields that need user review.
        
        Returns fields that are:
        - Empty/null
        - Have low confidence (< 0.5)
        - Are required but uncertain
        """
        missing = []
        
        # Required fields - must have high confidence
        required_fields = ["full_name", "role"]
        
        # Important fields - should be reviewed if low confidence
        important_fields = [
            "sales_methodology",
            "communication_style",
            "target_industries",
            "target_company_sizes",
            "email_tone",
        ]
        
        # Fields that are always private (never available from LinkedIn)
        always_missing = ["quarterly_goals"]
        
        # Check required fields
        for field_name in required_fields:
            source = field_sources.get(field_name)
            value = profile_data.get(field_name)
            
            if not value or (source and source.confidence < 0.7):
                missing.append(field_name)
        
        # Check important fields - flag if empty or low confidence
        for field_name in important_fields:
            source = field_sources.get(field_name)
            value = profile_data.get(field_name)
            
            is_empty = value is None or value == "" or (isinstance(value, list) and len(value) == 0)
            is_low_confidence = source and source.confidence < 0.5
            
            if is_empty or is_low_confidence:
                missing.append(field_name)
        
        # Always add private fields
        for field_name in always_missing:
            if field_name not in missing:
                missing.append(field_name)
        
        return missing
    
    # ==========================================
    # COMPANY PROFILE MAGIC
    # ==========================================
    
    async def search_company_options(
        self,
        company_name: str,
        country: str
    ) -> MagicCompanyProfileResult:
        """
        Search for company options matching the given name.
        
        This is the first step - user selects the correct company from options.
        
        Args:
            company_name: Name of the company
            country: Country where company is located
            
        Returns:
            MagicCompanyProfileResult with company options
        """
        logger.info(f"[MAGIC_ONBOARDING] Searching for company: {company_name} in {country}")
        
        try:
            # Use existing company lookup service
            options = await self.company_lookup.search_company_options(company_name, country)
            
            if not options:
                logger.warning(f"[MAGIC_ONBOARDING] No company options found for: {company_name}")
                return MagicCompanyProfileResult(
                    success=True,
                    company_options=[],
                    error=None
                )
            
            logger.info(f"[MAGIC_ONBOARDING] Found {len(options)} company options")
            
            return MagicCompanyProfileResult(
                success=True,
                company_options=options
            )
            
        except Exception as e:
            logger.error(f"[MAGIC_ONBOARDING] Error searching companies: {e}")
            return MagicCompanyProfileResult(
                success=False,
                error=str(e)
            )
    
    async def generate_company_profile(
        self,
        company_name: str,
        website: Optional[str] = None,
        linkedin_url: Optional[str] = None,
        country: Optional[str] = None
    ) -> MagicCompanyProfileResult:
        """
        Generate a complete company profile from company name and URLs.
        
        Flow:
        1. Research company website (if available)
        2. Use Claude with web knowledge to fill gaps
        3. Return structured profile with source tracking
        
        Args:
            company_name: Company name
            website: Optional company website URL
            linkedin_url: Optional LinkedIn company page URL
            country: Optional country hint
            
        Returns:
            MagicCompanyProfileResult with profile data
        """
        logger.info(f"[MAGIC_ONBOARDING] Generating company profile for: {company_name}")
        
        try:
            # Step 1: Research the company using Claude with web context
            profile_data, field_sources = await self._synthesize_company_profile(
                company_name=company_name,
                website=website,
                linkedin_url=linkedin_url,
                country=country
            )
            
            # Step 2: Identify missing fields
            missing_fields = self._identify_missing_company_fields(profile_data, field_sources)
            
            logger.info(f"[MAGIC_ONBOARDING] Company profile generated. Missing: {missing_fields}")
            
            return MagicCompanyProfileResult(
                success=True,
                profile_data=profile_data,
                field_sources=field_sources,
                missing_fields=missing_fields,
                selected_company={
                    "company_name": company_name,
                    "website": website,
                    "linkedin_url": linkedin_url,
                    "location": country
                }
            )
            
        except Exception as e:
            logger.error(f"[MAGIC_ONBOARDING] Error generating company profile: {e}")
            return MagicCompanyProfileResult(
                success=False,
                error=str(e)
            )
    
    async def _research_company_with_exa(
        self,
        company_name: str,
        website: Optional[str] = None,
        country: Optional[str] = None
    ) -> Optional[str]:
        """
        Research a company using Exa web search.
        
        Uses the same Exa service as prospect research for consistent,
        high-quality, factual data collection.
        
        Args:
            company_name: Name of the company
            website: Optional company website URL
            country: Optional country hint
            
        Returns:
            Markdown formatted research data, or None if unavailable
        """
        try:
            exa_researcher = ExaComprehensiveResearcher()
            
            if not exa_researcher.is_available:
                logger.warning("[MAGIC_ONBOARDING] Exa researcher not available, falling back to AI-only")
                return None
            
            logger.info(f"[MAGIC_ONBOARDING] Starting Exa research for company: {company_name}")
            
            # Use the full Exa research pipeline (34 searches)
            # This is the same quality as prospect research
            result = await exa_researcher.research_company(
                company_name=company_name,
                country=country,
                website_url=website
            )
            
            if not result.success:
                logger.warning(f"[MAGIC_ONBOARDING] Exa research failed: {result.errors}")
                return None
            
            logger.info(
                f"[MAGIC_ONBOARDING] Exa research complete. "
                f"Topics completed: {result.topics_completed}, Failed: {result.topics_failed}"
            )
            
            return result.markdown_output
            
        except Exception as e:
            logger.error(f"[MAGIC_ONBOARDING] Exa research error: {e}")
            return None
    
    async def _synthesize_company_profile(
        self,
        company_name: str,
        website: Optional[str] = None,
        linkedin_url: Optional[str] = None,
        country: Optional[str] = None
    ) -> Tuple[Dict[str, Any], Dict[str, ProfileField]]:
        """
        Research and synthesize a company profile using Exa web search + Claude analysis.
        
        Flow:
        1. Exa web research (same as prospect research) for factual data
        2. Claude synthesis of research data into structured profile
        
        This approach ensures factual, verifiable data instead of AI hallucinations.
        """
        # Step 1: Research company with Exa (real web search)
        research_data = await self._research_company_with_exa(
            company_name=company_name,
            website=website,
            country=country
        )
        
        # Determine if we have web research or need to rely on AI knowledge
        has_research = research_data is not None and len(research_data) > 500
        
        if has_research:
            logger.info(f"[MAGIC_ONBOARDING] Using Exa research data ({len(research_data)} chars) for synthesis")
            prompt = f"""You are an expert at analyzing B2B company research. Based on the following REAL WEB RESEARCH DATA, create a comprehensive company profile.

## COMPANY BEING ANALYZED
- Company Name: {company_name}
- Website: {website or 'Not provided'}
- LinkedIn: {linkedin_url or 'Not provided'}
- Country: {country or 'Not provided'}

## WEB RESEARCH DATA
The following is real data collected from web searches about this company:

{research_data}

---

## TASK
Analyze the research data above and extract/synthesize a structured company profile.
- ONLY use information that is supported by the research data
- If something is not in the research, mark confidence as low or omit
- Do NOT hallucinate or invent information not present in the research

Return ONLY valid JSON with this exact structure:"""
            source_type = "web_research"
            base_confidence = 0.85
        else:
            logger.warning(f"[MAGIC_ONBOARDING] No Exa research available, using AI knowledge only")
            prompt = f"""You are an expert at researching B2B companies. Analyze the following company and create a profile.

## COMPANY BEING ANALYZED
- Company Name: {company_name}
- Website: {website or 'Not provided'}
- LinkedIn: {linkedin_url or 'Not provided'}
- Country: {country or 'Not provided'}

## TASK
Based on your training knowledge about this company (if any), create a profile.
- Be honest about what you know vs don't know
- Mark confidence appropriately
- If you don't have specific knowledge, focus on industry patterns

Return ONLY valid JSON with this exact structure:"""
            source_type = "ai_knowledge"
            base_confidence = 0.5
        
        # Complete the prompt with JSON structure
        prompt += f"""
{{
    "company_name": "{company_name}",
    "industry": "Primary industry/sector",
    "company_size": "Estimated size (e.g., '10-50', '50-200', '200-1000', '1000+')",
    "headquarters": "Location if known",
    "website": "{website or ''}",
    "products": [
        {{
            "name": "Product/Service name",
            "description": "Brief description",
            "value_proposition": "Key value",
            "target_persona": "Who it's for"
        }}
    ],
    "core_value_props": ["List of 3-5 core value propositions"],
    "differentiators": ["What makes them unique"],
    "unique_selling_points": "Summary of USPs",
    "ideal_customer_profile": {{
        "industries": ["Target industries"],
        "company_sizes": ["Target company sizes"],
        "regions": ["Target regions"],
        "pain_points": ["Problems they solve"],
        "buying_triggers": ["What triggers buying"]
    }},
    "buyer_personas": [
        {{
            "title": "Job title of typical buyer",
            "seniority": "C-level, VP, Director, Manager",
            "pain_points": ["Their challenges"],
            "goals": ["Their objectives"],
            "objections": ["Common objections"]
        }}
    ],
    "case_studies": [],
    "competitors": ["Known competitors"],
    "competitive_advantages": "How they stand out",
    "typical_sales_cycle": "Estimated sales cycle (e.g., '1-3 months')",
    "average_deal_size": null,
    "ai_summary": "2-3 sentence summary of the company",
    "company_narrative": "4-6 paragraph narrative about this company. Write professionally and compellingly.",
    
    "_field_confidence": {{
        "company_name": 1.0,
        "industry": 0.0-1.0,
        "products": 0.0-1.0,
        "core_value_props": 0.0-1.0,
        "differentiators": 0.0-1.0,
        "ideal_customer_profile": 0.0-1.0,
        "buyer_personas": 0.0-1.0,
        "competitors": 0.0-1.0
    }}
}}

Confidence scoring guidelines:
- 0.9+ = Directly stated in research data OR you have specific verified knowledge
- 0.6-0.8 = Strongly implied by research data OR reasonable inference
- 0.3-0.5 = Weak inference, may need user verification
- Leave fields empty/null if truly unknown"""

        try:
            response = await self.anthropic.messages.create(
                model=self.model,
                max_tokens=4000,
                messages=[{"role": "user", "content": prompt}]
            )
            
            content = response.content[0].text.strip()
            
            # Clean markdown
            if content.startswith("```"):
                content = content.split("```")[1]
                if content.startswith("json"):
                    content = content[4:]
            if content.endswith("```"):
                content = content[:-3]
            
            result = json.loads(content)
            
            # Extract confidence scores
            confidence_data = result.pop("_field_confidence", {})
            
            # Build field sources with appropriate confidence based on data source
            field_sources = {}
            for field_name, value in result.items():
                if field_name.startswith("_"):
                    continue
                
                # Get AI-reported confidence, adjust based on source type
                ai_confidence = confidence_data.get(field_name, 0.5)
                
                if has_research:
                    # Web research - boost confidence, cap at 0.95
                    source = source_type
                    confidence = min(0.95, ai_confidence * 1.1)
                else:
                    # AI-only - reduce confidence
                    source = source_type
                    confidence = ai_confidence * 0.7
                
                # Website was provided, higher confidence for those fields
                if website and field_name in ["website", "company_name"]:
                    source = "user_provided"
                    confidence = 1.0
                
                field_sources[field_name] = ProfileField(
                    value=value,
                    source=source,
                    confidence=confidence,
                    editable=True,
                    required=field_name in ["company_name", "industry"]
                )
            
            return result, field_sources
            
        except json.JSONDecodeError as e:
            logger.error(f"[MAGIC_ONBOARDING] Failed to parse company profile: {e}")
            return self._build_fallback_company_profile(company_name, website), {}
        except Exception as e:
            logger.error(f"[MAGIC_ONBOARDING] Error in company synthesis: {e}")
            return self._build_fallback_company_profile(company_name, website), {}
    
    def _build_fallback_company_profile(
        self,
        company_name: str,
        website: Optional[str] = None
    ) -> Dict[str, Any]:
        """Build a basic company profile when AI synthesis fails."""
        return {
            "company_name": company_name,
            "industry": None,
            "company_size": None,
            "headquarters": None,
            "website": website,
            "products": [],
            "core_value_props": [],
            "differentiators": [],
            "unique_selling_points": None,
            "ideal_customer_profile": {},
            "buyer_personas": [],
            "case_studies": [],
            "competitors": [],
            "competitive_advantages": None,
            "typical_sales_cycle": None,
            "average_deal_size": None,
            "ai_summary": f"{company_name} is building their company profile.",
            "company_narrative": "This company is setting up their profile. More details will be added after review."
        }
    
    def _identify_missing_company_fields(
        self,
        profile_data: Dict[str, Any],
        field_sources: Dict[str, ProfileField]
    ) -> List[str]:
        """Identify company fields that need user input."""
        missing = []
        
        # Critical fields
        critical_fields = [
            "industry",
            "products",
            "core_value_props",
        ]
        
        # Optional but valuable
        optional_fields = [
            "ideal_customer_profile",
            "typical_sales_cycle",
            "average_deal_size",
            "case_studies",
        ]
        
        for field_name in critical_fields:
            source = field_sources.get(field_name)
            value = profile_data.get(field_name)
            
            is_empty = (
                value is None or 
                (isinstance(value, str) and not value.strip()) or
                (isinstance(value, list) and len(value) == 0) or
                (isinstance(value, dict) and len(value) == 0)
            )
            
            if is_empty or (source and source.confidence < 0.5):
                missing.append(field_name)
        
        for field_name in optional_fields:
            value = profile_data.get(field_name)
            is_empty = (
                value is None or 
                (isinstance(value, list) and len(value) == 0) or
                (isinstance(value, dict) and len(value) == 0)
            )
            if is_empty:
                missing.append(field_name)
        
        return missing


# Singleton instance
_magic_onboarding_service: Optional[MagicOnboardingService] = None


def get_magic_onboarding_service() -> MagicOnboardingService:
    """Get or create the MagicOnboardingService singleton."""
    global _magic_onboarding_service
    if _magic_onboarding_service is None:
        _magic_onboarding_service = MagicOnboardingService()
    return _magic_onboarding_service

