"""
DealMotion Autopilot - API Router
SPEC-045 / TASK-048

Endpoints for the Autopilot feature.
"""

from fastapi import APIRouter, Depends, HTTPException, Query
from typing import Optional, List
from datetime import datetime, timedelta
import logging

from app.deps import get_current_user
from app.database import get_supabase_service
from app.models.autopilot import (
    AutopilotProposal,
    ProposalsResponse,
    ProposalCounts,
    ProposalActionRequest,
    AutopilotSettings,
    AutopilotSettingsUpdate,
    AutopilotStats,
    MeetingOutcome,
    OutcomeRequest,
    PrepViewedRequest,
)
from app.services.autopilot_orchestrator import AutopilotOrchestrator

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1/autopilot", tags=["autopilot"])


# =============================================================================
# PROPOSALS ENDPOINTS
# =============================================================================

@router.get("/proposals", response_model=ProposalsResponse)
async def get_proposals(
    status: Optional[str] = Query(None, description="Filter by status"),
    limit: int = Query(20, ge=1, le=100),
    current_user: dict = Depends(get_current_user)
):
    """
    Get autopilot proposals for the current user.
    
    Returns proposals sorted by priority (highest first).
    """
    user_id = current_user["sub"]
    
    try:
        orchestrator = AutopilotOrchestrator()
        proposals, counts = await orchestrator.get_proposals(
            user_id=user_id,
            status=status,
            limit=limit
        )
        
        return ProposalsResponse(
            proposals=proposals,
            counts=counts,
            total=len(proposals)
        )
        
    except Exception as e:
        logger.error(f"Error getting proposals: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/proposals/{proposal_id}", response_model=AutopilotProposal)
async def get_proposal(
    proposal_id: str,
    current_user: dict = Depends(get_current_user)
):
    """Get a specific proposal by ID."""
    user_id = current_user["sub"]
    
    try:
        orchestrator = AutopilotOrchestrator()
        proposal = await orchestrator.get_proposal(
            proposal_id=proposal_id,
            user_id=user_id
        )
        
        if not proposal:
            raise HTTPException(status_code=404, detail="Proposal not found")
        
        return proposal
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting proposal {proposal_id}: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/proposals/{proposal_id}/accept", response_model=AutopilotProposal)
async def accept_proposal(
    proposal_id: str,
    request: Optional[ProposalActionRequest] = None,
    current_user: dict = Depends(get_current_user)
):
    """
    Accept a proposal and trigger execution.
    
    The proposal will be executed asynchronously via Inngest.
    """
    user_id = current_user["sub"]
    
    try:
        orchestrator = AutopilotOrchestrator()
        proposal = await orchestrator.accept_proposal(
            proposal_id=proposal_id,
            user_id=user_id,
            reason=request.reason if request else None
        )
        
        return proposal
        
    except Exception as e:
        logger.error(f"Error accepting proposal {proposal_id}: {e}")
        if "not found" in str(e).lower():
            raise HTTPException(status_code=404, detail="Proposal not found or already processed")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/proposals/{proposal_id}/decline", response_model=AutopilotProposal)
async def decline_proposal(
    proposal_id: str,
    request: Optional[ProposalActionRequest] = None,
    current_user: dict = Depends(get_current_user)
):
    """Decline a proposal."""
    user_id = current_user["sub"]
    
    try:
        orchestrator = AutopilotOrchestrator()
        proposal = await orchestrator.decline_proposal(
            proposal_id=proposal_id,
            user_id=user_id,
            reason=request.reason if request else None
        )
        
        return proposal
        
    except Exception as e:
        logger.error(f"Error declining proposal {proposal_id}: {e}")
        if "not found" in str(e).lower():
            raise HTTPException(status_code=404, detail="Proposal not found or already processed")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/proposals/{proposal_id}/snooze", response_model=AutopilotProposal)
async def snooze_proposal(
    proposal_id: str,
    request: ProposalActionRequest,
    current_user: dict = Depends(get_current_user)
):
    """
    Snooze a proposal until a specific time.
    
    Requires `snooze_until` in the request body.
    """
    user_id = current_user["sub"]
    
    if not request.snooze_until:
        raise HTTPException(status_code=400, detail="snooze_until is required")
    
    try:
        orchestrator = AutopilotOrchestrator()
        proposal = await orchestrator.snooze_proposal(
            proposal_id=proposal_id,
            user_id=user_id,
            until=request.snooze_until,
            reason=request.reason
        )
        
        return proposal
        
    except Exception as e:
        logger.error(f"Error snoozing proposal {proposal_id}: {e}")
        if "not found" in str(e).lower():
            raise HTTPException(status_code=404, detail="Proposal not found or already processed")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/proposals/{proposal_id}/retry", response_model=AutopilotProposal)
async def retry_proposal(
    proposal_id: str,
    current_user: dict = Depends(get_current_user)
):
    """
    Retry a failed proposal.
    
    Only works for proposals in 'failed' status.
    """
    user_id = current_user["sub"]
    
    try:
        orchestrator = AutopilotOrchestrator()
        proposal = await orchestrator.retry_proposal(
            proposal_id=proposal_id,
            user_id=user_id
        )
        
        return proposal
        
    except Exception as e:
        logger.error(f"Error retrying proposal {proposal_id}: {e}")
        if "not found" in str(e).lower() or "not in failed" in str(e).lower():
            raise HTTPException(status_code=404, detail="Proposal not found or not in failed status")
        raise HTTPException(status_code=500, detail=str(e))


# =============================================================================
# SETTINGS ENDPOINTS
# =============================================================================

@router.get("/settings", response_model=AutopilotSettings)
async def get_settings(current_user: dict = Depends(get_current_user)):
    """Get autopilot settings for the current user."""
    user_id = current_user["sub"]
    
    try:
        orchestrator = AutopilotOrchestrator()
        settings = await orchestrator.get_settings(user_id)
        return settings
        
    except Exception as e:
        logger.error(f"Error getting settings: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.patch("/settings", response_model=AutopilotSettings)
async def update_settings(
    updates: AutopilotSettingsUpdate,
    current_user: dict = Depends(get_current_user)
):
    """Update autopilot settings."""
    user_id = current_user["sub"]
    
    try:
        orchestrator = AutopilotOrchestrator()
        settings = await orchestrator.update_settings(user_id, updates)
        return settings
        
    except Exception as e:
        logger.error(f"Error updating settings: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# =============================================================================
# STATS ENDPOINT
# =============================================================================

@router.get("/stats", response_model=AutopilotStats)
async def get_stats(current_user: dict = Depends(get_current_user)):
    """
    Get autopilot stats for the home page.
    
    Includes:
    - Pending proposal count
    - Urgent proposal count
    - Completed today count
    - Upcoming meetings
    - Luna greeting
    """
    user_id = current_user["sub"]
    
    try:
        # Get organization ID
        supabase = get_supabase_service()
        org_result = supabase.table("organization_members") \
            .select("organization_id") \
            .eq("user_id", user_id) \
            .execute()
        
        if not org_result.data:
            raise HTTPException(status_code=400, detail="User has no organization")
        
        organization_id = org_result.data[0]["organization_id"]
        
        orchestrator = AutopilotOrchestrator()
        stats = await orchestrator.get_stats(user_id, organization_id)
        return stats
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting stats: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# =============================================================================
# OUTCOMES ENDPOINTS
# =============================================================================

@router.post("/outcomes", response_model=MeetingOutcome)
async def record_outcome(
    request: OutcomeRequest,
    current_user: dict = Depends(get_current_user)
):
    """
    Record a meeting outcome for learning.
    
    This helps Autopilot learn what works for you.
    """
    user_id = current_user["sub"]
    
    try:
        # Get organization ID
        supabase = get_supabase_service()
        org_result = supabase.table("organization_members") \
            .select("organization_id") \
            .eq("user_id", user_id) \
            .execute()
        
        if not org_result.data:
            raise HTTPException(status_code=400, detail="User has no organization")
        
        organization_id = org_result.data[0]["organization_id"]
        
        orchestrator = AutopilotOrchestrator()
        outcome = await orchestrator.record_outcome(
            user_id=user_id,
            organization_id=organization_id,
            outcome=request
        )
        return outcome
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error recording outcome: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/prep-viewed")
async def record_prep_viewed(
    request: PrepViewedRequest,
    current_user: dict = Depends(get_current_user)
):
    """
    Record that a prep was viewed.
    
    Used for implicit learning about prep engagement.
    """
    user_id = current_user["sub"]
    
    try:
        # Get organization ID
        supabase = get_supabase_service()
        org_result = supabase.table("organization_members") \
            .select("organization_id") \
            .eq("user_id", user_id) \
            .execute()
        
        if not org_result.data:
            return {"success": True, "message": "No organization"}
        
        organization_id = org_result.data[0]["organization_id"]
        
        orchestrator = AutopilotOrchestrator()
        await orchestrator.record_prep_viewed(
            user_id=user_id,
            organization_id=organization_id,
            preparation_id=request.preparation_id,
            view_duration_seconds=request.view_duration_seconds,
            scroll_depth=request.scroll_depth
        )
        
        return {"success": True}
        
    except Exception as e:
        logger.error(f"Error recording prep viewed: {e}")
        # Don't fail - this is non-critical
        return {"success": False, "error": str(e)}
