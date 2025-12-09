"""
Contact Search Service - Search for LinkedIn profiles matching a contact.

This service uses Claude with web search to find possible LinkedIn matches
for a contact person, returning multiple results with confidence scores.
"""

import os
import json
import re
import logging
from typing import Optional, List
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


class ContactSearchResult(BaseModel):
    """Result of a contact search."""
    matches: List[ContactMatch] = []
    search_query_used: str = ""
    search_source: str = "claude"
    error: Optional[str] = None


class ContactSearchService:
    """
    Service to search for LinkedIn profiles matching a contact person.
    
    Uses Claude with web search to find possible matches, returning
    up to 5 results with confidence scores for user selection.
    """
    
    def __init__(self):
        self.api_key = os.getenv("ANTHROPIC_API_KEY")
        if not self.api_key:
            logger.warning("ANTHROPIC_API_KEY not set - contact search will fail")
    
    async def search_contact(
        self,
        name: str,
        role: Optional[str] = None,
        company_name: Optional[str] = None,
        company_linkedin_url: Optional[str] = None
    ) -> ContactSearchResult:
        """
        Search for LinkedIn profiles matching the given contact info.
        
        Args:
            name: Contact's full name (required)
            role: Contact's job title/role (optional, helps narrow search)
            company_name: Company name for context (optional but recommended)
            company_linkedin_url: Company LinkedIn URL (optional, improves accuracy)
        
        Returns:
            ContactSearchResult with up to 5 matches sorted by confidence
        """
        if not self.api_key:
            return ContactSearchResult(
                matches=[],
                error="API key not configured"
            )
        
        try:
            from anthropic import AsyncAnthropic
            
            # Use AsyncAnthropic to not block the event loop
            client = AsyncAnthropic(api_key=self.api_key)
            
            # Build search query
            search_parts = [f'"{name}"']
            if company_name:
                search_parts.append(f'"{company_name}"')
            if role:
                search_parts.append(role)
            search_parts.append("site:linkedin.com/in")
            
            search_query = " ".join(search_parts)
            
            prompt = self._build_search_prompt(name, role, company_name, company_linkedin_url)
            
            logger.info(f"[CONTACT_SEARCH] Searching for: {name} at {company_name}")
            
            # Use await with AsyncAnthropic to not block the event loop
            response = await client.messages.create(
                model="claude-sonnet-4-20250514",
                max_tokens=2000,
                messages=[
                    {
                        "role": "user",
                        "content": prompt
                    }
                ],
                tools=[
                    {
                        "type": "web_search_20250305",
                        "name": "web_search",
                        "max_uses": 3
                    }
                ]
            )
            
            # Extract the text response
            result_text = ""
            for block in response.content:
                if hasattr(block, 'text'):
                    result_text += block.text
            
            logger.info(f"[CONTACT_SEARCH] Response received, parsing matches...")
            
            matches = self._parse_matches(result_text, name, company_name)
            
            # Sort by confidence (highest first)
            matches.sort(key=lambda m: m.confidence, reverse=True)
            
            # Limit to 5 matches
            matches = matches[:5]
            
            logger.info(f"[CONTACT_SEARCH] Found {len(matches)} matches")
            
            return ContactSearchResult(
                matches=matches,
                search_query_used=search_query,
                search_source="claude"
            )
            
        except Exception as e:
            logger.error(f"[CONTACT_SEARCH] Error: {e}")
            return ContactSearchResult(
                matches=[],
                search_query_used="",
                error=str(e)
            )
    
    def _build_search_prompt(
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

**Match reason examples:**
- "Name + Company + Role exact match"
- "Name + Company match, different title"
- "Name match, similar company name"
- "Name match, same industry"
- "Possible name variation"

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
        """Parse Claude's response into ContactMatch objects."""
        
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
                            match_reason=item.get("match_reason", "Found in search")
                        )
                        matches.append(match)
            
            # If no JSON found, try to extract info from text
            if not matches:
                logger.warning("[CONTACT_SEARCH] No JSON found, parsing text response")
                # Look for LinkedIn URLs in text
                url_pattern = r'https?://(?:www\.)?linkedin\.com/in/[\w-]+'
                urls = re.findall(url_pattern, response_text, re.IGNORECASE)
                
                for url in urls[:5]:
                    # Extract username from URL for display
                    username = url.split("/in/")[-1].rstrip("/")
                    matches.append(ContactMatch(
                        name=search_name,
                        linkedin_url=url,
                        confidence=0.5,
                        match_reason="URL found in search results"
                    ))
        
        except json.JSONDecodeError as e:
            logger.error(f"[CONTACT_SEARCH] JSON parse error: {e}")
        except Exception as e:
            logger.error(f"[CONTACT_SEARCH] Parse error: {e}")
        
        return matches


# Singleton instance
_contact_search_service: Optional[ContactSearchService] = None


def get_contact_search_service() -> ContactSearchService:
    """Get or create the ContactSearchService singleton."""
    global _contact_search_service
    if _contact_search_service is None:
        _contact_search_service = ContactSearchService()
    return _contact_search_service

