"""
Contact Search Service - Search for LinkedIn profiles matching a contact.

This service uses Gemini with Google Search (primary, much cheaper) or Claude 
with web search (fallback) to find possible LinkedIn matches for a contact person,
returning multiple results with confidence scores.

Also provides research executives matching to cross-validate contacts.
"""

import os
import json
import re
import logging
from typing import Optional, List, Dict, Any
from pydantic import BaseModel

logger = logging.getLogger(__name__)


class ContactMatch(BaseModel):
    """A potential LinkedIn match for a contact."""
    name: str
    title: Optional[str] = None
    company: Optional[str] = None
    location: Optional[str] = None
    linkedin_url: Optional[str] = None
    headline: Optional[str] = None
    confidence: float = 0.5
    match_reason: str = "Name match"
    from_research: bool = False  # True if this was found in research data


class ContactSearchResult(BaseModel):
    """Result of a contact search."""
    matches: List[ContactMatch] = []
    search_query_used: str = ""
    search_source: str = "gemini"  # "gemini", "claude", or "research"
    error: Optional[str] = None


class ResearchExecutive(BaseModel):
    """An executive found in research data."""
    name: str
    title: Optional[str] = None
    linkedin_url: Optional[str] = None
    background: Optional[str] = None
    relevance: Optional[str] = None


class ContactSearchService:
    """
    Service to search for LinkedIn profiles matching a contact person.
    
    Uses Gemini with Google Search (primary) or Claude with web search (fallback)
    to find possible matches, returning up to 5 results with confidence scores.
    
    Also extracts known executives from research data for cross-validation.
    """
    
    def __init__(self):
        self.gemini_api_key = os.getenv("GOOGLE_AI_API_KEY") or os.getenv("GOOGLE_API_KEY")
        self.anthropic_api_key = os.getenv("ANTHROPIC_API_KEY")
        
        if not self.gemini_api_key and not self.anthropic_api_key:
            logger.warning("No API keys set - contact search will fail")
    
    async def search_contact(
        self,
        name: str,
        role: Optional[str] = None,
        company_name: Optional[str] = None,
        company_linkedin_url: Optional[str] = None,
        research_executives: Optional[List[Dict[str, Any]]] = None
    ) -> ContactSearchResult:
        """
        Search for LinkedIn profiles matching the given contact info.
        
        Uses a tiered approach:
        1. First check against known executives from research (instant, free)
        2. Then use Gemini with Google Search (fast, cheap)
        3. Fall back to Claude if Gemini fails (slower, more expensive)
        
        Args:
            name: Contact's full name (required)
            role: Contact's job title/role (optional, helps narrow search)
            company_name: Company name for context (optional but recommended)
            company_linkedin_url: Company LinkedIn URL (optional, improves accuracy)
            research_executives: List of executives from research data (optional)
        
        Returns:
            ContactSearchResult with up to 5 matches sorted by confidence
        """
        matches: List[ContactMatch] = []
        search_source = "gemini"
        search_query = f'"{name}" "{company_name or ""}" linkedin'
        
        # Step 1: Check against known research executives first (free, instant)
        if research_executives:
            research_matches = self._match_against_research(
                name, role, company_name, research_executives
            )
            if research_matches:
                matches.extend(research_matches)
                logger.info(f"[CONTACT_SEARCH] Found {len(research_matches)} matches from research")
        
        # Step 2: Use Gemini with Google Search (primary - cheap)
        if self.gemini_api_key:
            try:
                gemini_matches = await self._search_with_gemini(
                    name, role, company_name, company_linkedin_url
                )
                if gemini_matches:
                    # Merge with existing matches, avoiding duplicates
                    matches = self._merge_matches(matches, gemini_matches)
                    search_source = "gemini"
                    logger.info(f"[CONTACT_SEARCH] Gemini found {len(gemini_matches)} matches")
            except Exception as e:
                logger.warning(f"[CONTACT_SEARCH] Gemini failed: {e}, trying Claude")
                # Fall through to Claude
        
        # Step 3: Fall back to Claude ONLY if Gemini failed completely (not just few results)
        # We don't want to use Claude just because Gemini found 1 result - that's fine
        if len(matches) == 0 and self.anthropic_api_key:
            try:
                claude_matches = await self._search_with_claude(
                    name, role, company_name, company_linkedin_url
                )
                if claude_matches:
                    matches = self._merge_matches(matches, claude_matches)
                    search_source = "claude" if not self.gemini_api_key else "gemini+claude"
                    logger.info(f"[CONTACT_SEARCH] Claude found {len(claude_matches)} matches")
            except Exception as e:
                logger.error(f"[CONTACT_SEARCH] Claude also failed: {e}")
                if not matches:
                    return ContactSearchResult(
                        matches=[],
                        search_query_used=search_query,
                        error=str(e)
                    )
        
        # Sort by confidence (highest first) and limit to 5
        matches.sort(key=lambda m: m.confidence, reverse=True)
        matches = matches[:5]
        
        # Update search source if we used research data
        if matches and matches[0].from_research:
            search_source = "research+" + search_source
        
        logger.info(f"[CONTACT_SEARCH] Final: {len(matches)} matches, source={search_source}")
        
        return ContactSearchResult(
            matches=matches,
            search_query_used=search_query,
            search_source=search_source
        )
    
    def _match_against_research(
        self,
        name: str,
        role: Optional[str],
        company_name: Optional[str],
        research_executives: List[Dict[str, Any]]
    ) -> List[ContactMatch]:
        """
        Match a contact name against known executives from research.
        
        Uses fuzzy name matching to find potential matches.
        """
        matches = []
        name_lower = name.lower().strip()
        name_parts = set(name_lower.split())
        
        for exec_data in research_executives:
            exec_name = exec_data.get("name", "").lower().strip()
            if not exec_name:
                continue
            
            exec_parts = set(exec_name.split())
            
            # Calculate name similarity
            # Full match
            if exec_name == name_lower:
                confidence = 0.95
                match_reason = "Exact name match from research"
            # All parts of search name are in executive name (or vice versa)
            elif name_parts.issubset(exec_parts) or exec_parts.issubset(name_parts):
                confidence = 0.85
                match_reason = "Name match from research"
            # At least 2 name parts match (for names like "Jan van der Berg")
            elif len(name_parts & exec_parts) >= 2:
                confidence = 0.75
                match_reason = "Partial name match from research"
            # First and last name match
            elif len(name_parts) >= 2 and len(exec_parts) >= 2:
                if list(name_parts)[0] in exec_parts or list(name_parts)[-1] in exec_parts:
                    confidence = 0.65
                    match_reason = "First/last name match from research"
                else:
                    continue
            else:
                continue
            
            # Boost confidence if role matches
            exec_title = exec_data.get("title", "") or ""
            if role and exec_title:
                role_lower = role.lower()
                title_lower = exec_title.lower()
                if role_lower in title_lower or title_lower in role_lower:
                    confidence = min(1.0, confidence + 0.05)
                    match_reason += " + role match"
            
            match = ContactMatch(
                name=exec_data.get("name", name),
                title=exec_data.get("title"),
                company=company_name,
                location=exec_data.get("location"),
                linkedin_url=exec_data.get("linkedin_url"),
                headline=exec_data.get("background", "")[:100] if exec_data.get("background") else None,
                confidence=confidence,
                match_reason=match_reason,
                from_research=True
            )
            matches.append(match)
        
        return matches
    
    async def _search_with_gemini(
        self,
        name: str,
        role: Optional[str],
        company_name: Optional[str],
        company_linkedin_url: Optional[str]
    ) -> List[ContactMatch]:
        """
        Search for LinkedIn profiles using Gemini with Google Search grounding.
        
        Much cheaper than Claude (~10x) with similar quality for this task.
        """
        try:
            from google import genai
            from google.genai import types
            
            client = genai.Client(api_key=self.gemini_api_key)
            
            # Build context
            role_context = f", {role}" if role else ""
            company_context = f" at {company_name}" if company_name else ""
            linkedin_context = f"\nCompany LinkedIn: {company_linkedin_url}" if company_linkedin_url else ""
            
            prompt = f"""Find LinkedIn profiles for: {name}{role_context}{company_context}
{linkedin_context}

Search for this person's LinkedIn profile and any other people with similar names at the same company.

Return a JSON array with up to 5 matches:
```json
[
  {{
    "name": "Full Name on LinkedIn",
    "title": "Current Job Title",
    "company": "Company Name",
    "location": "City, Country",
    "linkedin_url": "https://linkedin.com/in/username",
    "headline": "Profile headline (first 100 chars)",
    "confidence": 0.95,
    "match_reason": "Name + Company match"
  }}
]
```

Confidence scoring:
- 0.90-1.00: Name + Company + Role all match
- 0.75-0.89: Name + Company match
- 0.60-0.74: Name matches, similar company
- 0.40-0.59: Name matches, different company
- Below 0.40: Partial match

IMPORTANT:
- Always include LinkedIn URL (https://linkedin.com/in/...)
- Return empty array [] if nothing found
- Be thorough - include all plausible matches"""

            logger.info(f"[CONTACT_SEARCH] Gemini searching for: {name} at {company_name}")
            
            response = await client.aio.models.generate_content(
                model="gemini-2.0-flash",
                contents=prompt,
                config=types.GenerateContentConfig(
                    tools=[types.Tool(google_search=types.GoogleSearch())],
                    temperature=0.1,
                    max_output_tokens=2000
                )
            )
            
            if not response or not response.text:
                logger.warning("[CONTACT_SEARCH] Gemini returned empty response")
                return []
            
            return self._parse_matches(response.text, name, company_name)
            
        except Exception as e:
            logger.error(f"[CONTACT_SEARCH] Gemini search error: {e}")
            raise
    
    async def _search_with_claude(
        self,
        name: str,
        role: Optional[str],
        company_name: Optional[str],
        company_linkedin_url: Optional[str]
    ) -> List[ContactMatch]:
        """
        Search for LinkedIn profiles using Claude with web search.
        
        Used as fallback when Gemini doesn't find enough results.
        """
        try:
            from anthropic import AsyncAnthropic
            
            client = AsyncAnthropic(api_key=self.anthropic_api_key)
            
            prompt = self._build_claude_prompt(name, role, company_name, company_linkedin_url)
            
            logger.info(f"[CONTACT_SEARCH] Claude searching for: {name} at {company_name}")
            
            response = await client.messages.create(
                model="claude-sonnet-4-20250514",
                max_tokens=2000,
                messages=[{"role": "user", "content": prompt}],
                tools=[{
                    "type": "web_search_20250305",
                    "name": "web_search",
                    "max_uses": 3
                }]
            )
            
            # Extract text from response
            result_text = ""
            for block in response.content:
                if hasattr(block, 'text'):
                    result_text += block.text
            
            return self._parse_matches(result_text, name, company_name)
            
        except Exception as e:
            logger.error(f"[CONTACT_SEARCH] Claude search error: {e}")
            raise
    
    def _build_claude_prompt(
        self,
        name: str,
        role: Optional[str],
        company_name: Optional[str],
        company_linkedin_url: Optional[str]
    ) -> str:
        """Build the search prompt for Claude."""
        
        company_context = ""
        if company_name:
            company_context = f"\nCompany: {company_name}"
        if company_linkedin_url:
            company_context += f"\nCompany LinkedIn: {company_linkedin_url}"
        
        role_context = ""
        if role:
            role_context = f"\nExpected role: {role}"
        
        return f"""You are a LinkedIn profile researcher. Find possible LinkedIn profiles matching this person:

**Target Person:**
- Name: {name}{role_context}{company_context}

**Instructions:**
1. Search LinkedIn for people matching this name
2. If company is provided, prioritize people at that company
3. If role is provided, look for matching job titles
4. Consider name variations (e.g., Jan/Johannes, Bob/Robert)
5. Return ALL plausible matches, not just the best one

**Return up to 5 matches as a JSON array:**
```json
[
  {{
    "name": "Full Name as shown on LinkedIn",
    "title": "Current Job Title",
    "company": "Current Company",
    "location": "City, Country",
    "linkedin_url": "https://linkedin.com/in/username",
    "headline": "First 100 chars of profile headline...",
    "confidence": 0.95,
    "match_reason": "Name + Company + Role exact match"
  }}
]
```

**Confidence scoring guidelines:**
- 0.90-1.00: Name + Company + Role all match exactly
- 0.75-0.89: Name + Company match (role different or unknown)
- 0.60-0.74: Name matches, similar company name or same industry
- 0.40-0.59: Name matches, different company but role matches
- 0.20-0.39: Partial name match or possible name variation
- Below 0.20: Unlikely match

**IMPORTANT:**
- Always include the LinkedIn URL if you find it
- Include location when available
- Return empty array [] if no matches found
- Be thorough - better to show more options than miss the right person
"""

    def _parse_matches(
        self,
        response_text: str,
        search_name: str,
        company_name: Optional[str]
    ) -> List[ContactMatch]:
        """Parse AI response into ContactMatch objects."""
        
        matches = []
        
        try:
            # Try to find JSON array in response
            json_match = re.search(r'\[\s*\{.*?\}\s*\]', response_text, re.DOTALL)
            if json_match:
                json_str = json_match.group(0)
                data = json.loads(json_str)
                
                for item in data:
                    if isinstance(item, dict):
                        # Validate LinkedIn URL
                        linkedin_url = item.get("linkedin_url", "")
                        if linkedin_url and "linkedin.com/in/" not in linkedin_url.lower():
                            linkedin_url = None
                        
                        # Calculate confidence if not provided or seems wrong
                        confidence = item.get("confidence", 0.5)
                        if not isinstance(confidence, (int, float)):
                            confidence = 0.5
                        confidence = max(0, min(1, float(confidence)))
                        
                        match = ContactMatch(
                            name=item.get("name", search_name),
                            title=item.get("title"),
                            company=item.get("company"),
                            location=item.get("location"),
                            linkedin_url=linkedin_url,
                            headline=item.get("headline"),
                            confidence=confidence,
                            match_reason=item.get("match_reason", "Found in search"),
                            from_research=False
                        )
                        matches.append(match)
            
            # If no JSON found, try to extract info from text
            if not matches:
                logger.warning("[CONTACT_SEARCH] No JSON found, parsing text response")
                # Look for LinkedIn URLs in text
                url_pattern = r'https?://(?:www\.)?linkedin\.com/in/[\w-]+'
                urls = re.findall(url_pattern, response_text, re.IGNORECASE)
                
                for url in urls[:5]:
                    matches.append(ContactMatch(
                        name=search_name,
                        linkedin_url=url,
                        confidence=0.5,
                        match_reason="URL found in search results",
                        from_research=False
                    ))
        
        except json.JSONDecodeError as e:
            logger.error(f"[CONTACT_SEARCH] JSON parse error: {e}")
        except Exception as e:
            logger.error(f"[CONTACT_SEARCH] Parse error: {e}")
        
        return matches
    
    def _merge_matches(
        self,
        existing: List[ContactMatch],
        new_matches: List[ContactMatch]
    ) -> List[ContactMatch]:
        """
        Merge two lists of matches, avoiding duplicates.
        
        Duplicates are detected by LinkedIn URL or name similarity.
        Research matches are boosted when confirmed by search.
        """
        merged = list(existing)
        existing_urls = {m.linkedin_url.lower() for m in existing if m.linkedin_url}
        existing_names = {m.name.lower() for m in existing}
        
        for new_match in new_matches:
            # Check for duplicate by URL
            if new_match.linkedin_url:
                url_lower = new_match.linkedin_url.lower()
                if url_lower in existing_urls:
                    # Boost confidence of existing match if confirmed by search
                    for existing_match in merged:
                        if existing_match.linkedin_url and existing_match.linkedin_url.lower() == url_lower:
                            if existing_match.from_research:
                                existing_match.confidence = min(1.0, existing_match.confidence + 0.05)
                                existing_match.match_reason += " (confirmed by search)"
                    continue
                existing_urls.add(url_lower)
            
            # Check for duplicate by name
            name_lower = new_match.name.lower()
            if name_lower in existing_names:
                continue
            existing_names.add(name_lower)
            
            merged.append(new_match)
        
        return merged
    
    def extract_executives_from_research(
        self,
        research_data: Dict[str, Any],
        brief_content: Optional[str] = None
    ) -> List[ResearchExecutive]:
        """
        Extract executives from research data and brief content.
        
        Looks for leadership information in:
        1. Structured research_data (if available)
        2. Brief content text (parsing markdown tables and lists)
        
        Returns list of executives with their details.
        """
        executives = []
        seen_names = set()
        
        # Method 1: Extract from structured research_data
        if research_data:
            # Check for executives in various possible locations
            for key in ["executives", "leadership", "team", "people", "contacts"]:
                if key in research_data and isinstance(research_data[key], list):
                    for exec_data in research_data[key]:
                        if isinstance(exec_data, dict) and exec_data.get("name"):
                            name = exec_data["name"]
                            if name.lower() not in seen_names:
                                seen_names.add(name.lower())
                                executives.append(ResearchExecutive(
                                    name=name,
                                    title=exec_data.get("title") or exec_data.get("role"),
                                    linkedin_url=exec_data.get("linkedin_url") or exec_data.get("linkedin"),
                                    background=exec_data.get("background") or exec_data.get("notes"),
                                    relevance=exec_data.get("relevance")
                                ))
        
        # Method 2: Parse from brief_content markdown
        if brief_content:
            extracted = self._extract_executives_from_markdown(brief_content)
            for exec_data in extracted:
                name = exec_data.get("name", "")
                if name and name.lower() not in seen_names:
                    seen_names.add(name.lower())
                    executives.append(ResearchExecutive(
                        name=name,
                        title=exec_data.get("title"),
                        linkedin_url=exec_data.get("linkedin_url"),
                        background=exec_data.get("background"),
                        relevance=exec_data.get("relevance")
                    ))
        
        logger.info(f"[CONTACT_SEARCH] Extracted {len(executives)} executives from research")
        return executives
    
    def _extract_executives_from_markdown(
        self,
        content: str
    ) -> List[Dict[str, str]]:
        """
        Parse executives from markdown content (tables and lists).
        
        IMPORTANT: Only looks in leadership-related sections to avoid
        parsing other tables (like Executive Summary metrics).
        
        Looks for patterns like:
        - Leadership tables with Name | Title | LinkedIn columns
        - Bullet lists with "Name - Title" or "Name (Title)" patterns
        """
        executives = []
        
        if not content:
            return executives
        
        # First, find the leadership section(s) in the content
        # Look for Section 3 (People & Power) or similar headers
        leadership_section = self._extract_leadership_section(content)
        
        if not leadership_section:
            logger.debug("[CONTACT_SEARCH] No leadership section found in brief")
            return executives
        
        # Pattern 1: Parse markdown tables intelligently
        # Tables can have varying columns: | NAME | TITLE | LINKEDIN | BACKGROUND | NOTES |
        # We need to find the header row first, then parse data rows based on column positions
        
        lines = leadership_section.split('\n')
        header_indices = {}  # Maps column type to column index
        
        for i, line in enumerate(lines):
            # Look for header row (contains "name" or "naam")
            if '|' in line and any(h in line.lower() for h in ['name', 'naam']):
                cols = [c.strip().lower() for c in line.split('|')]
                for idx, col in enumerate(cols):
                    if 'name' in col or 'naam' in col:
                        header_indices['name'] = idx
                    elif 'title' in col or 'titel' in col or 'role' in col or 'rol' in col:
                        header_indices['title'] = idx
                    elif 'linkedin' in col:
                        header_indices['linkedin'] = idx
                    elif 'background' in col or 'achtergrond' in col:
                        header_indices['background'] = idx
                
                # Now parse subsequent rows
                for data_line in lines[i+1:]:
                    # Skip separator rows
                    if '---' in data_line or not '|' in data_line:
                        continue
                    
                    # Stop at next section
                    if data_line.strip().startswith('#'):
                        break
                    
                    cols = [c.strip() for c in data_line.split('|')]
                    
                    # Extract name from the identified column
                    name = None
                    title = None
                    linkedin_url = None
                    background = None
                    
                    if 'name' in header_indices and header_indices['name'] < len(cols):
                        name = cols[header_indices['name']].strip('*').strip()
                    
                    if 'title' in header_indices and header_indices['title'] < len(cols):
                        title = cols[header_indices['title']].strip('*').strip()
                    
                    if 'linkedin' in header_indices and header_indices['linkedin'] < len(cols):
                        linkedin_val = cols[header_indices['linkedin']].strip()
                        if 'linkedin.com/in/' in linkedin_val.lower():
                            linkedin_url = linkedin_val
                    
                    if 'background' in header_indices and header_indices['background'] < len(cols):
                        background = cols[header_indices['background']].strip('*').strip()
                    
                    # Validate name - should look like a person name
                    if name and len(name) > 2:
                        # Skip if it looks like a metric or header value
                        if any(skip in name.lower() for skip in [
                            'niet gevonden', 'not found', '---', 'n/a', 'unknown',
                            'opportunity', 'timing', 'financial', 'dimension'
                        ]):
                            continue
                        
                        # Real names have capital letters and typically 2+ words or are single proper nouns
                        if any(c.isupper() for c in name):
                            executives.append({
                                "name": name,
                                "title": title,
                                "linkedin_url": linkedin_url,
                                "background": background
                            })
                
                break  # Found and processed the table
        
        # Pattern 2: Bullet points with "Name - Title" or "Name, Title"
        bullet_pattern = r'[-•*]\s*\*?\*?([A-Z][a-zA-Z\s\.]+?)[-–,]\s*([^|\n]+?)(?:\||$|\n)'
        
        for match in re.finditer(bullet_pattern, leadership_section):
            name = match.group(1).strip().strip('*')
            title = match.group(2).strip().strip('*')
            
            # Skip if name looks like a label or metric
            if any(label in name.lower() for label in [
                "naam", "name", "contact", "email", "opportunity", "timing", 
                "dimension", "aspect", "assessment"
            ]):
                continue
            
            if name and len(name) > 2:
                executives.append({
                    "name": name,
                    "title": title
                })
        
        # Pattern 3: Look for LinkedIn URLs with context (in leadership section only)
        linkedin_pattern = r'(?:([A-Z][a-zA-Z\s]+?)(?:\s*[-–:]\s*|\s+))?(https?://(?:www\.)?linkedin\.com/in/[^\s)>\]]+)'
        
        for match in re.finditer(linkedin_pattern, leadership_section):
            name = match.group(1)
            url = match.group(2)
            
            if name:
                name = name.strip()
                # Only add if we found a real name before the URL
                if name and len(name) > 2 and not name.lower() in ["linkedin", "url", "link"]:
                    executives.append({
                        "name": name,
                        "linkedin_url": url
                    })
        
        # Deduplicate by name
        seen = set()
        unique = []
        for exec_data in executives:
            name_lower = exec_data.get("name", "").lower()
            if name_lower and name_lower not in seen:
                seen.add(name_lower)
                unique.append(exec_data)
        
        return unique
    
    def _extract_leadership_section(self, content: str) -> str:
        """
        Extract only the leadership/people section from the research brief.
        
        This prevents parsing other tables (like Executive Summary metrics)
        as executives.
        
        Looks for:
        - Section 3: People & Power
        - Section 3: Mensen & Macht
        - Executive Leadership sections
        """
        if not content:
            return ""
        
        lines = content.split('\n')
        leadership_content = []
        in_leadership_section = False
        section_depth = 0
        
        for i, line in enumerate(lines):
            line_lower = line.lower()
            
            # Check for start of leadership section
            # Look for "Section 3" or "People & Power" or "Mensen & Macht" or "Executive Leadership"
            is_leadership_header = any([
                'section 3' in line_lower and ('people' in line_lower or 'mensen' in line_lower or 'macht' in line_lower or 'power' in line_lower),
                'people & power' in line_lower,
                'mensen & macht' in line_lower,
                'executive leadership' in line_lower and line.strip().startswith('#'),
                '3.1' in line_lower and ('leadership' in line_lower or 'leiderschap' in line_lower),
                '3.2' in line_lower and ('leadership' in line_lower or 'leiderschap' in line_lower),
            ])
            
            if is_leadership_header:
                in_leadership_section = True
                # Determine section depth (number of #)
                section_depth = len(line) - len(line.lstrip('#'))
                leadership_content.append(line)
                continue
            
            # Check for end of leadership section (next major section)
            if in_leadership_section:
                # A new section at same or higher level ends our section
                is_new_major_section = (
                    line.strip().startswith('#') and
                    not any(sub in line_lower for sub in ['3.1', '3.2', '3.3', '3.4', '3.5', '3.6', '3.7']) and
                    ('section 4' in line_lower or 
                     'section 5' in line_lower or
                     'sectie 4' in line_lower or
                     'sectie 5' in line_lower or
                     'wat er nu gebeurt' in line_lower or
                     'what\'s happening' in line_lower or
                     'recent developments' in line_lower or
                     'recente ontwikkelingen' in line_lower)
                )
                
                if is_new_major_section:
                    in_leadership_section = False
                    break
                
                leadership_content.append(line)
        
        result = '\n'.join(leadership_content)
        
        if result:
            logger.debug(f"[CONTACT_SEARCH] Extracted leadership section: {len(result)} chars")
        
        return result


# Singleton instance
_contact_search_service: Optional[ContactSearchService] = None


def get_contact_search_service() -> ContactSearchService:
    """Get or create the ContactSearchService singleton."""
    global _contact_search_service
    if _contact_search_service is None:
        _contact_search_service = ContactSearchService()
    return _contact_search_service
