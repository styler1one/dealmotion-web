"""
DealMotion Autopilot Orchestrator Service
SPEC-045 / TASK-048

Core service for the Autopilot feature:
- Detect opportunities
- Create proposals
- Execute accepted proposals
- Manage settings and outcomes
"""

import logging
from datetime import datetime, timedelta
from typing import Optional, List, Dict, Any, Tuple
from uuid import UUID

from app.database import get_supabase_service
from app.models.autopilot import (
    ProposalType,
    ProposalStatus,
    TriggerType,
    NotificationStyle,
    LunaMode,
    AutopilotProposal,
    AutopilotProposalCreate,
    AutopilotSettings,
    AutopilotSettingsUpdate,
    LunaGreeting,
    UpcomingMeeting,
    AutopilotStats,
    ProposalCounts,
    MeetingOutcome,
    OutcomeRequest,
    UserPrepPreferences,
    SuggestedAction,
    LUNA_TEMPLATES,
)

logger = logging.getLogger(__name__)


class AutopilotOrchestrator:
    """
    Orchestrates the Autopilot feature.
    
    Responsibilities:
    - Detect opportunities from calendar, transcripts, etc.
    - Create proposals for users
    - Handle proposal accept/decline/snooze
    - Execute proposals by triggering pipelines
    - Manage user settings
    - Track outcomes for learning
    """
    
    def __init__(self, supabase=None):
        """Initialize with optional Supabase client."""
        self.supabase = supabase or get_supabase_service()
    
    # =========================================================================
    # PROPOSAL MANAGEMENT
    # =========================================================================
    
    async def get_proposals(
        self,
        user_id: str,
        status: Optional[str] = None,
        limit: int = 20
    ) -> Tuple[List[AutopilotProposal], ProposalCounts]:
        """
        Get proposals for a user with optional status filter.
        
        Returns proposals sorted by priority (highest first).
        Automatically validates and expires outdated proposals.
        """
        try:
            # Build query
            query = self.supabase.table("autopilot_proposals") \
                .select("*") \
                .eq("user_id", user_id) \
                .order("priority", desc=True) \
                .order("created_at", desc=True) \
                .limit(limit)
            
            if status:
                query = query.eq("status", status)
            
            result = query.execute()
            
            # Validate and filter proposals
            valid_proposals = []
            proposals_to_expire = []
            proposals_to_timeout = []
            
            for row in (result.data or []):
                proposal = AutopilotProposal(**row)
                
                # Check for stuck "executing" proposals (> 10 minutes)
                if proposal.status in ["accepted", "executing"]:
                    if proposal.execution_started_at:
                        try:
                            started = datetime.fromisoformat(
                                str(proposal.execution_started_at).replace("Z", "+00:00")
                            ).replace(tzinfo=None)
                            minutes_executing = (datetime.now() - started).total_seconds() / 60
                            if minutes_executing > 10:
                                # Check if action was completed outside autopilot
                                is_valid = await self._validate_proposal_still_valid(proposal)
                                if not is_valid:
                                    # Action was completed, mark as completed
                                    proposals_to_expire.append(proposal.id)
                                else:
                                    # Action not completed, mark as failed (timeout)
                                    proposals_to_timeout.append(proposal.id)
                                continue
                        except Exception as e:
                            logger.warning(f"Error checking execution time: {e}")
                
                # Only validate active proposals
                if proposal.status in ["proposed", "accepted", "executing"]:
                    is_valid = await self._validate_proposal_still_valid(proposal)
                    if is_valid:
                        valid_proposals.append(proposal)
                    else:
                        proposals_to_expire.append(proposal.id)
                else:
                    valid_proposals.append(proposal)
            
            # Auto-expire invalid proposals (sync to ensure counts are correct)
            expired_count = 0
            if proposals_to_expire:
                for proposal_id in proposals_to_expire:
                    try:
                        self.supabase.table("autopilot_proposals").update({
                            "status": "completed",
                            "execution_completed_at": datetime.now().isoformat(),
                            "execution_result": {"auto_completed": True, "reason": "Action completed outside Autopilot"}
                        }).eq("id", proposal_id).execute()
                        logger.info(f"Auto-completed proposal {proposal_id} - action already done")
                        expired_count += 1
                    except Exception as e:
                        logger.warning(f"Failed to auto-complete proposal {proposal_id}: {e}")
            
            # Mark timed-out proposals as failed
            if proposals_to_timeout:
                for proposal_id in proposals_to_timeout:
                    try:
                        self.supabase.table("autopilot_proposals").update({
                            "status": "failed",
                            "execution_completed_at": datetime.now().isoformat(),
                            "execution_error": "Execution timed out after 10 minutes"
                        }).eq("id", proposal_id).execute()
                        logger.info(f"Timed out proposal {proposal_id}")
                    except Exception as e:
                        logger.warning(f"Failed to timeout proposal {proposal_id}: {e}")
            
            # Get fresh counts AFTER expiring (ensures accuracy)
            counts = await self._get_proposal_counts(user_id)
            
            # Log for debugging
            if expired_count > 0:
                logger.info(f"Auto-expired {expired_count} proposals, new counts: proposed={counts.proposed}")
            
            return valid_proposals, counts
            
        except Exception as e:
            logger.error(f"Error getting proposals for user {user_id}: {e}")
            raise
    
    async def _validate_proposal_still_valid(self, proposal: AutopilotProposal) -> bool:
        """
        Check if a proposal is still valid (action not yet completed).
        
        Returns True if the proposal should still be shown to user.
        """
        try:
            context = proposal.context_data or {}
            flow_step = context.get("flow_step")
            prospect_id = context.get("prospect_id")
            research_id = context.get("research_id")
            
            if not flow_step:
                return True  # Unknown flow step, keep it
            
            # Check based on flow_step
            if flow_step == "add_contacts":
                # Check if prospect now has contacts
                if prospect_id:
                    contacts_result = self.supabase.table("prospect_contacts") \
                        .select("id") \
                        .eq("prospect_id", prospect_id) \
                        .limit(1) \
                        .execute()
                    if contacts_result.data and len(contacts_result.data) > 0:
                        return False  # Contacts already added
            
            elif flow_step == "create_prep":
                # Check if prospect now has a prep
                if prospect_id:
                    prep_result = self.supabase.table("meeting_preps") \
                        .select("id") \
                        .eq("prospect_id", prospect_id) \
                        .eq("status", "completed") \
                        .limit(1) \
                        .execute()
                    if prep_result.data and len(prep_result.data) > 0:
                        return False  # Prep already created
            
            elif flow_step == "start_research":
                # Check if prospect now has research
                if prospect_id:
                    research_result = self.supabase.table("research_briefs") \
                        .select("id") \
                        .eq("prospect_id", prospect_id) \
                        .eq("status", "completed") \
                        .limit(1) \
                        .execute()
                    if research_result.data and len(research_result.data) > 0:
                        return False  # Research already done
            
            elif flow_step == "meeting_analysis":
                # Check if there's a followup now
                if prospect_id:
                    followup_result = self.supabase.table("followups") \
                        .select("id") \
                        .eq("prospect_id", prospect_id) \
                        .eq("status", "completed") \
                        .limit(1) \
                        .execute()
                    if followup_result.data and len(followup_result.data) > 0:
                        return False  # Meeting analysis already done
            
            return True  # Proposal is still valid
            
        except Exception as e:
            logger.warning(f"Error validating proposal {proposal.id}: {e}")
            return True  # On error, keep the proposal
    
    async def get_proposal(
        self,
        proposal_id: str,
        user_id: str
    ) -> Optional[AutopilotProposal]:
        """Get a single proposal by ID."""
        try:
            result = self.supabase.table("autopilot_proposals") \
                .select("*") \
                .eq("id", proposal_id) \
                .eq("user_id", user_id) \
                .execute()
            
            if result.data:
                return AutopilotProposal(**result.data[0])
            return None
            
        except Exception as e:
            logger.error(f"Error getting proposal {proposal_id}: {e}")
            raise
    
    async def create_proposal(
        self,
        proposal: AutopilotProposalCreate
    ) -> AutopilotProposal:
        """
        Create a new proposal.
        
        Uses upsert to handle unique constraint on trigger_entity_id.
        """
        try:
            # Prepare data
            data = {
                "organization_id": proposal.organization_id,
                "user_id": proposal.user_id,
                "proposal_type": proposal.proposal_type.value,
                "trigger_type": proposal.trigger_type.value,
                "trigger_entity_id": proposal.trigger_entity_id,
                "trigger_entity_type": proposal.trigger_entity_type,
                "title": proposal.title,
                "description": proposal.description,
                "luna_message": proposal.luna_message,
                "proposal_reason": proposal.proposal_reason,
                "suggested_actions": [a.model_dump() for a in proposal.suggested_actions],
                "priority": proposal.priority,
                "expires_at": proposal.expires_at.isoformat() if proposal.expires_at else None,
                "context_data": proposal.context_data,
                "status": "proposed",
            }
            
            result = self.supabase.table("autopilot_proposals") \
                .insert(data) \
                .execute()
            
            if result.data:
                logger.info(f"Created proposal {result.data[0]['id']} for user {proposal.user_id}")
                return AutopilotProposal(**result.data[0])
            
            raise Exception("Failed to create proposal")
            
        except Exception as e:
            # Check if it's a duplicate (unique constraint)
            if "unique" in str(e).lower() or "duplicate" in str(e).lower():
                logger.info(f"Duplicate proposal skipped for trigger {proposal.trigger_entity_id}")
                return None
            logger.error(f"Error creating proposal: {e}")
            raise
    
    async def accept_proposal(
        self,
        proposal_id: str,
        user_id: str,
        reason: Optional[str] = None
    ) -> AutopilotProposal:
        """Accept a proposal and trigger execution."""
        try:
            result = self.supabase.table("autopilot_proposals") \
                .update({
                    "status": "accepted",
                    "decided_at": datetime.now().isoformat(),
                    "decision_reason": reason,
                }) \
                .eq("id", proposal_id) \
                .eq("user_id", user_id) \
                .eq("status", "proposed") \
                .execute()
            
            if not result.data:
                raise Exception("Proposal not found or already processed")
            
            proposal = AutopilotProposal(**result.data[0])
            logger.info(f"Proposal {proposal_id} accepted by user {user_id}")
            
            # Trigger execution via Inngest event
            await self._send_execution_event(proposal)
            
            return proposal
            
        except Exception as e:
            logger.error(f"Error accepting proposal {proposal_id}: {e}")
            raise
    
    async def complete_proposal_inline(
        self,
        proposal_id: str,
        user_id: str
    ) -> AutopilotProposal:
        """
        Mark a proposal as completed directly (for inline actions).
        
        This skips Inngest execution - use when user completed action
        via inline modal/sheet (e.g., ContactSearchModal, PreparationForm).
        """
        try:
            now = datetime.now().isoformat()
            result = self.supabase.table("autopilot_proposals") \
                .update({
                    "status": "completed",
                    "decided_at": now,
                    "execution_started_at": now,
                    "execution_completed_at": now,
                    "artifacts": [{"type": "inline", "message": "Actie voltooid via inline UI"}],
                }) \
                .eq("id", proposal_id) \
                .eq("user_id", user_id) \
                .in_("status", ["proposed", "accepted", "executing"]) \
                .execute()
            
            if not result.data:
                raise Exception("Proposal not found or already processed")
            
            logger.info(f"Proposal {proposal_id} completed inline by user {user_id}")
            return AutopilotProposal(**result.data[0])
            
        except Exception as e:
            logger.error(f"Error completing proposal inline {proposal_id}: {e}")
            raise
    
    async def decline_proposal(
        self,
        proposal_id: str,
        user_id: str,
        reason: Optional[str] = None
    ) -> AutopilotProposal:
        """Decline a proposal."""
        try:
            result = self.supabase.table("autopilot_proposals") \
                .update({
                    "status": "declined",
                    "decided_at": datetime.now().isoformat(),
                    "decision_reason": reason,
                }) \
                .eq("id", proposal_id) \
                .eq("user_id", user_id) \
                .eq("status", "proposed") \
                .execute()
            
            if not result.data:
                raise Exception("Proposal not found or already processed")
            
            logger.info(f"Proposal {proposal_id} declined by user {user_id}")
            return AutopilotProposal(**result.data[0])
            
        except Exception as e:
            logger.error(f"Error declining proposal {proposal_id}: {e}")
            raise
    
    async def snooze_proposal(
        self,
        proposal_id: str,
        user_id: str,
        until: datetime,
        reason: Optional[str] = None
    ) -> AutopilotProposal:
        """Snooze a proposal until a specific time."""
        try:
            result = self.supabase.table("autopilot_proposals") \
                .update({
                    "status": "snoozed",
                    "snoozed_until": until.isoformat(),
                    "decision_reason": reason,
                }) \
                .eq("id", proposal_id) \
                .eq("user_id", user_id) \
                .eq("status", "proposed") \
                .execute()
            
            if not result.data:
                raise Exception("Proposal not found or already processed")
            
            logger.info(f"Proposal {proposal_id} snoozed until {until}")
            return AutopilotProposal(**result.data[0])
            
        except Exception as e:
            logger.error(f"Error snoozing proposal {proposal_id}: {e}")
            raise
    
    async def retry_proposal(
        self,
        proposal_id: str,
        user_id: str
    ) -> AutopilotProposal:
        """Retry a failed proposal."""
        try:
            result = self.supabase.table("autopilot_proposals") \
                .update({
                    "status": "accepted",
                    "execution_error": None,
                    "execution_started_at": None,
                    "execution_completed_at": None,
                }) \
                .eq("id", proposal_id) \
                .eq("user_id", user_id) \
                .eq("status", "failed") \
                .execute()
            
            if not result.data:
                raise Exception("Proposal not found or not in failed status")
            
            proposal = AutopilotProposal(**result.data[0])
            logger.info(f"Proposal {proposal_id} retry initiated")
            
            # Trigger execution via Inngest event
            await self._send_execution_event(proposal)
            
            return proposal
            
        except Exception as e:
            logger.error(f"Error retrying proposal {proposal_id}: {e}")
            raise
    
    async def update_proposal_status(
        self,
        proposal_id: str,
        status: str,
        execution_result: Optional[Dict] = None,
        error: Optional[str] = None,
        artifacts: Optional[List[Dict]] = None
    ) -> None:
        """Update proposal status (called by execution functions)."""
        try:
            update_data = {"status": status}
            
            if status == "executing":
                update_data["execution_started_at"] = datetime.now().isoformat()
            elif status == "completed":
                update_data["execution_completed_at"] = datetime.now().isoformat()
                if execution_result:
                    update_data["execution_result"] = execution_result
                if artifacts:
                    update_data["artifacts"] = artifacts
            elif status == "failed":
                update_data["execution_completed_at"] = datetime.now().isoformat()
                if error:
                    update_data["execution_error"] = error
            
            self.supabase.table("autopilot_proposals") \
                .update(update_data) \
                .eq("id", proposal_id) \
                .execute()
            
            logger.info(f"Proposal {proposal_id} status updated to {status}")
            
        except Exception as e:
            logger.error(f"Error updating proposal status {proposal_id}: {e}")
            raise
    
    async def _get_proposal_counts(self, user_id: str) -> ProposalCounts:
        """Get counts of proposals by status."""
        try:
            result = self.supabase.table("autopilot_proposals") \
                .select("status") \
                .eq("user_id", user_id) \
                .execute()
            
            counts = ProposalCounts()
            for row in (result.data or []):
                status = row.get("status")
                if status == "proposed":
                    counts.proposed += 1
                elif status == "executing":
                    counts.executing += 1
                elif status == "completed":
                    counts.completed += 1
                elif status == "declined":
                    counts.declined += 1
                elif status == "snoozed":
                    counts.snoozed += 1
                elif status == "expired":
                    counts.expired += 1
                elif status == "failed":
                    counts.failed += 1
            
            return counts
            
        except Exception as e:
            logger.error(f"Error getting proposal counts: {e}")
            return ProposalCounts()
    
    async def _send_execution_event(self, proposal: AutopilotProposal) -> None:
        """Send Inngest event to trigger proposal execution."""
        try:
            from app.inngest.client import inngest_client
            
            await inngest_client.send({
                "name": "autopilot/proposal.accepted",
                "data": {
                    "proposal_id": proposal.id,
                    "user_id": proposal.user_id,
                    "organization_id": proposal.organization_id,
                    "proposal_type": proposal.proposal_type.value if isinstance(proposal.proposal_type, ProposalType) else proposal.proposal_type,
                    "context_data": proposal.context_data,
                }
            })
            
            logger.info(f"Sent execution event for proposal {proposal.id}")
            
        except Exception as e:
            logger.error(f"Error sending execution event: {e}")
            # Don't raise - the proposal is already accepted
    
    # =========================================================================
    # SETTINGS MANAGEMENT
    # =========================================================================
    
    async def get_settings(self, user_id: str) -> AutopilotSettings:
        """Get autopilot settings for a user, creating defaults if needed."""
        try:
            result = self.supabase.table("autopilot_settings") \
                .select("*") \
                .eq("user_id", user_id) \
                .execute()
            
            if result.data:
                return AutopilotSettings(**result.data[0])
            
            # Create default settings
            return await self._create_default_settings(user_id)
            
        except Exception as e:
            logger.error(f"Error getting settings for user {user_id}: {e}")
            raise
    
    async def update_settings(
        self,
        user_id: str,
        updates: AutopilotSettingsUpdate
    ) -> AutopilotSettings:
        """Update autopilot settings."""
        try:
            # Get existing or create
            existing = await self.get_settings(user_id)
            
            # Build update data (only non-None values)
            update_data = {k: v for k, v in updates.model_dump().items() if v is not None}
            
            if not update_data:
                return existing
            
            # Convert enum to value
            if "notification_style" in update_data and isinstance(update_data["notification_style"], NotificationStyle):
                update_data["notification_style"] = update_data["notification_style"].value
            
            update_data["updated_at"] = datetime.now().isoformat()
            
            result = self.supabase.table("autopilot_settings") \
                .update(update_data) \
                .eq("user_id", user_id) \
                .execute()
            
            if result.data:
                return AutopilotSettings(**result.data[0])
            
            raise Exception("Failed to update settings")
            
        except Exception as e:
            logger.error(f"Error updating settings for user {user_id}: {e}")
            raise
    
    async def _create_default_settings(self, user_id: str) -> AutopilotSettings:
        """Create default settings for a new user."""
        try:
            data = {
                "user_id": user_id,
                "enabled": True,
                "auto_research_new_meetings": True,
                "auto_prep_known_prospects": True,
                "auto_followup_after_meeting": True,
                "reactivation_days_threshold": 14,
                "prep_hours_before_meeting": 24,
                "notification_style": "balanced",
                "excluded_meeting_keywords": [],
            }
            
            result = self.supabase.table("autopilot_settings") \
                .insert(data) \
                .execute()
            
            if result.data:
                return AutopilotSettings(**result.data[0])
            
            raise Exception("Failed to create default settings")
            
        except Exception as e:
            logger.error(f"Error creating default settings: {e}")
            raise
    
    # =========================================================================
    # STATS & LUNA GREETING
    # =========================================================================
    
    async def get_stats(self, user_id: str, organization_id: str) -> AutopilotStats:
        """Get stats for the autopilot home page."""
        try:
            # Get proposal counts
            counts = await self._get_proposal_counts(user_id)
            
            # Get completed today
            today_start = datetime.now().replace(hour=0, minute=0, second=0, microsecond=0)
            completed_result = self.supabase.table("autopilot_proposals") \
                .select("id", count="exact") \
                .eq("user_id", user_id) \
                .eq("status", "completed") \
                .gte("execution_completed_at", today_start.isoformat()) \
                .execute()
            completed_today = completed_result.count or 0
            
            # Get urgent (high priority proposed)
            urgent_result = self.supabase.table("autopilot_proposals") \
                .select("id", count="exact") \
                .eq("user_id", user_id) \
                .eq("status", "proposed") \
                .gte("priority", 80) \
                .execute()
            urgent_count = urgent_result.count or 0
            
            # Get upcoming meetings (next 48 hours)
            upcoming_meetings = await self._get_upcoming_meetings(user_id, organization_id)
            
            # Generate Luna greeting
            luna_greeting = await self._get_luna_greeting(
                user_id=user_id,
                pending_count=counts.proposed,
                urgent_count=urgent_count,
                completed_today=completed_today,
                upcoming_meetings=upcoming_meetings
            )
            
            return AutopilotStats(
                pending_count=counts.proposed,
                urgent_count=urgent_count,
                completed_today=completed_today,
                upcoming_meetings=upcoming_meetings,
                luna_greeting=luna_greeting
            )
            
        except Exception as e:
            logger.error(f"Error getting stats for user {user_id}: {e}")
            raise
    
    async def _get_upcoming_meetings(
        self,
        user_id: str,
        organization_id: str
    ) -> List[UpcomingMeeting]:
        """Get upcoming meetings in the next 48 hours."""
        try:
            now = datetime.now()
            end_time = now + timedelta(hours=48)
            
            result = self.supabase.table("calendar_meetings") \
                .select("id, title, start_time, prospect_id, preparation_id, prospects(company_name)") \
                .eq("user_id", user_id) \
                .eq("organization_id", organization_id) \
                .neq("status", "cancelled") \
                .gte("start_time", now.isoformat()) \
                .lte("start_time", end_time.isoformat()) \
                .order("start_time") \
                .limit(5) \
                .execute()
            
            meetings = []
            for row in (result.data or []):
                start_time = datetime.fromisoformat(row["start_time"].replace("Z", "+00:00"))
                hours_until = (start_time.replace(tzinfo=None) - now).total_seconds() / 3600
                
                # Get company name from prospect or parse from title
                company = None
                if row.get("prospects") and row["prospects"].get("company_name"):
                    company = row["prospects"]["company_name"]
                
                meetings.append(UpcomingMeeting(
                    id=row["id"],
                    title=row["title"],
                    company=company,
                    start_time=start_time,
                    starts_in_hours=round(hours_until, 1),
                    has_prep=row.get("preparation_id") is not None,
                    prospect_id=row.get("prospect_id"),
                ))
            
            return meetings
            
        except Exception as e:
            logger.error(f"Error getting upcoming meetings: {e}")
            return []
    
    async def _get_user_first_name(self, user_id: str) -> str:
        """Get the user's first name from their profile."""
        try:
            # Try sales_profiles first (most likely to have a name)
            result = self.supabase.table("sales_profiles") \
                .select("full_name") \
                .eq("user_id", user_id) \
                .limit(1) \
                .execute()
            
            if result.data and result.data[0].get("full_name"):
                full_name = result.data[0]["full_name"]
                return full_name.split()[0]  # First name
            
            # Fallback to users table
            result = self.supabase.table("users") \
                .select("full_name") \
                .eq("id", user_id) \
                .limit(1) \
                .execute()
            
            if result.data and result.data[0].get("full_name"):
                full_name = result.data[0]["full_name"]
                return full_name.split()[0]
            
        except Exception as e:
            logger.debug(f"Could not get user name: {e}")
        
        return ""  # Empty string, so greeting works without name
    
    async def _get_luna_greeting(
        self,
        user_id: str,
        pending_count: int,
        urgent_count: int,
        completed_today: int,
        upcoming_meetings: List[UpcomingMeeting]
    ) -> LunaGreeting:
        """Generate Luna's dynamic greeting based on context."""
        hour = datetime.now().hour
        
        # Get user's first name for personalization
        first_name = await self._get_user_first_name(user_id)
        name_suffix = f", {first_name}" if first_name else ""
        
        # Check for urgent meeting (without prep, starting soon)
        urgent_meeting = next(
            (m for m in upcoming_meetings if m.starts_in_hours < 2 and not m.has_prep),
            None
        )
        
        if urgent_meeting:
            hours_text = "1 uur" if urgent_meeting.starts_in_hours < 1.5 else f"{int(urgent_meeting.starts_in_hours)} uur"
            company = urgent_meeting.company or urgent_meeting.title
            return LunaGreeting(
                mode=LunaMode.URGENCY,
                message=f"Hey{name_suffix}! Je meeting met {company} begint over {hours_text}. Wil je dat ik snel een prep maak?",
                emphasis=company,
                action="Maak prep",
                action_route=f"/dashboard/preparation?meeting={urgent_meeting.id}",
                pending_count=pending_count,
                urgent_count=urgent_count,
            )
        
        # Morning greeting (before 12:00)
        if hour < 12:
            if pending_count > 0:
                return LunaGreeting(
                    mode=LunaMode.MORNING,
                    message=f"Goedemorgen{name_suffix}! Ik heb {pending_count} {'suggestie' if pending_count == 1 else 'suggesties'} voor je klaarliggen.",
                    pending_count=pending_count,
                    urgent_count=urgent_count,
                )
            else:
                # No pending items in morning - suggest proactive action
                next_meeting = next((m for m in upcoming_meetings), None)
                if next_meeting:
                    return LunaGreeting(
                        mode=LunaMode.MORNING,
                        message=f"Goedemorgen{name_suffix}! Je volgende meeting is om {next_meeting.start_time.strftime('%H:%M') if hasattr(next_meeting.start_time, 'strftime') else next_meeting.start_time}. Alles staat klaar.",
                        pending_count=0,
                        urgent_count=0,
                    )
                return LunaGreeting(
                    mode=LunaMode.MORNING,
                    message=f"Goedemorgen{name_suffix}! Je agenda is vrij. Tijd om aan nieuwe prospects te werken?",
                    action="Ontdek prospects",
                    action_route="/dashboard/prospecting",
                    pending_count=0,
                    urgent_count=0,
                )
        
        # Afternoon greeting (12:00 - 18:00)
        if 12 <= hour < 18:
            if pending_count > 0:
                return LunaGreeting(
                    mode=LunaMode.PROPOSAL,
                    message=f"Je hebt {pending_count} {'voorstel' if pending_count == 1 else 'voorstellen'} klaarstaan{name_suffix}.",
                    pending_count=pending_count,
                    urgent_count=urgent_count,
                )
            return LunaGreeting(
                mode=LunaMode.COACH,
                message=f"Goede middag{name_suffix}! Geen openstaande items. Bekijk je prospects of start nieuwe research.",
                pending_count=0,
                urgent_count=0,
            )
        
        # Evening greeting (after 18:00)
        if hour >= 18:
            if pending_count > 0:
                return LunaGreeting(
                    mode=LunaMode.PROPOSAL,
                    message=f"Goedenavond{name_suffix}. Je hebt nog {pending_count} {'item' if pending_count == 1 else 'items'} openstaan, maar dat kan ook morgen.",
                    pending_count=pending_count,
                    urgent_count=urgent_count,
                )
            return LunaGreeting(
                mode=LunaMode.COACH,
                message=f"Goedenavond{name_suffix}! Alles op orde voor morgen.",
                pending_count=0,
                urgent_count=0,
            )
        
        # Celebration mode (3+ completed today)
        if completed_today >= 3:
            return LunaGreeting(
                mode=LunaMode.CELEBRATION,
                message=f"Goed bezig{name_suffix}! Je hebt vandaag al {completed_today} items afgerond. 🎉",
                pending_count=pending_count,
                urgent_count=urgent_count,
            )
        
        # Generic fallback
        if pending_count > 0:
            return LunaGreeting(
                mode=LunaMode.PROPOSAL,
                message=f"Hey{name_suffix}! Ik heb {pending_count} {'suggestie' if pending_count == 1 else 'suggesties'} voor je.",
                pending_count=pending_count,
                urgent_count=urgent_count,
            )
        
        return LunaGreeting(
            mode=LunaMode.COACH,
            message=f"Welkom terug{name_suffix}! Wat wil je vandaag bereiken?",
            pending_count=0,
            urgent_count=0,
        )
    
    # =========================================================================
    # OUTCOMES & LEARNING
    # =========================================================================
    
    async def record_outcome(
        self,
        user_id: str,
        organization_id: str,
        outcome: OutcomeRequest
    ) -> MeetingOutcome:
        """Record a meeting outcome for learning."""
        try:
            data = {
                "user_id": user_id,
                "organization_id": organization_id,
                "outcome_rating": outcome.outcome_rating.value,
                "outcome_source": "user_input",
                "calendar_meeting_id": outcome.calendar_meeting_id,
                "preparation_id": outcome.preparation_id,
                "followup_id": outcome.followup_id,
                "prospect_id": outcome.prospect_id,
            }
            
            result = self.supabase.table("meeting_outcomes") \
                .insert(data) \
                .execute()
            
            if result.data:
                logger.info(f"Recorded outcome for user {user_id}")
                return MeetingOutcome(**result.data[0])
            
            raise Exception("Failed to record outcome")
            
        except Exception as e:
            logger.error(f"Error recording outcome: {e}")
            raise
    
    async def record_prep_viewed(
        self,
        user_id: str,
        organization_id: str,
        preparation_id: str,
        view_duration_seconds: int,
        scroll_depth: float
    ) -> None:
        """Record that a prep was viewed (for learning)."""
        try:
            # Check if outcome exists for this prep
            existing = self.supabase.table("meeting_outcomes") \
                .select("id") \
                .eq("user_id", user_id) \
                .eq("preparation_id", preparation_id) \
                .execute()
            
            if existing.data:
                # Update existing
                self.supabase.table("meeting_outcomes") \
                    .update({
                        "prep_viewed": True,
                        "prep_view_duration_seconds": view_duration_seconds,
                        "prep_scroll_depth": scroll_depth,
                    }) \
                    .eq("id", existing.data[0]["id"]) \
                    .execute()
            else:
                # Create new
                self.supabase.table("meeting_outcomes") \
                    .insert({
                        "user_id": user_id,
                        "organization_id": organization_id,
                        "preparation_id": preparation_id,
                        "prep_viewed": True,
                        "prep_view_duration_seconds": view_duration_seconds,
                        "prep_scroll_depth": scroll_depth,
                    }) \
                    .execute()
            
            logger.info(f"Recorded prep viewed for {preparation_id}")
            
        except Exception as e:
            logger.error(f"Error recording prep viewed: {e}")
            # Don't raise - this is non-critical
    
    async def get_user_preferences(self, user_id: str) -> Optional[UserPrepPreferences]:
        """Get learned preferences for a user."""
        try:
            result = self.supabase.table("user_prep_preferences") \
                .select("*") \
                .eq("user_id", user_id) \
                .execute()
            
            if result.data:
                return UserPrepPreferences(**result.data[0])
            return None
            
        except Exception as e:
            logger.error(f"Error getting user preferences: {e}")
            return None
    
    # =========================================================================
    # OPPORTUNITY DETECTION
    # =========================================================================
    
    async def detect_calendar_opportunities(
        self,
        user_id: str,
        organization_id: str
    ) -> List[AutopilotProposal]:
        """
        Detect opportunities from calendar meetings.
        
        Called after calendar sync to find meetings that need research/prep.
        """
        try:
            # Get user settings
            settings = await self.get_settings(user_id)
            
            if not settings.enabled:
                logger.info(f"Autopilot disabled for user {user_id}")
                return []
            
            # Get upcoming meetings without linked prospect or without prep
            now = datetime.now()
            lookahead = now + timedelta(hours=settings.prep_hours_before_meeting * 2)
            
            result = self.supabase.table("calendar_meetings") \
                .select("*") \
                .eq("user_id", user_id) \
                .eq("organization_id", organization_id) \
                .neq("status", "cancelled") \
                .gte("start_time", now.isoformat()) \
                .lte("start_time", lookahead.isoformat()) \
                .execute()
            
            proposals = []
            for meeting in (result.data or []):
                # Skip if keywords match exclusion list
                if self._should_exclude_meeting(meeting, settings.excluded_meeting_keywords):
                    continue
                
                proposal = await self._create_calendar_proposal(meeting, user_id, organization_id, settings)
                if proposal:
                    proposals.append(proposal)
            
            return proposals
            
        except Exception as e:
            logger.error(f"Error detecting calendar opportunities: {e}")
            return []
    
    def _should_exclude_meeting(self, meeting: dict, excluded_keywords: List[str]) -> bool:
        """Check if meeting should be excluded based on keywords."""
        if not excluded_keywords:
            return False
        
        title = (meeting.get("title") or "").lower()
        for keyword in excluded_keywords:
            if keyword.lower() in title:
                return True
        return False
    
    async def _create_calendar_proposal(
        self,
        meeting: dict,
        user_id: str,
        organization_id: str,
        settings: AutopilotSettings
    ) -> Optional[AutopilotProposal]:
        """Create a proposal for a calendar meeting if appropriate."""
        try:
            meeting_id = meeting["id"]
            prospect_id = meeting.get("prospect_id")
            preparation_id = meeting.get("preparation_id")
            start_time = datetime.fromisoformat(meeting["start_time"].replace("Z", "+00:00"))
            
            # Format time for message
            time_str = start_time.strftime("%d %b om %H:%M")
            company = meeting.get("title", "Onbekend")
            
            # Determine proposal type
            if not prospect_id:
                # New organization - need research + prep
                if not settings.auto_research_new_meetings:
                    return None
                
                proposal = AutopilotProposalCreate(
                    organization_id=organization_id,
                    user_id=user_id,
                    proposal_type=ProposalType.RESEARCH_PREP,
                    trigger_type=TriggerType.CALENDAR_NEW_ORG,
                    trigger_entity_id=meeting_id,
                    trigger_entity_type="calendar_meeting",
                    title=f"Meeting met {company}",
                    description="Nieuw bedrijf gedetecteerd in je agenda",
                    luna_message=LUNA_TEMPLATES["research_prep_new"].format(time=time_str),
                    suggested_actions=[
                        SuggestedAction(action="research", params={"meeting_id": meeting_id}),
                        SuggestedAction(action="prep", params={"meeting_id": meeting_id}),
                    ],
                    priority=self._calculate_priority(ProposalType.RESEARCH_PREP, start_time, {"prospect_status": None}),
                    expires_at=start_time,
                    context_data={
                        "meeting_id": meeting_id,
                        "meeting_title": meeting.get("title"),
                        "meeting_start": start_time.isoformat(),
                    },
                )
                
            elif not preparation_id:
                # Known prospect but no prep
                if not settings.auto_prep_known_prospects:
                    return None
                
                # Get prospect data (name and status)
                prospect_result = self.supabase.table("prospects") \
                    .select("company_name, status") \
                    .eq("id", prospect_id) \
                    .execute()
                
                prospect = prospect_result.data[0] if prospect_result.data else None
                company = prospect.get("company_name", company) if prospect else company
                prospect_status = prospect.get("status") if prospect else None
                
                proposal = AutopilotProposalCreate(
                    organization_id=organization_id,
                    user_id=user_id,
                    proposal_type=ProposalType.PREP_ONLY,
                    trigger_type=TriggerType.CALENDAR_KNOWN_PROSPECT,
                    trigger_entity_id=meeting_id,
                    trigger_entity_type="calendar_meeting",
                    title=f"Prep voor {company}",
                    description="Research bestaat, prep nog niet",
                    luna_message=LUNA_TEMPLATES["prep_only"].format(company=company, time=time_str),
                    suggested_actions=[
                        SuggestedAction(action="prep", params={
                            "meeting_id": meeting_id,
                            "prospect_id": prospect_id,
                        }),
                    ],
                    priority=self._calculate_priority(ProposalType.PREP_ONLY, start_time, {"prospect_status": prospect_status}),
                    expires_at=start_time,
                    context_data={
                        "meeting_id": meeting_id,
                        "prospect_id": prospect_id,
                        "company_name": company,
                        "meeting_start": start_time.isoformat(),
                    },
                )
            else:
                # Already has prep
                return None
            
            return await self.create_proposal(proposal)
            
        except Exception as e:
            logger.error(f"Error creating calendar proposal: {e}")
            return None
    
    def _calculate_priority(
        self, 
        proposal_type: ProposalType, 
        meeting_start: datetime = None,
        context_data: dict = None
    ) -> int:
        """
        Calculate priority for a proposal based on multiple factors.
        
        Factors considered:
        - Proposal type (base priority)
        - Time urgency (upcoming meetings)
        - Deal value (if available)
        - Prospect status (qualified prospects get boost)
        - Days since last activity (urgency for stale items)
        """
        base_priority = {
            ProposalType.RESEARCH_PREP: 80,
            ProposalType.PREP_ONLY: 75,
            ProposalType.FOLLOWUP_PACK: 70,
            ProposalType.RESEARCH_ONLY: 65,
            ProposalType.REACTIVATION: 50,
            ProposalType.COMPLETE_FLOW: 60,
        }
        
        priority = base_priority.get(proposal_type, 50)
        context = context_data or {}
        
        # Time urgency boost (meetings)
        if meeting_start:
            hours_until = (meeting_start.replace(tzinfo=None) - datetime.now()).total_seconds() / 3600
            if hours_until < 2:
                priority += 20  # Urgent!
            elif hours_until < 4:
                priority += 15
            elif hours_until < 24:
                priority += 10
            elif hours_until < 48:
                priority += 5
        
        # Deal value boost
        deal_value = context.get("deal_value")
        if deal_value:
            try:
                value = float(deal_value)
                if value >= 100000:
                    priority += 15  # High value deal
                elif value >= 50000:
                    priority += 10
                elif value >= 10000:
                    priority += 5
            except (ValueError, TypeError):
                pass
        
        # Prospect status boost
        prospect_status = context.get("prospect_status")
        if prospect_status in ["qualified", "proposal_sent"]:
            priority += 5  # Active deals get boost
        elif prospect_status == "meeting_scheduled":
            priority += 10  # Already engaged
        
        # Days since last activity (stale = more urgent)
        days_silent = context.get("days_silent")
        if days_silent:
            try:
                days = int(days_silent)
                if days >= 14:
                    priority += 5  # Getting stale
                if days >= 30:
                    priority += 10  # Very stale
            except (ValueError, TypeError):
                pass
        
        # Flow step importance
        flow_step = context.get("flow_step")
        if flow_step == "plan_meeting":
            priority += 5  # Close to conversion
        elif flow_step == "complete_actions":
            priority += 3  # Follow-up is important
        
        return min(priority, 100)
    
    # =========================================================================
    # EXPIRY MANAGEMENT
    # =========================================================================
    
    async def expire_proposals(self) -> int:
        """
        Expire proposals that have passed their expiry time.
        
        Called by cron job every 5 minutes.
        """
        try:
            now = datetime.now()
            
            result = self.supabase.table("autopilot_proposals") \
                .update({
                    "status": "expired",
                    "expired_reason": "Time expired",
                }) \
                .eq("status", "proposed") \
                .lt("expires_at", now.isoformat()) \
                .execute()
            
            expired_count = len(result.data) if result.data else 0
            
            if expired_count > 0:
                logger.info(f"Expired {expired_count} proposals")
            
            return expired_count
            
        except Exception as e:
            logger.error(f"Error expiring proposals: {e}")
            return 0
    
    async def unsnooze_proposals(self) -> int:
        """
        Unsnooze proposals whose snooze time has passed.
        
        Called by cron job every 5 minutes.
        """
        try:
            now = datetime.now()
            
            result = self.supabase.table("autopilot_proposals") \
                .update({
                    "status": "proposed",
                    "snoozed_until": None,
                }) \
                .eq("status", "snoozed") \
                .lt("snoozed_until", now.isoformat()) \
                .execute()
            
            unsnoozed_count = len(result.data) if result.data else 0
            
            if unsnoozed_count > 0:
                logger.info(f"Unsnoozed {unsnoozed_count} proposals")
            
            return unsnoozed_count
            
        except Exception as e:
            logger.error(f"Error unsnoozing proposals: {e}")
            return 0
