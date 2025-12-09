"""
Usage Service

Tracks usage metrics and enforces subscription limits.

v2 (December 2025): Simplified flow-based tracking
- 1 flow = 1 research + 1 prep + 1 followup
- KB and transcription have no limits
"""

import logging
from typing import Dict, Any, Optional
from datetime import datetime
from app.database import get_supabase_service

logger = logging.getLogger(__name__)

# Use centralized database module
supabase = get_supabase_service()


class UsageService:
    """Service for tracking and enforcing usage limits"""
    
    def __init__(self):
        self.supabase = supabase
    
    # ==========================================
    # FLOW-BASED USAGE (v2)
    # ==========================================
    
    async def get_flow_usage(self, organization_id: str) -> Dict[str, Any]:
        """
        Get flow-based usage for v2 pricing model
        
        Returns:
            {
                "period_start": str,
                "period_end": str,
                "flow": {
                    "used": int,
                    "limit": int,
                    "unlimited": bool,
                    "remaining": int
                }
            }
        """
        try:
            period_start = datetime.utcnow().replace(day=1, hour=0, minute=0, second=0, microsecond=0)
            period_end = (period_start.replace(month=period_start.month + 1) if period_start.month < 12 
                         else period_start.replace(year=period_start.year + 1, month=1))
            
            # Get usage record
            usage_response = self.supabase.table("usage_records").select("*").eq(
                "organization_id", organization_id
            ).eq(
                "period_start", period_start.isoformat()
            ).maybe_single().execute()
            
            flow_count = 0
            if usage_response and hasattr(usage_response, 'data') and usage_response.data:
                flow_count = usage_response.data.get("flow_count", 0)
            
            # Get subscription for flow limit
            sub_response = self.supabase.table("organization_subscriptions").select(
                "plan_id, subscription_plans(features)"
            ).eq("organization_id", organization_id).maybe_single().execute()
            
            flow_limit = 2  # Default free limit
            if sub_response and hasattr(sub_response, 'data') and sub_response.data:
                plan_data = sub_response.data.get("subscription_plans", {})
                features = plan_data.get("features", {}) if plan_data else {}
                flow_limit = features.get("flow_limit", 2)
            
            unlimited = flow_limit == -1
            remaining = -1 if unlimited else max(0, flow_limit - flow_count)
            
            return {
                "period_start": period_start.isoformat(),
                "period_end": period_end.isoformat(),
                "flow": {
                    "used": flow_count,
                    "limit": flow_limit,
                    "unlimited": unlimited,
                    "remaining": remaining,
                }
            }
            
        except Exception as e:
            logger.error(f"Error getting flow usage: {e}")
            return {
                "period_start": datetime.utcnow().replace(day=1).isoformat(),
                "flow": {"used": 0, "limit": 2, "unlimited": False, "remaining": 2}
            }
    
    async def check_flow_limit(self, organization_id: str) -> Dict[str, Any]:
        """
        Check if user can start a new flow (research)
        
        v3: Also checks flow pack balance if subscription limit is reached
        
        Returns:
            {
                "allowed": bool,
                "current": int,
                "limit": int,
                "unlimited": bool,
                "remaining": int,
                "upgrade_required": bool,
                "flow_pack_balance": int,
                "using_flow_pack": bool
            }
        """
        try:
            flow_usage = await self.get_flow_usage(organization_id)
            flow = flow_usage.get("flow", {})
            
            used = flow.get("used", 0)
            limit = flow.get("limit", 2)
            unlimited = flow.get("unlimited", False)
            
            if unlimited:
                return {
                    "allowed": True,
                    "current": used,
                    "limit": -1,
                    "unlimited": True,
                    "remaining": -1,
                    "upgrade_required": False,
                    "flow_pack_balance": 0,
                    "using_flow_pack": False,
                }
            
            subscription_remaining = max(0, limit - used)
            
            # Check flow pack balance if subscription is exhausted
            flow_pack_balance = 0
            using_flow_pack = False
            
            if subscription_remaining == 0:
                # Import here to avoid circular imports
                from app.services.flow_pack_service import get_flow_pack_service
                flow_pack_service = get_flow_pack_service()
                balance = await flow_pack_service.get_balance(organization_id)
                flow_pack_balance = balance.get("total_remaining", 0)
                using_flow_pack = flow_pack_balance > 0
            
            total_remaining = subscription_remaining + flow_pack_balance
            allowed = total_remaining > 0
            
            return {
                "allowed": allowed,
                "current": used,
                "limit": limit,
                "unlimited": False,
                "remaining": subscription_remaining,
                "upgrade_required": not allowed,
                "flow_pack_balance": flow_pack_balance,
                "using_flow_pack": using_flow_pack,
            }
            
        except Exception as e:
            logger.error(f"Error checking flow limit: {e}")
            return {
                "allowed": False,
                "current": 0,
                "limit": 2,
                "unlimited": False,
                "remaining": 0,
                "upgrade_required": True,
                "flow_pack_balance": 0,
                "using_flow_pack": False,
                "error": str(e),
            }
    
    async def increment_flow(self, organization_id: str, use_flow_pack: bool = False) -> bool:
        """
        Increment flow count when starting a new research
        
        v3: If use_flow_pack=True, consume from flow pack instead of subscription
        
        Args:
            organization_id: Organization UUID
            use_flow_pack: If True, consume from flow pack balance
            
        Returns:
            True if successful
        """
        try:
            # If using flow pack, consume from pack first
            if use_flow_pack:
                from app.services.flow_pack_service import get_flow_pack_service
                flow_pack_service = get_flow_pack_service()
                consumed = await flow_pack_service.consume_flow(organization_id, 1)
                if not consumed:
                    logger.error(f"Failed to consume flow pack for org {organization_id}")
                    return False
                logger.info(f"Consumed 1 flow from flow pack for org {organization_id}")
            
            period_start = datetime.utcnow().replace(day=1, hour=0, minute=0, second=0, microsecond=0)
            period_end = (period_start.replace(month=period_start.month + 1) if period_start.month < 12 
                         else period_start.replace(year=period_start.year + 1, month=1))
            
            # Get existing record
            existing = self.supabase.table("usage_records").select("id", "flow_count", "research_count").eq(
                "organization_id", organization_id
            ).eq(
                "period_start", period_start.isoformat()
            ).maybe_single().execute()
            
            if existing and hasattr(existing, 'data') and existing.data:
                # Update existing record
                current_flow = existing.data.get("flow_count", 0) or 0
                current_research = existing.data.get("research_count", 0) or 0
                
                self.supabase.table("usage_records").update({
                    "flow_count": current_flow + 1,
                    "research_count": current_research + 1,
                    "updated_at": datetime.utcnow().isoformat(),
                }).eq("id", existing.data["id"]).execute()
            else:
                # Create new record
                self.supabase.table("usage_records").insert({
                    "organization_id": organization_id,
                    "period_start": period_start.isoformat(),
                    "period_end": period_end.isoformat(),
                    "flow_count": 1,
                    "research_count": 1,
                }).execute()
            
            source = "flow pack" if use_flow_pack else "subscription"
            logger.info(f"Incremented flow count for org {organization_id} (source: {source})")
            return True
            
        except Exception as e:
            logger.error(f"Error incrementing flow: {e}")
            return False
    
    # ==========================================
    # USAGE RETRIEVAL (v1 compatibility + v2 flow)
    # ==========================================
    
    async def get_usage(self, organization_id: str) -> Dict[str, Any]:
        """
        Get current usage stats for an organization
        
        Returns usage counts and limits for the current billing period
        """
        try:
            # Get current period (start of month)
            period_start = datetime.utcnow().replace(day=1, hour=0, minute=0, second=0, microsecond=0)
            
            # Get usage record - use maybe_single to handle 0 rows gracefully
            usage_response = self.supabase.table("usage_records").select("*").eq(
                "organization_id", organization_id
            ).eq(
                "period_start", period_start.isoformat()
            ).maybe_single().execute()
            
            # Get subscription for limits - use maybe_single to handle 0 rows gracefully
            sub_response = self.supabase.table("organization_subscriptions").select(
                "plan_id, subscription_plans(features)"
            ).eq("organization_id", organization_id).maybe_single().execute()
            
            # Default usage if no record (handle None response)
            usage = {
                "research_count": 0,
                "preparation_count": 0,
                "followup_count": 0,
                "flow_count": 0,
                "transcription_seconds": 0,
                "kb_document_count": 0,
            }
            if usage_response and hasattr(usage_response, 'data') and usage_response.data:
                usage = usage_response.data
            
            # Default to free plan features (handle None response)
            features = {}
            if sub_response and hasattr(sub_response, 'data') and sub_response.data:
                plan_data = sub_response.data.get("subscription_plans", {})
                features = plan_data.get("features", {}) if plan_data else {}
            
            # v2 flow-based limits (default to free: 2 flows)
            flow_limit = features.get("flow_limit", 2)
            flow_count = usage.get("flow_count", 0) or 0
            flow_unlimited = flow_limit == -1
            
            # For backward compatibility, also check old limits
            # But prefer flow_limit if it exists
            if "flow_limit" not in features:
                features = {
                    "research_limit": 3,
                    "preparation_limit": 3,
                    "followup_limit": 1,
                    "transcription_seconds_limit": 0,
                    "kb_document_limit": 0,
                    "flow_limit": 2,
                }
            
            period_end = (period_start.replace(month=period_start.month + 1) if period_start.month < 12 
                         else period_start.replace(year=period_start.year + 1, month=1))
            
            return {
                "period_start": period_start.isoformat(),
                "period_end": period_end.isoformat(),
                # v2: Primary metric is flow
                "flow": {
                    "used": flow_count,
                    "limit": flow_limit,
                    "unlimited": flow_unlimited,
                    "remaining": -1 if flow_unlimited else max(0, flow_limit - flow_count),
                },
                # v1 compatibility: individual metrics (still tracked for analytics)
                "research": {
                    "used": usage.get("research_count", 0),
                    "limit": flow_limit,  # Use flow_limit for all
                    "unlimited": flow_unlimited,
                },
                "preparation": {
                    "used": usage.get("preparation_count", 0),
                    "limit": flow_limit,  # Use flow_limit for all
                    "unlimited": flow_unlimited,
                },
                "followup": {
                    "used": usage.get("followup_count", 0),
                    "limit": flow_limit,  # Use flow_limit for all
                    "unlimited": flow_unlimited,
                },
                # These are now unlimited (no limits in v2)
                "transcription_seconds": {
                    "used": usage.get("transcription_seconds", 0),
                    "limit": -1,  # Unlimited in v2
                    "unlimited": True,
                    "used_hours": round(usage.get("transcription_seconds", 0) / 3600, 2),
                    "limit_hours": 0,
                },
                "kb_documents": {
                    "used": usage.get("kb_document_count", 0),
                    "limit": -1,  # Unlimited in v2
                    "unlimited": True,
                },
            }
            
        except Exception as e:
            logger.error(f"Error getting usage: {e}")
            # Return default free limits on error
            return self._get_default_usage()
    
    def _get_default_usage(self) -> Dict[str, Any]:
        """Return default usage object"""
        return {
            "period_start": datetime.utcnow().replace(day=1).isoformat(),
            "research": {"used": 0, "limit": 3, "unlimited": False},
            "preparation": {"used": 0, "limit": 3, "unlimited": False},
            "followup": {"used": 0, "limit": 1, "unlimited": False},
            "transcription_seconds": {"used": 0, "limit": 0, "unlimited": False, "used_hours": 0, "limit_hours": 0},
            "kb_documents": {"used": 0, "limit": 0, "unlimited": False},
        }
    
    # ==========================================
    # LIMIT CHECKING
    # ==========================================
    
    async def check_limit(self, organization_id: str, metric: str) -> Dict[str, Any]:
        """
        Check if an action is allowed within limits
        
        Args:
            organization_id: Organization UUID
            metric: One of 'research', 'preparation', 'followup', 'transcription_seconds', 'kb_document'
        
        Returns:
            {
                "allowed": bool,
                "current": int,
                "limit": int,
                "unlimited": bool,
                "remaining": int,
                "upgrade_required": bool
            }
        """
        try:
            usage = await self.get_usage(organization_id)
            
            metric_key = metric
            if metric == "kb_document":
                metric_key = "kb_documents"
            
            metric_data = usage.get(metric_key, {"used": 0, "limit": 0, "unlimited": False})
            
            used = metric_data.get("used", 0)
            limit = metric_data.get("limit", 0)
            unlimited = metric_data.get("unlimited", False)
            
            if unlimited:
                return {
                    "allowed": True,
                    "current": used,
                    "limit": -1,
                    "unlimited": True,
                    "remaining": -1,
                    "upgrade_required": False,
                }
            
            remaining = max(0, limit - used)
            allowed = used < limit
            
            return {
                "allowed": allowed,
                "current": used,
                "limit": limit,
                "unlimited": False,
                "remaining": remaining,
                "upgrade_required": not allowed,
            }
            
        except Exception as e:
            logger.error(f"Error checking limit: {e}")
            # Default to not allowed on error (safe default)
            return {
                "allowed": False,
                "current": 0,
                "limit": 0,
                "unlimited": False,
                "remaining": 0,
                "upgrade_required": True,
                "error": str(e),
            }
    
    async def check_transcription_limit(
        self, 
        organization_id: str, 
        additional_seconds: int
    ) -> Dict[str, Any]:
        """
        Check if transcription is allowed given additional seconds needed
        
        Args:
            organization_id: Organization UUID
            additional_seconds: Seconds of transcription needed
        
        Returns:
            Same as check_limit but accounts for additional_seconds
        """
        try:
            usage = await self.get_usage(organization_id)
            trans_data = usage.get("transcription_seconds", {})
            
            used = trans_data.get("used", 0)
            limit = trans_data.get("limit", 0)
            unlimited = trans_data.get("unlimited", False)
            
            if unlimited:
                return {
                    "allowed": True,
                    "current": used,
                    "limit": -1,
                    "unlimited": True,
                    "remaining": -1,
                    "upgrade_required": False,
                }
            
            would_use = used + additional_seconds
            allowed = would_use <= limit
            remaining = max(0, limit - used)
            
            return {
                "allowed": allowed,
                "current": used,
                "limit": limit,
                "unlimited": False,
                "remaining": remaining,
                "would_use": would_use,
                "upgrade_required": not allowed,
            }
            
        except Exception as e:
            logger.error(f"Error checking transcription limit: {e}")
            return {
                "allowed": False,
                "current": 0,
                "limit": 0,
                "unlimited": False,
                "remaining": 0,
                "upgrade_required": True,
                "error": str(e),
            }
    
    # ==========================================
    # USAGE TRACKING
    # ==========================================
    
    async def increment_usage(
        self, 
        organization_id: str, 
        metric: str, 
        amount: int = 1
    ) -> bool:
        """
        Increment a usage counter
        
        Args:
            organization_id: Organization UUID
            metric: Column name (research_count, preparation_count, etc.)
            amount: Amount to increment (default 1)
        
        Returns:
            True if successful
        """
        try:
            # Map metric names to column names
            column_map = {
                "research": "research_count",
                "preparation": "preparation_count",
                "followup": "followup_count",
                "transcription_seconds": "transcription_seconds",
                "kb_document": "kb_document_count",
            }
            
            column = column_map.get(metric, metric)
            
            # Get current period
            period_start = datetime.utcnow().replace(day=1, hour=0, minute=0, second=0, microsecond=0)
            period_end = (period_start.replace(month=period_start.month + 1) if period_start.month < 12 
                         else period_start.replace(year=period_start.year + 1, month=1))
            
            # Get or create usage record
            existing = self.supabase.table("usage_records").select("id", column).eq(
                "organization_id", organization_id
            ).eq(
                "period_start", period_start.isoformat()
            ).maybe_single().execute()
            
            if existing and hasattr(existing, 'data') and existing.data:
                # Update existing record
                current_value = existing.data.get(column, 0)
                self.supabase.table("usage_records").update({
                    column: current_value + amount,
                    "updated_at": datetime.utcnow().isoformat(),
                }).eq("id", existing.data["id"]).execute()
            else:
                # Create new record
                insert_data = {
                    "organization_id": organization_id,
                    "period_start": period_start.isoformat(),
                    "period_end": period_end.isoformat(),
                    column: amount,
                }
                self.supabase.table("usage_records").insert(insert_data).execute()
            
            logger.info(f"Incremented {column} by {amount} for org {organization_id}")
            return True
            
        except Exception as e:
            logger.error(f"Error incrementing usage: {e}")
            return False
    
    async def decrement_usage(
        self, 
        organization_id: str, 
        metric: str, 
        amount: int = 1
    ) -> bool:
        """
        Decrement a usage counter (e.g., when deleting a KB document)
        
        Args:
            organization_id: Organization UUID
            metric: Column name
            amount: Amount to decrement (default 1)
        
        Returns:
            True if successful
        """
        try:
            column_map = {
                "research": "research_count",
                "preparation": "preparation_count",
                "followup": "followup_count",
                "transcription_seconds": "transcription_seconds",
                "kb_document": "kb_document_count",
            }
            
            column = column_map.get(metric, metric)
            period_start = datetime.utcnow().replace(day=1, hour=0, minute=0, second=0, microsecond=0)
            
            # Get existing record
            existing = self.supabase.table("usage_records").select("id", column).eq(
                "organization_id", organization_id
            ).eq(
                "period_start", period_start.isoformat()
            ).maybe_single().execute()
            
            if existing and hasattr(existing, 'data') and existing.data:
                current_value = existing.data.get(column, 0)
                new_value = max(0, current_value - amount)  # Don't go below 0
                
                self.supabase.table("usage_records").update({
                    column: new_value,
                    "updated_at": datetime.utcnow().isoformat(),
                }).eq("id", existing.data["id"]).execute()
                
                logger.info(f"Decremented {column} by {amount} for org {organization_id}")
            
            return True
            
        except Exception as e:
            logger.error(f"Error decrementing usage: {e}")
            return False
    
    # ==========================================
    # KB DOCUMENT COUNT (Special handling)
    # ==========================================
    
    async def get_kb_document_count(self, organization_id: str) -> int:
        """
        Get actual KB document count from knowledge_base table
        (More accurate than usage counter for documents)
        """
        try:
            response = self.supabase.table("knowledge_base_files").select(
                "id", count="exact"
            ).eq("organization_id", organization_id).execute()
            
            return response.count or 0
            
        except Exception as e:
            logger.error(f"Error getting KB document count: {e}")
            return 0
    
    async def sync_kb_document_count(self, organization_id: str) -> None:
        """
        Sync KB document count from actual files
        (Run periodically or after uploads/deletes)
        """
        try:
            actual_count = await self.get_kb_document_count(organization_id)
            period_start = datetime.utcnow().replace(day=1, hour=0, minute=0, second=0, microsecond=0)
            
            # Update usage record
            self.supabase.table("usage_records").upsert({
                "organization_id": organization_id,
                "period_start": period_start.isoformat(),
                "kb_document_count": actual_count,
            }, on_conflict="organization_id,period_start").execute()
            
            logger.info(f"Synced KB document count for org {organization_id}: {actual_count}")
            
        except Exception as e:
            logger.error(f"Error syncing KB document count: {e}")


# Singleton instance
_usage_service: Optional[UsageService] = None


def get_usage_service() -> UsageService:
    """Get or create usage service instance"""
    global _usage_service
    if _usage_service is None:
        _usage_service = UsageService()
    return _usage_service

