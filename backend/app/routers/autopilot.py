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


@router.post("/proposals/{proposal_id}/complete", response_model=AutopilotProposal)
async def complete_proposal_inline(
    proposal_id: str,
    current_user: dict = Depends(get_current_user)
):
    """
    Mark a proposal as completed directly (for inline actions).
    
    Use this when the user completed the action via an inline modal/sheet
    (e.g., adding contacts, creating prep) and the proposal should be
    marked complete WITHOUT triggering Inngest execution.
    """
    user_id = current_user["sub"]
    
    try:
        orchestrator = AutopilotOrchestrator()
        proposal = await orchestrator.complete_proposal_inline(
            proposal_id=proposal_id,
            user_id=user_id
        )
        
        return proposal
        
    except Exception as e:
        logger.error(f"Error completing proposal {proposal_id}: {e}")
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


# =============================================================================
# MANUAL DETECTION ENDPOINT
# =============================================================================

@router.post("/detect")
async def trigger_detection(
    prospect_id: Optional[str] = Query(None, description="Prospect ID to check for proposals"),
    current_user: dict = Depends(get_current_user)
):
    """
    Manually trigger proposal detection for existing prospects/researches.
    
    Checks the FULL sales flow and creates proposals for incomplete steps:
    1. Research ✓, Contacts ✗ → "Add contacts"
    2. Research ✓, Contacts ✓, Prep ✗ → "Create prep"
    3. Prep ✓, Meeting Analysis ✗ → "Upload recording"
    4. Meeting Analysis ✓, Actions ✗ → "Generate actions"
    
    If prospect_id is provided, checks only that prospect.
    If not provided, scans all prospects for the user.
    """
    from app.models.autopilot import (
        ProposalType, TriggerType, AutopilotProposalCreate,
        SuggestedAction,
    )
    
    user_id = current_user["sub"]
    
    try:
        supabase = get_supabase_service()
        orchestrator = AutopilotOrchestrator()
        
        # Get user settings
        settings = await orchestrator.get_settings(user_id)
        if not settings.enabled:
            return {"success": False, "reason": "autopilot_disabled", "created": 0}
        
        # Get organization ID
        org_result = supabase.table("organization_members") \
            .select("organization_id") \
            .eq("user_id", user_id) \
            .execute()
        
        if not org_result.data:
            return {"success": False, "reason": "no_organization", "created": 0}
        
        organization_id = org_result.data[0]["organization_id"]
        
        created_count = 0
        checked_count = 0
        proposals_created = []
        
        # =====================================================================
        # STRATEGY 1: Check prospects with research
        # =====================================================================
        
        # Get completed researches
        research_query = supabase.table("research_briefs") \
            .select("id, company_name, prospect_id") \
            .eq("organization_id", organization_id) \
            .eq("status", "completed")
        
        if prospect_id:
            research_query = research_query.eq("prospect_id", prospect_id)
        else:
            research_query = research_query.limit(30)
        
        research_result = research_query.execute()
        researches = research_result.data or []
        
        for research in researches:
            checked_count += 1
            r_id = research["id"]
            p_id = research.get("prospect_id")
            company = research.get("company_name", "Onbekend")
            
            if not p_id:
                continue
            
            # Check contacts
            contacts_result = supabase.table("prospect_contacts") \
                .select("id, name") \
                .eq("prospect_id", p_id) \
                .limit(5) \
                .execute()
            
            has_contacts = len(contacts_result.data or []) > 0
            contact_count = len(contacts_result.data or [])
            
            # Check prep
            prep_result = supabase.table("meeting_preps") \
                .select("id, status") \
                .eq("prospect_id", p_id) \
                .eq("status", "completed") \
                .limit(1) \
                .execute()
            
            has_completed_prep = len(prep_result.data or []) > 0
            prep_id = prep_result.data[0]["id"] if prep_result.data else None
            
            # -----------------------------------------------------------------
            # FLOW STEP 1: Research ✓, Contacts ✗ → Suggest adding contacts
            # -----------------------------------------------------------------
            if not has_contacts:
                try:
                    proposal = AutopilotProposalCreate(
                        organization_id=organization_id,
                        user_id=user_id,
                        proposal_type=ProposalType.COMPLETE_FLOW,
                        trigger_type=TriggerType.MANUAL,
                        trigger_entity_id=r_id,
                        trigger_entity_type="research",
                        title=f"Voeg contacten toe aan {company}",
                        description="Research klaar, contacten ontbreken",
                        luna_message=f"Je research over {company} is klaar! Voeg nu contactpersonen toe om je prep te personaliseren.",
                        proposal_reason=f"Je hebt research voor {company} maar nog geen contactpersonen. Met contacten kan ik je prep personaliseren.",
                        suggested_actions=[
                            SuggestedAction(action="add_contacts", params={
                                "prospect_id": p_id,
                                "research_id": r_id,
                            }),
                        ],
                        priority=80,
                        expires_at=datetime.now() + timedelta(days=7),
                        context_data={
                            "prospect_id": p_id,
                            "company_name": company,
                            "research_id": r_id,
                            "flow_step": "add_contacts",
                            "action_route": f"/dashboard/research/{r_id}",
                        },
                    )
                    
                    result = await orchestrator.create_proposal(proposal)
                    if result:
                        created_count += 1
                        proposals_created.append({"type": "add_contacts", "company": company})
                        
                except Exception as e:
                    if "duplicate" not in str(e).lower() and "unique" not in str(e).lower():
                        logger.warning(f"Failed to create add_contacts proposal for {company}: {e}")
                
                continue  # Don't check further steps if contacts missing
            
            # -----------------------------------------------------------------
            # FLOW STEP 2: Research ✓, Contacts ✓, Prep ✗ → Suggest creating prep
            # -----------------------------------------------------------------
            if not has_completed_prep:
                try:
                    proposal = AutopilotProposalCreate(
                        organization_id=organization_id,
                        user_id=user_id,
                        proposal_type=ProposalType.PREP_ONLY,
                        trigger_type=TriggerType.MANUAL,
                        trigger_entity_id=p_id,
                        trigger_entity_type="prospect",
                        title=f"Maak prep voor {company}",
                        description=f"Research en {contact_count} contacten klaar",
                        luna_message=f"Je hebt research over {company} en {contact_count} contacten toegevoegd. Wil je een prep maken voor het eerste gesprek?",
                        proposal_reason=f"Research en {contact_count} contactpersonen zijn compleet. Een prep helpt je het gesprek effectief te voeren.",
                        suggested_actions=[
                            SuggestedAction(action="prep", params={
                                "prospect_id": p_id,
                                "research_id": r_id,
                                "meeting_type": "discovery",
                            }),
                        ],
                        priority=75,
                        expires_at=datetime.now() + timedelta(days=7),
                        context_data={
                            "prospect_id": p_id,
                            "company_name": company,
                            "research_id": r_id,
                            "contact_count": contact_count,
                            "flow_step": "create_prep",
                        },
                    )
                    
                    result = await orchestrator.create_proposal(proposal)
                    if result:
                        created_count += 1
                        proposals_created.append({"type": "create_prep", "company": company})
                        
                except Exception as e:
                    if "duplicate" not in str(e).lower() and "unique" not in str(e).lower():
                        logger.warning(f"Failed to create prep proposal for {company}: {e}")
                
                continue  # Don't check further steps if prep missing
            
            # -----------------------------------------------------------------
            # FLOW STEP 3: Prep ✓, Meeting Analysis ✗ → Suggest uploading recording
            # -----------------------------------------------------------------
            if prep_id:
                # Check for follow-up (meeting analysis)
                followup_result = supabase.table("followups") \
                    .select("id, status") \
                    .eq("prospect_id", p_id) \
                    .eq("status", "completed") \
                    .limit(1) \
                    .execute()
                
                has_completed_followup = len(followup_result.data or []) > 0
                followup_id = followup_result.data[0]["id"] if followup_result.data else None
                
                if not has_completed_followup:
                    try:
                        proposal = AutopilotProposalCreate(
                            organization_id=organization_id,
                            user_id=user_id,
                            proposal_type=ProposalType.FOLLOWUP_PACK,
                            trigger_type=TriggerType.MANUAL,
                            trigger_entity_id=prep_id,
                            trigger_entity_type="prep",
                            title=f"Analyseer meeting met {company}",
                            description="Prep klaar, upload je meeting recording",
                            luna_message=f"Je prep voor {company} is klaar. Na je meeting, upload de recording voor een analyse en follow-up acties.",
                            proposal_reason="Je prep is af. Na het gesprek kan ik de recording analyseren voor samenvatting en actiepunten.",
                            suggested_actions=[
                                SuggestedAction(action="meeting_analysis", params={
                                    "prospect_id": p_id,
                                    "prep_id": prep_id,
                                }),
                            ],
                            priority=70,
                            expires_at=datetime.now() + timedelta(days=14),
                            context_data={
                                "prospect_id": p_id,
                                "company_name": company,
                                "prep_id": prep_id,
                                "flow_step": "meeting_analysis",
                                "action_route": "/dashboard/followup",
                            },
                        )
                        
                        result = await orchestrator.create_proposal(proposal)
                        if result:
                            created_count += 1
                            proposals_created.append({"type": "meeting_analysis", "company": company})
                            
                    except Exception as e:
                        if "duplicate" not in str(e).lower() and "unique" not in str(e).lower():
                            logger.warning(f"Failed to create meeting_analysis proposal for {company}: {e}")
                    
                    continue
                
                # -----------------------------------------------------------------
                # FLOW STEP 4: Meeting Analysis ✓, Actions ✗ → Suggest generating actions
                # -----------------------------------------------------------------
                if followup_id:
                    # Check for actions
                    actions_result = supabase.table("followup_actions") \
                        .select("id") \
                        .eq("followup_id", followup_id) \
                        .limit(1) \
                        .execute()
                    
                    has_actions = len(actions_result.data or []) > 0
                    
                    if not has_actions:
                        try:
                            proposal = AutopilotProposalCreate(
                                organization_id=organization_id,
                                user_id=user_id,
                                proposal_type=ProposalType.COMPLETE_FLOW,
                                trigger_type=TriggerType.MANUAL,
                                trigger_entity_id=followup_id,
                                trigger_entity_type="followup",
                                title=f"Genereer acties voor {company}",
                                description="Meeting analyse klaar, acties ontbreken",
                                luna_message=f"Je meeting analyse voor {company} is klaar. Wil je een customer report of andere acties genereren?",
                                proposal_reason="De meeting is geanalyseerd. Genereer nu follow-up acties zoals een rapport of email.",
                                suggested_actions=[
                                    SuggestedAction(action="generate_actions", params={
                                        "followup_id": followup_id,
                                        "prospect_id": p_id,
                                    }),
                                ],
                                priority=65,
                                expires_at=datetime.now() + timedelta(days=7),
                                context_data={
                                    "prospect_id": p_id,
                                    "company_name": company,
                                    "followup_id": followup_id,
                                    "flow_step": "generate_actions",
                                    "action_route": f"/dashboard/followup/{followup_id}",
                                },
                            )
                            
                            result = await orchestrator.create_proposal(proposal)
                            if result:
                                created_count += 1
                                proposals_created.append({"type": "generate_actions", "company": company})
                                
                        except Exception as e:
                            if "duplicate" not in str(e).lower() and "unique" not in str(e).lower():
                                logger.warning(f"Failed to create generate_actions proposal for {company}: {e}")
        
        return {
            "success": True,
            "checked": checked_count,
            "created": created_count,
            "proposals": proposals_created
        }
        
    except Exception as e:
        logger.error(f"Error in manual detection: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# =============================================================================
# AI EMAIL GENERATION
# =============================================================================

from pydantic import BaseModel
from typing import Optional

class GenerateMeetingEmailRequest(BaseModel):
    prospect_id: str
    contact_id: Optional[str] = None
    prep_id: Optional[str] = None
    user_name: Optional[str] = None


class GenerateMeetingEmailResponse(BaseModel):
    subject: str
    body: str
    contact_name: Optional[str] = None
    company_name: Optional[str] = None


@router.post("/generate-meeting-email", response_model=GenerateMeetingEmailResponse)
async def generate_meeting_email(
    request: GenerateMeetingEmailRequest,
    current_user: dict = Depends(get_current_user)
):
    """
    Generate an AI-powered meeting request email based on prospect context.
    
    Uses research, prep, and contact data to create a personalized email.
    """
    user_id = current_user["sub"]
    supabase = get_supabase_service()
    
    try:
        # Get user's output language
        output_language = "en"
        try:
            settings_result = supabase.table("user_settings") \
                .select("output_language") \
                .eq("user_id", user_id) \
                .limit(1) \
                .execute()
            if settings_result.data:
                output_language = settings_result.data[0].get("output_language", "en")
        except Exception:
            pass
        
        # Get prospect info
        prospect_result = supabase.table("prospects") \
            .select("company_name, website, industry") \
            .eq("id", request.prospect_id) \
            .limit(1) \
            .execute()
        
        if not prospect_result.data:
            raise HTTPException(status_code=404, detail="Prospect not found")
        
        prospect = prospect_result.data[0]
        company_name = prospect.get("company_name", "Unknown")
        
        # Get contact info if provided
        contact_name = None
        contact_role = None
        if request.contact_id:
            contact_result = supabase.table("prospect_contacts") \
                .select("name, role, profile_brief") \
                .eq("id", request.contact_id) \
                .limit(1) \
                .execute()
            
            if contact_result.data:
                contact = contact_result.data[0]
                contact_name = contact.get("name")
                contact_role = contact.get("role")
        
        # Get prep info if provided
        prep_summary = None
        key_topics = None
        if request.prep_id:
            prep_result = supabase.table("meeting_preps") \
                .select("executive_summary, key_topics, objectives") \
                .eq("id", request.prep_id) \
                .limit(1) \
                .execute()
            
            if prep_result.data:
                prep = prep_result.data[0]
                prep_summary = prep.get("executive_summary")
                key_topics = prep.get("key_topics", [])
        
        # Get user name from sales_profiles if not provided
        user_name = request.user_name
        if not user_name:
            profile_result = supabase.table("sales_profiles") \
                .select("full_name") \
                .eq("user_id", user_id) \
                .limit(1) \
                .execute()
            
            if profile_result.data:
                user_name = profile_result.data[0].get("full_name", "").split()[0]
        
        # Try to use Gemini for email generation
        try:
            from google import genai
            import os
            
            gemini_key = os.getenv("GOOGLE_AI_API_KEY") or os.getenv("GEMINI_API_KEY")
            if gemini_key:
                client = genai.Client(api_key=gemini_key)
                
                # Build context for email
                context_parts = [
                    f"Company: {company_name}",
                    f"Industry: {prospect.get('industry', 'Unknown')}",
                ]
                
                if contact_name:
                    context_parts.append(f"Contact: {contact_name}, {contact_role or 'Unknown role'}")
                
                if prep_summary:
                    context_parts.append(f"Key Context: {prep_summary[:500]}")
                
                if key_topics and isinstance(key_topics, list):
                    context_parts.append(f"Topics to discuss: {', '.join(key_topics[:3])}")
                
                context = "\n".join(context_parts)
                
                lang_instruction = "in Dutch" if output_language == "nl" else "in English"
                
                prompt = f"""Generate a professional meeting request email {lang_instruction}.

Context:
{context}

Requirements:
- Keep it concise (3-4 short paragraphs max)
- Be professional but warm
- Show genuine interest in their business
- Reference specific context from the research if available
- Include a clear call to action to schedule a meeting
- Do NOT use overly salesy language
- Sign off with the sender's first name only

Sender: {user_name or 'the sales rep'}

Provide the response in this exact format:
SUBJECT: [email subject line]
BODY:
[email body text]"""
                
                response = client.models.generate_content(
                    model="gemini-2.0-flash",
                    contents=prompt
                )
                
                # Parse response
                response_text = response.text
                
                # Extract subject
                subject_match = response_text.find("SUBJECT:")
                body_match = response_text.find("BODY:")
                
                if subject_match >= 0 and body_match >= 0:
                    subject = response_text[subject_match + 8:body_match].strip()
                    body = response_text[body_match + 5:].strip()
                else:
                    # Fallback parsing
                    lines = response_text.strip().split("\n")
                    subject = lines[0].replace("SUBJECT:", "").strip() if lines else "Meeting Request"
                    body = "\n".join(lines[1:]).replace("BODY:", "").strip()
                
                return GenerateMeetingEmailResponse(
                    subject=subject,
                    body=body,
                    contact_name=contact_name,
                    company_name=company_name
                )
        
        except Exception as ai_error:
            logger.warning(f"AI email generation failed, using template: {ai_error}")
        
        # Fallback to template-based email
        if output_language == "nl":
            subject = f"Kennismaking - {company_name}"
            
            if contact_name:
                greeting = f"Beste {contact_name.split()[0]},"
            else:
                greeting = "Beste,"
            
            body = f"""{greeting}

Ik ben bezig met research naar {company_name} en zie interessante mogelijkheden voor samenwerking.

{'Specifiek gezien jullie werk op het gebied van ' + ', '.join(key_topics[:2]) + ', denk ik dat er waardevolle punten zijn om te bespreken.' if key_topics and len(key_topics) >= 2 else 'Ik denk dat er waardevolle punten zijn om te bespreken.'}

Zou je komende week tijd hebben voor een kort gesprek van 30 minuten? Ik kijk ernaar uit om te horen hoe het gaat en waar ik kan helpen.

Met vriendelijke groet,
{user_name or 'DealMotion gebruiker'}"""
        else:
            subject = f"Introduction - {company_name}"
            
            if contact_name:
                greeting = f"Hi {contact_name.split()[0]},"
            else:
                greeting = "Hi,"
            
            body = f"""{greeting}

I've been researching {company_name} and see some interesting opportunities for collaboration.

{'Specifically regarding your work in ' + ', '.join(key_topics[:2]) + ', I believe there are valuable points to discuss.' if key_topics and len(key_topics) >= 2 else 'I believe there are valuable points to discuss.'}

Would you have time for a brief 30-minute call next week? I look forward to hearing how things are going and where I can help.

Best regards,
{user_name or 'DealMotion user'}"""
        
        return GenerateMeetingEmailResponse(
            subject=subject,
            body=body,
            contact_name=contact_name,
            company_name=company_name
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error generating meeting email: {e}")
        raise HTTPException(status_code=500, detail=str(e))
