"""
Calendar Post-Sync Inngest Functions.

Handles post-processing after calendar sync completes:
1. ProspectMatcher - match meetings to prospects
2. Auto-Record Processing - schedule AI Notetaker bots

This ensures:
- Fast API response (sync doesn't wait for matching)
- Reliable retries on failure
- Proper ordering (matching completes before auto-record)
- Scalability for many users

Event: dealmotion/calendar.sync.completed
"""

import logging
from inngest import TriggerEvent

from app.inngest.client import inngest_client
from app.database import get_supabase_service

logger = logging.getLogger(__name__)


async def run_prospect_matching(user_id: str, organization_id: str) -> dict:
    """
    Run ProspectMatcher to link unlinked calendar meetings to prospects.
    
    Returns dict with match statistics.
    """
    from app.services.prospect_matcher import ProspectMatcher
    
    logger.info(f"[PROSPECT-MATCH] Starting for user {user_id[:8]}..., org {organization_id[:8]}...")
    
    supabase = get_supabase_service()
    
    # First, check how many unlinked meetings exist
    unlinked_check = supabase.table("calendar_meetings").select(
        "id, title"
    ).eq(
        "organization_id", organization_id
    ).is_(
        "prospect_id", "null"
    ).execute()
    
    unlinked_count = len(unlinked_check.data or [])
    logger.info(f"[PROSPECT-MATCH] Found {unlinked_count} unlinked meetings for org {organization_id[:8]}...")
    
    if unlinked_count > 0:
        for m in (unlinked_check.data or [])[:5]:  # Log first 5
            logger.debug(f"[PROSPECT-MATCH] Unlinked meeting: '{m.get('title')}'")
    
    # Also check how many contacts exist for matching
    contacts_check = supabase.table("prospect_contacts").select(
        "id"
    ).eq(
        "organization_id", organization_id
    ).execute()
    
    contacts_count = len(contacts_check.data or [])
    logger.info(f"[PROSPECT-MATCH] Organization has {contacts_count} contacts for matching")
    
    matcher = ProspectMatcher(supabase)
    
    results = await matcher.match_all_unlinked(organization_id)
    
    auto_linked = sum(1 for r in results if r.auto_linked)
    total_matched = sum(1 for r in results if r.best_match is not None)
    
    logger.info(
        f"[PROSPECT-MATCH] Completed for org {organization_id[:8]}...: "
        f"{auto_linked} auto-linked, {total_matched} total matches out of {len(results)} meetings"
    )
    
    return {
        "total_meetings": len(results),
        "auto_linked": auto_linked,
        "total_with_match": total_matched,
        "unlinked_before": unlinked_count,
        "contacts_available": contacts_count
    }


async def run_auto_record_processing(user_id: str, organization_id: str) -> dict:
    """
    Process calendar meetings for auto-recording.
    
    This checks user's auto-record settings and schedules AI Notetaker bots
    for qualifying meetings.
    
    Returns dict with scheduling statistics.
    """
    from app.services.auto_record_matcher import process_calendar_for_auto_record
    
    result = await process_calendar_for_auto_record(user_id, organization_id)
    
    logger.info(
        f"Auto-record processing completed for user {user_id[:8]}...: "
        f"{result.get('scheduled', 0)} scheduled, {result.get('skipped', 0)} skipped"
    )
    
    return result


@inngest_client.create_function(
    fn_id="calendar-post-sync",
    trigger=TriggerEvent(event="dealmotion/calendar.sync.completed"),
    retries=3,
)
async def process_calendar_post_sync_fn(ctx, step):
    """
    Process calendar after sync completes.
    
    Steps:
    1. Run ProspectMatcher to link meetings to prospects
    2. Run auto-record processing to schedule AI Notetaker bots
    
    The order is important: matching must complete BEFORE auto-record
    so that scheduled recordings have the prospect_id.
    """
    event_data = ctx.event.data
    user_id = event_data["user_id"]
    organization_id = event_data["organization_id"]
    new_meetings = event_data.get("new_meetings", 0)
    updated_meetings = event_data.get("updated_meetings", 0)
    
    logger.info(
        f"[POST-SYNC] Starting calendar post-sync for user {user_id[:8]}..., org {organization_id[:8]}... "
        f"(new={new_meetings}, updated={updated_meetings})"
    )
    
    # Step 1: Run ProspectMatcher (only if there are new/updated meetings)
    match_result = {"skipped": True}
    if new_meetings > 0 or updated_meetings > 0:
        logger.info(f"[POST-SYNC] Running ProspectMatcher (new={new_meetings}, updated={updated_meetings})")
        match_result = await step.run(
            "prospect-matching",
            run_prospect_matching,
            user_id, organization_id
        )
        logger.info(f"[POST-SYNC] ProspectMatcher result: {match_result}")
    else:
        logger.warning(f"[POST-SYNC] Skipping ProspectMatcher - no new/updated meetings (new={new_meetings}, updated={updated_meetings})")
    
    # Step 2: Run auto-record processing (always, to catch any eligible meetings)
    auto_record_result = await step.run(
        "auto-record-processing",
        run_auto_record_processing,
        user_id, organization_id
    )
    
    return {
        "user_id": user_id,
        "prospect_matching": match_result,
        "auto_record": auto_record_result
    }

