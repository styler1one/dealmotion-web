"""
GDPR Router

API endpoints for GDPR compliance:
- Account deletion (Art. 17 Right to Erasure)
- Data export (Art. 15/20 Right of Access/Portability)
- Data summary (Art. 15 Right of Access)

All endpoints require authentication and only allow users to manage their own data.
"""

from fastapi import APIRouter, Depends, HTTPException, status, Request, BackgroundTasks
from typing import Optional
from datetime import datetime
import logging

from app.deps import get_current_user
from app.database import get_supabase_service
from app.services.gdpr_service import GDPRService
from app.models.gdpr import (
    DeleteAccountRequest,
    DeleteAccountResponse,
    CancelDeletionRequest,
    CancelDeletionResponse,
    DeletionStatusResponse,
    DeletionCheckResponse,
    RequestExportRequest,
    RequestExportResponse,
    ExportStatusResponse,
    ExportListResponse,
    DataSummaryResponse,
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/user", tags=["gdpr"])


def get_gdpr_service() -> GDPRService:
    """Dependency to get GDPR service."""
    return GDPRService()


def get_client_info(request: Request) -> tuple:
    """Extract client IP and user agent from request."""
    ip_address = request.client.host if request.client else None
    user_agent = request.headers.get("user-agent")
    return ip_address, user_agent


# ============================================================
# DELETION ENDPOINTS
# ============================================================

@router.get("/delete/check", response_model=DeletionCheckResponse)
async def check_can_delete(
    current_user: dict = Depends(get_current_user),
    service: GDPRService = Depends(get_gdpr_service),
):
    """
    Check if user can delete their account.
    
    Returns whether deletion is possible and any blockers (e.g., active subscription).
    """
    user_id = current_user.get("sub")
    
    can_delete, reason, sub_end_date = await service.can_delete_account(user_id)
    
    return DeletionCheckResponse(
        can_delete=can_delete,
        reason=reason,
        has_active_subscription=reason is not None and "subscription" in reason.lower() if reason else False,
        subscription_end_date=sub_end_date,
    )


@router.get("/delete/status", response_model=DeletionStatusResponse)
async def get_deletion_status(
    current_user: dict = Depends(get_current_user),
    service: GDPRService = Depends(get_gdpr_service),
):
    """
    Get current deletion status for user.
    
    Returns whether there's a pending deletion and when it will occur.
    """
    user_id = current_user.get("sub")
    
    status = await service.get_deletion_status(user_id)
    
    return DeletionStatusResponse(**status)


@router.post("/delete", response_model=DeleteAccountResponse)
async def delete_account(
    request_body: DeleteAccountRequest,
    request: Request,
    background_tasks: BackgroundTasks,
    current_user: dict = Depends(get_current_user),
    service: GDPRService = Depends(get_gdpr_service),
):
    """
    Request account deletion.
    
    Initiates account deletion with a 48-hour grace period.
    During this time, the user can cancel the deletion.
    After 48 hours, the account and all associated data will be permanently deleted.
    
    Billing data is anonymized and retained for 7 years for legal compliance.
    """
    if not request_body.confirm:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Deletion must be explicitly confirmed"
        )
    
    user_id = current_user.get("sub")
    user_email = current_user.get("email", "")
    ip_address, user_agent = get_client_info(request)
    
    result = await service.request_deletion(
        user_id=user_id,
        user_email=user_email,
        reason=request_body.reason,
        ip_address=ip_address,
        user_agent=user_agent,
    )
    
    if not result.get("success"):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=result.get("message", "Failed to schedule deletion")
        )
    
    # Trigger Inngest to process deletion after grace period
    try:
        from app.inngest.events import send_event, GDPR_EXECUTE_DELETION
        
        logger.info(f"[GDPR] Sending deletion event for user {user_id}, request_id: {result['deletion_request_id']}")
        
        event_sent = await send_event(
            GDPR_EXECUTE_DELETION,
            {
                "deletion_request_id": result["deletion_request_id"],
                "user_id": user_id,
                "scheduled_for": result["scheduled_for"].isoformat(),
            },
        )
        
        if event_sent:
            logger.info(f"[GDPR] Deletion event sent successfully for user {user_id}")
        else:
            logger.warning(f"[GDPR] Deletion event not sent for user {user_id} - Inngest may be disabled")
    except Exception as e:
        logger.error(f"[GDPR] Failed to trigger deletion job: {e}", exc_info=True)
        # Don't fail the request - the scheduled job will still run
    
    logger.info(f"Account deletion requested for user {user_id}")
    
    return DeleteAccountResponse(
        success=True,
        message="Account deletion scheduled. You can cancel within 48 hours.",
        deletion_request_id=result["deletion_request_id"],
        scheduled_for=result["scheduled_for"],
        can_cancel_until=result["can_cancel_until"],
        grace_period_hours=result["grace_period_hours"],
    )


@router.post("/delete/cancel", response_model=CancelDeletionResponse)
async def cancel_deletion(
    request_body: CancelDeletionRequest,
    current_user: dict = Depends(get_current_user),
    service: GDPRService = Depends(get_gdpr_service),
):
    """
    Cancel a pending account deletion.
    
    Can only be done during the 48-hour grace period.
    """
    user_id = current_user.get("sub")
    
    result = await service.cancel_deletion(
        user_id=user_id,
        reason=request_body.reason,
    )
    
    if not result.get("success"):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=result.get("message", "Failed to cancel deletion")
        )
    
    logger.info(f"Account deletion cancelled for user {user_id}")
    
    return CancelDeletionResponse(
        success=True,
        message="Account deletion cancelled successfully"
    )


# ============================================================
# EXPORT ENDPOINTS
# ============================================================

@router.post("/export", response_model=RequestExportResponse)
async def request_data_export(
    request: Request,
    current_user: dict = Depends(get_current_user),
    service: GDPRService = Depends(get_gdpr_service),
):
    """
    Request a data export.
    
    Creates a downloadable ZIP file containing all user data in JSON format.
    The export will be available for 7 days after generation.
    """
    user_id = current_user.get("sub")
    ip_address, user_agent = get_client_info(request)
    
    # Get organization ID
    supabase = get_supabase_service()
    org_result = supabase.table("organization_members").select(
        "organization_id"
    ).eq("user_id", user_id).limit(1).single().execute()
    
    if not org_result.data:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="User organization not found"
        )
    
    organization_id = org_result.data["organization_id"]
    
    result = await service.request_export(
        user_id=user_id,
        organization_id=organization_id,
        ip_address=ip_address,
        user_agent=user_agent,
    )
    
    if not result.get("success"):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=result.get("message", "Failed to request export")
        )
    
    # Trigger Inngest to generate export
    try:
        from app.inngest.events import send_event, GDPR_GENERATE_EXPORT
        
        logger.info(f"[GDPR] Sending export event for user {user_id}, export_id: {result['export_id']}")
        
        event_sent = await send_event(
            GDPR_GENERATE_EXPORT,
            {
                "export_id": result["export_id"],
                "user_id": user_id,
            },
        )
        
        if event_sent:
            logger.info(f"[GDPR] Export event sent successfully for user {user_id}")
        else:
            logger.warning(f"[GDPR] Export event not sent for user {user_id} - Inngest may be disabled")
    except Exception as e:
        logger.error(f"[GDPR] Failed to trigger export job: {e}", exc_info=True)
    
    logger.info(f"Data export requested for user {user_id}")
    
    return RequestExportResponse(
        success=True,
        message="Data export requested. You'll receive a download link shortly.",
        export_id=result["export_id"],
        estimated_completion=result["estimated_completion"],
    )


@router.get("/export/{export_id}", response_model=ExportStatusResponse)
async def get_export_status(
    export_id: str,
    current_user: dict = Depends(get_current_user),
    service: GDPRService = Depends(get_gdpr_service),
):
    """
    Get status of a specific data export.
    
    Returns the export status and download URL if ready.
    """
    user_id = current_user.get("sub")
    
    export = await service.get_export_status(user_id, export_id)
    
    if not export:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Export not found"
        )
    
    return ExportStatusResponse(
        export_id=export["id"],
        status=export["status"],
        requested_at=export["requested_at"],
        completed_at=export.get("completed_at"),
        download_url=export.get("download_url"),
        download_expires_at=export.get("download_expires_at"),
        file_size_bytes=export.get("file_size_bytes"),
        download_count=export.get("download_count", 0),
        error_message=export.get("error_message"),
    )


@router.get("/exports", response_model=ExportListResponse)
async def list_exports(
    current_user: dict = Depends(get_current_user),
    service: GDPRService = Depends(get_gdpr_service),
):
    """
    List all data exports for the user.
    
    Returns the last 10 export requests.
    """
    user_id = current_user.get("sub")
    
    exports = await service.list_exports(user_id)
    
    return ExportListResponse(
        exports=[
            ExportStatusResponse(
                export_id=e["id"],
                status=e["status"],
                requested_at=e["requested_at"],
                completed_at=e.get("completed_at"),
                download_url=e.get("download_url"),
                download_expires_at=e.get("download_expires_at"),
                expires_at=e.get("expires_at"),
                file_size_bytes=e.get("file_size_bytes"),
                download_count=e.get("download_count", 0),
                error_message=e.get("error_message"),
            )
            for e in exports
        ],
        total=len(exports),
    )


@router.post("/export/{export_id}/download")
async def record_export_download(
    export_id: str,
    current_user: dict = Depends(get_current_user),
    service: GDPRService = Depends(get_gdpr_service),
):
    """
    Record that an export was downloaded.
    
    Called when user clicks download link.
    """
    user_id = current_user.get("sub")
    
    await service.record_download(user_id, export_id)
    
    return {"success": True}


@router.post("/export/{export_id}/retry")
async def retry_export(
    export_id: str,
    request: Request,
    current_user: dict = Depends(get_current_user),
    service: GDPRService = Depends(get_gdpr_service),
):
    """
    Retry a stuck or failed export.
    
    Cancels the existing export and creates a new one.
    """
    user_id = current_user.get("sub")
    ip_address, user_agent = get_client_info(request)
    
    # Get organization ID
    supabase = get_supabase_service()
    org_result = supabase.table("organization_members").select(
        "organization_id"
    ).eq("user_id", user_id).limit(1).single().execute()
    
    if not org_result.data:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="User organization not found"
        )
    
    organization_id = org_result.data["organization_id"]
    
    # Mark the stuck export as failed (to allow retry)
    supabase.table("gdpr_data_exports").update({
        "status": "failed",
        "error_message": "Cancelled by user for retry",
    }).eq("id", export_id).eq("user_id", user_id).execute()
    
    logger.info(f"[GDPR] Marked stuck export {export_id} as failed for user {user_id}")
    
    # Create new export request
    result = await service.request_export(
        user_id=user_id,
        organization_id=organization_id,
        ip_address=ip_address,
        user_agent=user_agent,
    )
    
    if not result.get("success"):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=result.get("message", "Failed to request export")
        )
    
    # Trigger Inngest to generate export
    try:
        from app.inngest.events import send_event, GDPR_GENERATE_EXPORT
        
        logger.info(f"[GDPR] Sending export event for retry, user {user_id}, export_id: {result['export_id']}")
        
        event_sent = await send_event(
            GDPR_GENERATE_EXPORT,
            {
                "export_id": result["export_id"],
                "user_id": user_id,
            },
        )
        
        if event_sent:
            logger.info(f"[GDPR] Retry export event sent successfully for user {user_id}")
        else:
            logger.warning(f"[GDPR] Retry export event not sent for user {user_id} - Inngest may be disabled")
    except Exception as e:
        logger.error(f"[GDPR] Failed to trigger retry export job: {e}", exc_info=True)
    
    return {
        "success": True,
        "message": "Export retry initiated",
        "export_id": result["export_id"],
    }


@router.delete("/export/{export_id}")
async def cancel_export(
    export_id: str,
    current_user: dict = Depends(get_current_user),
):
    """
    Cancel a pending or processing export.
    """
    user_id = current_user.get("sub")
    
    supabase = get_supabase_service()
    
    # Only cancel if pending or processing - mark as failed since 'cancelled' is not a valid status
    result = supabase.table("gdpr_data_exports").update({
        "status": "failed",
        "error_message": "Cancelled by user",
    }).eq("id", export_id).eq("user_id", user_id).in_(
        "status", ["pending", "processing"]
    ).execute()
    
    if result.data and len(result.data) > 0:
        logger.info(f"[GDPR] Cancelled export {export_id} for user {user_id}")
        return {"success": True, "message": "Export cancelled"}
    
    return {"success": False, "message": "Export not found or already completed"}


# ============================================================
# DATA SUMMARY ENDPOINT
# ============================================================

@router.get("/data-summary", response_model=DataSummaryResponse)
async def get_data_summary(
    current_user: dict = Depends(get_current_user),
    service: GDPRService = Depends(get_gdpr_service),
):
    """
    Get summary of all stored user data.
    
    Returns a read-only overview of what data is stored about the user.
    This is useful for transparency and helps users understand their data footprint.
    """
    user_id = current_user.get("sub")
    user_email = current_user.get("email", "")
    
    # Get organization ID
    supabase = get_supabase_service()
    org_result = supabase.table("organization_members").select(
        "organization_id"
    ).eq("user_id", user_id).limit(1).single().execute()
    
    if not org_result.data:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="User organization not found"
        )
    
    organization_id = org_result.data["organization_id"]
    
    summary = await service.get_data_summary(
        user_id=user_id,
        user_email=user_email,
        organization_id=organization_id,
    )
    
    return summary

