"""
Calendar Sync Inngest Functions.

Handles automated calendar synchronization and cleanup.

Functions:
- sync_all_calendars: Cron job to sync all active calendar connections
- sync_single_calendar: Event-triggered sync for a specific connection
- cleanup_old_meetings: Daily job to remove old calendar meetings
"""

import logging
from datetime import datetime, timedelta
import inngest
from inngest import TriggerEvent, TriggerCron

from app.inngest.client import inngest_client
from app.database import get_supabase_service
from app.services.calendar_sync import CalendarSyncService
from app.services.auto_record_matcher import process_calendar_for_auto_record

logger = logging.getLogger(__name__)

# Database client
supabase = get_supabase_service()


@inngest_client.create_function(
    fn_id="sync-all-calendars",
    trigger=TriggerCron(cron="*/15 * * * *"),  # Every 15 minutes
    retries=1,
)
async def sync_all_calendars_fn(ctx, step):
    """
    Scheduled job to sync all active calendar connections.
    
    Runs every 15 minutes to keep calendar data fresh.
    """
    logger.info("Starting scheduled calendar sync for all connections")
    
    # Step 1: Get all active connections
    connections = await step.run("get-active-connections", get_active_connections)
    
    if not connections:
        logger.info("No active calendar connections to sync")
        return {"synced": 0, "message": "No connections to sync"}
    
    logger.info(f"Found {len(connections)} active connections to sync")
    
    # Step 2: Sync each connection
    results = []
    for conn in connections:
        try:
            result = await step.run(
                f"sync-connection-{conn['id'][:8]}",
                sync_connection,
                conn["id"]
            )
            results.append({
                "connection_id": conn["id"],
                "provider": conn["provider"],
                "user_id": conn.get("user_id"),
                "organization_id": conn.get("organization_id"),
                "success": True,
                **result
            })
        except Exception as e:
            logger.error(f"Failed to sync connection {conn['id']}: {e}")
            results.append({
                "connection_id": conn["id"],
                "provider": conn["provider"],
                "success": False,
                "error": str(e)
            })
    
    # Step 3: Post-process for each unique user (prospect matching + auto-record)
    # Group by user to avoid duplicate processing
    from app.inngest.functions.calendar_post_sync import run_prospect_matching
    
    processed_users = set()
    for r in results:
        if not r.get("success"):
            continue
        user_id = r.get("user_id")
        org_id = r.get("organization_id")
        if not user_id or not org_id:
            continue
        if user_id in processed_users:
            continue
        processed_users.add(user_id)
        
        try:
            # Run prospect matching
            match_result = await step.run(
                f"prospect-match-{user_id[:8]}",
                run_prospect_matching,
                user_id, org_id
            )
            logger.info(f"User {user_id[:8]}: {match_result.get('auto_linked', 0)} prospects auto-linked")
            
            # Run auto-record processing
            auto_result = await step.run(
                f"auto-record-{user_id[:8]}",
                process_calendar_for_auto_record,
                user_id, org_id
            )
            logger.info(f"User {user_id[:8]}: {auto_result.get('scheduled', 0)} recordings scheduled")
        except Exception as e:
            logger.error(f"Post-processing failed for user {user_id[:8]}: {e}")
    
    # Summary
    successful = sum(1 for r in results if r["success"])
    logger.info(f"Calendar sync complete: {successful}/{len(results)} successful, {len(processed_users)} users post-processed")
    
    return {
        "synced": len(results),
        "successful": successful,
        "users_processed": len(processed_users),
        "results": results
    }


@inngest_client.create_function(
    fn_id="sync-calendar-connection",
    trigger=TriggerEvent(event="dealmotion/calendar.sync.requested"),
    retries=2,
)
async def sync_calendar_connection_fn(ctx, step):
    """
    Sync a specific calendar connection.
    
    Triggered when:
    - A new calendar connection is created
    - User manually requests a sync
    - Calendar needs re-authentication
    """
    event_data = ctx.event.data
    connection_id = event_data["connection_id"]
    
    logger.info(f"Syncing calendar connection {connection_id}")
    
    # Step 1: Get connection details
    connection = await step.run("get-connection", get_connection, connection_id)
    
    if not connection:
        logger.error(f"Connection {connection_id} not found")
        return {"success": False, "error": "Connection not found"}
    
    if not connection.get("sync_enabled"):
        logger.info(f"Sync disabled for connection {connection_id}")
        return {"success": False, "error": "Sync disabled"}
    
    # Step 2: Perform sync
    result = await step.run("sync-connection", sync_connection, connection_id)
    
    # Step 3: Run ProspectMatcher to link meetings to prospects
    # This was missing before - prospect matching only happened on manual sync!
    user_id = connection.get("user_id")
    organization_id = connection.get("organization_id")
    
    if user_id and organization_id:
        # Import here to avoid circular imports
        from app.inngest.functions.calendar_post_sync import run_prospect_matching
        
        prospect_result = await step.run(
            "prospect-matching",
            run_prospect_matching,
            user_id, organization_id
        )
        logger.info(f"Prospect matching: {prospect_result.get('auto_linked', 0)} auto-linked")
        
        # Step 4: Process auto-record for this user's calendar (if enabled)
        auto_record_result = await step.run(
            "process-auto-record",
            process_calendar_for_auto_record,
            user_id, organization_id
        )
        logger.info(f"Auto-record processed: {auto_record_result.get('scheduled', 0)} scheduled")
    
    return {
        "success": True,
        "connection_id": connection_id,
        "provider": connection.get("provider"),
        **result
    }


# =============================================================================
# Step Functions
# =============================================================================

def get_active_connections() -> list:
    """Get all active calendar connections that need syncing."""
    try:
        result = supabase.table("calendar_connections").select(
            "id, provider, user_id, organization_id, last_sync_at"
        ).eq(
            "sync_enabled", True
        ).is_(
            "needs_reauth", False  # Skip connections that need re-authentication
        ).execute()
        
        return result.data or []
    except Exception as e:
        logger.error(f"Failed to get active connections: {e}")
        return []


def get_connection(connection_id: str) -> dict:
    """Get a specific calendar connection."""
    try:
        result = supabase.table("calendar_connections").select("*").eq(
            "id", connection_id
        ).execute()
        
        if result.data and len(result.data) > 0:
            return result.data[0]
        return None
    except Exception as e:
        logger.error(f"Failed to get connection {connection_id}: {e}")
        return None


def sync_connection(connection_id: str) -> dict:
    """Sync a calendar connection using the sync service."""
    try:
        sync_service = CalendarSyncService()
        result = sync_service.sync_connection(connection_id)
        
        return {
            "synced_meetings": result.synced_meetings,
            "new_meetings": result.new_meetings,
            "updated_meetings": result.updated_meetings,
            "deleted_meetings": result.deleted_meetings,
            "errors": result.errors if result.errors else []
        }
    except Exception as e:
        logger.error(f"Sync failed for connection {connection_id}: {e}")
        raise


# =============================================================================
# Cleanup Job
# =============================================================================

@inngest_client.create_function(
    fn_id="cleanup-old-meetings",
    trigger=TriggerCron(cron="0 3 * * *"),  # Daily at 3:00 AM UTC
    retries=1,
)
async def cleanup_old_meetings_fn(ctx, step):
    """
    Daily cleanup job to remove old calendar meetings.
    
    Removes meetings older than 30 days to keep the database clean.
    Related records (followups, external_recordings) are NOT deleted,
    but their calendar_meeting_id is set to NULL.
    """
    logger.info("Starting daily calendar meetings cleanup")
    
    # Step 1: Get count of old meetings
    stats = await step.run("get-old-meeting-stats", get_old_meeting_stats)
    
    if stats["count"] == 0:
        logger.info("No old meetings to clean up")
        return {"deleted": 0, "message": "No old meetings found"}
    
    logger.info(f"Found {stats['count']} meetings older than 30 days")
    
    # Step 2: Clear calendar_meeting_id in related followups
    cleared_followups = await step.run("clear-followup-links", clear_followup_calendar_links)
    
    # Step 3: Clear matched_meeting_id in external_recordings
    cleared_recordings = await step.run("clear-recording-links", clear_recording_meeting_links)
    
    # Step 4: Delete old meetings
    deleted = await step.run("delete-old-meetings", delete_old_meetings)
    
    logger.info(f"Cleanup complete: deleted {deleted} meetings, cleared {cleared_followups} followup links, {cleared_recordings} recording links")
    
    return {
        "deleted": deleted,
        "cleared_followup_links": cleared_followups,
        "cleared_recording_links": cleared_recordings
    }


def get_old_meeting_stats() -> dict:
    """Get count of meetings older than 30 days."""
    try:
        cutoff_date = (datetime.utcnow() - timedelta(days=30)).isoformat()
        
        result = supabase.table("calendar_meetings").select(
            "id", count="exact"
        ).lt("end_time", cutoff_date).execute()
        
        return {"count": result.count or 0, "cutoff_date": cutoff_date}
    except Exception as e:
        logger.error(f"Failed to get old meeting stats: {e}")
        return {"count": 0, "cutoff_date": None}


def clear_followup_calendar_links() -> int:
    """Set calendar_meeting_id to NULL for followups linked to old meetings."""
    try:
        cutoff_date = (datetime.utcnow() - timedelta(days=30)).isoformat()
        
        # Get IDs of old meetings
        old_meetings = supabase.table("calendar_meetings").select("id").lt(
            "end_time", cutoff_date
        ).execute()
        
        if not old_meetings.data:
            return 0
        
        old_meeting_ids = [m["id"] for m in old_meetings.data]
        
        # Update followups
        result = supabase.table("followups").update({
            "calendar_meeting_id": None
        }).in_("calendar_meeting_id", old_meeting_ids).execute()
        
        return len(result.data) if result.data else 0
    except Exception as e:
        logger.error(f"Failed to clear followup links: {e}")
        return 0


def clear_recording_meeting_links() -> int:
    """Set matched_meeting_id to NULL for external_recordings linked to old meetings."""
    try:
        cutoff_date = (datetime.utcnow() - timedelta(days=30)).isoformat()
        
        # Get IDs of old meetings
        old_meetings = supabase.table("calendar_meetings").select("id").lt(
            "end_time", cutoff_date
        ).execute()
        
        if not old_meetings.data:
            return 0
        
        old_meeting_ids = [m["id"] for m in old_meetings.data]
        
        # Update external_recordings
        result = supabase.table("external_recordings").update({
            "matched_meeting_id": None
        }).in_("matched_meeting_id", old_meeting_ids).execute()
        
        return len(result.data) if result.data else 0
    except Exception as e:
        logger.error(f"Failed to clear recording links: {e}")
        return 0


def delete_old_meetings() -> int:
    """Delete meetings older than 30 days."""
    try:
        cutoff_date = (datetime.utcnow() - timedelta(days=30)).isoformat()
        
        result = supabase.table("calendar_meetings").delete().lt(
            "end_time", cutoff_date
        ).execute()
        
        return len(result.data) if result.data else 0
    except Exception as e:
        logger.error(f"Failed to delete old meetings: {e}")
        return 0

