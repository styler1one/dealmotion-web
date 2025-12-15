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
                
                # Find silent prospects
                prospects_result = supabase.table("prospects") \
                    .select("id, company_name, last_activity_at") \
                    .eq("organization_id", organization_id) \
                    .lt("last_activity_at", cutoff.isoformat()) \
                    .in_("status", ["qualified", "meeting_scheduled"]) \
                    .limit(5) \
                    .execute()
                
                for prospect in (prospects_result.data or []):
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
