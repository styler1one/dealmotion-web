"""
Affiliate Service

Central service for managing the DealMotion Affiliate Program.
Handles affiliate registration, referral tracking, commission calculation,
and Stripe Connect integration for automated payouts.

Key features:
- Affiliate registration with unique referral codes
- Click tracking with 30-day attribution window
- Commission calculation (15% subscriptions, 10% credit packs)
- 14-day refund window before commission approval
- Stripe Connect Express for automated payouts
"""

import os
import logging
import secrets
import string
from decimal import Decimal
from typing import Optional, Dict, Any, List, Tuple
from datetime import datetime, timedelta
import stripe

from app.database import get_supabase_service

logger = logging.getLogger(__name__)

# Initialize Stripe
stripe.api_key = os.getenv("STRIPE_SECRET_KEY")

# =============================================================================
# CONFIGURATION
# =============================================================================

# Commission rates (can be overridden per affiliate)
DEFAULT_COMMISSION_RATE_SUBSCRIPTION = Decimal("0.15")  # 15%
DEFAULT_COMMISSION_RATE_CREDITS = Decimal("0.10")       # 10%

# Payout settings
DEFAULT_MINIMUM_PAYOUT_CENTS = 5000  # €50
REFUND_WINDOW_DAYS = 14  # Days before commission is approved
ATTRIBUTION_WINDOW_DAYS = 30  # Cookie/click attribution window

# Stripe Connect
STRIPE_CONNECT_CLIENT_ID = os.getenv("STRIPE_CONNECT_CLIENT_ID")

# Auto-approve new affiliates (set to False for manual review)
AUTO_APPROVE_AFFILIATES = os.getenv("AFFILIATE_AUTO_APPROVE", "true").lower() == "true"


class AffiliateService:
    """
    Central affiliate management service.
    
    Usage:
        affiliate_service = get_affiliate_service()
        
        # Check if user is an affiliate
        affiliate = await affiliate_service.get_affiliate_by_user(user_id)
        
        # Apply to become affiliate
        affiliate = await affiliate_service.apply_to_become_affiliate(
            user_id=user_id,
            organization_id=org_id,
            application_notes="I'm a sales trainer..."
        )
        
        # Track a click
        await affiliate_service.track_click(
            affiliate_code="AFF_X7K2M9",
            click_id="...",
            landing_page="/signup",
            ip_address="1.2.3.4"
        )
        
        # Record a referral (on signup)
        await affiliate_service.record_referral(
            affiliate_code="AFF_X7K2M9",
            referred_user_id=user_id,
            referred_email="user@example.com",
            click_id="..."
        )
        
        # Process commission (on payment)
        await affiliate_service.create_commission(
            referral_id=referral_id,
            payment_type="subscription",
            payment_amount_cents=7500,
            stripe_invoice_id="in_xxx"
        )
    """
    
    def __init__(self):
        self.supabase = get_supabase_service()
        if self.supabase is None:
            logger.error("Failed to initialize Supabase client for AffiliateService")
        self.stripe = stripe
    
    # =========================================================================
    # AFFILIATE MANAGEMENT
    # =========================================================================
    
    async def get_affiliate_by_user(self, user_id: str) -> Optional[Dict[str, Any]]:
        """Get affiliate record for a user, if they are an affiliate."""
        try:
            if self.supabase is None:
                logger.error("Supabase client not initialized")
                return None
            
            # Debug: Check if we can access the table
            logger.debug(f"Querying affiliates table for user_id={user_id}")
            
            response = self.supabase.table("affiliates").select("*").eq(
                "user_id", user_id
            ).maybe_single().execute()
            
            if response is None:
                logger.warning("Supabase returned None response - affiliates table may not exist")
                return None
            
            # Check for API errors in response
            if hasattr(response, 'error') and response.error:
                logger.error(f"Supabase API error: {response.error}")
                return None
                
            return response.data
        except Exception as e:
            logger.error(f"Error getting affiliate by user: {e}", exc_info=True)
            return None
    
    async def get_affiliate_by_code(self, affiliate_code: str) -> Optional[Dict[str, Any]]:
        """Get affiliate record by referral code."""
        try:
            response = self.supabase.table("affiliates").select("*").eq(
                "affiliate_code", affiliate_code
            ).eq(
                "status", "active"
            ).maybe_single().execute()
            
            return response.data
        except Exception as e:
            logger.error(f"Error getting affiliate by code: {e}")
            return None
    
    async def get_affiliate_by_id(self, affiliate_id: str) -> Optional[Dict[str, Any]]:
        """Get affiliate record by ID."""
        try:
            response = self.supabase.table("affiliates").select("*").eq(
                "id", affiliate_id
            ).maybe_single().execute()
            
            return response.data
        except Exception as e:
            logger.error(f"Error getting affiliate by ID: {e}")
            return None
    
    async def validate_affiliate_code(self, affiliate_code: str) -> Tuple[bool, Optional[str]]:
        """
        Validate if an affiliate code exists and is active.
        
        Returns:
            Tuple of (is_valid, affiliate_display_name or None)
        """
        try:
            response = self.supabase.table("affiliates").select(
                "id, status, user_id"
            ).eq(
                "affiliate_code", affiliate_code
            ).maybe_single().execute()
            
            if not response.data:
                return False, None
            
            if response.data.get("status") != "active":
                return False, None
            
            # Get affiliate's first name for display
            user_response = self.supabase.table("users").select(
                "full_name"
            ).eq(
                "id", response.data["user_id"]
            ).maybe_single().execute()
            
            display_name = None
            if user_response.data and user_response.data.get("full_name"):
                # Only show first name for privacy
                full_name = user_response.data["full_name"]
                display_name = full_name.split()[0] if full_name else None
            
            return True, display_name
            
        except Exception as e:
            logger.error(f"Error validating affiliate code: {e}")
            return False, None
    
    async def apply_to_become_affiliate(
        self,
        user_id: str,
        organization_id: str,
        application_notes: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Apply to become an affiliate.
        
        Args:
            user_id: The user applying
            organization_id: Their organization
            application_notes: Why they want to join, how they'll promote
            
        Returns:
            The created affiliate record
            
        Raises:
            ValueError: If user cannot become an affiliate
        """
        try:
            # Check if user can become affiliate
            can_apply = await self._can_user_become_affiliate(user_id)
            if not can_apply["allowed"]:
                raise ValueError(can_apply["reason"])
            
            # Generate unique affiliate code
            affiliate_code = await self._generate_affiliate_code()
            
            # Determine initial status
            initial_status = "active" if AUTO_APPROVE_AFFILIATES else "pending"
            activated_at = datetime.utcnow().isoformat() if AUTO_APPROVE_AFFILIATES else None
            
            # Create affiliate record
            affiliate_data = {
                "user_id": user_id,
                "organization_id": organization_id,
                "affiliate_code": affiliate_code,
                "status": initial_status,
                "commission_rate_subscription": float(DEFAULT_COMMISSION_RATE_SUBSCRIPTION),
                "commission_rate_credits": float(DEFAULT_COMMISSION_RATE_CREDITS),
                "minimum_payout_cents": DEFAULT_MINIMUM_PAYOUT_CENTS,
                "application_notes": application_notes,
                "activated_at": activated_at,
            }
            
            if self.supabase is None:
                raise ValueError("Database connection not available")
            
            response = self.supabase.table("affiliates").insert(
                affiliate_data
            ).execute()
            
            if response is None:
                raise ValueError("Failed to create affiliate - database may not be ready")
            
            affiliate = response.data[0] if response.data else None
            
            if affiliate:
                # Log event
                await self._log_event(
                    affiliate_id=affiliate["id"],
                    event_type="application_submitted",
                    event_data={
                        "auto_approved": AUTO_APPROVE_AFFILIATES,
                        "status": initial_status,
                    },
                    actor_type="user",
                    actor_id=user_id
                )
                
                logger.info(
                    f"New affiliate application: user={user_id}, "
                    f"code={affiliate_code}, status={initial_status}"
                )
            
            return affiliate
            
        except ValueError:
            raise
        except Exception as e:
            logger.error(f"Error creating affiliate: {e}")
            raise
    
    async def update_affiliate_status(
        self,
        affiliate_id: str,
        status: str,
        reason: Optional[str] = None,
        admin_id: Optional[str] = None
    ) -> bool:
        """Update affiliate status (for admin use)."""
        try:
            update_data = {
                "status": status,
                "status_reason": reason,
            }
            
            if status == "active":
                update_data["activated_at"] = datetime.utcnow().isoformat()
            
            self.supabase.table("affiliates").update(
                update_data
            ).eq("id", affiliate_id).execute()
            
            # Log event
            await self._log_event(
                affiliate_id=affiliate_id,
                event_type=f"status_changed_to_{status}",
                event_data={"reason": reason},
                actor_type="admin" if admin_id else "system",
                actor_id=admin_id
            )
            
            logger.info(f"Affiliate {affiliate_id} status changed to {status}")
            return True
            
        except Exception as e:
            logger.error(f"Error updating affiliate status: {e}")
            return False
    
    # =========================================================================
    # CLICK TRACKING
    # =========================================================================
    
    async def track_click(
        self,
        affiliate_code: str,
        click_id: str,
        landing_page: Optional[str] = None,
        referrer_url: Optional[str] = None,
        ip_address: Optional[str] = None,
        user_agent: Optional[str] = None,
        utm_source: Optional[str] = None,
        utm_medium: Optional[str] = None,
        utm_campaign: Optional[str] = None
    ) -> bool:
        """
        Track an affiliate link click.
        
        Args:
            affiliate_code: The affiliate's referral code
            click_id: Client-generated UUID for this click
            landing_page: The page they landed on
            referrer_url: Where they came from
            ip_address: For fraud detection
            user_agent: For fraud detection
            
        Returns:
            True if click was recorded, False otherwise
        """
        try:
            # Get affiliate
            affiliate = await self.get_affiliate_by_code(affiliate_code)
            if not affiliate:
                logger.warning(f"Click with invalid affiliate code: {affiliate_code}")
                return False
            
            # Rate limiting: max 100 clicks per hour per affiliate
            recent_clicks = self.supabase.table("affiliate_clicks").select(
                "id", count="exact"
            ).eq(
                "affiliate_id", affiliate["id"]
            ).gte(
                "created_at", (datetime.utcnow() - timedelta(hours=1)).isoformat()
            ).execute()
            
            if recent_clicks.count and recent_clicks.count > 100:
                logger.warning(f"Rate limit exceeded for affiliate {affiliate['id']}")
                return False
            
            # Check for duplicate click_id
            existing = self.supabase.table("affiliate_clicks").select(
                "id"
            ).eq("click_id", click_id).maybe_single().execute()
            
            if existing.data:
                return True  # Already tracked, not an error
            
            # Insert click record
            click_data = {
                "affiliate_id": affiliate["id"],
                "click_id": click_id,
                "landing_page": landing_page,
                "referrer_url": referrer_url,
                "utm_source": utm_source,
                "utm_medium": utm_medium,
                "utm_campaign": utm_campaign,
                "ip_address": ip_address,
                "user_agent": user_agent[:500] if user_agent else None,  # Truncate
                "expires_at": (datetime.utcnow() + timedelta(days=ATTRIBUTION_WINDOW_DAYS)).isoformat(),
            }
            
            self.supabase.table("affiliate_clicks").insert(click_data).execute()
            
            # Update affiliate stats
            self.supabase.table("affiliates").update({
                "total_clicks": affiliate.get("total_clicks", 0) + 1
            }).eq("id", affiliate["id"]).execute()
            
            return True
            
        except Exception as e:
            logger.error(f"Error tracking click: {e}")
            return False
    
    async def get_click_by_id(self, click_id: str) -> Optional[Dict[str, Any]]:
        """Get click record by click_id."""
        try:
            response = self.supabase.table("affiliate_clicks").select(
                "*, affiliates(id, affiliate_code, user_id)"
            ).eq(
                "click_id", click_id
            ).maybe_single().execute()
            
            return response.data
        except Exception as e:
            logger.error(f"Error getting click: {e}")
            return None
    
    # =========================================================================
    # REFERRAL TRACKING
    # =========================================================================
    
    async def record_referral(
        self,
        affiliate_code: str,
        referred_user_id: str,
        referred_email: str,
        referred_organization_id: Optional[str] = None,
        click_id: Optional[str] = None
    ) -> Optional[Dict[str, Any]]:
        """
        Record a new referral when a user signs up via affiliate link.
        
        Args:
            affiliate_code: The affiliate's referral code
            referred_user_id: The new user's ID
            referred_email: The new user's email
            referred_organization_id: The new user's organization (if known)
            click_id: The click that led to this signup (for attribution)
            
        Returns:
            The created referral record, or None if failed
        """
        try:
            # Get affiliate
            affiliate = await self.get_affiliate_by_code(affiliate_code)
            if not affiliate:
                logger.warning(f"Referral with invalid affiliate code: {affiliate_code}")
                return None
            
            # Anti-fraud: check if user is trying to refer themselves
            if referred_user_id == affiliate["user_id"]:
                logger.warning(f"Self-referral attempt blocked: {referred_user_id}")
                return None
            
            # Check if user was already referred
            existing = self.supabase.table("affiliate_referrals").select(
                "id"
            ).eq("referred_user_id", referred_user_id).maybe_single().execute()
            
            if existing.data:
                logger.info(f"User {referred_user_id} was already referred")
                return None
            
            # Get click record if provided
            click_record = None
            click_uuid = None
            if click_id:
                click_record = await self.get_click_by_id(click_id)
                if click_record:
                    click_uuid = click_record["id"]
                    
                    # Mark click as converted
                    self.supabase.table("affiliate_clicks").update({
                        "converted_to_signup": True,
                        "signup_user_id": referred_user_id,
                        "converted_at": datetime.utcnow().isoformat(),
                    }).eq("id", click_uuid).execute()
            
            # Create referral record
            referral_data = {
                "affiliate_id": affiliate["id"],
                "click_id": click_uuid,
                "referred_user_id": referred_user_id,
                "referred_organization_id": referred_organization_id,
                "referred_email": referred_email,
                "signup_at": datetime.utcnow().isoformat(),
            }
            
            response = self.supabase.table("affiliate_referrals").insert(
                referral_data
            ).execute()
            
            referral = response.data[0] if response.data else None
            
            if referral:
                # Update affiliate stats
                self.supabase.table("affiliates").update({
                    "total_signups": affiliate.get("total_signups", 0) + 1
                }).eq("id", affiliate["id"]).execute()
                
                # Update user record with affiliate reference
                self.supabase.table("users").update({
                    "referred_by_affiliate_id": affiliate["id"],
                    "referral_click_id": click_id,
                }).eq("id", referred_user_id).execute()
                
                # Log event
                await self._log_event(
                    affiliate_id=affiliate["id"],
                    event_type="referral_signup",
                    event_data={
                        "referral_id": referral["id"],
                        "referred_email": referred_email,
                        "had_click": click_record is not None,
                    },
                    actor_type="system"
                )
                
                logger.info(
                    f"New referral recorded: affiliate={affiliate['id']}, "
                    f"referred_user={referred_user_id}"
                )
            
            return referral
            
        except Exception as e:
            logger.error(f"Error recording referral: {e}")
            return None
    
    async def get_referral_by_user(self, user_id: str) -> Optional[Dict[str, Any]]:
        """Get referral record for a user (if they were referred)."""
        try:
            response = self.supabase.table("affiliate_referrals").select(
                "*, affiliates(id, affiliate_code, user_id)"
            ).eq(
                "referred_user_id", user_id
            ).maybe_single().execute()
            
            return response.data
        except Exception as e:
            logger.error(f"Error getting referral by user: {e}")
            return None
    
    async def get_referral_by_organization(self, organization_id: str) -> Optional[Dict[str, Any]]:
        """Get referral record for an organization (for commission attribution)."""
        try:
            response = self.supabase.table("affiliate_referrals").select(
                "*, affiliates(id, affiliate_code, commission_rate_subscription, commission_rate_credits)"
            ).eq(
                "referred_organization_id", organization_id
            ).maybe_single().execute()
            
            return response.data
        except Exception as e:
            logger.error(f"Error getting referral by organization: {e}")
            return None
    
    async def update_referral_organization(
        self,
        referred_user_id: str,
        organization_id: str
    ) -> bool:
        """Update referral with organization ID (called when org is created)."""
        try:
            self.supabase.table("affiliate_referrals").update({
                "referred_organization_id": organization_id
            }).eq("referred_user_id", referred_user_id).execute()
            
            return True
        except Exception as e:
            logger.error(f"Error updating referral organization: {e}")
            return False
    
    # =========================================================================
    # COMMISSION MANAGEMENT
    # =========================================================================
    
    async def create_commission(
        self,
        organization_id: str,
        payment_type: str,
        payment_amount_cents: int,
        stripe_invoice_id: Optional[str] = None,
        stripe_charge_id: Optional[str] = None,
        stripe_payment_intent_id: Optional[str] = None,
        currency: str = "eur"
    ) -> Optional[Dict[str, Any]]:
        """
        Create a commission record for a payment.
        
        Called from invoice.paid webhook when a referred user makes a payment.
        
        Args:
            organization_id: The paying organization
            payment_type: 'subscription' or 'credit_pack'
            payment_amount_cents: Payment amount in cents
            stripe_invoice_id: Stripe invoice ID
            stripe_charge_id: Stripe charge ID
            stripe_payment_intent_id: Stripe payment intent ID
            currency: Currency code (default: eur)
            
        Returns:
            The created commission record, or None if no affiliate attribution
        """
        try:
            # Get referral for this organization
            referral = await self.get_referral_by_organization(organization_id)
            if not referral:
                return None  # No affiliate attribution
            
            affiliate = referral.get("affiliates")
            if not affiliate:
                return None
            
            affiliate_id = affiliate["id"]
            
            # Determine commission rate based on payment type
            if payment_type == "subscription":
                commission_rate = Decimal(str(
                    affiliate.get("commission_rate_subscription", DEFAULT_COMMISSION_RATE_SUBSCRIPTION)
                ))
            else:
                commission_rate = Decimal(str(
                    affiliate.get("commission_rate_credits", DEFAULT_COMMISSION_RATE_CREDITS)
                ))
            
            # Calculate commission
            commission_amount_cents = int(Decimal(payment_amount_cents) * commission_rate)
            
            if commission_amount_cents <= 0:
                return None
            
            # Check for duplicate (same invoice)
            if stripe_invoice_id:
                existing = self.supabase.table("affiliate_commissions").select(
                    "id"
                ).eq("stripe_invoice_id", stripe_invoice_id).maybe_single().execute()
                
                if existing.data:
                    logger.info(f"Commission already exists for invoice {stripe_invoice_id}")
                    return None
            
            # Create commission record
            now = datetime.utcnow()
            commission_data = {
                "affiliate_id": affiliate_id,
                "referral_id": referral["id"],
                "stripe_invoice_id": stripe_invoice_id,
                "stripe_charge_id": stripe_charge_id,
                "stripe_payment_intent_id": stripe_payment_intent_id,
                "payment_type": payment_type,
                "payment_amount_cents": payment_amount_cents,
                "currency": currency,
                "commission_rate": float(commission_rate),
                "commission_amount_cents": commission_amount_cents,
                "status": "pending",
                "payment_at": now.isoformat(),
                "approved_at": (now + timedelta(days=REFUND_WINDOW_DAYS)).isoformat(),
            }
            
            response = self.supabase.table("affiliate_commissions").insert(
                commission_data
            ).execute()
            
            commission = response.data[0] if response.data else None
            
            if commission:
                # Update referral stats
                self.supabase.table("affiliate_referrals").update({
                    "converted": True,
                    "first_payment_at": referral.get("first_payment_at") or now.isoformat(),
                    "lifetime_revenue_cents": (referral.get("lifetime_revenue_cents", 0) or 0) + payment_amount_cents,
                    "lifetime_commission_cents": (referral.get("lifetime_commission_cents", 0) or 0) + commission_amount_cents,
                }).eq("id", referral["id"]).execute()
                
                # Update affiliate stats
                affiliate_record = await self.get_affiliate_by_id(affiliate_id)
                if affiliate_record:
                    # Only increment conversions if this is first payment for this referral
                    conversion_increment = 1 if not referral.get("converted") else 0
                    
                    self.supabase.table("affiliates").update({
                        "total_conversions": affiliate_record.get("total_conversions", 0) + conversion_increment,
                        "total_earned_cents": (affiliate_record.get("total_earned_cents", 0) or 0) + commission_amount_cents,
                    }).eq("id", affiliate_id).execute()
                
                # Log event
                await self._log_event(
                    affiliate_id=affiliate_id,
                    event_type="commission_created",
                    event_data={
                        "commission_id": commission["id"],
                        "payment_type": payment_type,
                        "payment_amount_cents": payment_amount_cents,
                        "commission_amount_cents": commission_amount_cents,
                        "commission_rate": float(commission_rate),
                    },
                    actor_type="stripe"
                )
                
                logger.info(
                    f"Commission created: affiliate={affiliate_id}, "
                    f"amount={commission_amount_cents} cents, type={payment_type}"
                )
            
            return commission
            
        except Exception as e:
            logger.error(f"Error creating commission: {e}")
            return None
    
    async def reverse_commission(
        self,
        stripe_invoice_id: Optional[str] = None,
        stripe_charge_id: Optional[str] = None,
        stripe_refund_id: Optional[str] = None,
        reason: str = "refund"
    ) -> bool:
        """
        Reverse a commission due to refund or chargeback.
        
        Args:
            stripe_invoice_id: The invoice that was refunded
            stripe_charge_id: The charge that was refunded
            stripe_refund_id: The Stripe refund ID
            reason: Reason for reversal ('refund', 'chargeback', 'dispute')
            
        Returns:
            True if commission was reversed, False otherwise
        """
        try:
            # Find commission by invoice or charge
            query = self.supabase.table("affiliate_commissions").select("*")
            
            if stripe_invoice_id:
                query = query.eq("stripe_invoice_id", stripe_invoice_id)
            elif stripe_charge_id:
                query = query.eq("stripe_charge_id", stripe_charge_id)
            else:
                return False
            
            response = query.maybe_single().execute()
            
            if not response.data:
                return False  # No commission to reverse
            
            commission = response.data
            
            # Only reverse if not already paid
            if commission["status"] == "paid":
                logger.warning(
                    f"Cannot reverse paid commission {commission['id']}, "
                    f"will need manual handling"
                )
                # Mark as disputed for manual review
                self.supabase.table("affiliate_commissions").update({
                    "status": "disputed",
                    "reversal_reason": f"Refund after payout: {reason}",
                    "reversed_at": datetime.utcnow().isoformat(),
                    "original_stripe_refund_id": stripe_refund_id,
                }).eq("id", commission["id"]).execute()
                return False
            
            # Reverse the commission
            self.supabase.table("affiliate_commissions").update({
                "status": "reversed",
                "reversal_reason": reason,
                "reversed_at": datetime.utcnow().isoformat(),
                "original_stripe_refund_id": stripe_refund_id,
            }).eq("id", commission["id"]).execute()
            
            # Update affiliate stats if commission was approved
            if commission["status"] == "approved":
                affiliate = await self.get_affiliate_by_id(commission["affiliate_id"])
                if affiliate:
                    self.supabase.table("affiliates").update({
                        "current_balance_cents": max(0, 
                            (affiliate.get("current_balance_cents", 0) or 0) - commission["commission_amount_cents"]
                        ),
                    }).eq("id", affiliate["id"]).execute()
            
            # Log event
            await self._log_event(
                affiliate_id=commission["affiliate_id"],
                event_type="commission_reversed",
                event_data={
                    "commission_id": commission["id"],
                    "reason": reason,
                    "amount_cents": commission["commission_amount_cents"],
                },
                actor_type="stripe"
            )
            
            logger.info(f"Commission {commission['id']} reversed: {reason}")
            return True
            
        except Exception as e:
            logger.error(f"Error reversing commission: {e}")
            return False
    
    async def approve_pending_commissions(self) -> int:
        """
        Approve pending commissions that have passed the refund window.
        
        Called by daily Inngest job.
        
        Returns:
            Number of commissions approved
        """
        try:
            now = datetime.utcnow()
            
            # Find pending commissions past their approval date
            response = self.supabase.table("affiliate_commissions").select(
                "id, affiliate_id, commission_amount_cents"
            ).eq(
                "status", "pending"
            ).lte(
                "approved_at", now.isoformat()
            ).execute()
            
            if not response.data:
                return 0
            
            approved_count = 0
            
            for commission in response.data:
                # Update commission status
                self.supabase.table("affiliate_commissions").update({
                    "status": "approved",
                }).eq("id", commission["id"]).execute()
                
                # Add to affiliate balance
                affiliate = await self.get_affiliate_by_id(commission["affiliate_id"])
                if affiliate:
                    self.supabase.table("affiliates").update({
                        "current_balance_cents": (
                            (affiliate.get("current_balance_cents", 0) or 0) + 
                            commission["commission_amount_cents"]
                        ),
                    }).eq("id", affiliate["id"]).execute()
                
                approved_count += 1
            
            if approved_count > 0:
                logger.info(f"Approved {approved_count} pending commissions")
            
            return approved_count
            
        except Exception as e:
            logger.error(f"Error approving commissions: {e}")
            return 0
    
    # =========================================================================
    # STRIPE CONNECT
    # =========================================================================
    
    async def create_connect_account(self, affiliate_id: str, email: str) -> Optional[str]:
        """
        Create a Stripe Connect Express account for an affiliate.
        
        Returns:
            The Stripe account ID, or None if failed
        """
        try:
            # Create Express account
            account = self.stripe.Account.create(
                type="express",
                country="NL",
                email=email,
                capabilities={
                    "transfers": {"requested": True},
                },
                business_type="individual",
                metadata={
                    "affiliate_id": affiliate_id,
                    "platform": "dealmotion",
                },
                settings={
                    "payouts": {
                        "schedule": {
                            "interval": "manual"
                        }
                    }
                }
            )
            
            # Update affiliate record
            self.supabase.table("affiliates").update({
                "stripe_connect_account_id": account.id,
                "stripe_connect_status": "pending",
            }).eq("id", affiliate_id).execute()
            
            # Log event
            await self._log_event(
                affiliate_id=affiliate_id,
                event_type="connect_account_created",
                event_data={"stripe_account_id": account.id},
                actor_type="system"
            )
            
            logger.info(f"Created Stripe Connect account {account.id} for affiliate {affiliate_id}")
            return account.id
            
        except Exception as e:
            logger.error(f"Error creating Connect account: {e}")
            return None
    
    async def get_connect_onboarding_url(
        self,
        affiliate_id: str,
        return_url: str,
        refresh_url: str
    ) -> Optional[str]:
        """
        Get Stripe Connect onboarding URL for an affiliate.
        
        Args:
            affiliate_id: The affiliate ID
            return_url: URL to redirect after completion
            refresh_url: URL if link expires
            
        Returns:
            The onboarding URL, or None if failed
        """
        try:
            affiliate = await self.get_affiliate_by_id(affiliate_id)
            if not affiliate:
                return None
            
            account_id = affiliate.get("stripe_connect_account_id")
            
            # Create account if doesn't exist
            if not account_id:
                # Get user email
                user_response = self.supabase.table("users").select(
                    "email"
                ).eq("id", affiliate["user_id"]).maybe_single().execute()
                
                if not user_response.data:
                    return None
                
                account_id = await self.create_connect_account(
                    affiliate_id=affiliate_id,
                    email=user_response.data["email"]
                )
                
                if not account_id:
                    return None
            
            # Create account link
            account_link = self.stripe.AccountLink.create(
                account=account_id,
                refresh_url=refresh_url,
                return_url=return_url,
                type="account_onboarding",
            )
            
            return account_link.url
            
        except Exception as e:
            logger.error(f"Error getting onboarding URL: {e}")
            return None
    
    async def sync_connect_account_status(self, affiliate_id: str) -> bool:
        """
        Sync Stripe Connect account status from Stripe.
        
        Called by hourly Inngest job or webhook.
        """
        try:
            affiliate = await self.get_affiliate_by_id(affiliate_id)
            if not affiliate or not affiliate.get("stripe_connect_account_id"):
                return False
            
            account_id = affiliate["stripe_connect_account_id"]
            
            # Get account from Stripe
            account = self.stripe.Account.retrieve(account_id)
            
            # Determine status
            if account.get("details_submitted") and account.get("payouts_enabled"):
                status = "active"
            elif account.get("requirements", {}).get("disabled_reason"):
                status = "disabled"
            elif account.get("requirements", {}).get("currently_due"):
                status = "restricted"
            else:
                status = "pending"
            
            # Update affiliate
            self.supabase.table("affiliates").update({
                "stripe_connect_status": status,
                "stripe_payouts_enabled": account.get("payouts_enabled", False),
                "stripe_charges_enabled": account.get("charges_enabled", False),
            }).eq("id", affiliate_id).execute()
            
            return True
            
        except Exception as e:
            logger.error(f"Error syncing Connect status: {e}")
            return False
    
    async def create_payout_transfer(
        self,
        affiliate_id: str,
        amount_cents: int,
        payout_id: str
    ) -> Optional[str]:
        """
        Create a Stripe Transfer to affiliate's Connect account.
        
        Args:
            affiliate_id: The affiliate ID
            amount_cents: Amount to transfer in cents
            payout_id: Our payout record ID
            
        Returns:
            Stripe transfer ID, or None if failed
        """
        try:
            affiliate = await self.get_affiliate_by_id(affiliate_id)
            if not affiliate:
                return None
            
            account_id = affiliate.get("stripe_connect_account_id")
            if not account_id:
                logger.error(f"Affiliate {affiliate_id} has no Connect account")
                return None
            
            if not affiliate.get("stripe_payouts_enabled"):
                logger.error(f"Affiliate {affiliate_id} Connect account not ready for payouts")
                return None
            
            # Create transfer
            transfer = self.stripe.Transfer.create(
                amount=amount_cents,
                currency="eur",
                destination=account_id,
                metadata={
                    "affiliate_id": affiliate_id,
                    "payout_id": payout_id,
                    "platform": "dealmotion",
                },
                description="DealMotion affiliate commission payout"
            )
            
            logger.info(
                f"Created transfer {transfer.id} for affiliate {affiliate_id}, "
                f"amount={amount_cents} cents"
            )
            
            return transfer.id
            
        except Exception as e:
            logger.error(f"Error creating transfer: {e}")
            return None
    
    # =========================================================================
    # PAYOUT MANAGEMENT
    # =========================================================================
    
    async def process_payout(self, affiliate_id: str) -> Optional[Dict[str, Any]]:
        """
        Process payout for an affiliate.
        
        Aggregates all approved commissions and creates a single payout.
        
        Returns:
            The created payout record, or None if no eligible commissions
        """
        try:
            affiliate = await self.get_affiliate_by_id(affiliate_id)
            if not affiliate:
                return None
            
            # Check if eligible for payout
            balance = affiliate.get("current_balance_cents", 0) or 0
            minimum = affiliate.get("minimum_payout_cents", DEFAULT_MINIMUM_PAYOUT_CENTS)
            
            if balance < minimum:
                logger.info(
                    f"Affiliate {affiliate_id} balance ({balance}) below minimum ({minimum})"
                )
                return None
            
            if not affiliate.get("stripe_payouts_enabled"):
                logger.warning(f"Affiliate {affiliate_id} Connect not ready for payouts")
                return None
            
            # Get approved commissions
            commissions_response = self.supabase.table("affiliate_commissions").select(
                "id, commission_amount_cents"
            ).eq(
                "affiliate_id", affiliate_id
            ).eq(
                "status", "approved"
            ).execute()
            
            commissions = commissions_response.data or []
            if not commissions:
                return None
            
            total_amount = sum(c["commission_amount_cents"] for c in commissions)
            
            # Create payout record
            payout_data = {
                "affiliate_id": affiliate_id,
                "amount_cents": total_amount,
                "currency": "eur",
                "commission_count": len(commissions),
                "status": "pending",
                "scheduled_for": datetime.utcnow().isoformat(),
            }
            
            payout_response = self.supabase.table("affiliate_payouts").insert(
                payout_data
            ).execute()
            
            payout = payout_response.data[0] if payout_response.data else None
            
            if not payout:
                return None
            
            # Create Stripe transfer
            transfer_id = await self.create_payout_transfer(
                affiliate_id=affiliate_id,
                amount_cents=total_amount,
                payout_id=payout["id"]
            )
            
            if transfer_id:
                # Update payout with transfer ID
                self.supabase.table("affiliate_payouts").update({
                    "stripe_transfer_id": transfer_id,
                    "status": "processing",
                    "initiated_at": datetime.utcnow().isoformat(),
                }).eq("id", payout["id"]).execute()
                
                # Update commissions with payout ID
                commission_ids = [c["id"] for c in commissions]
                self.supabase.table("affiliate_commissions").update({
                    "payout_id": payout["id"],
                    "status": "processing",
                }).in_("id", commission_ids).execute()
                
                # Log event
                await self._log_event(
                    affiliate_id=affiliate_id,
                    event_type="payout_initiated",
                    event_data={
                        "payout_id": payout["id"],
                        "amount_cents": total_amount,
                        "commission_count": len(commissions),
                        "stripe_transfer_id": transfer_id,
                    },
                    actor_type="system"
                )
            else:
                # Transfer failed
                self.supabase.table("affiliate_payouts").update({
                    "status": "failed",
                    "failure_reason": "Failed to create Stripe transfer",
                    "failed_at": datetime.utcnow().isoformat(),
                }).eq("id", payout["id"]).execute()
                
                return None
            
            return payout
            
        except Exception as e:
            logger.error(f"Error processing payout: {e}")
            return None
    
    async def handle_transfer_updated(self, transfer: Dict[str, Any]) -> bool:
        """
        Handle Stripe transfer.updated webhook.
        
        Updates payout and commission status based on transfer outcome.
        """
        try:
            transfer_id = transfer.get("id")
            status = transfer.get("status")  # 'pending', 'paid', 'failed', 'canceled'
            
            # Find payout by transfer ID
            payout_response = self.supabase.table("affiliate_payouts").select(
                "*"
            ).eq(
                "stripe_transfer_id", transfer_id
            ).maybe_single().execute()
            
            if not payout_response.data:
                return False
            
            payout = payout_response.data
            
            if status == "paid":
                # Update payout
                self.supabase.table("affiliate_payouts").update({
                    "status": "succeeded",
                    "completed_at": datetime.utcnow().isoformat(),
                }).eq("id", payout["id"]).execute()
                
                # Update commissions
                self.supabase.table("affiliate_commissions").update({
                    "status": "paid",
                    "paid_at": datetime.utcnow().isoformat(),
                }).eq("payout_id", payout["id"]).execute()
                
                # Update affiliate stats
                affiliate = await self.get_affiliate_by_id(payout["affiliate_id"])
                if affiliate:
                    self.supabase.table("affiliates").update({
                        "total_paid_cents": (affiliate.get("total_paid_cents", 0) or 0) + payout["amount_cents"],
                        "current_balance_cents": 0,  # Reset balance after payout
                    }).eq("id", affiliate["id"]).execute()
                
                # Log event
                await self._log_event(
                    affiliate_id=payout["affiliate_id"],
                    event_type="payout_completed",
                    event_data={
                        "payout_id": payout["id"],
                        "amount_cents": payout["amount_cents"],
                    },
                    actor_type="stripe"
                )
                
            elif status in ("failed", "canceled"):
                # Update payout
                self.supabase.table("affiliate_payouts").update({
                    "status": "failed",
                    "failure_reason": transfer.get("failure_message") or f"Transfer {status}",
                    "failed_at": datetime.utcnow().isoformat(),
                    "retry_count": payout.get("retry_count", 0) + 1,
                }).eq("id", payout["id"]).execute()
                
                # Revert commissions to approved
                self.supabase.table("affiliate_commissions").update({
                    "status": "approved",
                    "payout_id": None,
                }).eq("payout_id", payout["id"]).execute()
                
                # Log event
                await self._log_event(
                    affiliate_id=payout["affiliate_id"],
                    event_type="payout_failed",
                    event_data={
                        "payout_id": payout["id"],
                        "reason": transfer.get("failure_message"),
                    },
                    actor_type="stripe"
                )
            
            return True
            
        except Exception as e:
            logger.error(f"Error handling transfer update: {e}")
            return False
    
    # =========================================================================
    # DASHBOARD & STATS
    # =========================================================================
    
    async def get_dashboard_data(self, affiliate_id: str) -> Dict[str, Any]:
        """Get all data needed for affiliate dashboard."""
        try:
            affiliate = await self.get_affiliate_by_id(affiliate_id)
            if not affiliate:
                return {}
            
            # Get recent referrals
            referrals_response = self.supabase.table("affiliate_referrals").select(
                "id, referred_email, signup_at, converted, first_payment_at, lifetime_revenue_cents, lifetime_commission_cents, status"
            ).eq(
                "affiliate_id", affiliate_id
            ).order(
                "signup_at", desc=True
            ).limit(10).execute()
            
            # Get recent commissions
            commissions_response = self.supabase.table("affiliate_commissions").select(
                "id, payment_type, payment_amount_cents, commission_amount_cents, status, payment_at"
            ).eq(
                "affiliate_id", affiliate_id
            ).order(
                "payment_at", desc=True
            ).limit(10).execute()
            
            # Get recent payouts
            payouts_response = self.supabase.table("affiliate_payouts").select(
                "id, amount_cents, commission_count, status, completed_at, created_at"
            ).eq(
                "affiliate_id", affiliate_id
            ).order(
                "created_at", desc=True
            ).limit(5).execute()
            
            # Calculate pending commissions
            pending_response = self.supabase.table("affiliate_commissions").select(
                "commission_amount_cents"
            ).eq(
                "affiliate_id", affiliate_id
            ).eq(
                "status", "pending"
            ).execute()
            
            pending_amount = sum(
                c["commission_amount_cents"] for c in (pending_response.data or [])
            )
            
            return {
                "affiliate": {
                    "id": affiliate["id"],
                    "affiliate_code": affiliate["affiliate_code"],
                    "referral_url": f"https://www.dealmotion.ai/signup?ref={affiliate['affiliate_code']}",
                    "status": affiliate["status"],
                    "stripe_connect_status": affiliate.get("stripe_connect_status", "not_connected"),
                    "stripe_payouts_enabled": affiliate.get("stripe_payouts_enabled", False),
                },
                "stats": {
                    "total_clicks": affiliate.get("total_clicks", 0),
                    "total_signups": affiliate.get("total_signups", 0),
                    "total_conversions": affiliate.get("total_conversions", 0),
                    "conversion_rate": round(
                        (affiliate.get("total_conversions", 0) / affiliate.get("total_signups", 1)) * 100, 1
                    ) if affiliate.get("total_signups", 0) > 0 else 0,
                    "total_earned_cents": affiliate.get("total_earned_cents", 0),
                    "total_paid_cents": affiliate.get("total_paid_cents", 0),
                    "current_balance_cents": affiliate.get("current_balance_cents", 0),
                    "pending_commissions_cents": pending_amount,
                },
                "recent_referrals": referrals_response.data or [],
                "recent_commissions": commissions_response.data or [],
                "recent_payouts": payouts_response.data or [],
            }
            
        except Exception as e:
            logger.error(f"Error getting dashboard data: {e}")
            return {}
    
    async def get_referrals(
        self,
        affiliate_id: str,
        page: int = 1,
        page_size: int = 20,
        status: Optional[str] = None
    ) -> Tuple[List[Dict[str, Any]], int]:
        """Get paginated referrals for an affiliate."""
        try:
            query = self.supabase.table("affiliate_referrals").select(
                "*", count="exact"
            ).eq("affiliate_id", affiliate_id)
            
            if status:
                query = query.eq("status", status)
            
            offset = (page - 1) * page_size
            response = query.order(
                "signup_at", desc=True
            ).range(offset, offset + page_size - 1).execute()
            
            return response.data or [], response.count or 0
            
        except Exception as e:
            logger.error(f"Error getting referrals: {e}")
            return [], 0
    
    async def get_commissions(
        self,
        affiliate_id: str,
        page: int = 1,
        page_size: int = 20,
        status: Optional[str] = None
    ) -> Tuple[List[Dict[str, Any]], int]:
        """Get paginated commissions for an affiliate."""
        try:
            query = self.supabase.table("affiliate_commissions").select(
                "*", count="exact"
            ).eq("affiliate_id", affiliate_id)
            
            if status:
                query = query.eq("status", status)
            
            offset = (page - 1) * page_size
            response = query.order(
                "payment_at", desc=True
            ).range(offset, offset + page_size - 1).execute()
            
            return response.data or [], response.count or 0
            
        except Exception as e:
            logger.error(f"Error getting commissions: {e}")
            return [], 0
    
    async def get_payouts(
        self,
        affiliate_id: str,
        page: int = 1,
        page_size: int = 20
    ) -> Tuple[List[Dict[str, Any]], int]:
        """Get paginated payouts for an affiliate."""
        try:
            offset = (page - 1) * page_size
            response = self.supabase.table("affiliate_payouts").select(
                "*", count="exact"
            ).eq(
                "affiliate_id", affiliate_id
            ).order(
                "created_at", desc=True
            ).range(offset, offset + page_size - 1).execute()
            
            return response.data or [], response.count or 0
            
        except Exception as e:
            logger.error(f"Error getting payouts: {e}")
            return [], 0
    
    # =========================================================================
    # PRIVATE HELPERS
    # =========================================================================
    
    async def _can_user_become_affiliate(self, user_id: str) -> Dict[str, Any]:
        """Check if user can become an affiliate."""
        try:
            if self.supabase is None:
                return {"allowed": False, "reason": "Database connection not available"}
            
            # Check if already an affiliate
            existing = self.supabase.table("affiliates").select(
                "id"
            ).eq("user_id", user_id).maybe_single().execute()
            
            if existing and existing.data:
                return {"allowed": False, "reason": "User is already an affiliate"}
            
            # Check if user was referred (can't be affiliate if referred)
            referral = self.supabase.table("affiliate_referrals").select(
                "id"
            ).eq("referred_user_id", user_id).maybe_single().execute()
            
            if referral and referral.data:
                return {"allowed": False, "reason": "Referred users cannot become affiliates"}
            
            return {"allowed": True, "reason": None}
        except Exception as e:
            logger.error(f"Error checking if user can become affiliate: {e}", exc_info=True)
            return {"allowed": False, "reason": f"Error checking eligibility: {str(e)}"}
    
    async def _generate_affiliate_code(self) -> str:
        """Generate a unique affiliate code."""
        chars = string.ascii_uppercase + string.digits
        
        for _ in range(10):  # Max 10 attempts
            code = "AFF_" + "".join(secrets.choice(chars) for _ in range(6))
            
            try:
                # Check if exists
                existing = self.supabase.table("affiliates").select(
                    "id"
                ).eq("affiliate_code", code).maybe_single().execute()
                
                if not existing or not existing.data:
                    return code
            except Exception as e:
                logger.warning(f"Error checking affiliate code uniqueness: {e}")
                # If we can't check, assume it's unique
                return code
        
        # Fallback: use timestamp
        return f"AFF_{int(datetime.utcnow().timestamp())}"
    
    async def _log_event(
        self,
        affiliate_id: Optional[str],
        event_type: str,
        event_data: Dict[str, Any],
        actor_type: str,
        actor_id: Optional[str] = None,
        ip_address: Optional[str] = None
    ) -> None:
        """Log an affiliate event for audit trail."""
        try:
            self.supabase.table("affiliate_events").insert({
                "affiliate_id": affiliate_id,
                "event_type": event_type,
                "event_data": event_data,
                "actor_type": actor_type,
                "actor_id": actor_id,
                "ip_address": ip_address,
            }).execute()
        except Exception as e:
            logger.error(f"Error logging affiliate event: {e}")


# =============================================================================
# SINGLETON FACTORY
# =============================================================================

_affiliate_service: Optional[AffiliateService] = None


def get_affiliate_service() -> AffiliateService:
    """Get singleton AffiliateService instance."""
    global _affiliate_service
    if _affiliate_service is None:
        _affiliate_service = AffiliateService()
    return _affiliate_service

