"""
API Usage Service

Tracks all external API calls with token counts, costs, and credit consumption.
This service provides detailed logging for analytics and cost management.

Usage:
    from app.services.api_usage_service import get_api_usage_service
    
    usage_service = get_api_usage_service()
    await usage_service.log_llm_usage(
        organization_id="...",
        user_id="...",
        provider="anthropic",
        model="claude-sonnet-4-20250514",
        input_tokens=1000,
        output_tokens=500,
        service="research_analysis"
    )
"""

import logging
from decimal import Decimal
from typing import Optional, Dict, Any, List
from datetime import datetime
from app.database import get_supabase_service
from app.services.credit_service import CREDIT_COSTS

logger = logging.getLogger(__name__)


# API Pricing (USD per unit) - Updated December 2024
API_PRICING = {
    "anthropic": {
        "claude-sonnet-4-20250514": {
            "input_per_million": Decimal("3.00"),
            "output_per_million": Decimal("15.00"),
        },
        "claude-3-5-sonnet-20241022": {
            "input_per_million": Decimal("3.00"),
            "output_per_million": Decimal("15.00"),
        },
        "claude-3-haiku-20240307": {
            "input_per_million": Decimal("0.25"),
            "output_per_million": Decimal("1.25"),
        },
    },
    "gemini": {
        "gemini-2.0-flash": {
            "input_per_million": Decimal("0.10"),
            "output_per_million": Decimal("0.40"),
        },
        "gemini-1.5-flash": {
            "input_per_million": Decimal("0.075"),
            "output_per_million": Decimal("0.30"),
        },
    },
    "exa": {
        "search": Decimal("0.005"),  # per request
        "search_and_contents": Decimal("0.01"),  # per request with contents
    },
    "deepgram": {
        "nova-3": Decimal("0.000187"),  # $0.0112/min = $0.000187/sec (Nova-3 Multilingual + Diarization)
    },
    "voyage": {
        "voyage-2": Decimal("0.10"),  # per million tokens
    },
    "pinecone": {
        "query": Decimal("0.000004"),  # approximate per query
        "upsert": Decimal("0.000002"),  # approximate per upsert
    },
    "recall": {
        "bot_session": Decimal("0.25"),  # per meeting bot
    },
    "brave": {
        "search": Decimal("0.005"),  # per request
    },
}


class APIUsageService:
    """
    Centralized API usage tracking service.
    
    Logs all external API calls with:
    - Token counts (for LLMs)
    - Request counts (for search APIs)
    - Duration (for audio APIs)
    - Estimated costs
    - Credit consumption
    """
    
    def __init__(self):
        self.supabase = get_supabase_service()
    
    # ==========================================
    # LLM USAGE (Claude, Gemini)
    # ==========================================
    
    async def log_llm_usage(
        self,
        organization_id: str,
        provider: str,
        model: str,
        input_tokens: int,
        output_tokens: int,
        user_id: Optional[str] = None,
        service: Optional[str] = None,
        credits_consumed: Optional[float] = None,
        metadata: Optional[Dict[str, Any]] = None
    ) -> None:
        """
        Log LLM API usage (Claude, Gemini).
        
        Args:
            organization_id: Organization UUID
            provider: 'anthropic' or 'gemini'
            model: Model name (e.g., 'claude-sonnet-4-20250514')
            input_tokens: Number of input tokens
            output_tokens: Number of output tokens
            user_id: Optional user ID
            service: Service context (e.g., 'research_analysis')
            credits_consumed: Override credit consumption
            metadata: Additional context
        """
        try:
            # Calculate cost
            pricing = API_PRICING.get(provider, {}).get(model, {})
            input_cost = pricing.get("input_per_million", Decimal("0"))
            output_cost = pricing.get("output_per_million", Decimal("0"))
            
            cost_usd = (
                (Decimal(input_tokens) * input_cost / Decimal("1000000")) +
                (Decimal(output_tokens) * output_cost / Decimal("1000000"))
            )
            cost_cents = int(cost_usd * 100)
            
            # Default credits consumed based on service
            if credits_consumed is None:
                if service == "research_analysis":
                    credits_consumed = float(CREDIT_COSTS.get("research_flow", Decimal("1.0")))
                elif service in ["preparation", "prep_generation"]:
                    credits_consumed = float(CREDIT_COSTS.get("preparation", Decimal("0.5")))
                elif service in ["followup", "followup_generation"]:
                    credits_consumed = float(CREDIT_COSTS.get("followup", Decimal("0.5")))
                else:
                    credits_consumed = 0  # Just logging, no credit consumption
            
            await self._insert_log(
                organization_id=organization_id,
                user_id=user_id,
                api_provider=provider,
                api_service=service,
                model=model,
                input_tokens=input_tokens,
                output_tokens=output_tokens,
                estimated_cost_cents=cost_cents,
                credits_consumed=credits_consumed,
                request_metadata=metadata
            )
            
            logger.debug(
                f"Logged {provider}/{model} usage: "
                f"{input_tokens}in/{output_tokens}out tokens, "
                f"${cost_usd:.4f}, {credits_consumed} credits"
            )
            
        except Exception as e:
            logger.error(f"Error logging LLM usage: {e}")
    
    # ==========================================
    # SEARCH USAGE (Exa, Brave)
    # ==========================================
    
    async def log_search_usage(
        self,
        organization_id: str,
        provider: str,
        request_type: str,
        request_count: int = 1,
        user_id: Optional[str] = None,
        service: Optional[str] = None,
        credits_consumed: Optional[float] = None,
        metadata: Optional[Dict[str, Any]] = None
    ) -> None:
        """
        Log search API usage (Exa, Brave).
        
        Args:
            organization_id: Organization UUID
            provider: 'exa' or 'brave'
            request_type: 'search' or 'search_and_contents'
            request_count: Number of requests
            user_id: Optional user ID
            service: Service context
            credits_consumed: Override credit consumption
            metadata: Additional context
        """
        try:
            # Calculate cost
            price_per_request = API_PRICING.get(provider, {}).get(request_type, Decimal("0.01"))
            cost_usd = price_per_request * request_count
            cost_cents = int(cost_usd * 100)
            
            # Default credits for discovery searches
            if credits_consumed is None:
                if service == "discovery":
                    credits_consumed = float(CREDIT_COSTS.get("discovery_search", Decimal("0.2"))) * request_count
                elif service == "contact_search":
                    credits_consumed = float(CREDIT_COSTS.get("contact_search", Decimal("0.1")))
                else:
                    credits_consumed = 0
            
            await self._insert_log(
                organization_id=organization_id,
                user_id=user_id,
                api_provider=provider,
                api_service=service or request_type,
                model=request_type,
                request_count=request_count,
                estimated_cost_cents=cost_cents,
                credits_consumed=credits_consumed,
                request_metadata=metadata
            )
            
            logger.debug(
                f"Logged {provider} search usage: "
                f"{request_count} requests, ${cost_usd:.4f}"
            )
            
        except Exception as e:
            logger.error(f"Error logging search usage: {e}")
    
    # ==========================================
    # AUDIO USAGE (Deepgram)
    # ==========================================
    
    async def log_audio_usage(
        self,
        organization_id: str,
        provider: str,
        model: str,
        duration_seconds: int,
        user_id: Optional[str] = None,
        service: Optional[str] = None,
        credits_consumed: Optional[float] = None,
        metadata: Optional[Dict[str, Any]] = None
    ) -> None:
        """
        Log audio transcription usage (Deepgram).
        
        Args:
            organization_id: Organization UUID
            provider: 'deepgram'
            model: Model name (e.g., 'nova-3')
            duration_seconds: Audio duration in seconds
            user_id: Optional user ID
            service: Service context
            credits_consumed: Override credit consumption
            metadata: Additional context
        """
        try:
            # Calculate cost
            price_per_second = API_PRICING.get(provider, {}).get(model, Decimal("0.0043"))
            cost_usd = price_per_second * duration_seconds
            cost_cents = int(cost_usd * 100)
            
            # Credits: 0.1 per minute = 10 minutes per credit
            if credits_consumed is None:
                duration_minutes = duration_seconds / 60
                credits_consumed = float(CREDIT_COSTS.get("transcription_minute", Decimal("0.1"))) * duration_minutes
            
            await self._insert_log(
                organization_id=organization_id,
                user_id=user_id,
                api_provider=provider,
                api_service=service or "transcription",
                model=model,
                duration_seconds=duration_seconds,
                estimated_cost_cents=cost_cents,
                credits_consumed=credits_consumed,
                request_metadata=metadata
            )
            
            logger.debug(
                f"Logged {provider} audio usage: "
                f"{duration_seconds}s, ${cost_usd:.4f}"
            )
            
        except Exception as e:
            logger.error(f"Error logging audio usage: {e}")
    
    # ==========================================
    # EMBEDDING USAGE (Voyage)
    # ==========================================
    
    async def log_embedding_usage(
        self,
        organization_id: str,
        provider: str,
        model: str,
        token_count: int,
        chunk_count: int = 1,
        user_id: Optional[str] = None,
        service: Optional[str] = None,
        credits_consumed: Optional[float] = None,
        metadata: Optional[Dict[str, Any]] = None
    ) -> None:
        """
        Log embedding API usage (Voyage).
        
        Args:
            organization_id: Organization UUID
            provider: 'voyage'
            model: Model name (e.g., 'voyage-2')
            token_count: Estimated tokens (chars / 4)
            chunk_count: Number of chunks embedded
            user_id: Optional user ID
            service: Service context
            credits_consumed: Override credit consumption
            metadata: Additional context
        """
        try:
            # Calculate cost
            price_per_million = API_PRICING.get(provider, {}).get(model, Decimal("0.10"))
            cost_usd = (Decimal(token_count) * price_per_million) / Decimal("1000000")
            cost_cents = int(cost_usd * 100)
            
            # Credits per chunk
            if credits_consumed is None:
                credits_consumed = float(CREDIT_COSTS.get("embedding_chunk", Decimal("0.01"))) * chunk_count
            
            await self._insert_log(
                organization_id=organization_id,
                user_id=user_id,
                api_provider=provider,
                api_service=service or "embedding",
                model=model,
                input_tokens=token_count,
                request_count=chunk_count,
                estimated_cost_cents=cost_cents,
                credits_consumed=credits_consumed,
                request_metadata=metadata
            )
            
            logger.debug(
                f"Logged {provider} embedding usage: "
                f"{chunk_count} chunks, {token_count} tokens, ${cost_usd:.6f}"
            )
            
        except Exception as e:
            logger.error(f"Error logging embedding usage: {e}")
    
    # ==========================================
    # VECTOR STORE USAGE (Pinecone)
    # ==========================================
    
    async def log_vector_usage(
        self,
        organization_id: str,
        operation: str,
        count: int = 1,
        user_id: Optional[str] = None,
        service: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None
    ) -> None:
        """
        Log vector store usage (Pinecone).
        
        Args:
            organization_id: Organization UUID
            operation: 'query' or 'upsert'
            count: Number of operations
            user_id: Optional user ID
            service: Service context
            metadata: Additional context
        """
        try:
            price_per_op = API_PRICING.get("pinecone", {}).get(operation, Decimal("0.000004"))
            cost_usd = price_per_op * count
            cost_cents = max(1, int(cost_usd * 100))  # Min 1 cent for tracking
            
            await self._insert_log(
                organization_id=organization_id,
                user_id=user_id,
                api_provider="pinecone",
                api_service=service or operation,
                model=operation,
                request_count=count,
                estimated_cost_cents=cost_cents,
                credits_consumed=0,  # Vector ops don't consume credits
                request_metadata=metadata
            )
            
        except Exception as e:
            logger.error(f"Error logging vector usage: {e}")
    
    # ==========================================
    # MEETING BOT USAGE (Recall)
    # ==========================================
    
    async def log_meeting_bot_usage(
        self,
        organization_id: str,
        user_id: Optional[str] = None,
        service: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None
    ) -> None:
        """
        Log meeting bot usage (Recall.ai).
        
        Args:
            organization_id: Organization UUID
            user_id: Optional user ID
            service: Service context
            metadata: Additional context (meeting_id, platform, etc.)
        """
        try:
            price = API_PRICING.get("recall", {}).get("bot_session", Decimal("0.25"))
            cost_cents = int(price * 100)
            
            await self._insert_log(
                organization_id=organization_id,
                user_id=user_id,
                api_provider="recall",
                api_service=service or "meeting_bot",
                model="bot_session",
                request_count=1,
                estimated_cost_cents=cost_cents,
                credits_consumed=0,  # Bot sessions don't consume credits (separate billing)
                request_metadata=metadata
            )
            
        except Exception as e:
            logger.error(f"Error logging meeting bot usage: {e}")
    
    # ==========================================
    # AGGREGATION & REPORTING
    # ==========================================
    
    async def get_usage_summary(
        self,
        organization_id: str,
        period_start: Optional[datetime] = None,
        period_end: Optional[datetime] = None
    ) -> Dict[str, Any]:
        """
        Get aggregated usage summary for an organization.
        
        Returns breakdown by provider and service.
        """
        try:
            if not period_start:
                period_start = datetime.utcnow().replace(day=1, hour=0, minute=0, second=0, microsecond=0)
            if not period_end:
                period_end = datetime.utcnow()
            
            response = self.supabase.table("api_usage_logs").select(
                "api_provider, api_service, input_tokens, output_tokens, "
                "request_count, duration_seconds, estimated_cost_cents, credits_consumed"
            ).eq(
                "organization_id", organization_id
            ).gte(
                "created_at", period_start.isoformat()
            ).lte(
                "created_at", period_end.isoformat()
            ).execute()
            
            # Aggregate
            by_provider = {}
            by_service = {}
            totals = {
                "tokens": 0,
                "requests": 0,
                "duration_seconds": 0,
                "cost_cents": 0,
                "credits": 0,
                "api_calls": 0
            }
            
            for row in (response.data or []):
                provider = row.get("api_provider", "unknown")
                service = row.get("api_service", "unknown")
                
                tokens = (row.get("input_tokens", 0) or 0) + (row.get("output_tokens", 0) or 0)
                requests = row.get("request_count", 0) or 0
                duration = row.get("duration_seconds", 0) or 0
                cost = row.get("estimated_cost_cents", 0) or 0
                credits = float(row.get("credits_consumed", 0) or 0)
                
                # By provider
                if provider not in by_provider:
                    by_provider[provider] = {"tokens": 0, "requests": 0, "cost_cents": 0, "credits": 0, "calls": 0}
                by_provider[provider]["tokens"] += tokens
                by_provider[provider]["requests"] += requests
                by_provider[provider]["cost_cents"] += cost
                by_provider[provider]["credits"] += credits
                by_provider[provider]["calls"] += 1
                
                # By service
                if service not in by_service:
                    by_service[service] = {"tokens": 0, "requests": 0, "cost_cents": 0, "credits": 0, "calls": 0}
                by_service[service]["tokens"] += tokens
                by_service[service]["requests"] += requests
                by_service[service]["cost_cents"] += cost
                by_service[service]["credits"] += credits
                by_service[service]["calls"] += 1
                
                # Totals
                totals["tokens"] += tokens
                totals["requests"] += requests
                totals["duration_seconds"] += duration
                totals["cost_cents"] += cost
                totals["credits"] += credits
                totals["api_calls"] += 1
            
            return {
                "by_provider": by_provider,
                "by_service": by_service,
                "totals": totals,
                "period_start": period_start.isoformat(),
                "period_end": period_end.isoformat(),
            }
            
        except Exception as e:
            logger.error(f"Error getting usage summary: {e}")
            return {"by_provider": {}, "by_service": {}, "totals": {}}
    
    async def get_recent_logs(
        self,
        organization_id: str,
        limit: int = 50
    ) -> List[Dict[str, Any]]:
        """Get recent API usage logs."""
        try:
            response = self.supabase.table("api_usage_logs").select(
                "*"
            ).eq(
                "organization_id", organization_id
            ).order(
                "created_at", desc=True
            ).limit(limit).execute()
            
            return response.data or []
            
        except Exception as e:
            logger.error(f"Error getting recent logs: {e}")
            return []
    
    # ==========================================
    # HELPERS
    # ==========================================
    
    async def _insert_log(
        self,
        organization_id: str,
        api_provider: str,
        user_id: Optional[str] = None,
        api_service: Optional[str] = None,
        model: Optional[str] = None,
        input_tokens: int = 0,
        output_tokens: int = 0,
        request_count: int = 1,
        duration_seconds: int = 0,
        estimated_cost_cents: int = 0,
        credits_consumed: float = 0,
        request_metadata: Optional[Dict[str, Any]] = None
    ) -> None:
        """Insert a usage log record."""
        try:
            self.supabase.table("api_usage_logs").insert({
                "organization_id": organization_id,
                "user_id": user_id,
                "api_provider": api_provider,
                "api_service": api_service,
                "model": model,
                "input_tokens": input_tokens,
                "output_tokens": output_tokens,
                "request_count": request_count,
                "duration_seconds": duration_seconds,
                "estimated_cost_cents": estimated_cost_cents,
                "credits_consumed": credits_consumed,
                "request_metadata": request_metadata or {},
            }).execute()
        except Exception as e:
            # Log but don't fail the main operation
            logger.error(f"Error inserting API usage log: {e}")


# Singleton instance
_api_usage_service: Optional[APIUsageService] = None


def get_api_usage_service() -> APIUsageService:
    """Get or create API usage service instance."""
    global _api_usage_service
    if _api_usage_service is None:
        _api_usage_service = APIUsageService()
    return _api_usage_service

