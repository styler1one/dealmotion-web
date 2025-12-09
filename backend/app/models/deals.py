"""
Deal Management Models

IMPORTANT: This is NOT a CRM replacement!
- Deals are for GROUPING preps/followups, not pipeline management
- CRM fields are for future sync only (read-only)
- No manual entry of value, stage, probability
"""

from pydantic import BaseModel, Field
from typing import Optional, List
from datetime import datetime, date
from uuid import UUID


# ============================================================
# DEAL MODELS
# ============================================================

class DealBase(BaseModel):
    """Base deal model - only user-editable fields"""
    name: str = Field(..., min_length=1, max_length=255, description="Deal name, e.g., 'Enterprise License 2025'")
    description: Optional[str] = Field(None, max_length=2000, description="Optional context/notes")


class DealCreate(DealBase):
    """Create a new deal"""
    prospect_id: UUID


class DealUpdate(BaseModel):
    """Update a deal - all fields optional"""
    name: Optional[str] = Field(None, min_length=1, max_length=255)
    description: Optional[str] = Field(None, max_length=2000)
    is_active: Optional[bool] = None


class DealCRMSync(BaseModel):
    """CRM sync data - populated by CRM integration, NOT by users"""
    crm_deal_id: Optional[str] = None
    crm_source: Optional[str] = None  # 'hubspot', 'salesforce', 'pipedrive'
    crm_stage: Optional[str] = None
    crm_value_cents: Optional[int] = None
    crm_currency: Optional[str] = None
    crm_probability: Optional[int] = Field(None, ge=0, le=100)
    crm_expected_close: Optional[date] = None
    crm_owner: Optional[str] = None


class Deal(DealBase):
    """Full deal model with all fields"""
    id: UUID
    prospect_id: UUID
    organization_id: UUID
    is_active: bool = True
    
    # CRM sync fields (read-only)
    crm_deal_id: Optional[str] = None
    crm_source: Optional[str] = None
    crm_stage: Optional[str] = None
    crm_value_cents: Optional[int] = None
    crm_currency: Optional[str] = None
    crm_probability: Optional[int] = None
    crm_expected_close: Optional[date] = None
    crm_owner: Optional[str] = None
    crm_synced_at: Optional[datetime] = None
    
    # Metadata
    created_at: datetime
    updated_at: datetime
    created_by: Optional[UUID] = None
    
    class Config:
        from_attributes = True


class DealWithStats(Deal):
    """Deal with computed statistics"""
    meeting_count: int = 0
    prep_count: int = 0
    followup_count: int = 0
    company_name: Optional[str] = None
    latest_meeting: Optional[dict] = None


# ============================================================
# MEETING MODELS
# ============================================================

class MeetingBase(BaseModel):
    """Base meeting model"""
    title: str = Field(..., min_length=1, max_length=255, description="Meeting title")
    meeting_type: Optional[str] = Field(None, description="Type: discovery, demo, negotiation, closing, review, other")
    scheduled_date: Optional[datetime] = None
    actual_date: Optional[datetime] = None
    duration_minutes: Optional[int] = Field(None, ge=0)
    location: Optional[str] = Field(None, max_length=255, description="Zoom, Teams, On-site, URL")
    notes: Optional[str] = None


class MeetingCreate(MeetingBase):
    """Create a new meeting"""
    prospect_id: UUID
    deal_id: Optional[UUID] = None
    contact_ids: List[UUID] = []


class MeetingUpdate(BaseModel):
    """Update a meeting - all fields optional"""
    title: Optional[str] = Field(None, min_length=1, max_length=255)
    meeting_type: Optional[str] = None
    deal_id: Optional[UUID] = None
    scheduled_date: Optional[datetime] = None
    actual_date: Optional[datetime] = None
    duration_minutes: Optional[int] = Field(None, ge=0)
    location: Optional[str] = Field(None, max_length=255)
    contact_ids: Optional[List[UUID]] = None
    notes: Optional[str] = None
    status: Optional[str] = Field(None, description="scheduled, completed, cancelled, no_show")
    outcome: Optional[str] = Field(None, description="positive, neutral, negative")


class Meeting(MeetingBase):
    """Full meeting model"""
    id: UUID
    deal_id: Optional[UUID] = None
    prospect_id: UUID
    organization_id: UUID
    contact_ids: List[UUID] = []
    status: str = "scheduled"
    outcome: Optional[str] = None
    
    # Metadata
    created_at: datetime
    updated_at: datetime
    created_by: Optional[UUID] = None
    
    class Config:
        from_attributes = True


class MeetingWithLinks(Meeting):
    """Meeting with linked prep and followup info"""
    has_prep: bool = False
    prep_id: Optional[UUID] = None
    has_followup: bool = False
    followup_id: Optional[UUID] = None
    contact_names: List[str] = []


# ============================================================
# ACTIVITY MODELS (Timeline)
# ============================================================

class ActivityCreate(BaseModel):
    """Create an activity log entry"""
    prospect_id: UUID
    deal_id: Optional[UUID] = None
    meeting_id: Optional[UUID] = None
    activity_type: str  # 'research', 'contact_added', 'prep', 'meeting', 'followup', 'deal_created', 'note'
    activity_id: Optional[UUID] = None
    title: str
    description: Optional[str] = None
    icon: Optional[str] = None
    metadata: Optional[dict] = None


class Activity(BaseModel):
    """Activity log entry"""
    id: UUID
    prospect_id: UUID
    deal_id: Optional[UUID] = None
    meeting_id: Optional[UUID] = None
    organization_id: UUID
    activity_type: str
    activity_id: Optional[UUID] = None
    title: str
    description: Optional[str] = None
    icon: Optional[str] = None
    metadata: Optional[dict] = None
    created_at: datetime
    created_by: Optional[UUID] = None
    
    class Config:
        from_attributes = True


# ============================================================
# PROSPECT HUB MODELS
# ============================================================

class ProspectHubSummary(BaseModel):
    """Summary for Prospect Hub overview"""
    prospect_id: UUID
    company_name: str
    status: Optional[str] = None
    
    # Counts
    research_count: int = 0
    contact_count: int = 0
    active_deal_count: int = 0
    meeting_count: int = 0
    prep_count: int = 0
    followup_count: int = 0
    
    # Latest activity
    latest_activity: Optional[dict] = None
    
    # Timestamps
    created_at: datetime
    last_activity_at: Optional[datetime] = None


class ProspectHub(BaseModel):
    """Full Prospect Hub data"""
    prospect: dict  # Full prospect data
    research: Optional[dict] = None  # Latest research brief
    contacts: List[dict] = []  # All contacts
    deals: List[DealWithStats] = []  # All deals with stats
    recent_activities: List[Activity] = []  # Recent timeline entries
    stats: ProspectHubSummary

