"""
Research Agent API endpoints.
"""
import uuid
import logging
from typing import Optional
from fastapi import APIRouter, Depends, HTTPException, BackgroundTasks, Response, Request
from fastapi.responses import JSONResponse
from pydantic import BaseModel
from slowapi import Limiter
from slowapi.util import get_remote_address

logger = logging.getLogger(__name__)

from app.deps import get_current_user, get_auth_token
from app.utils.errors import handle_exception

# Get limiter from app state
limiter = Limiter(key_func=get_remote_address)
from app.database import get_supabase_service, get_user_client
from app.services.prospect_service import get_prospect_service
from app.services.company_lookup import get_company_lookup
from app.services.usage_service import get_usage_service
from app.inngest.events import send_event, Events, use_inngest_for, get_research_event, get_research_architecture


router = APIRouter()

# Use centralized database module
supabase_service = get_supabase_service()


# Request/Response models
class ResearchRequest(BaseModel):
    company_name: str
    company_linkedin_url: Optional[str] = None
    company_website_url: Optional[str] = None  # Direct website scraping
    country: Optional[str] = None
    city: Optional[str] = None
    custom_intel: Optional[str] = None  # User's own knowledge about the prospect
    # Note: language is now read from user_settings.output_language (not from request)


class ResearchResponse(BaseModel):
    id: str
    company_name: str
    prospect_id: Optional[str] = None
    status: str
    created_at: str


class LookupRequest(BaseModel):
    company_name: str
    country: Optional[str] = None


class LookupResponse(BaseModel):
    company_name: str
    country: Optional[str] = None
    website: Optional[str] = None
    website_confidence: int = 0
    linkedin_url: Optional[str] = None
    linkedin_confidence: int = 0
    suggestions_found: bool = False


class CompanySearchRequest(BaseModel):
    """Request for searching company options."""
    company_name: str
    country: str  # REQUIRED - we need country to find the right company


class CompanyOption(BaseModel):
    """A possible company match."""
    company_name: str
    description: Optional[str] = None
    website: Optional[str] = None
    linkedin_url: Optional[str] = None
    location: Optional[str] = None
    confidence: int = 0


class CompanySearchResponse(BaseModel):
    """Response with multiple company options."""
    query_company: str
    query_country: str
    options: list[CompanyOption] = []
    message: Optional[str] = None


# Background processing function
def process_research_background(
    research_id: str,
    company_name: str,
    country: Optional[str],
    city: Optional[str],
    linkedin_url: Optional[str],
    website_url: Optional[str] = None,
    organization_id: Optional[str] = None,  # NEW: For seller context
    user_id: Optional[str] = None,  # NEW: For sales profile
    language: str = "en"  # i18n: output language (default: English)
):
    """
    Background task to process research request.
    1. Execute parallel searches (Claude, Gemini, KVK, Website)
    2. Merge results with seller context (what you sell!)
    3. Generate PDF
    4. Update database
    """
    import asyncio
    from app.services.research_orchestrator import ResearchOrchestrator
    
    try:
        logger.info(f"Starting research for {company_name}")
        logger.debug(f"Seller context - org_id={organization_id}, user_id={user_id}")
        if website_url:
            logger.debug(f"Will scrape website: {website_url}")
        
        # Update status to researching
        supabase_service.table("research_briefs").update({
            "status": "researching"
        }).eq("id", research_id).execute()
        
        logger.debug("Status updated to researching")
        
        # Execute research with seller context using proper event loop handling
        orchestrator = ResearchOrchestrator()
        
        # Create a new event loop for this background task
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        try:
            research_data = loop.run_until_complete(orchestrator.research_company(
                company_name=company_name,
                country=country,
                city=city,
                linkedin_url=linkedin_url,
                website_url=website_url,
                organization_id=organization_id,  # NEW: Pass for seller context
                user_id=user_id,  # NEW: Pass for sales profile
                language=language  # i18n: output language
            ))
        finally:
            # Properly close the event loop and cleanup pending tasks
            try:
                # Cancel all pending tasks
                pending = asyncio.all_tasks(loop)
                for task in pending:
                    task.cancel()
                # Allow cancelled tasks to complete
                if pending:
                    loop.run_until_complete(asyncio.gather(*pending, return_exceptions=True))
                # Shutdown async generators
                loop.run_until_complete(loop.shutdown_asyncgens())
            finally:
                loop.close()
        
        logger.info(f"Research completed, got {len(research_data.get('sources', {}))} sources")
        logger.debug(f"Success count: {research_data.get('success_count', 0)}")
        
        # Store source data
        # Map source names to allowed source_type values in database
        source_type_map = {
            "claude": "claude",
            "claude_analysis": "claude",  # New Gemini-first architecture
            "gemini": "gemini",
            "kvk": "kvk",
            "website": "web",  # website scraper -> 'web' in database
            "knowledge_base": "web",  # KB chunks -> 'web' in database
            "premium": "premium",
            "web": "web"
        }
        
        for source_name, source_result in research_data["sources"].items():
            success = source_result.get('success', False)
            error = source_result.get('error', 'No error message')
            logger.debug(f"Source {source_name} - Success: {success}")
            if not success:
                logger.warning(f"Source {source_name} failed: {error}")
            
            # Map source_name to valid source_type
            source_type = source_type_map.get(source_name, "web")
            
            supabase_service.table("research_sources").insert({
                "research_id": research_id,
                "source_type": source_type,
                "source_name": source_name,
                "data": source_result
            }).execute()
        
        # Get the unified brief
        brief_content = research_data.get("brief", "")
        logger.debug(f"Brief length: {len(brief_content)} characters")
        
        # TODO: Generate PDF (Phase 2.5)
        pdf_url = None
        
        # Update research status to completed
        supabase_service.table("research_briefs").update({
            "status": "completed",
            "research_data": research_data,
            "brief_content": brief_content,
            "pdf_url": pdf_url,
            "completed_at": "now()"
        }).eq("id", research_id).execute()
        
        logger.info(f"Research {research_id} completed successfully")
        
    except Exception as e:
        logger.error(f"Research failed: {type(e).__name__}: {str(e)}", exc_info=True)
        
        # Update status to failed
        supabase_service.table("research_briefs").update({
            "status": "failed",
            "error_message": str(e)
        }).eq("id", research_id).execute()


@router.post("/start", response_model=ResearchResponse)
@limiter.limit("10/minute")
async def start_research(
    request: Request,  # Required for rate limiting
    body: ResearchRequest,
    background_tasks: BackgroundTasks,
    current_user: dict = Depends(get_current_user),
    auth_token: str = Depends(get_auth_token)
):
    """
    Start a new research brief.
    
    Rate limited to 10 requests per minute.
    """
    # Create user-specific client for RLS security
    user_supabase = get_user_client(auth_token)
    
    # Get user's organization
    user_id = current_user.get("sub")
    org_response = user_supabase.table("organization_members").select("organization_id").eq("user_id", user_id).execute()
    
    if not org_response.data:
        raise HTTPException(status_code=403, detail="User not in any organization")
    
    organization_id = org_response.data[0]["organization_id"]
    
    # Get user's preferred output language from settings (consistent with other routers)
    output_language = "en"  # Default to English
    try:
        settings_response = supabase_service.table("user_settings")\
            .select("output_language")\
            .eq("user_id", user_id)\
            .maybe_single()\
            .execute()
        if settings_response.data and settings_response.data.get("output_language"):
            output_language = settings_response.data["output_language"]
            logger.info(f"Using user's output language for research: {output_language}")
    except Exception as e:
        logger.warning(f"Could not get user settings, using default language: {e}")
    
    # Check subscription limit (v3: flow-based with flow pack fallback)
    usage_service = get_usage_service()
    limit_check = await usage_service.check_flow_limit(organization_id)
    use_flow_pack = limit_check.get("using_flow_pack", False)
    
    if not limit_check.get("allowed"):
        raise HTTPException(
            status_code=402,  # Payment Required
            detail={
                "error": "limit_exceeded",
                "message": "You have reached your flow limit for this month",
                "current": limit_check.get("current", 0),
                "limit": limit_check.get("limit", 0),
                "flow_pack_balance": limit_check.get("flow_pack_balance", 0),
                "upgrade_url": "/pricing"
            }
        )
    
    # Get or create prospect (NEW!)
    prospect_service = get_prospect_service()
    prospect_id = prospect_service.get_or_create_prospect(
        organization_id=organization_id,
        company_name=body.company_name
    )
    
    # Generate research ID
    research_id = str(uuid.uuid4())
    
    try:
        # Create database record with prospect_id
        db_record = {
            "id": research_id,
            "organization_id": organization_id,
            "user_id": user_id,
            "prospect_id": prospect_id,  # Link to prospect!
            "company_name": body.company_name,
            "company_linkedin_url": body.company_linkedin_url,
            "country": body.country,
            "city": body.city,
            "status": "pending"
        }
        
        # Only add custom_notes if provided (column may not exist in older schemas)
        if body.custom_intel:
            db_record["custom_notes"] = body.custom_intel
        
        result = supabase_service.table("research_briefs").insert(db_record).execute()
        
        # Update prospect with additional info if provided
        if prospect_id and (body.company_linkedin_url or body.company_website_url or body.country or body.city):
            updates = {}
            if body.company_linkedin_url:
                updates["linkedin_url"] = body.company_linkedin_url
            if body.company_website_url:
                updates["website"] = body.company_website_url
            if body.country:
                updates["country"] = body.country
            if body.city:
                updates["city"] = body.city
            if updates:
                prospect_service.update_prospect(prospect_id, organization_id, updates)
        
        # Start processing via Inngest (if enabled) or BackgroundTasks (fallback)
        use_background_tasks = True  # Default fallback
        
        if use_inngest_for("research"):
            # Determine which research architecture to use (V1 or V2)
            research_arch = get_research_architecture()
            research_event = get_research_event()
            
            # Try Inngest for durable execution and observability
            event_sent = await send_event(
                research_event,
                {
                    "research_id": research_id,
                    "company_name": body.company_name,
                    "country": body.country,
                    "city": body.city,
                    "linkedin_url": body.company_linkedin_url,
                    "website_url": body.company_website_url,
                    "custom_intel": body.custom_intel,  # User's own knowledge
                    "organization_id": organization_id,
                    "user_id": user_id,
                    "language": output_language
                },
                user={"id": user_id}
            )
            if event_sent:
                use_background_tasks = False
                logger.info(f"Research {research_id} triggered via Inngest ({research_arch})")
            else:
                logger.warning(f"Inngest event failed, falling back to BackgroundTasks for {research_id}")
        
        if use_background_tasks:
            # Fallback to BackgroundTasks
            background_tasks.add_task(
                process_research_background,
                research_id,
                body.company_name,
                body.country,
                body.city,
                body.company_linkedin_url,
                body.company_website_url,
                organization_id,
                user_id,
                output_language
            )
            logger.info(f"Research {research_id} triggered via BackgroundTasks")
        
        # Increment flow counter (v3: flow-based tracking with flow pack support)
        await usage_service.increment_flow(organization_id, use_flow_pack=use_flow_pack)
        
        return ResearchResponse(
            id=research_id,
            company_name=body.company_name,
            prospect_id=prospect_id,
            status="pending",
            created_at=result.data[0]["created_at"]
        )
        
    except Exception as e:
        raise handle_exception(e, "start_research", user_id=user_id)


@router.get("/briefs")
async def list_research_briefs(
    current_user: dict = Depends(get_current_user),
    auth_token: str = Depends(get_auth_token)
):
    """
    List all research briefs for user's organization.
    """
    # Create user-specific client for RLS security
    user_supabase = get_user_client(auth_token)
    
    # Get user's organization
    user_id = current_user.get("sub")
    org_response = user_supabase.table("organization_members").select("organization_id").eq("user_id", user_id).execute()
    
    if not org_response.data:
        raise HTTPException(status_code=403, detail="User not in any organization")
    
    organization_id = org_response.data[0]["organization_id"]
    
    # Get research briefs
    briefs_response = user_supabase.table("research_briefs").select("*").eq(
        "organization_id", organization_id
    ).order("created_at", desc=True).execute()
    
    return {"briefs": briefs_response.data}


@router.get("/{research_id}/status")
async def get_research_status(
    research_id: str,
    current_user: dict = Depends(get_current_user),
    auth_token: str = Depends(get_auth_token)
):
    """
    Get status of a specific research brief.
    """
    # Create user-specific client for RLS security
    user_supabase = get_user_client(auth_token)
    
    # Get research brief (RLS ensures user can only see their org's research)
    research_response = user_supabase.table("research_briefs").select("*").eq("id", research_id).execute()
    
    if not research_response.data:
        raise HTTPException(status_code=404, detail="Research not found")
    
    research = research_response.data[0]
    
    # Build progress info
    progress = {
        "status": research["status"],
        "created_at": research["created_at"],
        "completed_at": research.get("completed_at")
    }
    
    if research["status"] == "failed":
        progress["error"] = research.get("error_message")
    
    return progress


@router.delete("/{research_id}")
async def delete_research(
    research_id: str,
    current_user: dict = Depends(get_current_user),
    auth_token: str = Depends(get_auth_token)
):
    """
    Delete a research brief.
    """
    from app.services.coach_cleanup import cleanup_suggestions_for_entity
    
    # Create user-specific client for RLS security
    user_supabase = get_user_client(auth_token)
    
    # Get research brief to check ownership and get PDF URL
    research_response = user_supabase.table("research_briefs").select("*").eq("id", research_id).execute()
    
    if not research_response.data:
        raise HTTPException(status_code=404, detail="Research not found")
    
    research = research_response.data[0]
    user_id = current_user.get("sub") or current_user.get("id")
    
    try:
        # Delete PDF from storage if exists
        if research.get("pdf_url"):
            # Extract path from URL
            # TODO: Implement PDF deletion from storage
            pass
        
        # Clean up related coach suggestions
        await cleanup_suggestions_for_entity(
            supabase_service, 
            "research", 
            research_id, 
            user_id
        )
        
        # Delete research sources (will cascade)
        # Delete research brief (RLS ensures user can only delete their org's research)
        supabase_service.table("research_briefs").delete().eq("id", research_id).execute()
        
        return Response(status_code=204)
        
    except Exception as e:
        raise handle_exception(e, "delete_research", user_id=user_id, resource_id=research_id)


@router.get("/{research_id}/brief")
async def get_research_brief(
    research_id: str,
    current_user: dict = Depends(get_current_user),
    auth_token: str = Depends(get_auth_token)
):
    """
    Get the full research brief content.
    """
    # Create user-specific client for RLS security
    user_supabase = get_user_client(auth_token)
    
    # Get research brief (RLS ensures user can only see their org's research)
    research_response = user_supabase.table("research_briefs").select("*").eq("id", research_id).execute()
    
    if not research_response.data:
        raise HTTPException(status_code=404, detail="Research not found")
    
    research = research_response.data[0]
    
    if research["status"] != "completed":
        raise HTTPException(status_code=400, detail=f"Research is {research['status']}, not completed")
    
    return {
        "id": research["id"],
        "company_name": research["company_name"],
        "brief_content": research["brief_content"],
        "pdf_url": research.get("pdf_url"),
        "created_at": research["created_at"],
        "completed_at": research["completed_at"]
    }


class UpdateBriefRequest(BaseModel):
    """Request model for updating brief content"""
    brief_content: str


@router.patch("/{research_id}/brief")
async def update_research_brief(
    research_id: str,
    request: UpdateBriefRequest,
    current_user: dict = Depends(get_current_user),
    auth_token: str = Depends(get_auth_token)
):
    """
    Update the research brief content.
    Allows users to edit AI-generated briefs for accuracy and personalization.
    """
    user_id = current_user.get("sub")
    
    # Create user-specific client for RLS security
    user_supabase = get_user_client(auth_token)
    
    # Verify the research exists and belongs to user's org
    research_response = user_supabase.table("research_briefs").select("id, status").eq("id", research_id).execute()
    
    if not research_response.data:
        raise HTTPException(status_code=404, detail="Research not found")
    
    research = research_response.data[0]
    
    if research["status"] != "completed":
        raise HTTPException(status_code=400, detail="Can only edit completed research briefs")
    
    # Update the brief content
    try:
        update_response = user_supabase.table("research_briefs").update({
            "brief_content": request.brief_content
        }).eq("id", research_id).execute()
        
        if not update_response.data:
            raise HTTPException(status_code=500, detail="Failed to update brief")
        
        return {
            "id": research_id,
            "brief_content": request.brief_content,
            "updated_at": update_response.data[0].get("updated_at")
        }
        
    except Exception as e:
        raise handle_exception(e, "update_research", user_id=user_id, resource_id=research_id)


@router.post("/lookup", response_model=LookupResponse)
async def lookup_company(
    request: LookupRequest,
    current_user: dict = Depends(get_current_user)
):
    """
    Auto-lookup company website and LinkedIn URL based on company name and country.
    
    Returns URLs with confidence scores. Only returns suggestions with >= 80% confidence.
    Use this to pre-fill the research form.
    """
    try:
        lookup_service = get_company_lookup()
        result = await lookup_service.lookup_company(
            company_name=request.company_name,
            country=request.country
        )
        return LookupResponse(**result)
    except Exception as e:
        logger.warning(f"Lookup error: {e}")
        # Return empty result on error (non-blocking)
        return LookupResponse(
            company_name=request.company_name,
            country=request.country,
            suggestions_found=False
        )


@router.post("/search-company", response_model=CompanySearchResponse)
async def search_company_options(
    request: CompanySearchRequest,
    current_user: dict = Depends(get_current_user)
):
    """
    Search for company options matching name and country.
    
    Use this when:
    - User has entered both company name AND country
    - You want to show multiple possible matches for user to choose from
    
    Returns up to 3 companies with website, LinkedIn, and description.
    """
    try:
        if not request.country:
            return CompanySearchResponse(
                query_company=request.company_name,
                query_country=request.country,
                options=[],
                message="Country is required to find the correct company"
            )
        
        lookup_service = get_company_lookup()
        options = await lookup_service.search_company_options(
            company_name=request.company_name,
            country=request.country
        )
        
        # Convert to response model
        company_options = [
            CompanyOption(
                company_name=opt.get("company_name", request.company_name),
                description=opt.get("description"),
                website=opt.get("website"),
                linkedin_url=opt.get("linkedin_url"),
                location=opt.get("location"),
                confidence=opt.get("confidence", 0)
            )
            for opt in options
        ]
        
        return CompanySearchResponse(
            query_company=request.company_name,
            query_country=request.country,
            options=company_options,
            message=None if company_options else "No companies found"
        )
        
    except Exception as e:
        logger.error(f"Company search error: {e}")
        return CompanySearchResponse(
            query_company=request.company_name,
            query_country=request.country,
            options=[],
            message=f"Search failed: {str(e)}"
        )
