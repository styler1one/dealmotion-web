"""
Subscription Service

Handles subscription management, Stripe integration, and billing operations.
"""

import os
import logging
from typing import Optional, Dict, Any, List
from datetime import datetime, timedelta
import stripe
from app.database import get_supabase_service

logger = logging.getLogger(__name__)

# Initialize Stripe
stripe.api_key = os.getenv("STRIPE_SECRET_KEY")

# Use centralized database module
supabase = get_supabase_service()

# Stripe Price IDs (set via environment variables after creating in Stripe)
# v4 pricing model (December 2025) - High-end pricing
STRIPE_PRICES = {
    # v4 plans - Pro (without AI Notetaker)
    "pro_monthly": os.getenv("STRIPE_PRICE_PRO_MONTHLY"),
    "pro_yearly": os.getenv("STRIPE_PRICE_PRO_YEARLY"),
    # v4 plans - Pro+ (with AI Notetaker)
    "pro_plus_monthly": os.getenv("STRIPE_PRICE_PRO_PLUS_MONTHLY"),
    "pro_plus_yearly": os.getenv("STRIPE_PRICE_PRO_PLUS_YEARLY"),
    # Legacy aliases (for backwards compatibility with existing subscriptions)
    "pro_solo": os.getenv("STRIPE_PRICE_PRO_MONTHLY"),
    "unlimited_solo": os.getenv("STRIPE_PRICE_PRO_PLUS_MONTHLY"),
    "light_solo": os.getenv("STRIPE_PRICE_PRO_MONTHLY"),
    "solo_monthly": os.getenv("STRIPE_PRICE_PRO_MONTHLY"),
    "solo_yearly": os.getenv("STRIPE_PRICE_PRO_YEARLY"),
}

# Stripe Donation Link (for free users)
STRIPE_DONATION_LINK = os.getenv("STRIPE_DONATION_LINK")


class SubscriptionService:
    """Service for managing subscriptions and billing"""
    
    def __init__(self):
        self.stripe = stripe
        self.supabase = supabase
    
    # ==========================================
    # SUBSCRIPTION RETRIEVAL
    # ==========================================
    
    async def get_subscription(self, organization_id: str) -> Dict[str, Any]:
        """
        Get subscription details for an organization
        
        Returns subscription with plan details and features
        """
        try:
            # Get subscription
            response = self.supabase.table("organization_subscriptions").select(
                "*, subscription_plans(*)"
            ).eq("organization_id", organization_id).single().execute()
            
            if not response.data:
                # Create default FREE subscription if none exists
                return await self._create_default_subscription(organization_id)
            
            subscription = response.data
            plan = subscription.get("subscription_plans", {})
            
            return {
                "id": subscription["id"],
                "organization_id": subscription["organization_id"],
                "plan_id": subscription["plan_id"],
                "plan_name": plan.get("name", "Free"),
                "status": subscription["status"],
                "features": plan.get("features", {}),
                "price_cents": plan.get("price_cents", 0),
                "billing_interval": plan.get("billing_interval"),
                "current_period_start": subscription.get("current_period_start"),
                "current_period_end": subscription.get("current_period_end"),
                "cancel_at_period_end": subscription.get("cancel_at_period_end", False),
                "trial_start": subscription.get("trial_start"),
                "trial_end": subscription.get("trial_end"),
                "stripe_subscription_id": subscription.get("stripe_subscription_id"),
                "is_trialing": subscription["status"] == "trialing",
                "is_active": subscription["status"] in ["active", "trialing"],
                "is_paid": subscription["plan_id"] not in ["free"],
            }
            
        except Exception as e:
            logger.error(f"Error getting subscription: {e}")
            # Return default free subscription on error
            return self._get_default_subscription(organization_id)
    
    async def _create_default_subscription(self, organization_id: str) -> Dict[str, Any]:
        """Create default FREE subscription for organization"""
        try:
            response = self.supabase.table("organization_subscriptions").insert({
                "organization_id": organization_id,
                "plan_id": "free",
                "status": "active"
            }).execute()
            
            if response.data:
                return await self.get_subscription(organization_id)
            
        except Exception as e:
            logger.error(f"Error creating default subscription: {e}")
        
        return self._get_default_subscription(organization_id)
    
    def _get_default_subscription(self, organization_id: str) -> Dict[str, Any]:
        """Return default free subscription object"""
        return {
            "id": None,
            "organization_id": organization_id,
            "plan_id": "free",
            "plan_name": "Free",
            "status": "active",
            "features": {
                "research_limit": 3,
                "preparation_limit": 3,
                "followup_limit": 1,
                "transcription_seconds_limit": 0,
                "kb_document_limit": 0,
                "contact_analysis": "basic",
                "pdf_watermark": True,
                "user_limit": 1,
                "crm_integration": False,
                "team_sharing": False,
                "priority_support": False
            },
            "price_cents": 0,
            "billing_interval": None,
            "is_trialing": False,
            "is_active": True,
            "is_paid": False,
        }
    
    # ==========================================
    # PLAN MANAGEMENT
    # ==========================================
    
    async def get_plans(self, include_teams: bool = False) -> List[Dict[str, Any]]:
        """Get all available subscription plans"""
        try:
            query = self.supabase.table("subscription_plans").select("*").eq("is_active", True)
            
            if not include_teams:
                query = query.neq("id", "teams")
            
            response = query.order("display_order").execute()
            
            return response.data or []
            
        except Exception as e:
            logger.error(f"Error getting plans: {e}")
            return []
    
    async def get_plan_features(self, plan_id: str) -> Dict[str, Any]:
        """Get features for a specific plan"""
        try:
            response = self.supabase.table("subscription_plans").select(
                "features"
            ).eq("id", plan_id).single().execute()
            
            return response.data.get("features", {}) if response.data else {}
            
        except Exception as e:
            logger.error(f"Error getting plan features: {e}")
            return {}
    
    # ==========================================
    # STRIPE CHECKOUT
    # ==========================================
    
    async def create_checkout_session(
        self,
        organization_id: str,
        plan_id: str,
        user_email: str,
        success_url: str,
        cancel_url: str
    ) -> Dict[str, Any]:
        """
        Create Stripe Checkout session for subscription
        
        Returns:
            {"checkout_url": "https://checkout.stripe.com/..."}
        """
        try:
            # Validate plan
            if plan_id not in STRIPE_PRICES:
                raise ValueError(f"Invalid plan: {plan_id}")
            
            stripe_price_id = STRIPE_PRICES[plan_id]
            if not stripe_price_id:
                raise ValueError(f"Stripe price not configured for plan: {plan_id}")
            
            # Get or create Stripe customer
            stripe_customer_id = await self._get_or_create_stripe_customer(
                organization_id, user_email
            )
            
            # Create checkout session
            # v2: No trial period - direct payment
            session = self.stripe.checkout.Session.create(
                customer=stripe_customer_id,
                payment_method_types=["card", "ideal", "bancontact"],  # EU payment methods (SEPA enabled)
                line_items=[{
                    "price": stripe_price_id,
                    "quantity": 1,
                }],
                mode="subscription",
                success_url=success_url + "?session_id={CHECKOUT_SESSION_ID}",
                cancel_url=cancel_url,
                subscription_data={
                    # v2: No trial - removed trial_period_days
                    "metadata": {
                        "organization_id": organization_id,
                        "plan_id": plan_id,
                    }
                },
                metadata={
                    "organization_id": organization_id,
                    "plan_id": plan_id,
                },
                allow_promotion_codes=True,
                billing_address_collection="required",
                customer_update={
                    "address": "auto",
                    "name": "auto",
                },
            )
            
            logger.info(f"Created checkout session {session.id} for org {organization_id}")
            
            return {
                "checkout_url": session.url,
                "session_id": session.id,
            }
            
        except stripe.error.StripeError as e:
            logger.error(f"Stripe error creating checkout: {e}")
            raise
        except Exception as e:
            logger.error(f"Error creating checkout session: {e}")
            raise
    
    async def _get_or_create_stripe_customer(
        self,
        organization_id: str,
        email: str
    ) -> str:
        """Get existing Stripe customer or create new one"""
        try:
            # Check if customer exists
            response = self.supabase.table("organization_subscriptions").select(
                "stripe_customer_id"
            ).eq("organization_id", organization_id).single().execute()
            
            if response.data and response.data.get("stripe_customer_id"):
                return response.data["stripe_customer_id"]
            
            # Get organization name
            org_response = self.supabase.table("organizations").select(
                "name"
            ).eq("id", organization_id).single().execute()
            
            org_name = org_response.data.get("name", "Unknown") if org_response.data else "Unknown"
            
            # Create Stripe customer
            customer = self.stripe.Customer.create(
                email=email,
                name=org_name,
                metadata={
                    "organization_id": organization_id,
                }
            )
            
            # Save customer ID - ONLY update stripe_customer_id, preserve existing plan!
            # First check if a subscription record exists
            existing = self.supabase.table("organization_subscriptions").select(
                "plan_id"
            ).eq("organization_id", organization_id).maybe_single().execute()
            
            if existing.data:
                # Record exists - only update stripe_customer_id
                self.supabase.table("organization_subscriptions").update({
                    "stripe_customer_id": customer.id,
                }).eq("organization_id", organization_id).execute()
            else:
                # No record - create with free plan (new user)
                self.supabase.table("organization_subscriptions").insert({
                    "organization_id": organization_id,
                    "stripe_customer_id": customer.id,
                    "plan_id": "free",
                    "status": "active",
                }).execute()
            
            logger.info(f"Created Stripe customer {customer.id} for org {organization_id}")
            
            return customer.id
            
        except Exception as e:
            logger.error(f"Error getting/creating Stripe customer: {e}")
            raise
    
    # ==========================================
    # STRIPE BILLING PORTAL
    # ==========================================
    
    async def create_portal_session(
        self,
        organization_id: str,
        return_url: str
    ) -> Dict[str, Any]:
        """
        Create Stripe Billing Portal session for subscription management
        
        Returns:
            {"portal_url": "https://billing.stripe.com/..."}
        """
        try:
            # Get Stripe customer ID
            response = self.supabase.table("organization_subscriptions").select(
                "stripe_customer_id"
            ).eq("organization_id", organization_id).single().execute()
            
            if not response.data or not response.data.get("stripe_customer_id"):
                raise ValueError("No Stripe customer found for organization")
            
            stripe_customer_id = response.data["stripe_customer_id"]
            
            # Create portal session
            session = self.stripe.billing_portal.Session.create(
                customer=stripe_customer_id,
                return_url=return_url,
            )
            
            logger.info(f"Created portal session for org {organization_id}")
            
            return {
                "portal_url": session.url,
            }
            
        except stripe.error.StripeError as e:
            logger.error(f"Stripe error creating portal: {e}")
            raise
        except Exception as e:
            logger.error(f"Error creating portal session: {e}")
            raise
    
    # ==========================================
    # SUBSCRIPTION MANAGEMENT
    # ==========================================
    
    async def cancel_subscription(self, organization_id: str) -> Dict[str, Any]:
        """
        Cancel subscription at end of billing period
        
        Returns updated subscription
        """
        try:
            # Get subscription
            response = self.supabase.table("organization_subscriptions").select(
                "stripe_subscription_id"
            ).eq("organization_id", organization_id).single().execute()
            
            if not response.data or not response.data.get("stripe_subscription_id"):
                raise ValueError("No active subscription found")
            
            stripe_subscription_id = response.data["stripe_subscription_id"]
            
            # Cancel at period end in Stripe
            subscription = self.stripe.Subscription.modify(
                stripe_subscription_id,
                cancel_at_period_end=True
            )
            
            # Update local record
            self.supabase.table("organization_subscriptions").update({
                "cancel_at_period_end": True,
                "canceled_at": datetime.utcnow().isoformat(),
            }).eq("organization_id", organization_id).execute()
            
            logger.info(f"Canceled subscription for org {organization_id}")
            
            return await self.get_subscription(organization_id)
            
        except stripe.error.StripeError as e:
            logger.error(f"Stripe error canceling subscription: {e}")
            raise
        except Exception as e:
            logger.error(f"Error canceling subscription: {e}")
            raise
    
    async def reactivate_subscription(self, organization_id: str) -> Dict[str, Any]:
        """
        Reactivate a canceled subscription (before period end)
        
        Returns updated subscription
        """
        try:
            # Get subscription
            response = self.supabase.table("organization_subscriptions").select(
                "stripe_subscription_id"
            ).eq("organization_id", organization_id).single().execute()
            
            if not response.data or not response.data.get("stripe_subscription_id"):
                raise ValueError("No subscription found")
            
            stripe_subscription_id = response.data["stripe_subscription_id"]
            
            # Reactivate in Stripe
            subscription = self.stripe.Subscription.modify(
                stripe_subscription_id,
                cancel_at_period_end=False
            )
            
            # Update local record
            self.supabase.table("organization_subscriptions").update({
                "cancel_at_period_end": False,
                "canceled_at": None,
            }).eq("organization_id", organization_id).execute()
            
            logger.info(f"Reactivated subscription for org {organization_id}")
            
            return await self.get_subscription(organization_id)
            
        except stripe.error.StripeError as e:
            logger.error(f"Stripe error reactivating subscription: {e}")
            raise
        except Exception as e:
            logger.error(f"Error reactivating subscription: {e}")
            raise
    
    # ==========================================
    # WEBHOOK HANDLERS
    # ==========================================
    
    async def handle_checkout_completed(self, session: Dict[str, Any]) -> None:
        """Handle checkout.session.completed webhook event"""
        try:
            organization_id = session.get("metadata", {}).get("organization_id")
            plan_id = session.get("metadata", {}).get("plan_id")
            subscription_id = session.get("subscription")
            customer_id = session.get("customer")
            
            if not organization_id or not subscription_id:
                logger.error("Missing organization_id or subscription_id in checkout session")
                return
            
            # Get subscription details from Stripe
            stripe_sub = self.stripe.Subscription.retrieve(subscription_id)
            
            # Build update data - handle both dict and object access patterns
            current_period_start = getattr(stripe_sub, 'current_period_start', None) or stripe_sub.get('current_period_start')
            current_period_end = getattr(stripe_sub, 'current_period_end', None) or stripe_sub.get('current_period_end')
            trial_start = getattr(stripe_sub, 'trial_start', None) or stripe_sub.get('trial_start')
            trial_end = getattr(stripe_sub, 'trial_end', None) or stripe_sub.get('trial_end')
            status = getattr(stripe_sub, 'status', None) or stripe_sub.get('status', 'active')
            
            update_data = {
                "organization_id": organization_id,
                "plan_id": plan_id,
                "status": status,
                "stripe_customer_id": customer_id,
                "stripe_subscription_id": subscription_id,
            }
            
            if current_period_start:
                update_data["current_period_start"] = datetime.fromtimestamp(current_period_start).isoformat()
            if current_period_end:
                update_data["current_period_end"] = datetime.fromtimestamp(current_period_end).isoformat()
            if trial_start:
                update_data["trial_start"] = datetime.fromtimestamp(trial_start).isoformat()
            if trial_end:
                update_data["trial_end"] = datetime.fromtimestamp(trial_end).isoformat()
            
            # Update local subscription
            self.supabase.table("organization_subscriptions").upsert(
                update_data, 
                on_conflict="organization_id"
            ).execute()
            
            logger.info(f"Checkout completed for org {organization_id}, plan {plan_id}")
            
        except Exception as e:
            logger.error(f"Error handling checkout completed: {e}")
            raise
    
    async def handle_subscription_updated(self, subscription: Dict[str, Any]) -> None:
        """Handle customer.subscription.updated webhook event"""
        try:
            subscription_id = subscription.get("id")
            status = subscription.get("status")
            cancel_at_period_end = subscription.get("cancel_at_period_end", False)
            
            # Find organization by subscription ID - use maybe_single to handle 0 rows
            response = self.supabase.table("organization_subscriptions").select(
                "organization_id"
            ).eq("stripe_subscription_id", subscription_id).maybe_single().execute()
            
            if not response.data:
                # Subscription might not exist yet (created event before checkout completed)
                logger.info(f"No organization found for subscription {subscription_id}, will be handled by checkout webhook")
                return
            
            organization_id = response.data["organization_id"]
            
            # Determine plan from Stripe price
            plan_id = self._get_plan_from_stripe_subscription(subscription)
            
            # Update local subscription
            update_data = {
                "status": status,
                "cancel_at_period_end": cancel_at_period_end,
                "current_period_start": datetime.fromtimestamp(subscription["current_period_start"]).isoformat(),
                "current_period_end": datetime.fromtimestamp(subscription["current_period_end"]).isoformat(),
            }
            
            if plan_id:
                update_data["plan_id"] = plan_id
            
            self.supabase.table("organization_subscriptions").update(
                update_data
            ).eq("organization_id", organization_id).execute()
            
            logger.info(f"Subscription updated for org {organization_id}, status: {status}")
            
        except Exception as e:
            logger.error(f"Error handling subscription updated: {e}")
            raise
    
    async def handle_subscription_deleted(self, subscription: Dict[str, Any]) -> None:
        """Handle customer.subscription.deleted webhook event"""
        try:
            subscription_id = subscription.get("id")
            
            # Find organization by subscription ID
            response = self.supabase.table("organization_subscriptions").select(
                "organization_id"
            ).eq("stripe_subscription_id", subscription_id).single().execute()
            
            if not response.data:
                logger.warning(f"No organization found for subscription {subscription_id}")
                return
            
            organization_id = response.data["organization_id"]
            
            # Downgrade to free
            self.supabase.table("organization_subscriptions").update({
                "plan_id": "free",
                "status": "canceled",
                "stripe_subscription_id": None,
                "current_period_start": None,
                "current_period_end": None,
                "cancel_at_period_end": False,
            }).eq("organization_id", organization_id).execute()
            
            logger.info(f"Subscription deleted for org {organization_id}, downgraded to free")
            
        except Exception as e:
            logger.error(f"Error handling subscription deleted: {e}")
            raise
    
    async def handle_invoice_paid(self, invoice: Dict[str, Any]) -> None:
        """
        Handle invoice.paid webhook event.
        
        This resets subscription credits for monthly subscriptions.
        For yearly subscriptions, a separate cron job handles monthly resets.
        """
        try:
            customer_id = invoice.get("customer")
            invoice_id = invoice.get("id")
            amount_paid = invoice.get("amount_paid", 0)
            invoice_pdf = invoice.get("invoice_pdf")
            invoice_number = invoice.get("number")
            subscription_id = invoice.get("subscription")
            
            # Find organization by customer ID
            response = self.supabase.table("organization_subscriptions").select(
                "organization_id, plan_id"
            ).eq("stripe_customer_id", customer_id).single().execute()
            
            if not response.data:
                logger.warning(f"No organization found for customer {customer_id}")
                return
            
            organization_id = response.data["organization_id"]
            plan_id = response.data.get("plan_id")
            
            # Record payment
            self.supabase.table("payment_history").insert({
                "organization_id": organization_id,
                "stripe_invoice_id": invoice_id,
                "amount_cents": amount_paid,
                "currency": invoice.get("currency", "eur"),
                "status": "paid",
                "invoice_pdf_url": invoice_pdf,
                "invoice_number": invoice_number,
                "paid_at": datetime.utcnow().isoformat(),
            }).execute()
            
            # Reset subscription credits for this billing period
            # This applies to monthly subscriptions
            if subscription_id and plan_id:
                from app.services.credit_service import get_credit_service
                credit_service = get_credit_service()
                
                # Get Stripe subscription to get the ACTUAL billing period
                # This ensures credits reset on the purchase anniversary, not the 1st of month
                try:
                    stripe_sub = self.stripe.Subscription.retrieve(subscription_id)
                    billing_period_start = datetime.fromtimestamp(stripe_sub.current_period_start)
                    billing_period_end = datetime.fromtimestamp(stripe_sub.current_period_end)
                    logger.info(
                        f"Stripe billing period for {organization_id}: "
                        f"{billing_period_start.date()} to {billing_period_end.date()}"
                    )
                except Exception as stripe_err:
                    logger.warning(f"Could not fetch Stripe subscription: {stripe_err}")
                    billing_period_start = None
                    billing_period_end = None
                
                # Get plan credit allocation
                plan_response = self.supabase.table("subscription_plans").select(
                    "credits_per_month"
                ).eq("id", plan_id).single().execute()
                
                if plan_response.data:
                    credits_per_month = plan_response.data.get("credits_per_month", 0)
                    is_unlimited = credits_per_month == -1
                    
                    # Reset credits for the new billing period (dynamic based on Stripe)
                    await credit_service.reset_subscription_credits(
                        organization_id=organization_id,
                        credits_total=credits_per_month if not is_unlimited else 0,
                        is_unlimited=is_unlimited,
                        billing_period_start=billing_period_start,
                        billing_period_end=billing_period_end
                    )
                    
                    logger.info(
                        f"Reset credits for org {organization_id}: "
                        f"{credits_per_month} credits, unlimited={is_unlimited}, "
                        f"period: {billing_period_start} to {billing_period_end}"
                    )
            
            logger.info(f"Invoice paid for org {organization_id}, amount: {amount_paid}")
            
        except Exception as e:
            logger.error(f"Error handling invoice paid: {e}")
            raise
    
    async def handle_invoice_payment_failed(self, invoice: Dict[str, Any]) -> None:
        """Handle invoice.payment_failed webhook event"""
        try:
            customer_id = invoice.get("customer")
            invoice_id = invoice.get("id")
            
            # Find organization by customer ID
            response = self.supabase.table("organization_subscriptions").select(
                "organization_id"
            ).eq("stripe_customer_id", customer_id).single().execute()
            
            if not response.data:
                logger.warning(f"No organization found for customer {customer_id}")
                return
            
            organization_id = response.data["organization_id"]
            
            # Update subscription status to past_due
            self.supabase.table("organization_subscriptions").update({
                "status": "past_due",
            }).eq("organization_id", organization_id).execute()
            
            # Record failed payment
            self.supabase.table("payment_history").insert({
                "organization_id": organization_id,
                "stripe_invoice_id": invoice_id,
                "amount_cents": invoice.get("amount_due", 0),
                "currency": invoice.get("currency", "eur"),
                "status": "failed",
                "failed_at": datetime.utcnow().isoformat(),
            }).execute()
            
            logger.info(f"Invoice payment failed for org {organization_id}")
            
            # TODO: Send email notification to user
            
        except Exception as e:
            logger.error(f"Error handling invoice payment failed: {e}")
            raise
    
    def _get_plan_from_stripe_subscription(self, subscription: Dict[str, Any]) -> Optional[str]:
        """Extract plan ID from Stripe subscription object"""
        try:
            items = subscription.get("items", {}).get("data", [])
            if not items:
                return None
            
            price_id = items[0].get("price", {}).get("id")
            
            # Reverse lookup from price ID to plan ID
            for plan_id, stripe_price in STRIPE_PRICES.items():
                if stripe_price == price_id:
                    return plan_id
            
            return None
            
        except Exception:
            return None


# Singleton instance
_subscription_service: Optional[SubscriptionService] = None


def get_subscription_service() -> SubscriptionService:
    """Get or create subscription service instance"""
    global _subscription_service
    if _subscription_service is None:
        _subscription_service = SubscriptionService()
    return _subscription_service

