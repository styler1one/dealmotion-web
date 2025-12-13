"""
Contacts Router - API endpoints for contact person management and analysis.

Endpoints:
- POST /research/{research_id}/contacts - Add and analyze contact for research
- GET /research/{research_id}/contacts - List contacts for research
- GET /research/{research_id}/executives - Get executives found in research
- GET /prospects/{prospect_id}/contacts - List contacts for prospect
- GET /contacts/{contact_id} - Get single contact
- DELETE /contacts/{contact_id} - Delete contact
- POST /contacts/lookup - Lookup contact LinkedIn and role online
- POST /contacts/search - Search for LinkedIn profiles (uses research executives for matching)
"""

import logging
import asyncio
import os
from typing import Optional, List
from datetime import datetime
from uuid import uuid4

from fastapi import APIRouter, HTTPException, Depends, BackgroundTasks
from pydantic import BaseModel

from app.deps import get_current_user
from app.database import get_supabase_service
from app.services.contact_analyzer import get_contact_analyzer
from app.services.contact_search import get_contact_search_service, ContactMatch as ContactMatchModel

# Inngest integration
from app.inngest.events import send_event, use_inngest_for, Events

logger = logging.getLogger(__name__)

router = APIRouter()

# Use centralized database module
supabase_service = get_supabase_service()


# ==================== Pydantic Models ====================

class ContactCreate(BaseModel):
    """Request model for creating a contact."""
    name: str
    role: Optional[str] = None
    linkedin_url: Optional[str] = None
    email: Optional[str] = None
    phone: Optional[str] = None
    is_primary: bool = False
    # User-provided LinkedIn info (since LinkedIn blocks scraping)
    linkedin_about: Optional[str] = None
    linkedin_experience: Optional[str] = None
    additional_notes: Optional[str] = None


class ContactResponse(BaseModel):
    """Response model for a contact."""
    id: str
    prospect_id: str
    name: str
    role: Optional[str]
    email: Optional[str]
    phone: Optional[str]
    linkedin_url: Optional[str]
    
    # Analysis results
    communication_style: Optional[str]
    decision_authority: Optional[str]
    probable_drivers: Optional[str]
    profile_brief: Optional[str]
    opening_suggestions: Optional[List[str]]
    questions_to_ask: Optional[List[str]]
    topics_to_avoid: Optional[List[str]]
    
    # Meta
    is_primary: bool
    analyzed_at: Optional[str]
    created_at: str


class ContactListResponse(BaseModel):
    """Response model for contact list."""
    contacts: List[ContactResponse]
    count: int


class ContactLookupRequest(BaseModel):
    """Request model for looking up contact info online."""
    name: str
    company_name: str
    country: Optional[str] = None


class ContactLookupResponse(BaseModel):
    """Response model for contact lookup."""
    name: str
    role: Optional[str] = None
    linkedin_url: Optional[str] = None
    headline: Optional[str] = None
    found: bool = False
    confidence: Optional[str] = None  # "high", "medium", "low"


class ContactSearchRequest(BaseModel):
    """Request model for searching contact profiles."""
    name: str
    role: Optional[str] = None
    company_name: Optional[str] = None
    company_linkedin_url: Optional[str] = None
    research_id: Optional[str] = None  # If provided, uses executives from research for matching


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
    from_research: bool = False  # True if this match came from research data


class ContactSearchResponse(BaseModel):
    """Response model for contact search."""
    matches: List[ContactMatch] = []
    search_query_used: str = ""
    search_source: str = "gemini"  # "gemini", "claude", "research", or combinations
    error: Optional[str] = None


class ResearchExecutive(BaseModel):
    """An executive found in research data."""
    name: str
    title: Optional[str] = None
    linkedin_url: Optional[str] = None
    background: Optional[str] = None


class ResearchExecutivesResponse(BaseModel):
    """Response model for research executives."""
    executives: List[ResearchExecutive] = []
    company_name: Optional[str] = None
    source: str = "research_brief"


# ==================== Helper Functions ====================

def get_organization_id(user_id: str) -> str:
    """Get organization ID for user."""
    response = supabase_service.table("organization_members")\
        .select("organization_id")\
        .eq("user_id", user_id)\
        .execute()
    
    if not response.data:
        raise HTTPException(status_code=403, detail="User not in any organization")
    
    return response.data[0]["organization_id"]


def get_prospect_id_from_research(research_id: str, organization_id: str) -> str:
    """Get prospect_id from a research brief."""
    response = supabase_service.table("research_briefs")\
        .select("prospect_id")\
        .eq("id", research_id)\
        .eq("organization_id", organization_id)\
        .single()\
        .execute()
    
    if not response.data:
        raise HTTPException(status_code=404, detail="Research not found")
    
    prospect_id = response.data.get("prospect_id")
    if not prospect_id:
        raise HTTPException(status_code=400, detail="Research has no linked prospect")
    
    return prospect_id


# ==================== Contact Lookup via Gemini ====================

async def lookup_contact_online(name: str, company_name: str, country: Optional[str] = None) -> dict:
    """
    Lookup contact information (LinkedIn URL, role) via multiple strategies:
    1. Direct LinkedIn URL patterns (most reliable)
    2. Gemini with Google Search as fallback
    
    Returns a dict with:
    - name: str
    - role: Optional[str]
    - linkedin_url: Optional[str]
    - found: bool
    - confidence: str ("high", "medium", "low")
    """
    import json
    import re
    import aiohttp
    
    logger.info(f"Starting contact lookup for: {name} at {company_name}")
    
    # Strategy 1: Try direct LinkedIn URL patterns
    linkedin_url = await _try_linkedin_direct(name)
    if linkedin_url:
        logger.info(f"Found contact via direct URL: {linkedin_url}")
        return {
            "name": name,
            "found": True,
            "linkedin_url": linkedin_url,
            "role": None,  # Can't get role from direct lookup
            "confidence": "high"
        }
    
    # Strategy 2: Try Gemini with Google Search
    logger.debug("Direct lookup failed, trying Gemini...")
    result = await _try_gemini_search(name, company_name, country)
    if result.get("found"):
        return result
    
    # Strategy 3: Return not found but with suggested URL to try
    suggested_slug = _name_to_linkedin_slug(name)
    return {
        "name": name,
        "found": False,
        "linkedin_url": None,
        "role": None,
        "confidence": "low",
        "suggested_url": f"https://www.linkedin.com/in/{suggested_slug}"
    }


def _name_to_linkedin_slug(name: str) -> str:
    """Convert name to potential LinkedIn slug."""
    import re
    # Remove special chars, lowercase, replace spaces with hyphens
    slug = name.lower().strip()
    slug = re.sub(r'[^a-z0-9\s-]', '', slug)
    slug = re.sub(r'\s+', '-', slug)
    return slug


async def _try_linkedin_direct(name: str) -> Optional[str]:
    """Try to find LinkedIn profile via direct URL patterns."""
    import aiohttp
    
    slug = _name_to_linkedin_slug(name)
    
    # Generate URL variations
    variations = [
        f"https://www.linkedin.com/in/{slug}",
        f"https://www.linkedin.com/in/{slug.replace('-', '')}",
        f"https://linkedin.com/in/{slug}",
    ]
    
    # Also try without "van", "de", etc. for Dutch names
    parts = slug.split('-')
    if len(parts) > 2:
        # Try first-last only
        first_last = f"{parts[0]}-{parts[-1]}"
        variations.append(f"https://www.linkedin.com/in/{first_last}")
    
    logger.debug(f"Trying direct URLs: {variations}")
    
    timeout = aiohttp.ClientTimeout(total=5)
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
        "Accept": "text/html,application/xhtml+xml",
        "Accept-Language": "en-US,en;q=0.9,nl;q=0.8",
    }
    
    async with aiohttp.ClientSession(timeout=timeout, headers=headers) as session:
        for url in variations:
            try:
                async with session.head(url, allow_redirects=True) as response:
                    final_url = str(response.url)
                    logger.debug(f"{url} -> status={response.status}, final={final_url}")
                    
                    # LinkedIn returns 200 for valid profiles
                    # Redirects to /authwall or /login for invalid ones
                    if response.status == 200:
                        if "/authwall" not in final_url and "/login" not in final_url:
                            # Valid profile found!
                            return final_url
            except Exception as e:
                logger.debug(f"URL check failed for {url}: {e}")
                continue
    
    return None


async def _try_gemini_search(name: str, company_name: str, country: Optional[str]) -> dict:
    """Try to find contact via Gemini with Google Search."""
    import json
    import re
    
    try:
        from google import genai
        from google.genai import types
        
        api_key = os.getenv("GOOGLE_AI_API_KEY") or os.getenv("GOOGLE_API_KEY")
        if not api_key:
            logger.warning("No API key for Gemini")
            return {"name": name, "found": False, "confidence": "low"}
        
        client = genai.Client(api_key=api_key)
        
        search_query = f"{name} {company_name} linkedin"
        
        prompt = f"""Search for: {search_query}

Find the LinkedIn profile URL for {name} at {company_name}.

Return ONLY JSON:
{{"found": true, "linkedin_url": "https://linkedin.com/in/...", "role": "Job Title", "confidence": "high"}}

Or if not found:
{{"found": false, "linkedin_url": null, "role": null, "confidence": "low"}}
"""
        
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
            result_text = response.text.strip()
            logger.debug(f"Gemini response: {result_text[:200]}")
            
            # Extract JSON
            json_match = re.search(r'\{[^{}]*"found"[^{}]*\}', result_text, re.DOTALL)
            if json_match:
                result = json.loads(json_match.group(0))
                result["name"] = name
                
                # Validate LinkedIn URL
                if result.get("linkedin_url"):
                    if "linkedin.com/in/" not in result["linkedin_url"].lower():
                        result["linkedin_url"] = None
                        result["found"] = False
                
                return result
    
    except Exception as e:
        logger.error(f"Gemini lookup error: {e}")
    
    return {"name": name, "found": False, "confidence": "low"}


# ==================== Background Tasks ====================

def analyze_contact_background(
    contact_id: str,
    contact_name: str,
    contact_role: Optional[str],
    linkedin_url: Optional[str],
    research_id: str,
    organization_id: str,
    user_id: str,
    # User-provided info
    linkedin_about: Optional[str] = None,
    linkedin_experience: Optional[str] = None,
    additional_notes: Optional[str] = None,
    # i18n: output language
    language: str = "en"
):
    """Background task to analyze contact."""
    import asyncio
    
    try:
        logger.info(f"Starting contact analysis for {contact_name} in language: {language}")
        
        analyzer = get_contact_analyzer()
        
        # Get contexts
        company_context = asyncio.run(analyzer.get_company_context(research_id))
        seller_context = asyncio.run(analyzer.get_seller_context(organization_id, user_id))
        
        # Build user-provided context
        user_provided_context = {}
        if linkedin_about:
            user_provided_context["about"] = linkedin_about
        if linkedin_experience:
            user_provided_context["experience"] = linkedin_experience
        if additional_notes:
            user_provided_context["notes"] = additional_notes
        
        # Run analysis with language setting
        analysis = asyncio.run(analyzer.analyze_contact(
            contact_name=contact_name,
            contact_role=contact_role,
            linkedin_url=linkedin_url,
            company_context=company_context,
            seller_context=seller_context,
            language=language,
            user_provided_context=user_provided_context if user_provided_context else None
        ))
        
        # Update contact with analysis results
        update_data = {
            "profile_brief": analysis.get("profile_brief"),
            "communication_style": analysis.get("communication_style"),
            "decision_authority": analysis.get("decision_authority"),
            "probable_drivers": analysis.get("probable_drivers"),
            "opening_suggestions": analysis.get("opening_suggestions"),
            "questions_to_ask": analysis.get("questions_to_ask"),
            "topics_to_avoid": analysis.get("topics_to_avoid"),
            "analyzed_at": datetime.utcnow().isoformat(),
            "analysis_source": "linkedin" if linkedin_url else "role_based"
        }
        
        supabase_service.table("prospect_contacts")\
            .update(update_data)\
            .eq("id", contact_id)\
            .execute()
        
        logger.info(f"Contact analysis completed for {contact_name}")
        
    except Exception as e:
        logger.error(f"Contact analysis failed: {e}")
        # Update with error
        supabase_service.table("prospect_contacts")\
            .update({
                "profile_brief": f"# {contact_name}\n\nAnalysis failed: {str(e)}",
                "analyzed_at": datetime.utcnow().isoformat()
            })\
            .eq("id", contact_id)\
            .execute()


# ==================== Endpoints ====================

@router.post("/contacts/lookup", response_model=ContactLookupResponse)
async def lookup_contact(
    request: ContactLookupRequest,
    current_user: dict = Depends(get_current_user)
):
    """
    Lookup contact information online (LinkedIn URL, role/title).
    
    Uses Gemini with Google Search to find the person's LinkedIn profile
    and current job title at the specified company.
    
    Note: For multiple matches, use /contacts/search instead.
    """
    logger.info(f"Looking up contact: {request.name} at {request.company_name}")
    
    result = await lookup_contact_online(
        name=request.name,
        company_name=request.company_name,
        country=request.country
    )
    
    return ContactLookupResponse(
        name=result.get("name", request.name),
        role=result.get("role"),
        linkedin_url=result.get("linkedin_url"),
        headline=result.get("headline"),
        found=result.get("found", False),
        confidence=result.get("confidence", "low")
    )


@router.post("/contacts/search", response_model=ContactSearchResponse)
async def search_contact_profiles(
    request: ContactSearchRequest,
    current_user: dict = Depends(get_current_user)
):
    """
    Search for LinkedIn profiles matching a contact person.
    
    Returns up to 5 possible matches with confidence scores.
    User can then select the correct profile before adding the contact.
    
    If research_id is provided, the search will also match against
    executives found in the research data (instant, free matching).
    
    Uses Gemini with Google Search (primary, cheap) with Claude as fallback.
    """
    user_id = current_user.get("sub")
    organization_id = get_organization_id(user_id)
    
    logger.info(f"Searching contacts: {request.name} at {request.company_name}")
    
    # Extract research executives if research_id is provided
    research_executives = None
    if request.research_id:
        try:
            research_executives = await _get_research_executives(
                request.research_id, 
                organization_id
            )
            if research_executives:
                logger.info(f"Found {len(research_executives)} executives from research")
        except Exception as e:
            logger.warning(f"Could not load research executives: {e}")
    
    search_service = get_contact_search_service()
    
    result = await search_service.search_contact(
        name=request.name,
        role=request.role,
        company_name=request.company_name,
        company_linkedin_url=request.company_linkedin_url,
        research_executives=research_executives
    )
    
    # Convert internal models to response models
    matches = [
        ContactMatch(
            name=m.name,
            title=m.title,
            company=m.company,
            location=m.location,
            linkedin_url=m.linkedin_url,
            headline=m.headline,
            confidence=m.confidence,
            match_reason=m.match_reason,
            from_research=m.from_research
        )
        for m in result.matches
    ]
    
    return ContactSearchResponse(
        matches=matches,
        search_query_used=result.search_query_used,
        search_source=result.search_source,
        error=result.error
    )


async def _get_research_executives(
    research_id: str, 
    organization_id: str
) -> List[dict]:
    """
    Extract executives from research data.
    
    Parses both structured research_data and brief_content markdown.
    """
    try:
        response = supabase_service.table("research_briefs")\
            .select("research_data, brief_content, company_name")\
            .eq("id", research_id)\
            .eq("organization_id", organization_id)\
            .single()\
            .execute()
        
        if not response.data:
            return []
        
        research_data = response.data.get("research_data", {}) or {}
        brief_content = response.data.get("brief_content", "") or ""
        
        search_service = get_contact_search_service()
        executives = search_service.extract_executives_from_research(
            research_data, 
            brief_content
        )
        
        # Convert to dict format expected by search_contact
        return [
            {
                "name": e.name,
                "title": e.title,
                "linkedin_url": e.linkedin_url,
                "background": e.background,
                "relevance": e.relevance
            }
            for e in executives
        ]
    except Exception as e:
        logger.error(f"Error extracting research executives: {e}")
        return []


@router.get("/research/{research_id}/executives", response_model=ResearchExecutivesResponse)
async def get_research_executives(
    research_id: str,
    current_user: dict = Depends(get_current_user)
):
    """
    Get executives found in research data.
    
    Extracts leadership information from the research brief, including:
    - Names and titles from structured data
    - Names and LinkedIn URLs parsed from markdown tables/lists
    
    Use this to pre-populate contact suggestions in the UI.
    """
    user_id = current_user.get("sub")
    organization_id = get_organization_id(user_id)
    
    try:
        response = supabase_service.table("research_briefs")\
            .select("research_data, brief_content, company_name")\
            .eq("id", research_id)\
            .eq("organization_id", organization_id)\
            .single()\
            .execute()
        
        if not response.data:
            raise HTTPException(status_code=404, detail="Research not found")
        
        research_data = response.data.get("research_data", {}) or {}
        brief_content = response.data.get("brief_content", "") or ""
        company_name = response.data.get("company_name", "")
        
        search_service = get_contact_search_service()
        executives = search_service.extract_executives_from_research(
            research_data, 
            brief_content
        )
        
        return ResearchExecutivesResponse(
            executives=[
                ResearchExecutive(
                    name=e.name,
                    title=e.title,
                    linkedin_url=e.linkedin_url,
                    background=e.background
                )
                for e in executives
            ],
            company_name=company_name,
            source="research_brief"
        )
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting research executives: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/research/{research_id}/contacts", response_model=ContactResponse)
async def add_contact_to_research(
    research_id: str,
    contact: ContactCreate,
    background_tasks: BackgroundTasks,
    current_user: dict = Depends(get_current_user)
):
    """
    Add a contact person to a research and start analysis.
    
    The contact will be linked to the prospect associated with the research.
    Analysis runs in the background and updates the contact when complete.
    """
    user_id = current_user.get("sub")
    organization_id = get_organization_id(user_id)
    
    # Get user's preferred output language from settings
    output_language = "en"  # Default to English
    try:
        settings_response = supabase_service.table("user_settings")\
            .select("output_language")\
            .eq("user_id", user_id)\
            .maybe_single()\
            .execute()
        if settings_response.data and settings_response.data.get("output_language"):
            output_language = settings_response.data["output_language"]
            logger.info(f"Using user's output language: {output_language}")
    except Exception as e:
        logger.warning(f"Could not get user settings, using default language: {e}")
    
    # Get prospect_id from research
    prospect_id = get_prospect_id_from_research(research_id, organization_id)
    
    # Create contact record
    contact_id = str(uuid4())
    
    contact_data = {
        "id": contact_id,
        "prospect_id": prospect_id,
        "organization_id": organization_id,
        "name": contact.name,
        "role": contact.role,
        "email": contact.email,
        "phone": contact.phone,
        "linkedin_url": contact.linkedin_url,
        "is_primary": contact.is_primary,
        "analysis_source": "pending"
    }
    
    try:
        result = supabase_service.table("prospect_contacts")\
            .insert(contact_data)\
            .execute()
        
        if not result.data:
            raise HTTPException(status_code=500, detail="Failed to create contact")
        
        created_contact = result.data[0]
        
        # Start analysis via Inngest (if enabled) or BackgroundTasks (fallback)
        if use_inngest_for("contacts"):
            event_sent = await send_event(
                Events.CONTACT_ADDED,
                {
                    "contact_id": contact_id,
                    "contact_name": contact.name,
                    "contact_role": contact.role,
                    "linkedin_url": contact.linkedin_url,
                    "research_id": research_id,
                    "organization_id": organization_id,
                    "user_id": user_id,
                    "linkedin_about": contact.linkedin_about,
                    "linkedin_experience": contact.linkedin_experience,
                    "additional_notes": contact.additional_notes,
                    "language": output_language
                },
                user={"id": user_id}
            )
            
            if event_sent:
                logger.info(f"Contact {contact_id} analysis triggered via Inngest")
            else:
                # Fallback to BackgroundTasks if Inngest fails
                logger.warning(f"Inngest event failed, falling back to BackgroundTasks for contact {contact_id}")
                background_tasks.add_task(
                    analyze_contact_background,
                    contact_id,
                    contact.name,
                    contact.role,
                    contact.linkedin_url,
                    research_id,
                    organization_id,
                    user_id,
                    contact.linkedin_about,
                    contact.linkedin_experience,
                    contact.additional_notes,
                    output_language
                )
        else:
            # Use BackgroundTasks (legacy/fallback)
            background_tasks.add_task(
                analyze_contact_background,
                contact_id,
                contact.name,
                contact.role,
                contact.linkedin_url,
                research_id,
                organization_id,
                user_id,
                contact.linkedin_about,
                contact.linkedin_experience,
                contact.additional_notes,
                output_language
            )
            logger.info(f"Contact {contact_id} analysis triggered via BackgroundTasks")
        
        return ContactResponse(
            id=created_contact["id"],
            prospect_id=created_contact["prospect_id"],
            name=created_contact["name"],
            role=created_contact.get("role"),
            email=created_contact.get("email"),
            phone=created_contact.get("phone"),
            linkedin_url=created_contact.get("linkedin_url"),
            communication_style=None,
            decision_authority=None,
            probable_drivers=None,
            profile_brief="Analysis in progress...",
            opening_suggestions=None,
            questions_to_ask=None,
            topics_to_avoid=None,
            is_primary=created_contact.get("is_primary", False),
            analyzed_at=None,
            created_at=created_contact["created_at"]
        )
        
    except Exception as e:
        logger.error(f"Error creating contact: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/research/{research_id}/contacts", response_model=ContactListResponse)
async def list_contacts_for_research(
    research_id: str,
    current_user: dict = Depends(get_current_user)
):
    """List all contacts for a research."""
    user_id = current_user.get("sub")
    organization_id = get_organization_id(user_id)
    
    # Get prospect_id from research
    prospect_id = get_prospect_id_from_research(research_id, organization_id)
    
    # Get contacts for prospect
    response = supabase_service.table("prospect_contacts")\
        .select("*")\
        .eq("prospect_id", prospect_id)\
        .eq("organization_id", organization_id)\
        .order("is_primary", desc=True)\
        .order("created_at", desc=True)\
        .execute()
    
    contacts = []
    for c in response.data or []:
        contacts.append(ContactResponse(
            id=c["id"],
            prospect_id=c["prospect_id"],
            name=c["name"],
            role=c.get("role"),
            email=c.get("email"),
            phone=c.get("phone"),
            linkedin_url=c.get("linkedin_url"),
            communication_style=c.get("communication_style"),
            decision_authority=c.get("decision_authority"),
            probable_drivers=c.get("probable_drivers"),
            profile_brief=c.get("profile_brief"),
            opening_suggestions=c.get("opening_suggestions"),
            questions_to_ask=c.get("questions_to_ask"),
            topics_to_avoid=c.get("topics_to_avoid"),
            is_primary=c.get("is_primary", False),
            analyzed_at=c.get("analyzed_at"),
            created_at=c["created_at"]
        ))
    
    return ContactListResponse(contacts=contacts, count=len(contacts))


@router.get("/prospects/{prospect_id}/contacts", response_model=ContactListResponse)
async def list_contacts_for_prospect(
    prospect_id: str,
    current_user: dict = Depends(get_current_user)
):
    """List all contacts for a prospect."""
    user_id = current_user.get("sub")
    organization_id = get_organization_id(user_id)
    
    # Verify prospect belongs to organization
    prospect_check = supabase_service.table("prospects")\
        .select("id")\
        .eq("id", prospect_id)\
        .eq("organization_id", organization_id)\
        .execute()
    
    if not prospect_check.data:
        raise HTTPException(status_code=404, detail="Prospect not found")
    
    # Get contacts
    response = supabase_service.table("prospect_contacts")\
        .select("*")\
        .eq("prospect_id", prospect_id)\
        .eq("organization_id", organization_id)\
        .order("is_primary", desc=True)\
        .order("created_at", desc=True)\
        .execute()
    
    contacts = []
    for c in response.data or []:
        contacts.append(ContactResponse(
            id=c["id"],
            prospect_id=c["prospect_id"],
            name=c["name"],
            role=c.get("role"),
            email=c.get("email"),
            phone=c.get("phone"),
            linkedin_url=c.get("linkedin_url"),
            communication_style=c.get("communication_style"),
            decision_authority=c.get("decision_authority"),
            probable_drivers=c.get("probable_drivers"),
            profile_brief=c.get("profile_brief"),
            opening_suggestions=c.get("opening_suggestions"),
            questions_to_ask=c.get("questions_to_ask"),
            topics_to_avoid=c.get("topics_to_avoid"),
            is_primary=c.get("is_primary", False),
            analyzed_at=c.get("analyzed_at"),
            created_at=c["created_at"]
        ))
    
    return ContactListResponse(contacts=contacts, count=len(contacts))


@router.get("/contacts", response_model=ContactListResponse)
async def get_contacts_by_ids(
    ids: str,  # Comma-separated contact IDs
    current_user: dict = Depends(get_current_user)
):
    """Get multiple contacts by IDs (comma-separated)."""
    user_id = current_user.get("sub")
    organization_id = get_organization_id(user_id)
    
    # Parse IDs
    contact_ids = [id.strip() for id in ids.split(",") if id.strip()]
    
    if not contact_ids:
        return ContactListResponse(contacts=[], count=0)
    
    # Get contacts
    response = supabase_service.table("prospect_contacts")\
        .select("*")\
        .in_("id", contact_ids)\
        .eq("organization_id", organization_id)\
        .execute()
    
    contacts = []
    for c in response.data or []:
        contacts.append(ContactResponse(
            id=c["id"],
            prospect_id=c["prospect_id"],
            name=c["name"],
            role=c.get("role"),
            email=c.get("email"),
            phone=c.get("phone"),
            linkedin_url=c.get("linkedin_url"),
            communication_style=c.get("communication_style"),
            decision_authority=c.get("decision_authority"),
            probable_drivers=c.get("probable_drivers"),
            profile_brief=c.get("profile_brief"),
            opening_suggestions=c.get("opening_suggestions"),
            questions_to_ask=c.get("questions_to_ask"),
            topics_to_avoid=c.get("topics_to_avoid"),
            is_primary=c.get("is_primary", False),
            analyzed_at=c.get("analyzed_at"),
            created_at=c["created_at"]
        ))
    
    return ContactListResponse(contacts=contacts, count=len(contacts))


@router.get("/contacts/{contact_id}", response_model=ContactResponse)
async def get_contact(
    contact_id: str,
    current_user: dict = Depends(get_current_user)
):
    """Get a single contact by ID."""
    user_id = current_user.get("sub")
    organization_id = get_organization_id(user_id)
    
    response = supabase_service.table("prospect_contacts")\
        .select("*")\
        .eq("id", contact_id)\
        .eq("organization_id", organization_id)\
        .single()\
        .execute()
    
    if not response.data:
        raise HTTPException(status_code=404, detail="Contact not found")
    
    c = response.data
    return ContactResponse(
        id=c["id"],
        prospect_id=c["prospect_id"],
        name=c["name"],
        role=c.get("role"),
        email=c.get("email"),
        phone=c.get("phone"),
        linkedin_url=c.get("linkedin_url"),
        communication_style=c.get("communication_style"),
        decision_authority=c.get("decision_authority"),
        probable_drivers=c.get("probable_drivers"),
        profile_brief=c.get("profile_brief"),
        opening_suggestions=c.get("opening_suggestions"),
        questions_to_ask=c.get("questions_to_ask"),
        topics_to_avoid=c.get("topics_to_avoid"),
        is_primary=c.get("is_primary", False),
        analyzed_at=c.get("analyzed_at"),
        created_at=c["created_at"]
    )


class ContactUpdate(BaseModel):
    """Request model for updating a contact."""
    name: Optional[str] = None
    role: Optional[str] = None
    email: Optional[str] = None
    phone: Optional[str] = None
    linkedin_url: Optional[str] = None
    is_primary: Optional[bool] = None
    profile_brief: Optional[str] = None  # For editing the analysis


@router.patch("/contacts/{contact_id}", response_model=ContactResponse)
async def update_contact(
    contact_id: str,
    updates: ContactUpdate,
    current_user: dict = Depends(get_current_user)
):
    """
    Update a contact's information or analysis.
    
    Can be used to:
    - Edit contact details (name, role, email, phone)
    - Edit the profile_brief (analysis content)
    - Set/unset primary contact status
    """
    user_id = current_user.get("sub")
    organization_id = get_organization_id(user_id)
    
    # Verify contact exists and belongs to org
    check = supabase_service.table("prospect_contacts")\
        .select("*")\
        .eq("id", contact_id)\
        .eq("organization_id", organization_id)\
        .single()\
        .execute()
    
    if not check.data:
        raise HTTPException(status_code=404, detail="Contact not found")
    
    # Build update dict from non-None fields
    update_data = {}
    if updates.name is not None:
        update_data["name"] = updates.name
    if updates.role is not None:
        update_data["role"] = updates.role
    if updates.email is not None:
        update_data["email"] = updates.email
    if updates.phone is not None:
        update_data["phone"] = updates.phone
    if updates.linkedin_url is not None:
        update_data["linkedin_url"] = updates.linkedin_url
    if updates.is_primary is not None:
        update_data["is_primary"] = updates.is_primary
    if updates.profile_brief is not None:
        update_data["profile_brief"] = updates.profile_brief
    
    if not update_data:
        raise HTTPException(status_code=400, detail="No updates provided")
    
    # Update
    result = supabase_service.table("prospect_contacts")\
        .update(update_data)\
        .eq("id", contact_id)\
        .execute()
    
    if not result.data:
        raise HTTPException(status_code=500, detail="Failed to update contact")
    
    c = result.data[0]
    logger.info(f"Updated contact {contact_id}: {list(update_data.keys())}")
    
    return ContactResponse(
        id=c["id"],
        prospect_id=c["prospect_id"],
        name=c["name"],
        role=c.get("role"),
        email=c.get("email"),
        phone=c.get("phone"),
        linkedin_url=c.get("linkedin_url"),
        communication_style=c.get("communication_style"),
        decision_authority=c.get("decision_authority"),
        probable_drivers=c.get("probable_drivers"),
        profile_brief=c.get("profile_brief"),
        opening_suggestions=c.get("opening_suggestions"),
        questions_to_ask=c.get("questions_to_ask"),
        topics_to_avoid=c.get("topics_to_avoid"),
        is_primary=c.get("is_primary", False),
        analyzed_at=c.get("analyzed_at"),
        created_at=c["created_at"]
    )


@router.delete("/contacts/{contact_id}")
async def delete_contact(
    contact_id: str,
    current_user: dict = Depends(get_current_user)
):
    """Delete a contact."""
    user_id = current_user.get("sub")
    organization_id = get_organization_id(user_id)
    
    # Verify contact exists and belongs to org
    check = supabase_service.table("prospect_contacts")\
        .select("id")\
        .eq("id", contact_id)\
        .eq("organization_id", organization_id)\
        .execute()
    
    if not check.data:
        raise HTTPException(status_code=404, detail="Contact not found")
    
    # Delete
    supabase_service.table("prospect_contacts")\
        .delete()\
        .eq("id", contact_id)\
        .execute()
    
    return {"message": "Contact deleted"}


@router.post("/contacts/{contact_id}/reanalyze", response_model=ContactResponse)
async def reanalyze_contact(
    contact_id: str,
    background_tasks: BackgroundTasks,
    current_user: dict = Depends(get_current_user)
):
    """Re-run analysis for a contact."""
    user_id = current_user.get("sub")
    organization_id = get_organization_id(user_id)
    
    # Get user's preferred output language from settings
    output_language = "en"  # Default to English
    try:
        settings_response = supabase_service.table("user_settings")\
            .select("output_language")\
            .eq("user_id", user_id)\
            .maybe_single()\
            .execute()
        if settings_response.data and settings_response.data.get("output_language"):
            output_language = settings_response.data["output_language"]
    except Exception:
        pass
    
    # Get contact
    response = supabase_service.table("prospect_contacts")\
        .select("*, prospects(id)")\
        .eq("id", contact_id)\
        .eq("organization_id", organization_id)\
        .single()\
        .execute()
    
    if not response.data:
        raise HTTPException(status_code=404, detail="Contact not found")
    
    contact = response.data
    
    # Find a research for this prospect to get company context
    research_response = supabase_service.table("research_briefs")\
        .select("id")\
        .eq("prospect_id", contact["prospect_id"])\
        .eq("organization_id", organization_id)\
        .order("created_at", desc=True)\
        .limit(1)\
        .execute()
    
    research_id = research_response.data[0]["id"] if research_response.data else None
    
    if not research_id:
        raise HTTPException(status_code=400, detail="No research found for this prospect")
    
    # Clear old analysis
    supabase_service.table("prospect_contacts")\
        .update({
            "profile_brief": "Re-analyzing...",
            "analyzed_at": None
        })\
        .eq("id", contact_id)\
        .execute()
    
    # Start analysis via Inngest (if enabled) or BackgroundTasks (fallback)
    if use_inngest_for("contacts"):
        event_sent = await send_event(
            Events.CONTACT_ADDED,
            {
                "contact_id": contact_id,
                "contact_name": contact["name"],
                "contact_role": contact.get("role"),
                "linkedin_url": contact.get("linkedin_url"),
                "research_id": research_id,
                "organization_id": organization_id,
                "user_id": user_id,
                "language": output_language
            },
            user={"id": user_id}
        )
        
        if event_sent:
            logger.info(f"Contact {contact_id} re-analysis triggered via Inngest")
        else:
            logger.warning(f"Inngest event failed, falling back to BackgroundTasks")
            background_tasks.add_task(
                analyze_contact_background,
                contact_id,
                contact["name"],
                contact.get("role"),
                contact.get("linkedin_url"),
                research_id,
                organization_id,
                user_id,
                None, None, None,
                output_language
            )
    else:
        background_tasks.add_task(
            analyze_contact_background,
            contact_id,
            contact["name"],
            contact.get("role"),
            contact.get("linkedin_url"),
            research_id,
            organization_id,
            user_id,
            None, None, None,
            output_language
        )
    
    return ContactResponse(
        id=contact["id"],
        prospect_id=contact["prospect_id"],
        name=contact["name"],
        role=contact.get("role"),
        email=contact.get("email"),
        phone=contact.get("phone"),
        linkedin_url=contact.get("linkedin_url"),
        communication_style=None,
        decision_authority=None,
        probable_drivers=None,
        profile_brief="Re-analyzing...",
        opening_suggestions=None,
        questions_to_ask=None,
        topics_to_avoid=None,
        is_primary=contact.get("is_primary", False),
        analyzed_at=None,
        created_at=contact["created_at"]
    )

