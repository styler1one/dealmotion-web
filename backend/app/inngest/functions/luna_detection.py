"""
Luna Detection Inngest Functions.
SPEC-046-Luna-Unified-AI-Assistant

Functions for detecting opportunities and creating Luna messages:
- luna_detect_periodic_fn: Cron every 15 minutes
- luna_detect_for_user_fn: Event-driven for specific user
- luna_expire_messages_fn: Cron every 5 minutes
"""

import logging
from datetime import datetime, timedelta
import inngest
from inngest import TriggerEvent, TriggerCron

from app.inngest.client import inngest_client
from app.database import get_supabase_service

logger = logging.getLogger(__name__)


# =============================================================================
# PERIODIC DETECTION (Cron)
# =============================================================================

@inngest_client.create_function(
    fn_id="luna-detect-periodic",
    trigger=TriggerCron(cron="*/15 * * * *"),  # Every 15 minutes
    retries=1,
)
async def luna_detect_periodic_fn(ctx, step):
    """
    Periodic detection for all active users.
    Creates Luna messages based on user context.
    
    Runs in shadow mode by default (creates messages but UI doesn't show).
    """
    from app.services.luna_detection import LunaDetectionEngine
    from app.services.luna_service import LunaService
    
    supabase = get_supabase_service()
    
    logger.info("Running periodic Luna detection")
    
    # Step 1: Check if shadow mode is enabled
    async def check_shadow_mode():
        result = supabase.table("luna_feature_flags") \
            .select("flag_value") \
            .eq("flag_name", "luna_shadow_mode") \
            .limit(1) \
            .execute()
        return result.data[0]["flag_value"] if result.data else True
    
    shadow_mode = await step.run("check-shadow-mode", check_shadow_mode)
    
    # Step 2: Get active users (recently active or with pending messages)
    async def get_active_users():
        # Get users who have been active in the last 24 hours
        cutoff = (datetime.utcnow() - timedelta(hours=24)).isoformat()
        
        # Get distinct users from recent activities
        result = supabase.table("organization_members") \
            .select("user_id, organization_id") \
            .execute()
        
        users = []
        for row in (result.data or []):
            # Check if user has Luna enabled
            settings_check = supabase.table("luna_settings") \
                .select("enabled") \
                .eq("user_id", row["user_id"]) \
                .limit(1) \
                .execute()
            
            if settings_check.data and not settings_check.data[0].get("enabled", True):
                continue
            
            users.append({
                "user_id": row["user_id"],
                "organization_id": row["organization_id"]
            })
        
        return users[:50]  # Limit to 50 users per run
    
    users = await step.run("get-active-users", get_active_users)
    
    if not users:
        logger.info("No active users for Luna detection")
        return {"processed": 0, "messages_created": 0}
    
    logger.info(f"Running Luna detection for {len(users)} users")
    
    # Step 3: Run detection for each user
    async def run_detection():
        engine = LunaDetectionEngine()
        service = LunaService()
        
        total_created = 0
        errors = 0
        
        for user in users:
            try:
                user_id = user["user_id"]
                org_id = user["organization_id"]
                
                # Run detection
                messages = await engine.detect_for_user(user_id, org_id)
                
                # Create messages
                for msg in messages:
                    result = await service.create_message(msg)
                    if result:
                        total_created += 1
                        logger.debug(f"Created Luna message: {msg.message_type} for user {user_id[:8]}")
                
            except Exception as e:
                logger.error(f"Error detecting for user {user.get('user_id', 'unknown')}: {e}")
                errors += 1
        
        return {"created": total_created, "errors": errors}
    
    result = await step.run("run-detection", run_detection)
    
    logger.info(
        f"Luna detection complete: {len(users)} users, "
        f"{result['created']} messages created, {result['errors']} errors"
    )
    
    return {
        "shadow_mode": shadow_mode,
        "processed": len(users),
        "messages_created": result["created"],
        "errors": result["errors"]
    }


# =============================================================================
# USER-SPECIFIC DETECTION (Event)
# =============================================================================

@inngest_client.create_function(
    fn_id="luna-detect-for-user",
    trigger=TriggerEvent(event="dealmotion/luna.detect.user"),
    retries=1,
)
async def luna_detect_for_user_fn(ctx, step):
    """
    Run Luna detection for a specific user.
    
    Triggered by:
    - Calendar sync completion
    - Research completion
    - Followup completion
    - Manual trigger
    """
    from app.services.luna_detection import LunaDetectionEngine
    from app.services.luna_service import LunaService
    
    event_data = ctx.event.data
    user_id = event_data.get("user_id")
    organization_id = event_data.get("organization_id")
    trigger_source = event_data.get("trigger_source", "manual")
    
    if not user_id or not organization_id:
        logger.warning("Missing user_id or organization_id in Luna detect event")
        return {"created": 0, "error": "Missing required data"}
    
    logger.info(f"Running Luna detection for user {user_id[:8]} (trigger: {trigger_source})")
    
    # Step 1: Run detection
    async def detect_messages():
        engine = LunaDetectionEngine()
        return await engine.detect_for_user(user_id, organization_id)
    
    messages = await step.run("detect-messages", detect_messages)
    
    if not messages:
        logger.info(f"No new messages detected for user {user_id[:8]}")
        return {"created": 0}
    
    # Step 2: Create messages
    async def create_messages():
        service = LunaService()
        created = 0
        
        for msg in messages:
            result = await service.create_message(msg)
            if result:
                created += 1
        
        return created
    
    created_count = await step.run("create-messages", create_messages)
    
    logger.info(f"Created {created_count} Luna messages for user {user_id[:8]}")
    
    return {
        "user_id": user_id,
        "trigger_source": trigger_source,
        "detected": len(messages),
        "created": created_count
    }


# =============================================================================
# MESSAGE EXPIRATION (Cron)
# =============================================================================

@inngest_client.create_function(
    fn_id="luna-expire-messages",
    trigger=TriggerCron(cron="*/5 * * * *"),  # Every 5 minutes
    retries=1,
)
async def luna_expire_messages_fn(ctx, step):
    """
    Expire Luna messages that have passed their expires_at.
    """
    supabase = get_supabase_service()
    
    logger.info("Checking for expired Luna messages")
    
    async def expire_messages():
        now = datetime.utcnow().isoformat()
        
        # Find and expire pending messages past their expires_at
        result = supabase.table("luna_messages") \
            .update({
                "status": "expired",
                "updated_at": now
            }) \
            .eq("status", "pending") \
            .lt("expires_at", now) \
            .execute()
        
        expired_count = len(result.data or [])
        
        # Also record feedback for analytics
        if expired_count > 0:
            for row in (result.data or []):
                try:
                    supabase.table("luna_feedback").insert({
                        "user_id": row["user_id"],
                        "organization_id": row["organization_id"],
                        "message_id": row["id"],
                        "feedback_type": "expired",
                        "message_type": row["message_type"],
                        "created_at": now
                    }).execute()
                except Exception as e:
                    logger.warning(f"Error recording expired feedback: {e}")
        
        return expired_count
    
    expired_count = await step.run("expire-messages", expire_messages)
    
    if expired_count > 0:
        logger.info(f"Expired {expired_count} Luna messages")
    
    return {"expired": expired_count}


# =============================================================================
# UN-SNOOZE MESSAGES (Cron)
# =============================================================================

@inngest_client.create_function(
    fn_id="luna-unsnooze-messages",
    trigger=TriggerCron(cron="*/5 * * * *"),  # Every 5 minutes
    retries=1,
)
async def luna_unsnooze_messages_fn(ctx, step):
    """
    Un-snooze Luna messages whose snooze_until has passed.
    """
    supabase = get_supabase_service()
    
    logger.info("Checking for messages to un-snooze")
    
    async def unsnooze_messages():
        now = datetime.utcnow().isoformat()
        
        result = supabase.table("luna_messages") \
            .update({
                "status": "pending",
                "snooze_until": None,
                "updated_at": now
            }) \
            .eq("status", "snoozed") \
            .lt("snooze_until", now) \
            .execute()
        
        return len(result.data or [])
    
    unsnoozed_count = await step.run("unsnooze-messages", unsnooze_messages)
    
    if unsnoozed_count > 0:
        logger.info(f"Un-snoozed {unsnoozed_count} Luna messages")
    
    return {"unsnoozed": unsnoozed_count}
