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
    
    async def get_profile_info(
        self,
        name: str,
        company_name: str,
        role: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Get enriched profile information for a person.
        
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
        result = await self.search_person(
            name=name,
            role=role,
            company_name=company_name,
            max_results=3
        )
        
        if result.matches:
            best_match = result.matches[0]
            return {
                "found": True,
                "name": best_match.name,
                "headline": best_match.headline or best_match.title,
                "title": best_match.title,
                "company": best_match.company,
                "location": best_match.location,
                "about": best_match.summary,
                "experience_years": best_match.experience_years,
                "skills": best_match.skills or [],
                "linkedin_url": best_match.linkedin_url,
                "raw_text": best_match.raw_text,
                "source": result.source,
                "confidence": best_match.confidence
            }
        
        return {
            "found": False,
            "source": result.source
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
        
        Uses semantic search with people category for optimal results.
        """
        # Build optimized query for people search
        query_parts = [f'"{name}"']
        if role:
            query_parts.append(role)
        if company_name:
            query_parts.append(f'at {company_name}')
        
        query = " ".join(query_parts)
        
        # Execute search with people category
        # Run in thread pool since exa_py is sync
        loop = asyncio.get_event_loop()
        
        def do_search():
            # Use search_and_contents to get full profile data in one call
            return self._primary_client.search_and_contents(
                query,
                type="auto",
                category="linkedin profile",
                num_results=max_results * 2,  # Get extra to filter
                text={"max_characters": 3000},  # More profile text for better context
                summary={
                    "query": "Extract: current role, company, experience summary, skills, and notable achievements"
                },  # AI-generated summary of profile
                livecrawl="fallback",  # Fresh data if cache is stale
            )
        
        response = await loop.run_in_executor(None, do_search)
        
        # Parse results
        matches = []
        for result in response.results:
            url = result.url or ""
            
            # Only include LinkedIn profile URLs
            if "linkedin.com/in/" not in url.lower():
                continue
            
            # Parse name and title from result title
            # Typical format: "Name - Title | LinkedIn"
            title_parts = (result.title or "").split(" - ")
            parsed_name = title_parts[0].strip() if title_parts else name
            parsed_title = None
            if len(title_parts) > 1:
                parsed_title = title_parts[1].split(" | ")[0].strip()
            
            # Extract all available profile content
            profile_text = getattr(result, 'text', None) or ""
            ai_summary = getattr(result, 'summary', None) or ""
            
            # Parse structured info from profile text
            parsed_info = self._parse_linkedin_text(profile_text)
            
            # Build comprehensive summary
            summary = None
            if ai_summary:
                # AI summary is most valuable - contains extracted insights
                summary = ai_summary
            elif profile_text:
                # Fall back to truncated profile text
                summary = profile_text[:800].strip()
                if len(profile_text) > 800:
                    summary += "..."
            
            # Calculate confidence based on name match + content
            confidence = self._calculate_confidence(
                search_name=name,
                found_name=parsed_name,
                search_company=company_name,
                found_text=(result.title or "") + " " + profile_text
            )
            
            matches.append(ProfileMatch(
                name=parsed_name,
                title=parsed_title or parsed_info.get("current_role"),
                company=parsed_info.get("company") or company_name,
                location=parsed_info.get("location"),
                linkedin_url=url,
                headline=parsed_title or parsed_info.get("headline"),
                summary=summary,
                experience_years=parsed_info.get("experience_years"),
                skills=parsed_info.get("skills") or [],
                confidence=confidence,
                match_reason=self._get_match_reason(confidence, company_name),
                source="primary",
                raw_text=profile_text[:2000] if profile_text else None  # Keep for Claude
            ))
        
        # Sort by confidence and limit
        matches.sort(key=lambda m: m.confidence, reverse=True)
        matches = matches[:max_results]
        
        return ProfileSearchResult(
            matches=matches,
            query_used=query,
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
                        
                        # Parse name from title
                        parsed_name = title.split(" - ")[0].strip() if " - " in title else title.split(" | ")[0].strip()
                        parsed_title = None
                        if " - " in title:
                            parts = title.split(" - ")
                            if len(parts) > 1:
                                parsed_title = parts[1].split(" | ")[0].strip()
                        
                        confidence = self._calculate_confidence(
                            search_name=name,
                            found_name=parsed_name,
                            search_company=company_name,
                            found_text=title + " " + description
                        )
                        
                        matches.append(ProfileMatch(
                            name=parsed_name,
                            title=parsed_title,
                            company=company_name,
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
        """Calculate match confidence score."""
        confidence = 0.5
        
        search_lower = search_name.lower()
        found_lower = found_name.lower()
        
        # Name matching
        search_parts = set(search_lower.split())
        found_parts = set(found_lower.split())
        
        # Remove common non-name words
        skip_words = {'van', 'de', 'der', 'den', 'het', 'rc', 're', 'mba', 'msc', 'dr', 'mr'}
        search_parts = search_parts - skip_words
        found_parts = found_parts - skip_words
        
        common_parts = search_parts & found_parts
        
        if search_lower == found_lower:
            confidence = 0.95
        elif len(common_parts) >= 2:
            confidence = 0.90
        elif len(common_parts) == 1:
            confidence = 0.70
        else:
            confidence = 0.30
        
        # Boost if company matches
        if search_company and search_company.lower() in found_text.lower():
            confidence = min(1.0, confidence + 0.05)
        
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
        
        Extracts:
        - current_role: Current job title
        - company: Current company
        - location: Geographic location
        - headline: Profile headline
        - experience_years: Estimated years of experience
        - skills: List of mentioned skills
        """
        import re
        
        result = {
            "current_role": None,
            "company": None,
            "location": None,
            "headline": None,
            "experience_years": None,
            "skills": []
        }
        
        if not text:
            return result
        
        lines = text.split('\n')
        
        # Common patterns in LinkedIn profile text
        for i, line in enumerate(lines[:20]):  # First 20 lines usually have key info
            line = line.strip()
            
            # Skip empty lines
            if not line:
                continue
            
            # Location patterns
            if not result["location"]:
                loc_patterns = [
                    r'(?:Location|Locatie|Based in)[:\s]+(.+)',
                    r'(Amsterdam|Rotterdam|Utrecht|Den Haag|Eindhoven|Netherlands|Nederland|Belgium|België)',
                    r'(\w+,\s*\w+\s*(?:Area|Region|Metro))',
                ]
                for pattern in loc_patterns:
                    match = re.search(pattern, line, re.IGNORECASE)
                    if match:
                        result["location"] = match.group(1).strip()
                        break
            
            # Experience patterns
            if "Experience" in line or "Ervaring" in line:
                # Next lines might contain role info
                if i + 1 < len(lines):
                    next_line = lines[i + 1].strip()
                    if next_line and len(next_line) < 100:
                        result["current_role"] = next_line
            
            # Years of experience
            years_match = re.search(r'(\d+)\+?\s*(?:years?|jaar|yrs)', line, re.IGNORECASE)
            if years_match and not result["experience_years"]:
                result["experience_years"] = int(years_match.group(1))
        
        # Extract skills from common skill sections
        skills_section = re.search(r'(?:Skills?|Vaardigheden)[:\s]*(.+?)(?:\n\n|$)', text, re.IGNORECASE | re.DOTALL)
        if skills_section:
            skills_text = skills_section.group(1)
            # Split on common delimiters
            skills = re.split(r'[,•·|\n]+', skills_text)
            result["skills"] = [s.strip() for s in skills if s.strip() and len(s.strip()) < 50][:10]
        
        return result
    
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
