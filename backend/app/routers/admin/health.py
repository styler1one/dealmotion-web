"""
Admin Health Router
===================

Comprehensive health monitoring for all external services.
Provides real-time status, historical trends, and job statistics.

Services monitored:
- Supabase (Database & Auth)
- Anthropic (Claude AI)
- Stripe (Payments)
- Inngest (Workflows)
- Deepgram (Transcription)
- Recall.ai (Meeting Bots)
- Pinecone (Vector DB)
- Voyage AI (Embeddings)
- Exa (Web Research)
- Google AI (Gemini)
- SendGrid (Email)
"""

from fastapi import APIRouter, Depends, Query
from typing import Optional, List, Dict, Any
from datetime import datetime, timedelta
from decimal import Decimal
import os
import httpx
import asyncio
import logging

from app.deps import get_admin_user, AdminContext
from app.database import get_supabase_service
from .models import CamelModel

router = APIRouter(prefix="/health", tags=["admin-health"])
logger = logging.getLogger(__name__)


# ============================================================
# Models (with camelCase serialization)
# ============================================================

class ServiceStatus(CamelModel):
    """Real-time status of a single service."""
    name: str
    display_name: str
    status: str  # 'healthy', 'degraded', 'down', 'unknown'
    response_time_ms: Optional[int] = None
    last_check: datetime
    details: Optional[str] = None
    error_message: Optional[str] = None
    is_critical: bool = False  # Critical services affect core functionality


class ServiceUptime(CamelModel):
    """Uptime statistics for a service."""
    service_name: str
    display_name: str
    uptime_percent_24h: float
    uptime_percent_7d: float
    uptime_percent_30d: float
    avg_response_time_ms: Optional[int] = None
    total_checks_30d: int
    last_incident: Optional[datetime] = None


class HealthOverview(CamelModel):
    """Overall system health status."""
    overall_status: str  # 'healthy', 'degraded', 'down'
    healthy_count: int
    degraded_count: int
    down_count: int
    services: List[ServiceStatus]
    last_updated: datetime


class JobStats(CamelModel):
    """Job statistics for a specific job type."""
    name: str
    display_name: str
    total_24h: int
    completed: int
    failed: int
    pending: int
    success_rate: float
    avg_duration_seconds: Optional[float] = None


class JobHealthResponse(CamelModel):
    """Job health overview."""
    jobs: List[JobStats]
    overall_success_rate: float
    total_jobs_24h: int
    total_failed_24h: int


class HealthTrendPoint(CamelModel):
    """Single point in health trend data."""
    date: str  # YYYY-MM-DD
    uptime_percent: float
    avg_response_time_ms: Optional[int] = None
    incident_count: int


class ServiceHealthTrend(CamelModel):
    """Health trend for a single service."""
    service_name: str
    display_name: str
    trend_data: List[HealthTrendPoint]


class HealthTrendsResponse(CamelModel):
    """Health trends for all services."""
    services: List[ServiceHealthTrend]
    period_days: int


class RecentIncident(CamelModel):
    """A recent service incident."""
    id: str
    service_name: str
    display_name: str
    status: str
    error_message: Optional[str] = None
    occurred_at: datetime
    duration_minutes: Optional[int] = None
    resolved: bool


class IncidentsResponse(CamelModel):
    """Recent incidents list."""
    incidents: List[RecentIncident]
    total: int


# ============================================================
# Service Display Names
# ============================================================

SERVICE_CONFIG = {
    "supabase": {"display_name": "Supabase", "is_critical": True},
    "anthropic": {"display_name": "Anthropic (Claude)", "is_critical": True},
    "stripe": {"display_name": "Stripe", "is_critical": True},
    "inngest": {"display_name": "Inngest", "is_critical": True},
    "deepgram": {"display_name": "Deepgram", "is_critical": False},
    "recall": {"display_name": "Recall.ai", "is_critical": False},
    "pinecone": {"display_name": "Pinecone", "is_critical": False},
    "voyage": {"display_name": "Voyage AI", "is_critical": False},
    "exa": {"display_name": "Exa", "is_critical": False},
    "google": {"display_name": "Google AI", "is_critical": False},
    "sendgrid": {"display_name": "SendGrid", "is_critical": False},
}


# ============================================================
# Endpoints
# ============================================================

@router.get("/overview", response_model=HealthOverview)
async def get_health_overview(
    admin: AdminContext = Depends(get_admin_user)
):
    """
    Get real-time health status of all external services.
    
    Performs actual API calls to verify connectivity.
    Results are logged to admin_service_health_logs for trending.
    """
    now = datetime.utcnow()
    supabase = get_supabase_service()
    
    # Run all health checks in parallel
    checks = await asyncio.gather(
        _check_supabase_health(),
        _check_anthropic_health(),
        _check_stripe_health(),
        _check_inngest_health(),
        _check_deepgram_health(),
        _check_recall_health(),
        _check_pinecone_health(),
        _check_voyage_health(),
        _check_exa_health(),
        _check_google_health(),
        _check_sendgrid_health(),
        return_exceptions=True
    )
    
    services = []
    for check in checks:
        if isinstance(check, Exception):
            # Handle unexpected errors
            logger.error(f"Health check error: {check}")
            continue
        if check:
            services.append(check)
            
            # Log to database for trending
            try:
                supabase.rpc("log_service_health", {
                    "p_service_name": check.name,
                    "p_status": check.status,
                    "p_response_time_ms": check.response_time_ms,
                    "p_error_message": check.error_message
                }).execute()
            except Exception as e:
                logger.warning(f"Failed to log health check: {e}")
    
    # Calculate overall status
    statuses = [s.status for s in services]
    critical_services = [s for s in services if s.is_critical]
    critical_statuses = [s.status for s in critical_services]
    
    if any(s == "down" for s in critical_statuses):
        overall = "down"
    elif any(s == "down" for s in statuses) or any(s == "degraded" for s in critical_statuses):
        overall = "degraded"
    elif all(s == "healthy" for s in statuses):
        overall = "healthy"
    else:
        overall = "degraded"
    
    return HealthOverview(
        overall_status=overall,
        healthy_count=sum(1 for s in statuses if s == "healthy"),
        degraded_count=sum(1 for s in statuses if s == "degraded"),
        down_count=sum(1 for s in statuses if s == "down"),
        services=services,
        last_updated=now
    )


@router.get("/uptime", response_model=List[ServiceUptime])
async def get_service_uptime(
    admin: AdminContext = Depends(get_admin_user)
):
    """
    Get uptime statistics for all services (24h, 7d, 30d).
    """
    supabase = get_supabase_service()
    
    uptimes = []
    
    for service_name, config in SERVICE_CONFIG.items():
        try:
            # Query uptime views
            result_24h = supabase.from_("admin_service_uptime_24h") \
                .select("*") \
                .eq("service_name", service_name) \
                .limit(1) \
                .execute()
            
            result_7d = supabase.from_("admin_service_uptime_7d") \
                .select("*") \
                .eq("service_name", service_name) \
                .limit(1) \
                .execute()
            
            result_30d = supabase.from_("admin_service_uptime_30d") \
                .select("*") \
                .eq("service_name", service_name) \
                .limit(1) \
                .execute()
            
            # Get last incident
            incident_result = supabase.table("admin_service_health_logs") \
                .select("checked_at") \
                .eq("service_name", service_name) \
                .neq("status", "healthy") \
                .order("checked_at", desc=True) \
                .limit(1) \
                .execute()
            
            data_24h = result_24h.data[0] if result_24h.data else {}
            data_7d = result_7d.data[0] if result_7d.data else {}
            data_30d = result_30d.data[0] if result_30d.data else {}
            
            uptimes.append(ServiceUptime(
                service_name=service_name,
                display_name=config["display_name"],
                uptime_percent_24h=float(data_24h.get("uptime_percent", 100)),
                uptime_percent_7d=float(data_7d.get("uptime_percent", 100)),
                uptime_percent_30d=float(data_30d.get("uptime_percent", 100)),
                avg_response_time_ms=int(data_30d.get("avg_response_time_ms", 0)) if data_30d.get("avg_response_time_ms") else None,
                total_checks_30d=int(data_30d.get("total_checks", 0)),
                last_incident=incident_result.data[0]["checked_at"] if incident_result.data else None
            ))
        except Exception as e:
            logger.error(f"Error getting uptime for {service_name}: {e}")
            # Return with no data rather than failing
            uptimes.append(ServiceUptime(
                service_name=service_name,
                display_name=config["display_name"],
                uptime_percent_24h=100,
                uptime_percent_7d=100,
                uptime_percent_30d=100,
                total_checks_30d=0
            ))
    
    return uptimes


@router.get("/trends", response_model=HealthTrendsResponse)
async def get_health_trends(
    days: int = Query(30, ge=1, le=30, description="Number of days of history"),
    admin: AdminContext = Depends(get_admin_user)
):
    """
    Get daily health trends for all services.
    """
    supabase = get_supabase_service()
    start_date = datetime.utcnow() - timedelta(days=days)
    
    services_trends = []
    
    for service_name, config in SERVICE_CONFIG.items():
        try:
            # Get daily aggregates
            result = supabase.table("admin_service_health_logs") \
                .select("checked_at, status, response_time_ms") \
                .eq("service_name", service_name) \
                .gte("checked_at", start_date.isoformat()) \
                .order("checked_at", desc=False) \
                .execute()
            
            # Group by date
            daily_data: Dict[str, Dict] = {}
            for row in (result.data or []):
                date = row["checked_at"][:10]  # YYYY-MM-DD
                if date not in daily_data:
                    daily_data[date] = {
                        "total": 0,
                        "healthy": 0,
                        "response_times": [],
                        "incidents": 0
                    }
                daily_data[date]["total"] += 1
                if row["status"] == "healthy":
                    daily_data[date]["healthy"] += 1
                else:
                    daily_data[date]["incidents"] += 1
                if row.get("response_time_ms"):
                    daily_data[date]["response_times"].append(row["response_time_ms"])
            
            trend_points = []
            for date in sorted(daily_data.keys()):
                data = daily_data[date]
                uptime = (data["healthy"] / data["total"] * 100) if data["total"] > 0 else 100
                avg_rt = int(sum(data["response_times"]) / len(data["response_times"])) if data["response_times"] else None
                
                trend_points.append(HealthTrendPoint(
                    date=date,
                    uptime_percent=round(uptime, 2),
                    avg_response_time_ms=avg_rt,
                    incident_count=data["incidents"]
                ))
            
            services_trends.append(ServiceHealthTrend(
                service_name=service_name,
                display_name=config["display_name"],
                trend_data=trend_points
            ))
        except Exception as e:
            logger.error(f"Error getting trends for {service_name}: {e}")
    
    return HealthTrendsResponse(
        services=services_trends,
        period_days=days
    )


@router.get("/incidents", response_model=IncidentsResponse)
async def get_recent_incidents(
    limit: int = Query(50, ge=1, le=200),
    service: Optional[str] = Query(None, description="Filter by service"),
    admin: AdminContext = Depends(get_admin_user)
):
    """
    Get recent service incidents (non-healthy statuses).
    """
    supabase = get_supabase_service()
    
    query = supabase.table("admin_service_health_logs") \
        .select("*") \
        .neq("status", "healthy") \
        .order("checked_at", desc=True) \
        .limit(limit)
    
    if service:
        query = query.eq("service_name", service)
    
    result = query.execute()
    
    incidents = []
    for row in (result.data or []):
        config = SERVICE_CONFIG.get(row["service_name"], {"display_name": row["service_name"]})
        incidents.append(RecentIncident(
            id=row["id"],
            service_name=row["service_name"],
            display_name=config["display_name"],
            status=row["status"],
            error_message=row.get("error_message"),
            occurred_at=row["checked_at"],
            duration_minutes=None,  # Could calculate if we track resolution
            resolved=True  # Assume resolved for historical incidents
        ))
    
    return IncidentsResponse(
        incidents=incidents,
        total=len(incidents)
    )


@router.get("/jobs", response_model=JobHealthResponse)
async def get_job_health(
    admin: AdminContext = Depends(get_admin_user)
):
    """
    Get job success rates for the last 24 hours.
    
    Tracks:
    - Research jobs
    - Preparation jobs
    - Follow-up jobs
    - Knowledge base processing
    - Transcription jobs
    """
    supabase = get_supabase_service()
    day_ago = (datetime.utcnow() - timedelta(days=1)).isoformat()
    
    job_configs = [
        ("research", "research_briefs", "Research Briefs"),
        ("preparation", "meeting_preps", "Meeting Preparations"),
        ("followup", "followups", "Follow-ups"),
        ("knowledge_base", "knowledge_base_files", "Knowledge Base"),
        ("transcription", "mobile_recordings", "Transcriptions"),
    ]
    
    jobs = []
    total_jobs = 0
    total_failed = 0
    total_success = 0
    
    for job_id, table_name, display_name in job_configs:
        try:
            stats = await _get_job_stats(supabase, table_name, day_ago)
            
            jobs.append(JobStats(
                name=job_id,
                display_name=display_name,
                total_24h=stats["total"],
                completed=stats["completed"],
                failed=stats["failed"],
                pending=stats["pending"],
                success_rate=stats["success_rate"],
                avg_duration_seconds=stats.get("avg_duration")
            ))
            
            total_jobs += stats["total"]
            total_failed += stats["failed"]
            total_success += stats["completed"]
        except Exception as e:
            logger.error(f"Error getting job stats for {table_name}: {e}")
            jobs.append(JobStats(
                name=job_id,
                display_name=display_name,
                total_24h=0,
                completed=0,
                failed=0,
                pending=0,
                success_rate=0.0
            ))
    
    overall_rate = (total_success / total_jobs * 100) if total_jobs > 0 else 0.0
    
    return JobHealthResponse(
        jobs=jobs,
        overall_success_rate=round(overall_rate, 1),
        total_jobs_24h=total_jobs,
        total_failed_24h=total_failed
    )


# ============================================================
# Health Check Implementations
# ============================================================

async def _check_supabase_health() -> ServiceStatus:
    """Check Supabase database connectivity."""
    config = SERVICE_CONFIG["supabase"]
    now = datetime.utcnow()
    start = datetime.utcnow()
    
    try:
        supabase = get_supabase_service()
        result = supabase.table("users").select("id").limit(1).execute()
        
        elapsed = int((datetime.utcnow() - start).total_seconds() * 1000)
        
        return ServiceStatus(
            name="supabase",
            display_name=config["display_name"],
            status="healthy" if elapsed < 1000 else "degraded",
            response_time_ms=elapsed,
            last_check=now,
            details=f"Database responding in {elapsed}ms",
            is_critical=config["is_critical"]
        )
    except Exception as e:
        return ServiceStatus(
            name="supabase",
            display_name=config["display_name"],
            status="down",
            last_check=now,
            error_message=str(e)[:200],
            is_critical=config["is_critical"]
        )


async def _check_anthropic_health() -> ServiceStatus:
    """Check Anthropic API connectivity with minimal token usage."""
    config = SERVICE_CONFIG["anthropic"]
    now = datetime.utcnow()
    start = datetime.utcnow()
    
    api_key = os.getenv("ANTHROPIC_API_KEY")
    if not api_key:
        return ServiceStatus(
            name="anthropic",
            display_name=config["display_name"],
            status="unknown",
            last_check=now,
            details="ANTHROPIC_API_KEY not configured",
            is_critical=config["is_critical"]
        )
    
    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            # Use a minimal request to check connectivity
            response = await client.post(
                "https://api.anthropic.com/v1/messages",
                headers={
                    "x-api-key": api_key,
                    "anthropic-version": "2023-06-01",
                    "Content-Type": "application/json"
                },
                json={
                    "model": "claude-3-haiku-20240307",
                    "max_tokens": 1,
                    "messages": [{"role": "user", "content": "hi"}]
                }
            )
            
            elapsed = int((datetime.utcnow() - start).total_seconds() * 1000)
            
            if response.status_code == 200:
                return ServiceStatus(
                    name="anthropic",
                    display_name=config["display_name"],
                    status="healthy",
                    response_time_ms=elapsed,
                    last_check=now,
                    details=f"Claude API responding in {elapsed}ms",
                    is_critical=config["is_critical"]
                )
            elif response.status_code == 529:
                return ServiceStatus(
                    name="anthropic",
                    display_name=config["display_name"],
                    status="degraded",
                    response_time_ms=elapsed,
                    last_check=now,
                    details="Anthropic API overloaded",
                    is_critical=config["is_critical"]
                )
            else:
                return ServiceStatus(
                    name="anthropic",
                    display_name=config["display_name"],
                    status="degraded",
                    response_time_ms=elapsed,
                    last_check=now,
                    error_message=f"HTTP {response.status_code}",
                    is_critical=config["is_critical"]
                )
    except httpx.TimeoutException:
        return ServiceStatus(
            name="anthropic",
            display_name=config["display_name"],
            status="degraded",
            last_check=now,
            error_message="Request timeout (>10s)",
            is_critical=config["is_critical"]
        )
    except Exception as e:
        return ServiceStatus(
            name="anthropic",
            display_name=config["display_name"],
            status="down",
            last_check=now,
            error_message=str(e)[:200],
            is_critical=config["is_critical"]
        )


async def _check_stripe_health() -> ServiceStatus:
    """Check Stripe API connectivity."""
    config = SERVICE_CONFIG["stripe"]
    now = datetime.utcnow()
    start = datetime.utcnow()
    
    stripe_key = os.getenv("STRIPE_SECRET_KEY")
    if not stripe_key:
        return ServiceStatus(
            name="stripe",
            display_name=config["display_name"],
            status="unknown",
            last_check=now,
            details="STRIPE_SECRET_KEY not configured",
            is_critical=config["is_critical"]
        )
    
    try:
        import stripe
        stripe.api_key = stripe_key
        
        # Quick balance check (read-only, no cost)
        stripe.Balance.retrieve()
        
        elapsed = int((datetime.utcnow() - start).total_seconds() * 1000)
        
        return ServiceStatus(
            name="stripe",
            display_name=config["display_name"],
            status="healthy",
            response_time_ms=elapsed,
            last_check=now,
            details=f"Stripe API responding in {elapsed}ms",
            is_critical=config["is_critical"]
        )
    except Exception as e:
        return ServiceStatus(
            name="stripe",
            display_name=config["display_name"],
            status="down",
            last_check=now,
            error_message=str(e)[:200],
            is_critical=config["is_critical"]
        )


async def _check_inngest_health() -> ServiceStatus:
    """Check Inngest service connectivity."""
    config = SERVICE_CONFIG["inngest"]
    now = datetime.utcnow()
    start = datetime.utcnow()
    
    inngest_key = os.getenv("INNGEST_EVENT_KEY")
    if not inngest_key:
        return ServiceStatus(
            name="inngest",
            display_name=config["display_name"],
            status="unknown",
            last_check=now,
            details="INNGEST_EVENT_KEY not configured",
            is_critical=config["is_critical"]
        )
    
    try:
        async with httpx.AsyncClient(timeout=5.0) as client:
            response = await client.post(
                f"https://inn.gs/e/{inngest_key}",
                json={
                    "name": "admin/health-check",
                    "data": {"timestamp": now.isoformat()}
                }
            )
            
            elapsed = int((datetime.utcnow() - start).total_seconds() * 1000)
            
            if response.status_code in [200, 201, 202]:
                return ServiceStatus(
                    name="inngest",
                    display_name=config["display_name"],
                    status="healthy",
                    response_time_ms=elapsed,
                    last_check=now,
                    details=f"Inngest responding in {elapsed}ms",
                    is_critical=config["is_critical"]
                )
            else:
                return ServiceStatus(
                    name="inngest",
                    display_name=config["display_name"],
                    status="degraded",
                    response_time_ms=elapsed,
                    last_check=now,
                    error_message=f"HTTP {response.status_code}",
                    is_critical=config["is_critical"]
                )
    except Exception as e:
        return ServiceStatus(
            name="inngest",
            display_name=config["display_name"],
            status="down",
            last_check=now,
            error_message=str(e)[:200],
            is_critical=config["is_critical"]
        )


async def _check_deepgram_health() -> ServiceStatus:
    """Check Deepgram API connectivity."""
    config = SERVICE_CONFIG["deepgram"]
    now = datetime.utcnow()
    start = datetime.utcnow()
    
    api_key = os.getenv("DEEPGRAM_API_KEY")
    if not api_key:
        return ServiceStatus(
            name="deepgram",
            display_name=config["display_name"],
            status="unknown",
            last_check=now,
            details="DEEPGRAM_API_KEY not configured",
            is_critical=config["is_critical"]
        )
    
    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            # Check projects endpoint (no cost)
            response = await client.get(
                "https://api.deepgram.com/v1/projects",
                headers={"Authorization": f"Token {api_key}"}
            )
            
            elapsed = int((datetime.utcnow() - start).total_seconds() * 1000)
            
            if response.status_code == 200:
                return ServiceStatus(
                    name="deepgram",
                    display_name=config["display_name"],
                    status="healthy",
                    response_time_ms=elapsed,
                    last_check=now,
                    details=f"Deepgram API responding in {elapsed}ms",
                    is_critical=config["is_critical"]
                )
            else:
                return ServiceStatus(
                    name="deepgram",
                    display_name=config["display_name"],
                    status="degraded",
                    response_time_ms=elapsed,
                    last_check=now,
                    error_message=f"HTTP {response.status_code}",
                    is_critical=config["is_critical"]
                )
    except Exception as e:
        return ServiceStatus(
            name="deepgram",
            display_name=config["display_name"],
            status="down",
            last_check=now,
            error_message=str(e)[:200],
            is_critical=config["is_critical"]
        )


async def _check_recall_health() -> ServiceStatus:
    """Check Recall.ai API connectivity."""
    config = SERVICE_CONFIG["recall"]
    now = datetime.utcnow()
    start = datetime.utcnow()
    
    api_key = os.getenv("RECALL_API_KEY")
    if not api_key:
        return ServiceStatus(
            name="recall",
            display_name=config["display_name"],
            status="unknown",
            last_check=now,
            details="RECALL_API_KEY not configured",
            is_critical=config["is_critical"]
        )
    
    recall_region = os.getenv("RECALL_REGION", "us-east-1")
    base_url = f"https://{recall_region}.recall.ai/api/v1"
    
    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            response = await client.get(
                f"{base_url}/bot",
                headers={"Authorization": f"Token {api_key}"},
                params={"limit": 1}
            )
            
            elapsed = int((datetime.utcnow() - start).total_seconds() * 1000)
            
            if response.status_code == 200:
                return ServiceStatus(
                    name="recall",
                    display_name=config["display_name"],
                    status="healthy",
                    response_time_ms=elapsed,
                    last_check=now,
                    details=f"Recall.ai responding in {elapsed}ms",
                    is_critical=config["is_critical"]
                )
            else:
                return ServiceStatus(
                    name="recall",
                    display_name=config["display_name"],
                    status="degraded",
                    response_time_ms=elapsed,
                    last_check=now,
                    error_message=f"HTTP {response.status_code}",
                    is_critical=config["is_critical"]
                )
    except Exception as e:
        return ServiceStatus(
            name="recall",
            display_name=config["display_name"],
            status="down",
            last_check=now,
            error_message=str(e)[:200],
            is_critical=config["is_critical"]
        )


async def _check_pinecone_health() -> ServiceStatus:
    """Check Pinecone API connectivity."""
    config = SERVICE_CONFIG["pinecone"]
    now = datetime.utcnow()
    start = datetime.utcnow()
    
    api_key = os.getenv("PINECONE_API_KEY")
    if not api_key:
        return ServiceStatus(
            name="pinecone",
            display_name=config["display_name"],
            status="unknown",
            last_check=now,
            details="PINECONE_API_KEY not configured",
            is_critical=config["is_critical"]
        )
    
    try:
        from pinecone import Pinecone
        pc = Pinecone(api_key=api_key)
        
        # List indexes (no cost)
        indexes = pc.list_indexes()
        
        elapsed = int((datetime.utcnow() - start).total_seconds() * 1000)
        
        return ServiceStatus(
            name="pinecone",
            display_name=config["display_name"],
            status="healthy",
            response_time_ms=elapsed,
            last_check=now,
            details=f"Pinecone responding in {elapsed}ms ({len(indexes)} indexes)",
            is_critical=config["is_critical"]
        )
    except Exception as e:
        return ServiceStatus(
            name="pinecone",
            display_name=config["display_name"],
            status="down",
            last_check=now,
            error_message=str(e)[:200],
            is_critical=config["is_critical"]
        )


async def _check_voyage_health() -> ServiceStatus:
    """Check Voyage AI API connectivity."""
    config = SERVICE_CONFIG["voyage"]
    now = datetime.utcnow()
    start = datetime.utcnow()
    
    api_key = os.getenv("VOYAGE_API_KEY")
    if not api_key:
        return ServiceStatus(
            name="voyage",
            display_name=config["display_name"],
            status="unknown",
            last_check=now,
            details="VOYAGE_API_KEY not configured",
            is_critical=config["is_critical"]
        )
    
    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            # Minimal embedding request
            response = await client.post(
                "https://api.voyageai.com/v1/embeddings",
                headers={
                    "Authorization": f"Bearer {api_key}",
                    "Content-Type": "application/json"
                },
                json={
                    "model": "voyage-2",
                    "input": ["test"]
                }
            )
            
            elapsed = int((datetime.utcnow() - start).total_seconds() * 1000)
            
            if response.status_code == 200:
                return ServiceStatus(
                    name="voyage",
                    display_name=config["display_name"],
                    status="healthy",
                    response_time_ms=elapsed,
                    last_check=now,
                    details=f"Voyage AI responding in {elapsed}ms",
                    is_critical=config["is_critical"]
                )
            else:
                return ServiceStatus(
                    name="voyage",
                    display_name=config["display_name"],
                    status="degraded",
                    response_time_ms=elapsed,
                    last_check=now,
                    error_message=f"HTTP {response.status_code}",
                    is_critical=config["is_critical"]
                )
    except Exception as e:
        return ServiceStatus(
            name="voyage",
            display_name=config["display_name"],
            status="down",
            last_check=now,
            error_message=str(e)[:200],
            is_critical=config["is_critical"]
        )


async def _check_exa_health() -> ServiceStatus:
    """Check Exa API connectivity."""
    config = SERVICE_CONFIG["exa"]
    now = datetime.utcnow()
    start = datetime.utcnow()
    
    api_key = os.getenv("EXA_API_KEY")
    if not api_key:
        return ServiceStatus(
            name="exa",
            display_name=config["display_name"],
            status="unknown",
            last_check=now,
            details="EXA_API_KEY not configured",
            is_critical=config["is_critical"]
        )
    
    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            # Minimal search (1 result)
            response = await client.post(
                "https://api.exa.ai/search",
                headers={
                    "x-api-key": api_key,
                    "Content-Type": "application/json"
                },
                json={
                    "query": "health check",
                    "num_results": 1,
                    "type": "keyword"
                }
            )
            
            elapsed = int((datetime.utcnow() - start).total_seconds() * 1000)
            
            if response.status_code == 200:
                return ServiceStatus(
                    name="exa",
                    display_name=config["display_name"],
                    status="healthy",
                    response_time_ms=elapsed,
                    last_check=now,
                    details=f"Exa API responding in {elapsed}ms",
                    is_critical=config["is_critical"]
                )
            else:
                return ServiceStatus(
                    name="exa",
                    display_name=config["display_name"],
                    status="degraded",
                    response_time_ms=elapsed,
                    last_check=now,
                    error_message=f"HTTP {response.status_code}",
                    is_critical=config["is_critical"]
                )
    except Exception as e:
        return ServiceStatus(
            name="exa",
            display_name=config["display_name"],
            status="down",
            last_check=now,
            error_message=str(e)[:200],
            is_critical=config["is_critical"]
        )


async def _check_google_health() -> ServiceStatus:
    """Check Google AI (Gemini) API connectivity."""
    config = SERVICE_CONFIG["google"]
    now = datetime.utcnow()
    start = datetime.utcnow()
    
    api_key = os.getenv("GOOGLE_AI_API_KEY") or os.getenv("GOOGLE_API_KEY")
    if not api_key:
        return ServiceStatus(
            name="google",
            display_name=config["display_name"],
            status="unknown",
            last_check=now,
            details="GOOGLE_API_KEY not configured",
            is_critical=config["is_critical"]
        )
    
    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            # List models endpoint (no cost)
            response = await client.get(
                f"https://generativelanguage.googleapis.com/v1beta/models?key={api_key}"
            )
            
            elapsed = int((datetime.utcnow() - start).total_seconds() * 1000)
            
            if response.status_code == 200:
                return ServiceStatus(
                    name="google",
                    display_name=config["display_name"],
                    status="healthy",
                    response_time_ms=elapsed,
                    last_check=now,
                    details=f"Google AI responding in {elapsed}ms",
                    is_critical=config["is_critical"]
                )
            else:
                return ServiceStatus(
                    name="google",
                    display_name=config["display_name"],
                    status="degraded",
                    response_time_ms=elapsed,
                    last_check=now,
                    error_message=f"HTTP {response.status_code}",
                    is_critical=config["is_critical"]
                )
    except Exception as e:
        return ServiceStatus(
            name="google",
            display_name=config["display_name"],
            status="down",
            last_check=now,
            error_message=str(e)[:200],
            is_critical=config["is_critical"]
        )


async def _check_sendgrid_health() -> ServiceStatus:
    """Check SendGrid API connectivity."""
    config = SERVICE_CONFIG["sendgrid"]
    now = datetime.utcnow()
    start = datetime.utcnow()
    
    api_key = os.getenv("SENDGRID_API_KEY")
    if not api_key:
        return ServiceStatus(
            name="sendgrid",
            display_name=config["display_name"],
            status="unknown",
            last_check=now,
            details="SENDGRID_API_KEY not configured",
            is_critical=config["is_critical"]
        )
    
    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            # Get user profile (no cost)
            response = await client.get(
                "https://api.sendgrid.com/v3/user/profile",
                headers={"Authorization": f"Bearer {api_key}"}
            )
            
            elapsed = int((datetime.utcnow() - start).total_seconds() * 1000)
            
            if response.status_code == 200:
                return ServiceStatus(
                    name="sendgrid",
                    display_name=config["display_name"],
                    status="healthy",
                    response_time_ms=elapsed,
                    last_check=now,
                    details=f"SendGrid responding in {elapsed}ms",
                    is_critical=config["is_critical"]
                )
            else:
                return ServiceStatus(
                    name="sendgrid",
                    display_name=config["display_name"],
                    status="degraded",
                    response_time_ms=elapsed,
                    last_check=now,
                    error_message=f"HTTP {response.status_code}",
                    is_critical=config["is_critical"]
                )
    except Exception as e:
        return ServiceStatus(
            name="sendgrid",
            display_name=config["display_name"],
            status="down",
            last_check=now,
            error_message=str(e)[:200],
            is_critical=config["is_critical"]
        )


# ============================================================
# Helper Functions
# ============================================================

async def _get_job_stats(supabase, table_name: str, since: str) -> dict:
    """Get job statistics from a table."""
    try:
        # Total
        total_result = supabase.table(table_name) \
            .select("id", count="exact") \
            .gte("created_at", since) \
            .execute()
        total = total_result.count or 0
        
        # Completed
        completed_result = supabase.table(table_name) \
            .select("id", count="exact") \
            .gte("created_at", since) \
            .eq("status", "completed") \
            .execute()
        completed = completed_result.count or 0
        
        # Failed
        failed_result = supabase.table(table_name) \
            .select("id", count="exact") \
            .gte("created_at", since) \
            .eq("status", "failed") \
            .execute()
        failed = failed_result.count or 0
        
        # Pending/Processing
        pending_result = supabase.table(table_name) \
            .select("id", count="exact") \
            .gte("created_at", since) \
            .in_("status", ["pending", "processing", "queued"]) \
            .execute()
        pending = pending_result.count or 0
        
        success_rate = (completed / total * 100) if total > 0 else 0.0
        
        return {
            "total": total,
            "completed": completed,
            "failed": failed,
            "pending": pending,
            "success_rate": round(success_rate, 1)
        }
    except Exception as e:
        logger.error(f"Error getting job stats for {table_name}: {e}")
        return {
            "total": 0,
            "completed": 0,
            "failed": 0,
            "pending": 0,
            "success_rate": 0.0
        }

