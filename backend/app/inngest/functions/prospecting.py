"""
Prospecting Discovery Inngest Functions.

Async processing for prospect discovery searches.
Used for larger searches or when we want to process in the background.
"""

import logging
from datetime import datetime
from inngest import TriggerEvent

from app.inngest import inngest_client
from app.database import get_supabase_service
from app.services.prospect_discovery import (
    get_prospect_discovery_service,
    DiscoveryInput
)

logger = logging.getLogger(__name__)


@inngest_client.create_function(
    fn_id="prospecting-discovery",
    trigger=TriggerEvent(event="prospecting/discover"),
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
    max_results = data.get("max_results", 25)
    input_data = data.get("input", {})
    
    print(f"[PROSPECTING_INNGEST] 🚀 START Processing search {search_id}")
    print(f"[PROSPECTING_INNGEST] Input: region={input_data.get('region')}, sector={input_data.get('sector')}")
    logger.info(f"[PROSPECTING_INNGEST] Processing search {search_id} (max_results={max_results})")
    
    supabase = get_supabase_service()
    
    # Step 1: Update status to searching
    def update_status_searching():
        supabase.table("prospecting_searches")\
            .update({"status": "searching"})\
            .eq("id", search_id)\
            .execute()
        return {"updated": True}  # Return serializable data
    
    await step.run("update-status-searching", update_status_searching)
    
    # Step 2: Build input and run discovery
    input_obj = DiscoveryInput(
        region=input_data.get("region"),
        sector=input_data.get("sector"),
        company_size=input_data.get("company_size"),
        proposition=input_data.get("proposition"),
        target_role=input_data.get("target_role"),
        pain_point=input_data.get("pain_point"),
        reference_customers=input_data.get("reference_customers")
    )
    
    discovery_service = get_prospect_discovery_service()
    print(f"[PROSPECTING_INNGEST] Discovery service available: {discovery_service.is_available}")
    
    async def run_discovery():
        print(f"[PROSPECTING_INNGEST] 🔍 Calling discover_prospects...")
        result = await discovery_service.discover_prospects(
            user_id=user_id,
            organization_id=organization_id,
            input=input_obj,
            max_results=max_results
        )
        
        print(f"[PROSPECTING_INNGEST] ✅ Discovery result: success={result.success}, prospects={len(result.prospects)}, error={result.error}")
        
        # Convert to serializable dict
        return {
            "success": result.success,
            "error": result.error,
            "generated_queries": result.generated_queries,
            "reference_context": result.reference_context,
            "execution_time_seconds": result.execution_time_seconds,
            "prospects": [
                {
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
                    "source_published_date": p.source_published_date if p.source_published_date else None,
                    "matched_query": p.matched_query
                }
                for p in result.prospects
            ]
        }
    
    result = await step.run("run-discovery", run_discovery)
    
    # Step 3: Handle failure
    if not result["success"]:
        def update_status_failed():
            supabase.table("prospecting_searches")\
                .update({
                    "status": "failed",
                    "error_message": result["error"],
                    "completed_at": datetime.now().isoformat()
                })\
                .eq("id", search_id)\
                .execute()
            return {"updated": True}
        
        await step.run("update-status-failed", update_status_failed)
        return {"success": False, "error": result["error"]}
    
    # Step 4: Save results
    def save_results():
        prospects = result["prospects"]
        
        if prospects:
            results_data = [
                {
                    "search_id": search_id,
                    "organization_id": organization_id,
                    "company_name": p["company_name"],
                    "website": p["website"],
                    "linkedin_url": p["linkedin_url"],
                    "inferred_sector": p["inferred_sector"],
                    "inferred_region": p["inferred_region"],
                    "inferred_size": p["inferred_size"],
                    "fit_score": p["fit_score"],
                    "proposition_fit": p["proposition_fit"],
                    "seller_fit": p["seller_fit"],
                    "intent_score": p["intent_score"],
                    "recency_score": p["recency_score"],
                    "fit_reason": p["fit_reason"],
                    "key_signal": p["key_signal"],
                    "source_url": p["source_url"],
                    "source_title": p["source_title"],
                    "source_snippet": p["source_snippet"],
                    "source_published_date": p["source_published_date"],
                    "matched_query": p["matched_query"]
                }
                for p in prospects
            ]
            
            supabase.table("prospecting_results").insert(results_data).execute()
        
        # Update search status
        supabase.table("prospecting_searches").update({
            "status": "completed",
            "generated_queries": result["generated_queries"],
            "results_count": len(prospects),
            "execution_time_seconds": result["execution_time_seconds"],
            "completed_at": datetime.now().isoformat()
        }).eq("id", search_id).execute()
        
        return {"saved": True, "count": len(prospects)}
    
    save_result = await step.run("save-results", save_results)
    
    logger.info(f"[PROSPECTING_INNGEST] Completed search {search_id} with {save_result['count']} prospects")
    
    return {
        "success": True,
        "search_id": search_id,
        "prospects_found": save_result["count"]
    }
