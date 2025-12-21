"""
Autopilot Detection Inngest Functions.
SPEC-045 / TASK-048

Functions for detecting opportunities and creating proposals:
- detect_calendar_opportunities_fn: After calendar sync
- detect_meeting_ended_fn: Cron every 15 min
- detect_silent_prospects_fn: Daily at 9 AM
- detect_incomplete_flow_fn: After research completed
- expire_proposals_fn: Cron every 5 min
"""

import logging
from datetime import datetime, timedelta
import inngest
from inngest import TriggerEvent, TriggerCron

from app.inngest.client import inngest_client
from app.database import get_supabase_service

logger = logging.getLogger(__name__)


# =============================================================================
# CALENDAR OPPORTUNITY DETECTION
# =============================================================================

@inngest_client.create_function(
    fn_id="autopilot-detect-calendar-opportunities",
    trigger=TriggerEvent(event="dealmotion/calendar.sync.completed"),
    retries=1,
)
async def detect_calendar_opportunities_fn(ctx, step):
    """
    Detect new meeting opportunities after calendar sync.
    
    Triggered when:
    - Calendar sync completes (cron or manual)
    - New calendar connection is synced
    """
    from app.services.autopilot_orchestrator import AutopilotOrchestrator
    
    event_data = ctx.event.data
    user_id = event_data.get("user_id")
    organization_id = event_data.get("organization_id")
    
    if not user_id or not organization_id:
        logger.warning("Missing user_id or organization_id in calendar sync event")
        return {"created": 0, "error": "Missing required data"}
    
    logger.info(f"Detecting calendar opportunities for user {user_id[:8]}")
    
    # Step 1: Detect opportunities
    async def detect_opportunities():
        orchestrator = AutopilotOrchestrator()
        proposals = await orchestrator.detect_calendar_opportunities(
            user_id=user_id,
            organization_id=organization_id
        )
        return [p.id if p else None for p in proposals]
    
    proposal_ids = await step.run("detect-opportunities", detect_opportunities)
    
    # Filter out None values (duplicates that were skipped)
    created_ids = [id for id in proposal_ids if id]
    
    logger.info(f"Created {len(created_ids)} proposals for user {user_id[:8]}")
    
    return {
        "user_id": user_id,
        "created": len(created_ids),
        "proposal_ids": created_ids
    }


# =============================================================================
# MEETING ENDED DETECTION
# =============================================================================

@inngest_client.create_function(
    fn_id="autopilot-detect-meeting-ended",
    trigger=TriggerCron(cron="*/15 * * * *"),  # Every 15 minutes
    retries=1,
)
async def detect_meeting_ended_fn(ctx, step):
    """
    Detect meetings that have ended and create follow-up proposals.
    
    Checks for:
    - Meetings ended in the last 15-60 minutes
    - With transcript available (from AI Notetaker or upload)
    - Without existing follow-up
    """
    from app.services.autopilot_orchestrator import AutopilotOrchestrator
    from app.models.autopilot import (
        ProposalType, TriggerType, AutopilotProposalCreate,
        SuggestedAction, LUNA_TEMPLATES
    )
    
    supabase = get_supabase_service()
    
    logger.info("Detecting ended meetings for follow-up proposals")
    
    # Step 1: Find meetings ended 15-60 min ago
    async def find_ended_meetings():
        now = datetime.now()
        window_start = now - timedelta(minutes=60)
        window_end = now - timedelta(minutes=15)
        
        result = supabase.table("calendar_meetings") \
            .select("*, prospects(company_name)") \
            .neq("status", "cancelled") \
            .gte("end_time", window_start.isoformat()) \
            .lte("end_time", window_end.isoformat()) \
            .is_("followup_id", None) \
            .execute()
        
        return result.data or []
    
    ended_meetings = await step.run("find-ended-meetings", find_ended_meetings)
    
    if not ended_meetings:
        logger.info("No ended meetings found for follow-up")
        return {"checked": 0, "created": 0}
    
    logger.info(f"Found {len(ended_meetings)} ended meetings")
    
    # Step 2: Create proposals for each
    async def create_followup_proposals():
        orchestrator = AutopilotOrchestrator()
        created = 0
        
        for meeting in ended_meetings:
            try:
                meeting_id = meeting["id"]
                
                # Get company name
                company = "Onbekend"
                if meeting.get("prospects") and meeting["prospects"].get("company_name"):
                    company = meeting["prospects"]["company_name"]
                elif meeting.get("title"):
                    company = meeting["title"]
                
                # Check if user has autopilot enabled
                settings = await orchestrator.get_settings(meeting["user_id"])
                if not settings.enabled or not settings.auto_followup_after_meeting:
                    continue
                
                # Check if there's already a transcript (from Fireflies or AI notetaker)
                transcript_exists = False
                
                # Check Fireflies recordings
                fireflies_result = supabase.table("fireflies_recordings") \
                    .select("id") \
                    .eq("meeting_id", meeting_id) \
                    .limit(1) \
                    .execute()
                
                if fireflies_result.data and len(fireflies_result.data) > 0:
                    transcript_exists = True
                
                # Check AI notetaker recordings
                if not transcript_exists:
                    notetaker_result = supabase.table("ai_notetaker_recordings") \
                        .select("id") \
                        .eq("meeting_id", meeting_id) \
                        .limit(1) \
                        .execute()
                    
                    if notetaker_result.data and len(notetaker_result.data) > 0:
                        transcript_exists = True
                
                # If transcript exists, skip - the summarize will be triggered by that flow
                if transcript_exists:
                    logger.info(f"Skipping meeting {meeting_id} - transcript already exists")
                    continue
                
                proposal = AutopilotProposalCreate(
                    organization_id=meeting["organization_id"],
                    user_id=meeting["user_id"],
                    proposal_type=ProposalType.FOLLOWUP_PACK,
                    trigger_type=TriggerType.MEETING_ENDED,
                    trigger_entity_id=meeting["id"],
                    trigger_entity_type="calendar_meeting",
                    title=f"Follow-up voor {company}",
                    description="Meeting afgelopen",
                    luna_message=LUNA_TEMPLATES["followup_pack"].format(company=company),
                    proposal_reason=f"Je meeting met {company} is zojuist afgelopen. Ik kan een samenvatting en follow-up email maken.",
                    suggested_actions=[
                        SuggestedAction(action="followup_summarize", params={
                            "meeting_id": meeting["id"],
                            "prospect_id": meeting.get("prospect_id"),
                        }),
                        SuggestedAction(action="followup_email", params={
                            "meeting_id": meeting["id"],
                        }),
                    ],
                    priority=70,
                    expires_at=datetime.now() + timedelta(hours=72),
                    context_data={
                        "meeting_id": meeting["id"],
                        "company_name": company,
                        "prospect_id": meeting.get("prospect_id"),
                        "flow_step": "meeting_analysis",
                    },
                )
                
                result = await orchestrator.create_proposal(proposal)
                if result:
                    created += 1
                    
            except Exception as e:
                logger.error(f"Error creating follow-up proposal for meeting {meeting['id']}: {e}")
        
        return created
    
    created_count = await step.run("create-followup-proposals", create_followup_proposals)
    
    logger.info(f"Created {created_count} follow-up proposals")
    
    return {
        "checked": len(ended_meetings),
        "created": created_count
    }


# =============================================================================
# SILENT PROSPECT DETECTION
# =============================================================================

@inngest_client.create_function(
    fn_id="autopilot-detect-silent-prospects",
    trigger=TriggerCron(cron="0 9 * * *"),  # Daily at 9 AM
    retries=1,
)
async def detect_silent_prospects_fn(ctx, step):
    """
    Detect prospects that need reactivation.
    
    Checks for:
    - Prospects with activity but silent > 14 days
    - Had positive outcome in last meeting
    - No scheduled meeting
    """
    from app.services.autopilot_orchestrator import AutopilotOrchestrator
    from app.models.autopilot import (
        ProposalType, TriggerType, AutopilotProposalCreate,
        SuggestedAction, LUNA_TEMPLATES
    )
    
    supabase = get_supabase_service()
    
    logger.info("Detecting silent prospects for reactivation")
    
    # Step 1: Get all users with autopilot enabled
    async def get_enabled_users():
        result = supabase.table("autopilot_settings") \
            .select("user_id") \
            .eq("enabled", True) \
            .execute()
        return [row["user_id"] for row in (result.data or [])]
    
    enabled_users = await step.run("get-enabled-users", get_enabled_users)
    
    if not enabled_users:
        return {"users_checked": 0, "created": 0}
    
    # Step 2: For each user, find silent prospects
    async def find_and_create_proposals():
        orchestrator = AutopilotOrchestrator()
        total_created = 0
        
        cutoff_date = datetime.now() - timedelta(days=14)
        
        for user_id in enabled_users:
            try:
                settings = await orchestrator.get_settings(user_id)
                days_threshold = settings.reactivation_days_threshold
                cutoff = datetime.now() - timedelta(days=days_threshold)
                
                # Get user's organization
                org_result = supabase.table("organization_members") \
                    .select("organization_id") \
                    .eq("user_id", user_id) \
                    .execute()
                
                if not org_result.data:
                    continue
                
                organization_id = org_result.data[0]["organization_id"]
                
                # Find silent prospects (exclude lost/rejected deals)
                prospects_result = supabase.table("prospects") \
                    .select("id, company_name, last_activity_at, status") \
                    .eq("organization_id", organization_id) \
                    .lt("last_activity_at", cutoff.isoformat()) \
                    .in_("status", ["qualified", "meeting_scheduled", "proposal_sent"]) \
                    .not_.in_("status", ["lost", "rejected", "churned"]) \
                    .limit(5) \
                    .execute()
                
                for prospect in (prospects_result.data or []):
                    # Check if there's an active or positive deal
                    deal_result = supabase.table("deals") \
                        .select("id, outcome, is_active") \
                        .eq("prospect_id", prospect["id"]) \
                        .order("created_at", desc=True) \
                        .limit(1) \
                        .execute()
                    
                    # Skip if there's a lost deal
                    if deal_result.data:
                        deal = deal_result.data[0]
                        if deal.get("outcome") in ["lost", "rejected", "no_decision"]:
                            continue  # Don't suggest reactivation for lost deals
                    
                    days_silent = (datetime.now() - datetime.fromisoformat(
                        prospect["last_activity_at"].replace("Z", "+00:00")
                    ).replace(tzinfo=None)).days
                    
                    proposal = AutopilotProposalCreate(
                        organization_id=organization_id,
                        user_id=user_id,
                        proposal_type=ProposalType.REACTIVATION,
                        trigger_type=TriggerType.PROSPECT_SILENT,
                        trigger_entity_id=prospect["id"],
                        trigger_entity_type="prospect",
                        title=f"{prospect['company_name']} is stil",
                        description=f"Laatste contact: {days_silent} dagen geleden",
                        luna_message=LUNA_TEMPLATES["reactivation"].format(
                            company=prospect["company_name"],
                            days=days_silent
                        ),
                        proposal_reason=f"Je hebt al {days_silent} dagen geen contact gehad met {prospect['company_name']}. Tijd om weer eens te checken?",
                        suggested_actions=[
                            SuggestedAction(action="prep", params={
                                "prospect_id": prospect["id"],
                                "type": "reactivation",
                            }),
                        ],
                        priority=50,
                        expires_at=datetime.now() + timedelta(days=7),
                        context_data={
                            "prospect_id": prospect["id"],
                            "company_name": prospect["company_name"],
                            "days_silent": days_silent,
                        },
                    )
                    
                    result = await orchestrator.create_proposal(proposal)
                    if result:
                        total_created += 1
                        
            except Exception as e:
                logger.error(f"Error processing user {user_id}: {e}")
        
        return total_created
    
    created_count = await step.run("create-reactivation-proposals", find_and_create_proposals)
    
    logger.info(f"Created {created_count} reactivation proposals")
    
    return {
        "users_checked": len(enabled_users),
        "created": created_count
    }


# =============================================================================
# INCOMPLETE FLOW DETECTION (Research done, no prep)
# =============================================================================

@inngest_client.create_function(
    fn_id="autopilot-detect-incomplete-flow",
    trigger=TriggerEvent(event="dealmotion/research.completed"),
    retries=1,
)
async def detect_incomplete_flow_fn(ctx, step):
    """
    Detect incomplete flows after research completes.
    
    SPEC-045 Flow 5: Creates proposal when:
    - Research completed
    - Prospect has contacts
    - No prep exists for this prospect
    - No meeting scheduled (optional)
    """
    from app.services.autopilot_orchestrator import AutopilotOrchestrator
    from app.models.autopilot import (
        ProposalType, TriggerType, AutopilotProposalCreate,
        SuggestedAction, LUNA_TEMPLATES
    )
    
    event_data = ctx.event.data
    research_id = event_data.get("research_id")
    prospect_id = event_data.get("prospect_id")
    user_id = event_data.get("user_id")
    organization_id = event_data.get("organization_id")
    company_name = event_data.get("company_name", "Onbekend")
    
    if not research_id or not user_id:
        logger.warning("Missing research_id or user_id in research completed event")
        return {"created": False, "reason": "missing_data"}
    
    logger.info(f"Checking incomplete flow for research {research_id[:8]}")
    
    supabase = get_supabase_service()
    
    # Step 1: Check if user has autopilot enabled
    async def check_settings():
        orchestrator = AutopilotOrchestrator()
        settings = await orchestrator.get_settings(user_id)
        return settings.enabled
    
    enabled = await step.run("check-settings", check_settings)
    
    if not enabled:
        return {"created": False, "reason": "autopilot_disabled"}
    
    # Step 2: Check if prospect has contacts and no prep
    async def check_flow_state():
        # Get prospect info
        if not prospect_id:
            # Research without prospect - skip
            return {"has_contacts": False, "has_prep": True}
        
        # Check for contacts
        contacts_result = supabase.table("prospect_contacts") \
            .select("id") \
            .eq("prospect_id", prospect_id) \
            .limit(1) \
            .execute()
        
        has_contacts = len(contacts_result.data or []) > 0
        
        # Check for existing prep
        prep_result = supabase.table("meeting_preps") \
            .select("id") \
            .eq("prospect_id", prospect_id) \
            .limit(1) \
            .execute()
        
        has_prep = len(prep_result.data or []) > 0
        
        # Check for scheduled meeting
        meeting_result = supabase.table("calendar_meetings") \
            .select("id") \
            .eq("prospect_id", prospect_id) \
            .gte("start_time", datetime.now().isoformat()) \
            .eq("status", "confirmed") \
            .limit(1) \
            .execute()
        
        has_meeting = len(meeting_result.data or []) > 0
        
        return {
            "has_contacts": has_contacts,
            "has_prep": has_prep,
            "has_meeting": has_meeting
        }
    
    flow_state = await step.run("check-flow-state", check_flow_state)
    
    # Step 3: Determine what proposal to create based on flow state
    
    # CASE 1: No contacts yet → Suggest adding contacts
    if not flow_state["has_contacts"]:
        async def create_add_contacts_proposal():
            orchestrator = AutopilotOrchestrator()
            
            proposal = AutopilotProposalCreate(
                organization_id=organization_id,
                user_id=user_id,
                proposal_type=ProposalType.COMPLETE_FLOW,
                trigger_type=TriggerType.FLOW_INCOMPLETE,
                trigger_entity_id=research_id,
                trigger_entity_type="research",
                title=f"Voeg contacten toe aan {company_name}",
                description="Research klaar, contacten ontbreken",
                luna_message=f"Je research over {company_name} is klaar! Voeg nu contactpersonen toe om je prep te personaliseren.",
                proposal_reason=f"Research voor {company_name} is afgerond, maar er zijn nog geen contactpersonen. Met contacten maak ik betere preps.",
                suggested_actions=[
                    SuggestedAction(action="add_contacts", params={
                        "prospect_id": prospect_id,
                        "research_id": research_id,
                    }),
                ],
                priority=80,
                expires_at=datetime.now() + timedelta(days=7),
                context_data={
                    "research_id": research_id,
                    "prospect_id": prospect_id,
                    "company_name": company_name,
                    "flow_step": "add_contacts",
                    "action_route": f"/dashboard/research/{research_id}",
                },
            )
            
            result = await orchestrator.create_proposal(proposal)
            return result.id if result else None
        
        proposal_id = await step.run("create-add-contacts-proposal", create_add_contacts_proposal)
        
        if proposal_id:
            logger.info(f"Created add_contacts proposal {proposal_id} for {company_name}")
            return {"created": True, "proposal_id": proposal_id, "type": "add_contacts"}
        else:
            return {"created": False, "reason": "duplicate_or_error"}
    
    # CASE 2: Has contacts but already has prep → Nothing to do
    if flow_state["has_prep"]:
        return {"created": False, "reason": "prep_exists"}
    
    # CASE 3: Has contacts but meeting scheduled → Calendar detection handles this
    if flow_state["has_meeting"]:
        return {"created": False, "reason": "meeting_scheduled"}
    
    # CASE 4: Has contacts, no prep, no meeting → Suggest creating prep
    async def get_contact_name():
        if not prospect_id:
            return None
        result = supabase.table("prospect_contacts") \
            .select("name") \
            .eq("prospect_id", prospect_id) \
            .order("created_at", desc=True) \
            .limit(1) \
            .execute()
        if result.data:
            return result.data[0].get("name")
        return None
    
    contact_name = await step.run("get-contact-name", get_contact_name)
    
    async def create_prep_proposal():
        orchestrator = AutopilotOrchestrator()
        
        if contact_name:
            luna_message = f"Je hebt {contact_name} toegevoegd aan {company_name}. Wil je een prep maken voor het eerste gesprek?"
        else:
            luna_message = f"Je research over {company_name} is klaar en je hebt contacten toegevoegd. Wil je een prep maken?"
        
        proposal = AutopilotProposalCreate(
            organization_id=organization_id,
            user_id=user_id,
            proposal_type=ProposalType.PREP_ONLY,
            trigger_type=TriggerType.FLOW_INCOMPLETE,
            trigger_entity_id=research_id,
            trigger_entity_type="research",
            title=f"Maak prep voor {company_name}",
            description="Research + contacten klaar",
            luna_message=luna_message,
            proposal_reason=f"Research en contacten voor {company_name} zijn klaar. Een prep helpt je voorbereiden op het eerste gesprek.",
            suggested_actions=[
                SuggestedAction(action="prep", params={
                    "prospect_id": prospect_id,
                    "research_id": research_id,
                    "meeting_type": "discovery",
                }),
            ],
            priority=75,
            expires_at=datetime.now() + timedelta(days=7),
            context_data={
                "research_id": research_id,
                "prospect_id": prospect_id,
                "company_name": company_name,
                "contact_name": contact_name,
                "flow_step": "create_prep",
            },
        )
        
        result = await orchestrator.create_proposal(proposal)
        return result.id if result else None
    
    proposal_id = await step.run("create-prep-proposal", create_prep_proposal)
    
    if proposal_id:
        logger.info(f"Created prep proposal {proposal_id} for {company_name}")
        return {"created": True, "proposal_id": proposal_id, "type": "create_prep"}
    else:
        return {"created": False, "reason": "duplicate_or_error"}


# =============================================================================
# CONTACT ADDED DETECTION (Suggest prep after contact is added)
# =============================================================================

@inngest_client.create_function(
    fn_id="autopilot-detect-contact-added",
    trigger=TriggerEvent(event="dealmotion/contact.added"),
    retries=1,
)
async def detect_contact_added_fn(ctx, step):
    """
    Detect when a contact is added and suggest creating a prep.
    
    Triggered when:
    - User adds a contact to a prospect
    
    Creates proposal when:
    - Research exists for the prospect
    - No prep exists yet
    - No meeting scheduled
    """
    from app.services.autopilot_orchestrator import AutopilotOrchestrator
    from app.models.autopilot import (
        ProposalType, TriggerType, AutopilotProposalCreate,
        SuggestedAction, LUNA_TEMPLATES
    )
    
    event_data = ctx.event.data
    contact_id = event_data.get("contact_id")
    contact_name = event_data.get("contact_name")
    research_id = event_data.get("research_id")
    user_id = event_data.get("user_id")
    organization_id = event_data.get("organization_id")
    
    if not contact_id or not user_id or not research_id:
        logger.warning("Missing data in contact added event")
        return {"created": False, "reason": "missing_data"}
    
    logger.info(f"Checking prep proposal after contact {contact_name} added")
    
    supabase = get_supabase_service()
    
    # Step 1: Check if user has autopilot enabled
    async def check_settings():
        orchestrator = AutopilotOrchestrator()
        settings = await orchestrator.get_settings(user_id)
        return settings.enabled
    
    enabled = await step.run("check-settings", check_settings)
    
    if not enabled:
        return {"created": False, "reason": "autopilot_disabled"}
    
    # Step 2: Get prospect and company info from research
    async def get_context():
        research = supabase.table("research_briefs") \
            .select("prospect_id, company_name") \
            .eq("id", research_id) \
            .single() \
            .execute()
        
        if not research.data:
            return None
        
        prospect_id = research.data.get("prospect_id")
        company_name = research.data.get("company_name", "Onbekend")
        
        # Check if prep exists
        prep_result = supabase.table("meeting_preps") \
            .select("id") \
            .eq("prospect_id", prospect_id) \
            .limit(1) \
            .execute()
        
        has_prep = len(prep_result.data or []) > 0
        
        # Check for scheduled meeting
        meeting_result = supabase.table("calendar_meetings") \
            .select("id") \
            .eq("prospect_id", prospect_id) \
            .gte("start_time", datetime.now().isoformat()) \
            .eq("status", "confirmed") \
            .limit(1) \
            .execute()
        
        has_meeting = len(meeting_result.data or []) > 0
        
        return {
            "prospect_id": prospect_id,
            "company_name": company_name,
            "has_prep": has_prep,
            "has_meeting": has_meeting
        }
    
    context = await step.run("get-context", get_context)
    
    if not context:
        return {"created": False, "reason": "research_not_found"}
    
    if context["has_prep"]:
        return {"created": False, "reason": "prep_exists"}
    
    if context["has_meeting"]:
        # Meeting scheduled - calendar detection will handle prep
        return {"created": False, "reason": "meeting_scheduled"}
    
    # Step 3: Create "create prep" proposal
    async def create_prep_proposal():
        orchestrator = AutopilotOrchestrator()
        
        luna_message = f"Je hebt {contact_name} toegevoegd aan {context['company_name']}. Wil je een prep maken voor het eerste gesprek?"
        
        proposal = AutopilotProposalCreate(
            organization_id=organization_id,
            user_id=user_id,
            proposal_type=ProposalType.PREP_ONLY,
            trigger_type=TriggerType.FLOW_INCOMPLETE,
            trigger_entity_id=contact_id,
            trigger_entity_type="contact",
            title=f"Maak prep voor {context['company_name']}",
            description=f"Contact {contact_name} toegevoegd",
            luna_message=luna_message,
            proposal_reason=f"{contact_name} is toegevoegd. Met een prep bereid je je optimaal voor op het gesprek.",
            suggested_actions=[
                SuggestedAction(action="prep", params={
                    "prospect_id": context["prospect_id"],
                    "research_id": research_id,
                    "meeting_type": "discovery",
                }),
            ],
            priority=75,
            expires_at=datetime.now() + timedelta(days=7),
            context_data={
                "research_id": research_id,
                "prospect_id": context["prospect_id"],
                "company_name": context["company_name"],
                "contact_name": contact_name,
                "contact_id": contact_id,
                "flow_step": "create_prep",
            },
        )
        
        result = await orchestrator.create_proposal(proposal)
        return result.id if result else None
    
    proposal_id = await step.run("create-prep-proposal", create_prep_proposal)
    
    if proposal_id:
        logger.info(f"Created prep proposal {proposal_id} after contact {contact_name} added")
        return {"created": True, "proposal_id": proposal_id}
    else:
        return {"created": False, "reason": "duplicate_or_error"}


# =============================================================================
# PREP WITHOUT MEETING DETECTION (Remind to plan meeting after 3 days)
# =============================================================================

@inngest_client.create_function(
    fn_id="autopilot-detect-prep-no-meeting",
    trigger=TriggerCron(cron="0 10 * * *"),  # Daily at 10 AM
    retries=1,
)
async def detect_prep_no_meeting_fn(ctx, step):
    """
    Detect preps without scheduled meetings after 3 days.
    
    Checks for:
    - Preps created >3 days ago
    - No meeting scheduled for the prospect
    - No existing proposal for this prep
    """
    from app.services.autopilot_orchestrator import AutopilotOrchestrator
    from app.models.autopilot import (
        ProposalType, TriggerType, AutopilotProposalCreate,
        SuggestedAction
    )
    
    supabase = get_supabase_service()
    
    logger.info("Detecting preps without scheduled meetings")
    
    # Step 1: Find preps without meetings
    async def find_preps_without_meetings():
        three_days_ago = datetime.now() - timedelta(days=3)
        
        # Get preps older than 3 days
        preps_result = supabase.table("meeting_preps") \
            .select("id, prospect_id, organization_id, user_id, created_at, prospects(company_name)") \
            .lt("created_at", three_days_ago.isoformat()) \
            .execute()
        
        if not preps_result.data:
            return []
        
        preps_without_meeting = []
        
        for prep in preps_result.data:
            prospect_id = prep.get("prospect_id")
            if not prospect_id:
                continue
            
            # Check if meeting is scheduled
            meeting_result = supabase.table("calendar_meetings") \
                .select("id") \
                .eq("prospect_id", prospect_id) \
                .gte("start_time", datetime.now().isoformat()) \
                .neq("status", "cancelled") \
                .limit(1) \
                .execute()
            
            if not meeting_result.data:
                # No meeting scheduled - add to list
                preps_without_meeting.append(prep)
        
        return preps_without_meeting
    
    preps = await step.run("find-preps-without-meetings", find_preps_without_meetings)
    
    if not preps:
        logger.info("No preps without meetings found")
        return {"checked": 0, "created": 0}
    
    logger.info(f"Found {len(preps)} preps without scheduled meetings")
    
    # Step 2: Create proposals
    async def create_plan_meeting_proposals():
        orchestrator = AutopilotOrchestrator()
        created = 0
        
        for prep in preps:
            try:
                # Get company name
                company = "Onbekend"
                if prep.get("prospects") and prep["prospects"].get("company_name"):
                    company = prep["prospects"]["company_name"]
                
                # Check if user has autopilot enabled
                settings = await orchestrator.get_settings(prep["user_id"])
                if not settings.enabled:
                    continue
                
                proposal = AutopilotProposalCreate(
                    organization_id=prep["organization_id"],
                    user_id=prep["user_id"],
                    proposal_type=ProposalType.COMPLETE_FLOW,
                    trigger_type=TriggerType.FLOW_INCOMPLETE,
                    trigger_entity_id=prep["id"],
                    trigger_entity_type="meeting_prep",
                    title=f"Plan meeting met {company}",
                    description="Prep klaar, meeting niet gepland",
                    luna_message=f"Je prep voor {company} is al een paar dagen klaar. Tijd om je meeting te plannen!",
                    proposal_reason=f"Je prep is af maar er staat nog geen meeting gepland. Plan een moment om je voorbereiding te benutten.",
                    suggested_actions=[
                        SuggestedAction(action="plan_meeting", params={
                            "prospect_id": prep.get("prospect_id"),
                            "prep_id": prep["id"],
                        }),
                    ],
                    priority=65,
                    expires_at=datetime.now() + timedelta(days=7),
                    context_data={
                        "prep_id": prep["id"],
                        "prospect_id": prep.get("prospect_id"),
                        "company_name": company,
                        "flow_step": "plan_meeting",
                        "action_route": f"/dashboard/preparation/{prep['id']}",
                    },
                )
                
                result = await orchestrator.create_proposal(proposal)
                if result:
                    created += 1
                    
            except Exception as e:
                logger.error(f"Error creating plan meeting proposal for prep {prep['id']}: {e}")
        
        return created
    
    created_count = await step.run("create-plan-meeting-proposals", create_plan_meeting_proposals)
    
    logger.info(f"Created {created_count} plan meeting proposals")
    
    return {
        "checked": len(preps),
        "created": created_count
    }


# =============================================================================
# INCOMPLETE FOLLOW-UP ACTIONS DETECTION (Remind to complete actions)
# =============================================================================

@inngest_client.create_function(
    fn_id="autopilot-detect-incomplete-actions",
    trigger=TriggerCron(cron="0 11 * * *"),  # Daily at 11 AM
    retries=1,
)
async def detect_incomplete_actions_fn(ctx, step):
    """
    Detect follow-up actions not completed after 3 days.
    
    Checks for:
    - Followup actions created >3 days ago
    - Status is 'pending' or 'in_progress'
    - No existing proposal for these actions
    """
    from app.services.autopilot_orchestrator import AutopilotOrchestrator
    from app.models.autopilot import (
        ProposalType, TriggerType, AutopilotProposalCreate,
        SuggestedAction
    )
    
    supabase = get_supabase_service()
    
    logger.info("Detecting incomplete follow-up actions")
    
    # Step 1: Find incomplete actions older than 3 days
    async def find_incomplete_actions():
        three_days_ago = datetime.now() - timedelta(days=3)
        
        # Get followup actions that are incomplete
        # Group by followup_id to avoid multiple proposals for same followup
        result = supabase.table("followup_actions") \
            .select("followup_id, organization_id, user_id, created_at") \
            .in_("status", ["pending", "in_progress"]) \
            .lt("created_at", three_days_ago.isoformat()) \
            .execute()
        
        if not result.data:
            return []
        
        # Group by followup_id and get unique followups
        followup_ids = set()
        unique_followups = []
        
        for action in result.data:
            followup_id = action.get("followup_id")
            if followup_id and followup_id not in followup_ids:
                followup_ids.add(followup_id)
                unique_followups.append(action)
        
        return unique_followups
    
    incomplete_followups = await step.run("find-incomplete-actions", find_incomplete_actions)
    
    if not incomplete_followups:
        logger.info("No incomplete follow-up actions found")
        return {"checked": 0, "created": 0}
    
    logger.info(f"Found {len(incomplete_followups)} followups with incomplete actions")
    
    # Step 2: Get followup details and create proposals
    async def create_complete_actions_proposals():
        orchestrator = AutopilotOrchestrator()
        created = 0
        
        for action in incomplete_followups:
            try:
                followup_id = action.get("followup_id")
                
                # Get followup details with prospect
                followup_result = supabase.table("followup_analyses") \
                    .select("id, prospect_id, prospects(company_name)") \
                    .eq("id", followup_id) \
                    .single() \
                    .execute()
                
                if not followup_result.data:
                    continue
                
                followup = followup_result.data
                
                # Get company name
                company = "Onbekend"
                if followup.get("prospects") and followup["prospects"].get("company_name"):
                    company = followup["prospects"]["company_name"]
                
                # Count pending actions
                actions_result = supabase.table("followup_actions") \
                    .select("id", count="exact") \
                    .eq("followup_id", followup_id) \
                    .in_("status", ["pending", "in_progress"]) \
                    .execute()
                
                pending_count = actions_result.count or 0
                
                # Check if user has autopilot enabled
                settings = await orchestrator.get_settings(action["user_id"])
                if not settings.enabled:
                    continue
                
                proposal = AutopilotProposalCreate(
                    organization_id=action["organization_id"],
                    user_id=action["user_id"],
                    proposal_type=ProposalType.COMPLETE_FLOW,
                    trigger_type=TriggerType.FLOW_INCOMPLETE,
                    trigger_entity_id=followup_id,
                    trigger_entity_type="followup_analysis",
                    title=f"Rond acties af voor {company}",
                    description=f"{pending_count} acties nog open",
                    luna_message=f"Je hebt nog {pending_count} openstaande acties voor {company}. Tijd om ze af te ronden!",
                    proposal_reason=f"Er staan al {pending_count} acties klaar sinds je meeting. Afronden houdt momentum in je deal.",
                    suggested_actions=[
                        SuggestedAction(action="complete_actions", params={
                            "followup_id": followup_id,
                            "prospect_id": followup.get("prospect_id"),
                        }),
                    ],
                    priority=60,
                    expires_at=datetime.now() + timedelta(days=7),
                    context_data={
                        "followup_id": followup_id,
                        "prospect_id": followup.get("prospect_id"),
                        "company_name": company,
                        "pending_count": pending_count,
                        "flow_step": "complete_actions",
                        "action_route": f"/dashboard/followup/{followup_id}",
                    },
                )
                
                result = await orchestrator.create_proposal(proposal)
                if result:
                    created += 1
                    
            except Exception as e:
                logger.error(f"Error creating complete actions proposal for followup {action.get('followup_id')}: {e}")
        
        return created
    
    created_count = await step.run("create-complete-actions-proposals", create_complete_actions_proposals)
    
    logger.info(f"Created {created_count} complete actions proposals")
    
    return {
        "checked": len(incomplete_followups),
        "created": created_count
    }


# =============================================================================
# EXPIRY & UNSNOOZE
# =============================================================================

@inngest_client.create_function(
    fn_id="autopilot-expire-proposals",
    trigger=TriggerCron(cron="*/5 * * * *"),  # Every 5 minutes
    retries=1,
)
async def expire_proposals_fn(ctx, step):
    """
    Expire proposals that have passed their expiry time.
    Also unsnooze proposals whose snooze time has passed.
    """
    from app.services.autopilot_orchestrator import AutopilotOrchestrator
    
    logger.info("Running proposal expiry check")
    
    orchestrator = AutopilotOrchestrator()
    
    # Step 1: Expire proposals
    expired_count = await step.run("expire-proposals", orchestrator.expire_proposals)
    
    # Step 2: Unsnooze proposals
    unsnoozed_count = await step.run("unsnooze-proposals", orchestrator.unsnooze_proposals)
    
    if expired_count > 0 or unsnoozed_count > 0:
        logger.info(f"Expired: {expired_count}, Unsnoozed: {unsnoozed_count}")
    
    return {
        "expired": expired_count,
        "unsnoozed": unsnoozed_count
    }


# =============================================================================
# PROSPECT IMPORTED DETECTION
# =============================================================================

@inngest_client.create_function(
    fn_id="autopilot-detect-prospect-imported",
    trigger=TriggerEvent(event="dealmotion/prospect.imported"),
    retries=1,
)
async def detect_prospect_imported_fn(ctx, step):
    """
    Triggered when a prospect is imported from prospecting.
    Creates a proposal to start research on the new prospect.
    
    Event data:
    - prospect_id: ID of the imported prospect
    - company_name: Company name
    - user_id: User who imported
    - organization_id: Organization ID
    """
    from app.services.autopilot_orchestrator import AutopilotOrchestrator
    from app.models.autopilot import (
        ProposalType, TriggerType, AutopilotProposalCreate,
        SuggestedAction
    )
    
    data = ctx.event.data
    prospect_id = data.get("prospect_id")
    company_name = data.get("company_name", "Unknown")
    user_id = data.get("user_id")
    organization_id = data.get("organization_id")
    
    if not prospect_id or not user_id or not organization_id:
        logger.warning("detect_prospect_imported_fn: Missing required data")
        return {"created": False, "reason": "missing_data"}
    
    logger.info(f"Prospect imported: {company_name} ({prospect_id})")
    
    # Check if autopilot is enabled for this user
    orchestrator = AutopilotOrchestrator()
    settings = await orchestrator.get_settings(user_id)
    
    if not settings.enabled:
        return {"created": False, "reason": "autopilot_disabled"}
    
    # Create proposal to start research
    async def create_research_proposal():
        proposal = AutopilotProposalCreate(
            organization_id=organization_id,
            user_id=user_id,
            proposal_type=ProposalType.RESEARCH_ONLY,
            trigger_type=TriggerType.MANUAL,  # Triggered by user action
            trigger_entity_id=prospect_id,
            trigger_entity_type="prospect",
            title=f"Start research voor {company_name}",
            description="Nieuwe prospect geïmporteerd",
            luna_message=f"Je hebt {company_name} toegevoegd aan je prospects! Wil je dat ik research doe over dit bedrijf?",
            proposal_reason=f"{company_name} is nieuw in je lijst. Met research krijg je inzicht in het bedrijf voordat je contact opneemt.",
            suggested_actions=[
                SuggestedAction(action="research", params={
                    "prospect_id": prospect_id,
                    "company_name": company_name,
                }),
            ],
            priority=85,  # High priority for new prospects
            expires_at=datetime.now() + timedelta(days=7),
            context_data={
                "prospect_id": prospect_id,
                "company_name": company_name,
                "source": "prospecting_import",
                "flow_step": "start_research",
            },
        )
        
        result = await orchestrator.create_proposal(proposal)
        return result.id if result else None
    
    proposal_id = await step.run("create-research-proposal", create_research_proposal)
    
    if proposal_id:
        logger.info(f"Created research proposal {proposal_id} for imported prospect {company_name}")
        return {"created": True, "proposal_id": proposal_id}
    else:
        return {"created": False, "reason": "duplicate_or_error"}
