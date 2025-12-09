"""
Coach Pattern Learning Service

This service analyzes user behavior events to learn patterns that can be used
to improve suggestion timing and prioritization.

Patterns tracked:
- Work hours: When the user is typically active
- Step timing: How long users take between workflow steps
- Dismiss patterns: Which suggestion types get dismissed frequently
- Success patterns: What actions lead to successful outcomes
"""

from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any
from enum import Enum
from collections import defaultdict
import logging

logger = logging.getLogger(__name__)


class PatternType(str, Enum):
    """Types of patterns we can learn."""
    WORK_HOURS = "work_hours"
    STEP_TIMING = "step_timing"
    DISMISS_PATTERN = "dismiss_pattern"
    PAGE_FREQUENCY = "page_frequency"
    ACTION_SEQUENCE = "action_sequence"


class PatternLearner:
    """
    Analyzes behavior events to learn user patterns.
    """
    
    def __init__(self, supabase):
        self.supabase = supabase
    
    async def analyze_work_hours(
        self, 
        user_id: str, 
        days: int = 30
    ) -> Dict[str, Any]:
        """
        Analyze when the user is typically active.
        
        Returns:
            Dict with:
            - peak_hours: List of most active hours (0-23)
            - active_days: List of most active weekdays (0-6)
            - quiet_hours: List of typically inactive hours
            - confidence: How confident we are in this pattern (0-1)
        """
        since = (datetime.now() - timedelta(days=days)).isoformat()
        
        try:
            result = self.supabase.table("coach_behavior_events") \
                .select("created_at") \
                .eq("user_id", user_id) \
                .gte("created_at", since) \
                .execute()
            
            if not result.data or len(result.data) < 10:
                # Not enough data
                return {
                    "peak_hours": [9, 10, 11, 14, 15, 16],  # Default business hours
                    "active_days": [0, 1, 2, 3, 4],  # Mon-Fri
                    "quiet_hours": [0, 1, 2, 3, 4, 5, 6, 22, 23],
                    "confidence": 0.1,
                }
            
            # Count events per hour and day
            hour_counts = defaultdict(int)
            day_counts = defaultdict(int)
            
            for event in result.data:
                dt = datetime.fromisoformat(event["created_at"].replace("Z", "+00:00"))
                hour_counts[dt.hour] += 1
                day_counts[dt.weekday()] += 1
            
            # Find peak hours (top 6)
            sorted_hours = sorted(hour_counts.items(), key=lambda x: x[1], reverse=True)
            peak_hours = [h for h, _ in sorted_hours[:6]]
            
            # Find quiet hours (bottom 6 or hours with 0 events)
            all_hours = set(range(24))
            active_hours = set(hour_counts.keys())
            inactive_hours = all_hours - active_hours
            
            if len(inactive_hours) >= 6:
                quiet_hours = list(inactive_hours)[:9]
            else:
                sorted_by_activity = sorted(hour_counts.items(), key=lambda x: x[1])
                quiet_hours = list(inactive_hours) + [h for h, _ in sorted_by_activity[:9 - len(inactive_hours)]]
            
            # Find active days
            sorted_days = sorted(day_counts.items(), key=lambda x: x[1], reverse=True)
            active_days = [d for d, _ in sorted_days if day_counts[d] > 0]
            
            # Calculate confidence based on data volume
            total_events = len(result.data)
            confidence = min(1.0, total_events / 100)
            
            return {
                "peak_hours": sorted(peak_hours),
                "active_days": sorted(active_days),
                "quiet_hours": sorted(quiet_hours),
                "confidence": round(confidence, 2),
                "total_events_analyzed": total_events,
            }
            
        except Exception as e:
            logger.error(f"Error analyzing work hours: {e}")
            return {
                "peak_hours": [9, 10, 11, 14, 15, 16],
                "active_days": [0, 1, 2, 3, 4],
                "quiet_hours": [0, 1, 2, 3, 4, 5, 6, 22, 23],
                "confidence": 0.0,
                "error": str(e),
            }
    
    async def analyze_step_timing(
        self, 
        user_id: str, 
        organization_id: str
    ) -> Dict[str, Any]:
        """
        Analyze how long users typically take between workflow steps.
        
        E.g., time between research completion and prep creation.
        
        Returns:
            Dict with timing statistics for each step transition.
        """
        try:
            # Get research briefs with their completion times
            research_result = self.supabase.table("research_briefs") \
                .select("company_name, completed_at, prospect_id") \
                .eq("organization_id", organization_id) \
                .eq("status", "completed") \
                .not_.is_("completed_at", "null") \
                .order("completed_at") \
                .execute()
            
            # Get preps with their times
            preps_result = self.supabase.table("meeting_preps") \
                .select("prospect_company_name, created_at, completed_at") \
                .eq("organization_id", organization_id) \
                .order("created_at") \
                .execute()
            
            # Get followups with their times
            followups_result = self.supabase.table("followups") \
                .select("prospect_company_name, created_at, completed_at") \
                .eq("organization_id", organization_id) \
                .order("created_at") \
                .execute()
            
            # Calculate timing patterns
            research_to_prep_times = []
            prep_to_followup_times = []
            
            # Match research to preps by company name
            research_by_company = {
                r.get("company_name", "").lower(): r 
                for r in (research_result.data or [])
            }
            preps_by_company = {
                p.get("prospect_company_name", "").lower(): p 
                for p in (preps_result.data or [])
            }
            followups_by_company = {
                f.get("prospect_company_name", "").lower(): f 
                for f in (followups_result.data or [])
            }
            
            # Research → Prep timing
            for company, research in research_by_company.items():
                if company in preps_by_company:
                    prep = preps_by_company[company]
                    if research.get("completed_at") and prep.get("created_at"):
                        research_time = datetime.fromisoformat(
                            research["completed_at"].replace("Z", "+00:00")
                        )
                        prep_time = datetime.fromisoformat(
                            prep["created_at"].replace("Z", "+00:00")
                        )
                        delta = (prep_time - research_time).total_seconds() / 3600  # hours
                        if delta >= 0:  # Only positive deltas
                            research_to_prep_times.append(delta)
            
            # Prep → Follow-up timing
            for company, prep in preps_by_company.items():
                if company in followups_by_company:
                    followup = followups_by_company[company]
                    if prep.get("completed_at") and followup.get("created_at"):
                        prep_time = datetime.fromisoformat(
                            prep["completed_at"].replace("Z", "+00:00")
                        )
                        followup_time = datetime.fromisoformat(
                            followup["created_at"].replace("Z", "+00:00")
                        )
                        delta = (followup_time - prep_time).total_seconds() / 3600
                        if delta >= 0:
                            prep_to_followup_times.append(delta)
            
            def calculate_stats(times: List[float]) -> Dict[str, Any]:
                if not times:
                    return {"average_hours": None, "median_hours": None, "sample_size": 0}
                sorted_times = sorted(times)
                avg = sum(times) / len(times)
                median = sorted_times[len(times) // 2]
                return {
                    "average_hours": round(avg, 1),
                    "median_hours": round(median, 1),
                    "min_hours": round(min(times), 1),
                    "max_hours": round(max(times), 1),
                    "sample_size": len(times),
                }
            
            return {
                "research_to_prep": calculate_stats(research_to_prep_times),
                "prep_to_followup": calculate_stats(prep_to_followup_times),
                "confidence": min(1.0, (len(research_to_prep_times) + len(prep_to_followup_times)) / 20),
            }
            
        except Exception as e:
            logger.error(f"Error analyzing step timing: {e}")
            return {
                "research_to_prep": {"average_hours": None, "sample_size": 0},
                "prep_to_followup": {"average_hours": None, "sample_size": 0},
                "confidence": 0.0,
                "error": str(e),
            }
    
    async def analyze_dismiss_patterns(
        self, 
        user_id: str
    ) -> Dict[str, Any]:
        """
        Analyze which suggestion types get dismissed frequently.
        
        This helps reduce the priority of suggestions the user doesn't find helpful.
        
        Returns:
            Dict with dismiss rates per suggestion type.
        """
        try:
            # Get suggestion actions
            result = self.supabase.table("coach_suggestions") \
                .select("suggestion_type, action_taken") \
                .eq("user_id", user_id) \
                .not_.is_("action_taken", "null") \
                .execute()
            
            if not result.data:
                return {
                    "dismiss_rates": {},
                    "confidence": 0.0,
                    "total_actions": 0,
                }
            
            # Count actions per suggestion type
            type_stats = defaultdict(lambda: {"dismissed": 0, "completed": 0, "snoozed": 0, "total": 0})
            
            for suggestion in result.data:
                stype = suggestion.get("suggestion_type", "unknown")
                action = suggestion.get("action_taken", "")
                type_stats[stype]["total"] += 1
                
                if action == "dismissed":
                    type_stats[stype]["dismissed"] += 1
                elif action == "completed":
                    type_stats[stype]["completed"] += 1
                elif action == "snoozed":
                    type_stats[stype]["snoozed"] += 1
            
            # Calculate dismiss rates
            dismiss_rates = {}
            for stype, stats in type_stats.items():
                if stats["total"] > 0:
                    dismiss_rates[stype] = {
                        "dismiss_rate": round(stats["dismissed"] / stats["total"], 2),
                        "complete_rate": round(stats["completed"] / stats["total"], 2),
                        "snooze_rate": round(stats["snoozed"] / stats["total"], 2),
                        "sample_size": stats["total"],
                    }
            
            total_actions = len(result.data)
            confidence = min(1.0, total_actions / 50)
            
            return {
                "dismiss_rates": dismiss_rates,
                "confidence": round(confidence, 2),
                "total_actions": total_actions,
            }
            
        except Exception as e:
            logger.error(f"Error analyzing dismiss patterns: {e}")
            return {
                "dismiss_rates": {},
                "confidence": 0.0,
                "error": str(e),
            }
    
    async def get_priority_adjustments(
        self, 
        user_id: str
    ) -> Dict[str, float]:
        """
        Get priority adjustment factors based on learned patterns.
        
        Returns:
            Dict mapping suggestion types to priority multipliers.
            - 1.0 = no adjustment
            - < 1.0 = reduce priority (user often dismisses)
            - > 1.0 = increase priority (user often completes)
        """
        dismiss_data = await self.analyze_dismiss_patterns(user_id)
        
        adjustments = {}
        
        for stype, stats in dismiss_data.get("dismiss_rates", {}).items():
            sample_size = stats.get("sample_size", 0)
            
            # Only adjust if we have enough data
            if sample_size >= 3:
                dismiss_rate = stats.get("dismiss_rate", 0)
                complete_rate = stats.get("complete_rate", 0)
                
                # Calculate adjustment factor
                # High dismiss rate = lower priority
                # High complete rate = higher priority
                adjustment = 1.0 - (dismiss_rate * 0.3) + (complete_rate * 0.2)
                
                # Clamp between 0.5 and 1.5
                adjustment = max(0.5, min(1.5, adjustment))
                
                adjustments[stype] = round(adjustment, 2)
        
        return adjustments
    
    async def update_user_patterns(
        self, 
        user_id: str, 
        organization_id: str
    ) -> Dict[str, Any]:
        """
        Recalculate and store all patterns for a user.
        
        This should be called periodically (e.g., daily) or after significant activity.
        """
        try:
            # Gather all pattern data
            work_hours = await self.analyze_work_hours(user_id)
            step_timing = await self.analyze_step_timing(user_id, organization_id)
            dismiss_patterns = await self.analyze_dismiss_patterns(user_id)
            priority_adjustments = await self.get_priority_adjustments(user_id)
            
            # Prepare pattern data for storage
            patterns_to_store = [
                {
                    "user_id": user_id,
                    "organization_id": organization_id,
                    "pattern_type": PatternType.WORK_HOURS.value,
                    "pattern_data": work_hours,
                    "confidence": work_hours.get("confidence", 0),
                },
                {
                    "user_id": user_id,
                    "organization_id": organization_id,
                    "pattern_type": PatternType.STEP_TIMING.value,
                    "pattern_data": step_timing,
                    "confidence": step_timing.get("confidence", 0),
                },
                {
                    "user_id": user_id,
                    "organization_id": organization_id,
                    "pattern_type": PatternType.DISMISS_PATTERN.value,
                    "pattern_data": dismiss_patterns,
                    "confidence": dismiss_patterns.get("confidence", 0),
                },
            ]
            
            # Upsert patterns (update if exists, insert if not)
            for pattern in patterns_to_store:
                # Check if pattern exists
                existing = self.supabase.table("coach_user_patterns") \
                    .select("id") \
                    .eq("user_id", user_id) \
                    .eq("pattern_type", pattern["pattern_type"]) \
                    .execute()
                
                if existing.data:
                    # Update existing
                    self.supabase.table("coach_user_patterns") \
                        .update({
                            "pattern_data": pattern["pattern_data"],
                            "confidence": pattern["confidence"],
                            "updated_at": datetime.now().isoformat(),
                        }) \
                        .eq("id", existing.data[0]["id"]) \
                        .execute()
                else:
                    # Insert new
                    self.supabase.table("coach_user_patterns") \
                        .insert(pattern) \
                        .execute()
            
            logger.info(f"Updated patterns for user {user_id}")
            
            return {
                "success": True,
                "patterns_updated": len(patterns_to_store),
                "work_hours_confidence": work_hours.get("confidence", 0),
                "step_timing_confidence": step_timing.get("confidence", 0),
                "dismiss_patterns_confidence": dismiss_patterns.get("confidence", 0),
                "priority_adjustments": priority_adjustments,
            }
            
        except Exception as e:
            logger.error(f"Error updating user patterns: {e}")
            return {
                "success": False,
                "error": str(e),
            }


# =============================================================================
# HELPER FUNCTIONS
# =============================================================================

def should_show_suggestion_now(
    work_hours_pattern: Dict[str, Any],
    suggestion_type: str = None
) -> bool:
    """
    Check if now is a good time to show suggestions based on work hours pattern.
    """
    current_hour = datetime.now().hour
    current_day = datetime.now().weekday()
    
    quiet_hours = work_hours_pattern.get("quiet_hours", [])
    active_days = work_hours_pattern.get("active_days", [0, 1, 2, 3, 4])
    
    # Don't show during quiet hours
    if current_hour in quiet_hours:
        return False
    
    # Don't show on inactive days (unless low confidence)
    confidence = work_hours_pattern.get("confidence", 0)
    if confidence > 0.5 and current_day not in active_days:
        return False
    
    return True


def get_optimal_reminder_time(
    work_hours_pattern: Dict[str, Any]
) -> Optional[int]:
    """
    Get the optimal hour to send a reminder based on work hours pattern.
    """
    peak_hours = work_hours_pattern.get("peak_hours", [10])
    
    if peak_hours:
        # Return the middle of peak hours as optimal time
        return peak_hours[len(peak_hours) // 2]
    
    return 10  # Default to 10 AM

