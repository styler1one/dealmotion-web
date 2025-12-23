"""
GDPR Compliance Models

Pydantic models for GDPR-related API requests and responses.
Implements:
- Account deletion (Art. 17 Right to Erasure)
- Data export (Art. 15/20 Right of Access/Portability)
- Data summary (Art. 15 Right of Access)
"""

from pydantic import BaseModel, Field
from typing import Optional, List, Dict, Any
from datetime import datetime
from enum import Enum


class DeletionStatus(str, Enum):
    """Status of a deletion request."""
    ACTIVE = "active"
    PENDING_DELETION = "pending_deletion"
    DELETED = "deleted"
    ANONYMIZED = "anonymized"


class DeletionRequestStatus(str, Enum):
    """Status of the deletion request process."""
    PENDING = "pending"
    PROCESSING = "processing"
    COMPLETED = "completed"
    CANCELLED = "cancelled"
    FAILED = "failed"


class ExportStatus(str, Enum):
    """Status of a data export request."""
    PENDING = "pending"
    PROCESSING = "processing"
    READY = "ready"
    DOWNLOADED = "downloaded"
    EXPIRED = "expired"
    FAILED = "failed"


# ============================================================
# DELETION REQUESTS
# ============================================================

class DeleteAccountRequest(BaseModel):
    """Request to delete user account."""
    reason: Optional[str] = Field(None, max_length=500, description="Optional reason for deletion")
    confirm: bool = Field(..., description="Must be True to confirm deletion")


class DeleteAccountResponse(BaseModel):
    """Response after initiating account deletion."""
    success: bool
    message: str
    deletion_request_id: str
    scheduled_for: datetime
    can_cancel_until: datetime
    grace_period_hours: int = 48


class CancelDeletionRequest(BaseModel):
    """Request to cancel a pending deletion."""
    reason: Optional[str] = Field(None, max_length=500)


class CancelDeletionResponse(BaseModel):
    """Response after cancelling deletion."""
    success: bool
    message: str


class DeletionStatusResponse(BaseModel):
    """Current deletion status for user."""
    has_pending_deletion: bool
    deletion_request_id: Optional[str] = None
    status: Optional[DeletionRequestStatus] = None
    scheduled_for: Optional[datetime] = None
    can_cancel: bool = False
    requested_at: Optional[datetime] = None
    reason: Optional[str] = None


class DeletionCheckResponse(BaseModel):
    """Check if user can delete their account."""
    can_delete: bool
    reason: Optional[str] = None
    has_active_subscription: bool = False
    subscription_end_date: Optional[datetime] = None


# ============================================================
# DATA EXPORT
# ============================================================

class RequestExportRequest(BaseModel):
    """Request to export user data."""
    # No additional fields needed - exports all user data
    pass


class RequestExportResponse(BaseModel):
    """Response after requesting data export."""
    success: bool
    message: str
    export_id: str
    estimated_completion: datetime


class ExportStatusResponse(BaseModel):
    """Status of a data export request."""
    export_id: str
    status: ExportStatus
    requested_at: datetime
    completed_at: Optional[datetime] = None
    download_url: Optional[str] = None
    download_expires_at: Optional[datetime] = None
    expires_at: Optional[datetime] = None  # When the export will be auto-deleted
    file_size_bytes: Optional[int] = None
    download_count: int = 0
    error_message: Optional[str] = None


class ExportListResponse(BaseModel):
    """List of user's export requests."""
    exports: List[ExportStatusResponse]
    total: int


# ============================================================
# DATA SUMMARY
# ============================================================

class DataCategorySummary(BaseModel):
    """Summary of data in a category."""
    category: str
    description: str
    count: int
    last_updated: Optional[datetime] = None


class StorageUsageSummary(BaseModel):
    """Storage usage summary."""
    bucket: str
    file_count: int
    total_size_bytes: int


class DataSummaryResponse(BaseModel):
    """Summary of all stored user data."""
    user_id: str
    email: str
    account_created_at: datetime
    
    # Profile data
    has_sales_profile: bool
    has_company_profile: bool
    
    # Content data
    data_categories: List[DataCategorySummary]
    
    # Storage
    storage_usage: List[StorageUsageSummary]
    total_storage_bytes: int
    
    # External connections
    connected_calendars: List[str]
    connected_integrations: List[str]
    
    # Subscription
    subscription_plan: str
    subscription_status: str
    
    # Generated at
    generated_at: datetime


# ============================================================
# INTERNAL MODELS (for service layer)
# ============================================================

class DeletionTask(BaseModel):
    """Internal model for deletion task processing."""
    deletion_request_id: str
    user_id: str
    organization_id: str
    user_email: str
    tables_to_clean: List[str]
    storage_buckets: List[str]
    vector_namespaces: List[str]


class DeletionResult(BaseModel):
    """Result of deletion operation."""
    success: bool
    tables_cleaned: List[str]
    storage_deleted: List[str]
    vectors_deleted: List[str]
    billing_records_anonymized: int
    auth_user_deleted: bool
    errors: List[str]


class ExportData(BaseModel):
    """Structure of exported user data."""
    export_version: str = "1.0"
    exported_at: datetime
    user_id: str
    
    profile: Optional[Dict[str, Any]] = None
    account: Optional[Dict[str, Any]] = None
    company: Optional[Dict[str, Any]] = None
    
    content: Optional[Dict[str, Any]] = None
    activity: Optional[Dict[str, Any]] = None
    
    metadata: Dict[str, Any] = Field(default_factory=dict)

