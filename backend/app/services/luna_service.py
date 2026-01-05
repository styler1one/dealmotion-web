"""
Luna Unified AI Assistant - Service Layer
SPEC-046-Luna-Unified-AI-Assistant

Core service for Luna:
- Message management (CRUD, status transitions)
- Settings management
- Feedback recording
- Analytics tracking
- Greeting generation
- Stats calculation
"""

import logging
from datetime import datetime, timedelta
from typing import Optional, List, Dict, Any, Tuple
from zoneinfo import ZoneInfo
from datetime import timezone

from app.database import get_supabase_service
from app.models.luna import (
    MessageType,
    MessageStatus,
    ActionType,
    SnoozeOption,
    FeedbackType,
    Surface,
    LunaMessage,
    LunaMessageCreate,
    MessageCounts,
    MessagesResponse,
    LunaSettings,
    LunaSettingsUpdate,
    LunaGreeting,
    LunaMode,
    TodayStats,
    WeekStats,
    LunaStats,
    TipOfDay,
    TipCategory,
    UpcomingMeeting,
    FeatureFlagsResponse,
    MAX_CONCURRENT_MESSAGES,
    SEQUENTIAL_TYPES,
    DEPENDENCY_MAP,
    MESSAGE_PRIORITIES,
)

logger = logging.getLogger(__name__)


# =============================================================================
# STATIC TIP POOL (generic tips only, no CTA per SPEC-046)
# =============================================================================
STATIC_TIPS: List[Dict[str, Any]] = [
    {
        "id": "tip_research_context",
        "content": "Research briefs with recent news and financial data lead to more relevant conversations.",
        "icon": "🔍",
        "category": "research"
    },
    {
        "id": "tip_prep_contacts",
        "content": "Preps that include contact analysis have 2x higher engagement in meetings.",
        "icon": "📋",
        "category": "prep"
    },
    {
        "id": "tip_followup_timing",
        "content": "Follow-ups sent within 24 hours of a meeting have the highest response rates.",
        "icon": "⏰",
        "category": "followup"
    },
    {
        "id": "tip_outreach_personalization",
        "content": "Personalized outreach messages that reference recent company news get 3x more responses.",
        "icon": "✨",
        "category": "general"
    },
    {
        "id": "tip_meeting_prep",
        "content": "Reading your prep 30 minutes before a meeting helps you enter with confidence.",
        "icon": "📋",
        "category": "prep"
    },
    {
        "id": "tip_action_items",
        "content": "Meetings with documented action items are 50% more likely to lead to next steps.",
        "icon": "✅",
        "category": "followup"
    },
    {
        "id": "tip_research_linkedin",
        "content": "Research that includes LinkedIn activity analysis reveals what your prospect cares about.",
        "icon": "💼",
        "category": "research"
    },
    {
        "id": "tip_crm_notes",
        "content": "Keeping CRM notes updated helps your entire team stay aligned on deal progress.",
        "icon": "📝",
        "category": "general"
    },
]


class LunaService:
    """
    Service for Luna AI Assistant.
    
    Responsibilities:
    - CRUD operations for luna_messages
    - Status transitions (accept, dismiss, snooze)
    - Viewed/acted timestamp management
    - Settings management
    - Feedback recording
    - Analytics event tracking
    - Greeting generation
    - Stats calculation
    """
    
    def __init__(self, supabase=None):
        """Initialize with optional Supabase client."""
        self.supabase = supabase or get_supabase_service()
    
    # =========================================================================
    # FEATURE FLAGS
    # =========================================================================
    
    async def get_feature_flags(self, user_id: str) -> FeatureFlagsResponse:
        """Get Luna feature flags for a user."""
        try:
            result = self.supabase.table("luna_feature_flags").select("*").execute()
            flags = {row["flag_name"]: row for row in (result.data or [])}
            
            # Check if user is in percentage rollout or explicit list
            luna_enabled = False
            if "luna_enabled" in flags:
                flag = flags["luna_enabled"]
                if flag["flag_value"]:
                    luna_enabled = True
                elif user_id in (flag.get("enabled_user_ids") or []):
                    luna_enabled = True
                elif flag.get("user_percentage", 0) > 0:
                    # Deterministic hash
                    user_hash = abs(hash(user_id)) % 100
                    luna_enabled = user_hash < flag["user_percentage"]
            
            return FeatureFlagsResponse(
                luna_enabled=luna_enabled,
                luna_shadow_mode=flags.get("luna_shadow_mode", {}).get("flag_value", False),
                luna_widget_enabled=flags.get("luna_widget_enabled", {}).get("flag_value", False),
                luna_p1_features=flags.get("luna_p1_features", {}).get("flag_value", False),
            )
        except Exception as e:
            logger.error(f"Error getting feature flags: {e}")
            # Safe defaults
            return FeatureFlagsResponse(
                luna_enabled=False,
                luna_shadow_mode=True,
                luna_widget_enabled=False,
                luna_p1_features=False,
            )
    
    # =========================================================================
    # MESSAGE MANAGEMENT
    # =========================================================================
    
    async def get_messages(
        self,
        user_id: str,
        status: Optional[str] = None,
        limit: int = 20
    ) -> MessagesResponse:
        """
        Get Luna messages for a user with optional status filter.
        
        Returns messages sorted by priority (highest first).
        Automatically processes snoozed messages that are ready.
        """
        try:
            # First, un-snooze messages whose snooze_until has passed
            await self._process_snoozed_messages(user_id)
            
            # Build query
            query = self.supabase.table("luna_messages") \
                .select("*") \
                .eq("user_id", user_id) \
                .order("priority", desc=True) \
                .order("created_at", desc=True) \
                .limit(limit)
            
            if status:
                query = query.eq("status", status)
            else:
                # By default, only show actionable messages
                query = query.in_("status", ["pending", "executing"])
            
            result = query.execute()
            
            messages = [LunaMessage(**row) for row in (result.data or [])]
            counts = await self._get_message_counts(user_id)
            
            return MessagesResponse(
                messages=messages,
                counts=counts,
                total=len(messages)
            )
            
        except Exception as e:
            logger.error(f"Error getting messages for user {user_id}: {e}")
            raise
    
    async def _process_snoozed_messages(self, user_id: str) -> int:
        """Un-snooze messages whose snooze_until has passed."""
        try:
            now = datetime.utcnow().isoformat()
            
            result = self.supabase.table("luna_messages") \
                .update({"status": "pending", "snooze_until": None}) \
                .eq("user_id", user_id) \
                .eq("status", "snoozed") \
                .lt("snooze_until", now) \
                .execute()
            
            count = len(result.data or [])
            if count > 0:
                logger.info(f"Un-snoozed {count} messages for user {user_id}")
            return count
            
        except Exception as e:
            logger.warning(f"Error processing snoozed messages: {e}")
            return 0
    
    async def _get_message_counts(self, user_id: str) -> MessageCounts:
        """Get counts of messages by status."""
        try:
            result = self.supabase.table("luna_messages") \
                .select("status, priority") \
                .eq("user_id", user_id) \
                .execute()
            
            counts = MessageCounts()
            for row in (result.data or []):
                status = row.get("status")
                priority = row.get("priority", 50)
                
                if status == "pending":
                    counts.pending += 1
                    if priority >= 80:
                        counts.urgent += 1
                elif status == "executing":
                    counts.executing += 1
                elif status == "completed":
                    counts.completed += 1
                elif status == "dismissed":
                    counts.dismissed += 1
                elif status == "snoozed":
                    counts.snoozed += 1
                elif status == "expired":
                    counts.expired += 1
                elif status == "failed":
                    counts.failed += 1
            
            return counts
            
        except Exception as e:
            logger.error(f"Error getting message counts: {e}")
            return MessageCounts()
    
    async def get_message(self, message_id: str, user_id: str) -> Optional[LunaMessage]:
        """Get a single message by ID."""
        try:
            result = self.supabase.table("luna_messages") \
                .select("*") \
                .eq("id", message_id) \
                .eq("user_id", user_id) \
                .single() \
                .execute()
            
            if result.data:
                return LunaMessage(**result.data)
            return None
            
        except Exception as e:
            logger.error(f"Error getting message {message_id}: {e}")
            return None
    
    async def create_message(self, message: LunaMessageCreate) -> Optional[LunaMessage]:
        """Create a new Luna message with deduplication."""
        try:
            # Use mode='json' to convert datetime objects to ISO strings
            data = message.model_dump(mode='json')
            data["created_at"] = datetime.utcnow().isoformat()
            data["updated_at"] = datetime.utcnow().isoformat()
            
            result = self.supabase.table("luna_messages") \
                .upsert(data, on_conflict="user_id,dedupe_key") \
                .execute()
            
            if result.data:
                return LunaMessage(**result.data[0])
            return None
            
        except Exception as e:
            logger.error(f"Error creating message: {e}")
            return None
    
    # =========================================================================
    # STATUS TRANSITIONS
    # =========================================================================
    
    async def mark_shown(
        self,
        message_id: str,
        user_id: str,
        surface: Surface
    ) -> bool:
        """
        Mark a message as shown (viewed_at set once).
        Per SPEC-046 section 13.4: viewed_at is set ONCE on first show.
        """
        try:
            # Get current message to check if already viewed
            message = await self.get_message(message_id, user_id)
            if not message:
                return False
            
            # Only set viewed_at if not already set
            if message.viewed_at is None:
                self.supabase.table("luna_messages") \
                    .update({
                        "viewed_at": datetime.utcnow().isoformat(),
                        "updated_at": datetime.utcnow().isoformat()
                    }) \
                    .eq("id", message_id) \
                    .eq("user_id", user_id) \
                    .execute()
            
            # Track analytics event (always, even if not first view)
            await self._track_event("luna_message_shown", user_id, {
                "message_id": message_id,
                "message_type": message.message_type,
                "priority": message.priority,
                "surface": surface.value,
                "first_view": message.viewed_at is None
            })
            
            return True
            
        except Exception as e:
            logger.error(f"Error marking message shown: {e}")
            return False
    
    async def accept_message(
        self,
        message_id: str,
        user_id: str,
        surface: Optional[Surface] = None
    ) -> Tuple[bool, Optional[str]]:
        """
        Accept a message (user clicked the CTA).
        Transitions: pending -> executing (for execute actions)
                    pending -> completed (for navigate/inline)
        """
        try:
            message = await self.get_message(message_id, user_id)
            if not message:
                return False, "Message not found"
            
            if message.status != MessageStatus.PENDING:
                return False, f"Cannot accept message in status {message.status}"
            
            now = datetime.utcnow()
            
            # Determine new status based on action type
            if message.action_type == ActionType.EXECUTE:
                new_status = MessageStatus.EXECUTING
            else:
                new_status = MessageStatus.COMPLETED
            
            # Update message
            self.supabase.table("luna_messages") \
                .update({
                    "status": new_status.value,
                    "acted_at": now.isoformat(),
                    "updated_at": now.isoformat()
                }) \
                .eq("id", message_id) \
                .eq("user_id", user_id) \
                .execute()
            
            # Calculate time to action
            time_to_action = None
            if message.viewed_at:
                try:
                    viewed = datetime.fromisoformat(str(message.viewed_at).replace("Z", "+00:00")).replace(tzinfo=None)
                    time_to_action = int((now - viewed).total_seconds())
                except:
                    pass
            
            # Record feedback
            await self._record_feedback(
                user_id=user_id,
                message=message,
                feedback_type=FeedbackType.ACCEPTED,
                time_to_action_seconds=time_to_action,
                surface=surface
            )
            
            # Track analytics
            await self._track_event("luna_message_accepted", user_id, {
                "message_id": message_id,
                "message_type": message.message_type,
                "time_to_action_seconds": time_to_action,
                "surface": surface.value if surface else None
            })
            
            return True, None
            
        except Exception as e:
            logger.error(f"Error accepting message: {e}")
            return False, str(e)
    
    async def dismiss_message(
        self,
        message_id: str,
        user_id: str,
        surface: Optional[Surface] = None
    ) -> Tuple[bool, Optional[str]]:
        """Dismiss a message (user clicked X)."""
        try:
            message = await self.get_message(message_id, user_id)
            if not message:
                return False, "Message not found"
            
            if message.status not in [MessageStatus.PENDING, MessageStatus.EXECUTING]:
                return False, f"Cannot dismiss message in status {message.status}"
            
            now = datetime.utcnow()
            
            # Update message
            self.supabase.table("luna_messages") \
                .update({
                    "status": MessageStatus.DISMISSED.value,
                    "acted_at": now.isoformat(),
                    "updated_at": now.isoformat()
                }) \
                .eq("id", message_id) \
                .eq("user_id", user_id) \
                .execute()
            
            # Calculate time shown
            time_shown = None
            if message.viewed_at:
                try:
                    viewed = datetime.fromisoformat(str(message.viewed_at).replace("Z", "+00:00")).replace(tzinfo=None)
                    time_shown = int((now - viewed).total_seconds())
                except:
                    pass
            
            # Record feedback
            await self._record_feedback(
                user_id=user_id,
                message=message,
                feedback_type=FeedbackType.DISMISSED,
                time_shown_seconds=time_shown,
                surface=surface
            )
            
            # Track analytics
            await self._track_event("luna_message_dismissed", user_id, {
                "message_id": message_id,
                "message_type": message.message_type,
                "time_shown_seconds": time_shown
            })
            
            return True, None
            
        except Exception as e:
            logger.error(f"Error dismissing message: {e}")
            return False, str(e)
    
    async def snooze_message(
        self,
        message_id: str,
        user_id: str,
        snooze_option: SnoozeOption,
        custom_datetime: Optional[datetime] = None,
        surface: Optional[Surface] = None,
        user_timezone: str = "Europe/Amsterdam"
    ) -> Tuple[bool, Optional[str]]:
        """
        Snooze a message (user clicked Later).
        Per SPEC-046 section 12: snooze does NOT change dedupe_key.
        """
        try:
            message = await self.get_message(message_id, user_id)
            if not message:
                return False, "Message not found"
            
            if message.status != MessageStatus.PENDING:
                return False, f"Cannot snooze message in status {message.status}"
            
            # Calculate snooze_until based on option
            snooze_until = self._calculate_snooze_until(
                snooze_option,
                custom_datetime,
                message.meeting_id,
                user_timezone
            )
            
            if not snooze_until:
                return False, "Could not calculate snooze time"
            
            now = datetime.utcnow()
            
            # Update message
            self.supabase.table("luna_messages") \
                .update({
                    "status": MessageStatus.SNOOZED.value,
                    "snooze_until": snooze_until.isoformat(),
                    "acted_at": now.isoformat(),
                    "updated_at": now.isoformat()
                }) \
                .eq("id", message_id) \
                .eq("user_id", user_id) \
                .execute()
            
            # Calculate snooze duration
            snooze_hours = int((snooze_until - now).total_seconds() / 3600)
            
            # Record feedback
            await self._record_feedback(
                user_id=user_id,
                message=message,
                feedback_type=FeedbackType.SNOOZED,
                snooze_duration_hours=snooze_hours,
                surface=surface
            )
            
            # Track analytics
            await self._track_event("luna_message_snoozed", user_id, {
                "message_id": message_id,
                "message_type": message.message_type,
                "snooze_duration_hours": snooze_hours
            })
            
            return True, None
            
        except Exception as e:
            logger.error(f"Error snoozing message: {e}")
            return False, str(e)
    
    def _calculate_snooze_until(
        self,
        option: SnoozeOption,
        custom_datetime: Optional[datetime],
        meeting_id: Optional[str],
        user_timezone: str
    ) -> Optional[datetime]:
        """Calculate snooze_until datetime based on option."""
        try:
            tz = ZoneInfo(user_timezone)
            now_local = datetime.now(tz)
            
            if option == SnoozeOption.LATER_TODAY:
                # +4 hours
                return (now_local + timedelta(hours=4)).astimezone(timezone.utc).replace(tzinfo=None)
            
            elif option == SnoozeOption.TOMORROW_MORNING:
                # Next day 09:00 local
                tomorrow = now_local + timedelta(days=1)
                morning = tomorrow.replace(hour=9, minute=0, second=0, microsecond=0)
                return morning.astimezone(timezone.utc).replace(tzinfo=None)
            
            elif option == SnoozeOption.NEXT_WORKING_DAY:
                # Next weekday 09:00 local
                next_day = now_local + timedelta(days=1)
                while next_day.weekday() >= 5:  # Saturday=5, Sunday=6
                    next_day += timedelta(days=1)
                morning = next_day.replace(hour=9, minute=0, second=0, microsecond=0)
                return morning.astimezone(timezone.utc).replace(tzinfo=None)
            
            elif option == SnoozeOption.AFTER_MEETING:
                # Meeting end time (only if meeting_id present)
                if meeting_id:
                    # TODO: Look up meeting end time from database
                    # For now, default to +2 hours
                    return (now_local + timedelta(hours=2)).astimezone(timezone.utc).replace(tzinfo=None)
                return None
            
            elif option == SnoozeOption.CUSTOM:
                if custom_datetime:
                    return custom_datetime
                return None
            
            return None
            
        except Exception as e:
            logger.error(f"Error calculating snooze time: {e}")
            return None
    
    async def mark_completed(
        self,
        message_id: str,
        user_id: str,
        result: Optional[Dict[str, Any]] = None
    ) -> bool:
        """Mark an executing message as completed."""
        try:
            message = await self.get_message(message_id, user_id)
            if not message:
                return False
            
            self.supabase.table("luna_messages") \
                .update({
                    "status": MessageStatus.COMPLETED.value,
                    "updated_at": datetime.utcnow().isoformat()
                }) \
                .eq("id", message_id) \
                .eq("user_id", user_id) \
                .execute()
            
            # Record feedback
            await self._record_feedback(
                user_id=user_id,
                message=message,
                feedback_type=FeedbackType.COMPLETED
            )
            
            # Track analytics
            await self._track_event("luna_action_completed", user_id, {
                "message_id": message_id,
                "message_type": message.message_type,
                "result_type": result.get("type") if result else None,
                "result_id": result.get("id") if result else None
            })
            
            return True
            
        except Exception as e:
            logger.error(f"Error marking message completed: {e}")
            return False
    
    async def mark_failed(
        self,
        message_id: str,
        user_id: str,
        error_code: str,
        error_message: str,
        retryable: bool = False
    ) -> bool:
        """Mark an executing message as failed."""
        try:
            message = await self.get_message(message_id, user_id)
            if not message:
                return False
            
            self.supabase.table("luna_messages") \
                .update({
                    "status": MessageStatus.FAILED.value,
                    "error_code": error_code,
                    "error_message": error_message,
                    "retryable": retryable,
                    "updated_at": datetime.utcnow().isoformat()
                }) \
                .eq("id", message_id) \
                .eq("user_id", user_id) \
                .execute()
            
            # Record feedback
            await self._record_feedback(
                user_id=user_id,
                message=message,
                feedback_type=FeedbackType.FAILED
            )
            
            # Track analytics
            await self._track_event("luna_action_failed", user_id, {
                "message_id": message_id,
                "message_type": message.message_type,
                "error_code": error_code,
                "retryable": retryable
            })
            
            return True
            
        except Exception as e:
            logger.error(f"Error marking message failed: {e}")
            return False
    
    # =========================================================================
    # SETTINGS
    # =========================================================================
    
    async def get_settings(self, user_id: str, organization_id: str) -> LunaSettings:
        """Get Luna settings for a user, creating defaults if needed."""
        try:
            result = self.supabase.table("luna_settings") \
                .select("*") \
                .eq("user_id", user_id) \
                .single() \
                .execute()
            
            if result.data:
                return LunaSettings(**result.data)
            
            # Create default settings
            return await self._create_default_settings(user_id, organization_id)
            
        except Exception as e:
            # If single() fails (no row), create defaults
            if "PGRST116" in str(e):
                return await self._create_default_settings(user_id, organization_id)
            logger.error(f"Error getting settings: {e}")
            raise
    
    async def _create_default_settings(
        self,
        user_id: str,
        organization_id: str
    ) -> LunaSettings:
        """Create default Luna settings for a user."""
        try:
            now = datetime.utcnow().isoformat()
            data = {
                "user_id": user_id,
                "organization_id": organization_id,
                "enabled": True,
                "show_widget": True,
                "show_contextual_tips": True,
                "prep_reminder_hours": 24,
                "outreach_cooldown_days": 14,
                "excluded_meeting_keywords": ["internal", "1:1", "standup", "sync"],
                "created_at": now,
                "updated_at": now
            }
            
            result = self.supabase.table("luna_settings") \
                .insert(data) \
                .execute()
            
            if result.data:
                return LunaSettings(**result.data[0])
            
            raise Exception("Failed to create settings")
            
        except Exception as e:
            logger.error(f"Error creating default settings: {e}")
            raise
    
    async def update_settings(
        self,
        user_id: str,
        updates: LunaSettingsUpdate
    ) -> LunaSettings:
        """Update Luna settings for a user."""
        try:
            data = updates.model_dump(exclude_unset=True)
            data["updated_at"] = datetime.utcnow().isoformat()
            
            result = self.supabase.table("luna_settings") \
                .update(data) \
                .eq("user_id", user_id) \
                .execute()
            
            if result.data:
                return LunaSettings(**result.data[0])
            
            raise Exception("Settings not found")
            
        except Exception as e:
            logger.error(f"Error updating settings: {e}")
            raise
    
    # =========================================================================
    # GREETING
    # =========================================================================
    
    async def get_greeting(self, user_id: str) -> LunaGreeting:
        """Generate contextual greeting for Luna Home."""
        try:
            counts = await self._get_message_counts(user_id)
            
            # Determine mode based on context
            now = datetime.now()
            hour = now.hour
            
            if counts.urgent > 0:
                mode = LunaMode.URGENCY
                message = f"Je hebt {counts.urgent} urgente {'actie' if counts.urgent == 1 else 'acties'} die aandacht nodig {'heeft' if counts.urgent == 1 else 'hebben'}."
                emphasis = "Let op!"
            elif counts.pending == 0:
                mode = LunaMode.CELEBRATION
                message = "Alles is bijgewerkt! Neem even de tijd om te focussen op je meetings."
                emphasis = "Goed bezig!"
            elif hour < 12:
                mode = LunaMode.MORNING
                message = f"Goedemorgen! Je hebt {counts.pending} {'actie' if counts.pending == 1 else 'acties'} voor vandaag."
                emphasis = None
            else:
                mode = LunaMode.FOCUS
                message = f"Je hebt {counts.pending} {'actie' if counts.pending == 1 else 'acties'} klaarstaan."
                emphasis = None
            
            return LunaGreeting(
                mode=mode,
                message=message,
                emphasis=emphasis,
                pending_count=counts.pending,
                urgent_count=counts.urgent
            )
            
        except Exception as e:
            logger.error(f"Error generating greeting: {e}")
            return LunaGreeting(
                mode=LunaMode.MORNING,
                message="Welkom bij Luna!",
                pending_count=0,
                urgent_count=0
            )
    
    # =========================================================================
    # STATS
    # =========================================================================
    
    async def get_stats(self, user_id: str, organization_id: str) -> LunaStats:
        """
        Get Luna stats for a user.
        
        IMPORTANT: Stats count ACTUAL items created today, not Luna messages viewed.
        - research_completed: research_briefs created today
        - preps_completed: meeting_preps created today  
        - followups_completed: followups completed today
        - outreach_sent: outreach_messages sent today
        """
        try:
            counts = await self._get_message_counts(user_id)
            
            # Get today's start timestamp
            today_start = datetime.utcnow().replace(hour=0, minute=0, second=0, microsecond=0)
            today_iso = today_start.isoformat()
            
            today = TodayStats()
            
            # Count ACTUAL research briefs created today
            research_result = self.supabase.table("research_briefs") \
                .select("id", count="exact") \
                .eq("user_id", user_id) \
                .eq("status", "completed") \
                .gte("completed_at", today_iso) \
                .execute()
            today.research_completed = research_result.count or 0
            
            # Count ACTUAL meeting preps created today
            preps_result = self.supabase.table("meeting_preps") \
                .select("id", count="exact") \
                .eq("user_id", user_id) \
                .eq("status", "completed") \
                .gte("completed_at", today_iso) \
                .execute()
            today.preps_completed = preps_result.count or 0
            
            # Count ACTUAL followups completed today
            followups_result = self.supabase.table("followups") \
                .select("id", count="exact") \
                .eq("user_id", user_id) \
                .eq("status", "completed") \
                .gte("completed_at", today_iso) \
                .execute()
            today.followups_completed = followups_result.count or 0
            
            # Count ACTUAL outreach messages sent today
            outreach_result = self.supabase.table("outreach_messages") \
                .select("id", count="exact") \
                .eq("user_id", user_id) \
                .eq("status", "sent") \
                .gte("sent_at", today_iso) \
                .execute()
            today.outreach_sent = outreach_result.count or 0
            
            # Total is sum of all actual items
            today.total_actions = (
                today.research_completed + 
                today.preps_completed + 
                today.followups_completed + 
                today.outreach_sent
            )
            
            # Get this week's start timestamp (Monday 00:00:00)
            now = datetime.utcnow()
            days_since_monday = now.weekday()  # 0 = Monday, 6 = Sunday
            week_start = (now - timedelta(days=days_since_monday)).replace(hour=0, minute=0, second=0, microsecond=0)
            week_iso = week_start.isoformat()
            
            week = WeekStats()
            
            # Count ACTUAL research briefs created this week
            research_week_result = self.supabase.table("research_briefs") \
                .select("id", count="exact") \
                .eq("user_id", user_id) \
                .eq("status", "completed") \
                .gte("completed_at", week_iso) \
                .execute()
            week.research_completed = research_week_result.count or 0
            
            # Count ACTUAL meeting preps created this week
            preps_week_result = self.supabase.table("meeting_preps") \
                .select("id", count="exact") \
                .eq("user_id", user_id) \
                .eq("status", "completed") \
                .gte("completed_at", week_iso) \
                .execute()
            week.preps_completed = preps_week_result.count or 0
            
            # Count ACTUAL followups completed this week
            followups_week_result = self.supabase.table("followups") \
                .select("id", count="exact") \
                .eq("user_id", user_id) \
                .eq("status", "completed") \
                .gte("completed_at", week_iso) \
                .execute()
            week.followups_completed = followups_week_result.count or 0
            
            # Count ACTUAL outreach messages sent this week
            outreach_week_result = self.supabase.table("outreach_messages") \
                .select("id", count="exact") \
                .eq("user_id", user_id) \
                .eq("status", "sent") \
                .gte("sent_at", week_iso) \
                .execute()
            week.outreach_sent = outreach_week_result.count or 0
            
            # Total is sum of all actual items
            week.total_actions = (
                week.research_completed + 
                week.preps_completed + 
                week.followups_completed + 
                week.outreach_sent
            )
            
            return LunaStats(
                today=today,
                week=week,
                pending_count=counts.pending,
                urgent_count=counts.urgent,
                completed_today=today.total_actions
            )
            
        except Exception as e:
            logger.error(f"Error getting stats: {e}")
            return LunaStats(today=TodayStats(), week=WeekStats())
    
    # =========================================================================
    # TIP OF DAY
    # =========================================================================
    
    async def get_tip_of_day(self, user_id: str) -> TipOfDay:
        """
        Get tip of the day - generic only, no CTA per SPEC-046.
        Cached for 24 hours.
        """
        try:
            # Simple rotation based on day of year
            day_of_year = datetime.now().timetuple().tm_yday
            tip_index = day_of_year % len(STATIC_TIPS)
            tip_data = STATIC_TIPS[tip_index]
            
            return TipOfDay(
                id=tip_data["id"],
                content=tip_data["content"],
                icon=tip_data["icon"],
                category=TipCategory(tip_data["category"])
            )
            
        except Exception as e:
            logger.error(f"Error getting tip of day: {e}")
            # Fallback tip
            return TipOfDay(
                id="tip_fallback",
                content="Focus on your highest priority actions first.",
                icon="💡",
                category=TipCategory.GENERAL
            )
    
    # =========================================================================
    # UPCOMING MEETINGS
    # =========================================================================
    
    async def get_upcoming_meetings(
        self,
        user_id: str,
        organization_id: str,
        limit: int = 5
    ) -> List[UpcomingMeeting]:
        """Get upcoming meetings with prep status."""
        try:
            now = datetime.utcnow()
            end_of_day = now.replace(hour=23, minute=59, second=59)
            
            # Get meetings from calendar_meetings or meetings table
            result = self.supabase.table("calendar_meetings") \
                .select("id, title, start_time, prospect_id, prospects(company_name)") \
                .eq("user_id", user_id) \
                .gte("start_time", now.isoformat()) \
                .lte("start_time", end_of_day.isoformat()) \
                .order("start_time") \
                .limit(limit) \
                .execute()
            
            meetings = []
            for row in (result.data or []):
                meeting_id = row["id"]
                start_time = datetime.fromisoformat(row["start_time"].replace("Z", "+00:00")).replace(tzinfo=None)
                starts_in_hours = (start_time - now).total_seconds() / 3600
                
                # Check for prep
                prep_result = self.supabase.table("meeting_preps") \
                    .select("id") \
                    .eq("prospect_id", row.get("prospect_id")) \
                    .limit(1) \
                    .execute()
                
                has_prep = bool(prep_result.data)
                prep_id = prep_result.data[0]["id"] if prep_result.data else None
                
                company = None
                if row.get("prospects"):
                    company = row["prospects"].get("company_name")
                
                meetings.append(UpcomingMeeting(
                    id=meeting_id,
                    title=row["title"],
                    company=company,
                    start_time=start_time,
                    starts_in_hours=starts_in_hours,
                    has_prep=has_prep,
                    prospect_id=row.get("prospect_id"),
                    prep_id=prep_id
                ))
            
            return meetings
            
        except Exception as e:
            logger.error(f"Error getting upcoming meetings: {e}")
            return []
    
    # =========================================================================
    # FEEDBACK & ANALYTICS
    # =========================================================================
    
    async def _record_feedback(
        self,
        user_id: str,
        message: LunaMessage,
        feedback_type: FeedbackType,
        time_to_action_seconds: Optional[int] = None,
        time_shown_seconds: Optional[int] = None,
        snooze_duration_hours: Optional[int] = None,
        surface: Optional[Surface] = None
    ) -> None:
        """Record feedback for analytics and learning."""
        try:
            # Get organization_id from message
            org_result = self.supabase.table("organization_members") \
                .select("organization_id") \
                .eq("user_id", user_id) \
                .limit(1) \
                .execute()
            
            org_id = org_result.data[0]["organization_id"] if org_result.data else None
            
            data = {
                "user_id": user_id,
                "organization_id": org_id,
                "message_id": message.id,
                "feedback_type": feedback_type.value,
                "message_type": message.message_type,
                "time_to_action_seconds": time_to_action_seconds,
                "time_shown_seconds": time_shown_seconds,
                "snooze_duration_hours": snooze_duration_hours,
                "surface": surface.value if surface else None,
                "created_at": datetime.utcnow().isoformat()
            }
            
            self.supabase.table("luna_feedback").insert(data).execute()
            
        except Exception as e:
            logger.warning(f"Error recording feedback: {e}")
    
    async def _track_event(
        self,
        event_name: str,
        user_id: str,
        properties: Dict[str, Any]
    ) -> None:
        """Track analytics event."""
        try:
            # Log for now - integrate with actual analytics service later
            logger.info(f"Analytics: {event_name} - user={user_id} - {properties}")
            
            # TODO: Integrate with actual analytics service (e.g., PostHog, Mixpanel)
            # from app.services.analytics import track
            # await track(user_id, event_name, properties)
            
        except Exception as e:
            logger.warning(f"Error tracking event: {e}")
