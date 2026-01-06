"""
Luna Unified AI Assistant - Detection Engine
SPEC-046-Luna-Unified-AI-Assistant

Detection engine for creating Luna messages:
- Prospect-first loop (research, outreach, meeting)
- Meeting-driven loop (prep, post-meeting)
- Sequencing rules and dependencies
- Deduplication via dedupe_key
"""

import logging
from datetime import datetime, timedelta
from typing import List, Dict, Any, Optional, Set
from dataclasses import dataclass

from app.database import get_supabase_service
from app.models.luna import (
    MessageType,
    MessageStatus,
    ActionType,
    LunaMessageCreate,
    SEQUENTIAL_TYPES,
    PARALLEL_TYPES,
    DEPENDENCY_MAP,
    MESSAGE_PRIORITIES,
    DEDUPE_KEY_PATTERNS,
    MAX_CONCURRENT_MESSAGES,
)

logger = logging.getLogger(__name__)


@dataclass
class DetectionContext:
    """Context for detection logic."""
    user_id: str
    organization_id: str
    settings: Dict[str, Any]
    existing_dedupe_keys: Set[str]
    pending_message_types: Set[str]
    completed_message_types: Dict[str, Set[str]]  # By entity (meeting_id, etc.)


class LunaDetectionEngine:
    """
    Detection engine for Luna messages.
    
    Responsibilities:
    - Detect opportunities for all canonical message types
    - Respect sequencing rules and dependencies
    - Enforce deduplication via dedupe_key
    - Calculate priority per SPEC-046
    """
    
    def __init__(self, supabase=None):
        """Initialize with optional Supabase client."""
        self.supabase = supabase or get_supabase_service()
    
    # =========================================================================
    # MAIN DETECTION
    # =========================================================================
    
    async def detect_for_user(
        self,
        user_id: str,
        organization_id: str
    ) -> List[LunaMessageCreate]:
        """
        Run all detection rules for a user.
        Returns list of messages to create (respects dedupe, sequencing).
        """
        logger.info(f"Running Luna detection for user {user_id[:8]}")
        
        # Build detection context
        ctx = await self._build_context(user_id, organization_id)
        
        if not ctx.settings.get("enabled", True):
            logger.info(f"Luna disabled for user {user_id[:8]}")
            return []
        
        messages: List[LunaMessageCreate] = []
        
        # Setup checks (highest priority - should be done first)
        messages.extend(await self._detect_setup_requirements(ctx))
        
        # Prospecting Loop (P0)
        messages.extend(await self._detect_prospecting_loop(ctx))
        
        # Meeting Loop (P0)
        messages.extend(await self._detect_meeting_loop(ctx))
        
        # Post-Meeting Loop (P0)
        messages.extend(await self._detect_post_meeting_loop(ctx))
        
        # Apply sequencing rules
        filtered_messages = self._apply_sequencing(messages, ctx)
        
        # Limit to max concurrent
        limited_messages = filtered_messages[:MAX_CONCURRENT_MESSAGES]
        
        logger.info(
            f"Detection complete: {len(messages)} detected, "
            f"{len(filtered_messages)} after sequencing, "
            f"{len(limited_messages)} after limit"
        )
        
        return limited_messages
    
    async def _build_context(
        self,
        user_id: str,
        organization_id: str
    ) -> DetectionContext:
        """Build detection context with existing state."""
        # Get user settings
        settings_result = self.supabase.table("luna_settings") \
            .select("*") \
            .eq("user_id", user_id) \
            .limit(1) \
            .execute()
        
        settings = settings_result.data[0] if settings_result.data else {
            "enabled": True,
            "outreach_cooldown_days": 14,
            "prep_reminder_hours": 24,
            "excluded_meeting_keywords": ["internal", "1:1", "standup", "sync"]
        }
        
        # Get existing dedupe keys for pending/snoozed messages
        existing_result = self.supabase.table("luna_messages") \
            .select("dedupe_key, message_type, meeting_id, status") \
            .eq("user_id", user_id) \
            .in_("status", ["pending", "executing", "snoozed"]) \
            .execute()
        
        existing_dedupe_keys = set()
        pending_types = set()
        
        for row in (existing_result.data or []):
            existing_dedupe_keys.add(row["dedupe_key"])
            pending_types.add(row["message_type"])
        
        # Get completed message types by entity (for dependency checking)
        completed_result = self.supabase.table("luna_messages") \
            .select("message_type, meeting_id") \
            .eq("user_id", user_id) \
            .eq("status", "completed") \
            .gte("acted_at", (datetime.utcnow() - timedelta(days=7)).isoformat()) \
            .execute()
        
        completed_by_entity: Dict[str, Set[str]] = {}
        for row in (completed_result.data or []):
            meeting_id = row.get("meeting_id") or "global"
            if meeting_id not in completed_by_entity:
                completed_by_entity[meeting_id] = set()
            completed_by_entity[meeting_id].add(row["message_type"])
        
        return DetectionContext(
            user_id=user_id,
            organization_id=organization_id,
            settings=settings,
            existing_dedupe_keys=existing_dedupe_keys,
            pending_message_types=pending_types,
            completed_message_types=completed_by_entity
        )
    
    # =========================================================================
    # SETUP REQUIREMENTS
    # =========================================================================
    
    async def _detect_setup_requirements(
        self,
        ctx: DetectionContext
    ) -> List[LunaMessageCreate]:
        """Detect setup requirements (company profile, etc.)."""
        messages = []
        
        # Check for company profile
        messages.extend(await self._detect_missing_company_profile(ctx))
        
        return messages
    
    async def _detect_missing_company_profile(
        self,
        ctx: DetectionContext
    ) -> List[LunaMessageCreate]:
        """Detect if company profile is missing."""
        dedupe_key = f"setup_company_profile_{ctx.organization_id}"
        
        # Skip if already pending
        if dedupe_key in ctx.existing_dedupe_keys:
            return []
        
        # Check if company profile exists
        profile_result = self.supabase.table("company_profiles") \
            .select("id") \
            .eq("organization_id", ctx.organization_id) \
            .limit(1) \
            .execute()
        
        if profile_result.data:
            # Company profile exists, no message needed
            return []
        
        # Company profile missing - create message
        return [LunaMessageCreate(
            user_id=ctx.user_id,
            organization_id=ctx.organization_id,
            message_type=MessageType.PREPARE_OUTREACH,  # Reuse existing type, or we could add a new one
            dedupe_key=dedupe_key,
            title="Stel je Company Profile in",
            description="Je company profile is nog niet ingesteld. Dit helpt Luna om betere, gepersonaliseerde berichten te genereren.",
            luna_message="Je company profile is nog niet ingesteld. Dit helpt Luna om betere, gepersonaliseerde berichten te genereren. Wil je dit nu instellen?",
            action_type=ActionType.NAVIGATE,
            action_route="/settings?tab=company-profile",
            action_data={},
            priority=90,  # High priority for setup
            priority_inputs={"setup_required": True},
            expires_at=None,
            retryable=False
        )]
    
    # =========================================================================
    # PROSPECTING LOOP
    # =========================================================================
    
    async def _detect_prospecting_loop(
        self,
        ctx: DetectionContext
    ) -> List[LunaMessageCreate]:
        """Detect messages for prospecting loop."""
        messages = []
        
        # 1. start_research: New prospects without research
        messages.extend(await self._detect_start_research(ctx))
        
        # 2. review_research: Completed research not viewed
        messages.extend(await self._detect_review_research(ctx))
        
        # 3. prepare_outreach: Research viewed, contact exists, no outreach
        messages.extend(await self._detect_prepare_outreach(ctx))
        
        # 4. first_touch_sent: Outreach marked as sent
        messages.extend(await self._detect_first_touch_sent(ctx))
        
        # 5. suggest_meeting_creation: Interest signaled, no meeting
        messages.extend(await self._detect_suggest_meeting(ctx))
        
        return messages
    
    async def _detect_start_research(
        self,
        ctx: DetectionContext
    ) -> List[LunaMessageCreate]:
        """Detect prospects that need research started."""
        messages = []
        
        # Find prospects without research
        result = self.supabase.table("prospects") \
            .select("id, company_name") \
            .eq("organization_id", ctx.organization_id) \
            .not_.in_("status", ["won", "lost", "inactive"]) \
            .execute()
        
        for prospect in (result.data or []):
            prospect_id = prospect["id"]
            company = prospect["company_name"]
            
            # Check if research exists
            research_check = self.supabase.table("research_briefs") \
                .select("id") \
                .eq("prospect_id", prospect_id) \
                .limit(1) \
                .execute()
            
            if research_check.data:
                continue  # Already has research
            
            dedupe_key = f"start_research:prospect:{prospect_id}"
            if dedupe_key in ctx.existing_dedupe_keys:
                continue
            
            messages.append(LunaMessageCreate(
                user_id=ctx.user_id,
                organization_id=ctx.organization_id,
                dedupe_key=dedupe_key,
                message_type=MessageType.START_RESEARCH.value,
                title=f"Start research voor {company}",
                description=f"Begin met onderzoek naar {company}",
                luna_message=f"Ik zie dat je {company} als prospect hebt toegevoegd. Zal ik research starten om je voor te bereiden?",
                action_type=ActionType.EXECUTE.value,
                action_route=f"/dashboard/research?prospect={prospect_id}",
                action_data={"prospect_id": prospect_id, "company_name": company},
                priority=MESSAGE_PRIORITIES.get(MessageType.START_RESEARCH, 70),
                expires_at=datetime.utcnow() + timedelta(days=7),
                prospect_id=prospect_id
            ))
        
        return messages
    
    async def _detect_review_research(
        self,
        ctx: DetectionContext
    ) -> List[LunaMessageCreate]:
        """Detect completed research that needs review."""
        messages = []
        
        # Find completed research not viewed recently
        result = self.supabase.table("research_briefs") \
            .select("id, company_name, prospect_id, prospects(company_name)") \
            .eq("user_id", ctx.user_id) \
            .eq("status", "completed") \
            .execute()
        
        for research in (result.data or []):
            research_id = research["id"]
            company = research.get("company_name") or (
                research.get("prospects", {}).get("company_name") if research.get("prospects") else "Prospect"
            )
            
            dedupe_key = f"review_research:{research_id}"
            if dedupe_key in ctx.existing_dedupe_keys:
                continue
            
            messages.append(LunaMessageCreate(
                user_id=ctx.user_id,
                organization_id=ctx.organization_id,
                dedupe_key=dedupe_key,
                message_type=MessageType.REVIEW_RESEARCH.value,
                title=f"Research klaar: {company}",
                description="Je research brief is gereed om te bekijken",
                luna_message=f"De research voor {company} is klaar. Bekijk de inzichten en begin met je voorbereiding.",
                action_type=ActionType.NAVIGATE.value,
                action_route=f"/dashboard/research/{research_id}",
                action_data={"research_id": research_id},
                priority=MESSAGE_PRIORITIES.get(MessageType.REVIEW_RESEARCH, 75),
                expires_at=datetime.utcnow() + timedelta(days=14),
                prospect_id=research.get("prospect_id"),
                research_id=research_id
            ))
        
        return messages[:3]  # Limit to 3 review messages
    
    async def _detect_prepare_outreach(
        self,
        ctx: DetectionContext
    ) -> List[LunaMessageCreate]:
        """
        Detect opportunities for outreach.
        Per SPEC-046: research viewed, contact exists, no outreach in cooldown, NO meeting linked.
        """
        messages = []
        cooldown_days = ctx.settings.get("outreach_cooldown_days", 14)
        cooldown_start = datetime.utcnow() - timedelta(days=cooldown_days)
        
        # Find prospects with:
        # - Completed research
        # - At least one contact
        # - No recent outreach for that contact
        # - No linked meeting
        result = self.supabase.table("prospect_contacts") \
            .select("id, prospect_id, name, prospects(company_name, id)") \
            .eq("organization_id", ctx.organization_id) \
            .execute()
        
        for contact in (result.data or []):
            contact_id = contact["id"]
            prospect_id = contact["prospect_id"]
            contact_name = contact["name"]
            company = contact.get("prospects", {}).get("company_name", "Prospect") if contact.get("prospects") else "Prospect"
            
            # Check if prospect has a linked meeting (exclude from outreach)
            meeting_check = self.supabase.table("calendar_meetings") \
                .select("id") \
                .eq("prospect_id", prospect_id) \
                .limit(1) \
                .execute()
            
            if meeting_check.data:
                continue  # Has meeting, skip outreach
            
            # Also check meetings table
            meetings_check = self.supabase.table("meetings") \
                .select("id") \
                .eq("prospect_id", prospect_id) \
                .limit(1) \
                .execute()
            
            if meetings_check.data:
                continue  # Has meeting, skip outreach
            
            # Check if research exists and is completed
            research_check = self.supabase.table("research_briefs") \
                .select("id") \
                .eq("prospect_id", prospect_id) \
                .eq("status", "completed") \
                .limit(1) \
                .execute()
            
            if not research_check.data:
                continue  # No completed research
            
            research_id = research_check.data[0]["id"]
            
            # Check outreach cooldown
            outreach_check = self.supabase.table("outreach_messages") \
                .select("id") \
                .eq("user_id", ctx.user_id) \
                .eq("contact_id", contact_id) \
                .in_("status", ["draft", "sent"]) \
                .gte("created_at", cooldown_start.isoformat()) \
                .limit(1) \
                .execute()
            
            if outreach_check.data:
                continue  # Recent outreach exists
            
            dedupe_key = f"prepare_outreach:{prospect_id}:{contact_id}"
            if dedupe_key in ctx.existing_dedupe_keys:
                continue
            
            messages.append(LunaMessageCreate(
                user_id=ctx.user_id,
                organization_id=ctx.organization_id,
                dedupe_key=dedupe_key,
                message_type=MessageType.PREPARE_OUTREACH.value,
                title=f"Bereik {contact_name} bij {company}",
                description="Bereid je eerste contact voor",
                luna_message=f"Je hebt research over {company}. Wil je een bericht opstellen voor {contact_name}?",
                action_type=ActionType.INLINE.value,
                action_route=None,
                action_data={
                    "sheet": "outreach_options",
                    "prospect_id": prospect_id,
                    "contact_id": contact_id,
                    "research_id": research_id,
                    "channels": ["linkedin_connect", "linkedin_message", "email"]
                },
                priority=MESSAGE_PRIORITIES.get(MessageType.PREPARE_OUTREACH, 65),
                expires_at=datetime.utcnow() + timedelta(days=14),
                prospect_id=prospect_id,
                contact_id=contact_id,
                research_id=research_id
            ))
        
        return messages[:2]  # Limit to 2 outreach messages
    
    async def _detect_first_touch_sent(
        self,
        ctx: DetectionContext
    ) -> List[LunaMessageCreate]:
        """Detect outreach that has been marked as sent."""
        messages = []
        
        # Find sent outreach without a progress message
        result = self.supabase.table("outreach_messages") \
            .select("id, prospect_id, contact_id, channel, prospects(company_name), prospect_contacts(name)") \
            .eq("user_id", ctx.user_id) \
            .eq("status", "sent") \
            .gte("sent_at", (datetime.utcnow() - timedelta(days=7)).isoformat()) \
            .execute()
        
        for outreach in (result.data or []):
            outreach_id = outreach["id"]
            prospect_id = outreach["prospect_id"]
            company = outreach.get("prospects", {}).get("company_name", "Prospect") if outreach.get("prospects") else "Prospect"
            contact_name = outreach.get("prospect_contacts", {}).get("name", "Contact") if outreach.get("prospect_contacts") else "Contact"
            channel = outreach.get("channel", "message")
            
            dedupe_key = f"first_touch_sent:{prospect_id}:{outreach_id}"
            if dedupe_key in ctx.existing_dedupe_keys:
                continue
            
            channel_label = {
                "linkedin_connect": "LinkedIn connect",
                "linkedin_message": "LinkedIn bericht",
                "email": "email",
                "whatsapp": "WhatsApp"
            }.get(channel, channel)
            
            messages.append(LunaMessageCreate(
                user_id=ctx.user_id,
                organization_id=ctx.organization_id,
                dedupe_key=dedupe_key,
                message_type=MessageType.FIRST_TOUCH_SENT.value,
                title=f"Bericht verstuurd naar {contact_name}",
                description=f"Je {channel_label} is onderweg",
                luna_message=f"Goed bezig! Je hebt contact gelegd met {contact_name} bij {company}.",
                action_type=ActionType.NAVIGATE.value,
                action_route=f"/dashboard/prospects/{prospect_id}",
                action_data={"outreach_id": outreach_id, "prospect_id": prospect_id},
                priority=MESSAGE_PRIORITIES.get(MessageType.FIRST_TOUCH_SENT, 40),
                expires_at=datetime.utcnow() + timedelta(days=3),
                prospect_id=prospect_id,
                contact_id=outreach.get("contact_id"),
                outreach_id=outreach_id
            ))
        
        return messages
    
    async def _detect_suggest_meeting(
        self,
        ctx: DetectionContext
    ) -> List[LunaMessageCreate]:
        """
        Detect prospects that might be ready for a meeting.
        Triggered when "interest signaled" - currently based on status or outreach response.
        NOTE: This is gated behind checking if existing signal exists in codebase.
        """
        messages = []
        
        # Look for prospects with status 'qualified' but no meeting
        result = self.supabase.table("prospects") \
            .select("id, company_name") \
            .eq("organization_id", ctx.organization_id) \
            .eq("status", "qualified") \
            .execute()
        
        for prospect in (result.data or []):
            prospect_id = prospect["id"]
            company = prospect["company_name"]
            
            # Check if meeting exists
            meeting_check = self.supabase.table("calendar_meetings") \
                .select("id") \
                .eq("prospect_id", prospect_id) \
                .limit(1) \
                .execute()
            
            if meeting_check.data:
                continue
            
            # Also check meetings table
            meetings_check = self.supabase.table("meetings") \
                .select("id") \
                .eq("prospect_id", prospect_id) \
                .limit(1) \
                .execute()
            
            if meetings_check.data:
                continue
            
            dedupe_key = f"suggest_meeting_creation:{prospect_id}"
            if dedupe_key in ctx.existing_dedupe_keys:
                continue
            
            messages.append(LunaMessageCreate(
                user_id=ctx.user_id,
                organization_id=ctx.organization_id,
                dedupe_key=dedupe_key,
                message_type=MessageType.SUGGEST_MEETING_CREATION.value,
                title=f"Plan meeting met {company}",
                description="Deze prospect lijkt klaar voor een gesprek",
                luna_message=f"{company} is gekwalificeerd. Wil je een meeting inplannen?",
                action_type=ActionType.INLINE.value,
                action_route=None,
                action_data={
                    "sheet": "schedule_meeting",
                    "prospect_id": prospect_id
                },
                priority=MESSAGE_PRIORITIES.get(MessageType.SUGGEST_MEETING_CREATION, 60),
                expires_at=datetime.utcnow() + timedelta(days=7),
                prospect_id=prospect_id
            ))
        
        return messages[:2]
    
    # =========================================================================
    # MEETING LOOP
    # =========================================================================
    
    async def _detect_meeting_loop(
        self,
        ctx: DetectionContext
    ) -> List[LunaMessageCreate]:
        """Detect messages for meeting loop."""
        messages = []
        
        # create_prep: Upcoming meetings without prep
        messages.extend(await self._detect_create_prep(ctx))
        
        # prep_ready: Completed preps not viewed
        messages.extend(await self._detect_prep_ready(ctx))
        
        return messages
    
    async def _detect_create_prep(
        self,
        ctx: DetectionContext
    ) -> List[LunaMessageCreate]:
        """Detect meetings that need prep created."""
        messages = []
        prep_hours = ctx.settings.get("prep_reminder_hours", 24)
        excluded_keywords = ctx.settings.get("excluded_meeting_keywords", [])
        
        now = datetime.utcnow()
        window_end = now + timedelta(hours=prep_hours)
        
        # Find upcoming meetings without prep
        result = self.supabase.table("calendar_meetings") \
            .select("id, title, start_time, prospect_id, prospects(company_name)") \
            .eq("user_id", ctx.user_id) \
            .gte("start_time", now.isoformat()) \
            .lte("start_time", window_end.isoformat()) \
            .neq("status", "cancelled") \
            .execute()
        
        for meeting in (result.data or []):
            meeting_id = meeting["id"]
            title = meeting.get("title", "")
            prospect_id = meeting.get("prospect_id")
            company = meeting.get("prospects", {}).get("company_name") if meeting.get("prospects") else title
            
            # Skip excluded meetings
            if any(kw.lower() in title.lower() for kw in excluded_keywords):
                continue
            
            # Check if prep exists
            prep_check = self.supabase.table("meeting_preps") \
                .select("id") \
                .eq("meeting_id", meeting_id) \
                .limit(1) \
                .execute()
            
            if prep_check.data:
                continue  # Already has prep
            
            # Calculate window bucket (for dedupe)
            start_time = datetime.fromisoformat(meeting["start_time"].replace("Z", "+00:00")).replace(tzinfo=None)
            hours_until = (start_time - now).total_seconds() / 3600
            window_bucket = "24h" if hours_until >= 12 else "4h" if hours_until >= 2 else "1h"
            
            # Adjust priority based on urgency
            base_priority = MESSAGE_PRIORITIES.get(MessageType.CREATE_PREP, 75)
            if window_bucket == "1h":
                priority = min(base_priority + 15, 95)  # Very urgent
            elif window_bucket == "4h":
                priority = base_priority + 5
            else:
                priority = base_priority
            
            dedupe_key = f"create_prep:{meeting_id}:{window_bucket}"
            if dedupe_key in ctx.existing_dedupe_keys:
                continue
            
            messages.append(LunaMessageCreate(
                user_id=ctx.user_id,
                organization_id=ctx.organization_id,
                dedupe_key=dedupe_key,
                message_type=MessageType.CREATE_PREP.value,
                title=f"Bereid je voor op {company}",
                description=f"Meeting over {int(hours_until)} uur",
                luna_message=f"Je meeting met {company} begint over {int(hours_until)} uur. Zal ik een voorbereiding maken?",
                action_type=ActionType.EXECUTE.value,
                action_route=f"/dashboard/preparation?meeting={meeting_id}",
                action_data={"meeting_id": meeting_id, "prospect_id": prospect_id},
                priority=priority,
                expires_at=start_time,  # Expire when meeting starts
                prospect_id=prospect_id,
                meeting_id=meeting_id
            ))
        
        return messages
    
    async def _detect_prep_ready(
        self,
        ctx: DetectionContext
    ) -> List[LunaMessageCreate]:
        """Detect completed preps that need review."""
        messages = []
        
        result = self.supabase.table("meeting_preps") \
            .select("id, prospect_company_name, prospect_id, meeting_id") \
            .eq("user_id", ctx.user_id) \
            .eq("status", "completed") \
            .execute()
        
        for prep in (result.data or []):
            prep_id = prep["id"]
            company = prep.get("prospect_company_name", "Prospect")
            
            dedupe_key = f"prep_ready:{prep_id}"
            if dedupe_key in ctx.existing_dedupe_keys:
                continue
            
            messages.append(LunaMessageCreate(
                user_id=ctx.user_id,
                organization_id=ctx.organization_id,
                dedupe_key=dedupe_key,
                message_type=MessageType.PREP_READY.value,
                title=f"Voorbereiding klaar: {company}",
                description="Je meeting prep is gereed",
                luna_message=f"Je voorbereiding voor {company} is klaar. Bekijk de inzichten voordat je meeting begint.",
                action_type=ActionType.NAVIGATE.value,
                action_route=f"/dashboard/preparation/{prep_id}",
                action_data={"prep_id": prep_id},
                priority=MESSAGE_PRIORITIES.get(MessageType.PREP_READY, 85),
                expires_at=datetime.utcnow() + timedelta(days=2),
                prospect_id=prep.get("prospect_id"),
                prep_id=prep_id,
                meeting_id=prep.get("meeting_id")
            ))
        
        return messages[:3]  # Limit
    
    # =========================================================================
    # POST-MEETING LOOP
    # =========================================================================
    
    async def _detect_post_meeting_loop(
        self,
        ctx: DetectionContext
    ) -> List[LunaMessageCreate]:
        """
        Detect messages for post-meeting loop.
        
        Sequential flow (per SPEC-046 section 7):
        1. review_meeting_summary → requires followup completed
        2. review_customer_report → requires #1 completed
        3. send_followup_email → requires #2 completed  
        4. create_action_items → requires #3 completed
        
        Parallel (after #1):
        - update_crm_notes → requires #1 completed only
        """
        messages = []
        
        # 1. review_meeting_summary: Transcript ready
        messages.extend(await self._detect_review_summary(ctx))
        
        # 2. review_customer_report: After summary reviewed
        messages.extend(await self._detect_review_customer_report(ctx))
        
        # 3. send_followup_email: After customer report viewed
        messages.extend(await self._detect_send_followup_email(ctx))
        
        # 4. create_action_items: After email sent
        messages.extend(await self._detect_create_action_items(ctx))
        
        # 5. update_crm_notes: Parallel path after summary
        messages.extend(await self._detect_update_crm_notes(ctx))
        
        return messages
    
    async def _detect_review_summary(
        self,
        ctx: DetectionContext
    ) -> List[LunaMessageCreate]:
        """Detect followups that need summary review."""
        messages = []
        
        # Find followups with executive_summary but not yet reviewed
        result = self.supabase.table("followups") \
            .select("id, meeting_subject, prospect_id, calendar_meeting_id") \
            .eq("user_id", ctx.user_id) \
            .eq("status", "completed") \
            .not_.is_("executive_summary", None) \
            .execute()
        
        for followup in (result.data or []):
            followup_id = followup["id"]
            meeting_id = followup.get("calendar_meeting_id")
            subject = followup.get("meeting_subject", "Meeting")
            
            dedupe_key = f"review_meeting_summary:{meeting_id or followup_id}"
            if dedupe_key in ctx.existing_dedupe_keys:
                continue
            
            messages.append(LunaMessageCreate(
                user_id=ctx.user_id,
                organization_id=ctx.organization_id,
                dedupe_key=dedupe_key,
                message_type=MessageType.REVIEW_MEETING_SUMMARY.value,
                title=f"Bekijk samenvatting: {subject}",
                description="Je meeting samenvatting is klaar",
                luna_message=f"De samenvatting van '{subject}' is klaar. Bekijk de highlights en actiepunten.",
                action_type=ActionType.NAVIGATE.value,
                action_route=f"/dashboard/followup/{followup_id}",
                action_data={"followup_id": followup_id, "meeting_id": meeting_id},
                priority=MESSAGE_PRIORITIES.get(MessageType.REVIEW_MEETING_SUMMARY, 90),
                expires_at=datetime.utcnow() + timedelta(days=3),
                prospect_id=followup.get("prospect_id"),
                followup_id=followup_id,
                meeting_id=meeting_id
            ))
        
        return messages[:2]
    
    async def _detect_review_customer_report(
        self,
        ctx: DetectionContext
    ) -> List[LunaMessageCreate]:
        """
        Detect followups ready for customer report review.
        Requires review_meeting_summary completed.
        
        Uses existing followup action system - navigates to ActionSheet.
        """
        messages = []
        
        # Find followups with completed summary message
        result = self.supabase.table("followups") \
            .select("id, meeting_subject, prospect_id, calendar_meeting_id") \
            .eq("user_id", ctx.user_id) \
            .eq("status", "completed") \
            .not_.is_("executive_summary", None) \
            .execute()
        
        for followup in (result.data or []):
            followup_id = followup["id"]
            meeting_id = followup.get("calendar_meeting_id")
            subject = followup.get("meeting_subject", "Meeting")
            entity_key = meeting_id or followup_id
            
            dedupe_key = f"review_customer_report:{entity_key}"
            if dedupe_key in ctx.existing_dedupe_keys:
                continue
            
            # Check dependency: review_meeting_summary must be completed for this entity
            completed_for_entity = ctx.completed_message_types.get(entity_key, set())
            if MessageType.REVIEW_MEETING_SUMMARY.value not in completed_for_entity:
                continue
            
            messages.append(LunaMessageCreate(
                user_id=ctx.user_id,
                organization_id=ctx.organization_id,
                dedupe_key=dedupe_key,
                message_type=MessageType.REVIEW_CUSTOMER_REPORT.value,
                title=f"Klantrapport: {subject}",
                description="Bekijk het klantrapport voor je prospect",
                luna_message=f"Het klantrapport voor '{subject}' is klaar. Bijlage voor je follow-up email.",
                action_type=ActionType.NAVIGATE.value,
                # Navigate to followup page with action=customer_report
                action_route=f"/dashboard/followup/{followup_id}?action=customer_report",
                action_data={
                    "followup_id": followup_id,
                    "meeting_id": meeting_id,
                    "action_type": "customer_report"
                },
                priority=MESSAGE_PRIORITIES.get(MessageType.REVIEW_CUSTOMER_REPORT, 85),
                expires_at=datetime.utcnow() + timedelta(days=3),
                prospect_id=followup.get("prospect_id"),
                followup_id=followup_id,
                meeting_id=meeting_id
            ))
        
        return messages[:2]
    
    async def _detect_send_followup_email(
        self,
        ctx: DetectionContext
    ) -> List[LunaMessageCreate]:
        """
        Detect followups ready for follow-up email.
        Requires review_customer_report completed.
        
        Uses existing followup ActionSheet with share_email action.
        """
        messages = []
        
        result = self.supabase.table("followups") \
            .select("id, meeting_subject, prospect_id, calendar_meeting_id") \
            .eq("user_id", ctx.user_id) \
            .eq("status", "completed") \
            .execute()
        
        for followup in (result.data or []):
            followup_id = followup["id"]
            meeting_id = followup.get("calendar_meeting_id")
            subject = followup.get("meeting_subject", "Meeting")
            entity_key = meeting_id or followup_id
            
            dedupe_key = f"send_followup_email:{entity_key}"
            if dedupe_key in ctx.existing_dedupe_keys:
                continue
            
            # Check dependency: review_customer_report must be completed
            completed_for_entity = ctx.completed_message_types.get(entity_key, set())
            if MessageType.REVIEW_CUSTOMER_REPORT.value not in completed_for_entity:
                continue
            
            messages.append(LunaMessageCreate(
                user_id=ctx.user_id,
                organization_id=ctx.organization_id,
                dedupe_key=dedupe_key,
                message_type=MessageType.SEND_FOLLOWUP_EMAIL.value,
                title=f"Verstuur follow-up: {subject}",
                description="Je follow-up email staat klaar om te versturen",
                luna_message=f"De follow-up email voor '{subject}' staat klaar. Review en verstuur naar je prospect.",
                action_type=ActionType.NAVIGATE.value,
                # Navigate to followup page with share_email action
                action_route=f"/dashboard/followup/{followup_id}?action=share_email",
                action_data={
                    "followup_id": followup_id,
                    "meeting_id": meeting_id,
                    "action_type": "share_email"
                },
                priority=MESSAGE_PRIORITIES.get(MessageType.SEND_FOLLOWUP_EMAIL, 80),
                expires_at=datetime.utcnow() + timedelta(days=3),
                prospect_id=followup.get("prospect_id"),
                followup_id=followup_id,
                meeting_id=meeting_id
            ))
        
        return messages[:2]
    
    async def _detect_create_action_items(
        self,
        ctx: DetectionContext
    ) -> List[LunaMessageCreate]:
        """
        Detect followups with action items to assign.
        Requires send_followup_email completed AND action_items exist.
        
        Per SPEC-046: If no action items detected → message is NOT created.
        """
        messages = []
        
        # Only select followups with action items
        result = self.supabase.table("followups") \
            .select("id, meeting_subject, prospect_id, calendar_meeting_id, action_items") \
            .eq("user_id", ctx.user_id) \
            .eq("status", "completed") \
            .execute()
        
        for followup in (result.data or []):
            followup_id = followup["id"]
            meeting_id = followup.get("calendar_meeting_id")
            subject = followup.get("meeting_subject", "Meeting")
            action_items = followup.get("action_items") or []
            entity_key = meeting_id or followup_id
            
            # Skip if no action items (per SPEC-046)
            if not action_items or len(action_items) == 0:
                continue
            
            dedupe_key = f"create_action_items:{entity_key}"
            if dedupe_key in ctx.existing_dedupe_keys:
                continue
            
            # Check dependency: send_followup_email must be completed
            completed_for_entity = ctx.completed_message_types.get(entity_key, set())
            if MessageType.SEND_FOLLOWUP_EMAIL.value not in completed_for_entity:
                continue
            
            messages.append(LunaMessageCreate(
                user_id=ctx.user_id,
                organization_id=ctx.organization_id,
                dedupe_key=dedupe_key,
                message_type=MessageType.CREATE_ACTION_ITEMS.value,
                title=f"Actiepunten: {subject}",
                description=f"{len(action_items)} actiepunten om toe te wijzen",
                luna_message=f"Er zijn {len(action_items)} actiepunten uit '{subject}'. Wijs ze toe en plan ze in.",
                action_type=ActionType.NAVIGATE.value,
                # Navigate to followup page with action_items action
                action_route=f"/dashboard/followup/{followup_id}?action=action_items",
                action_data={
                    "followup_id": followup_id,
                    "meeting_id": meeting_id,
                    "action_type": "action_items",
                    "count": len(action_items)
                },
                priority=MESSAGE_PRIORITIES.get(MessageType.CREATE_ACTION_ITEMS, 75),
                expires_at=datetime.utcnow() + timedelta(days=5),
                prospect_id=followup.get("prospect_id"),
                followup_id=followup_id,
                meeting_id=meeting_id
            ))
        
        return messages[:2]
    
    async def _detect_update_crm_notes(
        self,
        ctx: DetectionContext
    ) -> List[LunaMessageCreate]:
        """
        Detect followups ready for CRM notes update.
        Parallel path - only requires review_meeting_summary completed.
        
        Per SPEC-046: This message runs in PARALLEL with main sequential flow.
        """
        messages = []
        
        result = self.supabase.table("followups") \
            .select("id, meeting_subject, prospect_id, calendar_meeting_id") \
            .eq("user_id", ctx.user_id) \
            .eq("status", "completed") \
            .execute()
        
        for followup in (result.data or []):
            followup_id = followup["id"]
            meeting_id = followup.get("calendar_meeting_id")
            subject = followup.get("meeting_subject", "Meeting")
            entity_key = meeting_id or followup_id
            
            dedupe_key = f"update_crm_notes:{entity_key}"
            if dedupe_key in ctx.existing_dedupe_keys:
                continue
            
            # Check dependency: review_meeting_summary must be completed (parallel path)
            completed_for_entity = ctx.completed_message_types.get(entity_key, set())
            if MessageType.REVIEW_MEETING_SUMMARY.value not in completed_for_entity:
                continue
            
            messages.append(LunaMessageCreate(
                user_id=ctx.user_id,
                organization_id=ctx.organization_id,
                dedupe_key=dedupe_key,
                message_type=MessageType.UPDATE_CRM_NOTES.value,
                title=f"CRM notities: {subject}",
                description="Sync meeting notities naar je CRM",
                luna_message=f"De notities van '{subject}' zijn klaar voor je CRM. Review en sync.",
                action_type=ActionType.NAVIGATE.value,
                # Navigate to followup page with internal_report action
                action_route=f"/dashboard/followup/{followup_id}?action=internal_report",
                action_data={
                    "followup_id": followup_id,
                    "meeting_id": meeting_id,
                    "action_type": "internal_report"
                },
                priority=MESSAGE_PRIORITIES.get(MessageType.UPDATE_CRM_NOTES, 70),
                expires_at=datetime.utcnow() + timedelta(days=5),
                prospect_id=followup.get("prospect_id"),
                followup_id=followup_id,
                meeting_id=meeting_id
            ))
        
        return messages[:2]
    
    # =========================================================================
    # SEQUENCING
    # =========================================================================
    
    def _apply_sequencing(
        self,
        messages: List[LunaMessageCreate],
        ctx: DetectionContext
    ) -> List[LunaMessageCreate]:
        """
        Apply sequencing rules per SPEC-046 section 7.
        
        Rules:
        1. Sequential types must wait for dependencies
        2. Parallel types can run alongside after dependency met
        3. Max 2 concurrent messages
        """
        allowed_messages = []
        
        for msg in messages:
            msg_type = MessageType(msg.message_type)
            
            # Check if dependencies are met
            if msg_type in DEPENDENCY_MAP:
                deps = DEPENDENCY_MAP[msg_type]
                
                # Get entity key for dependency check
                entity_key = msg.meeting_id or msg.prospect_id or "global"
                completed_for_entity = ctx.completed_message_types.get(entity_key, set())
                
                # Check if all dependencies are completed
                deps_met = all(
                    dep.value in completed_for_entity
                    for dep in deps
                )
                
                if not deps_met:
                    logger.debug(f"Skipping {msg_type.value} - dependencies not met")
                    continue
            
            # Check sequential type conflict
            if msg_type in SEQUENTIAL_TYPES:
                # Only one sequential type can be active at a time
                has_conflict = any(
                    t in ctx.pending_message_types
                    for t in SEQUENTIAL_TYPES
                    if t != msg_type.value
                )
                if has_conflict:
                    logger.debug(f"Skipping {msg_type.value} - sequential conflict")
                    continue
            
            allowed_messages.append(msg)
        
        # Sort by priority (highest first)
        allowed_messages.sort(key=lambda m: m.priority, reverse=True)
        
        return allowed_messages
    
    # =========================================================================
    # SINGLE MESSAGE DETECTION
    # =========================================================================
    
    async def should_create_prepare_outreach(
        self,
        user_id: str,
        contact_id: str,
        prospect_id: str
    ) -> bool:
        """
        Check if prepare_outreach should be created for a contact.
        Per SPEC-046 section 10.4.
        """
        # Get user settings
        settings_result = self.supabase.table("luna_settings") \
            .select("outreach_cooldown_days") \
            .eq("user_id", user_id) \
            .limit(1) \
            .execute()
        
        cooldown_days = 14
        if settings_result.data:
            cooldown_days = settings_result.data[0].get("outreach_cooldown_days", 14)
        
        cooldown_start = datetime.utcnow() - timedelta(days=cooldown_days)
        
        # Check 1: Research exists and is viewed
        research_check = self.supabase.table("research_briefs") \
            .select("id") \
            .eq("prospect_id", prospect_id) \
            .eq("status", "completed") \
            .limit(1) \
            .execute()
        
        if not research_check.data:
            return False
        
        # Check 2: Contact exists (passed as parameter)
        
        # Check 3: No recent outreach for contact
        outreach_check = self.supabase.table("outreach_messages") \
            .select("id") \
            .eq("user_id", user_id) \
            .eq("contact_id", contact_id) \
            .in_("status", ["draft", "sent"]) \
            .gte("created_at", cooldown_start.isoformat()) \
            .limit(1) \
            .execute()
        
        if outreach_check.data:
            return False
        
        # Check 4: No meeting linked to prospect
        meeting_check = self.supabase.table("calendar_meetings") \
            .select("id") \
            .eq("prospect_id", prospect_id) \
            .limit(1) \
            .execute()
        
        if meeting_check.data:
            return False
        
        meetings_check = self.supabase.table("meetings") \
            .select("id") \
            .eq("prospect_id", prospect_id) \
            .limit(1) \
            .execute()
        
        if meetings_check.data:
            return False
        
        return True
    
    async def should_create_first_touch_sent(
        self,
        user_id: str,
        outreach_id: str
    ) -> bool:
        """
        Check if first_touch_sent should be created for an outreach.
        Per SPEC-046 section 10.4.
        """
        # Check outreach status
        outreach_check = self.supabase.table("outreach_messages") \
            .select("status, prospect_id") \
            .eq("id", outreach_id) \
            .limit(1) \
            .execute()
        
        if not outreach_check.data:
            return False
        
        outreach = outreach_check.data[0]
        if outreach["status"] != "sent":
            return False
        
        # Check if progress message already exists
        prospect_id = outreach["prospect_id"]
        existing_check = self.supabase.table("luna_messages") \
            .select("id") \
            .eq("user_id", user_id) \
            .eq("dedupe_key", f"first_touch_sent:{prospect_id}:{outreach_id}") \
            .limit(1) \
            .execute()
        
        if existing_check.data:
            return False
        
        return True
