"""
Follow-up Actions Models

Pydantic models for the modular follow-up action system.
"""

from pydantic import BaseModel, Field
from typing import Optional, List, Dict, Any, Literal
from datetime import datetime
from enum import Enum


class ActionType(str, Enum):
    """Types of actions that can be generated for a follow-up"""
    CUSTOMER_REPORT = "customer_report"
    SHARE_EMAIL = "share_email"
    COMMERCIAL_ANALYSIS = "commercial_analysis"
    SALES_COACHING = "sales_coaching"
    ACTION_ITEMS = "action_items"
    INTERNAL_REPORT = "internal_report"


# Action type metadata for UI
ACTION_TYPE_INFO = {
    ActionType.CUSTOMER_REPORT: {
        "icon": "📄",
        "label_en": "Customer Report",
        "label_nl": "Klantverslag",
        "description_en": "Professional report to share with the customer",
        "description_nl": "Professioneel verslag om te delen met de klant",
    },
    ActionType.SHARE_EMAIL: {
        "icon": "✉️",
        "label_en": "Share Email",
        "label_nl": "Deel-email",
        "description_en": "Ready-to-send email to share the customer report",
        "description_nl": "Kant-en-klare email om het klantverslag te delen",
    },
    ActionType.COMMERCIAL_ANALYSIS: {
        "icon": "💰",
        "label_en": "Commercial Analysis",
        "label_nl": "Commerciële Analyse",
        "description_en": "Buying signals, risks, and deal assessment",
        "description_nl": "Koopsignalen, risico's en deal-inschatting",
    },
    ActionType.SALES_COACHING: {
        "icon": "📈",
        "label_en": "Sales Coaching",
        "label_nl": "Sales Coaching",
        "description_en": "Feedback on your sales performance",
        "description_nl": "Feedback op je salesgesprek",
    },
    ActionType.ACTION_ITEMS: {
        "icon": "✅",
        "label_en": "Action Items",
        "label_nl": "Actiepunten",
        "description_en": "Structured tasks with owners and deadlines",
        "description_nl": "Gestructureerde taken met eigenaren en deadlines",
    },
    ActionType.INTERNAL_REPORT: {
        "icon": "📝",
        "label_en": "Internal Report",
        "label_nl": "Intern Verslag",
        "description_en": "Short summary for CRM or team",
        "description_nl": "Korte samenvatting voor CRM of team",
    },
}


class FollowupActionBase(BaseModel):
    """Base model for follow-up actions"""
    action_type: ActionType
    content: Optional[str] = None
    metadata: Dict[str, Any] = Field(default_factory=dict)
    language: str = "en"


class FollowupActionCreate(BaseModel):
    """Request model for generating a new action"""
    action_type: ActionType
    regenerate: bool = False  # If true, replace existing action of same type


class FollowupActionUpdate(BaseModel):
    """Request model for updating an action"""
    content: Optional[str] = None
    metadata: Optional[Dict[str, Any]] = None


class FollowupAction(FollowupActionBase):
    """Full follow-up action model"""
    id: str
    followup_id: str
    organization_id: str
    user_id: str
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


class FollowupActionResponse(BaseModel):
    """Response model for a single action"""
    id: str
    followup_id: str
    action_type: ActionType
    content: Optional[str] = None
    metadata: Dict[str, Any] = Field(default_factory=dict)
    language: str
    created_at: str
    updated_at: str
    
    # Computed fields for UI
    icon: str = ""
    label: str = ""
    description: str = ""
    word_count: int = 0

    @classmethod
    def from_db(cls, data: dict, locale: str = "en") -> "FollowupActionResponse":
        """Create response from database row with localized labels"""
        action_type = ActionType(data["action_type"])
        info = ACTION_TYPE_INFO.get(action_type, {})
        
        content = data.get("content", "") or ""
        word_count = len(content.split()) if content else 0
        
        label_key = f"label_{locale}" if locale in ["en", "nl"] else "label_en"
        desc_key = f"description_{locale}" if locale in ["en", "nl"] else "description_en"
        
        return cls(
            id=data["id"],
            followup_id=data["followup_id"],
            action_type=action_type,
            content=content,
            metadata=data.get("metadata", {}),
            language=data.get("language", "en"),
            created_at=str(data["created_at"]),
            updated_at=str(data["updated_at"]),
            icon=info.get("icon", "📄"),
            label=info.get(label_key, info.get("label_en", "")),
            description=info.get(desc_key, info.get("description_en", "")),
            word_count=word_count,
        )


class FollowupActionsListResponse(BaseModel):
    """Response model for listing actions"""
    actions: List[FollowupActionResponse]
    count: int


class ActionTypesResponse(BaseModel):
    """Response model for available action types"""
    types: List[Dict[str, Any]]


# Metadata schemas for specific action types
class CustomerReportMetadata(BaseModel):
    """Metadata for customer report action"""
    word_count: int = 0
    sections: List[str] = Field(default_factory=list)
    contact_name: Optional[str] = None
    generated_with_context: List[str] = Field(default_factory=list)


class CommercialAnalysisMetadata(BaseModel):
    """Metadata for commercial analysis action"""
    deal_probability: Optional[int] = None  # 0-100
    recommended_stage: Optional[str] = None
    buying_signals_count: int = 0
    risk_level: Literal["low", "medium", "high"] = "medium"
    cross_sell_opportunities: List[str] = Field(default_factory=list)


class SalesCoachingMetadata(BaseModel):
    """Metadata for sales coaching action"""
    overall_score: Optional[float] = None  # 1-10
    strengths_count: int = 0
    improvements_count: int = 0
    techniques_suggested: List[str] = Field(default_factory=list)


class ActionItemsMetadata(BaseModel):
    """Metadata for action items action"""
    total_items: int = 0
    your_items: int = 0
    client_items: int = 0
    shared_items: int = 0
    high_priority_count: int = 0


class DealUpdateMetadata(BaseModel):
    """Metadata for deal update action"""
    current_stage: Optional[str] = None
    recommended_stage: Optional[str] = None
    probability_change: Optional[int] = None
    key_blocker: Optional[str] = None

