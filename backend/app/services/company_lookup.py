"""
Company Lookup Service

Automatically discovers company website and LinkedIn URL based on company name and country.
Uses multiple strategies:
1. Direct URL guessing (company.com, company.nl, etc.)
2. Google Search via Gemini (grounded search)
3. Common patterns for LinkedIn URLs
"""

import os
import re
import asyncio
import aiohttp
import json
from typing import Dict, Any, Optional, List, Tuple
from urllib.parse import quote_plus
import logging

logger = logging.getLogger(__name__)

# Lazy import for Gemini to avoid initialization issues
_genai_client = None

def get_genai_client():
    """Get or create Google GenAI client."""
    global _genai_client
    if _genai_client is None:
        from google import genai
        # Try both possible env var names
        api_key = os.getenv("GOOGLE_AI_API_KEY") or os.getenv("GOOGLE_API_KEY")
        if api_key:
            _genai_client = genai.Client(api_key=api_key)
    return _genai_client


class CompanyLookupService:
    """
    Service to automatically discover company URLs.
    
    Returns results with confidence scores (0-100).
    Only returns suggestions with high confidence (>= threshold).
    """
    
    def __init__(self):
        self.timeout = aiohttp.ClientTimeout(total=10)
        self.headers = {
            "User-Agent": "Mozilla/5.0 (compatible; DealMotion/1.0)",
            "Accept": "text/html,application/xhtml+xml",
        }
        self.confidence_threshold = 80  # Only return if >= 80% confident
        
        # Country TLDs for website guessing
        self.country_tlds = {
            "netherlands": [".nl", ".com", ".eu"],
            "nederland": [".nl", ".com", ".eu"],
            "germany": [".de", ".com", ".eu"],
            "duitsland": [".de", ".com", ".eu"],
            "belgium": [".be", ".com", ".eu"],
            "belgie": [".be", ".com", ".eu"],
            "france": [".fr", ".com", ".eu"],
            "frankrijk": [".fr", ".com", ".eu"],
            "uk": [".co.uk", ".com", ".uk"],
            "united kingdom": [".co.uk", ".com", ".uk"],
            "usa": [".com", ".us"],
            "united states": [".com", ".us"],
        }
        self.default_tlds = [".com", ".net", ".io", ".co"]
    
    async def lookup_company(
        self,
        company_name: str,
        country: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Look up company website and LinkedIn URL.
        
        Strategy:
        1. First try direct URL patterns (fast, no API cost)
        2. If not found, use Google Search via Gemini (more reliable)
        
        Args:
            company_name: Name of the company
            country: Optional country for better TLD guessing
            
        Returns:
            Dict with website_url, linkedin_url, and confidence scores
        """
        result = {
            "company_name": company_name,
            "country": country,
            "website": None,
            "website_confidence": 0,
            "linkedin_url": None,
            "linkedin_confidence": 0,
            "suggestions_found": False,
            "search_method": "direct"
        }
        
        if not company_name or len(company_name.strip()) < 2:
            return result
        
        # Clean company name for URL generation
        clean_name = self._clean_company_name(company_name)
        
        # PHASE 1: Try direct URL patterns (fast, no API cost)
        website_task = self._find_website(clean_name, company_name, country)
        linkedin_task = self._find_linkedin(clean_name, company_name)
        
        website_result, linkedin_result = await asyncio.gather(
            website_task, 
            linkedin_task,
            return_exceptions=True
        )
        
        # Process website result
        if isinstance(website_result, tuple) and website_result[0]:
            url, confidence = website_result
            if confidence >= self.confidence_threshold:
                result["website"] = url
                result["website_confidence"] = confidence
                result["suggestions_found"] = True
        
        # Process LinkedIn result
        if isinstance(linkedin_result, tuple) and linkedin_result[0]:
            url, confidence = linkedin_result
            if confidence >= self.confidence_threshold:
                result["linkedin_url"] = url
                result["linkedin_confidence"] = confidence
                result["suggestions_found"] = True
        
        # PHASE 2: If direct lookup failed, try Google Search via Gemini
        if not result["website"] or not result["linkedin_url"]:
            google_result = await self._google_search_lookup(
                company_name, 
                country,
                need_website=not result["website"],
                need_linkedin=not result["linkedin_url"]
            )
            
            if google_result:
                result["search_method"] = "google"
                
                if google_result.get("website") and not result["website"]:
                    result["website"] = google_result["website"]
                    result["website_confidence"] = google_result.get("website_confidence", 85)
                    result["suggestions_found"] = True
                    
                if google_result.get("linkedin_url") and not result["linkedin_url"]:
                    result["linkedin_url"] = google_result["linkedin_url"]
                    result["linkedin_confidence"] = google_result.get("linkedin_confidence", 85)
                    result["suggestions_found"] = True
        
        logger.info(
            f"Lookup for '{company_name}': "
            f"website={result['website']} ({result['website_confidence']}%), "
            f"linkedin={result['linkedin_url']} ({result['linkedin_confidence']}%)"
        )
        
        return result
    
    def _clean_company_name(self, name: str) -> str:
        """Clean company name for URL generation."""
        # Remove common suffixes
        suffixes = [
            " b.v.", " bv", " n.v.", " nv", " b.v", " n.v",
            " inc.", " inc", " ltd.", " ltd", " llc", " corp.",
            " gmbh", " ag", " sa", " srl", " spa",
            " holding", " group", " international",
        ]
        
        clean = name.lower().strip()
        for suffix in suffixes:
            if clean.endswith(suffix):
                clean = clean[:-len(suffix)].strip()
        
        # Remove special characters, keep only alphanumeric and spaces
        clean = re.sub(r'[^\w\s-]', '', clean)
        
        # Replace spaces with nothing for URL (shell.com) or hyphen (shell-corp.com)
        return clean
    
    async def _find_website(
        self,
        clean_name: str,
        original_name: str,
        country: Optional[str]
    ) -> Tuple[Optional[str], int]:
        """Find company website by trying common patterns."""
        
        # Get TLDs to try based on country
        tlds = self.default_tlds.copy()
        if country:
            country_lower = country.lower().strip()
            if country_lower in self.country_tlds:
                tlds = self.country_tlds[country_lower] + self.default_tlds
        
        # Generate URL variations to try
        url_variations = []
        
        # Remove spaces for domain
        domain_name = clean_name.replace(" ", "").replace("-", "")
        domain_name_hyphen = clean_name.replace(" ", "-")
        
        for tld in tlds[:4]:  # Limit TLDs to try
            url_variations.append(f"https://www.{domain_name}{tld}")
            url_variations.append(f"https://{domain_name}{tld}")
            if domain_name != domain_name_hyphen:
                url_variations.append(f"https://www.{domain_name_hyphen}{tld}")
        
        # Try each URL
        async with aiohttp.ClientSession(
            timeout=self.timeout,
            headers=self.headers
        ) as session:
            for url in url_variations:
                try:
                    async with session.head(
                        url, 
                        allow_redirects=True,
                        ssl=False  # Some sites have SSL issues
                    ) as response:
                        if response.status == 200:
                            final_url = str(response.url)
                            
                            # Check if the page title or URL contains company name
                            confidence = self._calculate_website_confidence(
                                final_url, clean_name, original_name
                            )
                            
                            if confidence >= 70:
                                return (final_url, confidence)
                                
                except Exception as e:
                    logger.debug(f"URL check failed for {url}: {e}")
                    continue
        
        return (None, 0)
    
    async def _find_linkedin(
        self,
        clean_name: str,
        original_name: str
    ) -> Tuple[Optional[str], int]:
        """Find company LinkedIn page."""
        
        # Generate LinkedIn URL variations
        linkedin_slug = clean_name.replace(" ", "-").lower()
        linkedin_slug_no_space = clean_name.replace(" ", "").lower()
        
        url_variations = [
            f"https://www.linkedin.com/company/{linkedin_slug}",
            f"https://www.linkedin.com/company/{linkedin_slug_no_space}",
            f"https://linkedin.com/company/{linkedin_slug}",
        ]
        
        async with aiohttp.ClientSession(
            timeout=self.timeout,
            headers={
                **self.headers,
                "Accept-Language": "en-US,en;q=0.9",
            }
        ) as session:
            for url in url_variations:
                try:
                    async with session.head(
                        url,
                        allow_redirects=True
                    ) as response:
                        # LinkedIn returns 200 for valid company pages
                        # and redirects to login for invalid ones
                        if response.status == 200:
                            final_url = str(response.url)
                            
                            # Check if we got redirected to a login page
                            if "/login" in final_url or "/authwall" in final_url:
                                continue
                            
                            # Valid company page found
                            confidence = 85  # LinkedIn URLs are fairly reliable
                            return (final_url, confidence)
                            
                except Exception as e:
                    logger.debug(f"LinkedIn check failed for {url}: {e}")
                    continue
        
        return (None, 0)
    
    def _calculate_website_confidence(
        self,
        url: str,
        clean_name: str,
        original_name: str
    ) -> int:
        """Calculate confidence that URL belongs to the company."""
        confidence = 70  # Base confidence for a working URL
        
        url_lower = url.lower()
        clean_lower = clean_name.lower().replace(" ", "")
        
        # Check if company name is in the domain
        if clean_lower in url_lower:
            confidence += 20
        
        # Check for exact domain match
        domain_match = re.search(r'://(?:www\.)?([^/]+)', url_lower)
        if domain_match:
            domain = domain_match.group(1)
            domain_name = domain.split('.')[0]
            
            if domain_name == clean_lower:
                confidence += 10  # Exact match bonus
        
        return min(confidence, 100)
    
    async def _google_search_lookup(
        self,
        company_name: str,
        country: Optional[str],
        need_website: bool = True,
        need_linkedin: bool = True
    ) -> Optional[Dict[str, Any]]:
        """
        Use Google Search via Gemini to find company URLs.
        
        This is more reliable than direct URL guessing but uses API quota.
        """
        client = get_genai_client()
        if not client:
            logger.warning("Google GenAI client not available for lookup")
            return None
        
        try:
            from google.genai import types
            
            # Build search query
            location_hint = f" in {country}" if country else ""
            
            search_parts = []
            if need_website:
                search_parts.append("official website URL")
            if need_linkedin:
                search_parts.append("LinkedIn company page URL")
            
            prompt = f"""Find the {" and ".join(search_parts)} for the company "{company_name}"{location_hint}.

Return ONLY a JSON object with these fields (no other text):
{{
    "website": "https://www.example.com" or null,
    "linkedin_url": "https://www.linkedin.com/company/example" or null,
    "website_confidence": 0-100,
    "linkedin_confidence": 0-100
}}

Rules:
- Only return URLs you are confident about (>80% sure)
- Website should be the official company homepage
- LinkedIn should be the official company LinkedIn page
- Set confidence to 0 if not found or unsure
- Return valid JSON only, no markdown or explanations"""

            # Use Gemini with Google Search grounding
            # Use client.aio for async to not block the event loop
            response = await client.aio.models.generate_content(
                model="gemini-2.0-flash",
                contents=prompt,
                config=types.GenerateContentConfig(
                    tools=[types.Tool(google_search=types.GoogleSearch())],
                    temperature=0.1,
                    max_output_tokens=500
                )
            )
            
            if response and response.text:
                # Parse JSON from response
                text = response.text.strip()
                
                # Remove markdown code blocks if present
                if text.startswith("```"):
                    text = re.sub(r'^```\w*\n?', '', text)
                    text = re.sub(r'\n?```$', '', text)
                
                result = json.loads(text)
                
                # Validate URLs
                if result.get("website"):
                    if not result["website"].startswith("http"):
                        result["website"] = "https://" + result["website"]
                
                if result.get("linkedin_url"):
                    if "linkedin.com" not in result["linkedin_url"]:
                        result["linkedin_url"] = None
                        result["linkedin_confidence"] = 0
                
                logger.info(f"Google Search found: website={result.get('website')}, linkedin={result.get('linkedin_url')}")
                return result
                
        except json.JSONDecodeError as e:
            logger.warning(f"Failed to parse Google Search response: {e}")
        except Exception as e:
            logger.error(f"Google Search lookup failed: {e}")
        
        return None
    
    async def search_company_options(
        self,
        company_name: str,
        country: str
    ) -> List[Dict[str, Any]]:
        """
        Search for multiple company options matching the name and country.
        
        Returns a list of possible matches for the user to select from.
        This is more accurate than auto-guessing the wrong company.
        
        Args:
            company_name: Name of the company
            country: Country where the company is located (REQUIRED)
            
        Returns:
            List of company options with website, linkedin, description
        """
        if not company_name or not country:
            return []
        
        client = get_genai_client()
        if not client:
            logger.warning("Google GenAI client not available for search - using fallback")
            # Fallback: try direct URL patterns and return as single option
            return await self._fallback_search(company_name, country)
        
        try:
            from google.genai import types
            
            prompt = f"""Search for companies matching "{company_name}" in {country}.

IMPORTANT: For each company, search for BOTH:
1. The official company website
2. The LinkedIn company page (search: "{company_name} linkedin" or "linkedin.com/company/{company_name}")

Return a JSON array with up to 3 most likely matches. Each match should have:
{{
    "company_name": "Official company name",
    "description": "Brief description (max 100 chars)",
    "website": "https://www.example.com",
    "linkedin_url": "https://www.linkedin.com/company/example",
    "location": "City, Country",
    "confidence": 0-100
}}

Rules:
- Only include companies that actually exist in {country}
- Order by relevance/confidence (most likely first)
- ALWAYS try to find the LinkedIn company page URL - most companies have one
- LinkedIn URLs should be in format: https://www.linkedin.com/company/company-name
- If company name is ambiguous, include different companies with same/similar names
- Return empty array [] if no matches found
- Return valid JSON array only, no markdown or explanations"""

            # Use client.aio for async to not block the event loop
            response = await client.aio.models.generate_content(
                model="gemini-2.0-flash",
                contents=prompt,
                config=types.GenerateContentConfig(
                    tools=[types.Tool(google_search=types.GoogleSearch())],
                    temperature=0.1,
                    max_output_tokens=1500
                )
            )
            
            if response and response.text:
                text = response.text.strip()
                
                # Check for empty response
                if not text:
                    logger.warning(f"Empty response from Gemini for company search: {company_name}")
                    return await self._fallback_search(company_name, country)
                
                # Remove markdown code blocks if present
                if text.startswith("```"):
                    text = re.sub(r'^```\w*\n?', '', text)
                    text = re.sub(r'\n?```$', '', text)
                
                # Try to find JSON array in the response
                text = text.strip()
                if not text.startswith("["):
                    # Try to extract JSON array from text
                    match = re.search(r'\[[\s\S]*\]', text)
                    if match:
                        text = match.group(0)
                    else:
                        logger.warning(f"No JSON array found in response: {text[:100]}...")
                        return await self._fallback_search(company_name, country)
                
                options = json.loads(text)
                
                if isinstance(options, list):
                    # Validate and clean URLs
                    for opt in options:
                        if opt.get("website") and not opt["website"].startswith("http"):
                            opt["website"] = "https://" + opt["website"]
                        if opt.get("linkedin_url") and "linkedin.com" not in opt.get("linkedin_url", ""):
                            opt["linkedin_url"] = None
                    
                    logger.info(f"Found {len(options)} company options for '{company_name}' in {country}")
                    return options
            else:
                logger.warning(f"No response from Gemini for company search: {company_name}")
                return await self._fallback_search(company_name, country)
                
        except json.JSONDecodeError as e:
            logger.warning(f"Failed to parse company options response: {e}. Text was: {text[:200] if 'text' in dir() else 'N/A'}")
        except Exception as e:
            logger.error(f"Company options search failed: {e}")
        
        # If Google Search fails, use fallback
        return await self._fallback_search(company_name, country)
    
    async def _fallback_search(
        self,
        company_name: str,
        country: str
    ) -> List[Dict[str, Any]]:
        """
        Fallback when Google Search is not available.
        Uses direct URL patterns to find company website.
        """
        logger.info(f"Using fallback search for '{company_name}' in {country}")
        
        clean_name = self._clean_company_name(company_name)
        
        # Try to find website using direct patterns
        website_result = await self._find_website(clean_name, company_name, country)
        linkedin_result = await self._find_linkedin(clean_name, company_name)
        
        website_url = None
        website_confidence = 0
        linkedin_url = None
        linkedin_confidence = 0
        
        if isinstance(website_result, tuple) and website_result[0]:
            website_url, website_confidence = website_result
        
        if isinstance(linkedin_result, tuple) and linkedin_result[0]:
            linkedin_url, linkedin_confidence = linkedin_result
        
        # If we found something, return it as an option
        if website_url or linkedin_url:
            return [{
                "company_name": company_name,
                "description": f"Gevonden via URL patronen in {country}",
                "website": website_url,
                "linkedin_url": linkedin_url,
                "location": country,
                "confidence": max(website_confidence, linkedin_confidence)
            }]
        
        # Nothing found - return empty but with helpful message
        logger.warning(f"Fallback search found nothing for '{company_name}' in {country}")
        return []


# Lazy singleton
_company_lookup: Optional[CompanyLookupService] = None

def get_company_lookup() -> CompanyLookupService:
    """Get or create company lookup service instance."""
    global _company_lookup
    if _company_lookup is None:
        _company_lookup = CompanyLookupService()
    return _company_lookup

