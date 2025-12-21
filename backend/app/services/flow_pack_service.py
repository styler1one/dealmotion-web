"""
Credit Pack Service (formerly Flow Pack Service)

Handles credit pack purchases, balance checking, and consumption.
Credit packs allow users to buy additional credits beyond their subscription limit.

Pack Options:
- Boost 100: 100 credits for €14.95 (€0.15/credit)
- Boost 300: 300 credits for €39.95 (€0.13/credit)
- Boost 600: 600 credits for €69.95 (€0.12/credit)
"""

import os
import logging
from typing import Optional, Dict, Any, List
from datetime import datetime
import stripe
from app.database import get_supabase_service

logger = logging.getLogger(__name__)

# Initialize Stripe
stripe.api_key = os.getenv("STRIPE_SECRET_KEY")

# Credit pack configuration
# Note: "flows" in the database = "credits" in the new terminology
CREDIT_PACK_CONFIG = {
    # New credit packs (v4)
    "boost_100": {
        "credits": 100,
        "price_cents": 1495,  # €14.95
        "name": "Boost 100",
        "stripe_price_env": "STRIPE_PRICE_CREDIT_PACK_100",
    },
    "boost_300": {
        "credits": 300,
        "price_cents": 3995,  # €39.95
        "name": "Boost 300",
        "stripe_price_env": "STRIPE_PRICE_CREDIT_PACK_300",
    },
    "boost_600": {
        "credits": 600,
        "price_cents": 6995,  # €69.95
        "name": "Boost 600",
        "stripe_price_env": "STRIPE_PRICE_CREDIT_PACK_600",
    },
    # Legacy pack (for backwards compatibility)
    "pack_5": {
        "credits": 5,
        "price_cents": 995,
        "name": "5 Flow Pack (Legacy)",
        "stripe_price_env": "STRIPE_PRICE_FLOW_PACK_5",
    }
}

# Alias for backwards compatibility
FLOW_PACK_CONFIG = CREDIT_PACK_CONFIG


class FlowPackService:
    """Service for managing credit pack purchases and consumption"""
    
    def __init__(self):
        self.stripe = stripe
        self.supabase = get_supabase_service()
    
    # ==========================================
    # BALANCE & AVAILABILITY
    # ==========================================
    
    async def get_balance(self, organization_id: str) -> Dict[str, Any]:
        """
        Get credit pack balance for an organization
        
        Returns:
            {
                "total_remaining": int,
                "packs": [{"id", "flows_remaining", "purchased_at", "expires_at"}]
            }
        """
        try:
            response = self.supabase.table("flow_packs").select(
                "id, flows_remaining, purchased_at, expires_at"
            ).eq(
                "organization_id", organization_id
            ).eq(
                "status", "active"
            ).gt(
                "flows_remaining", 0
            ).order(
                "purchased_at"
            ).execute()
            
            packs = response.data or []
            total = sum(p.get("flows_remaining", 0) for p in packs)
            
            return {
                "total_remaining": total,
                "packs": packs,
            }
            
        except Exception as e:
            logger.error(f"Error getting credit pack balance: {e}")
            return {"total_remaining": 0, "packs": []}
    
    async def has_available_credits(self, organization_id: str, required: int = 1) -> bool:
        """Check if organization has enough credit pack balance"""
        balance = await self.get_balance(organization_id)
        return balance["total_remaining"] >= required
    
    # Alias for backwards compatibility
    async def has_available_flows(self, organization_id: str, required: int = 1) -> bool:
        return await self.has_available_credits(organization_id, required)
    
    # ==========================================
    # CONSUMPTION
    # ==========================================
    
    async def consume_credits(self, organization_id: str, amount: int = 1) -> bool:
        """
        Consume credits from pack balance (FIFO - oldest pack first)
        
        Args:
            organization_id: Organization UUID
            amount: Number of credits to consume (default 1)
            
        Returns:
            True if successful, False if insufficient balance
        """
        try:
            # Get active packs ordered by purchase date
            response = self.supabase.table("flow_packs").select(
                "id, flows_remaining"
            ).eq(
                "organization_id", organization_id
            ).eq(
                "status", "active"
            ).gt(
                "flows_remaining", 0
            ).order(
                "purchased_at"
            ).execute()
            
            packs = response.data or []
            remaining = amount
            
            for pack in packs:
                if remaining <= 0:
                    break
                
                pack_remaining = pack.get("flows_remaining", 0)
                
                if pack_remaining >= remaining:
                    # This pack can cover it
                    new_remaining = pack_remaining - remaining
                    update_data = {
                        "flows_remaining": new_remaining,
                        "updated_at": datetime.utcnow().isoformat(),
                    }
                    if new_remaining == 0:
                        update_data["status"] = "depleted"
                        update_data["depleted_at"] = datetime.utcnow().isoformat()
                    
                    self.supabase.table("flow_packs").update(
                        update_data
                    ).eq("id", pack["id"]).execute()
                    
                    remaining = 0
                else:
                    # Use all from this pack
                    remaining -= pack_remaining
                    self.supabase.table("flow_packs").update({
                        "flows_remaining": 0,
                        "status": "depleted",
                        "depleted_at": datetime.utcnow().isoformat(),
                        "updated_at": datetime.utcnow().isoformat(),
                    }).eq("id", pack["id"]).execute()
            
            success = remaining == 0
            if success:
                logger.info(f"Consumed {amount} credit(s) from packs for org {organization_id}")
            else:
                logger.warning(f"Insufficient credit pack balance for org {organization_id}")
            
            return success
            
        except Exception as e:
            logger.error(f"Error consuming credit pack: {e}")
            return False
    
    # Alias for backwards compatibility
    async def consume_flow(self, organization_id: str, amount: int = 1) -> bool:
        return await self.consume_credits(organization_id, amount)
    
    # ==========================================
    # PURCHASE
    # ==========================================
    
    async def create_checkout_session(
        self,
        organization_id: str,
        pack_id: str,
        user_email: str,
        success_url: str,
        cancel_url: str
    ) -> Dict[str, Any]:
        """
        Create Stripe Checkout session for credit pack purchase
        
        Args:
            organization_id: Organization UUID
            pack_id: Pack type (e.g., 'boost_100', 'boost_300', 'boost_600')
            user_email: User's email
            success_url: Redirect URL after success
            cancel_url: Redirect URL after cancel
            
        Returns:
            {"checkout_url": str, "session_id": str}
        """
        try:
            # Validate pack
            if pack_id not in CREDIT_PACK_CONFIG:
                raise ValueError(f"Invalid pack: {pack_id}. Available: {list(CREDIT_PACK_CONFIG.keys())}")
            
            pack_config = CREDIT_PACK_CONFIG[pack_id]
            stripe_price_id = os.getenv(pack_config["stripe_price_env"])
            
            if not stripe_price_id:
                raise ValueError(f"Stripe price not configured for pack: {pack_id}. Set {pack_config['stripe_price_env']} in environment.")
            
            # Get or create Stripe customer
            stripe_customer_id = await self._get_stripe_customer(organization_id, user_email)
            
            # Create checkout session for one-time payment
            session = self.stripe.checkout.Session.create(
                customer=stripe_customer_id,
                payment_method_types=["card", "ideal", "bancontact"],
                line_items=[{
                    "price": stripe_price_id,
                    "quantity": 1,
                }],
                mode="payment",  # One-time payment, not subscription
                success_url=success_url + "?session_id={CHECKOUT_SESSION_ID}&type=credit_pack",
                cancel_url=cancel_url,
                metadata={
                    "type": "credit_pack",
                    "organization_id": organization_id,
                    "pack_id": pack_id,
                    "credits": pack_config["credits"],
                    # Legacy field for backwards compatibility
                    "flows": pack_config["credits"],
                },
                allow_promotion_codes=True,
            )
            
            logger.info(f"Created credit pack checkout {session.id} for org {organization_id}, pack: {pack_id}")
            
            return {
                "checkout_url": session.url,
                "session_id": session.id,
            }
            
        except stripe.error.StripeError as e:
            logger.error(f"Stripe error creating credit pack checkout: {e}")
            raise
        except Exception as e:
            logger.error(f"Error creating credit pack checkout: {e}")
            raise
    
    async def _get_stripe_customer(self, organization_id: str, email: str) -> str:
        """Get existing Stripe customer ID from subscription"""
        try:
            response = self.supabase.table("organization_subscriptions").select(
                "stripe_customer_id"
            ).eq("organization_id", organization_id).maybe_single().execute()
            
            if response.data and response.data.get("stripe_customer_id"):
                return response.data["stripe_customer_id"]
            
            # Create new customer if none exists
            customer = self.stripe.Customer.create(
                email=email,
                metadata={"organization_id": organization_id}
            )
            
            # Save customer ID
            self.supabase.table("organization_subscriptions").upsert({
                "organization_id": organization_id,
                "stripe_customer_id": customer.id,
                "plan_id": "free",
                "status": "active",
            }, on_conflict="organization_id").execute()
            
            return customer.id
            
        except Exception as e:
            logger.error(f"Error getting Stripe customer: {e}")
            raise
    
    # ==========================================
    # WEBHOOK HANDLER
    # ==========================================
    
    async def handle_checkout_completed(self, session: Dict[str, Any]) -> None:
        """
        Handle checkout.session.completed webhook for credit pack purchase
        
        Called from webhooks router when type=credit_pack or type=flow_pack
        """
        try:
            metadata = session.get("metadata", {})
            
            # Support both new and legacy types
            if metadata.get("type") not in ("credit_pack", "flow_pack"):
                return  # Not a credit pack purchase
            
            organization_id = metadata.get("organization_id")
            pack_id = metadata.get("pack_id")
            # Support both "credits" and legacy "flows"
            credits = int(metadata.get("credits") or metadata.get("flows", 0))
            
            if not organization_id or not credits:
                logger.error("Missing organization_id or credits in credit pack checkout")
                return
            
            pack_config = CREDIT_PACK_CONFIG.get(pack_id, {})
            price_cents = pack_config.get("price_cents", 0)
            
            # Create credit pack record (stored as flow_packs for backwards compatibility)
            self.supabase.table("flow_packs").insert({
                "organization_id": organization_id,
                "flows_purchased": credits,
                "flows_remaining": credits,
                "price_cents": price_cents,
                "stripe_checkout_session_id": session.get("id"),
                "stripe_payment_intent_id": session.get("payment_intent"),
                "status": "active",
                "purchased_at": datetime.utcnow().isoformat(),
            }).execute()
            
            logger.info(f"Credit pack created: {credits} credits for org {organization_id} (pack: {pack_id})")
            
        except Exception as e:
            logger.error(f"Error handling credit pack checkout: {e}")
            raise
    
    # ==========================================
    # ADMIN / LISTING
    # ==========================================
    
    async def get_purchase_history(
        self,
        organization_id: str,
        limit: int = 10
    ) -> List[Dict[str, Any]]:
        """Get credit pack purchase history"""
        try:
            response = self.supabase.table("flow_packs").select(
                "id, flows_purchased, flows_remaining, price_cents, status, purchased_at, depleted_at"
            ).eq(
                "organization_id", organization_id
            ).order(
                "purchased_at", desc=True
            ).limit(limit).execute()
            
            return response.data or []
            
        except Exception as e:
            logger.error(f"Error getting credit pack history: {e}")
            return []
    
    async def get_available_packs(self) -> List[Dict[str, Any]]:
        """Get available credit pack products for purchase"""
        # Return configured packs (excluding legacy pack_5)
        return [
            {
                "id": "boost_100",
                "name": "Boost 100",
                "credits": 100,
                "price_cents": 1495,
                "per_credit_cents": 15,  # €0.15
                "description": "~3-4 complete sales cycles",
            },
            {
                "id": "boost_300",
                "name": "Boost 300",
                "credits": 300,
                "price_cents": 3995,
                "per_credit_cents": 13,  # €0.13
                "description": "~10 complete sales cycles",
                "popular": True,
            },
            {
                "id": "boost_600",
                "name": "Boost 600",
                "credits": 600,
                "price_cents": 6995,
                "per_credit_cents": 12,  # €0.12
                "description": "~21 complete sales cycles",
                "best_value": True,
            },
        ]


# Singleton instance
_flow_pack_service: Optional[FlowPackService] = None


def get_flow_pack_service() -> FlowPackService:
    """Get or create credit pack service instance"""
    global _flow_pack_service
    if _flow_pack_service is None:
        _flow_pack_service = FlowPackService()
    return _flow_pack_service


# Alias for clarity
get_credit_pack_service = get_flow_pack_service
