"""
Webhooks Router - Stripe webhook handling

Handles incoming webhook events from Stripe for subscription management.
"""

import os
import logging
from fastapi import APIRouter, Request, HTTPException, Header
import stripe

from app.database import get_supabase_service
from app.services.subscription_service import get_subscription_service
from app.services.flow_pack_service import get_flow_pack_service

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
            
        elif event_type == "invoice.payment_failed":
            invoice = event["data"]["object"]
            await subscription_service.handle_invoice_payment_failed(invoice)
            
        elif event_type == "customer.subscription.trial_will_end":
            subscription = event["data"]["object"]
            # TODO: Send trial ending email notification
            logger.info(f"Trial ending soon for subscription {subscription.get('id')}")
            
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

