"""
Credit Reset Cron Job

Runs daily to reset subscription credits for organizations whose billing period has ended.
This is especially important for yearly subscriptions where invoice.paid only fires once per year,
but credits should reset monthly.

Schedule: Every day at 00:05 UTC
"""

import logging
from datetime import datetime
from dateutil.relativedelta import relativedelta
from inngest import TriggerCron
from app.inngest.client import inngest_client
from app.database import get_supabase_service

logger = logging.getLogger(__name__)


@inngest_client.create_function(
    fn_id="credit-reset-daily",
    trigger=TriggerCron(cron="5 0 * * *"),  # Daily at 00:05 UTC
)
async def credit_reset_daily_fn(ctx, step):
    """
    Daily cron job to reset subscription credits.
    
    Checks all organizations where subscription_period_end has passed
    and resets their subscription credits for the new period.
    """
    logger.info("Starting daily credit reset check")
    
    supabase = get_supabase_service()
    now = datetime.utcnow()
    
    # Find organizations where period has ended
    result = await step.run("find-expired-periods", lambda: find_expired_credit_periods(supabase, now))
    
    if not result["organizations"]:
        logger.info("No organizations need credit reset")
        return {"status": "ok", "reset_count": 0}
    
    # Reset credits for each organization
    reset_count = 0
    for org in result["organizations"]:
        org_id = org["organization_id"]
        credits_total = org["credits_per_month"]
        is_unlimited = credits_total == -1
        previous_period_end = org.get("previous_period_end")
        
        success = await step.run(
            f"reset-credits-{org_id[:8]}",
            lambda org_id=org_id, credits_total=credits_total, is_unlimited=is_unlimited, prev_end=previous_period_end: 
                reset_organization_credits(supabase, org_id, credits_total, is_unlimited, prev_end)
        )
        
        if success:
            reset_count += 1
    
    logger.info(f"Credit reset complete. Reset {reset_count} organizations.")
    
    return {
        "status": "ok",
        "reset_count": reset_count,
        "checked_at": now.isoformat()
    }


def find_expired_credit_periods(supabase, now: datetime) -> dict:
    """Find all organizations with expired credit periods (excluding free plan)."""
    try:
        # Query credit_balances where period has ended
        # Join with organization_subscriptions to get plan info
        response = supabase.table("credit_balances").select(
            "organization_id, subscription_period_end"
        ).lte(
            "subscription_period_end", now.isoformat()
        ).eq(
            "is_unlimited", False
        ).execute()
        
        if not response.data:
            return {"organizations": []}
        
        # For each organization, get their plan's credit allocation
        # SKIP free plan - free users get one-time credits that don't reset
        organizations = []
        for row in response.data:
            org_id = row["organization_id"]
            
            # Get plan info
            plan_response = supabase.table("organization_subscriptions").select(
                "plan_id, subscription_plans(credits_per_month)"
            ).eq("organization_id", org_id).single().execute()
            
            if plan_response.data:
                plan_id = plan_response.data.get("plan_id", "")
                
                # Skip free plan - free users get one-time credits only
                if plan_id == "free":
                    logger.debug(f"Skipping free plan org {org_id} - no monthly reset")
                    continue
                
                plan_data = plan_response.data.get("subscription_plans", {})
                credits_per_month = plan_data.get("credits_per_month", 25) if plan_data else 25
                
                organizations.append({
                    "organization_id": org_id,
                    "credits_per_month": credits_per_month,
                    "previous_period_end": row["subscription_period_end"]
                })
        
        logger.info(f"Found {len(organizations)} paid organizations needing credit reset")
        return {"organizations": organizations}
        
    except Exception as e:
        logger.error(f"Error finding expired credit periods: {e}")
        return {"organizations": []}


def reset_organization_credits(
    supabase, 
    organization_id: str, 
    credits_total: int, 
    is_unlimited: bool,
    previous_period_end: str = None
) -> bool:
    """
    Reset credits for a single organization.
    
    The new period starts from the previous period's end date (not the 1st of month).
    This ensures the billing cycle stays aligned with the original purchase date.
    """
    try:
        now = datetime.utcnow()
        
        # Calculate new period based on PREVIOUS period end (dynamic, not hardcoded)
        if previous_period_end:
            # Continue from where the last period ended
            period_start = datetime.fromisoformat(previous_period_end.replace('Z', '+00:00').replace('+00:00', ''))
        else:
            # Fallback: start from now
            period_start = now
        
        # New period is exactly 1 month from the start
        period_end = period_start + relativedelta(months=1)
        
        # Update credit balance
        supabase.table("credit_balances").update({
            "subscription_credits_total": credits_total if not is_unlimited else 0,
            "subscription_credits_used": 0,
            "subscription_period_start": period_start.isoformat(),
            "subscription_period_end": period_end.isoformat(),
            "is_unlimited": is_unlimited,
            "updated_at": now.isoformat()
        }).eq("organization_id", organization_id).execute()
        
        # Log transaction
        supabase.table("credit_transactions").insert({
            "organization_id": organization_id,
            "transaction_type": "subscription_reset",
            "credits_amount": credits_total if not is_unlimited else 0,
            "balance_after": credits_total if not is_unlimited else 0,
            "reference_type": "subscription",
            "description": f"Monthly credit reset: {credits_total} credits"
        }).execute()
        
        logger.info(f"Reset credits for org {organization_id}: {credits_total} credits")
        return True
        
    except Exception as e:
        logger.error(f"Error resetting credits for org {organization_id}: {e}")
        return False

