"""
Autopilot Execution Inngest Function.
SPEC-045 / TASK-048

Executes accepted proposals by triggering appropriate pipelines:
- Research + Prep for new meetings
- Prep only for known prospects
- Follow-up pack for ended meetings
"""

import logging
from datetime import datetime
import inngest
from inngest import TriggerEvent

from app.inngest.client import inngest_client
from app.database import get_supabase_service

logger = logging.getLogger(__name__)


@inngest_client.create_function(
    fn_id="autopilot-execute-proposal",
    trigger=TriggerEvent(event="autopilot/proposal.accepted"),
    retries=2,  # Retry on transient failures
)
async def execute_proposal_fn(ctx, step):
    """
    Execute an accepted proposal by triggering appropriate pipelines.
    
    Triggered when:
    - User accepts a proposal via the UI
    - User retries a failed proposal
    
    Handles:
    - research_prep: Research first, then prep
    - prep_only: Prep directly
    - followup_pack: Follow-up generation
    - reactivation: Special prep
    - complete_flow: Prep for next step
    """
    from app.services.autopilot_orchestrator import AutopilotOrchestrator
    from app.models.autopilot import ProposalType
    
    event_data = ctx.event.data
    proposal_id = event_data.get("proposal_id")
    user_id = event_data.get("user_id")
    organization_id = event_data.get("organization_id")
    proposal_type = event_data.get("proposal_type")
    context_data = event_data.get("context_data", {})
    
    logger.info(f"Executing proposal {proposal_id} of type {proposal_type}")
    
    orchestrator = AutopilotOrchestrator()
    supabase = get_supabase_service()
    
    try:
        # Step 1: Update status to executing
        await step.run("update-status-executing", lambda: 
            update_status(orchestrator, proposal_id, "executing")
        )
        
        # Step 2: Execute based on proposal type AND flow_step
        artifacts = []
        
        # Get the specific action from context_data (set by /detect endpoint)
        flow_step = context_data.get("flow_step")
        action_route = context_data.get("action_route")
        
        # =====================================================================
        # NAVIGATIONAL PROPOSALS (no auto-execution, just redirect)
        # These proposals require manual user action - we just mark complete
        # =====================================================================
        
        if flow_step in ["add_contacts", "generate_actions"]:
            # These can't be auto-executed - user needs to do this manually
            # Just mark as completed with a redirect route
            logger.info(f"Navigational proposal {proposal_id}: {flow_step} -> {action_route}")
            artifacts.append({
                "type": "redirect",
                "route": action_route,
                "message": "Ga naar de juiste pagina om deze actie uit te voeren"
            })
        
        # =====================================================================
        # EXECUTABLE PROPOSALS
        # =====================================================================
        
        elif proposal_type == "research_prep":
            # Research + Prep flow
            research_id = await step.run("execute-research", lambda:
                execute_research(
                    supabase,
                    user_id=user_id,
                    organization_id=organization_id,
                    context_data=context_data
                )
            )
            
            if research_id:
                artifacts.append({"type": "research", "id": research_id})
            
            # Wait for research to complete (non-blocking poll using step.sleep)
            research_complete = await wait_for_completion_async(
                step, supabase, "research_briefs", research_id, max_attempts=30
            )
            
            if research_complete:
                prep_id = await step.run("execute-prep", lambda:
                    execute_prep(
                        supabase,
                        user_id=user_id,
                        organization_id=organization_id,
                        research_id=research_id,
                        context_data=context_data
                    )
                )
                
                if prep_id:
                    artifacts.append({"type": "prep", "id": prep_id})
        
        elif proposal_type == "prep_only" or flow_step == "create_prep":
            # Prep only
            prep_id = await step.run("execute-prep", lambda:
                execute_prep(
                    supabase,
                    user_id=user_id,
                    organization_id=organization_id,
                    context_data=context_data
                )
            )
            
            if prep_id:
                artifacts.append({"type": "prep", "id": prep_id})
        
        elif proposal_type == "followup_pack" or flow_step == "meeting_analysis":
            # Follow-up generation (creates record, user still needs to upload transcript)
            followup_id = await step.run("execute-followup", lambda:
                execute_followup(
                    supabase,
                    user_id=user_id,
                    organization_id=organization_id,
                    context_data=context_data
                )
            )
            
            if followup_id:
                artifacts.append({"type": "followup", "id": followup_id})
                # Add route for user to upload transcript
                artifacts.append({
                    "type": "redirect",
                    "route": f"/dashboard/followup/{followup_id}",
                    "message": "Upload je meeting recording om de analyse te starten"
                })
        
        elif proposal_type == "reactivation":
            # Reactivation prep
            prep_id = await step.run("execute-prep", lambda:
                execute_prep(
                    supabase,
                    user_id=user_id,
                    organization_id=organization_id,
                    context_data=context_data,
                    meeting_type="reactivation"
                )
            )
            
            if prep_id:
                artifacts.append({"type": "prep", "id": prep_id})
        
        elif proposal_type == "complete_flow":
            # Complete flow - check if we should create prep or just redirect
            if context_data.get("research_id") and context_data.get("prospect_id"):
                # We have research, create prep
                prep_id = await step.run("execute-prep", lambda:
                    execute_prep(
                        supabase,
                        user_id=user_id,
                        organization_id=organization_id,
                        context_data=context_data,
                        meeting_type="discovery"
                    )
                )
                
                if prep_id:
                    artifacts.append({"type": "prep", "id": prep_id})
            else:
                # No valid execution path, just mark as redirect
                artifacts.append({
                    "type": "redirect",
                    "route": action_route or "/dashboard",
                    "message": "Actie vereist handmatige stappen"
                })
        
        # Step 3: Update status to completed
        await step.run("update-status-completed", lambda:
            update_status(
                orchestrator, 
                proposal_id, 
                "completed",
                artifacts=artifacts
            )
        )
        
        logger.info(f"Proposal {proposal_id} executed successfully with {len(artifacts)} artifacts")
        
        return {
            "success": True,
            "proposal_id": proposal_id,
            "artifacts": artifacts
        }
        
    except Exception as e:
        logger.error(f"Error executing proposal {proposal_id}: {e}")
        
        # Update status to failed
        try:
            await update_status(orchestrator, proposal_id, "failed", error=str(e))
        except:
            pass
        
        raise  # Re-raise for Inngest retry logic


# =============================================================================
# HELPER FUNCTIONS
# =============================================================================

async def update_status(orchestrator, proposal_id: str, status: str, artifacts=None, error=None):
    """Update proposal status."""
    await orchestrator.update_proposal_status(
        proposal_id=proposal_id,
        status=status,
        artifacts=artifacts,
        error=error
    )


def execute_research(supabase, user_id: str, organization_id: str, context_data: dict) -> str:
    """
    Create a research brief and trigger the research pipeline.
    
    Returns the research_id.
    """
    meeting_id = context_data.get("meeting_id")
    meeting_title = context_data.get("meeting_title", "Unknown")
    
    # Get meeting details if we have a meeting_id
    company_name = meeting_title
    if meeting_id:
        meeting_result = supabase.table("calendar_meetings") \
            .select("title, attendees") \
            .eq("id", meeting_id) \
            .execute()
        
        if meeting_result.data:
            company_name = meeting_result.data[0].get("title", meeting_title)
    
    # Create research brief
    research_data = {
        "user_id": user_id,
        "organization_id": organization_id,
        "company_name": company_name,
        "status": "pending",
        "language": "en",
    }
    
    result = supabase.table("research_briefs") \
        .insert(research_data) \
        .execute()
    
    if not result.data:
        raise Exception("Failed to create research brief")
    
    research_id = result.data[0]["id"]
    
    # Trigger research pipeline via Inngest event
    from app.inngest.client import inngest_client
    import asyncio
    
    asyncio.get_event_loop().run_until_complete(
        inngest_client.send({
            "name": "dealmotion/research.requested",
            "data": {
                "research_id": research_id,
                "user_id": user_id,
                "organization_id": organization_id,
            }
        })
    )
    
    logger.info(f"Created research {research_id} for {company_name}")
    return research_id


def execute_prep(
    supabase, 
    user_id: str, 
    organization_id: str, 
    context_data: dict,
    research_id: str = None,
    meeting_type: str = "discovery"
) -> str:
    """
    Create a meeting prep and trigger the prep pipeline.
    
    Returns the prep_id.
    """
    prospect_id = context_data.get("prospect_id")
    meeting_id = context_data.get("meeting_id")
    company_name = context_data.get("company_name", "Unknown")
    
    # If we have a research_id, use it; otherwise try to find one
    if not research_id and prospect_id:
        research_result = supabase.table("research_briefs") \
            .select("id") \
            .eq("prospect_id", prospect_id) \
            .eq("status", "completed") \
            .order("created_at", desc=True) \
            .limit(1) \
            .execute()
        
        if research_result.data:
            research_id = research_result.data[0]["id"]
    
    # Create meeting prep
    prep_data = {
        "user_id": user_id,
        "organization_id": organization_id,
        "prospect_id": prospect_id,
        "research_brief_id": research_id,
        "prospect_company_name": company_name,
        "meeting_type": meeting_type,
        "status": "pending",
        "language": "en",
    }
    
    result = supabase.table("meeting_preps") \
        .insert(prep_data) \
        .execute()
    
    if not result.data:
        raise Exception("Failed to create meeting prep")
    
    prep_id = result.data[0]["id"]
    
    # Link prep to calendar meeting if applicable
    if meeting_id:
        supabase.table("calendar_meetings") \
            .update({"preparation_id": prep_id}) \
            .eq("id", meeting_id) \
            .execute()
    
    # Trigger prep pipeline via Inngest event
    from app.inngest.client import inngest_client
    import asyncio
    
    asyncio.get_event_loop().run_until_complete(
        inngest_client.send({
            "name": "dealmotion/prep.requested",
            "data": {
                "prep_id": prep_id,
                "user_id": user_id,
                "organization_id": organization_id,
            }
        })
    )
    
    logger.info(f"Created prep {prep_id} for {company_name}")
    return prep_id


def execute_followup(
    supabase, 
    user_id: str, 
    organization_id: str, 
    context_data: dict
) -> str:
    """
    Create a follow-up and trigger the follow-up pipeline.
    
    Returns the followup_id.
    """
    meeting_id = context_data.get("meeting_id")
    prospect_id = context_data.get("prospect_id")
    company_name = context_data.get("company_name", "Unknown")
    
    # Create follow-up record
    followup_data = {
        "user_id": user_id,
        "organization_id": organization_id,
        "prospect_id": prospect_id,
        "calendar_meeting_id": meeting_id,
        "prospect_company_name": company_name,
        "meeting_subject": f"Follow-up: {company_name}",
        "status": "pending",
    }
    
    result = supabase.table("followups") \
        .insert(followup_data) \
        .execute()
    
    if not result.data:
        raise Exception("Failed to create follow-up")
    
    followup_id = result.data[0]["id"]
    
    # Link follow-up to calendar meeting
    if meeting_id:
        supabase.table("calendar_meetings") \
            .update({"followup_id": followup_id}) \
            .eq("id", meeting_id) \
            .execute()
    
    # Note: Follow-up pipeline is typically triggered by transcript upload
    # For now, just create the record - user will need to upload transcript
    
    logger.info(f"Created follow-up {followup_id} for {company_name}")
    return followup_id


def check_completion_status(supabase, table: str, record_id: str) -> str:
    """
    Check the status of a record.
    
    Returns: 'completed', 'failed', or 'pending'
    """
    result = supabase.table(table) \
        .select("status") \
        .eq("id", record_id) \
        .execute()
    
    if result.data:
        status = result.data[0].get("status")
        if status == "completed":
            return "completed"
        elif status == "failed":
            return "failed"
    
    return "pending"


async def wait_for_completion_async(step, supabase, table: str, record_id: str, max_attempts: int = 30) -> bool:
    """
    Wait for a record to reach 'completed' status using non-blocking step.sleep.
    
    Uses Inngest step.sleep for non-blocking waits (10 seconds between checks).
    """
    from datetime import timedelta
    
    for attempt in range(max_attempts):
        status = await step.run(
            f"check-{table}-status-{attempt}",
            lambda: check_completion_status(supabase, table, record_id)
        )
        
        if status == "completed":
            return True
        elif status == "failed":
            raise Exception(f"{table} {record_id} failed")
        
        # Non-blocking sleep using Inngest step.sleep
        await step.sleep(f"wait-for-{table}-{attempt}", timedelta(seconds=10))
    
    raise Exception(f"Timeout waiting for {table} {record_id} to complete")
