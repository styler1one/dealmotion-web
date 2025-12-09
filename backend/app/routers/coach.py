"""
AI Sales Coach "Luna" - API Router
TASK-029 / SPEC-028

Endpoints for the AI Sales Coach widget.
"""

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from typing import Optional, List
from datetime import datetime, timedelta
import logging
import uuid
from slowapi import Limiter
from slowapi.util import get_remote_address

from app.deps import get_current_user
from app.database import get_supabase_service

# Rate limiter
limiter = Limiter(key_func=get_remote_address)
from app.models.coach import (
    CoachSettings,
    CoachSettingsUpdate,
    BehaviorEventCreate,
    BehaviorEvent,
    Suggestion,
    SuggestionActionRequest,
    SuggestionsResponse,
    PatternsResponse,
    CoachStatsResponse,
    TodayStats,
    UserContext,
)
from app.services.coach_rules import rule_engine, build_user_context

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1/coach", tags=["coach"])


# =============================================================================
# SETTINGS ENDPOINTS
# =============================================================================

@router.get("/settings", response_model=CoachSettings)
async def get_settings(current_user: dict = Depends(get_current_user)):
    """Get the current user's coach settings."""
    supabase = get_supabase_service()
    user_id = current_user["sub"]
    
    try:
        result = supabase.table("coach_settings") \
            .select("*") \
            .eq("user_id", user_id) \
            .execute()
        
        if result.data:
            settings_data = result.data[0]
            return CoachSettings(**settings_data)
        
        # Create default settings if not exist
        org_result = supabase.table("organization_members") \
            .select("organization_id") \
            .eq("user_id", user_id) \
            .execute()
        
        if not org_result.data:
            # Return default settings for users without organization
            return CoachSettings(
                id=str(uuid.uuid4()),
                user_id=user_id,
                is_enabled=True,
                show_inline_tips=True,
                show_completion_modals=True,
                notification_frequency="normal",
                widget_state="minimized",
                dismissed_tip_ids=[],
                created_at=datetime.now(),
                updated_at=datetime.now(),
            )
        
        new_settings = {
            "user_id": user_id,
            "is_enabled": True,
            "show_inline_tips": True,
            "show_completion_modals": True,
            "notification_frequency": "normal",
            "widget_state": "minimized",
            "dismissed_tip_ids": [],
        }
        
        insert_result = supabase.table("coach_settings") \
            .insert(new_settings) \
            .execute()
        
        if insert_result.data:
            return CoachSettings(**insert_result.data[0])
        
        raise HTTPException(status_code=500, detail="Failed to create settings")
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting coach settings: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.patch("/settings", response_model=CoachSettings)
async def update_settings(
    updates: CoachSettingsUpdate,
    current_user: dict = Depends(get_current_user)
):
    """Update the current user's coach settings."""
    supabase = get_supabase_service()
    user_id = current_user["sub"]
    
    # Debug: log what we received
    
    try:
        # Check if settings exist
        existing_result = supabase.table("coach_settings") \
            .select("*") \
            .eq("user_id", user_id) \
            .execute()
        
        # Build update data (only non-None values)
        update_data = {k: v for k, v in updates.model_dump().items() if v is not None}
        
        if existing_result.data:
            # Update existing settings
            update_data["updated_at"] = datetime.now().isoformat()
            result = supabase.table("coach_settings") \
                .update(update_data) \
                .eq("user_id", user_id) \
                .execute()
        else:
            # Create new settings (upsert)
            update_data["user_id"] = user_id
            update_data["created_at"] = datetime.now().isoformat()
            update_data["updated_at"] = datetime.now().isoformat()
            # Set defaults for required fields if not provided
            update_data.setdefault("is_enabled", True)
            update_data.setdefault("show_inline_tips", True)
            update_data.setdefault("show_completion_modals", True)
            update_data.setdefault("notification_frequency", "normal")
            update_data.setdefault("widget_state", "minimized")
            update_data.setdefault("dismissed_tip_ids", [])
            
            result = supabase.table("coach_settings") \
                .insert(update_data) \
                .execute()
        
        if result.data:
            return CoachSettings(**result.data[0])
        
        raise HTTPException(status_code=500, detail="Failed to update settings")
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error updating coach settings: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# =============================================================================
# SUGGESTIONS ENDPOINTS
# =============================================================================

@router.get("/suggestions", response_model=SuggestionsResponse)
async def get_suggestions(
    limit: int = Query(10, ge=1, le=50),
    current_user: dict = Depends(get_current_user)
):
    """Get prioritized suggestions for the current user."""
    supabase = get_supabase_service()
    user_id = current_user["sub"]
    
    try:
        # Collect ALL organization IDs the user belongs to
        # Get organization from organization_members (single source of truth)
        organization_ids = []
        primary_org_id = None
        
        # 1. Check JWT token first
        jwt_org_id = current_user.get("organization_id")
        if jwt_org_id:
            organization_ids.append(jwt_org_id)
            primary_org_id = jwt_org_id
        
        # 2. Get from organization_members (primary source)
        org_members_result = supabase.table("organization_members") \
            .select("organization_id") \
            .eq("user_id", user_id) \
            .execute()
        
        if org_members_result.data:
            for member in org_members_result.data:
                member_org_id = member["organization_id"]
                if member_org_id not in organization_ids:
                    organization_ids.append(member_org_id)
                if not primary_org_id:
                    primary_org_id = member_org_id
        
        # New user without organization - return onboarding suggestions
        if not primary_org_id or len(organization_ids) == 0:
            logger.info(f"User {user_id} has no organization - returning onboarding suggestions")
            # Return basic profile completion suggestions
            from app.models.coach import SuggestionType
            onboarding_suggestion = Suggestion(
                id=str(uuid.uuid4()),
                user_id=user_id,
                organization_id="",
                suggestion_type=SuggestionType.COMPLETE_PROFILE,
                title="Complete your profile",
                description="Set up your sales profile and company to get started with personalized AI assistance.",
                reason="New account setup",
                priority=95,
                action_route="/onboarding",
                action_label="Start Setup",
                icon="🚀",
                related_entity_type=None,
                related_entity_id=None,
                shown_at=datetime.now(),
                expires_at=None,
                action_taken=None,
                action_taken_at=None,
                snooze_until=None,
                feedback_rating=None,
            )
            return SuggestionsResponse(
                suggestions=[onboarding_suggestion],
                count=1,
                has_priority=True,
            )
        
        
        # First, check for existing suggestions (snoozed or pending)
        now = datetime.now()
        existing_result = supabase.table("coach_suggestions") \
            .select("*") \
            .eq("user_id", user_id) \
            .is_("action_taken", "null") \
            .execute()
        
        # Also get snoozed suggestions that haven't expired
        snoozed_result = supabase.table("coach_suggestions") \
            .select("*") \
            .eq("user_id", user_id) \
            .eq("action_taken", "snoozed") \
            .execute()
        
        # Collect snoozed suggestion types and entity IDs that are still active
        snoozed_keys = set()
        for s in (snoozed_result.data or []):
            snooze_until_str = s.get("snooze_until")
            if snooze_until_str:
                try:
                    snooze_until = datetime.fromisoformat(snooze_until_str.replace("Z", "+00:00"))
                    # Make both datetimes timezone-naive for comparison
                    snooze_until_naive = snooze_until.replace(tzinfo=None)
                    if snooze_until_naive > now:
                        # Still snoozed - add to blocked set
                        stype = s.get("suggestion_type", "")
                        entity_id = s.get("related_entity_id", "")
                        snoozed_keys.add(f"{stype}:{entity_id}")
                except Exception as e:
                    logger.warning(f"Error parsing snooze_until: {e}")
        
        # Build user context - pass all organization IDs
        context = await build_user_context(supabase, user_id, organization_ids)
        
        # Evaluate rules to get suggestions
        suggestions = rule_engine.evaluate_all(context)
        
        # Filter out snoozed suggestions
        if snoozed_keys:
            original_count = len(suggestions)
            suggestions = [
                s for s in suggestions
                if f"{s.suggestion_type.value}:{s.related_entity_id or ''}" not in snoozed_keys
            ]
        
        # Apply pattern-based adjustments
        if context.patterns:
            suggestions = [
                rule_engine.adjust_priority_with_patterns(s, context.patterns)
                for s in suggestions
            ]
            # Re-sort after adjustments
            suggestions.sort(key=lambda s: s.priority, reverse=True)
        
        # Limit results
        suggestions = suggestions[:limit]
        
        # Convert to response format
        response_suggestions = []
        for i, suggestion in enumerate(suggestions):
            # Check if we already have a pending suggestion for this type/entity
            existing_key = f"{suggestion.suggestion_type.value}:{suggestion.related_entity_id or ''}"
            existing = None
            for e in (existing_result.data or []):
                e_key = f"{e.get('suggestion_type', '')}:{e.get('related_entity_id', '') or ''}"
                if e_key == existing_key:
                    existing = e
                    break
            
            if existing:
                # Use existing suggestion
                db_suggestion = existing
            else:
                # Create a Suggestion record in the database (for tracking)
                suggestion_data = {
                    "user_id": user_id,
                    "organization_id": primary_org_id,
                    "suggestion_type": suggestion.suggestion_type.value,
                    "suggestion_data": {
                        "title": suggestion.title,
                        "description": suggestion.description,
                        "reason": suggestion.reason,
                        "action_route": suggestion.action_route,
                        "action_label": suggestion.action_label,
                        "icon": suggestion.icon,
                    },
                    "priority": suggestion.priority,
                    "related_entity_type": suggestion.related_entity_type.value if suggestion.related_entity_type else None,
                    "related_entity_id": suggestion.related_entity_id,
                    "shown_at": datetime.now().isoformat(),
                }
                
                insert_result = supabase.table("coach_suggestions") \
                    .insert(suggestion_data) \
                    .execute()
                
                if not insert_result.data:
                    continue
                    
                db_suggestion = insert_result.data[0]
            
            # Parse snooze_until if present
            snooze_until_val = None
            if db_suggestion.get("snooze_until"):
                try:
                    snooze_until_val = datetime.fromisoformat(db_suggestion["snooze_until"].replace("Z", "+00:00"))
                except:
                    pass
            
            response_suggestions.append(Suggestion(
                id=db_suggestion["id"],
                user_id=user_id,
                organization_id=primary_org_id,
                suggestion_type=suggestion.suggestion_type,
                title=suggestion.title,
                description=suggestion.description,
                reason=suggestion.reason,
                priority=suggestion.priority,
                action_route=suggestion.action_route,
                action_label=suggestion.action_label,
                icon=suggestion.icon,
                related_entity_type=suggestion.related_entity_type,
                related_entity_id=suggestion.related_entity_id,
                shown_at=datetime.fromisoformat(db_suggestion["shown_at"].replace("Z", "+00:00")) if db_suggestion.get("shown_at") else datetime.now(),
                expires_at=None,
                action_taken=db_suggestion.get("action_taken"),
                action_taken_at=datetime.fromisoformat(db_suggestion["action_taken_at"].replace("Z", "+00:00")) if db_suggestion.get("action_taken_at") else None,
                snooze_until=snooze_until_val,
                feedback_rating=db_suggestion.get("feedback_rating"),
            ))
        
        return SuggestionsResponse(
            suggestions=response_suggestions,
            count=len(response_suggestions),
            has_priority=any(s.priority >= 80 for s in suggestions),
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting suggestions: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/suggestions/{suggestion_id}/action")
async def record_suggestion_action(
    suggestion_id: str,
    action_request: SuggestionActionRequest,
    current_user: dict = Depends(get_current_user)
):
    """Record user action on a suggestion (clicked, dismissed, snoozed)."""
    supabase = get_supabase_service()
    user_id = current_user["sub"]
    
    try:
        # Verify ownership
        check_result = supabase.table("coach_suggestions") \
            .select("id") \
            .eq("id", suggestion_id) \
            .eq("user_id", user_id) \
            .execute()
        
        if not check_result.data:
            raise HTTPException(status_code=404, detail="Suggestion not found")
        
        # Update the suggestion
        update_data = {
            "action_taken": action_request.action.value,
            "action_taken_at": datetime.now().isoformat(),
        }
        
        if action_request.snooze_until:
            update_data["snooze_until"] = action_request.snooze_until.isoformat()
        
        if action_request.feedback_rating:
            update_data["feedback_rating"] = action_request.feedback_rating
        
        result = supabase.table("coach_suggestions") \
            .update(update_data) \
            .eq("id", suggestion_id) \
            .execute()
        
        if not result.data:
            raise HTTPException(status_code=500, detail="Failed to update suggestion")
        
        # Also record as behavior event for pattern learning
        org_result = supabase.table("organization_members") \
            .select("organization_id") \
            .eq("user_id", user_id) \
            .execute()
        
        if org_result.data:
            event_type = f"suggestion_{action_request.action.value}"
            supabase.table("coach_behavior_events").insert({
                "user_id": user_id,
                "organization_id": org_result.data[0]["organization_id"],
                "event_type": event_type,
                "event_data": {"suggestion_id": suggestion_id},
            }).execute()
        
        return {"success": True, "action": action_request.action.value}
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error recording action: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/suggestions/reset")
async def reset_snoozed_suggestions(
    current_user: dict = Depends(get_current_user)
):
    """Reset all snoozed suggestions AND enable coach for the current user."""
    supabase = get_supabase_service()
    user_id = current_user["sub"]
    
    try:
        # 1. Clear snooze_until and action_taken for all snoozed suggestions
        result = supabase.table("coach_suggestions") \
            .update({
                "action_taken": None,
                "action_taken_at": None,
                "snooze_until": None,
            }) \
            .eq("user_id", user_id) \
            .eq("action_taken", "snoozed") \
            .execute()
        
        reset_count = len(result.data) if result.data else 0
        logger.info(f"Reset {reset_count} snoozed suggestions for user {user_id}")
        
        # 2. Force enable the coach and set widget to minimized
        settings_result = supabase.table("coach_settings") \
            .update({
                "is_enabled": True,
                "widget_state": "minimized",
                "updated_at": datetime.now().isoformat(),
            }) \
            .eq("user_id", user_id) \
            .execute()
        
        if settings_result.data:
            logger.info(f"Enabled coach for user {user_id}: is_enabled=True, widget_state=minimized")
        else:
            # Create new settings if they don't exist
            supabase.table("coach_settings") \
                .insert({
                    "user_id": user_id,
                    "is_enabled": True,
                    "widget_state": "minimized",
                    "show_inline_tips": True,
                    "show_completion_modals": True,
                    "notification_frequency": "normal",
                    "dismissed_tip_ids": [],
                }) \
                .execute()
            logger.info(f"Created new enabled coach settings for user {user_id}")
        
        return {"success": True, "reset_count": reset_count, "coach_enabled": True}
        
    except Exception as e:
        logger.error(f"Error resetting suggestions: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/suggestions/cleanup")
async def cleanup_orphaned_suggestions(
    current_user: dict = Depends(get_current_user)
):
    """
    Clean up orphaned suggestions for the current user.
    
    Removes suggestions that reference deleted entities (research, preps, followups).
    This is called automatically when entities are deleted, but can also be
    triggered manually to clean up any orphans.
    """
    from app.services.coach_cleanup import cleanup_orphaned_suggestions as do_cleanup
    
    supabase = get_supabase_service()
    user_id = current_user["sub"]
    
    try:
        stats = await do_cleanup(supabase, user_id)
        
        return {
            "success": True,
            "cleaned": stats["total_cleaned"],
            "details": stats,
        }
        
    except Exception as e:
        logger.error(f"Error cleaning orphaned suggestions: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# =============================================================================
# BEHAVIOR EVENTS ENDPOINTS
# =============================================================================

@router.post("/events")
async def record_event(
    event: BehaviorEventCreate,
    current_user: dict = Depends(get_current_user)
):
    """Record a behavior event for pattern learning."""
    supabase = get_supabase_service()
    user_id = current_user["sub"]
    
    try:
        # Get organization ID
        org_result = supabase.table("organization_members") \
            .select("organization_id") \
            .eq("user_id", user_id) \
            .execute()
        
        # Silently skip if user has no organization (new users)
        if not org_result.data:
            return {"success": True, "event_id": None, "message": "Skipped - no organization"}
        
        event_data = {
            "user_id": user_id,
            "organization_id": org_result.data[0]["organization_id"],
            "event_type": event.event_type.value,
            "event_data": event.event_data,
            "page_context": event.page_context,
        }
        
        result = supabase.table("coach_behavior_events") \
            .insert(event_data) \
            .execute()
        
        if result.data:
            return {"success": True, "event_id": result.data[0]["id"]}
        
        raise HTTPException(status_code=500, detail="Failed to record event")
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error recording event: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# =============================================================================
# PATTERNS ENDPOINTS
# =============================================================================

@router.get("/patterns", response_model=PatternsResponse)
async def get_patterns(current_user: dict = Depends(get_current_user)):
    """Get learned patterns for the current user."""
    supabase = get_supabase_service()
    user_id = current_user["sub"]
    
    try:
        result = supabase.table("coach_user_patterns") \
            .select("*") \
            .eq("user_id", user_id) \
            .execute()
        
        return PatternsResponse(patterns=result.data or [])
        
    except Exception as e:
        logger.error(f"Error getting patterns: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# =============================================================================
# STATS ENDPOINTS
# =============================================================================

@router.get("/stats", response_model=CoachStatsResponse)
async def get_stats(current_user: dict = Depends(get_current_user)):
    """Get today's progress stats for the current user."""
    supabase = get_supabase_service()
    user_id = current_user["sub"]
    
    try:
        # Get organization ID
        org_result = supabase.table("organization_members") \
            .select("organization_id") \
            .eq("user_id", user_id) \
            .execute()
        
        # Return empty stats for users without organization
        if not org_result.data:
            return CoachStatsResponse(
                today=TodayStats(),
                suggestions_pending=0,
                patterns_learned=0,
            )
        
        organization_id = org_result.data[0]["organization_id"]
        today_start = datetime.now().replace(hour=0, minute=0, second=0, microsecond=0).isoformat()
        
        stats = TodayStats()
        
        # Count research completed today
        research_result = supabase.table("research_briefs") \
            .select("id", count="exact") \
            .eq("organization_id", organization_id) \
            .eq("status", "completed") \
            .gte("completed_at", today_start) \
            .execute()
        stats.research_completed = research_result.count or 0
        
        # Count preps completed today
        preps_result = supabase.table("meeting_preps") \
            .select("id", count="exact") \
            .eq("organization_id", organization_id) \
            .eq("status", "completed") \
            .gte("completed_at", today_start) \
            .execute()
        stats.preps_completed = preps_result.count or 0
        
        # Count follow-ups completed today
        followups_result = supabase.table("followups") \
            .select("id", count="exact") \
            .eq("organization_id", organization_id) \
            .eq("status", "completed") \
            .gte("completed_at", today_start) \
            .execute()
        stats.followups_completed = followups_result.count or 0
        
        # Count actions generated today
        actions_result = supabase.table("followup_actions") \
            .select("id", count="exact") \
            .eq("organization_id", organization_id) \
            .gte("created_at", today_start) \
            .execute()
        stats.actions_generated = actions_result.count or 0
        
        stats.total_completed = (
            stats.research_completed + 
            stats.preps_completed + 
            stats.followups_completed + 
            stats.actions_generated
        )
        
        # Count pending suggestions
        suggestions_result = supabase.table("coach_suggestions") \
            .select("id", count="exact") \
            .eq("user_id", user_id) \
            .is_("action_taken", "null") \
            .execute()
        
        # Count learned patterns
        patterns_result = supabase.table("coach_user_patterns") \
            .select("id", count="exact") \
            .eq("user_id", user_id) \
            .execute()
        
        return CoachStatsResponse(
            today=stats,
            suggestions_pending=suggestions_result.count or 0,
            patterns_learned=patterns_result.count or 0,
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting stats: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# =============================================================================
# INLINE SUGGESTIONS ENDPOINT
# =============================================================================

@router.get("/suggestions/inline")
async def get_inline_suggestions(
    page: str = Query(..., description="Current page context"),
    current_user: dict = Depends(get_current_user)
):
    """Get contextual inline suggestions for a specific page."""
    supabase = get_supabase_service()
    user_id = current_user["sub"]
    
    try:
        # Check if user has inline tips enabled
        settings_result = supabase.table("coach_settings") \
            .select("show_inline_tips, dismissed_tip_ids") \
            .eq("user_id", user_id) \
            .execute()
        
        if settings_result.data:
            settings = settings_result.data[0]
            if not settings.get("show_inline_tips", True):
                return {"suggestions": [], "count": 0}
        
        # Page-specific inline tips
        inline_tips = {
            "/dashboard/research": [
                {
                    "id": "research-tip-1",
                    "title": "Add contacts after research",
                    "description": "Adding contacts helps personalize your meeting preparation",
                    "icon": "💡",
                }
            ],
            "/dashboard/preparation": [
                {
                    "id": "prep-tip-1",
                    "title": "Include custom notes",
                    "description": "Preps with custom notes generate 30% better results",
                    "icon": "📝",
                }
            ],
            "/dashboard/followup": [
                {
                    "id": "followup-tip-1",
                    "title": "Generate a Customer Report",
                    "description": "Share professional reports with your prospects",
                    "icon": "📄",
                }
            ],
        }
        
        # Get tips for current page
        page_tips = inline_tips.get(page, [])
        
        # Filter out dismissed tips
        if settings_result.data:
            dismissed = settings_result.data[0].get("dismissed_tip_ids", [])
            page_tips = [t for t in page_tips if t["id"] not in dismissed]
        
        return {"suggestions": page_tips, "count": len(page_tips)}
        
    except Exception as e:
        logger.error(f"Error getting inline suggestions: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# =============================================================================
# AI INSIGHTS ENDPOINTS
# =============================================================================

@router.get("/insights/tip")
@limiter.limit("30/minute")
async def get_tip_of_day(
    request: Request, 
    current_user: dict = Depends(get_current_user),
    force_ai: bool = False
):
    """
    Get the tip of the day.
    
    TASK-038: Token optimization - AI tips cached 1x per day.
    - Default: Returns curated tip (no AI tokens)
    - force_ai=true: Generates new AI tip (uses tokens, cached for day)
    
    Rate limited to 30/minute.
    """
    from app.services.coach_insights import CoachInsightsService, get_user_activity_context
    
    supabase = get_supabase_service()
    user_id = current_user["sub"]
    
    try:
        # Get organization IDs from organization_members (single source of truth)
        organization_ids = []
        
        org_members = supabase.table("organization_members") \
            .select("organization_id") \
            .eq("user_id", user_id) \
            .execute()
        for member in (org_members.data or []):
            if member["organization_id"] not in organization_ids:
                organization_ids.append(member["organization_id"])
        
        # Get user activity context (includes seller context)
        context = await get_user_activity_context(supabase, user_id, organization_ids)
        
        # Generate tip (cached or curated, AI only if force_ai=true)
        insights_service = CoachInsightsService(supabase)
        tip = await insights_service.generate_tip_of_day(user_id, context, force_ai=force_ai)
        
        return tip
        
    except Exception as e:
        logger.error(f"Error getting tip of day: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/insights/patterns")
@limiter.limit("30/minute")
async def get_success_patterns(request: Request, current_user: dict = Depends(get_current_user)):
    """Get success pattern analysis for the organization. Rate limited to 30/minute."""
    from app.services.coach_insights import CoachInsightsService
    
    supabase = get_supabase_service()
    user_id = current_user["sub"]
    
    try:
        # Get primary organization ID from organization_members (single source of truth)
        organization_id = None
        
        org_members = supabase.table("organization_members") \
            .select("organization_id") \
            .eq("user_id", user_id) \
            .limit(1) \
            .execute()
        if org_members.data:
            organization_id = org_members.data[0]["organization_id"]
        
        if not organization_id:
            return {"patterns": {}, "score": 0, "recommendations": []}
        
        # Analyze patterns
        insights_service = CoachInsightsService(supabase)
        patterns = await insights_service.analyze_success_patterns(organization_id)
        
        return {
            "patterns": {
                "contacts": patterns.get("contacts_analysis", {}),
                "timing": patterns.get("timing_analysis", {}),
                "actions": patterns.get("action_analysis", {}),
            },
            "score": patterns.get("overall_score", 0),
            "recommendations": patterns.get("recommendations", []),
        }
        
    except Exception as e:
        logger.error(f"Error getting success patterns: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/insights/predictions")
@limiter.limit("30/minute")
async def get_predictions(request: Request, current_user: dict = Depends(get_current_user)):
    """Get predictive suggestions based on patterns and timing. Rate limited to 30/minute."""
    from app.services.coach_insights import CoachInsightsService
    
    supabase = get_supabase_service()
    user_id = current_user["sub"]
    
    try:
        # Get organization IDs from organization_members (single source of truth)
        organization_ids = []
        
        org_members = supabase.table("organization_members") \
            .select("organization_id") \
            .eq("user_id", user_id) \
            .execute()
        for member in (org_members.data or []):
            if member["organization_id"] not in organization_ids:
                organization_ids.append(member["organization_id"])
        
        if not organization_ids:
            return {"predictions": [], "count": 0}
        
        # Get predictions
        insights_service = CoachInsightsService(supabase)
        predictions = await insights_service.get_predictive_suggestions(
            user_id, 
            organization_ids
        )
        
        return {"predictions": predictions, "count": len(predictions)}
        
    except Exception as e:
        logger.error(f"Error getting predictions: {e}")
        raise HTTPException(status_code=500, detail=str(e))

