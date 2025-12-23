"""
GDPR Inngest Functions.

Handles asynchronous GDPR operations:
- Account deletion after grace period
- Data export generation
- Expired exports cleanup
- Scheduled deletions processing
"""

import logging
from datetime import datetime, timedelta
import inngest
from inngest import TriggerEvent, TriggerCron

from app.inngest.client import inngest_client
from app.inngest.events import (
    GDPR_EXECUTE_DELETION,
    GDPR_GENERATE_EXPORT,
    GDPR_CLEANUP_EXPIRED_EXPORTS,
    GDPR_PROCESS_SCHEDULED_DELETIONS,
)
from app.services.gdpr_service import GDPRService

logger = logging.getLogger(__name__)


@inngest_client.create_function(
    fn_id="gdpr-execute-deletion",
    trigger=TriggerEvent(event=GDPR_EXECUTE_DELETION),
    retries=2,
)
async def execute_deletion_fn(ctx, step):
    """
    Execute account deletion after grace period.
    
    This function is triggered when a deletion is requested and waits
    until the scheduled time before executing the actual deletion.
    """
    event_data = ctx.event.data
    deletion_request_id = event_data.get("deletion_request_id")
    user_id = event_data.get("user_id")
    scheduled_for = event_data.get("scheduled_for")
    
    logger.info(f"[GDPR] Deletion execution triggered for user {user_id}, request {deletion_request_id}")
    
    if not deletion_request_id:
        logger.error("[GDPR] Missing deletion_request_id")
        return {"success": False, "error": "Missing deletion_request_id"}
    
    # Wait until scheduled time (48 hours from request)
    if scheduled_for:
        scheduled_datetime = datetime.fromisoformat(scheduled_for.replace("Z", "+00:00"))
        wait_until = scheduled_datetime
        
        # If scheduled time is in the future, wait
        if wait_until > datetime.now(wait_until.tzinfo):
            logger.info(f"[GDPR] Waiting until {wait_until} before executing deletion")
            
            await step.sleep_until(
                "wait-for-grace-period",
                wait_until
            )
    
    # Check if deletion was cancelled during grace period
    async def check_deletion_status():
        from app.database import get_supabase_service
        supabase = get_supabase_service()
        
        result = supabase.table("gdpr_deletion_requests").select("status").eq(
            "id", deletion_request_id
        ).single().execute()
        
        if not result.data:
            return None
        return result.data.get("status")
    
    status = await step.run("check-deletion-status", check_deletion_status)
    
    if status != "pending":
        logger.info(f"[GDPR] Deletion {deletion_request_id} is no longer pending (status: {status}), skipping")
        return {"success": False, "reason": "Deletion cancelled or already processed"}
    
    # Execute the deletion
    async def perform_deletion():
        service = GDPRService()
        result = await service.execute_deletion(deletion_request_id)
        return {
            "success": result.success,
            "tables_cleaned": result.tables_cleaned,
            "storage_deleted": result.storage_deleted,
            "vectors_deleted": result.vectors_deleted,
            "billing_records_anonymized": result.billing_records_anonymized,
            "auth_user_deleted": result.auth_user_deleted,
            "errors": result.errors,
        }
    
    result = await step.run("execute-deletion", perform_deletion)
    
    if result.get("success"):
        logger.info(f"[GDPR] Successfully deleted user {user_id}")
    else:
        logger.error(f"[GDPR] Failed to delete user {user_id}: {result.get('errors')}")
    
    return result


@inngest_client.create_function(
    fn_id="gdpr-generate-export",
    trigger=TriggerEvent(event=GDPR_GENERATE_EXPORT),
    retries=2,
)
async def generate_export_fn(ctx, step):
    """
    Generate data export for user.
    
    Creates a ZIP file with all user data in JSON format.
    """
    event_data = ctx.event.data
    export_id = event_data.get("export_id")
    user_id = event_data.get("user_id")
    
    logger.info(f"[GDPR] Export generation triggered for user {user_id}, export {export_id}")
    
    if not export_id:
        logger.error("[GDPR] Missing export_id")
        return {"success": False, "error": "Missing export_id"}
    
    async def generate_export():
        service = GDPRService()
        success = await service.generate_export(export_id)
        return {"success": success}
    
    result = await step.run("generate-export", generate_export)
    
    if result.get("success"):
        logger.info(f"[GDPR] Successfully generated export {export_id} for user {user_id}")
    else:
        logger.error(f"[GDPR] Failed to generate export {export_id} for user {user_id}")
    
    return result


@inngest_client.create_function(
    fn_id="gdpr-cleanup-expired-exports",
    trigger=TriggerCron(cron="0 3 * * *"),  # Daily at 3 AM
    retries=1,
)
async def cleanup_expired_exports_fn(ctx, step):
    """
    Cleanup expired data exports.
    
    Runs daily to delete expired export files from storage.
    """
    logger.info("[GDPR] Running expired exports cleanup")
    
    async def cleanup_exports():
        from app.database import get_supabase_service
        supabase = get_supabase_service()
        
        # Find expired exports
        now = datetime.utcnow().isoformat()
        result = supabase.table("gdpr_data_exports").select("id, storage_path").eq(
            "status", "ready"
        ).lt("expires_at", now).execute()
        
        if not result.data:
            return {"cleaned": 0}
        
        cleaned = 0
        for export in result.data:
            try:
                # Delete from storage
                if export.get("storage_path"):
                    supabase.storage.from_("gdpr-exports").remove([export["storage_path"]])
                
                # Update status
                supabase.table("gdpr_data_exports").update({
                    "status": "expired",
                    "download_url": None,
                }).eq("id", export["id"]).execute()
                
                cleaned += 1
            except Exception as e:
                logger.error(f"[GDPR] Failed to cleanup export {export['id']}: {e}")
        
        return {"cleaned": cleaned}
    
    result = await step.run("cleanup-exports", cleanup_exports)
    
    logger.info(f"[GDPR] Cleaned up {result.get('cleaned', 0)} expired exports")
    return result


@inngest_client.create_function(
    fn_id="gdpr-process-scheduled-deletions",
    trigger=TriggerCron(cron="*/15 * * * *"),  # Every 15 minutes
    retries=1,
)
async def process_scheduled_deletions_fn(ctx, step):
    """
    Process scheduled deletions that are due.
    
    This is a backup mechanism in case the event-driven deletion fails.
    Runs every 15 minutes to find and process any pending deletions.
    """
    logger.info("[GDPR] Checking for scheduled deletions")
    
    async def find_due_deletions():
        from app.database import get_supabase_service
        supabase = get_supabase_service()
        
        now = datetime.utcnow().isoformat()
        result = supabase.table("gdpr_deletion_requests").select("id, user_id").eq(
            "status", "pending"
        ).lt("scheduled_for", now).execute()
        
        return result.data or []
    
    due_deletions = await step.run("find-due-deletions", find_due_deletions)
    
    if not due_deletions:
        logger.info("[GDPR] No pending deletions due")
        return {"processed": 0}
    
    logger.info(f"[GDPR] Found {len(due_deletions)} pending deletions to process")
    
    processed = 0
    for deletion in due_deletions:
        async def process_deletion():
            service = GDPRService()
            result = await service.execute_deletion(deletion["id"])
            return result.success
        
        try:
            success = await step.run(f"process-deletion-{deletion['id']}", process_deletion)
            if success:
                processed += 1
        except Exception as e:
            logger.error(f"[GDPR] Failed to process deletion {deletion['id']}: {e}")
    
    logger.info(f"[GDPR] Processed {processed} deletions")
    return {"processed": processed, "total": len(due_deletions)}

