"""
AI Sales Coach "Luna" - Pydantic Models
TASK-029 / SPEC-028
"""

from pydantic import BaseModel, Field
from typing import Optional, List, Dict, Any, Literal
from datetime import datetime, time
from enum import Enum


# =============================================================================
# ENUMS
# =============================================================================

class EventType(str, Enum):
    PAGE_VIEW = "page_view"
    ACTION_COMPLETED = "action_completed"
    SUGGESTION_SHOWN = "suggestion_shown"
    SUGGESTION_CLICKED = "suggestion_clicked"
    SUGGESTION_DISMISSED = "suggestion_dismissed"
    SUGGESTION_SNOOZED = "suggestion_snoozed"
    WIDGET_EXPANDED = "widget_expanded"
    WIDGET_COLLAPSED = "widget_collapsed"
    SETTINGS_CHANGED = "settings_changed"


class SuggestionType(str, Enum):
    ADD_CONTACTS = "add_contacts"
    CREATE_PREP = "create_prep"
    CREATE_FOLLOWUP = "create_followup"
    GENERATE_ACTION = "generate_action"
    REVIEW_COACHING = "review_coaching"
    OVERDUE_PROSPECT = "overdue_prospect"
    MEETING_REMINDER = "meeting_reminder"
    COMPLETE_PROFILE = "complete_profile"
    TIP_OF_DAY = "tip_of_day"


class SuggestionAction(str, Enum):
    CLICKED = "clicked"
    DISMISSED = "dismissed"
    SNOOZED = "snoozed"
    EXPIRED = "expired"


class PatternType(str, Enum):
    WORK_HOURS = "work_hours"
    STEP_TIMING = "step_timing"
    PREFERRED_ACTIONS = "preferred_actions"
    DISMISS_PATTERNS = "dismiss_patterns"
    SUCCESS_PATTERNS = "success_patterns"


class NotificationFrequency(str, Enum):
    MINIMAL = "minimal"
    NORMAL = "normal"
    FREQUENT = "frequent"


class WidgetState(str, Enum):
    MINIMIZED = "minimized"
    COMPACT = "compact"
    EXPANDED = "expanded"
    HIDDEN = "hidden"


class EntityType(str, Enum):
    RESEARCH = "research"
    PREP = "prep"
    FOLLOWUP = "followup"
    PROSPECT = "prospect"
    DEAL = "deal"


# =============================================================================
# SETTINGS MODELS
# =============================================================================

class CoachSettingsBase(BaseModel):
    is_enabled: bool = True
    show_inline_tips: bool = True
    show_completion_modals: bool = True
    quiet_hours_start: Optional[str] = None  # HH:MM format
    quiet_hours_end: Optional[str] = None
    notification_frequency: NotificationFrequency = NotificationFrequency.NORMAL
    widget_state: WidgetState = WidgetState.MINIMIZED


class CoachSettingsUpdate(BaseModel):
    is_enabled: Optional[bool] = None
    show_inline_tips: Optional[bool] = None
    show_completion_modals: Optional[bool] = None
    quiet_hours_start: Optional[str] = None
    quiet_hours_end: Optional[str] = None
    notification_frequency: Optional[NotificationFrequency] = None
    widget_state: Optional[WidgetState] = None
    dismissed_tip_ids: Optional[List[str]] = None


class CoachSettings(CoachSettingsBase):
    id: str
    user_id: str
    dismissed_tip_ids: List[str] = Field(default_factory=list)
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


# =============================================================================
# BEHAVIOR EVENT MODELS
# =============================================================================

class BehaviorEventCreate(BaseModel):
    event_type: EventType
    event_data: Dict[str, Any] = Field(default_factory=dict)
    page_context: Optional[str] = None


class BehaviorEvent(BaseModel):
    id: str
    user_id: str
    organization_id: str
    event_type: EventType
    event_data: Dict[str, Any]
    page_context: Optional[str]
    created_at: datetime

    class Config:
        from_attributes = True


# =============================================================================
# SUGGESTION MODELS
# =============================================================================

class SuggestionBase(BaseModel):
    suggestion_type: SuggestionType
    title: str
    description: str
    reason: Optional[str] = None
    priority: float = 50.0
    action_route: Optional[str] = None
    action_label: Optional[str] = None
    related_entity_type: Optional[EntityType] = None
    related_entity_id: Optional[str] = None
    icon: str = "💡"


class SuggestionCreate(SuggestionBase):
    expires_at: Optional[datetime] = None


class Suggestion(SuggestionBase):
    id: str
    user_id: str
    organization_id: str
    shown_at: datetime
    expires_at: Optional[datetime]
    action_taken: Optional[SuggestionAction]
    action_taken_at: Optional[datetime]
    snooze_until: Optional[datetime]
    feedback_rating: Optional[int]

    class Config:
        from_attributes = True


class SuggestionActionRequest(BaseModel):
    action: SuggestionAction
    snooze_until: Optional[datetime] = None
    feedback_rating: Optional[int] = Field(None, ge=1, le=5)


class SuggestionsResponse(BaseModel):
    suggestions: List[Suggestion]
    count: int
    has_priority: bool = False


# =============================================================================
# PATTERN MODELS
# =============================================================================

class UserPattern(BaseModel):
    id: str
    user_id: str
    organization_id: str
    pattern_type: PatternType
    pattern_data: Dict[str, Any]
    confidence: float
    sample_size: int
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


class PatternsResponse(BaseModel):
    patterns: List[UserPattern]


# =============================================================================
# STATS MODELS
# =============================================================================

class TodayStats(BaseModel):
    research_completed: int = 0
    preps_completed: int = 0
    followups_completed: int = 0
    actions_generated: int = 0
    total_completed: int = 0
    streak_days: int = 0


class CoachStatsResponse(BaseModel):
    today: TodayStats
    suggestions_pending: int = 0
    patterns_learned: int = 0


# =============================================================================
# INSIGHT MODELS
# =============================================================================

class InsightType(str, Enum):
    CORRELATION = "correlation"
    PREDICTION = "prediction"
    RECOMMENDATION = "recommendation"
    TIP = "tip"


class Insight(BaseModel):
    id: str
    type: InsightType
    title: str
    description: str
    confidence: float = 0.5
    based_on: Optional[str] = None
    icon: str = "💡"
    action_route: Optional[str] = None
    action_label: Optional[str] = None


class InsightsResponse(BaseModel):
    insights: List[Insight]
    count: int


# =============================================================================
# CONTEXT MODEL (for rule evaluation)
# =============================================================================

class UserContext(BaseModel):
    """Context data used by the rule engine to generate suggestions."""
    user_id: str
    organization_id: str
    
    # Profile status
    has_sales_profile: bool = False
    has_company_profile: bool = False
    
    # Research data
    research_briefs: List[Dict[str, Any]] = Field(default_factory=list)
    research_without_contacts: List[Dict[str, Any]] = Field(default_factory=list)
    
    # Preparation data
    preps_without_followup: List[Dict[str, Any]] = Field(default_factory=list)
    preps_completed: List[Dict[str, Any]] = Field(default_factory=list)
    
    # Follow-up data
    followups_without_actions: List[Dict[str, Any]] = Field(default_factory=list)
    followups_completed: List[Dict[str, Any]] = Field(default_factory=list)
    
    # Prospects
    inactive_prospects: List[Dict[str, Any]] = Field(default_factory=list)
    
    # Patterns (learned)
    patterns: Dict[str, Any] = Field(default_factory=dict)
    
    # Time context
    current_hour: int = 12
    current_day_of_week: int = 0  # 0 = Monday
    
    # Autopilot integration (avoid duplicate suggestions)
    autopilot_enabled: bool = False


# =============================================================================
# RULE MODELS
# =============================================================================

class RuleDefinition(BaseModel):
    """Definition of a suggestion rule."""
    id: str
    name: str
    description: str
    suggestion_type: SuggestionType
    base_priority: float = 50.0
    icon: str = "💡"
    title_template: str  # Can include {company}, {name}, etc.
    description_template: str
    reason_template: Optional[str] = None
    action_route_template: Optional[str] = None
    action_label: Optional[str] = None

