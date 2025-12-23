"""
Webhooks Router - Stripe webhook handling

Handles incoming webhook events from Stripe for:
- Subscription management
- Credit pack purchases
- Affiliate commissions
- Stripe Connect (affiliate payouts)
"""

import os
import logging
from fastapi import APIRouter, Request, HTTPException, Header
import stripe

from app.database import get_supabase_service
from app.services.subscription_service import get_subscription_service
from app.services.flow_pack_service import get_flow_pack_service
from app.services.affiliate_service import get_affiliate_service

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/webhooks", tags=["webhooks"])

# Initialize Stripe
stripe.api_key = os.getenv("STRIPE_SECRET_KEY")
STRIPE_WEBHOOK_SECRET = os.getenv("STRIPE_WEBHOOK_SECRET")

# Use centralized database module for idempotency
supabase = get_supabase_service()


@router.post("/stripe")
async def stripe_webhook(
    request: Request,
    stripe_signature: str = Header(None, alias="Stripe-Signature")
):
    """
    Handle Stripe webhook events
    
    Events handled:
    - checkout.session.completed
    - customer.subscription.created
    - customer.subscription.updated
    - customer.subscription.deleted
    - invoice.paid
    - invoice.payment_failed
    - customer.subscription.trial_will_end
    """
    
    # Get raw body
    payload = await request.body()
    
    # Verify webhook signature
    if not STRIPE_WEBHOOK_SECRET:
        logger.warning("STRIPE_WEBHOOK_SECRET not configured, skipping signature verification")
        try:
            event = stripe.Event.construct_from(
                stripe.util.convert_to_stripe_object(payload),
                stripe.api_key
            )
        except Exception as e:
            logger.error(f"Error parsing webhook payload: {e}")
            raise HTTPException(status_code=400, detail="Invalid payload")
    else:
        try:
            event = stripe.Webhook.construct_event(
                payload, stripe_signature, STRIPE_WEBHOOK_SECRET
            )
        except stripe.error.SignatureVerificationError as e:
            logger.error(f"Invalid webhook signature: {e}")
            raise HTTPException(status_code=400, detail="Invalid signature")
        except Exception as e:
            logger.error(f"Error verifying webhook: {e}")
            raise HTTPException(status_code=400, detail="Invalid payload")
    
    event_id = event.get("id")
    event_type = event.get("type")
    
    logger.info(f"Received Stripe webhook: {event_type} ({event_id})")
    
    # Check idempotency - have we already processed this event?
    try:
        existing = supabase.table("stripe_webhook_events").select("id").eq(
            "id", event_id
        ).single().execute()
        
        if existing.data:
            logger.info(f"Event {event_id} already processed, skipping")
            return {"status": "already_processed"}
    except Exception:
        # No existing record, continue processing
        pass
    
    # Get subscription service
    subscription_service = get_subscription_service()
    
    try:
        # Handle event based on type
        if event_type == "checkout.session.completed":
            session = event["data"]["object"]
            
            # Check if this is a credit pack purchase or subscription
            metadata = session.get("metadata", {})
            if metadata.get("type") in ("credit_pack", "flow_pack"):
                # Handle credit pack purchase (supports both new and legacy type)
                flow_pack_service = get_flow_pack_service()
                await flow_pack_service.handle_checkout_completed(session)
            else:
                # Handle subscription checkout
                await subscription_service.handle_checkout_completed(session)
            
        elif event_type == "customer.subscription.created":
            subscription = event["data"]["object"]
            await subscription_service.handle_subscription_updated(subscription)
            
        elif event_type == "customer.subscription.updated":
            subscription = event["data"]["object"]
            await subscription_service.handle_subscription_updated(subscription)
            
        elif event_type == "customer.subscription.deleted":
            subscription = event["data"]["object"]
            await subscription_service.handle_subscription_deleted(subscription)
            
        elif event_type == "invoice.paid":
            invoice = event["data"]["object"]
            await subscription_service.handle_invoice_paid(invoice)
            
            # Process affiliate commission if applicable
            await _process_affiliate_commission(invoice)
            
        elif event_type == "invoice.payment_failed":
            invoice = event["data"]["object"]
            await subscription_service.handle_invoice_payment_failed(invoice)
            
        elif event_type == "customer.subscription.trial_will_end":
            subscription = event["data"]["object"]
            # TODO: Send trial ending email notification
            logger.info(f"Trial ending soon for subscription {subscription.get('id')}")
        
        # =====================================================================
        # REFUND EVENTS - Reverse affiliate commissions
        # =====================================================================
        elif event_type == "charge.refunded":
            charge = event["data"]["object"]
            await _handle_refund(charge)
        
        elif event_type == "charge.dispute.created":
            dispute = event["data"]["object"]
            await _handle_dispute(dispute)
        
        # =====================================================================
        # STRIPE CONNECT EVENTS - Affiliate payouts
        # =====================================================================
        elif event_type == "account.updated":
            account = event["data"]["object"]
            await _handle_connect_account_updated(account)
        
        elif event_type == "transfer.updated":
            transfer = event["data"]["object"]
            await _handle_transfer_updated(transfer)
        
        elif event_type == "transfer.failed":
            transfer = event["data"]["object"]
            await _handle_transfer_updated(transfer)
            
        else:
            logger.info(f"Unhandled event type: {event_type}")
        
        # Mark event as processed (idempotency)
        supabase.table("stripe_webhook_events").insert({
            "id": event_id,
            "event_type": event_type,
            "payload": event,
        }).execute()
        
        return {"status": "success"}
        
    except Exception as e:
        logger.error(f"Error processing webhook {event_type}: {e}")
        # Don't mark as processed so Stripe will retry
        raise HTTPException(status_code=500, detail="Processing error")


# =============================================================================
# AFFILIATE COMMISSION HELPERS
# =============================================================================

async def _process_affiliate_commission(invoice: dict) -> None:
    """
    Process affiliate commission for a paid invoice.
    
    Called after invoice.paid webhook handling.
    """
    try:
        customer_id = invoice.get("customer")
        amount_paid = invoice.get("amount_paid", 0)
        invoice_id = invoice.get("id")
        subscription_id = invoice.get("subscription")
        
        # Skip zero-amount invoices (trials, etc.)
        if amount_paid <= 0:
            return
        
        # Get customer to find organization
        customer = stripe.Customer.retrieve(customer_id)
        organization_id = customer.metadata.get("organization_id")
        
        if not organization_id:
            # Try to find organization via subscription table
            org_response = supabase.table("organization_subscriptions").select(
                "organization_id"
            ).eq("stripe_customer_id", customer_id).maybe_single().execute()
            
            if org_response.data:
                organization_id = org_response.data["organization_id"]
            else:
                return  # Can't attribute without organization
        
        # Determine payment type
        payment_type = "subscription" if subscription_id else "credit_pack"
        
        # Check metadata for credit pack type
        if invoice.get("metadata", {}).get("type") in ("credit_pack", "flow_pack"):
            payment_type = "credit_pack"
        
        # Create commission via affiliate service
        affiliate_service = get_affiliate_service()
        
        commission = await affiliate_service.create_commission(
            organization_id=organization_id,
            payment_type=payment_type,
            payment_amount_cents=amount_paid,
            stripe_invoice_id=invoice_id,
            stripe_charge_id=invoice.get("charge"),
            stripe_payment_intent_id=invoice.get("payment_intent"),
            currency=invoice.get("currency", "eur")
        )
        
        if commission:
            logger.info(
                f"Created affiliate commission for invoice {invoice_id}: "
                f"{commission['commission_amount_cents']} cents"
            )
    
    except Exception as e:
        # Don't fail the webhook for commission errors
        logger.error(f"Error processing affiliate commission: {e}")


async def _handle_refund(charge: dict) -> None:
    """
    Handle charge.refunded event - reverse affiliate commissions.
    """
    try:
        charge_id = charge.get("id")
        invoice_id = charge.get("invoice")
        refund_id = None
        
        # Get refund ID from charge data
        refunds = charge.get("refunds", {}).get("data", [])
        if refunds:
            refund_id = refunds[0].get("id")
        
        affiliate_service = get_affiliate_service()
        
        reversed = await affiliate_service.reverse_commission(
            stripe_invoice_id=invoice_id,
            stripe_charge_id=charge_id,
            stripe_refund_id=refund_id,
            reason="refund"
        )
        
        if reversed:
            logger.info(f"Reversed affiliate commission for charge {charge_id}")
    
    except Exception as e:
        logger.error(f"Error handling refund for affiliate: {e}")


async def _handle_dispute(dispute: dict) -> None:
    """
    Handle charge.dispute.created event - flag affiliate commissions.
    """
    try:
        charge_id = dispute.get("charge")
        
        affiliate_service = get_affiliate_service()
        
        reversed = await affiliate_service.reverse_commission(
            stripe_charge_id=charge_id,
            reason="chargeback"
        )
        
        if reversed:
            logger.info(f"Flagged affiliate commission for disputed charge {charge_id}")
    
    except Exception as e:
        logger.error(f"Error handling dispute for affiliate: {e}")


# =============================================================================
# STRIPE CONNECT HELPERS
# =============================================================================

async def _handle_connect_account_updated(account: dict) -> None:
    """
    Handle account.updated event for Stripe Connect accounts.
    
    Updates affiliate's Connect status based on account state.
    """
    try:
        account_id = account.get("id")
        
        # Find affiliate by Connect account ID
        affiliate_response = supabase.table("affiliates").select(
            "id"
        ).eq("stripe_connect_account_id", account_id).maybe_single().execute()
        
        if not affiliate_response.data:
            return  # Not one of our affiliates
        
        affiliate_id = affiliate_response.data["id"]
        
        # Sync status
        affiliate_service = get_affiliate_service()
        await affiliate_service.sync_connect_account_status(affiliate_id)
        
        logger.info(f"Synced Connect status for affiliate {affiliate_id}")
    
    except Exception as e:
        logger.error(f"Error handling Connect account update: {e}")


async def _handle_transfer_updated(transfer: dict) -> None:
    """
    Handle transfer.updated and transfer.failed events.
    
    Updates payout status based on transfer outcome.
    """
    try:
        affiliate_service = get_affiliate_service()
        await affiliate_service.handle_transfer_updated(transfer)
        
        logger.info(f"Handled transfer update: {transfer.get('id')} - {transfer.get('status')}")
    
    except Exception as e:
        logger.error(f"Error handling transfer update: {e}")

