"""
Prospecting Discovery Inngest Functions.

Async processing for prospect discovery searches.
Used for larger searches or when we want to process in the background.
"""

import logging
from datetime import datetime

from app.inngest import inngest_client
from app.database import get_supabase_service
from app.services.prospect_discovery import (
    get_prospect_discovery_service,
    DiscoveryInput
)

logger = logging.getLogger(__name__)


@inngest_client.create_function(
    fn_id="prospecting-discovery",
    trigger=inngest_client.TriggerEvent(event="prospecting/discover"),
    retries=1,
)
async def process_prospecting_discovery_fn(ctx, step):
    """
    Process a prospecting discovery search asynchronously.
    
    Event data:
    - search_id: ID of the search record
    - user_id: User ID
    - organization_id: Organization ID
    - input: Discovery input parameters
    """
    data = ctx.event.data
    search_id = data.get("search_id")
    user_id = data.get("user_id")
    organization_id = data.get("organization_id")
    input_data = data.get("input", {})
    
    logger.info(f"[PROSPECTING_INNGEST] Processing search {search_id}")
    
    supabase = get_supabase_service()
    
    # Update status to searching
    await step.run("update-status-searching", lambda: (
        supabase.table("prospecting_searches")
        .update({"status": "searching"})
        .eq("id", search_id)
        .execute()
    ))
    
    # Build input
    input = DiscoveryInput(
        region=input_data.get("region"),
        sector=input_data.get("sector"),
        company_size=input_data.get("company_size"),
        proposition=input_data.get("proposition"),
        target_role=input_data.get("target_role"),
        pain_point=input_data.get("pain_point")
    )
    
    # Run discovery
    discovery_service = get_prospect_discovery_service()
    
    async def run_discovery():
        return await discovery_service.discover_prospects(
            user_id=user_id,
            organization_id=organization_id,
            input=input,
            max_results=20
        )
    
    result = await step.run("run-discovery", run_discovery)
    
    if not result.success:
        # Update status to failed
        await step.run("update-status-failed", lambda: (
            supabase.table("prospecting_searches")
            .update({
                "status": "failed",
                "error_message": result.error,
                "completed_at": datetime.now().isoformat()
            })
            .eq("id", search_id)
            .execute()
        ))
        return {"success": False, "error": result.error}
    
    # Save results
    async def save_results():
        if result.prospects:
            results_data = [
                {
                    "search_id": search_id,
                    "organization_id": organization_id,
                    "company_name": p.company_name,
                    "website": p.website,
                    "linkedin_url": p.linkedin_url,
                    "inferred_sector": p.inferred_sector,
                    "inferred_region": p.inferred_region,
                    "inferred_size": p.inferred_size,
                    "fit_score": p.fit_score,
                    "proposition_fit": p.proposition_fit,
                    "seller_fit": p.seller_fit,
                    "intent_score": p.intent_score,
                    "recency_score": p.recency_score,
                    "fit_reason": p.fit_reason,
                    "key_signal": p.key_signal,
                    "source_url": p.source_url,
                    "source_title": p.source_title,
                    "source_snippet": p.source_snippet,
                    "source_published_date": p.source_published_date,
                    "matched_query": p.matched_query
                }
                for p in result.prospects
            ]
            
            supabase.table("prospecting_results").insert(results_data).execute()
        
        # Update search status
        supabase.table("prospecting_searches").update({
            "status": "completed",
            "generated_queries": result.generated_queries,
            "results_count": len(result.prospects),
            "execution_time_seconds": result.execution_time_seconds,
            "completed_at": datetime.now().isoformat()
        }).eq("id", search_id).execute()
    
    await step.run("save-results", save_results)
    
    logger.info(f"[PROSPECTING_INNGEST] Completed search {search_id} with {len(result.prospects)} prospects")
    
    return {
        "success": True,
        "search_id": search_id,
        "prospects_found": len(result.prospects)
    }

