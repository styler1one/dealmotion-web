"""
Affiliate Program Background Jobs

Handles automated affiliate program operations:
- Daily: Approve pending commissions (after 14-day refund window)
- Monthly: Process payouts to affiliates via Stripe Connect
- Hourly: Sync Stripe Connect account statuses
- Daily: Cleanup expired click records

Schedule:
- approve-commissions: Daily at 01:00 UTC
- process-payouts: 1st of month at 09:00 UTC
- sync-connect-status: Every hour at :15
- cleanup-expired-clicks: Daily at 03:00 UTC
"""

import logging
from datetime import datetime, timedelta
from inngest import TriggerCron
from app.inngest.client import inngest_client
from app.database import get_supabase_service
from app.services.affiliate_service import get_affiliate_service

logger = logging.getLogger(__name__)


# =============================================================================
# DAILY: APPROVE PENDING COMMISSIONS
# =============================================================================

@inngest_client.create_function(
    fn_id="affiliate-approve-commissions",
    trigger=TriggerCron(cron="0 1 * * *"),  # Daily at 01:00 UTC
)
async def approve_commissions_fn(ctx, step):
    """
    Move pending commissions to approved after 14-day refund window.
    
    This job runs daily and checks for commissions where:
    - status = 'pending'
    - approved_at (scheduled approval time) <= now
    
    For each qualifying commission:
    1. Update status to 'approved'
    2. Add commission amount to affiliate's current_balance_cents
    """
    logger.info("Starting daily commission approval check")
    
    affiliate_service = get_affiliate_service()
    
    approved_count = await step.run(
        "approve-commissions",
        lambda: affiliate_service.approve_pending_commissions()
    )
    
    logger.info(f"Commission approval complete: {approved_count} commissions approved")
    
    return {
        "status": "ok",
        "approved_count": approved_count,
        "checked_at": datetime.utcnow().isoformat()
    }


# =============================================================================
# MONTHLY: PROCESS PAYOUTS
# =============================================================================

@inngest_client.create_function(
    fn_id="affiliate-process-payouts",
    trigger=TriggerCron(cron="0 9 1 * *"),  # 1st of month at 09:00 UTC
)
async def process_payouts_fn(ctx, step):
    """
    Process monthly payouts for all eligible affiliates.
    
    This job runs on the 1st of each month and:
    1. Finds affiliates with balance >= minimum_payout_cents
    2. Checks Stripe Connect is enabled
    3. Creates payout record
    4. Initiates Stripe Transfer to affiliate's Connect account
    
    Payouts are tracked and can be monitored via admin dashboard.
    """
    logger.info("Starting monthly payout processing")
    
    supabase = get_supabase_service()
    affiliate_service = get_affiliate_service()
    
    # Find eligible affiliates
    eligible = await step.run("find-eligible-affiliates", lambda: _find_eligible_affiliates(supabase))
    
    if not eligible:
        logger.info("No affiliates eligible for payout")
        return {
            "status": "ok",
            "payouts_processed": 0,
            "total_amount_cents": 0
        }
    
    # Process each affiliate
    payouts_processed = 0
    total_amount = 0
    failed = []
    
    for affiliate in eligible:
        affiliate_id = affiliate["id"]
        affiliate_code = affiliate["affiliate_code"]
        balance = affiliate.get("current_balance_cents", 0)
        
        logger.info(f"Processing payout for affiliate {affiliate_code}: {balance} cents")
        
        try:
            payout = await step.run(
                f"payout-{affiliate_id[:8]}",
                lambda aid=affiliate_id: affiliate_service.process_payout(aid)
            )
            
            if payout:
                payouts_processed += 1
                total_amount += payout["amount_cents"]
                logger.info(f"Payout created: {payout['id']} for {payout['amount_cents']} cents")
            else:
                logger.warning(f"No payout created for affiliate {affiliate_code}")
                
        except Exception as e:
            logger.error(f"Failed to process payout for {affiliate_code}: {e}")
            failed.append({
                "affiliate_id": affiliate_id,
                "affiliate_code": affiliate_code,
                "error": str(e)
            })
    
    result = {
        "status": "ok",
        "payouts_processed": payouts_processed,
        "total_amount_cents": total_amount,
        "failed_count": len(failed),
        "failed": failed if failed else None,
        "processed_at": datetime.utcnow().isoformat()
    }
    
    logger.info(
        f"Monthly payout complete: {payouts_processed} payouts, "
        f"€{total_amount/100:.2f} total, {len(failed)} failed"
    )
    
    return result


def _find_eligible_affiliates(supabase) -> list:
    """Find affiliates eligible for payout."""
    try:
        # Find active affiliates with:
        # - Balance >= minimum_payout_cents
        # - Stripe Connect enabled
        response = supabase.table("affiliates").select(
            "id, affiliate_code, current_balance_cents, minimum_payout_cents"
        ).eq(
            "status", "active"
        ).eq(
            "stripe_payouts_enabled", True
        ).execute()
        
        # Filter by balance >= minimum (can't do this in Supabase query easily)
        eligible = [
            a for a in (response.data or [])
            if (a.get("current_balance_cents", 0) or 0) >= (a.get("minimum_payout_cents", 5000) or 5000)
        ]
        
        logger.info(f"Found {len(eligible)} affiliates eligible for payout")
        return eligible
        
    except Exception as e:
        logger.error(f"Error finding eligible affiliates: {e}")
        return []


# =============================================================================
# HOURLY: SYNC CONNECT STATUS
# =============================================================================

@inngest_client.create_function(
    fn_id="affiliate-sync-connect-status",
    trigger=TriggerCron(cron="15 * * * *"),  # Every hour at :15
)
async def sync_connect_status_fn(ctx, step):
    """
    Sync Stripe Connect account status for all affiliates with Connect accounts.
    
    This ensures our database reflects the current state of Connect accounts,
    including whether payouts are enabled or if there are pending requirements.
    """
    logger.info("Starting hourly Connect status sync")
    
    supabase = get_supabase_service()
    affiliate_service = get_affiliate_service()
    
    # Find affiliates with Connect accounts
    response = await step.run("find-connected-affiliates", lambda: 
        supabase.table("affiliates").select(
            "id, affiliate_code, stripe_connect_account_id"
        ).not_.is_(
            "stripe_connect_account_id", "null"
        ).neq(
            "stripe_connect_status", "disabled"
        ).execute()
    )
    
    affiliates = response.data or []
    
    if not affiliates:
        logger.info("No Connect accounts to sync")
        return {"status": "ok", "synced": 0}
    
    synced = 0
    for affiliate in affiliates:
        try:
            await step.run(
                f"sync-{affiliate['id'][:8]}",
                lambda aid=affiliate["id"]: affiliate_service.sync_connect_account_status(aid)
            )
            synced += 1
        except Exception as e:
            logger.error(f"Error syncing Connect for {affiliate['affiliate_code']}: {e}")
    
    logger.info(f"Connect status sync complete: {synced}/{len(affiliates)} synced")
    
    return {
        "status": "ok",
        "synced": synced,
        "total": len(affiliates),
        "synced_at": datetime.utcnow().isoformat()
    }


# =============================================================================
# DAILY: CLEANUP EXPIRED CLICKS
# =============================================================================

@inngest_client.create_function(
    fn_id="affiliate-cleanup-clicks",
    trigger=TriggerCron(cron="0 3 * * *"),  # Daily at 03:00 UTC
)
async def cleanup_clicks_fn(ctx, step):
    """
    Remove expired click records that were not converted.
    
    Click records have a 30-day attribution window. After that,
    if they haven't converted to a signup, we can delete them
    to keep the database clean.
    """
    logger.info("Starting daily click cleanup")
    
    supabase = get_supabase_service()
    now = datetime.utcnow()
    
    # Delete expired, non-converted clicks
    deleted = await step.run("delete-expired-clicks", lambda:
        supabase.table("affiliate_clicks").delete().eq(
            "converted_to_signup", False
        ).lt(
            "expires_at", now.isoformat()
        ).execute()
    )
    
    deleted_count = len(deleted.data or [])
    
    logger.info(f"Click cleanup complete: {deleted_count} expired clicks deleted")
    
    return {
        "status": "ok",
        "deleted": deleted_count,
        "cleaned_at": datetime.utcnow().isoformat()
    }


# =============================================================================
# EXPORT ALL FUNCTIONS
# =============================================================================

affiliate_functions = [
    approve_commissions_fn,
    process_payouts_fn,
    sync_connect_status_fn,
    cleanup_clicks_fn,
]

