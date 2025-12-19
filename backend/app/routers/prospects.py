"""
Prospects Router - API endpoints for prospect management

Now uses the dedicated prospects table for proper data management.
"""

from fastapi import APIRouter, HTTPException, Depends, Query
from pydantic import BaseModel, Field
from typing import List, Dict, Any, Optional
from datetime import datetime
import logging

from app.deps import get_current_user
from app.database import get_supabase_service
from app.services.prospect_service import get_prospect_service

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/prospects", tags=["prospects"])

# Use centralized database module
supabase = get_supabase_service()


# Request/Response models
class ProspectCreate(BaseModel):
    company_name: str = Field(..., min_length=1, max_length=255)
    website: Optional[str] = None
    linkedin_url: Optional[str] = None
    industry: Optional[str] = None
    company_size: Optional[str] = None
    country: Optional[str] = None
    city: Optional[str] = None
    contact_name: Optional[str] = None
    contact_email: Optional[str] = None
    contact_role: Optional[str] = None
    contact_linkedin: Optional[str] = None
    notes: Optional[str] = None
    tags: Optional[List[str]] = None


class ProspectUpdate(BaseModel):
    company_name: Optional[str] = None
    website: Optional[str] = None
    linkedin_url: Optional[str] = None
    industry: Optional[str] = None
    company_size: Optional[str] = None
    country: Optional[str] = None
    city: Optional[str] = None
    contact_name: Optional[str] = None
    contact_email: Optional[str] = None
    contact_role: Optional[str] = None
    contact_linkedin: Optional[str] = None
    status: Optional[str] = None
    notes: Optional[str] = None
    tags: Optional[List[str]] = None


class ProspectResponse(BaseModel):
    id: str
    company_name: str
    status: str
    website: Optional[str] = None
    linkedin_url: Optional[str] = None
    industry: Optional[str] = None
    company_size: Optional[str] = None
    country: Optional[str] = None
    city: Optional[str] = None
    contact_name: Optional[str] = None
    contact_email: Optional[str] = None
    contact_role: Optional[str] = None
    tags: Optional[List[str]] = None
    created_at: datetime
    updated_at: datetime
    last_activity_at: datetime
    # Activity counts
    research_count: Optional[int] = 0
    prep_count: Optional[int] = 0
    followup_count: Optional[int] = 0


class ProspectListResponse(BaseModel):
    prospects: List[Dict[str, Any]]
    total: int


class ProspectStatsResponse(BaseModel):
    total: int
    by_status: Dict[str, int]


class StatusUpdate(BaseModel):
    status: str = Field(..., pattern="^(new|researching|qualified|meeting_scheduled|proposal_sent|won|lost|inactive)$")


class NoteCreate(BaseModel):
    content: str = Field(..., min_length=1, max_length=5000)
    is_pinned: bool = False


class NoteUpdate(BaseModel):
    content: Optional[str] = Field(None, min_length=1, max_length=5000)
    is_pinned: Optional[bool] = None


class ContactCreate(BaseModel):
    name: str = Field(..., min_length=1, max_length=255)
    role: Optional[str] = None
    email: Optional[str] = None
    phone: Optional[str] = None
    linkedin_url: Optional[str] = None
    decision_authority: Optional[str] = Field(None, pattern="^(decision_maker|influencer|gatekeeper|end_user)$")


def get_organization_id(current_user: dict) -> str:
    """Helper to get user's organization ID."""
    user_id = current_user.get("sub") or current_user.get("id")
    
    org_response = supabase.table("organization_members").select(
        "organization_id"
    ).eq("user_id", user_id).limit(1).execute()
    
    if not org_response.data:
        raise HTTPException(status_code=404, detail="User not in any organization")
    
    return org_response.data[0]["organization_id"]


@router.get("/stats", response_model=ProspectStatsResponse)
async def get_prospect_stats(
    current_user: dict = Depends(get_current_user)
):
    """
    Get prospect statistics (counts per status).
    
    Returns total count and breakdown by status.
    """
    try:
        organization_id = get_organization_id(current_user)
        
        # Get all prospects with just status field
        response = supabase.table("prospects").select(
            "status"
        ).eq("organization_id", organization_id).execute()
        
        # Count by status
        by_status: Dict[str, int] = {}
        for p in response.data or []:
            status = p.get("status", "new")
            by_status[status] = by_status.get(status, 0) + 1
        
        return {
            "total": len(response.data or []),
            "by_status": by_status
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting prospect stats: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("", response_model=ProspectListResponse)
async def list_prospects(
    status: Optional[str] = None,
    search: Optional[str] = None,
    sort_by: str = Query(default="last_activity_at", pattern="^(last_activity_at|company_name|created_at|status)$"),
    sort_order: str = Query(default="desc", pattern="^(asc|desc)$"),
    limit: int = Query(default=50, le=100),
    offset: int = 0,
    current_user: dict = Depends(get_current_user)
):
    """
    List all prospects for the organization.
    
    Args:
        status: Filter by status (new, researching, qualified, etc.)
        search: Search by company name
        sort_by: Sort field (last_activity_at, company_name, created_at, status)
        sort_order: Sort order (asc, desc)
        limit: Max results (default 50, max 100)
        offset: Pagination offset
    """
    try:
        organization_id = get_organization_id(current_user)
        
        # Build query - also get contact count
        query = supabase.table("prospects").select(
            "*, research_briefs(id), meeting_preps(id), followups(id), prospect_contacts(id)",
            count="exact"
        ).eq("organization_id", organization_id)
        
        if status:
            query = query.eq("status", status)
        
        if search and len(search) >= 2:
            query = query.ilike("company_name", f"%{search}%")
        
        # Apply sorting
        query = query.order(sort_by, desc=(sort_order == "desc")).range(offset, offset + limit - 1)
        
        response = query.execute()
        
        # Transform data to include activity counts
        prospects = []
        for p in response.data or []:
            prospect = {**p}
            prospect["research_count"] = len(p.get("research_briefs", []) or [])
            prospect["prep_count"] = len(p.get("meeting_preps", []) or [])
            prospect["followup_count"] = len(p.get("followups", []) or [])
            prospect["contact_count"] = len(p.get("prospect_contacts", []) or [])
            # Remove nested arrays
            prospect.pop("research_briefs", None)
            prospect.pop("meeting_preps", None)
            prospect.pop("followups", None)
            prospect.pop("prospect_contacts", None)
            prospects.append(prospect)
        
        return {
            "prospects": prospects,
            "total": response.count if hasattr(response, 'count') and response.count else len(prospects)
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error listing prospects: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/search", response_model=List[Dict[str, Any]])
async def search_prospects(
    q: str,
    limit: int = 10,
    current_user: dict = Depends(get_current_user)
):
    """
    Search prospects by name (for autocomplete).
    
    Args:
        q: Search query (min 2 characters)
        limit: Max results to return
    """
    if len(q) < 2:
        return []
    
    try:
        organization_id = get_organization_id(current_user)
        
        # Search by normalized name
        response = supabase.table("prospects").select(
            "id, company_name, status, industry, last_activity_at"
        ).eq(
            "organization_id", organization_id
        ).ilike(
            "company_name", f"%{q}%"
        ).order(
            "last_activity_at", desc=True
        ).limit(limit).execute()
        
        return response.data or []
        
    except Exception as e:
        logger.error(f"Error searching prospects: {e}")
        return []


@router.post("", response_model=Dict[str, Any], status_code=201)
async def create_prospect(
    request: ProspectCreate,
    current_user: dict = Depends(get_current_user)
):
    """
    Create a new prospect.
    """
    try:
        organization_id = get_organization_id(current_user)
        
        # Use prospect service for proper handling
        prospect_service = get_prospect_service()
        
        # Check if prospect already exists
        existing = prospect_service.get_prospect_by_name(
            organization_id=organization_id,
            company_name=request.company_name
        )
        
        if existing:
            raise HTTPException(
                status_code=409, 
                detail=f"Prospect '{request.company_name}' already exists"
            )
        
        # Create prospect
        prospect_data = {
            "organization_id": organization_id,
            "company_name": request.company_name,
            "website": request.website,
            "linkedin_url": request.linkedin_url,
            "industry": request.industry,
            "company_size": request.company_size,
            "country": request.country,
            "city": request.city,
            "contact_name": request.contact_name,
            "contact_email": request.contact_email,
            "contact_role": request.contact_role,
            "contact_linkedin": request.contact_linkedin,
            "notes": request.notes,
            "tags": request.tags or [],
            "status": "new"
        }
        
        # Remove None values
        prospect_data = {k: v for k, v in prospect_data.items() if v is not None}
        
        response = supabase.table("prospects").insert(prospect_data).execute()
        
        if not response.data:
            raise HTTPException(status_code=500, detail="Failed to create prospect")
        
        logger.info(f"Created prospect: {request.company_name}")
        
        return response.data[0]
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error creating prospect: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/{prospect_id}", response_model=Dict[str, Any])
async def get_prospect(
    prospect_id: str,
    current_user: dict = Depends(get_current_user)
):
    """
    Get a specific prospect with activity details.
    """
    try:
        organization_id = get_organization_id(current_user)
        
        # Get prospect with related data
        response = supabase.table("prospects").select(
            "*, research_briefs(id, status, created_at), meeting_preps(id, status, meeting_type, created_at), followups(id, status, created_at)"
        ).eq(
            "id", prospect_id
        ).eq(
            "organization_id", organization_id
        ).limit(1).execute()
        
        if not response.data:
            raise HTTPException(status_code=404, detail="Prospect not found")
        
        prospect = response.data[0]
        
        # Add activity counts
        prospect["research_count"] = len(prospect.get("research_briefs", []) or [])
        prospect["prep_count"] = len(prospect.get("meeting_preps", []) or [])
        prospect["followup_count"] = len(prospect.get("followups", []) or [])
        
        return prospect
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting prospect: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/{prospect_id}/hub", response_model=Dict[str, Any])
async def get_prospect_hub(
    prospect_id: str,
    current_user: dict = Depends(get_current_user)
):
    """
    Get complete prospect hub data for the Prospect Hub page.
    Returns prospect, research, contacts, stats, and recent activities.
    """
    try:
        organization_id = get_organization_id(current_user)
        
        # Get prospect basic info
        prospect_response = supabase.table("prospects").select("*").eq(
            "id", prospect_id
        ).eq(
            "organization_id", organization_id
        ).limit(1).execute()
        
        if not prospect_response.data:
            raise HTTPException(status_code=404, detail="Prospect not found")
        
        prospect = prospect_response.data[0]
        
        # Get latest research for this prospect (any status - to show "in progress")
        # First try to get completed research
        completed_research = supabase.table("research_briefs").select(
            "id, company_name, brief_content, status, created_at, completed_at"
        ).eq(
            "prospect_id", prospect_id
        ).eq(
            "status", "completed"
        ).order(
            "completed_at", desc=True
        ).limit(1).execute()
        
        if completed_research.data:
            research = completed_research.data[0]
        else:
            # No completed research, check for pending/researching
            in_progress_research = supabase.table("research_briefs").select(
                "id, company_name, brief_content, status, created_at, completed_at"
            ).eq(
                "prospect_id", prospect_id
            ).in_(
                "status", ["pending", "researching"]
            ).order(
                "created_at", desc=True
            ).limit(1).execute()
            
            research = in_progress_research.data[0] if in_progress_research.data else None
        
        # Get contacts for this prospect (include analysis fields for status display)
        contacts_response = supabase.table("prospect_contacts").select(
            "id, name, role, email, linkedin_url, communication_style, decision_authority, is_primary, "
            "profile_brief, opening_suggestions, questions_to_ask, topics_to_avoid, analyzed_at"
        ).eq(
            "prospect_id", prospect_id
        ).order(
            "is_primary", desc=True
        ).order(
            "created_at", desc=True
        ).execute()
        
        contacts = contacts_response.data or []
        
        # Get deals for this prospect
        deals_response = supabase.table("deals").select(
            "id, name, is_active, created_at"
        ).eq(
            "prospect_id", prospect_id
        ).eq(
            "is_active", True
        ).execute()
        
        deals = deals_response.data or []
        
        # Get preps and followups linked to this prospect (with contact_ids for display)
        preps_response = supabase.table("meeting_preps").select(
            "id, prospect_company_name, meeting_type, status, created_at, completed_at, contact_ids"
        ).eq(
            "prospect_id", prospect_id
        ).order(
            "created_at", desc=True
        ).execute()
        
        followups_response = supabase.table("followups").select(
            "id, prospect_company_name, meeting_subject, status, created_at, completed_at, contact_ids"
        ).eq(
            "prospect_id", prospect_id
        ).order(
            "created_at", desc=True
        ).execute()
        
        # Build contact name lookup from already fetched contacts
        contact_name_map = {c["id"]: c["name"] for c in contacts}
        
        # Enrich preps with contact names
        preparations = []
        for p in preps_response.data or []:
            prep = {**p}
            contact_ids = p.get("contact_ids") or []
            prep["contact_names"] = [contact_name_map.get(cid, "") for cid in contact_ids if contact_name_map.get(cid)]
            preparations.append(prep)
        
        # Enrich followups with contact names  
        followups = []
        for f in followups_response.data or []:
            fu = {**f}
            contact_ids = f.get("contact_ids") or []
            fu["contact_names"] = [contact_name_map.get(cid, "") for cid in contact_ids if contact_name_map.get(cid)]
            followups.append(fu)
        
        # Filter for completed counts in stats
        completed_preps = [p for p in preparations if p.get("status") == "completed"]
        completed_followups = [f for f in followups if f.get("status") == "completed"]
        
        # Get recent activities
        activities_response = supabase.table("prospect_activities").select(
            "id, activity_type, title, description, created_at"
        ).eq(
            "prospect_id", prospect_id
        ).order(
            "created_at", desc=True
        ).limit(10).execute()
        
        recent_activities = activities_response.data or []
        
        # Build stats
        stats = {
            "prospect_id": prospect_id,
            "company_name": prospect.get("company_name"),
            "status": prospect.get("status"),
            "research_count": 1 if research else 0,
            "contact_count": len(contacts),
            "active_deal_count": len(deals),
            "meeting_count": 0,  # Not tracking meetings separately for now
            "prep_count": len(completed_preps),
            "followup_count": len(completed_followups),
            "created_at": prospect.get("created_at"),
            "last_activity_at": prospect.get("last_activity_at")
        }
        
        return {
            "prospect": prospect,
            "research": research,
            "contacts": contacts,
            "deals": deals,
            "preparations": preparations,
            "followups": followups,
            "recent_activities": recent_activities,
            "stats": stats
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting prospect hub: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.patch("/{prospect_id}", response_model=Dict[str, Any])
async def update_prospect(
    prospect_id: str,
    request: ProspectUpdate,
    current_user: dict = Depends(get_current_user)
):
    """
    Update a prospect.
    """
    try:
        organization_id = get_organization_id(current_user)
        
        # Build update data (only non-None values)
        update_data = request.model_dump(exclude_unset=True)
        
        if not update_data:
            raise HTTPException(status_code=400, detail="No fields to update")
        
        # Validate status if provided
        valid_statuses = ['new', 'researching', 'qualified', 'meeting_scheduled', 'proposal_sent', 'won', 'lost', 'inactive']
        if 'status' in update_data and update_data['status'] not in valid_statuses:
            raise HTTPException(
                status_code=400, 
                detail=f"Invalid status. Must be one of: {', '.join(valid_statuses)}"
            )
        
        response = supabase.table("prospects").update(update_data).eq(
            "id", prospect_id
        ).eq(
            "organization_id", organization_id
        ).execute()
        
        if not response.data:
            raise HTTPException(status_code=404, detail="Prospect not found")
        
        logger.info(f"Updated prospect {prospect_id}")
        
        return response.data[0]
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error updating prospect: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.delete("/{prospect_id}", status_code=204)
async def delete_prospect(
    prospect_id: str,
    current_user: dict = Depends(get_current_user)
):
    """
    Delete a prospect.
    
    Note: This will NOT delete related research/preps/followups,
    but will set their prospect_id to NULL.
    """
    try:
        organization_id = get_organization_id(current_user)
        
        response = supabase.table("prospects").delete().eq(
            "id", prospect_id
        ).eq(
            "organization_id", organization_id
        ).execute()
        
        if not response.data:
            raise HTTPException(status_code=404, detail="Prospect not found")
        
        logger.info(f"Deleted prospect {prospect_id}")
        
        return None
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error deleting prospect: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/{prospect_id}/timeline", response_model=List[Dict[str, Any]])
async def get_prospect_timeline(
    prospect_id: str,
    limit: int = 20,
    current_user: dict = Depends(get_current_user)
):
    """
    Get activity timeline for a prospect.
    
    Returns chronological list of all activities (research, preps, followups).
    """
    try:
        organization_id = get_organization_id(current_user)
        
        # Verify prospect exists and belongs to org
        prospect_response = supabase.table("prospects").select("id").eq(
            "id", prospect_id
        ).eq(
            "organization_id", organization_id
        ).limit(1).execute()
        
        if not prospect_response.data:
            raise HTTPException(status_code=404, detail="Prospect not found")
        
        timeline = []
        
        # Get research briefs
        research = supabase.table("research_briefs").select(
            "id, company_name, status, created_at, completed_at"
        ).eq("prospect_id", prospect_id).execute()
        
        for r in research.data or []:
            timeline.append({
                "type": "research",
                "id": r["id"],
                "title": f"Research: {r['company_name']}",
                "status": r["status"],
                "created_at": r["created_at"],
                "completed_at": r.get("completed_at")
            })
        
        # Get meeting preps
        preps = supabase.table("meeting_preps").select(
            "id, prospect_company_name, meeting_type, status, created_at, completed_at"
        ).eq("prospect_id", prospect_id).execute()
        
        for p in preps.data or []:
            timeline.append({
                "type": "preparation",
                "id": p["id"],
                "title": f"Prep ({p['meeting_type']}): {p['prospect_company_name']}",
                "status": p["status"],
                "created_at": p["created_at"],
                "completed_at": p.get("completed_at")
            })
        
        # Get followups
        followups = supabase.table("followups").select(
            "id, prospect_company_name, meeting_subject, status, created_at, completed_at"
        ).eq("prospect_id", prospect_id).execute()
        
        for f in followups.data or []:
            timeline.append({
                "type": "followup",
                "id": f["id"],
                "title": f"Follow-up: {f.get('meeting_subject') or f['prospect_company_name']}",
                "status": f["status"],
                "created_at": f["created_at"],
                "completed_at": f.get("completed_at")
            })
        
        # Sort by created_at descending
        timeline.sort(key=lambda x: x["created_at"], reverse=True)
        
        return timeline[:limit]
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting prospect timeline: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# =====================================================
# Quick Status Update
# =====================================================
@router.patch("/{prospect_id}/status", response_model=Dict[str, Any])
async def update_prospect_status(
    prospect_id: str,
    request: StatusUpdate,
    current_user: dict = Depends(get_current_user)
):
    """
    Quick status update for a prospect (for drag & drop / quick actions).
    """
    try:
        organization_id = get_organization_id(current_user)
        
        response = supabase.table("prospects").update({
            "status": request.status
        }).eq(
            "id", prospect_id
        ).eq(
            "organization_id", organization_id
        ).execute()
        
        if not response.data:
            raise HTTPException(status_code=404, detail="Prospect not found")
        
        logger.info(f"Updated prospect {prospect_id} status to {request.status}")
        
        return response.data[0]
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error updating prospect status: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# =====================================================
# Meeting Planned Action
# =====================================================
class MarkMeetingPlannedRequest(BaseModel):
    prep_id: Optional[str] = None
    contact_name: Optional[str] = None


@router.post("/{prospect_id}/mark-meeting-planned", response_model=Dict[str, Any])
async def mark_meeting_planned(
    prospect_id: str,
    request: MarkMeetingPlannedRequest,
    current_user: dict = Depends(get_current_user)
):
    """
    Mark that a meeting has been planned for this prospect.
    
    Actions:
    1. Updates prospect status to 'meeting_scheduled'
    2. Logs activity to prospect_activities timeline
    3. Updates last_activity_at
    """
    try:
        organization_id = get_organization_id(current_user)
        user_id = current_user.get("sub")
        
        # Verify prospect exists and get company name
        prospect = supabase.table("prospects").select("id, company_name").eq(
            "id", prospect_id
        ).eq(
            "organization_id", organization_id
        ).limit(1).execute()
        
        if not prospect.data:
            raise HTTPException(status_code=404, detail="Prospect not found")
        
        company_name = prospect.data[0].get("company_name", "Unknown")
        
        # 1. Update prospect status to 'meeting_scheduled'
        supabase.table("prospects").update({
            "status": "meeting_scheduled",
            "last_activity_at": "now()"
        }).eq(
            "id", prospect_id
        ).eq(
            "organization_id", organization_id
        ).execute()
        
        # 2. Log activity to timeline
        activity_title = f"Meeting gepland met {company_name}"
        if request.contact_name:
            activity_title = f"Meeting gepland met {request.contact_name} ({company_name})"
        
        activity_data = {
            "prospect_id": prospect_id,
            "organization_id": organization_id,
            "activity_type": "meeting_planned",
            "activity_id": request.prep_id,  # Link to prep if available
            "title": activity_title,
            "description": "Meeting uitnodiging verstuurd via Autopilot",
            "icon": "calendar",
            "created_by": user_id,
            "metadata": {
                "prep_id": request.prep_id,
                "contact_name": request.contact_name,
                "source": "autopilot_meeting_request"
            }
        }
        
        supabase.table("prospect_activities").insert(activity_data).execute()
        
        logger.info(f"Marked meeting planned for prospect {prospect_id}")
        
        return {
            "success": True,
            "prospect_id": prospect_id,
            "status": "meeting_scheduled",
            "activity_logged": True
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error marking meeting planned: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# =====================================================
# Notes CRUD
# =====================================================
@router.get("/{prospect_id}/notes", response_model=List[Dict[str, Any]])
async def list_prospect_notes(
    prospect_id: str,
    current_user: dict = Depends(get_current_user)
):
    """
    Get all notes for a prospect, pinned first then by date.
    """
    try:
        organization_id = get_organization_id(current_user)
        
        # Verify prospect exists
        prospect = supabase.table("prospects").select("id").eq(
            "id", prospect_id
        ).eq(
            "organization_id", organization_id
        ).limit(1).execute()
        
        if not prospect.data:
            raise HTTPException(status_code=404, detail="Prospect not found")
        
        # Get notes sorted by pinned then created_at
        response = supabase.table("prospect_notes").select(
            "id, prospect_id, user_id, content, is_pinned, created_at, updated_at"
        ).eq(
            "prospect_id", prospect_id
        ).order(
            "is_pinned", desc=True
        ).order(
            "created_at", desc=True
        ).execute()
        
        return response.data or []
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error listing prospect notes: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/{prospect_id}/notes", response_model=Dict[str, Any], status_code=201)
async def create_prospect_note(
    prospect_id: str,
    request: NoteCreate,
    current_user: dict = Depends(get_current_user)
):
    """
    Create a note for a prospect.
    """
    try:
        organization_id = get_organization_id(current_user)
        user_id = current_user.get("sub") or current_user.get("id")
        
        # Verify prospect exists
        prospect = supabase.table("prospects").select("id").eq(
            "id", prospect_id
        ).eq(
            "organization_id", organization_id
        ).limit(1).execute()
        
        if not prospect.data:
            raise HTTPException(status_code=404, detail="Prospect not found")
        
        # Create note
        response = supabase.table("prospect_notes").insert({
            "prospect_id": prospect_id,
            "organization_id": organization_id,
            "user_id": user_id,
            "content": request.content,
            "is_pinned": request.is_pinned
        }).execute()
        
        if not response.data:
            raise HTTPException(status_code=500, detail="Failed to create note")
        
        logger.info(f"Created note for prospect {prospect_id}")
        
        return response.data[0]
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error creating prospect note: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.patch("/{prospect_id}/notes/{note_id}", response_model=Dict[str, Any])
async def update_prospect_note(
    prospect_id: str,
    note_id: str,
    request: NoteUpdate,
    current_user: dict = Depends(get_current_user)
):
    """
    Update a note (only the owner can update).
    """
    try:
        user_id = current_user.get("sub") or current_user.get("id")
        
        # Build update data
        update_data = request.model_dump(exclude_unset=True)
        
        if not update_data:
            raise HTTPException(status_code=400, detail="No fields to update")
        
        # Update note (RLS ensures only owner can update)
        response = supabase.table("prospect_notes").update(update_data).eq(
            "id", note_id
        ).eq(
            "prospect_id", prospect_id
        ).eq(
            "user_id", user_id
        ).execute()
        
        if not response.data:
            raise HTTPException(status_code=404, detail="Note not found or not authorized")
        
        logger.info(f"Updated note {note_id}")
        
        return response.data[0]
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error updating prospect note: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.delete("/{prospect_id}/notes/{note_id}", status_code=204)
async def delete_prospect_note(
    prospect_id: str,
    note_id: str,
    current_user: dict = Depends(get_current_user)
):
    """
    Delete a note (only the owner can delete).
    """
    try:
        user_id = current_user.get("sub") or current_user.get("id")
        
        # Delete note (RLS ensures only owner can delete)
        response = supabase.table("prospect_notes").delete().eq(
            "id", note_id
        ).eq(
            "prospect_id", prospect_id
        ).eq(
            "user_id", user_id
        ).execute()
        
        if not response.data:
            raise HTTPException(status_code=404, detail="Note not found or not authorized")
        
        logger.info(f"Deleted note {note_id}")
        
        return None
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error deleting prospect note: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# =====================================================
# Quick Contact Add
# =====================================================
@router.post("/{prospect_id}/contacts", response_model=Dict[str, Any], status_code=201)
async def add_prospect_contact(
    prospect_id: str,
    request: ContactCreate,
    current_user: dict = Depends(get_current_user)
):
    """
    Quickly add a contact to a prospect (creates in prospect_contacts table).
    """
    try:
        organization_id = get_organization_id(current_user)
        
        # Verify prospect exists
        prospect = supabase.table("prospects").select("id").eq(
            "id", prospect_id
        ).eq(
            "organization_id", organization_id
        ).limit(1).execute()
        
        if not prospect.data:
            raise HTTPException(status_code=404, detail="Prospect not found")
        
        # Check if contact already exists by name
        existing = supabase.table("prospect_contacts").select("id").eq(
            "prospect_id", prospect_id
        ).eq(
            "name", request.name
        ).limit(1).execute()
        
        if existing.data:
            raise HTTPException(status_code=409, detail=f"Contact '{request.name}' already exists for this prospect")
        
        # Create contact
        contact_data = {
            "prospect_id": prospect_id,
            "organization_id": organization_id,
            "name": request.name,
            "role": request.role,
            "email": request.email,
            "phone": request.phone,
            "linkedin_url": request.linkedin_url,
            "decision_authority": request.decision_authority
        }
        
        # Remove None values
        contact_data = {k: v for k, v in contact_data.items() if v is not None}
        
        response = supabase.table("prospect_contacts").insert(contact_data).execute()
        
        if not response.data:
            raise HTTPException(status_code=500, detail="Failed to create contact")
        
        logger.info(f"Added contact {request.name} to prospect {prospect_id}")
        
        return response.data[0]
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error adding prospect contact: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# Keep legacy endpoint for backwards compatibility
@router.get("/known", response_model=List[Dict[str, Any]], deprecated=True)
async def get_known_prospects_legacy(
    current_user: dict = Depends(get_current_user)
):
    """
    [DEPRECATED] Use GET /prospects instead.
    
    Returns prospects in legacy format for backwards compatibility.
    """
    try:
        organization_id = get_organization_id(current_user)
        
        # Get all prospects with activity counts
        response = supabase.table("prospects").select(
            "id, company_name, status, last_activity_at, research_briefs(id), meeting_preps(id), followups(id)"
        ).eq(
            "organization_id", organization_id
        ).order(
            "last_activity_at", desc=True
        ).execute()
        
        # Transform to legacy format
        result = []
        for p in response.data or []:
            has_research = len(p.get("research_briefs", []) or []) > 0
            has_prep = len(p.get("meeting_preps", []) or []) > 0
            has_followup = len(p.get("followups", []) or []) > 0
            
            context_score = sum([has_research, has_prep, has_followup])
            
            result.append({
                "id": p["id"],
                "name": p["company_name"],
                "has_research": has_research,
                "has_prep": has_prep,
                "has_followup": has_followup,
                "last_activity": p["last_activity_at"],
                "last_activity_type": "unknown",  # Legacy field
                "context_score": context_score
            })
        
        return result
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting known prospects: {e}")
        raise HTTPException(status_code=500, detail=str(e))
