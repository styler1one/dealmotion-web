"""
Credit Service

Central service for managing credits in DealMotion.
Credits are the universal currency for API usage:
- 1 Credit = 1 Research Flow (Gemini + Claude)
- 1 Credit = 5 Discovery Searches (Exa)
- 1 Credit = 10 minutes Transcription (Deepgram)

Key principles:
- Check credits BEFORE making API calls
- Log consumption AFTER successful calls
- Subscription credits reset monthly
- Pack credits persist until used
"""

import logging
from decimal import Decimal
from typing import Optional, Dict, Any, List, Tuple
from datetime import datetime, timedelta
from app.database import get_supabase_service

logger = logging.getLogger(__name__)


# =============================================================================
# CREDIT COSTS - Based on actual API cost analysis (see docs/CREDIT_COST_ANALYSIS.md)
# 
# Pricing principle: 1 Credit = $0.10 | ALL prices include 30% margin
# Last updated: December 2024
#
# API Pricing Reference:
# - Claude Sonnet 4: $3/1M input, $15/1M output
# - Gemini 2.0 Flash: $0.10/1M input, $0.40/1M output  
# - Exa search_and_contents: ~$0.01/call
# - Deepgram Nova-3 Multilingual + Diarization: $0.0112/min (Pay As You Go)
# =============================================================================

CREDIT_COSTS = {
    # Research flow = 3 credits
    # Cost: Gemini ($0.014) + Claude ($0.191) = $0.21 × 1.30 = $0.273 → 3 credits
    # Verified from logs: ~42k input, ~4.3k output per analysis
    "research_flow": Decimal("3.0"),
    
    # Prospect discovery = 5 credits (includes ~22 Exa calls + 3 Claude calls)
    # Cost: Exa ($0.22) + Claude ($0.18) = $0.40 × 1.30 = $0.52 → 5 credits
    # Verified from logs: scoring call uses ~35k input, ~4k output
    "prospect_discovery": Decimal("5.0"),
    
    # Transcription = 0.15 credits per minute
    # Cost: Deepgram Nova-3 = $0.0112/min × 1.30 = $0.0146 → 0.15 credits
    # 30-min meeting = 4.5 credits for transcription only
    "transcription_minute": Decimal("0.15"),
    
    # Preparation = 2.0 credits
    # Cost: Claude = $0.134 × 1.30 = $0.174 → 2 credits
    # Verified: ~10k input, ~7k output tokens
    "preparation": Decimal("2.0"),
    
    # Followup summary = 2.0 credits
    # Cost: Claude = ~$0.155 × 1.30 = $0.20 → 2 credits
    # Uses full transcript as input (~34k tokens) like actions
    "followup": Decimal("2.0"),
    
    # Followup action (each of the 6 action types) = 2 credits per action
    # Cost: Average $0.142 × 1.30 = $0.185 → 2 credits
    # Range: $0.109 (Email) to $0.183 (Sales Coaching)
    # Verified: ~34-36k input (transcript), 500-5000 output (varies by type)
    # All 6 actions = 12 credits
    "followup_action": Decimal("2.0"),
    
    # Contact search = 0.25 credits (Exa + optional Claude)
    # Cost: ~$0.02 × 1.30 = $0.026 → 0.25 credits
    "contact_search": Decimal("0.25"),
    
    # Embeddings = 0.01 credits per document chunk (very cheap)
    "embedding_chunk": Decimal("0.01"),
    
    # =============================================================================
    # BUNDLES & MINIMUMS - For simplified UX (30% margin included)
    # =============================================================================
    
    # Full followup bundle (30-min meeting)
    # = transcription (4.5) + summary (2) + 6 actions (12) = 18.5 → 19 credits
    "followup_bundle": Decimal("19.0"),
    
    # Minimum check for followup upload (5-min transcription + summary)
    # = transcription (0.75) + summary (2) = 2.75 → 3 credits minimum
    # Used for upfront check before processing starts
    "followup_start": Decimal("3.0"),
}


class CreditService:
    """
    Central credit management service.
    
    Usage:
        credit_service = get_credit_service()
        
        # Check if action is allowed
        can_proceed, balance = await credit_service.check_credits(org_id, "research_flow")
        if not can_proceed:
            raise HTTPException(402, "Insufficient credits")
        
        # After successful API call, consume credits
        await credit_service.consume_credits(org_id, "research_flow", user_id)
    """
    
    def __init__(self):
        self.supabase = get_supabase_service()
    
    # ==========================================
    # BALANCE CHECKING
    # ==========================================
    
    async def get_balance(self, organization_id: str) -> Dict[str, Any]:
        """
        Get current credit balance for organization.
        
        Returns:
            {
                "subscription_credits_total": int,
                "subscription_credits_used": float,
                "subscription_credits_remaining": float,
                "pack_credits_remaining": float,
                "total_credits_available": float,
                "is_unlimited": bool,
                "period_start": str,
                "period_end": str
            }
        """
        try:
            response = self.supabase.table("credit_balances").select("*").eq(
                "organization_id", organization_id
            ).maybe_single().execute()
            
            if not response.data:
                # Initialize balance for new org
                await self._initialize_balance(organization_id)
                return await self.get_balance(organization_id)
            
            data = response.data
            sub_total = data.get("subscription_credits_total", 0) or 0
            sub_used = float(data.get("subscription_credits_used", 0) or 0)
            pack_remaining = float(data.get("pack_credits_remaining", 0) or 0)
            is_unlimited = data.get("is_unlimited", False)
            
            sub_remaining = max(0, sub_total - sub_used) if not is_unlimited else float('inf')
            total = float('inf') if is_unlimited else (sub_remaining + pack_remaining)
            
            # Check if free plan - free users have one-time credits, no period reset
            is_free_plan = False
            try:
                plan_response = self.supabase.table("organization_subscriptions").select(
                    "plan_id"
                ).eq("organization_id", organization_id).maybe_single().execute()
                if plan_response.data:
                    is_free_plan = plan_response.data.get("plan_id") == "free"
            except Exception:
                pass  # Default to showing period for safety
            
            return {
                "subscription_credits_total": sub_total,
                "subscription_credits_used": sub_used,
                "subscription_credits_remaining": sub_remaining if not is_unlimited else -1,
                "pack_credits_remaining": pack_remaining,
                "total_credits_available": total if not is_unlimited else -1,
                "is_unlimited": is_unlimited,
                "is_free_plan": is_free_plan,
                "period_start": data.get("subscription_period_start") if not is_free_plan else None,
                "period_end": data.get("subscription_period_end") if not is_free_plan else None,
            }
            
        except Exception as e:
            logger.error(f"Error getting credit balance: {e}")
            # Return empty balance on error (safe default - no credits)
            return {
                "subscription_credits_total": 0,
                "subscription_credits_used": 0,
                "subscription_credits_remaining": 0,
                "pack_credits_remaining": 0,
                "total_credits_available": 0,
                "is_unlimited": False,
                "is_free_plan": True,  # Assume free plan on error (safest default)
                "period_start": None,
                "period_end": None,
                "error": str(e),
            }
    
    async def check_credits(
        self,
        organization_id: str,
        action: str,
        quantity: int = 1
    ) -> Tuple[bool, Dict[str, Any]]:
        """
        Check if organization has enough credits for an action.
        
        Args:
            organization_id: Organization UUID
            action: Action type from CREDIT_COSTS
            quantity: Number of units (e.g., minutes for transcription)
        
        Returns:
            Tuple of (allowed: bool, balance: dict)
        """
        try:
            balance = await self.get_balance(organization_id)
            
            # Unlimited plan = always allowed
            if balance.get("is_unlimited"):
                return True, balance
            
            # Calculate required credits
            cost_per_unit = CREDIT_COSTS.get(action, Decimal("1.0"))
            required = float(cost_per_unit * quantity)
            
            available = balance.get("total_credits_available", 0)
            allowed = available >= required
            
            return allowed, {
                **balance,
                "required_credits": required,
                "action": action,
                "quantity": quantity,
            }
            
        except Exception as e:
            logger.error(f"Error checking credits: {e}")
            # Fail closed - don't allow if we can't check
            return False, {"error": str(e)}
    
    # ==========================================
    # CREDIT CONSUMPTION
    # ==========================================
    
    async def consume_credits(
        self,
        organization_id: str,
        action: str,
        user_id: Optional[str] = None,
        quantity: int = 1,
        metadata: Optional[Dict[str, Any]] = None
    ) -> bool:
        """
        Consume credits after a successful action.
        
        Uses subscription credits first, then pack credits (FIFO).
        
        Args:
            organization_id: Organization UUID
            action: Action type from CREDIT_COSTS
            user_id: Optional user who triggered the action
            quantity: Number of units
            metadata: Optional context (prospect_id, etc.)
        
        Returns:
            True if successful
        """
        try:
            balance = await self.get_balance(organization_id)
            
            # Unlimited plan = no consumption tracking needed for balance
            # But we still log the transaction for analytics
            is_unlimited = balance.get("is_unlimited", False)
            
            cost_per_unit = CREDIT_COSTS.get(action, Decimal("1.0"))
            credits_to_consume = float(cost_per_unit * quantity)
            
            if not is_unlimited:
                # Check if we have enough
                available = balance.get("total_credits_available", 0)
                if available < credits_to_consume:
                    logger.warning(
                        f"Insufficient credits for {organization_id}: "
                        f"need {credits_to_consume}, have {available}"
                    )
                    return False
                
                # Consume from subscription first, then packs
                sub_remaining = balance.get("subscription_credits_remaining", 0)
                pack_remaining = balance.get("pack_credits_remaining", 0)
                
                if sub_remaining >= credits_to_consume:
                    # All from subscription
                    await self._update_subscription_credits(
                        organization_id, 
                        credits_to_consume
                    )
                elif sub_remaining > 0:
                    # Partial from subscription, rest from pack
                    await self._update_subscription_credits(
                        organization_id, 
                        sub_remaining
                    )
                    await self._update_pack_credits(
                        organization_id, 
                        credits_to_consume - sub_remaining
                    )
                else:
                    # All from pack
                    await self._update_pack_credits(
                        organization_id, 
                        credits_to_consume
                    )
            
            # Log transaction with full context
            new_balance = await self.get_balance(organization_id)
            
            # Build user-friendly description
            description = self._get_action_description(action, credits_to_consume, metadata)
            
            await self._log_transaction(
                organization_id=organization_id,
                transaction_type="consumption",
                credits_amount=-credits_to_consume,
                balance_after=new_balance.get("total_credits_available", 0),
                reference_type=action,
                description=description,
                user_id=user_id,
                metadata=metadata
            )
            
            logger.info(
                f"Consumed {credits_to_consume} credits for {action} "
                f"from org {organization_id}"
            )
            return True
            
        except Exception as e:
            logger.error(f"Error consuming credits: {e}")
            return False
    
    def _get_action_description(
        self,
        action: str,
        credits: float,
        metadata: Optional[Dict[str, Any]] = None
    ) -> str:
        """Generate user-friendly description for credit transaction."""
        descriptions = {
            "research_flow": "Research",
            "prospect_discovery": "Prospect Discovery",
            "preparation": "Meeting Preparation",
            "followup": "Meeting Follow-up",
            "followup_action": "Follow-up Action",
            "transcription_minute": "Transcription",
            "contact_search": "Contact Analysis",
            "embedding_chunk": "Knowledge Base",
        }
        
        base = descriptions.get(action, action.replace("_", " ").title())
        
        # Add context from metadata
        if metadata:
            if action == "research_flow" and metadata.get("company_name"):
                return f"{base}: {metadata['company_name']}"
            elif action == "preparation" and metadata.get("prospect_company"):
                return f"{base}: {metadata['prospect_company']}"
            elif action == "contact_search" and metadata.get("contact_name"):
                return f"{base}: {metadata['contact_name']}"
            elif action == "followup_action" and metadata.get("action_type"):
                action_labels = {
                    "commercial_analysis": "Deal Analysis",
                    "sales_coaching": "Sales Coaching",
                    "customer_report": "Customer Report",
                    "action_items": "Action Items",
                    "internal_report": "CRM Notes",
                    "share_email": "Follow-up Email",
                }
                label = action_labels.get(metadata["action_type"], metadata["action_type"])
                return f"Follow-up: {label}"
            elif action == "transcription_minute" and metadata.get("followup_id"):
                duration = metadata.get("duration_seconds", 0)
                mins = int(duration / 60) if duration else 0
                return f"Transcription: {mins} min"
        
        return f"{base} ({credits} credits)"
    
    async def _update_subscription_credits(
        self,
        organization_id: str,
        amount: float
    ) -> None:
        """Update subscription credits used."""
        try:
            current = self.supabase.table("credit_balances").select(
                "subscription_credits_used"
            ).eq("organization_id", organization_id).single().execute()
            
            current_used = float(current.data.get("subscription_credits_used", 0) or 0)
            
            self.supabase.table("credit_balances").update({
                "subscription_credits_used": current_used + amount,
                "updated_at": datetime.utcnow().isoformat()
            }).eq("organization_id", organization_id).execute()
        except Exception as e:
            logger.error(f"Error updating subscription credits: {e}")
    
    async def _update_pack_credits(
        self,
        organization_id: str,
        amount: float
    ) -> None:
        """Update pack credits remaining."""
        try:
            current = self.supabase.table("credit_balances").select(
                "pack_credits_remaining"
            ).eq("organization_id", organization_id).single().execute()
            
            current_remaining = float(current.data.get("pack_credits_remaining", 0) or 0)
            new_remaining = max(0, current_remaining - amount)
            
            self.supabase.table("credit_balances").update({
                "pack_credits_remaining": new_remaining,
                "updated_at": datetime.utcnow().isoformat()
            }).eq("organization_id", organization_id).execute()
            
            # Also update flow_packs for consistency
            await self._consume_from_flow_packs(organization_id, amount)
            
        except Exception as e:
            logger.error(f"Error updating pack credits: {e}")
    
    async def _consume_from_flow_packs(
        self,
        organization_id: str,
        amount: float
    ) -> None:
        """Consume from flow_packs table (FIFO)."""
        remaining = amount
        
        # Get active packs ordered by purchase date
        response = self.supabase.table("flow_packs").select(
            "id, flows_remaining"
        ).eq(
            "organization_id", organization_id
        ).eq(
            "status", "active"
        ).gt(
            "flows_remaining", 0
        ).order("purchased_at").execute()
        
        for pack in (response.data or []):
            if remaining <= 0:
                break
            
            pack_remaining = float(pack.get("flows_remaining", 0))
            
            if pack_remaining >= remaining:
                new_remaining = pack_remaining - remaining
                update_data = {
                    "flows_remaining": new_remaining,
                    "updated_at": datetime.utcnow().isoformat()
                }
                if new_remaining <= 0:
                    update_data["status"] = "depleted"
                    update_data["depleted_at"] = datetime.utcnow().isoformat()
                
                self.supabase.table("flow_packs").update(
                    update_data
                ).eq("id", pack["id"]).execute()
                remaining = 0
            else:
                self.supabase.table("flow_packs").update({
                    "flows_remaining": 0,
                    "status": "depleted",
                    "depleted_at": datetime.utcnow().isoformat(),
                    "updated_at": datetime.utcnow().isoformat()
                }).eq("id", pack["id"]).execute()
                remaining -= pack_remaining
    
    # ==========================================
    # CREDIT ADDITION
    # ==========================================
    
    async def add_pack_credits(
        self,
        organization_id: str,
        credits: int,
        source: str = "pack_purchase"
    ) -> bool:
        """
        Add credits from a purchased pack.
        
        Args:
            organization_id: Organization UUID
            credits: Number of credits to add
            source: Source of credits
        
        Returns:
            True if successful
        """
        try:
            # Update balance
            current = self.supabase.table("credit_balances").select(
                "pack_credits_remaining"
            ).eq("organization_id", organization_id).maybe_single().execute()
            
            if not current.data:
                await self._initialize_balance(organization_id)
                current_remaining = 0
            else:
                current_remaining = float(current.data.get("pack_credits_remaining", 0) or 0)
            
            new_remaining = current_remaining + credits
            
            self.supabase.table("credit_balances").update({
                "pack_credits_remaining": new_remaining,
                "updated_at": datetime.utcnow().isoformat()
            }).eq("organization_id", organization_id).execute()
            
            # Log transaction
            new_balance = await self.get_balance(organization_id)
            await self._log_transaction(
                organization_id=organization_id,
                transaction_type="pack_purchase",
                credits_amount=credits,
                balance_after=new_balance.get("total_credits_available", 0),
                reference_type=source,
                description=f"Added {credits} credits from {source}"
            )
            
            logger.info(f"Added {credits} credits to org {organization_id}")
            return True
            
        except Exception as e:
            logger.error(f"Error adding pack credits: {e}")
            return False
    
    async def reset_subscription_credits(
        self,
        organization_id: str,
        credits_total: int,
        is_unlimited: bool = False,
        billing_period_start: Optional[datetime] = None,
        billing_period_end: Optional[datetime] = None
    ) -> bool:
        """
        Reset subscription credits (called on subscription change or monthly reset).
        
        Args:
            organization_id: Organization UUID
            credits_total: New total credits for the period
            is_unlimited: Whether this is an unlimited plan
            billing_period_start: Stripe billing period start (dynamic, based on purchase date)
            billing_period_end: Stripe billing period end (dynamic, based on purchase date)
        
        Returns:
            True if successful
        """
        try:
            now = datetime.utcnow()
            
            # Use Stripe billing cycle if provided, otherwise calculate from now
            # This ensures the period is dynamic (based on purchase date), not hardcoded to 1st of month
            if billing_period_start and billing_period_end:
                period_start = billing_period_start
                period_end = billing_period_end
            else:
                # Fallback: use current date + 1 month (for manual resets or cron jobs)
                period_start = now
                period_end = now + timedelta(days=30)  # Approximate 1 month
            
            self.supabase.table("credit_balances").upsert({
                "organization_id": organization_id,
                "subscription_credits_total": credits_total,
                "subscription_credits_used": 0,
                "subscription_period_start": period_start.isoformat(),
                "subscription_period_end": period_end.isoformat(),
                "is_unlimited": is_unlimited,
                "updated_at": now.isoformat()
            }, on_conflict="organization_id").execute()
            
            # Log transaction
            await self._log_transaction(
                organization_id=organization_id,
                transaction_type="subscription_reset",
                credits_amount=credits_total,
                balance_after=credits_total,
                reference_type="subscription",
                description=f"Subscription reset: {credits_total} credits"
            )
            
            logger.info(
                f"Reset subscription credits for {organization_id}: "
                f"{credits_total} credits, unlimited={is_unlimited}"
            )
            return True
            
        except Exception as e:
            logger.error(f"Error resetting subscription credits: {e}")
            return False
    
    # ==========================================
    # USAGE HISTORY
    # ==========================================
    
    async def get_usage_history(
        self,
        organization_id: str,
        days: int = 30,
        limit: int = 100
    ) -> List[Dict[str, Any]]:
        """Get recent credit transactions."""
        try:
            response = self.supabase.table("credit_transactions").select(
                "*"
            ).eq(
                "organization_id", organization_id
            ).order(
                "created_at", desc=True
            ).limit(limit).execute()
            
            return response.data or []
            
        except Exception as e:
            logger.error(f"Error getting usage history: {e}")
            return []
    
    async def get_detailed_usage_history(
        self,
        organization_id: str,
        page: int = 1,
        page_size: int = 25,
        filter_type: Optional[str] = None,
        filter_action: Optional[str] = None,
        start_date: Optional[str] = None,
        end_date: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Get detailed usage history with pagination, filtering, and statistics.
        
        This powers the Credits Usage page for full transparency.
        """
        try:
            # Build base query for transactions
            query = self.supabase.table("credit_transactions").select(
                "*", count="exact"
            ).eq("organization_id", organization_id)
            
            # Apply filters
            if filter_type:
                query = query.eq("transaction_type", filter_type)
            
            if filter_action:
                query = query.eq("reference_type", filter_action)
            
            if start_date:
                query = query.gte("created_at", start_date)
            
            if end_date:
                query = query.lte("created_at", end_date)
            
            # Apply pagination
            offset = (page - 1) * page_size
            query = query.order(
                "created_at", desc=True
            ).range(offset, offset + page_size - 1)
            
            response = query.execute()
            
            transactions = response.data or []
            total_count = response.count or len(transactions)
            
            # Get period statistics (for current billing period)
            period_stats = await self._get_period_statistics(
                organization_id, filter_type, filter_action, start_date, end_date
            )
            
            return {
                "transactions": transactions,
                "total_count": total_count,
                "period_stats": period_stats
            }
            
        except Exception as e:
            logger.error(f"Error getting detailed usage history: {e}")
            return {
                "transactions": [],
                "total_count": 0,
                "period_stats": {}
            }
    
    async def _get_period_statistics(
        self,
        organization_id: str,
        filter_type: Optional[str] = None,
        filter_action: Optional[str] = None,
        start_date: Optional[str] = None,
        end_date: Optional[str] = None
    ) -> Dict[str, Any]:
        """Calculate usage statistics for the filtered period."""
        try:
            # Build query for consumption only
            query = self.supabase.table("credit_transactions").select(
                "transaction_type, reference_type, credits_amount"
            ).eq("organization_id", organization_id)
            
            if filter_type:
                query = query.eq("transaction_type", filter_type)
            
            if filter_action:
                query = query.eq("reference_type", filter_action)
            
            if start_date:
                query = query.gte("created_at", start_date)
            
            if end_date:
                query = query.lte("created_at", end_date)
            
            response = query.execute()
            data = response.data or []
            
            # Calculate stats
            total_consumed = 0.0
            total_added = 0.0
            by_action: Dict[str, float] = {}
            
            for row in data:
                amount = float(row.get("credits_amount", 0))
                action = row.get("reference_type") or row.get("transaction_type", "unknown")
                
                if amount < 0:
                    total_consumed += abs(amount)
                    by_action[action] = by_action.get(action, 0) + abs(amount)
                else:
                    total_added += amount
            
            # Format by_action for display
            action_labels = {
                "research_flow": "Research",
                "prospect_discovery": "Prospect Discovery",
                "preparation": "Meeting Preparation",
                "followup": "Meeting Follow-up",
                "followup_action": "Follow-up Actions",
                "transcription_minute": "Transcription",
                "contact_search": "Contact Analysis",
                "embedding_chunk": "Knowledge Base",
                "subscription_reset": "Subscription Credits",
                "pack_purchase": "Credit Pack",
            }
            
            by_action_formatted = [
                {
                    "action": action,
                    "label": action_labels.get(action, action.replace("_", " ").title()),
                    "credits": round(credits, 2)
                }
                for action, credits in sorted(by_action.items(), key=lambda x: -x[1])
            ]
            
            return {
                "total_consumed": round(total_consumed, 2),
                "total_added": round(total_added, 2),
                "transaction_count": len(data),
                "by_action": by_action_formatted
            }
            
        except Exception as e:
            logger.error(f"Error calculating period statistics: {e}")
            return {}
    
    async def get_usage_by_service(
        self,
        organization_id: str,
        period_start: Optional[datetime] = None,
        period_end: Optional[datetime] = None
    ) -> Dict[str, Any]:
        """Get usage breakdown by service for the period."""
        try:
            if not period_start:
                period_start = datetime.utcnow().replace(day=1, hour=0, minute=0, second=0, microsecond=0)
            if not period_end:
                period_end = datetime.utcnow()
            
            response = self.supabase.table("api_usage_logs").select(
                "api_provider, api_service, credits_consumed, estimated_cost_cents"
            ).eq(
                "organization_id", organization_id
            ).gte(
                "created_at", period_start.isoformat()
            ).lte(
                "created_at", period_end.isoformat()
            ).execute()
            
            # Aggregate by service
            by_service = {}
            total_credits = 0
            total_cost_cents = 0
            
            for row in (response.data or []):
                service = row.get("api_service") or row.get("api_provider", "unknown")
                credits = float(row.get("credits_consumed", 0) or 0)
                cost = row.get("estimated_cost_cents", 0) or 0
                
                if service not in by_service:
                    by_service[service] = {"credits": 0, "cost_cents": 0, "calls": 0}
                
                by_service[service]["credits"] += credits
                by_service[service]["cost_cents"] += cost
                by_service[service]["calls"] += 1
                total_credits += credits
                total_cost_cents += cost
            
            return {
                "by_service": by_service,
                "total_credits": total_credits,
                "total_cost_cents": total_cost_cents,
                "period_start": period_start.isoformat(),
                "period_end": period_end.isoformat(),
            }
            
        except Exception as e:
            logger.error(f"Error getting usage by service: {e}")
            return {"by_service": {}, "total_credits": 0, "total_cost_cents": 0}
    
    # ==========================================
    # HELPERS
    # ==========================================
    
    async def _initialize_balance(self, organization_id: str) -> None:
        """Initialize credit balance for new organization."""
        try:
            # Get subscription plan
            sub_response = self.supabase.table("organization_subscriptions").select(
                "plan_id, subscription_plans(credits_per_month)"
            ).eq("organization_id", organization_id).maybe_single().execute()
            
            credits_total = 25  # Default free plan (25 credits/month)
            is_unlimited = False
            
            if sub_response.data:
                plan_data = sub_response.data.get("subscription_plans", {})
                credits_per_month = plan_data.get("credits_per_month") if plan_data else None
                if credits_per_month is not None:
                    credits_total = credits_per_month
                    is_unlimited = credits_per_month == -1
            
            # Get pack credits from flow_packs
            packs_response = self.supabase.table("flow_packs").select(
                "flows_remaining"
            ).eq(
                "organization_id", organization_id
            ).eq(
                "status", "active"
            ).execute()
            
            pack_credits = sum(
                float(p.get("flows_remaining", 0) or 0) 
                for p in (packs_response.data or [])
            )
            
            now = datetime.utcnow()
            period_start = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
            
            if period_start.month == 12:
                period_end = period_start.replace(year=period_start.year + 1, month=1)
            else:
                period_end = period_start.replace(month=period_start.month + 1)
            
            self.supabase.table("credit_balances").insert({
                "organization_id": organization_id,
                "subscription_credits_total": credits_total if not is_unlimited else 0,
                "subscription_credits_used": 0,
                "subscription_period_start": period_start.isoformat(),
                "subscription_period_end": period_end.isoformat(),
                "pack_credits_remaining": pack_credits,
                "is_unlimited": is_unlimited,
            }).execute()
            
            logger.info(f"Initialized credit balance for org {organization_id}")
            
        except Exception as e:
            logger.error(f"Error initializing credit balance: {e}")
    
    async def _log_transaction(
        self,
        organization_id: str,
        transaction_type: str,
        credits_amount: float,
        balance_after: float,
        reference_type: Optional[str] = None,
        reference_id: Optional[str] = None,
        description: Optional[str] = None,
        user_id: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None
    ) -> None:
        """Log a credit transaction with full context for transparency."""
        try:
            record = {
                "organization_id": organization_id,
                "transaction_type": transaction_type,
                "credits_amount": credits_amount,
                "balance_after": balance_after if balance_after != float('inf') else -1,
                "reference_type": reference_type,
                "reference_id": reference_id,
                "description": description,
            }
            
            # Add optional fields if provided
            if user_id:
                record["user_id"] = user_id
            if metadata:
                record["metadata"] = metadata
            
            self.supabase.table("credit_transactions").insert(record).execute()
        except Exception as e:
            logger.error(f"Error logging credit transaction: {e}")


# Singleton instance
_credit_service: Optional[CreditService] = None


def get_credit_service() -> CreditService:
    """Get or create credit service instance."""
    global _credit_service
    if _credit_service is None:
        _credit_service = CreditService()
    return _credit_service

