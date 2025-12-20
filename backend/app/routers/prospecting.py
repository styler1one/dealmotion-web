"""
Prospecting Router - Contextual Prospect Discovery API

Endpoints for AI-powered prospect discovery based on seller context.
This is NOT research of known companies - it's DISCOVERY of new prospects.
"""

import logging
from typing import Optional, List, Dict, Any
from datetime import datetime
from fastapi import APIRouter, Depends, HTTPException, BackgroundTasks
from pydantic import BaseModel, Field

from app.deps import get_current_user, get_user_org
from app.database import get_supabase_service
from app.services.prospect_discovery import (
    get_prospect_discovery_service,
    DiscoveryInput,
    DiscoveryResult,
    DiscoveredProspect
)
from app.services.usage_service import get_usage_service
from app.inngest.events import send_event

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/prospecting", tags=["prospecting"])


# =============================================================================
# Request/Response Models
# =============================================================================

class ProspectingSearchRequest(BaseModel):
    """Request to start a prospecting search."""
    region: Optional[str] = Field(None, description="Target region or country")
    sector: Optional[str] = Field(None, description="Industry/sector focus (free text)")
    company_size: Optional[str] = Field(None, description="Target size (e.g., 'mid-sized', 'enterprise')")
    proposition: Optional[str] = Field(None, description="What we sell (1 sentence)")
    target_role: Optional[str] = Field(None, description="Who is this relevant for?")
    pain_point: Optional[str] = Field(None, description="Where is pain/urgency?")
    reference_customers: Optional[List[str]] = Field(None, description="Companies that are 100% fit (for context enrichment)")
    max_results: int = Field(25, ge=10, le=100, description="Maximum number of results (10-100)")
    
    class Config:
        json_schema_extra = {
            "example": {
                "region": "Netherlands",
                "sector": "logistics and supply chain",
                "company_size": "mid-sized",
                "proposition": "AI-powered demand forecasting platform",
                "target_role": "COO or Supply Chain Director",
                "pain_point": "struggling with inventory optimization and demand volatility",
                "reference_customers": ["Bol.com", "Coolblue", "Picnic"]
            }
        }


class ProspectingSearchResponse(BaseModel):
    """Response when starting a prospecting search."""
    id: str
    status: str
    message: str


class DiscoveredProspectResponse(BaseModel):
    """A single discovered prospect."""
    id: Optional[str] = None
    company_name: str
    website: Optional[str] = None
    linkedin_url: Optional[str] = None
    
    # Inferred data
    inferred_sector: Optional[str] = None
    inferred_region: Optional[str] = None
    inferred_size: Optional[str] = None
    
    # Scores
    fit_score: int = 0
    proposition_fit: int = 0
    seller_fit: int = 0
    intent_score: int = 0
    recency_score: int = 0
    
    # Explanation
    fit_reason: Optional[str] = None
    key_signal: Optional[str] = None
    
    # Source
    source_url: Optional[str] = None
    source_title: Optional[str] = None
    source_published_date: Optional[str] = None
    
    # Import status
    prospect_id: Optional[str] = None
    imported_at: Optional[datetime] = None


class ProspectingResultsResponse(BaseModel):
    """Response with discovery results."""
    search_id: str
    status: str
    generated_queries: List[str] = []
    prospects: List[DiscoveredProspectResponse] = []
    total_count: int = 0
    reference_context: Optional[str] = None  # Extracted context from reference customers
    execution_time_seconds: Optional[float] = None


class SearchHistoryItem(BaseModel):
    """A search in the history."""
    id: str
    region: Optional[str]
    sector: Optional[str]
    company_size: Optional[str]
    proposition: Optional[str]
    reference_customers: Optional[List[str]] = None
    status: str
    results_count: int
    created_at: datetime


class SearchHistoryResponse(BaseModel):
    """Response with search history."""
    searches: List[SearchHistoryItem]


class ImportProspectRequest(BaseModel):
    """Request to import a discovered prospect."""
    result_id: str


class ImportProspectResponse(BaseModel):
    """Response after importing a prospect."""
    success: bool
    prospect_id: Optional[str] = None
    message: str


# =============================================================================
# Endpoints
# =============================================================================

class ProspectingSearchStartResponse(BaseModel):
    """Response when starting an async prospecting search."""
    search_id: str
    status: str
    message: str


@router.post("/search", response_model=ProspectingSearchStartResponse)
async def start_prospecting_search(
    request: ProspectingSearchRequest,
    user_org: tuple = Depends(get_user_org)
):
    """
    Start a new prospecting search (async via Inngest).
    
    This creates a search record and triggers background processing.
    Use GET /searches/{search_id} to poll for results.
    
    The search process (via Inngest):
    1. Uses your seller profile context
    2. Generates semantic search queries
    3. Searches for matching companies
    4. Scores each for fit
    5. Saves results to database
    """
    user_id, organization_id = user_org
    
    logger.info(f"[PROSPECTING] Starting async search for user {user_id}")
    
    # Check usage limit (counts as a flow)
    usage_service = get_usage_service()
    can_use = await usage_service.check_flow_limit(organization_id)
    
    if not can_use:
        raise HTTPException(
            status_code=402,
            detail="Flow limit reached. Upgrade your plan or purchase a flow pack."
        )
    
    # Get discovery service to check availability
    discovery_service = get_prospect_discovery_service()
    
    if not discovery_service.is_available:
        raise HTTPException(
            status_code=503,
            detail="Prospecting service is not available. Check API configuration."
        )
    
    supabase = get_supabase_service()
    
    # Create search record with pending status
    search_data = {
        "organization_id": organization_id,
        "user_id": user_id,
        "region": request.region,
        "sector": request.sector,
        "company_size": request.company_size,
        "proposition": request.proposition,
        "target_role": request.target_role,
        "pain_point": request.pain_point,
        "reference_customers": request.reference_customers or [],
        "status": "pending"
    }
    
    result = supabase.table("prospecting_searches").insert(search_data).execute()
    
    if not result.data:
        raise HTTPException(status_code=500, detail="Failed to create search record")
    
    search_id = result.data[0]["id"]
    
    # Increment usage now (before async processing)
    await usage_service.increment_flow(organization_id)
    
    # Trigger Inngest event for async processing
    await send_event(
        event_name="prospecting/discover",
        data={
            "search_id": search_id,
            "user_id": user_id,
            "organization_id": organization_id,
            "max_results": request.max_results,
            "input": {
                "region": request.region,
                "sector": request.sector,
                "company_size": request.company_size,
                "proposition": request.proposition,
                "target_role": request.target_role,
                "pain_point": request.pain_point,
                "reference_customers": request.reference_customers
            }
        }
    )
    
    logger.info(f"[PROSPECTING] Created search {search_id}, triggered Inngest")
    
    return ProspectingSearchStartResponse(
        search_id=search_id,
        status="pending",
        message="Search started. Poll /searches/{search_id} for results."
    )


@router.get("/searches", response_model=SearchHistoryResponse)
async def get_search_history(
    limit: int = 10,
    user_org: tuple = Depends(get_user_org)
):
    """
    Get recent prospecting searches for the organization.
    """
    user_id, organization_id = user_org
    
    discovery_service = get_prospect_discovery_service()
    searches = await discovery_service.get_search_history(
        organization_id=organization_id,
        limit=limit
    )
    
    items = [
        SearchHistoryItem(
            id=s["id"],
            region=s.get("region"),
            sector=s.get("sector"),
            company_size=s.get("company_size"),
            proposition=s.get("proposition"),
            reference_customers=s.get("reference_customers"),
            status=s["status"],
            results_count=s.get("results_count", 0),
            created_at=s["created_at"]
        )
        for s in searches
    ]
    
    return SearchHistoryResponse(searches=items)


@router.get("/searches/{search_id}", response_model=ProspectingResultsResponse)
async def get_search_results(
    search_id: str,
    min_score: int = 0,
    user_org: tuple = Depends(get_user_org)
):
    """
    Get results for a specific prospecting search.
    
    - min_score: Only return prospects with fit_score >= this value
    """
    user_id, organization_id = user_org
    
    supabase = get_supabase_service()
    
    # Get search
    search_response = supabase.table("prospecting_searches")\
        .select("*")\
        .eq("id", search_id)\
        .eq("organization_id", organization_id)\
        .single()\
        .execute()
    
    if not search_response.data:
        raise HTTPException(status_code=404, detail="Search not found")
    
    search = search_response.data
    
    # Get results
    discovery_service = get_prospect_discovery_service()
    results = await discovery_service.get_search_results(
        search_id=search_id,
        min_score=min_score
    )
    
    prospects = [
        DiscoveredProspectResponse(
            id=r["id"],
            company_name=r["company_name"],
            website=r.get("website"),
            linkedin_url=r.get("linkedin_url"),
            inferred_sector=r.get("inferred_sector"),
            inferred_region=r.get("inferred_region"),
            inferred_size=r.get("inferred_size"),
            fit_score=r.get("fit_score", 0),
            proposition_fit=r.get("proposition_fit", 0),
            seller_fit=r.get("seller_fit", 0),
            intent_score=r.get("intent_score", 0),
            recency_score=r.get("recency_score", 0),
            fit_reason=r.get("fit_reason"),
            key_signal=r.get("key_signal"),
            source_url=r.get("source_url"),
            source_title=r.get("source_title"),
            source_published_date=r.get("source_published_date"),
            prospect_id=r.get("prospect_id"),
            imported_at=r.get("imported_at")
        )
        for r in results
    ]
    
    return ProspectingResultsResponse(
        search_id=search_id,
        status=search["status"],
        generated_queries=search.get("generated_queries", []),
        prospects=prospects,
        total_count=len(prospects),
        reference_context=search.get("reference_context"),
        execution_time_seconds=search.get("execution_time_seconds")
    )


@router.post("/import", response_model=ImportProspectResponse)
async def import_prospect(
    request: ImportProspectRequest,
    user_org: tuple = Depends(get_user_org)
):
    """
    Import a discovered prospect into your prospects list.
    
    This creates a new prospect from a discovery result,
    allowing you to then research them in detail.
    """
    user_id, organization_id = user_org
    
    discovery_service = get_prospect_discovery_service()
    prospect_id = await discovery_service.import_to_prospects(
        result_id=request.result_id,
        organization_id=organization_id
    )
    
    if prospect_id:
        return ImportProspectResponse(
            success=True,
            prospect_id=prospect_id,
            message="Prospect imported successfully"
        )
    else:
        return ImportProspectResponse(
            success=False,
            message="Failed to import prospect. It may already be imported."
        )


@router.delete("/searches/{search_id}")
async def delete_search(
    search_id: str,
    user_org: tuple = Depends(get_user_org)
):
    """Delete a prospecting search and its results."""
    user_id, organization_id = user_org
    
    supabase = get_supabase_service()
    
    # Verify ownership
    search = supabase.table("prospecting_searches")\
        .select("id")\
        .eq("id", search_id)\
        .eq("organization_id", organization_id)\
        .single()\
        .execute()
    
    if not search.data:
        raise HTTPException(status_code=404, detail="Search not found")
    
    # Delete (cascade will handle results)
    supabase.table("prospecting_searches")\
        .delete()\
        .eq("id", search_id)\
        .execute()
    
    return {"success": True, "message": "Search deleted"}


@router.get("/check")
async def check_prospecting_available(
    user_org: tuple = Depends(get_user_org)
):
    """
    Check if prospecting service is available and user has required context.
    """
    user_id, organization_id = user_org
    
    supabase = get_supabase_service()
    discovery_service = get_prospect_discovery_service()
    
    # Check service availability
    service_available = discovery_service.is_available
    
    # Check for seller profile
    sales_profile = supabase.table("sales_profiles")\
        .select("id, profile_completeness")\
        .eq("user_id", user_id)\
        .limit(1)\
        .execute()
    
    has_sales_profile = bool(sales_profile.data)
    profile_completeness = sales_profile.data[0].get("profile_completeness", 0) if sales_profile.data else 0
    
    # Check for company profile
    company_profile = supabase.table("company_profiles")\
        .select("id, profile_completeness")\
        .eq("organization_id", organization_id)\
        .limit(1)\
        .execute()
    
    has_company_profile = bool(company_profile.data)
    company_completeness = company_profile.data[0].get("profile_completeness", 0) if company_profile.data else 0
    
    # Recommendations
    recommendations = []
    if not has_sales_profile:
        recommendations.append("Complete your sales profile for better prospect matching")
    elif profile_completeness < 50:
        recommendations.append("Your sales profile is incomplete - add more details for better results")
    
    if not has_company_profile:
        recommendations.append("Add your company profile to improve prospect discovery")
    elif company_completeness < 50:
        recommendations.append("Your company profile is incomplete - add products and ICP details")
    
    return {
        "available": service_available,
        "has_sales_profile": has_sales_profile,
        "sales_profile_completeness": profile_completeness,
        "has_company_profile": has_company_profile,
        "company_profile_completeness": company_completeness,
        "ready": service_available and has_sales_profile and has_company_profile,
        "recommendations": recommendations
    }

