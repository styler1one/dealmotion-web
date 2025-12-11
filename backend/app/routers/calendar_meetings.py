"""
Calendar Meetings Router - API endpoints for viewing synced meetings
SPEC-038: Meetings & Calendar Integration
"""
from fastapi import APIRouter, Depends, HTTPException, status, Query
from pydantic import BaseModel, Field
from typing import Optional, List
from datetime import datetime, timedelta, timezone
import logging

from app.deps import get_user_org
from app.database import get_supabase_service
from app.services.prospect_matcher import ProspectMatcher

logger = logging.getLogger(__name__)
supabase = get_supabase_service()

router = APIRouter(prefix="/api/v1/calendar-meetings", tags=["calendar-meetings"])


# ==========================================
# Pydantic Models
# ==========================================

class Attendee(BaseModel):
    """Meeting attendee."""
    email: str
    name: Optional[str] = None
    response_status: Optional[str] = None
    is_organizer: bool = False


class PrepStatus(BaseModel):
    """Preparation status for a meeting."""
    has_prep: bool = False
    prep_id: Optional[str] = None
    prep_created_at: Optional[datetime] = None


class LinkedContact(BaseModel):
    """A linked contact person."""
    id: str
    name: str
    role: Optional[str] = None


class CalendarMeetingResponse(BaseModel):
    """Response model for a calendar meeting."""
    id: str
    title: str
    description: Optional[str] = None
    start_time: datetime
    end_time: datetime
    location: Optional[str] = None
    meeting_url: Optional[str] = None
    is_online: bool = False
    status: str = "confirmed"
    attendees: List[Attendee] = []
    organizer_email: Optional[str] = None
    
    # Computed fields
    is_now: bool = False
    is_today: bool = False
    is_tomorrow: bool = False
    
    # Linked data
    prospect_id: Optional[str] = None
    prospect_name: Optional[str] = None
    contact_ids: List[str] = []
    contacts: List[LinkedContact] = []  # Resolved contact info
    prep_status: Optional[PrepStatus] = None
    
    # Recurring
    is_recurring: bool = False


class MeetingsListResponse(BaseModel):
    """Response for meetings list."""
    meetings: List[CalendarMeetingResponse]
    total: int
    has_more: bool = False


# ==========================================
# Helper Functions
# ==========================================

def is_meeting_now(start_time: datetime, end_time: datetime) -> bool:
    """Check if a meeting is currently happening."""
    now = datetime.now(timezone.utc)
    return start_time <= now <= end_time


def is_meeting_today(start_time: datetime) -> bool:
    """Check if a meeting is today."""
    now = datetime.now(timezone.utc)
    return start_time.date() == now.date()


def is_meeting_tomorrow(start_time: datetime) -> bool:
    """Check if a meeting is tomorrow."""
    now = datetime.now(timezone.utc)
    tomorrow = now + timedelta(days=1)
    return start_time.date() == tomorrow.date()


async def fetch_contacts_by_ids(contact_ids: List[str]) -> List[LinkedContact]:
    """Fetch contact details by their IDs."""
    if not contact_ids:
        return []
    
    try:
        result = supabase.table("prospect_contacts").select(
            "id, name, role"
        ).in_("id", contact_ids).execute()
        
        return [
            LinkedContact(
                id=c["id"],
                name=c.get("name", "Unknown"),
                role=c.get("role")
            )
            for c in (result.data or [])
        ]
    except Exception as e:
        logger.error(f"Failed to fetch contacts: {e}")
        return []


# ==========================================
# Endpoints
# ==========================================

@router.get("", response_model=MeetingsListResponse)
async def list_meetings(
    user_org: tuple = Depends(get_user_org),
    from_date: Optional[datetime] = Query(None, description="Start date filter (ISO format)"),
    to_date: Optional[datetime] = Query(None, description="End date filter (ISO format)"),
    prospect_id: Optional[str] = Query(None, description="Filter by prospect"),
    unprepared_only: bool = Query(False, description="Only show meetings without preparation"),
    limit: int = Query(50, ge=1, le=100, description="Max results"),
    offset: int = Query(0, ge=0, description="Offset for pagination"),
):
    """
    List calendar meetings for the current user.
    
    Returns synced meetings with computed fields like is_now, is_today,
    and linked prospect/prep information.
    """
    user_id, organization_id = user_org
    
    try:
        # Build query (including contact_ids)
        query = supabase.table("calendar_meetings").select(
            """
            id, title, description, start_time, end_time,
            location, meeting_url, is_online, status,
            attendees, organizer_email, is_recurring,
            prospect_id, contact_ids,
            prospects(id, company_name)
            """
        ).eq(
            "organization_id", organization_id
        ).neq(
            "status", "cancelled"
        ).order("start_time", desc=False)
        
        # Apply date filters
        if from_date:
            query = query.gte("start_time", from_date.isoformat())
        else:
            # Default: from now
            query = query.gte("start_time", datetime.now(timezone.utc).isoformat())
        
        if to_date:
            query = query.lte("start_time", to_date.isoformat())
        else:
            # Default: next 14 days
            default_to = datetime.now(timezone.utc) + timedelta(days=14)
            query = query.lte("start_time", default_to.isoformat())
        
        if prospect_id:
            query = query.eq("prospect_id", prospect_id)
        
        # Execute with pagination
        query = query.range(offset, offset + limit - 1)
        result = query.execute()
        
        meetings = []
        for row in result.data or []:
            # Parse attendees
            attendees = []
            for att in row.get("attendees") or []:
                attendees.append(Attendee(
                    email=att.get("email", ""),
                    name=att.get("name"),
                    response_status=att.get("response_status"),
                    is_organizer=att.get("is_organizer", False),
                ))
            
            # Parse times
            start_time = datetime.fromisoformat(row["start_time"].replace("Z", "+00:00"))
            end_time = datetime.fromisoformat(row["end_time"].replace("Z", "+00:00"))
            
            # Get prospect info
            prospect = row.get("prospects")
            prospect_id_val = row.get("prospect_id")
            prospect_name = prospect.get("company_name") if prospect else None
            
            # Check for existing preparation
            prep_status = None
            if prospect_id_val:
                prep_result = supabase.table("meeting_preps").select(
                    "id, created_at"
                ).eq("prospect_id", prospect_id_val).order(
                    "created_at", desc=True
                ).limit(1).execute()
                
                if prep_result.data and len(prep_result.data) > 0:
                    prep = prep_result.data[0]
                    prep_status = PrepStatus(
                        has_prep=True,
                        prep_id=prep["id"],
                        prep_created_at=prep["created_at"],
                    )
            
            # Skip if unprepared_only filter and has prep
            if unprepared_only and prep_status and prep_status.has_prep:
                continue
            
            # Get linked contacts
            contact_ids = row.get("contact_ids") or []
            contacts = await fetch_contacts_by_ids(contact_ids)
            
            meetings.append(CalendarMeetingResponse(
                id=row["id"],
                title=row["title"],
                description=row.get("description"),
                start_time=start_time,
                end_time=end_time,
                location=row.get("location"),
                meeting_url=row.get("meeting_url"),
                is_online=row.get("is_online", False),
                status=row.get("status", "confirmed"),
                attendees=attendees,
                organizer_email=row.get("organizer_email"),
                is_now=is_meeting_now(start_time, end_time),
                is_today=is_meeting_today(start_time),
                is_tomorrow=is_meeting_tomorrow(start_time),
                prospect_id=prospect_id_val,
                prospect_name=prospect_name,
                contact_ids=contact_ids,
                contacts=contacts,
                prep_status=prep_status,
                is_recurring=row.get("is_recurring", False),
            ))
        
        return MeetingsListResponse(
            meetings=meetings,
            total=len(meetings),
            has_more=len(result.data or []) == limit,
        )
        
    except Exception as e:
        logger.error(f"Failed to list meetings: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to load meetings: {str(e)}"
        )


@router.get("/{meeting_id}", response_model=CalendarMeetingResponse)
async def get_meeting(
    meeting_id: str,
    user_org: tuple = Depends(get_user_org),
):
    """Get a single calendar meeting by ID."""
    user_id, organization_id = user_org
    
    try:
        result = supabase.table("calendar_meetings").select(
            """
            id, title, description, start_time, end_time,
            location, meeting_url, is_online, status,
            attendees, organizer_email, is_recurring,
            prospect_id, prospects(id, company_name)
            """
        ).eq("id", meeting_id).eq("organization_id", organization_id).execute()
        
        if not result.data or len(result.data) == 0:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Meeting not found"
            )
        
        row = result.data[0]
        
        # Parse (same as list)
        attendees = []
        for att in row.get("attendees") or []:
            attendees.append(Attendee(
                email=att.get("email", ""),
                name=att.get("name"),
                response_status=att.get("response_status"),
                is_organizer=att.get("is_organizer", False),
            ))
        
        start_time = datetime.fromisoformat(row["start_time"].replace("Z", "+00:00"))
        end_time = datetime.fromisoformat(row["end_time"].replace("Z", "+00:00"))
        
        prospect = row.get("prospects")
        prospect_id_val = row.get("prospect_id")
        prospect_name = prospect.get("company_name") if prospect else None
        
        return CalendarMeetingResponse(
            id=row["id"],
            title=row["title"],
            description=row.get("description"),
            start_time=start_time,
            end_time=end_time,
            location=row.get("location"),
            meeting_url=row.get("meeting_url"),
            is_online=row.get("is_online", False),
            status=row.get("status", "confirmed"),
            attendees=attendees,
            organizer_email=row.get("organizer_email"),
            is_now=is_meeting_now(start_time, end_time),
            is_today=is_meeting_today(start_time),
            is_tomorrow=is_meeting_tomorrow(start_time),
            prospect_id=prospect_id_val,
            prospect_name=prospect_name,
            is_recurring=row.get("is_recurring", False),
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to get meeting {meeting_id}: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to load meeting: {str(e)}"
        )


# ==========================================
# Prospect Linking Endpoints
# ==========================================

class LinkProspectRequest(BaseModel):
    """Request to link a meeting to a prospect."""
    prospect_id: str


class LinkProspectResponse(BaseModel):
    """Response after linking."""
    success: bool
    message: str


class SuggestedMatchResponse(BaseModel):
    """A suggested prospect match."""
    prospect_id: str
    company_name: str
    confidence: float
    match_reason: str


class SuggestedMatchesResponse(BaseModel):
    """Response with suggested matches."""
    matches: List[SuggestedMatchResponse]


@router.post("/{meeting_id}/link-prospect", response_model=LinkProspectResponse)
async def link_meeting_to_prospect(
    meeting_id: str,
    request: LinkProspectRequest,
    user_org: tuple = Depends(get_user_org),
):
    """Manually link a meeting to a prospect."""
    user_id, organization_id = user_org
    
    try:
        # Verify meeting belongs to organization
        meeting_check = supabase.table("calendar_meetings").select("id").eq(
            "id", meeting_id
        ).eq("organization_id", organization_id).execute()
        
        if not meeting_check.data or len(meeting_check.data) == 0:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Meeting not found"
            )
        
        # Verify prospect belongs to organization
        prospect_check = supabase.table("prospects").select("id, company_name").eq(
            "id", request.prospect_id
        ).eq("organization_id", organization_id).execute()
        
        if not prospect_check.data or len(prospect_check.data) == 0:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Prospect not found"
            )
        
        # Update meeting with prospect link
        supabase.table("calendar_meetings").update({
            "prospect_id": request.prospect_id,
            "prospect_link_type": "manual",
            "match_confidence": 1.0,  # Manual links have 100% confidence
        }).eq("id", meeting_id).execute()
        
        company_name = prospect_check.data[0]["company_name"]
        
        return LinkProspectResponse(
            success=True,
            message=f"Meeting linked to {company_name}"
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to link meeting {meeting_id}: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to link meeting: {str(e)}"
        )


@router.delete("/{meeting_id}/link-prospect", response_model=LinkProspectResponse)
async def unlink_meeting_from_prospect(
    meeting_id: str,
    user_org: tuple = Depends(get_user_org),
):
    """Remove prospect link from a meeting."""
    user_id, organization_id = user_org
    
    try:
        # Verify meeting belongs to organization
        meeting_check = supabase.table("calendar_meetings").select("id").eq(
            "id", meeting_id
        ).eq("organization_id", organization_id).execute()
        
        if not meeting_check.data or len(meeting_check.data) == 0:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Meeting not found"
            )
        
        # Remove prospect link AND contact links (contacts are tied to prospect)
        supabase.table("calendar_meetings").update({
            "prospect_id": None,
            "prospect_link_type": None,
            "match_confidence": None,
            "contact_ids": [],  # Clear contacts too
        }).eq("id", meeting_id).execute()
        
        return LinkProspectResponse(
            success=True,
            message="Prospect link removed"
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to unlink meeting {meeting_id}: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to unlink meeting: {str(e)}"
        )


@router.delete("/{meeting_id}/contacts/{contact_id}", response_model=LinkProspectResponse)
async def unlink_contact_from_meeting(
    meeting_id: str,
    contact_id: str,
    user_org: tuple = Depends(get_user_org),
):
    """Remove a specific contact link from a meeting."""
    user_id, organization_id = user_org
    
    try:
        # Verify meeting belongs to organization and get current contact_ids
        meeting_result = supabase.table("calendar_meetings").select(
            "id, contact_ids"
        ).eq("id", meeting_id).eq("organization_id", organization_id).execute()
        
        if not meeting_result.data or len(meeting_result.data) == 0:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Meeting not found"
            )
        
        current_contact_ids = meeting_result.data[0].get("contact_ids") or []
        
        # Remove the specific contact
        new_contact_ids = [cid for cid in current_contact_ids if cid != contact_id]
        
        supabase.table("calendar_meetings").update({
            "contact_ids": new_contact_ids,
        }).eq("id", meeting_id).execute()
        
        return LinkProspectResponse(
            success=True,
            message="Contact unlinked from meeting"
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to unlink contact {contact_id} from meeting {meeting_id}: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to unlink contact: {str(e)}"
        )


@router.get("/{meeting_id}/suggested-matches", response_model=SuggestedMatchesResponse)
async def get_suggested_matches(
    meeting_id: str,
    user_org: tuple = Depends(get_user_org),
):
    """Get suggested prospect matches for a meeting."""
    user_id, organization_id = user_org
    
    try:
        # Get meeting details
        meeting_result = supabase.table("calendar_meetings").select(
            "id, title, attendees"
        ).eq("id", meeting_id).eq("organization_id", organization_id).execute()
        
        if not meeting_result.data or len(meeting_result.data) == 0:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Meeting not found"
            )
        
        meeting = meeting_result.data[0]
        
        # Run prospect matcher
        matcher = ProspectMatcher(supabase)
        result = await matcher.match_meeting(
            meeting_id=meeting["id"],
            meeting_title=meeting.get("title", ""),
            attendees=meeting.get("attendees", []),
            organization_id=organization_id
        )
        
        return SuggestedMatchesResponse(
            matches=[
                SuggestedMatchResponse(
                    prospect_id=m.prospect_id,
                    company_name=m.company_name,
                    confidence=m.confidence,
                    match_reason=m.match_reason
                )
                for m in result.all_matches
            ]
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to get matches for meeting {meeting_id}: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to get suggested matches: {str(e)}"
        )

