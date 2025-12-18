"""
People Search Provider - Unified interface for people/profile search.

This service provides an abstraction layer for searching LinkedIn profiles
and people information. The underlying provider can be swapped without
affecting the rest of the codebase.

Current implementation: Neural search with 1B+ indexed profiles
Fallback: Brave Search API

Key features:
- Semantic name matching (handles variations)
- Role-based filtering
- Company context awareness
- Profile content extraction (headline, summary)
"""

import os
import logging
import asyncio
from typing import Optional, List, Dict, Any
from dataclasses import dataclass

logger = logging.getLogger(__name__)


@dataclass
class ProfileMatch:
    """A matched LinkedIn profile with enriched data."""
    name: str
    title: Optional[str] = None
    company: Optional[str] = None
    location: Optional[str] = None
    linkedin_url: Optional[str] = None
    headline: Optional[str] = None
    summary: Optional[str] = None  # AI-generated or extracted summary
    experience_years: Optional[int] = None
    skills: Optional[List[str]] = None
    confidence: float = 0.5
    match_reason: str = "Name match"
    source: str = "search"  # "search", "research", "fallback"
    raw_text: Optional[str] = None  # Full profile text for Claude analysis


@dataclass
class ProfileSearchResult:
    """Result of a profile search."""
    matches: List[ProfileMatch]
    query_used: str
    source: str  # "primary", "fallback", "research"
    success: bool = True
    error: Optional[str] = None


class PeopleSearchProvider:
    """
    Unified people search interface with intelligent fallback.
    
    Priority:
    1. Primary neural search (1B+ profiles, semantic matching)
    2. Fallback web search (Brave API)
    
    Usage:
        provider = get_people_search_provider()
        result = await provider.search_person(
            name="John Smith",
            role="VP of Sales",
            company_name="Acme Corp"
        )
    """
    
    def __init__(self):
        """Initialize search providers."""
        # Primary provider
        self._primary_client = None
        self._primary_api_key = os.getenv("EXA_API_KEY")
        
        # Fallback provider
        self._fallback_api_key = os.getenv("BRAVE_API_KEY")
        
        if self._primary_api_key:
            try:
                from exa_py import Exa
                self._primary_client = Exa(api_key=self._primary_api_key)
                logger.info("[PEOPLE_SEARCH] Primary provider initialized")
            except Exception as e:
                logger.warning(f"[PEOPLE_SEARCH] Primary provider init failed: {e}")
        else:
            logger.warning("[PEOPLE_SEARCH] No primary API key - will use fallback only")
        
        if not self._fallback_api_key:
            logger.warning("[PEOPLE_SEARCH] No fallback API key configured")
    
    @property
    def has_primary(self) -> bool:
        """Check if primary provider is available."""
        return self._primary_client is not None
    
    @property
    def has_fallback(self) -> bool:
        """Check if fallback provider is available."""
        return bool(self._fallback_api_key)
    
    async def search_person(
        self,
        name: str,
        role: Optional[str] = None,
        company_name: Optional[str] = None,
        max_results: int = 5
    ) -> ProfileSearchResult:
        """
        Search for a person's LinkedIn profile.
        
        Args:
            name: Full name of the person
            role: Job title/role (optional, improves accuracy)
            company_name: Company they work at (optional, improves accuracy)
            max_results: Maximum number of matches to return
            
        Returns:
            ProfileSearchResult with list of matches sorted by confidence
        """
        # Build search query
        query_parts = [name]
        if role:
            query_parts.append(role)
        if company_name:
            query_parts.append(f"at {company_name}")
        query = " ".join(query_parts)
        
        logger.info(f"[PEOPLE_SEARCH] Searching for: {query}")
        
        # Try primary provider first
        if self.has_primary:
            try:
                result = await self._search_primary(name, role, company_name, max_results)
                if result.matches:
                    logger.info(f"[PEOPLE_SEARCH] Primary found {len(result.matches)} matches")
                    return result
                else:
                    logger.info("[PEOPLE_SEARCH] Primary returned no matches, trying fallback")
            except Exception as e:
                logger.warning(f"[PEOPLE_SEARCH] Primary search failed: {e}")
        
        # Fallback to Brave
        if self.has_fallback:
            try:
                result = await self._search_fallback(name, role, company_name, max_results)
                logger.info(f"[PEOPLE_SEARCH] Fallback found {len(result.matches)} matches")
                return result
            except Exception as e:
                logger.error(f"[PEOPLE_SEARCH] Fallback search failed: {e}")
        
        # No results from any provider
        return ProfileSearchResult(
            matches=[],
            query_used=query,
            source="none",
            success=False,
            error="No search providers available or all failed"
        )
    
    async def enrich_profile(self, linkedin_url: str) -> Dict[str, Any]:
        """
        Fetch full content for a selected LinkedIn profile.
        
        Called AFTER user selects a profile from search results.
        This is where we spend credits on text + summary retrieval.
        
        Cost: ~$0.002 per profile (text + summary for 1 page)
        
        Returns dict with structured profile data:
        - success: bool
        - about_section: str (the actual LinkedIn About/Summary text written by the person)
        - experience_section: str (career history text)
        - skills: list[str] (extracted skills)
        - ai_summary: str (AI-generated summary from Exa)
        - headline: str (profile headline)
        - location: str
        - experience_years: int
        - raw_text: str (full profile text for Claude analysis)
        """
        if not self._primary_client:
            return {"success": False, "error": "No search provider available"}
        
        try:
            loop = asyncio.get_event_loop()
            
            # Normalize URL: convert regional subdomains to www
            # e.g., nl.linkedin.com → www.linkedin.com
            normalized_url = self._normalize_linkedin_url(linkedin_url)
            logger.info(f"[PEOPLE_SEARCH] Enriching profile: {normalized_url}")
            
            def do_get_contents():
                # Get full content for this specific profile
                return self._primary_client.get_contents(
                    urls=[normalized_url],
                    text={"max_characters": 4000},  # Increased for better section extraction
                    summary={
                        "query": "Summarize this person's professional background: current role, key achievements, expertise areas, and career trajectory"
                    },
                )
            
            response = await loop.run_in_executor(None, do_get_contents)
            
            if not response.results:
                return {"success": False, "error": "No content retrieved"}
            
            result = response.results[0]
            profile_text = getattr(result, 'text', None) or ""
            ai_summary = getattr(result, 'summary', None) or ""
            
            # Parse structured info from profile text
            parsed_info = self._parse_linkedin_text(profile_text)
            
            # Also extract skills from AI summary if not found in profile text
            skills = parsed_info.get("skills") or []
            experience_years = parsed_info.get("experience_years")
            
            if ai_summary:
                # Try to extract additional info from AI summary
                import re
                
                # Extract skills from AI summary if we don't have enough
                if len(skills) < 3:
                    # Common skill patterns in summaries
                    skill_patterns = [
                        r'(?:expertise|skills?|specializ\w+|proficient)\s*(?:in|:)?\s*([^.]+)',
                        r'(?:experienced|background)\s+in\s+([^.]+)',
                    ]
                    for pattern in skill_patterns:
                        match = re.search(pattern, ai_summary, re.IGNORECASE)
                        if match:
                            extracted = match.group(1)
                            # Split on common delimiters
                            new_skills = re.split(r'[,;and]+', extracted)
                            for s in new_skills:
                                s = s.strip()
                                if s and 3 <= len(s) <= 40 and s not in skills:
                                    skills.append(s)
                            break
                
                # Extract years from AI summary if not found
                if not experience_years:
                    years_match = re.search(r'(\d+)\+?\s*(?:years?|jaar)', ai_summary, re.IGNORECASE)
                    if years_match:
                        try:
                            experience_years = int(years_match.group(1))
                        except ValueError:
                            pass
            
            logger.info(f"[PEOPLE_SEARCH] Enriched profile: {linkedin_url[:50]}...")
            logger.info(f"[PEOPLE_SEARCH] - About section: {'Found' if parsed_info.get('about_section') else 'Not found'}")
            logger.info(f"[PEOPLE_SEARCH] - Experience section: {'Found' if parsed_info.get('experience_section') else 'Not found'}")
            logger.info(f"[PEOPLE_SEARCH] - Skills: {len(skills)} found")
            logger.info(f"[PEOPLE_SEARCH] - Experience years: {experience_years}")
            logger.info(f"[PEOPLE_SEARCH] - Raw text length: {len(profile_text)} chars")
            
            return {
                "success": True,
                # NEW: Separate sections for better UI display
                "about_section": parsed_info.get("about_section"),  # LinkedIn About text
                "experience_section": parsed_info.get("experience_section"),  # Career history
                "skills": skills[:15],  # Limit to 15 skills
                "ai_summary": ai_summary,  # Exa's AI summary (for extra context)
                # Existing fields
                "headline": parsed_info.get("headline"),
                "location": parsed_info.get("location"),
                "experience_years": experience_years,
                # Full text for Claude analysis
                "raw_text": profile_text[:3000] if profile_text else None
            }
            
        except Exception as e:
            logger.error(f"[PEOPLE_SEARCH] Enrich failed: {e}")
            return {"success": False, "error": str(e)}
    
    async def get_profile_info(
        self,
        name: str,
        company_name: str,
        role: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Get enriched profile information for a person.
        
        This combines search + enrich for use in contact_analyzer.
        For contact search flow, use search_person() + enrich_profile() separately.
        
        Returns dict with:
        - found: bool
        - name: str
        - headline: str (job title/description)
        - about: str (AI-generated profile summary)
        - linkedin_url: str
        - location: str
        - experience_years: int
        - skills: list[str]
        - raw_text: str (full profile text for Claude analysis)
        - source: str
        - confidence: float
        """
        # First do light search
        result = await self.search_person(
            name=name,
            role=role,
            company_name=company_name,
            max_results=3
        )
        
        if not result.matches:
            return {"found": False, "source": result.source}
        
        best_match = result.matches[0]
        
        # Then enrich the best match
        if best_match.linkedin_url:
            enriched = await self.enrich_profile(best_match.linkedin_url)
            if enriched.get("success"):
                return {
                    "found": True,
                    "name": best_match.name,
                    "headline": enriched.get("headline") or best_match.headline or best_match.title,
                    "title": best_match.title,
                    "company": best_match.company,
                    "location": enriched.get("location"),
                    "about": enriched.get("summary"),
                    "experience_years": enriched.get("experience_years"),
                    "skills": enriched.get("skills") or [],
                    "linkedin_url": best_match.linkedin_url,
                    "raw_text": enriched.get("raw_text"),
                    "source": result.source,
                    "confidence": best_match.confidence
                }
        
        # Fallback: return what we have from light search
        return {
            "found": True,
            "name": best_match.name,
            "headline": best_match.headline or best_match.title,
            "title": best_match.title,
            "company": best_match.company,
            "location": None,
            "about": None,
            "experience_years": None,
            "skills": [],
            "linkedin_url": best_match.linkedin_url,
            "raw_text": None,
            "source": result.source,
            "confidence": best_match.confidence
        }
    
    async def _search_primary(
        self,
        name: str,
        role: Optional[str],
        company_name: Optional[str],
        max_results: int
    ) -> ProfileSearchResult:
        """
        Search using primary neural search provider.
        
        OPTIMIZED: 
        - Neural search with LinkedIn domain filter for EXACT name matching
        - Multiple query strategies run in sequence for better recall
        - Deep Search was too fuzzy (found "Kobus Boons" instead of "Kobus Dijkhorst")
        
        Cost: ~$0.005 per search x number of queries
        """
        # Clean the name for better matching
        clean_name = self._clean_name(name)
        
        # Build multiple query strategies - we'll run them in sequence
        # Neural search is more precise than Deep Search for exact name matches
        queries = []
        
        # Strategy 1: Exact name with LinkedIn context (best for unique names)
        queries.append(f'"{clean_name}" LinkedIn')
        
        # Strategy 2: Name with company (if person is still there)
        if company_name:
            queries.append(f'"{clean_name}" {company_name}')
        
        # Strategy 3: Just the name (for people with multiple companies like Kobus)
        queries.append(f'"{clean_name}"')
        
        loop = asyncio.get_event_loop()
        all_matches = []
        seen_urls = set()
        
        # Log with both logger and print to ensure visibility in Railway
        log_msg = f"[PEOPLE_SEARCH] Neural search with {len(queries)} queries for '{clean_name}'"
        logger.info(log_msg)
        print(log_msg, flush=True)
        
        for query in queries:
            print(f"[PEOPLE_SEARCH] Trying query: {query}", flush=True)
            
            def do_search(q=query):
                # Keyword search = literal text matching (NOT semantic)
                # Neural was matching "Kobus" to "Kube" (Kubernetes) - WRONG!
                return self._primary_client.search_and_contents(
                    q,
                    type="keyword",  # Keyword = exact text matching
                    include_domains=["linkedin.com"],  # Only LinkedIn
                    num_results=max_results * 2,
                    text={"max_characters": 300},
                )
            
            try:
                response = await loop.run_in_executor(None, do_search)
                
                # Log how many results Exa returned
                raw_count = len(response.results) if response.results else 0
                print(f"[PEOPLE_SEARCH] Query '{query}' returned {raw_count} results", flush=True)
                
                for result in response.results:
                    url = result.url or ""
                    result_title = result.title or ""
                    
                    # Log ALL results to debug
                    print(f"[PEOPLE_SEARCH] Raw result: {result_title[:60]}... -> {url[:80]}", flush=True)
                    
                    # Only include personal LinkedIn profile URLs (not company pages)
                    if "/in/" not in url.lower():
                        print(f"[PEOPLE_SEARCH] SKIP (no /in/): {url[:60]}", flush=True)
                        continue
                    
                    # Normalize LinkedIn URL for deduplication
                    url_slug = self._extract_linkedin_slug(url)
                    if url_slug in seen_urls:
                        continue
                    seen_urls.add(url_slug)
                    
                    # Get result text for better matching
                    result_text = getattr(result, 'text', '') or ""
                    combined_text = f"{result_title} {result_text}".lower()
                    
                    # Parse name, title, and company from result
                    parsed_name, parsed_title, parsed_company = self._parse_linkedin_title(
                        result_title, name, company_name
                    )
                    
                    # Calculate confidence with improved matching
                    confidence = self._calculate_confidence_v2(
                        search_name=clean_name,
                        found_name=parsed_name,
                        search_company=company_name,
                        search_role=role,
                        found_text=combined_text
                    )
                    
                    # Log each result for debugging
                    print(f"[PEOPLE_SEARCH] Result: '{result_title}' -> conf={confidence:.2f}, url={url}", flush=True)
                    
                    # Only include if confidence is reasonable
                    if confidence < 0.4:
                        print(f"[PEOPLE_SEARCH] FILTERED (conf < 0.4): {parsed_name}", flush=True)
                        continue
                    
                    all_matches.append(ProfileMatch(
                        name=parsed_name,
                        title=parsed_title,
                        company=parsed_company,
                        location=None,
                        linkedin_url=url,
                        headline=parsed_title,
                        summary=None,
                        experience_years=None,
                        skills=None,
                        confidence=confidence,
                        match_reason=self._get_match_reason(confidence, company_name),
                        source="primary",
                        raw_text=None
                    ))
                
            except Exception as e:
                print(f"[PEOPLE_SEARCH] Query '{query}' failed: {e}", flush=True)
                continue
        
        # Log total matches found
        print(f"[PEOPLE_SEARCH] Total matches after all queries: {len(all_matches)}", flush=True)
        
        # Sort by confidence and limit
        all_matches.sort(key=lambda m: m.confidence, reverse=True)
        matches = all_matches[:max_results]
        
        return ProfileSearchResult(
            matches=matches,
            query_used=queries[0] if queries else "",
            source="primary",
            success=True
        )
    
    async def _search_fallback(
        self,
        name: str,
        role: Optional[str],
        company_name: Optional[str],
        max_results: int
    ) -> ProfileSearchResult:
        """
        Search using fallback Brave Search API.
        """
        import aiohttp
        
        # Clean name for search
        clean_name = self._clean_name(name)
        
        # Build search queries
        queries = []
        if company_name:
            queries.append(f'site:linkedin.com/in "{clean_name}" "{company_name}"')
            if role:
                queries.append(f'site:linkedin.com/in "{clean_name}" "{role}"')
        queries.append(f'site:linkedin.com/in "{clean_name}"')
        
        matches = []
        
        async with aiohttp.ClientSession() as session:
            headers = {
                "Accept": "application/json",
                "X-Subscription-Token": self._fallback_api_key
            }
            
            for query in queries:
                if len(matches) >= max_results:
                    break
                
                params = {"q": query, "count": 10}
                
                async with session.get(
                    "https://api.search.brave.com/res/v1/web/search",
                    headers=headers,
                    params=params
                ) as response:
                    if response.status != 200:
                        continue
                    
                    data = await response.json()
                    results = data.get("web", {}).get("results", [])
                    
                    for result in results:
                        url = result.get("url", "")
                        if "linkedin.com/in/" not in url.lower():
                            continue
                        
                        # Already have this URL?
                        if any(m.linkedin_url == url for m in matches):
                            continue
                        
                        title = result.get("title", "")
                        description = result.get("description", "")
                        
                        # Parse name, title, and company from result
                        parsed_name, parsed_title, parsed_company = self._parse_linkedin_title(
                            title, name, company_name
                        )
                        
                        confidence = self._calculate_confidence_v2(
                            search_name=name,
                            found_name=parsed_name,
                            search_company=company_name,
                            search_role=role,
                            found_text=title + " " + description
                        )
                        
                        matches.append(ProfileMatch(
                            name=parsed_name,
                            title=parsed_title,
                            company=parsed_company,  # Use parsed company
                            linkedin_url=url,
                            headline=parsed_title,
                            summary=description[:500] if description else None,
                            confidence=confidence,
                            match_reason=self._get_match_reason(confidence, company_name),
                            source="fallback"
                        ))
                        
                        if len(matches) >= max_results:
                            break
        
        # Sort by confidence
        matches.sort(key=lambda m: m.confidence, reverse=True)
        
        return ProfileSearchResult(
            matches=matches,
            query_used=queries[0] if queries else "",
            source="fallback",
            success=True
        )
    
    def _calculate_confidence(
        self,
        search_name: str,
        found_name: str,
        search_company: Optional[str],
        found_text: str
    ) -> float:
        """Calculate match confidence score (legacy method)."""
        return self._calculate_confidence_v2(
            search_name=search_name,
            found_name=found_name,
            search_company=search_company,
            search_role=None,
            found_text=found_text
        )
    
    def _calculate_confidence_v2(
        self,
        search_name: str,
        found_name: str,
        search_company: Optional[str],
        search_role: Optional[str],
        found_text: str
    ) -> float:
        """
        Calculate match confidence score with improved matching.
        
        Scoring:
        - Name match: up to 60 points (required)
        - Company match: up to 25 points (bonus)
        - Role match: up to 15 points (bonus)
        
        Returns confidence as 0.0-1.0 float.
        """
        score = 0
        
        search_lower = search_name.lower().strip()
        found_lower = found_name.lower().strip()
        text_lower = found_text.lower()
        
        # === NAME MATCHING (up to 60 points) ===
        # Get name parts, handling Dutch names (van, de, der, etc.)
        prefixes = {'van', 'de', 'der', 'den', 'het', 'la', 'le', 'von'}
        noise = {'rc', 're', 'mba', 'msc', 'bsc', 'phd', 'dr', 'mr', 'mrs', 'drs', 'ir', 'prof'}
        
        search_parts = [p for p in search_lower.split() if p not in noise]
        found_parts = [p for p in found_lower.split() if p not in noise]
        
        # Get significant name parts (first name, last name - skip prefixes for matching)
        search_significant = [p for p in search_parts if p not in prefixes]
        found_significant = [p for p in found_parts if p not in prefixes]
        
        # Exact match
        if search_lower == found_lower:
            score += 60
        else:
            # Check first name
            if search_significant and found_significant:
                if search_significant[0] == found_significant[0]:
                    score += 25  # First name match
                elif search_significant[0] in text_lower:
                    score += 20  # First name found in text
            
            # Check last name
            if len(search_significant) >= 2 and len(found_significant) >= 2:
                if search_significant[-1] == found_significant[-1]:
                    score += 25  # Last name match
                elif search_significant[-1] in text_lower:
                    score += 20  # Last name found in text
            elif len(search_significant) >= 2:
                # Check if last name appears anywhere in found text
                if search_significant[-1] in text_lower:
                    score += 20
            
            # Bonus for multiple matching parts
            common = set(search_significant) & set(found_significant)
            if len(common) >= 2:
                score += 10
        
        # === COMPANY MATCHING (up to 25 points) ===
        if search_company:
            company_lower = search_company.lower()
            # Exact company match
            if company_lower in text_lower:
                score += 25
            else:
                # Partial company match (first significant word)
                company_words = [w for w in company_lower.split() if len(w) > 2]
                if company_words and company_words[0] in text_lower:
                    score += 15
        
        # === ROLE MATCHING (up to 15 points) ===
        if search_role:
            role_lower = search_role.lower()
            role_keywords = [w for w in role_lower.split() if len(w) > 2]
            
            # Check for role keywords in text
            role_matches = sum(1 for kw in role_keywords if kw in text_lower)
            if role_matches >= 2:
                score += 15
            elif role_matches == 1:
                score += 10
        
        # Convert to 0-1 scale (max score = 100)
        confidence = min(score / 100.0, 1.0)
        
        logger.debug(
            f"[PEOPLE_SEARCH] Confidence for '{found_name}': {confidence:.2f} "
            f"(name={search_name}, company={search_company})"
        )
        
        return round(confidence, 2)
    
    def _get_match_reason(self, confidence: float, company_name: Optional[str]) -> str:
        """Get human-readable match reason."""
        if confidence >= 0.90:
            reason = "Strong name match"
        elif confidence >= 0.70:
            reason = "Partial name match"
        else:
            reason = "Weak match - verify manually"
        
        if company_name and confidence >= 0.85:
            reason += " + Company context"
        
        return reason
    
    def _parse_linkedin_text(self, text: str) -> Dict[str, Any]:
        """
        Parse structured information from LinkedIn profile text.
        
        LinkedIn profiles typically follow this structure:
        [Name]
        [Headline]
        [Location]
        
        About
        [About text - user's own description]
        
        Experience
        [Company] · [Role]
        [Period]
        [Description]
        ...
        
        Skills
        [Skill 1], [Skill 2], ...
        
        Extracts:
        - about_section: The user's About/Summary text
        - experience_section: Career history
        - skills: List of skills
        - location: Geographic location
        - headline: Profile headline (first line after name)
        - experience_years: Estimated years of experience
        """
        import re
        
        result = {
            "about_section": None,      # NEW: The actual LinkedIn About text
            "experience_section": None,  # NEW: Career experience text
            "skills": [],
            "location": None,
            "headline": None,
            "experience_years": None,
            "current_role": None,
            "company": None,
        }
        
        if not text:
            return result
        
        # Normalize text - remove excessive whitespace
        text = re.sub(r'\n{3,}', '\n\n', text)
        lines = text.split('\n')
        
        # === EXTRACT LOCATION from first 15 lines ===
        for line in lines[:15]:
            line = line.strip()
            if not line:
                continue
            
            loc_patterns = [
                r'(?:Location|Locatie|Based in)[:\s]+(.+)',
                r'^([\w\s]+,\s*(?:Netherlands|Nederland|Belgium|België|Germany|Deutschland|UK|United Kingdom|France|USA|United States))$',
                r'^(Amsterdam|Rotterdam|Utrecht|Den Haag|The Hague|Eindhoven|Groningen|Maastricht)(?:\s+(?:Area|Region|Metro))?$',
                r'^([\w\s]+,\s*[\w\s]+\s*(?:Area|Region|Metro))$',
            ]
            for pattern in loc_patterns:
                match = re.search(pattern, line, re.IGNORECASE)
                if match:
                    result["location"] = match.group(1).strip()
                    break
            if result["location"]:
                break
        
        # === FIND SECTION BOUNDARIES ===
        # LinkedIn sections are typically: About, Experience, Education, Skills, etc.
        section_markers = [
            (r'^About\s*$', 'about'),
            (r'^Over\s*$', 'about'),  # Dutch
            (r'^Summary\s*$', 'about'),
            (r'^Experience\s*$', 'experience'),
            (r'^Ervaring\s*$', 'experience'),  # Dutch
            (r'^Werkervaring\s*$', 'experience'),  # Dutch
            (r'^Education\s*$', 'education'),
            (r'^Opleiding\s*$', 'education'),  # Dutch
            (r'^Skills?\s*$', 'skills'),
            (r'^Vaardigheden\s*$', 'skills'),  # Dutch
            (r'^Top Skills?\s*$', 'skills'),
            (r'^Licenses?\s*(?:&|and)?\s*Certifications?\s*$', 'certifications'),
            (r'^Languages?\s*$', 'languages'),
            (r'^Talen\s*$', 'languages'),  # Dutch
            (r'^Interests?\s*$', 'interests'),
            (r'^Recommendations?\s*$', 'recommendations'),
            (r'^Publications?\s*$', 'publications'),
            (r'^Projects?\s*$', 'projects'),
            (r'^Activity\s*$', 'activity'),
        ]
        
        sections = {}
        current_section = 'header'
        section_start = 0
        
        for i, line in enumerate(lines):
            line_stripped = line.strip()
            for pattern, section_name in section_markers:
                if re.match(pattern, line_stripped, re.IGNORECASE):
                    # Save previous section
                    if current_section:
                        sections[current_section] = {
                            'start': section_start,
                            'end': i
                        }
                    current_section = section_name
                    section_start = i + 1
                    break
        
        # Save last section
        if current_section:
            sections[current_section] = {
                'start': section_start,
                'end': len(lines)
            }
        
        # === EXTRACT ABOUT SECTION ===
        if 'about' in sections:
            start = sections['about']['start']
            end = sections['about']['end']
            about_lines = [l.strip() for l in lines[start:end] if l.strip()]
            if about_lines:
                about_text = '\n'.join(about_lines)
                # Clean up: remove "see more" links, etc.
                about_text = re.sub(r'(?:\.{3})?see more.*$', '', about_text, flags=re.IGNORECASE)
                about_text = re.sub(r'Show less.*$', '', about_text, flags=re.IGNORECASE)
                result["about_section"] = about_text.strip()[:1500]  # Limit size
        
        # === EXTRACT EXPERIENCE SECTION ===
        if 'experience' in sections:
            start = sections['experience']['start']
            end = sections['experience']['end']
            exp_lines = lines[start:end]
            
            # Build experience text, limit to first 3-4 positions
            experience_parts = []
            current_position = []
            position_count = 0
            
            for line in exp_lines:
                line = line.strip()
                if not line:
                    if current_position:
                        experience_parts.append('\n'.join(current_position))
                        current_position = []
                        position_count += 1
                        if position_count >= 4:  # Limit to 4 positions
                            break
                else:
                    current_position.append(line)
            
            if current_position and position_count < 4:
                experience_parts.append('\n'.join(current_position))
            
            if experience_parts:
                result["experience_section"] = '\n\n'.join(experience_parts)[:1500]  # Limit size
            
            # Extract years of experience from experience section
            full_exp_text = '\n'.join(exp_lines)
            years_patterns = [
                r'(\d+)\+?\s*(?:years?|jaar|yrs)\s*(?:of\s+)?(?:experience)?',
                r'(?:total|totaal)[:\s]+(\d+)\s*(?:years?|jaar)',
            ]
            for pattern in years_patterns:
                match = re.search(pattern, full_exp_text, re.IGNORECASE)
                if match:
                    try:
                        result["experience_years"] = int(match.group(1))
                        break
                    except ValueError:
                        pass
        
        # === EXTRACT SKILLS ===
        if 'skills' in sections:
            start = sections['skills']['start']
            end = sections['skills']['end']
            skills_text = '\n'.join(lines[start:end])
            
            # Split on common delimiters
            skill_candidates = re.split(r'[,•·|\n]+', skills_text)
            skills = []
            for s in skill_candidates:
                s = s.strip()
                # Filter: reasonable length, not a number, not common noise
                if s and 3 <= len(s) <= 50 and not s.isdigit():
                    # Skip common noise
                    noise = ['see more', 'show all', 'endorsements', 'endorsed by']
                    if not any(n in s.lower() for n in noise):
                        skills.append(s)
            result["skills"] = skills[:15]  # Top 15 skills
        
        # === EXTRACT HEADLINE (usually line 2-3 after name) ===
        # First non-empty line that looks like a headline
        for line in lines[1:8]:
            line = line.strip()
            if line and 10 < len(line) < 150:
                # Skip if it's a section marker or location
                is_section = any(re.match(p, line, re.IGNORECASE) for p, _ in section_markers)
                is_location = result["location"] and result["location"] in line
                if not is_section and not is_location:
                    result["headline"] = line
                    break
        
        # === ESTIMATE EXPERIENCE YEARS from dates if not found ===
        if not result["experience_years"] and result["experience_section"]:
            # Look for year patterns like "2015 - Present" or "2010 - 2020"
            year_matches = re.findall(r'\b(19|20)\d{2}\b', result["experience_section"])
            if year_matches:
                years = [int(y) for y in year_matches if 1980 <= int(y) <= 2025]
                if years:
                    from datetime import datetime
                    current_year = datetime.now().year
                    earliest = min(years)
                    result["experience_years"] = current_year - earliest
        
        return result
    
    def _extract_linkedin_slug(self, url: str) -> str:
        """
        Extract normalized LinkedIn profile slug from URL for deduplication.
        
        Handles various formats:
        - https://www.linkedin.com/in/username/
        - https://nl.linkedin.com/in/username
        - http://linkedin.com/in/username?param=value
        
        Returns: "linkedin.com/in/username" (normalized slug for comparison)
        """
        import re
        
        if not url:
            return ""
        
        url_lower = url.lower()
        
        # Extract the /in/username part
        match = re.search(r'/in/([a-zA-Z0-9\-]+)', url_lower)
        if match:
            username = match.group(1).rstrip('-')
            return f"linkedin.com/in/{username}"
        
        return url_lower.rstrip('/')
    
    def _normalize_linkedin_url(self, url: str) -> str:
        """
        Normalize LinkedIn URL to standard format for API calls.
        
        Converts regional subdomains (nl., de., uk., etc.) to www.
        This ensures consistent URL format for Exa's get_contents API.
        
        Examples:
        - https://nl.linkedin.com/in/username → https://www.linkedin.com/in/username
        - https://de.linkedin.com/in/username → https://www.linkedin.com/in/username
        - http://linkedin.com/in/username → https://www.linkedin.com/in/username
        """
        import re
        
        if not url:
            return url
        
        # Extract username from URL
        match = re.search(r'/in/([a-zA-Z0-9\-]+)', url)
        if match:
            username = match.group(1).rstrip('-')
            # Return normalized URL with www subdomain
            return f"https://www.linkedin.com/in/{username}"
        
        # If no match, return original URL
        return url
    
    def _parse_linkedin_title(
        self,
        title: str,
        fallback_name: str,
        search_company: Optional[str]
    ) -> tuple:
        """
        Parse name, title, and company from LinkedIn result title.
        
        Common formats:
        - "John Smith - CEO at Acme Corp | LinkedIn"
        - "John Smith - CEO | LinkedIn"  
        - "John Smith | LinkedIn"
        - "John Smith - Acme Corp | LinkedIn"
        
        Returns: (name, title, company)
        """
        import re
        
        if not title:
            return fallback_name, None, None  # Don't use search_company as fallback
        
        # Remove LinkedIn suffix
        title = re.sub(r'\s*\|\s*LinkedIn.*$', '', title, flags=re.IGNORECASE)
        title = title.strip()
        
        name = fallback_name
        parsed_title = None
        company = None
        
        # Split on " - " to get name and rest
        if " - " in title:
            parts = title.split(" - ", 1)
            name = parts[0].strip()
            rest = parts[1].strip() if len(parts) > 1 else ""
            
            # Check for "Title at Company" or "Title @ Company"
            at_match = re.search(r'^(.+?)\s+(?:at|@|bij)\s+(.+)$', rest, re.IGNORECASE)
            if at_match:
                parsed_title = at_match.group(1).strip()
                company = at_match.group(2).strip()
            else:
                # Just a title, no company in the format
                parsed_title = rest
        else:
            # No " - ", just name
            name = title
        
        # DON'T fallback to search_company - only show what's actually in the profile
        # If someone searches "Dave Jansen at Cmotions" but finds a Dave Jansen at "Remote Dev",
        # we shouldn't display "Cmotions" - that's misleading
        
        # Clean up: if title equals company name, it's probably not a real title
        if parsed_title and company:
            if parsed_title.lower() == company.lower():
                parsed_title = None
        
        return name, parsed_title, company
    
    def _clean_name(self, name: str) -> str:
        """Clean name by removing degree abbreviations and garbage."""
        import re
        
        if not name:
            return name
        
        patterns = [
            r'\bRc\s*Re\b', r'\bRC\s*RE\b', r'\bRA\b', r'\bAA\b',
            r'\bMBA\b', r'\bMSc\b', r'\bBSc\b', r'\bPhD\b',
            r'\bDr\.?\b', r'\bMr\.?\b', r'\bMrs\.?\b', r'\bDrs\.?\b',
            r'\bIr\.?\b', r'\bProf\.?\b', r'\bCPA\b', r'\bCFA\b',
            r'[\(\)]+', r'[\[\]]+', r'\|.*$', r'-\s*$',
        ]
        
        cleaned = name
        for pattern in patterns:
            cleaned = re.sub(pattern, '', cleaned, flags=re.IGNORECASE)
        
        return ' '.join(cleaned.split()).strip()


# Singleton instance
_provider: Optional[PeopleSearchProvider] = None


def get_people_search_provider() -> PeopleSearchProvider:
    """Get or create the PeopleSearchProvider singleton."""
    global _provider
    if _provider is None:
        _provider = PeopleSearchProvider()
    return _provider
