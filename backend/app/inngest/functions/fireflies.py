"""
Fireflies Sync Inngest Functions.

Handles automated Fireflies recording synchronization.

Functions:
- sync_all_fireflies: Cron job to sync all active Fireflies connections (every 5 minutes)
- sync_fireflies_user: Event-triggered sync for a specific user
"""

import logging
from datetime import datetime
import inngest
from inngest import TriggerEvent, TriggerCron

from app.inngest.client import inngest_client
from app.database import get_supabase_service
from app.services.fireflies_service import FirefliesService, sync_fireflies_recordings

logger = logging.getLogger(__name__)

# Database client
supabase = get_supabase_service()


@inngest_client.create_function(
    fn_id="sync-all-fireflies",
    trigger=TriggerCron(cron="*/5 * * * *"),  # Every 5 minutes
    retries=1,
)
async def sync_all_fireflies_fn(ctx, step):
    """
    Scheduled job to sync all active Fireflies connections.
    
    Runs every 5 minutes to keep recordings data fresh.
    """
    logger.info("Starting scheduled Fireflies sync for all connections")
    
    # Step 1: Get all active Fireflies integrations
    integrations = await step.run("get-active-integrations", get_active_fireflies_integrations)
    
    if not integrations:
        logger.info("No active Fireflies integrations to sync")
        return {"synced": 0, "message": "No integrations to sync"}
    
    logger.info(f"Found {len(integrations)} active Fireflies integrations to sync")
    
    # Step 2: Sync each integration
    results = []
    for integration in integrations:
        try:
            result = await step.run(
                f"sync-fireflies-{integration['id'][:8]}",
                sync_fireflies_integration,
                integration
            )
            results.append({
                "integration_id": integration["id"],
                "user_id": integration["user_id"],
                "success": True,
                **result
            })
        except Exception as e:
            logger.error(f"Failed to sync Fireflies for user {integration['user_id']}: {e}")
            results.append({
                "integration_id": integration["id"],
                "user_id": integration["user_id"],
                "success": False,
                "error": str(e)
            })
    
    # Summary
    successful = sum(1 for r in results if r["success"])
    logger.info(f"Fireflies sync complete: {successful}/{len(results)} successful")
    
    return {
        "synced": len(results),
        "successful": successful,
        "results": results
    }


@inngest_client.create_function(
    fn_id="sync-fireflies-user",
    trigger=TriggerEvent(event="dealmotion/fireflies.sync.requested"),
    retries=2,
)
async def sync_fireflies_user_fn(ctx, step):
    """
    Sync Fireflies recordings for a specific user.
    
    Triggered when:
    - A new Fireflies connection is created
    - User manually requests a sync
    """
    event_data = ctx.event.data
    user_id = event_data["user_id"]
    days_back = event_data.get("days_back", 30)
    
    logger.info(f"Syncing Fireflies for user {user_id}")
    
    # Step 1: Get integration for user
    integration = await step.run("get-integration", get_user_fireflies_integration, user_id)
    
    if not integration:
        logger.error(f"No Fireflies integration found for user {user_id}")
        return {"success": False, "error": "Integration not found"}
    
    # Step 2: Perform sync
    result = await step.run("sync-fireflies", sync_fireflies_integration_with_days, integration, days_back)
    
    return {
        "success": True,
        "user_id": user_id,
        **result
    }


# =============================================================================
# Step Functions
# =============================================================================

def get_active_fireflies_integrations() -> list:
    """Get all active Fireflies integrations that need syncing."""
    try:
        result = supabase.table("recording_integrations").select(
            "id, user_id, organization_id, credentials, auto_import, last_sync_at"
        ).eq(
            "provider", "fireflies"
        ).eq(
            "auto_import", True
        ).execute()
        
        return result.data or []
    except Exception as e:
        logger.error(f"Failed to get active Fireflies integrations: {e}")
        return []


def get_user_fireflies_integration(user_id: str) -> dict:
    """Get Fireflies integration for a specific user."""
    try:
        result = supabase.table("recording_integrations").select("*").eq(
            "user_id", user_id
        ).eq(
            "provider", "fireflies"
        ).execute()
        
        if result.data and len(result.data) > 0:
            return result.data[0]
        return None
    except Exception as e:
        logger.error(f"Failed to get Fireflies integration for user {user_id}: {e}")
        return None


async def sync_fireflies_integration(integration: dict) -> dict:
    """Sync a Fireflies integration (default 7 days for scheduled sync)."""
    return await sync_fireflies_integration_with_days(integration, days_back=7)


async def sync_fireflies_integration_with_days(integration: dict, days_back: int = 7) -> dict:
    """Sync a Fireflies integration with specified days back."""
    try:
        user_id = integration["user_id"]
        org_id = integration["organization_id"]
        integration_id = integration["id"]
        
        # Create service from integration
        service = FirefliesService.from_integration(integration)
        if not service:
            logger.error(f"Invalid Fireflies credentials for integration {integration_id}")
            return {"error": "Invalid credentials"}
        
        # Run sync (already async)
        stats = await sync_fireflies_recordings(
            user_id=user_id,
            org_id=org_id,
            integration_id=integration_id,
            service=service,
            days_back=days_back
        )
        
        return {
            "new_recordings": stats.get("new", 0),
            "updated_recordings": stats.get("updated", 0),
            "skipped_recordings": stats.get("skipped", 0),
            "errors": stats.get("error", 0)
        }
        
    except Exception as e:
        logger.error(f"Fireflies sync failed: {e}")
        raise

