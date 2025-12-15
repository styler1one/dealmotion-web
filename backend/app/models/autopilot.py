"""
DealMotion Autopilot - Pydantic Models
SPEC-045 / TASK-048

Models for the Autopilot feature: proposals, settings, outcomes, and preferences.
"""

from pydantic import BaseModel, Field
from typing import Optional, List, Dict, Any, Literal
from datetime import datetime
from enum import Enum


# =============================================================================
# ENUMS
# =============================================================================

class ProposalType(str, Enum):
    """Types of autopilot proposals."""
    RESEARCH_PREP = "research_prep"       # New meeting, unknown org
    PREP_ONLY = "prep_only"               # Known prospect, no prep
    FOLLOWUP_PACK = "followup_pack"       # Post-meeting
    REACTIVATION = "reactivation"         # Silent prospect
    COMPLETE_FLOW = "complete_flow"       # Research done, no next step


class ProposalStatus(str, Enum):
    """Status of an autopilot proposal."""
    PROPOSED = "proposed"
    ACCEPTED = "accepted"
    EXECUTING = "executing"
    COMPLETED = "completed"
    DECLINED = "declined"
    SNOOZED = "snoozed"
    EXPIRED = "expired"
    FAILED = "failed"


class TriggerType(str, Enum):
    """What triggered the proposal."""
    CALENDAR_NEW_ORG = "calendar_new_org"
    CALENDAR_KNOWN_PROSPECT = "calendar_known_prospect"
    MEETING_ENDED = "meeting_ended"
    TRANSCRIPT_READY = "transcript_ready"
    PROSPECT_SILENT = "prospect_silent"
    FLOW_INCOMPLETE = "flow_incomplete"
    MANUAL = "manual"


class NotificationStyle(str, Enum):
    """Notification frequency preference."""
    EAGER = "eager"         # Notify immediately
    BALANCED = "balanced"   # Smart timing
    MINIMAL = "minimal"     # Only urgent


class OutcomeRating(str, Enum):
    """Meeting outcome rating."""
    POSITIVE = "positive"
    NEUTRAL = "neutral"
    NEGATIVE = "negative"


class OutcomeSource(str, Enum):
    """Source of outcome rating."""
    USER_INPUT = "user_input"
    FOLLOWUP_SENTIMENT = "followup_sentiment"
    INFERRED = "inferred"


class PrepLength(str, Enum):
    """Preferred prep length."""
    SHORT = "short"
    MEDIUM = "medium"
    LONG = "long"


class LunaMode(str, Enum):
    """Luna greeting modes."""
    MORNING = "morning"
    PROPOSAL = "proposal"
    URGENCY = "urgency"
    CELEBRATION = "celebration"
    COACH = "coach"


# =============================================================================
# PROPOSAL MODELS
# =============================================================================

class SuggestedAction(BaseModel):
    """A single suggested action within a proposal."""
    action: str  # 'research', 'prep', 'followup_summarize', 'followup_email'
    params: Dict[str, Any] = Field(default_factory=dict)


class AutopilotProposalBase(BaseModel):
    """Base model for autopilot proposals."""
    proposal_type: ProposalType
    trigger_type: TriggerType
    trigger_entity_id: Optional[str] = None
    trigger_entity_type: Optional[str] = None
    title: str
    description: Optional[str] = None
    luna_message: str
    suggested_actions: List[SuggestedAction] = Field(default_factory=list)
    priority: int = Field(default=50, ge=0, le=100)
    expires_at: Optional[datetime] = None
    context_data: Dict[str, Any] = Field(default_factory=dict)


class AutopilotProposalCreate(AutopilotProposalBase):
    """Model for creating a new proposal."""
    organization_id: str
    user_id: str


class AutopilotProposal(AutopilotProposalBase):
    """Full autopilot proposal model."""
    id: str
    organization_id: str
    user_id: str
    status: ProposalStatus = ProposalStatus.PROPOSED
    decided_at: Optional[datetime] = None
    decision_reason: Optional[str] = None
    snoozed_until: Optional[datetime] = None
    execution_started_at: Optional[datetime] = None
    execution_completed_at: Optional[datetime] = None
    execution_result: Optional[Dict[str, Any]] = None
    execution_error: Optional[str] = None
    artifacts: List[Dict[str, Any]] = Field(default_factory=list)
    expired_reason: Optional[str] = None
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


class ProposalActionRequest(BaseModel):
    """Request model for proposal actions (accept/decline/snooze)."""
    reason: Optional[str] = None
    snooze_until: Optional[datetime] = None


class ProposalCounts(BaseModel):
    """Counts of proposals by status."""
    proposed: int = 0
    executing: int = 0
    completed: int = 0
    declined: int = 0
    snoozed: int = 0
    expired: int = 0
    failed: int = 0


class ProposalsResponse(BaseModel):
    """Response model for listing proposals."""
    proposals: List[AutopilotProposal]
    counts: ProposalCounts
    total: int


# =============================================================================
# SETTINGS MODELS
# =============================================================================

class AutopilotSettingsBase(BaseModel):
    """Base model for autopilot settings."""
    enabled: bool = True
    auto_research_new_meetings: bool = True
    auto_prep_known_prospects: bool = True
    auto_followup_after_meeting: bool = True
    reactivation_days_threshold: int = 14
    prep_hours_before_meeting: int = 24
    notification_style: NotificationStyle = NotificationStyle.BALANCED
    excluded_meeting_keywords: List[str] = Field(default_factory=list)


class AutopilotSettingsUpdate(BaseModel):
    """Model for updating autopilot settings."""
    enabled: Optional[bool] = None
    auto_research_new_meetings: Optional[bool] = None
    auto_prep_known_prospects: Optional[bool] = None
    auto_followup_after_meeting: Optional[bool] = None
    reactivation_days_threshold: Optional[int] = None
    prep_hours_before_meeting: Optional[int] = None
    notification_style: Optional[NotificationStyle] = None
    excluded_meeting_keywords: Optional[List[str]] = None


class AutopilotSettings(AutopilotSettingsBase):
    """Full autopilot settings model."""
    id: str
    user_id: str
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


# =============================================================================
# LUNA GREETING MODELS
# =============================================================================

class LunaGreeting(BaseModel):
    """Model for Luna's dynamic greeting."""
    mode: LunaMode
    message: str
    emphasis: Optional[str] = None
    action: Optional[str] = None
    action_route: Optional[str] = None
    pending_count: int = 0
    urgent_count: int = 0


class UpcomingMeeting(BaseModel):
    """Model for upcoming meeting info."""
    id: str
    title: str
    company: Optional[str] = None
    start_time: datetime
    starts_in_hours: float
    has_prep: bool = False
    prospect_id: Optional[str] = None


# =============================================================================
# STATS MODELS
# =============================================================================

class AutopilotStats(BaseModel):
    """Stats for the autopilot home page."""
    pending_count: int = 0
    urgent_count: int = 0
    completed_today: int = 0
    upcoming_meetings: List[UpcomingMeeting] = Field(default_factory=list)
    luna_greeting: LunaGreeting


# =============================================================================
# OUTCOME MODELS
# =============================================================================

class MeetingOutcomeBase(BaseModel):
    """Base model for meeting outcomes."""
    calendar_meeting_id: Optional[str] = None
    preparation_id: Optional[str] = None
    followup_id: Optional[str] = None
    prospect_id: Optional[str] = None
    outcome_rating: Optional[OutcomeRating] = None
    outcome_source: Optional[OutcomeSource] = None
    prep_viewed: bool = False
    prep_view_duration_seconds: Optional[int] = None
    prep_scroll_depth: Optional[float] = None
    had_contact_analysis: Optional[bool] = None
    had_kb_content: Optional[bool] = None
    prep_length_words: Optional[int] = None


class MeetingOutcomeCreate(MeetingOutcomeBase):
    """Model for creating a meeting outcome."""
    organization_id: str
    user_id: str


class MeetingOutcome(MeetingOutcomeBase):
    """Full meeting outcome model."""
    id: str
    organization_id: str
    user_id: str
    created_at: datetime

    class Config:
        from_attributes = True


class OutcomeRequest(BaseModel):
    """Request model for recording an outcome."""
    outcome_rating: OutcomeRating
    calendar_meeting_id: Optional[str] = None
    preparation_id: Optional[str] = None
    followup_id: Optional[str] = None
    prospect_id: Optional[str] = None


# =============================================================================
# PREFERENCES MODELS
# =============================================================================

class UserPrepPreferencesBase(BaseModel):
    """Base model for user prep preferences."""
    preferred_length: Optional[PrepLength] = None
    valued_sections: List[str] = Field(default_factory=list)
    deemphasized_sections: List[str] = Field(default_factory=list)
    avg_prep_view_duration_seconds: Optional[int] = None
    prep_completion_rate: Optional[float] = None
    positive_outcome_rate: Optional[float] = None
    sample_size: int = 0


class UserPrepPreferences(UserPrepPreferencesBase):
    """Full user prep preferences model."""
    id: str
    user_id: str
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


# =============================================================================
# PREP VIEWED TRACKING
# =============================================================================

class PrepViewedRequest(BaseModel):
    """Request model for tracking prep viewed."""
    preparation_id: str
    view_duration_seconds: int
    scroll_depth: float = Field(ge=0.0, le=1.0)


# =============================================================================
# LUNA MESSAGE TEMPLATES
# =============================================================================

LUNA_TEMPLATES = {
    # New meeting, unknown org
    "research_prep_new": "Je hebt {time} een meeting met een nieuw bedrijf. Wil je dat ik research doe en een briefing maak?",
    
    # Known prospect, no prep
    "prep_only": "Je hebt al research over {company}. Wil je dat ik een meeting prep maak voor {time}?",
    
    # Post-meeting
    "followup_pack": "Je meeting met {company} is afgelopen. Ik kan een samenvatting en follow-up email maken.",
    
    # Silent prospect
    "reactivation": "{company} is al {days} dagen stil. Het laatste gesprek was positief. Tijd voor een check-in?",
    
    # Incomplete flow
    "complete_flow": "Je hebt {contact} toegevoegd aan {company}. Wil je een prep maken voor het eerste gesprek?",
    
    # Execution complete
    "execution_complete": "Je briefing voor {company} is klaar!",
    
    # Execution failed
    "execution_failed": "Er ging iets mis bij het maken van je briefing voor {company}. Wil je het opnieuw proberen?",
    
    # Urgent
    "urgent": "Let op: je meeting met {company} begint over {hours} uur!",
}
