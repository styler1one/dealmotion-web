"""
Preparation Router

API endpoints for meeting preparation management.
"""

from fastapi import APIRouter, Depends, HTTPException, BackgroundTasks, Request
from pydantic import BaseModel, Field
from typing import List, Optional
from datetime import datetime
import logging
from slowapi import Limiter
from slowapi.util import get_remote_address
from app.deps import get_current_user
from app.database import get_supabase_service
from app.utils.errors import handle_exception

# Rate limiter
limiter = Limiter(key_func=get_remote_address)
from app.services.rag_service import rag_service
from app.services.prep_generator import prep_generator
from app.services.prospect_service import get_prospect_service
from app.services.usage_service import get_usage_service

# Inngest integration
from app.inngest.events import send_event, use_inngest_for, Events

logger = logging.getLogger(__name__)

router = APIRouter()

# Pydantic models
class PrepStartRequest(BaseModel):
    prospect_company_name: str = Field(..., min_length=1, max_length=255)
    meeting_type: str = Field(..., pattern="^(discovery|demo|closing|follow_up|other)$")
    custom_notes: Optional[str] = None
    contact_ids: Optional[List[str]] = None  # Selected contact persons for this meeting
    deal_id: Optional[str] = None  # Optional deal to link this prep to
    calendar_meeting_id: Optional[str] = None  # Link to calendar meeting (SPEC-038)
    language: Optional[str] = "en"  # i18n: output language (default: English)


class PrepResponse(BaseModel):
    id: str
    prospect_company_name: str
    meeting_type: str
    status: str
    custom_notes: Optional[str]
    brief_content: Optional[str]
    talking_points: Optional[List[dict]]
    questions: Optional[List[str]]
    strategy: Optional[str]
    pdf_url: Optional[str]
    created_at: datetime
    completed_at: Optional[datetime]


class PrepListResponse(BaseModel):
    preps: List[dict]
    total: int


# Use centralized database module
supabase = get_supabase_service()


def generate_prep_background(
    prep_id: str,
    prospect_company: str,
    meeting_type: str,
    organization_id: str,
    user_id: str,
    custom_notes: Optional[str],
    contact_ids: Optional[List[str]] = None,
    language: str = "en"  # i18n: output language (default: English)
):
    """Background task to generate meeting prep (synchronous for BackgroundTasks)"""
    import asyncio
    
    async def _generate():
        """Inner async function to do the actual work"""
        try:
            # Update status to generating
            supabase.table("meeting_preps").update({
                "status": "generating"
            }).eq("id", prep_id).execute()
            
            logger.info(f"Starting prep generation for {prep_id}")
            
            # Build context using RAG (now includes profile context)
            context = await rag_service.build_context_for_ai(
                prospect_company=prospect_company,
                meeting_type=meeting_type,
                organization_id=organization_id,
                user_id=user_id,
                custom_notes=custom_notes
            )
            
            # Fetch contact persons if specified
            contacts_data = []
            if contact_ids:
                logger.info(f"Fetching {len(contact_ids)} contacts for prep")
                contacts_response = supabase.table("prospect_contacts")\
                    .select("*")\
                    .in_("id", contact_ids)\
                    .eq("organization_id", organization_id)\
                    .execute()
                
                if contacts_response.data:
                    contacts_data = contacts_response.data
                    logger.info(f"Found {len(contacts_data)} contacts with analysis")
            
            # Add contacts to context
            context["contacts"] = contacts_data
            context["has_contacts"] = len(contacts_data) > 0
            
            # Generate brief with AI
            result = await prep_generator.generate_meeting_brief(context, language=language)
            
            # Update database with results
            supabase.table("meeting_preps").update({
                "status": "completed",
                "brief_content": result["brief_content"],
                "talking_points": result["talking_points"],
                "questions": result["questions"],
                "strategy": result["strategy"],
                "rag_sources": result["rag_sources"],
                "completed_at": datetime.utcnow().isoformat()
            }).eq("id", prep_id).execute()
            
            logger.info(f"Successfully completed prep generation for {prep_id}")
            
        except Exception as e:
            logger.error(f"Error generating prep {prep_id}: {e}")
            
            # Update status to failed
            supabase.table("meeting_preps").update({
                "status": "failed",
                "error_message": str(e)
            }).eq("id", prep_id).execute()
    
    # Run the async function in a new event loop (like research does)
    asyncio.run(_generate())


@router.post("/start", response_model=dict, status_code=202)
@limiter.limit("10/minute")
async def start_prep(
    request: Request,  # Required for rate limiting (must be named 'request')
    body: PrepStartRequest,
    background_tasks: BackgroundTasks,
    current_user: dict = Depends(get_current_user)
):
    """
    Start a new meeting prep generation
    
    Returns immediately with prep ID, generation happens in background.
    Rate limited to 10 requests per minute.
    """
    try:
        # Supabase JWT stores user id as 'sub' (subject)
        user_id = current_user.get("sub") or current_user.get("id")
        if not user_id:
            raise HTTPException(status_code=401, detail="Could not get user ID from token")
        
        # Get user's organization
        org_response = supabase.table("organization_members").select(
            "organization_id"
        ).eq("user_id", user_id).limit(1).execute()
        
        if not org_response.data:
            raise HTTPException(status_code=404, detail="User not in any organization")
        
        organization_id = org_response.data[0]["organization_id"]
        
        # Check subscription limit
        usage_service = get_usage_service()
        limit_check = await usage_service.check_limit(organization_id, "preparation")
        if not limit_check.get("allowed"):
            raise HTTPException(
                status_code=402,  # Payment Required
                detail={
                    "error": "limit_exceeded",
                    "message": "You have reached your preparation limit for this month",
                    "current": limit_check.get("current", 0),
                    "limit": limit_check.get("limit", 0),
                    "upgrade_url": "/pricing"
                }
            )
        
        # Get or create prospect (NEW!)
        prospect_service = get_prospect_service()
        prospect_id = prospect_service.get_or_create_prospect(
            organization_id=organization_id,
            company_name=body.prospect_company_name
        )
        
        # Check if research brief exists (now also by prospect_id)
        research_response = supabase.table("research_briefs").select("id").eq(
            "organization_id", organization_id
        ).eq(
            "status", "completed"
        )
        
        # Try to find by prospect_id first, then fallback to company name
        if prospect_id:
            research_response = research_response.eq("prospect_id", prospect_id)
        else:
            research_response = research_response.ilike(
                "company_name", f"%{body.prospect_company_name}%"
            )
        
        research_response = research_response.limit(1).execute()
        research_brief_id = research_response.data[0]["id"] if research_response.data else None
        
        # Create prep record with prospect_id, deal_id and contact_ids
        prep_data = {
            "organization_id": organization_id,
            "user_id": user_id,
            "prospect_id": prospect_id,  # Link to prospect!
            "deal_id": body.deal_id,  # Link to deal (optional)
            "prospect_company_name": body.prospect_company_name,
            "meeting_type": body.meeting_type,
            "custom_notes": body.custom_notes,
            "status": "pending",
            "research_brief_id": research_brief_id,
            "contact_ids": body.contact_ids or []  # Store linked contacts
        }
        
        response = supabase.table("meeting_preps").insert(prep_data).execute()
        
        if not response.data:
            raise HTTPException(status_code=500, detail="Failed to create prep")
        
        prep = response.data[0]
        prep_id = prep["id"]
        
        # Link back to calendar meeting if provided (SPEC-038)
        if body.calendar_meeting_id:
            try:
                supabase.table("calendar_meetings").update({
                    "preparation_id": prep_id
                }).eq("id", body.calendar_meeting_id).eq(
                    "organization_id", organization_id
                ).execute()
                logger.info(f"Linked prep {prep_id} to calendar meeting {body.calendar_meeting_id}")
            except Exception as e:
                logger.warning(f"Failed to link prep to calendar meeting: {e}")
        
        # Start processing via Inngest (if enabled) or BackgroundTasks (fallback)
        if use_inngest_for("preparation"):
            # Use Inngest for durable execution and observability
            event_sent = await send_event(
                Events.PREP_REQUESTED,
                {
                    "prep_id": prep_id,
                    "prospect_company": body.prospect_company_name,
                    "meeting_type": body.meeting_type,
                    "organization_id": organization_id,
                    "user_id": user_id,
                    "custom_notes": body.custom_notes,
                    "contact_ids": body.contact_ids or [],
                    "language": body.language or "en"
                },
                user={"id": user_id}
            )
            
            if event_sent:
                logger.info(f"Prep {prep_id} triggered via Inngest")
            else:
                # Fallback to BackgroundTasks if Inngest fails
                logger.warning(f"Inngest event failed, falling back to BackgroundTasks for prep {prep_id}")
                background_tasks.add_task(
                    generate_prep_background,
                    prep_id,
                    body.prospect_company_name,
                    body.meeting_type,
                    organization_id,
                    user_id,
                    body.custom_notes,
                    body.contact_ids,
                    body.language or "en"
                )
        else:
            # Use BackgroundTasks (legacy/fallback)
            background_tasks.add_task(
                generate_prep_background,
                prep_id,
                body.prospect_company_name,
                body.meeting_type,
                organization_id,
                user_id,
                body.custom_notes,
                body.contact_ids,
                body.language or "en"
            )
            logger.info(f"Prep {prep_id} triggered via BackgroundTasks")
        
        # Increment usage counter
        await usage_service.increment_usage(organization_id, "preparation")
        
        contact_count = len(body.contact_ids) if body.contact_ids else 0
        logger.info(f"Created prep {prep_id} for {body.prospect_company_name} (prospect: {prospect_id}, contacts: {contact_count})")
        
        return {
            "id": prep_id,
            "prospect_id": prospect_id,
            "prospect_company_name": body.prospect_company_name,
            "meeting_type": body.meeting_type,
            "status": "pending",
            "created_at": prep["created_at"]
        }
        
    except HTTPException:
        raise
    except Exception as e:
        raise handle_exception(e, "start_prep", user_id=user_id)


@router.get("/briefs", response_model=PrepListResponse)
async def list_preps(
    meeting_type: Optional[str] = None,
    status: Optional[str] = None,
    limit: int = 20,
    offset: int = 0,
    current_user: dict = Depends(get_current_user)
):
    """List all meeting preps for user's organization"""
    try:
        user_id = current_user.get("sub") or current_user.get("id")
        
        # Get user's organization
        org_response = supabase.table("organization_members").select(
            "organization_id"
        ).eq("user_id", user_id).limit(1).execute()
        
        if not org_response.data:
            raise HTTPException(status_code=404, detail="User not in any organization")
        
        organization_id = org_response.data[0]["organization_id"]
        
        # Build query
        query = supabase.table("meeting_preps").select(
            "id, prospect_company_name, meeting_type, status, created_at, completed_at"
        ).eq("organization_id", organization_id)
        
        if meeting_type:
            query = query.eq("meeting_type", meeting_type)
        
        if status:
            query = query.eq("status", status)
        
        query = query.order("created_at", desc=True).range(offset, offset + limit - 1)
        
        response = query.execute()
        
        # Get total count
        count_response = supabase.table("meeting_preps").select(
            "id", count="exact"
        ).eq("organization_id", organization_id).execute()
        
        total = count_response.count if hasattr(count_response, 'count') else len(response.data)
        
        return {
            "preps": response.data,
            "total": total
        }
        
    except HTTPException:
        raise
    except Exception as e:
        raise handle_exception(e, "list_preps", user_id=user_id)


@router.get("/{prep_id}", response_model=dict)
async def get_prep(
    prep_id: str,
    current_user: dict = Depends(get_current_user)
):
    """Get specific meeting prep with full details"""
    try:
        user_id = current_user.get("sub") or current_user.get("id")
        
        # Get user's organization
        org_response = supabase.table("organization_members").select(
            "organization_id"
        ).eq("user_id", user_id).limit(1).execute()
        
        if not org_response.data:
            raise HTTPException(status_code=404, detail="User not in any organization")
        
        organization_id = org_response.data[0]["organization_id"]
        
        # Get prep
        response = supabase.table("meeting_preps").select("*").eq(
            "id", prep_id
        ).eq(
            "organization_id", organization_id
        ).limit(1).execute()
        
        if not response.data:
            raise HTTPException(status_code=404, detail="Prep not found")
        
        return response.data[0]
        
    except HTTPException:
        raise
    except Exception as e:
        raise handle_exception(e, "get_prep", user_id=user_id, resource_id=prep_id)


class UpdatePrepRequest(BaseModel):
    """Request model for updating preparation"""
    brief_content: Optional[str] = None
    custom_notes: Optional[str] = None


@router.patch("/{prep_id}", response_model=dict)
async def update_prep(
    prep_id: str,
    request: UpdatePrepRequest,
    current_user: dict = Depends(get_current_user)
):
    """Update meeting prep (brief content or notes)"""
    try:
        user_id = current_user.get("sub") or current_user.get("id")
        
        # Get user's organization
        org_response = supabase.table("organization_members").select(
            "organization_id"
        ).eq("user_id", user_id).limit(1).execute()
        
        if not org_response.data:
            raise HTTPException(status_code=404, detail="User not in any organization")
        
        organization_id = org_response.data[0]["organization_id"]
        
        # Build update data
        update_data = {}
        if request.brief_content is not None:
            update_data["brief_content"] = request.brief_content
        if request.custom_notes is not None:
            update_data["custom_notes"] = request.custom_notes
        
        if not update_data:
            raise HTTPException(status_code=400, detail="No fields to update")
        
        # Update prep
        response = supabase.table("meeting_preps").update(update_data).eq(
            "id", prep_id
        ).eq("organization_id", organization_id).execute()
        
        if not response.data:
            raise HTTPException(status_code=404, detail="Prep not found")
        
        return response.data[0]
        
    except HTTPException:
        raise
    except Exception as e:
        raise handle_exception(e, "update_prep", user_id=user_id, resource_id=prep_id)


@router.delete("/{prep_id}", status_code=204)
async def delete_prep(
    prep_id: str,
    current_user: dict = Depends(get_current_user)
):
    """Delete a meeting prep"""
    from app.services.coach_cleanup import cleanup_suggestions_for_entity
    
    try:
        user_id = current_user.get("sub") or current_user.get("id")
        
        # Get user's organization
        org_response = supabase.table("organization_members").select(
            "organization_id"
        ).eq("user_id", user_id).limit(1).execute()
        
        if not org_response.data:
            raise HTTPException(status_code=404, detail="User not in any organization")
        
        organization_id = org_response.data[0]["organization_id"]
        
        # Clean up related coach suggestions
        await cleanup_suggestions_for_entity(supabase, "prep", prep_id, user_id)
        
        # Delete prep
        response = supabase.table("meeting_preps").delete().eq(
            "id", prep_id
        ).eq(
            "organization_id", organization_id
        ).execute()
        
        if not response.data:
            raise HTTPException(status_code=404, detail="Prep not found")
        
        return None
        
    except HTTPException:
        raise
    except Exception as e:
        raise handle_exception(e, "delete_prep", user_id=user_id, resource_id=prep_id)
