"""
Deal Management Router

IMPORTANT: This is NOT a CRM replacement!
- Deals are for GROUPING preps/followups
- No manual entry of CRM data (stage, value, probability)
"""

from fastapi import APIRouter, HTTPException, Depends
from typing import List, Optional
from uuid import UUID
from datetime import datetime

from ..models.deals import (
    Deal, DealCreate, DealUpdate, DealWithStats,
    Meeting, MeetingCreate, MeetingUpdate, MeetingWithLinks,
    Activity, ActivityCreate,
    ProspectHub, ProspectHubSummary
)
from ..database import get_supabase_service, get_user_client
from ..deps import get_current_user, get_auth_token

router = APIRouter(prefix="/api/v1/deals", tags=["deals"])


# ============================================================
# HELPER FUNCTIONS
# ============================================================

async def get_user_org(user: dict, supabase) -> tuple[str, str]:
    """Get user_id and organization_id from authenticated user."""
    user_id = user.get("sub")
    if not user_id:
        raise HTTPException(status_code=401, detail="Invalid user token")
    
    # Get organization
    org_result = supabase.table("organization_members").select("organization_id").eq("user_id", user_id).limit(1).execute()
    
    if not org_result.data:
        raise HTTPException(status_code=403, detail="User has no organization")
    
    return user_id, org_result.data[0]["organization_id"]


# ============================================================
# DEAL ENDPOINTS
# ============================================================

@router.get("", response_model=List[DealWithStats])
async def list_deals(
    prospect_id: Optional[UUID] = None,
    is_active: Optional[bool] = None,
    limit: int = 50,
    offset: int = 0,
    user: dict = Depends(get_current_user),
    token: str = Depends(get_auth_token)
):
    """List all deals, optionally filtered by prospect"""
    supabase = get_user_client(token)
    user_id, org_id = await get_user_org(user, supabase)
    
    query = supabase.table("deal_summary").select("*").eq("organization_id", org_id)
    
    if prospect_id:
        query = query.eq("prospect_id", str(prospect_id))
    if is_active is not None:
        query = query.eq("is_active", is_active)
    
    query = query.order("created_at", desc=True).range(offset, offset + limit - 1)
    
    result = query.execute()
    
    # Map view fields to model fields
    deals = []
    for d in result.data:
        if "deal_id" in d and "id" not in d:
            d["id"] = d.pop("deal_id")
        if "updated_at" not in d:
            d["updated_at"] = d.get("created_at")
        deals.append(DealWithStats(**d))
    
    return deals


@router.get("/{deal_id}", response_model=DealWithStats)
async def get_deal(
    deal_id: UUID,
    user: dict = Depends(get_current_user),
    token: str = Depends(get_auth_token)
):
    """Get a single deal with stats"""
    supabase = get_user_client(token)
    user_id, org_id = await get_user_org(user, supabase)
    
    result = supabase.table("deal_summary").select("*").eq("deal_id", str(deal_id)).eq("organization_id", org_id).single().execute()
    
    if not result.data:
        raise HTTPException(status_code=404, detail="Deal not found")
    
    d = result.data
    if "deal_id" in d and "id" not in d:
        d["id"] = d.pop("deal_id")
    if "updated_at" not in d:
        d["updated_at"] = d.get("created_at")
    
    return DealWithStats(**d)


@router.post("", response_model=Deal, status_code=201)
async def create_deal(
    deal: DealCreate,
    user: dict = Depends(get_current_user),
    token: str = Depends(get_auth_token)
):
    """Create a new deal"""
    supabase = get_user_client(token)
    user_id, org_id = await get_user_org(user, supabase)
    
    # Verify prospect belongs to organization
    prospect = supabase.table("prospects").select("id").eq("id", str(deal.prospect_id)).eq("organization_id", org_id).single().execute()
    
    if not prospect.data:
        raise HTTPException(status_code=404, detail="Prospect not found in your organization")
    
    # Create deal
    data = {
        "name": deal.name,
        "description": deal.description,
        "prospect_id": str(deal.prospect_id),
        "organization_id": org_id,
        "created_by": user_id,
        "is_active": True
    }
    
    result = supabase.table("deals").insert(data).execute()
    
    if not result.data:
        raise HTTPException(status_code=500, detail="Failed to create deal")
    
    return Deal(**result.data[0])


@router.patch("/{deal_id}", response_model=Deal)
async def update_deal(
    deal_id: UUID,
    deal: DealUpdate,
    user: dict = Depends(get_current_user),
    token: str = Depends(get_auth_token)
):
    """Update a deal"""
    supabase = get_user_client(token)
    user_id, org_id = await get_user_org(user, supabase)
    
    # Verify deal belongs to organization
    existing = supabase.table("deals").select("id").eq("id", str(deal_id)).eq("organization_id", org_id).single().execute()
    
    if not existing.data:
        raise HTTPException(status_code=404, detail="Deal not found")
    
    # Update only provided fields
    update_data = deal.model_dump(exclude_unset=True)
    update_data["updated_at"] = datetime.utcnow().isoformat()
    
    result = supabase.table("deals").update(update_data).eq("id", str(deal_id)).execute()
    
    if not result.data:
        raise HTTPException(status_code=500, detail="Failed to update deal")
    
    return Deal(**result.data[0])


@router.delete("/{deal_id}", status_code=204)
async def delete_deal(
    deal_id: UUID,
    user: dict = Depends(get_current_user),
    token: str = Depends(get_auth_token)
):
    """Delete a deal"""
    supabase = get_user_client(token)
    user_id, org_id = await get_user_org(user, supabase)
    
    # Verify deal belongs to organization
    existing = supabase.table("deals").select("id").eq("id", str(deal_id)).eq("organization_id", org_id).single().execute()
    
    if not existing.data:
        raise HTTPException(status_code=404, detail="Deal not found")
    
    supabase.table("deals").delete().eq("id", str(deal_id)).execute()
    
    return None


@router.post("/{deal_id}/archive", response_model=Deal)
async def archive_deal(
    deal_id: UUID,
    user: dict = Depends(get_current_user),
    token: str = Depends(get_auth_token)
):
    """Archive a deal (set is_active to false)"""
    supabase = get_user_client(token)
    user_id, org_id = await get_user_org(user, supabase)
    
    result = supabase.table("deals").update({
        "is_active": False,
        "updated_at": datetime.utcnow().isoformat()
    }).eq("id", str(deal_id)).eq("organization_id", org_id).execute()
    
    if not result.data:
        raise HTTPException(status_code=404, detail="Deal not found")
    
    return Deal(**result.data[0])


@router.post("/{deal_id}/activate", response_model=Deal)
async def activate_deal(
    deal_id: UUID,
    user: dict = Depends(get_current_user),
    token: str = Depends(get_auth_token)
):
    """Activate a deal (set is_active to true)"""
    supabase = get_user_client(token)
    user_id, org_id = await get_user_org(user, supabase)
    
    result = supabase.table("deals").update({
        "is_active": True,
        "updated_at": datetime.utcnow().isoformat()
    }).eq("id", str(deal_id)).eq("organization_id", org_id).execute()
    
    if not result.data:
        raise HTTPException(status_code=404, detail="Deal not found")
    
    return Deal(**result.data[0])


# ============================================================
# MEETING ENDPOINTS (under /deals/{deal_id}/meetings)
# ============================================================

@router.get("/{deal_id}/meetings", response_model=List[MeetingWithLinks])
async def list_deal_meetings(
    deal_id: UUID,
    user: dict = Depends(get_current_user),
    token: str = Depends(get_auth_token)
):
    """List all meetings for a deal - OPTIMIZED: batch queries instead of N+1"""
    supabase = get_user_client(token)
    user_id, org_id = await get_user_org(user, supabase)
    
    # Get meetings
    meetings_result = supabase.table("meetings").select("*").eq("deal_id", str(deal_id)).eq("organization_id", org_id).order("scheduled_date", desc=True).execute()
    
    if not meetings_result.data:
        return []
    
    meeting_ids = [m["id"] for m in meetings_result.data]
    
    # BATCH: Get all preps for these meetings in ONE query
    preps_result = supabase.table("meeting_preps").select("id, meeting_id").in_("meeting_id", meeting_ids).execute()
    prep_map = {p["meeting_id"]: p["id"] for p in preps_result.data}
    
    # BATCH: Get all followups for these meetings in ONE query
    followups_result = supabase.table("followups").select("id, meeting_id").in_("meeting_id", meeting_ids).execute()
    followup_map = {f["meeting_id"]: f["id"] for f in followups_result.data}
    
    # BATCH: Get all contacts referenced by meetings in ONE query
    all_contact_ids = []
    for m in meetings_result.data:
        if m.get("contact_ids"):
            all_contact_ids.extend(m["contact_ids"])
    
    contact_map = {}
    if all_contact_ids:
        contacts_result = supabase.table("prospect_contacts").select("id, name").in_("id", list(set(all_contact_ids))).execute()
        contact_map = {c["id"]: c["name"] for c in contacts_result.data}
    
    # Build response with mapped data
    meetings = []
    for m in meetings_result.data:
        contact_names = [contact_map.get(cid, "") for cid in (m.get("contact_ids") or []) if contact_map.get(cid)]
        
        meeting = MeetingWithLinks(
            **m,
            has_prep=m["id"] in prep_map,
            prep_id=prep_map.get(m["id"]),
            has_followup=m["id"] in followup_map,
            followup_id=followup_map.get(m["id"]),
            contact_names=contact_names
        )
        meetings.append(meeting)
    
    return meetings


# ============================================================
# MEETINGS ROUTER (separate for /api/v1/meetings)
# ============================================================

meetings_router = APIRouter(prefix="/api/v1/meetings", tags=["meetings"])


@meetings_router.get("", response_model=List[Meeting])
async def list_meetings(
    prospect_id: Optional[UUID] = None,
    deal_id: Optional[UUID] = None,
    status: Optional[str] = None,
    limit: int = 50,
    offset: int = 0,
    user: dict = Depends(get_current_user),
    token: str = Depends(get_auth_token)
):
    """List all meetings with optional filters"""
    supabase = get_user_client(token)
    user_id, org_id = await get_user_org(user, supabase)
    
    query = supabase.table("meetings").select("*").eq("organization_id", org_id)
    
    if prospect_id:
        query = query.eq("prospect_id", str(prospect_id))
    if deal_id:
        query = query.eq("deal_id", str(deal_id))
    if status:
        query = query.eq("status", status)
    
    query = query.order("scheduled_date", desc=True).range(offset, offset + limit - 1)
    
    result = query.execute()
    
    return [Meeting(**row) for row in result.data]


@meetings_router.get("/{meeting_id}", response_model=MeetingWithLinks)
async def get_meeting(
    meeting_id: UUID,
    user: dict = Depends(get_current_user),
    token: str = Depends(get_auth_token)
):
    """Get a single meeting with linked prep/followup info"""
    supabase = get_user_client(token)
    user_id, org_id = await get_user_org(user, supabase)
    
    result = supabase.table("meetings").select("*").eq("id", str(meeting_id)).eq("organization_id", org_id).single().execute()
    
    if not result.data:
        raise HTTPException(status_code=404, detail="Meeting not found")
    
    m = result.data
    
    # Check for linked prep
    prep = supabase.table("meeting_preps").select("id").eq("meeting_id", m["id"]).limit(1).execute()
    
    # Check for linked followup
    followup = supabase.table("followups").select("id").eq("meeting_id", m["id"]).limit(1).execute()
    
    # Get contact names
    contact_names = []
    if m.get("contact_ids"):
        contacts = supabase.table("prospect_contacts").select("name").in_("id", m["contact_ids"]).execute()
        contact_names = [c["name"] for c in contacts.data]
    
    return MeetingWithLinks(
        **m,
        has_prep=len(prep.data) > 0,
        prep_id=prep.data[0]["id"] if prep.data else None,
        has_followup=len(followup.data) > 0,
        followup_id=followup.data[0]["id"] if followup.data else None,
        contact_names=contact_names
    )


@meetings_router.post("", response_model=Meeting, status_code=201)
async def create_meeting(
    meeting: MeetingCreate,
    user: dict = Depends(get_current_user),
    token: str = Depends(get_auth_token)
):
    """Create a new meeting"""
    supabase = get_user_client(token)
    user_id, org_id = await get_user_org(user, supabase)
    
    # Verify prospect belongs to organization
    prospect = supabase.table("prospects").select("id").eq("id", str(meeting.prospect_id)).eq("organization_id", org_id).single().execute()
    
    if not prospect.data:
        raise HTTPException(status_code=404, detail="Prospect not found")
    
    # If deal_id provided, verify it belongs to this prospect
    if meeting.deal_id:
        deal = supabase.table("deals").select("id").eq("id", str(meeting.deal_id)).eq("prospect_id", str(meeting.prospect_id)).single().execute()
        if not deal.data:
            raise HTTPException(status_code=400, detail="Deal does not belong to this prospect")
    
    # Create meeting
    data = {
        "title": meeting.title,
        "meeting_type": meeting.meeting_type,
        "prospect_id": str(meeting.prospect_id),
        "deal_id": str(meeting.deal_id) if meeting.deal_id else None,
        "organization_id": org_id,
        "scheduled_date": meeting.scheduled_date.isoformat() if meeting.scheduled_date else None,
        "actual_date": meeting.actual_date.isoformat() if meeting.actual_date else None,
        "duration_minutes": meeting.duration_minutes,
        "location": meeting.location,
        "contact_ids": [str(c) for c in meeting.contact_ids],
        "notes": meeting.notes,
        "status": "scheduled",
        "created_by": user_id
    }
    
    result = supabase.table("meetings").insert(data).execute()
    
    if not result.data:
        raise HTTPException(status_code=500, detail="Failed to create meeting")
    
    return Meeting(**result.data[0])


@meetings_router.patch("/{meeting_id}", response_model=Meeting)
async def update_meeting(
    meeting_id: UUID,
    meeting: MeetingUpdate,
    user: dict = Depends(get_current_user),
    token: str = Depends(get_auth_token)
):
    """Update a meeting"""
    supabase = get_user_client(token)
    user_id, org_id = await get_user_org(user, supabase)
    
    # Verify meeting belongs to organization
    existing = supabase.table("meetings").select("id, prospect_id").eq("id", str(meeting_id)).eq("organization_id", org_id).single().execute()
    
    if not existing.data:
        raise HTTPException(status_code=404, detail="Meeting not found")
    
    # If deal_id provided, verify it belongs to this prospect
    if meeting.deal_id:
        deal = supabase.table("deals").select("id").eq("id", str(meeting.deal_id)).eq("prospect_id", existing.data["prospect_id"]).single().execute()
        if not deal.data:
            raise HTTPException(status_code=400, detail="Deal does not belong to this prospect")
    
    # Update only provided fields
    update_data = {}
    for field, value in meeting.model_dump(exclude_unset=True).items():
        if field == "deal_id":
            update_data[field] = str(value) if value else None
        elif field == "contact_ids":
            update_data[field] = [str(c) for c in value] if value else []
        elif field in ["scheduled_date", "actual_date"] and value:
            update_data[field] = value.isoformat()
        else:
            update_data[field] = value
    
    update_data["updated_at"] = datetime.utcnow().isoformat()
    
    result = supabase.table("meetings").update(update_data).eq("id", str(meeting_id)).execute()
    
    if not result.data:
        raise HTTPException(status_code=500, detail="Failed to update meeting")
    
    return Meeting(**result.data[0])


@meetings_router.delete("/{meeting_id}", status_code=204)
async def delete_meeting(
    meeting_id: UUID,
    user: dict = Depends(get_current_user),
    token: str = Depends(get_auth_token)
):
    """Delete a meeting"""
    supabase = get_user_client(token)
    user_id, org_id = await get_user_org(user, supabase)
    
    # Verify meeting belongs to organization
    existing = supabase.table("meetings").select("id").eq("id", str(meeting_id)).eq("organization_id", org_id).single().execute()
    
    if not existing.data:
        raise HTTPException(status_code=404, detail="Meeting not found")
    
    supabase.table("meetings").delete().eq("id", str(meeting_id)).execute()
    
    return None


# ============================================================
# PROSPECT HUB ENDPOINTS
# ============================================================

hub_router = APIRouter(prefix="/api/v1/prospects", tags=["prospect-hub"])


@hub_router.get("/{prospect_id}/hub", response_model=ProspectHub)
async def get_prospect_hub(
    prospect_id: UUID,
    organization_id: UUID,
    user: dict = Depends(get_current_user),
    token: str = Depends(get_auth_token)
):
    """Get full Prospect Hub data"""
    supabase = get_user_client(token)
    user_id, org_id = await get_user_org(user, supabase)
    
    # Verify org_id matches (extra security)
    if str(organization_id) != org_id:
        raise HTTPException(status_code=403, detail="Organization mismatch")
    
    # Get prospect
    prospect_result = supabase.table("prospects").select("*").eq("id", str(prospect_id)).eq("organization_id", org_id).single().execute()
    
    if not prospect_result.data:
        raise HTTPException(status_code=404, detail="Prospect not found")
    
    prospect = prospect_result.data
    
    # Get latest research (any status - to show "in progress")
    # First try completed research
    completed_result = supabase.table("research_briefs").select("*").eq("prospect_id", str(prospect_id)).eq("status", "completed").order("completed_at", desc=True).limit(1).execute()
    
    if completed_result.data:
        research = completed_result.data[0]
    else:
        # No completed, check for in-progress
        in_progress_result = supabase.table("research_briefs").select("*").eq("prospect_id", str(prospect_id)).in_("status", ["pending", "researching"]).order("created_at", desc=True).limit(1).execute()
        research = in_progress_result.data[0] if in_progress_result.data else None
    
    # Get contacts
    contacts_result = supabase.table("prospect_contacts").select("*").eq("prospect_id", str(prospect_id)).order("is_primary", desc=True).execute()
    
    contacts = contacts_result.data
    
    # Get deals with stats (using view)
    deals_result = supabase.table("deal_summary").select("*").eq("prospect_id", str(prospect_id)).order("is_active", desc=True).order("created_at", desc=True).execute()
    
    # Map view fields to model fields (view uses deal_id, model expects id)
    deals = []
    for d in deals_result.data:
        # Rename deal_id to id for Pydantic model
        if "deal_id" in d and "id" not in d:
            d["id"] = d.pop("deal_id")
        # Ensure updated_at exists (use created_at as fallback)
        if "updated_at" not in d:
            d["updated_at"] = d.get("created_at")
        deals.append(DealWithStats(**d))
    
    # Get recent activities
    activities_result = supabase.table("prospect_activities").select("*").eq("prospect_id", str(prospect_id)).order("created_at", desc=True).limit(20).execute()
    
    activities = [Activity(**a) for a in activities_result.data]
    
    # Build summary
    summary = ProspectHubSummary(
        prospect_id=prospect_id,
        company_name=prospect["company_name"],
        status=prospect.get("status"),
        research_count=1 if research else 0,
        contact_count=len(contacts),
        active_deal_count=len([d for d in deals if d.is_active]),
        meeting_count=sum(d.meeting_count for d in deals),
        prep_count=sum(d.prep_count for d in deals),
        followup_count=sum(d.followup_count for d in deals),
        latest_activity=activities[0].model_dump() if activities else None,
        created_at=prospect["created_at"],
        last_activity_at=prospect.get("last_activity_at")
    )
    
    return ProspectHub(
        prospect=prospect,
        research=research,
        contacts=contacts,
        deals=deals,
        recent_activities=activities,
        stats=summary
    )


@hub_router.get("/{prospect_id}/timeline", response_model=List[Activity])
async def get_prospect_timeline(
    prospect_id: UUID,
    organization_id: UUID,
    deal_id: Optional[UUID] = None,
    activity_type: Optional[str] = None,
    limit: int = 50,
    offset: int = 0,
    user: dict = Depends(get_current_user),
    token: str = Depends(get_auth_token)
):
    """Get prospect activity timeline"""
    supabase = get_user_client(token)
    user_id, org_id = await get_user_org(user, supabase)
    
    query = supabase.table("prospect_activities").select("*").eq("prospect_id", str(prospect_id)).eq("organization_id", org_id)
    
    if deal_id:
        query = query.eq("deal_id", str(deal_id))
    if activity_type:
        query = query.eq("activity_type", activity_type)
    
    query = query.order("created_at", desc=True).range(offset, offset + limit - 1)
    
    result = query.execute()
    
    return [Activity(**a) for a in result.data]


@hub_router.post("/{prospect_id}/activities", response_model=Activity, status_code=201)
async def create_activity(
    prospect_id: UUID,
    activity: ActivityCreate,
    user: dict = Depends(get_current_user),
    token: str = Depends(get_auth_token)
):
    """Manually create an activity log entry (e.g., a note)"""
    supabase = get_user_client(token)
    user_id, org_id = await get_user_org(user, supabase)
    
    # Verify prospect belongs to organization
    prospect = supabase.table("prospects").select("id").eq("id", str(prospect_id)).eq("organization_id", org_id).single().execute()
    
    if not prospect.data:
        raise HTTPException(status_code=404, detail="Prospect not found")
    
    data = {
        "prospect_id": str(prospect_id),
        "deal_id": str(activity.deal_id) if activity.deal_id else None,
        "meeting_id": str(activity.meeting_id) if activity.meeting_id else None,
        "organization_id": org_id,
        "activity_type": activity.activity_type,
        "activity_id": str(activity.activity_id) if activity.activity_id else None,
        "title": activity.title,
        "description": activity.description,
        "icon": activity.icon or "📝",
        "metadata": activity.metadata or {},
        "created_by": user_id
    }
    
    result = supabase.table("prospect_activities").insert(data).execute()
    
    if not result.data:
        raise HTTPException(status_code=500, detail="Failed to create activity")
    
    return Activity(**result.data[0])
