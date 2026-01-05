"""
Luna Unified AI Assistant - Pydantic Models
SPEC-046-Luna-Unified-AI-Assistant

Models for the Luna AI Assistant: messages, settings, feedback, and outreach.
"""

from pydantic import BaseModel, Field, ConfigDict
from typing import Optional, List, Dict, Any, Literal
from datetime import datetime
from enum import Enum


# =============================================================================
# CAMELCASE HELPER
# =============================================================================

def to_camel(string: str) -> str:
    """Convert snake_case to camelCase."""
    components = string.split('_')
    return components[0] + ''.join(x.title() for x in components[1:])


class CamelCaseModel(BaseModel):
    """Base model that serializes to camelCase."""
    model_config = ConfigDict(
        alias_generator=to_camel,
        populate_by_name=True,
        by_alias=True,  # Use camelCase when serializing
    )


# =============================================================================
# ENUMS
# =============================================================================

class MessageType(str, Enum):
    """Canonical Luna message types from SPEC-046 section 6."""
    # Prospecting-first messages (6.1)
    START_RESEARCH = "start_research"
    REVIEW_RESEARCH = "review_research"
    PREPARE_OUTREACH = "prepare_outreach"
    FIRST_TOUCH_SENT = "first_touch_sent"
    SUGGEST_MEETING_CREATION = "suggest_meeting_creation"
    
    # Meeting-driven messages (6.2)
    CREATE_PREP = "create_prep"
    PREP_READY = "prep_ready"
    
    # Post-meeting & Deal execution (6.3)
    REVIEW_MEETING_SUMMARY = "review_meeting_summary"
    REVIEW_CUSTOMER_REPORT = "review_customer_report"
    SEND_FOLLOWUP_EMAIL = "send_followup_email"
    CREATE_ACTION_ITEMS = "create_action_items"
    UPDATE_CRM_NOTES = "update_crm_notes"
    
    # P1 messages (6.4) - behind feature flag
    DEAL_ANALYSIS = "deal_analysis"
    SALES_COACHING_FEEDBACK = "sales_coaching_feedback"


class MessageStatus(str, Enum):
    """Luna message status from SPEC-046 section 8.1."""
    PENDING = "pending"       # Waiting for user action
    EXECUTING = "executing"   # Action in progress (async job)
    COMPLETED = "completed"   # Successfully finished
    DISMISSED = "dismissed"   # User clicked X
    SNOOZED = "snoozed"       # User clicked Later
    EXPIRED = "expired"       # Past expires_at without action
    FAILED = "failed"         # Execution failed


class ActionType(str, Enum):
    """CTA action types from SPEC-046 section 11."""
    NAVIGATE = "navigate"     # SSR-safe route navigation
    EXECUTE = "execute"       # Async job + executing state
    INLINE = "inline"         # Open existing modal/sheet


class SnoozeOption(str, Enum):
    """Snooze options from SPEC-046 section 12."""
    LATER_TODAY = "later_today"           # +4 hours
    TOMORROW_MORNING = "tomorrow_morning" # Next day 09:00 local
    NEXT_WORKING_DAY = "next_working_day" # Next weekday 09:00 local
    AFTER_MEETING = "after_meeting"       # Meeting end time (only if meeting_id)
    CUSTOM = "custom"                     # User-selected datetime


class FeedbackType(str, Enum):
    """Feedback types for luna_feedback table."""
    ACCEPTED = "accepted"
    DISMISSED = "dismissed"
    SNOOZED = "snoozed"
    COMPLETED = "completed"
    FAILED = "failed"
    EXPIRED = "expired"


class OutreachChannel(str, Enum):
    """Outreach channels from SPEC-046 section 6.1."""
    LINKEDIN_CONNECT = "linkedin_connect"
    LINKEDIN_MESSAGE = "linkedin_message"
    EMAIL = "email"
    WHATSAPP = "whatsapp"
    OTHER = "other"


class OutreachStatus(str, Enum):
    """Outreach message status."""
    DRAFT = "draft"
    SENT = "sent"
    SKIPPED = "skipped"


class Surface(str, Enum):
    """Luna surfaces from SPEC-046 section 5."""
    HOME = "home"
    WIDGET = "widget"


# =============================================================================
# MESSAGE MODELS
# =============================================================================

class LunaMessageBase(CamelCaseModel):
    """Base model for Luna messages."""
    message_type: MessageType
    title: str
    description: Optional[str] = None
    luna_message: str
    
    # Action configuration
    action_type: ActionType
    action_route: Optional[str] = None
    action_data: Dict[str, Any] = Field(default_factory=dict)
    
    # Priority
    priority: int = Field(default=50, ge=0, le=100)
    priority_inputs: Dict[str, Any] = Field(default_factory=dict)
    
    # Timing
    expires_at: Optional[datetime] = None


class LunaMessageCreate(LunaMessageBase):
    """Model for creating a new Luna message."""
    user_id: str
    organization_id: str
    dedupe_key: str
    
    # Related entities
    prospect_id: Optional[str] = None
    contact_id: Optional[str] = None
    meeting_id: Optional[str] = None
    research_id: Optional[str] = None
    prep_id: Optional[str] = None
    followup_id: Optional[str] = None
    outreach_id: Optional[str] = None


class LunaMessage(LunaMessageBase):
    """Full Luna message model."""
    id: str
    user_id: str
    organization_id: str
    dedupe_key: str
    status: MessageStatus = MessageStatus.PENDING
    
    # Related entities
    prospect_id: Optional[str] = None
    contact_id: Optional[str] = None
    meeting_id: Optional[str] = None
    research_id: Optional[str] = None
    prep_id: Optional[str] = None
    followup_id: Optional[str] = None
    outreach_id: Optional[str] = None
    
    # Timing
    snooze_until: Optional[datetime] = None
    
    # Error handling
    error_code: Optional[str] = None
    error_message: Optional[str] = None
    retryable: bool = False
    
    # Timestamps
    created_at: datetime
    updated_at: datetime
    viewed_at: Optional[datetime] = None
    acted_at: Optional[datetime] = None
    
    class Config:
        from_attributes = True


class MessageCounts(CamelCaseModel):
    """Counts of messages by status."""
    pending: int = 0
    executing: int = 0
    completed: int = 0
    dismissed: int = 0
    snoozed: int = 0
    expired: int = 0
    failed: int = 0
    urgent: int = 0  # High priority pending


class MessagesResponse(CamelCaseModel):
    """Response model for messages list."""
    messages: List[LunaMessage]
    counts: MessageCounts
    total: int


# =============================================================================
# ACTION MODELS
# =============================================================================

class MessageActionRequest(CamelCaseModel):
    """Request model for message actions (accept/dismiss/snooze)."""
    reason: Optional[str] = None
    snooze_until: Optional[datetime] = None
    snooze_option: Optional[SnoozeOption] = None
    surface: Optional[Surface] = None


class MessageShowRequest(CamelCaseModel):
    """Request model for marking message as shown."""
    surface: Surface


class MessageActionResponse(CamelCaseModel):
    """Response model for message actions."""
    success: bool
    message_id: str
    new_status: MessageStatus
    error: Optional[str] = None


# =============================================================================
# SETTINGS MODELS
# =============================================================================

class LunaSettingsBase(CamelCaseModel):
    """Base model for Luna settings."""
    enabled: bool = True
    show_widget: bool = True
    show_contextual_tips: bool = True
    prep_reminder_hours: int = 24
    outreach_cooldown_days: int = 14
    excluded_meeting_keywords: List[str] = Field(
        default_factory=lambda: ['internal', '1:1', 'standup', 'sync']
    )


class LunaSettingsUpdate(CamelCaseModel):
    """Model for updating Luna settings."""
    enabled: Optional[bool] = None
    show_widget: Optional[bool] = None
    show_contextual_tips: Optional[bool] = None
    prep_reminder_hours: Optional[int] = None
    outreach_cooldown_days: Optional[int] = None
    excluded_meeting_keywords: Optional[List[str]] = None


class LunaSettings(LunaSettingsBase):
    """Full Luna settings model."""
    id: str
    user_id: str
    organization_id: str
    created_at: datetime
    updated_at: datetime
    
    class Config:
        from_attributes = True


# =============================================================================
# GREETING MODELS
# =============================================================================

class LunaMode(str, Enum):
    """Luna greeting modes."""
    MORNING = "morning"
    PROPOSAL = "proposal"
    URGENCY = "urgency"
    CELEBRATION = "celebration"
    FOCUS = "focus"


class LunaGreeting(CamelCaseModel):
    """Luna greeting for the home page."""
    mode: LunaMode
    message: str
    emphasis: Optional[str] = None
    action: Optional[str] = None
    action_route: Optional[str] = None
    pending_count: int = 0
    urgent_count: int = 0


# =============================================================================
# STATS MODELS
# =============================================================================

class TodayStats(CamelCaseModel):
    """Today's progress stats."""
    research_completed: int = 0
    preps_completed: int = 0
    followups_completed: int = 0
    outreach_sent: int = 0
    total_actions: int = 0


class WeekStats(CamelCaseModel):
    """This week's progress stats."""
    research_completed: int = 0
    preps_completed: int = 0
    followups_completed: int = 0
    outreach_sent: int = 0
    total_actions: int = 0


class LunaStats(CamelCaseModel):
    """Luna statistics."""
    today: TodayStats
    week: WeekStats
    pending_count: int = 0
    urgent_count: int = 0
    completed_today: int = 0


# =============================================================================
# TIP OF DAY MODELS
# =============================================================================

class TipCategory(str, Enum):
    """Tip categories."""
    RESEARCH = "research"
    PREP = "prep"
    FOLLOWUP = "followup"
    GENERAL = "general"


class TipOfDay(CamelCaseModel):
    """Tip of the day - generic only, no CTA per SPEC-046."""
    id: str
    content: str
    icon: str
    category: TipCategory
    # No action_route - tips are informational only


# =============================================================================
# OUTREACH MODELS
# =============================================================================

class OutreachMessageBase(CamelCaseModel):
    """Base model for outreach messages."""
    prospect_id: str
    contact_id: Optional[str] = None
    research_id: Optional[str] = None
    channel: OutreachChannel
    subject: Optional[str] = None  # For email
    body: Optional[str] = None
    payload: Dict[str, Any] = Field(default_factory=dict)


class OutreachMessageCreate(OutreachMessageBase):
    """Model for creating outreach message."""
    user_id: str
    organization_id: str


class OutreachMessage(OutreachMessageBase):
    """Full outreach message model."""
    id: str
    user_id: str
    organization_id: str
    status: OutreachStatus = OutreachStatus.DRAFT
    sent_at: Optional[datetime] = None
    created_at: datetime
    updated_at: datetime
    
    class Config:
        from_attributes = True


class OutreachGenerateRequest(CamelCaseModel):
    """Request model for AI outreach generation."""
    prospect_id: str
    contact_id: str
    research_id: Optional[str] = None
    channel: OutreachChannel
    tone: str = "professional"  # professional | friendly | direct


class OutreachGenerateResponse(CamelCaseModel):
    """Response model for AI outreach generation."""
    subject: Optional[str] = None  # For email only
    body: str
    character_count: int


class OutreachMarkSentRequest(CamelCaseModel):
    """Request to mark outreach as sent."""
    pass  # No additional fields needed


# =============================================================================
# UPCOMING MEETING MODEL
# =============================================================================

class UpcomingMeeting(CamelCaseModel):
    """Upcoming meeting for sidebar."""
    id: str
    title: str
    company: Optional[str] = None
    start_time: datetime
    starts_in_hours: float
    has_prep: bool
    prospect_id: Optional[str] = None
    prep_id: Optional[str] = None


# =============================================================================
# FEATURE FLAGS
# =============================================================================

class FeatureFlag(CamelCaseModel):
    """Feature flag model."""
    flag_name: str
    flag_value: bool
    description: Optional[str] = None
    user_percentage: int = 0


class FeatureFlagsResponse(CamelCaseModel):
    """Response with all Luna feature flags."""
    luna_enabled: bool
    luna_shadow_mode: bool
    luna_widget_enabled: bool
    luna_p1_features: bool


# =============================================================================
# SEQUENCING CONSTANTS
# =============================================================================

# Maximum concurrent messages per user (from SPEC-046 section 7.3)
MAX_CONCURRENT_MESSAGES = 2

# Sequential message types (cannot run in parallel)
SEQUENTIAL_TYPES = {
    MessageType.REVIEW_MEETING_SUMMARY,
    MessageType.REVIEW_CUSTOMER_REPORT,
    MessageType.SEND_FOLLOWUP_EMAIL,
    MessageType.CREATE_ACTION_ITEMS,
}

# Parallel message types (can run alongside sequential after dependency met)
PARALLEL_TYPES = {
    MessageType.UPDATE_CRM_NOTES,
    MessageType.DEAL_ANALYSIS,
    MessageType.SALES_COACHING_FEEDBACK,
}

# Dependency map (from SPEC-046 section 7.2)
DEPENDENCY_MAP: Dict[MessageType, List[MessageType]] = {
    MessageType.REVIEW_CUSTOMER_REPORT: [MessageType.REVIEW_MEETING_SUMMARY],
    MessageType.SEND_FOLLOWUP_EMAIL: [MessageType.REVIEW_CUSTOMER_REPORT],
    MessageType.CREATE_ACTION_ITEMS: [MessageType.SEND_FOLLOWUP_EMAIL],
    MessageType.UPDATE_CRM_NOTES: [MessageType.REVIEW_MEETING_SUMMARY],
    MessageType.DEAL_ANALYSIS: [MessageType.REVIEW_MEETING_SUMMARY],
    MessageType.SALES_COACHING_FEEDBACK: [MessageType.REVIEW_MEETING_SUMMARY],
}

# Priority values per message type (from SPEC-046 Appendix A)
MESSAGE_PRIORITIES: Dict[MessageType, int] = {
    MessageType.START_RESEARCH: 70,
    MessageType.REVIEW_RESEARCH: 75,
    MessageType.PREPARE_OUTREACH: 65,
    MessageType.FIRST_TOUCH_SENT: 40,  # Progress message, lower priority
    MessageType.SUGGEST_MEETING_CREATION: 60,
    MessageType.CREATE_PREP: 75,  # Average of 70-80 window buckets
    MessageType.PREP_READY: 85,
    MessageType.REVIEW_MEETING_SUMMARY: 90,
    MessageType.REVIEW_CUSTOMER_REPORT: 85,
    MessageType.SEND_FOLLOWUP_EMAIL: 80,
    MessageType.CREATE_ACTION_ITEMS: 75,
    MessageType.UPDATE_CRM_NOTES: 70,
    # P1 features - no fixed priority yet
    MessageType.DEAL_ANALYSIS: 60,
    MessageType.SALES_COACHING_FEEDBACK: 55,
}

# Dedupe key patterns (from SPEC-046 Appendix B)
DEDUPE_KEY_PATTERNS: Dict[MessageType, str] = {
    MessageType.START_RESEARCH: "start_research:prospect:{prospect_id}",
    MessageType.REVIEW_RESEARCH: "review_research:{research_id}",
    MessageType.PREPARE_OUTREACH: "prepare_outreach:{prospect_id}:{contact_id}",
    MessageType.FIRST_TOUCH_SENT: "first_touch_sent:{prospect_id}:{outreach_id}",
    MessageType.SUGGEST_MEETING_CREATION: "suggest_meeting_creation:{prospect_id}",
    MessageType.CREATE_PREP: "create_prep:{meeting_id}:{window_bucket}",
    MessageType.PREP_READY: "prep_ready:{prep_id}",
    MessageType.REVIEW_MEETING_SUMMARY: "review_meeting_summary:{meeting_id}",
    MessageType.REVIEW_CUSTOMER_REPORT: "review_customer_report:{meeting_id}",
    MessageType.SEND_FOLLOWUP_EMAIL: "send_followup_email:{meeting_id}",
    MessageType.CREATE_ACTION_ITEMS: "create_action_items:{meeting_id}",
    MessageType.UPDATE_CRM_NOTES: "update_crm_notes:{meeting_id}",
    MessageType.DEAL_ANALYSIS: "deal_analysis:{prospect_id}",
    MessageType.SALES_COACHING_FEEDBACK: "sales_coaching:{meeting_id}",
}
