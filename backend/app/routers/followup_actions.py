"""
Follow-up Actions Router - API endpoints for modular follow-up actions

Handles on-demand generation, CRUD operations, and action management.
"""

from fastapi import APIRouter, HTTPException, Depends, BackgroundTasks
from typing import Optional, List
from datetime import datetime
import logging
import uuid

from app.deps import get_current_user
from app.database import get_supabase_service
from app.models.followup_actions import (
    ActionType,
    ACTION_TYPE_INFO,
    FollowupActionCreate,
    FollowupActionUpdate,
    FollowupActionResponse,
    FollowupActionsListResponse,
    ActionTypesResponse,
)

# Inngest integration
from app.inngest.events import send_event, use_inngest_for, Events

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/followup", tags=["followup-actions"])


@router.get("/action-types", response_model=ActionTypesResponse)
async def get_action_types(
    locale: str = "en",
    current_user: dict = Depends(get_current_user)
):
    """Get all available action types with localized labels"""
    types = []
    
    for action_type in ActionType:
        info = ACTION_TYPE_INFO.get(action_type, {})
        label_key = f"label_{locale}" if locale in ["en", "nl"] else "label_en"
        desc_key = f"description_{locale}" if locale in ["en", "nl"] else "description_en"
        
        types.append({
            "type": action_type.value,
            "icon": info.get("icon", "📄"),
            "label": info.get(label_key, info.get("label_en", "")),
            "description": info.get(desc_key, info.get("description_en", "")),
        })
    
    return ActionTypesResponse(types=types)


@router.get("/{followup_id}/actions", response_model=FollowupActionsListResponse)
async def list_followup_actions(
    followup_id: str,
    locale: str = "en",
    current_user: dict = Depends(get_current_user)
):
    """List all actions for a follow-up"""
    try:
        user_id = current_user.get("sub")
        supabase = get_supabase_service()
        
        # Verify user owns this followup
        followup_check = supabase.table("followups").select("id").eq("id", followup_id).eq("user_id", user_id).execute()
        if not followup_check.data:
            raise HTTPException(status_code=404, detail="Follow-up not found")
        
        # Get all actions for this followup
        result = supabase.table("followup_actions").select("*").eq("followup_id", followup_id).order("created_at", desc=False).execute()
        
        actions = [
            FollowupActionResponse.from_db(row, locale)
            for row in (result.data or [])
        ]
        
        return FollowupActionsListResponse(actions=actions, count=len(actions))
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error listing followup actions: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/{followup_id}/actions", response_model=FollowupActionResponse)
async def generate_action(
    followup_id: str,
    request: FollowupActionCreate,
    background_tasks: BackgroundTasks,
    locale: str = "en",
    current_user: dict = Depends(get_current_user)
):
    """Generate a new action for a follow-up"""
    try:
        user_id = current_user.get("sub")
        supabase = get_supabase_service()
        
        # Verify user owns this followup and get org_id
        followup_result = supabase.table("followups").select("id, organization_id, transcription_text, executive_summary, prospect_company_name").eq("id", followup_id).eq("user_id", user_id).execute()
        
        if not followup_result.data:
            raise HTTPException(status_code=404, detail="Follow-up not found")
        
        followup = followup_result.data[0]
        organization_id = followup["organization_id"]
        
        # Check credits BEFORE generating (v4: credit-based system)
        from app.services.credit_service import get_credit_service
        credit_service = get_credit_service()
        has_credits, credit_balance = await credit_service.check_credits(
            organization_id=organization_id,
            action="followup_action"
        )
        if not has_credits:
            raise HTTPException(
                status_code=402,
                detail={
                    "error": "insufficient_credits",
                    "message": "Not enough credits for this action",
                    "required": credit_balance.get("required_credits", 2),
                    "available": credit_balance.get("total_credits_available", 0),
                    "upgrade_url": "/pricing"
                }
            )
        
        # Check if action of this type already exists
        existing = supabase.table("followup_actions").select("id").eq("followup_id", followup_id).eq("action_type", request.action_type.value).execute()
        
        if existing.data and not request.regenerate:
            raise HTTPException(
                status_code=400, 
                detail=f"Action of type '{request.action_type.value}' already exists. Set regenerate=true to replace."
            )
        
        # If regenerating, delete existing
        if existing.data and request.regenerate:
            supabase.table("followup_actions").delete().eq("id", existing.data[0]["id"]).execute()
        
        # Get user's OUTPUT language preference (not app_language which is UI language)
        settings_result = supabase.table("user_settings").select("output_language").eq("user_id", user_id).execute()
        language = "en"
        if settings_result.data:
            language = settings_result.data[0].get("output_language", "en")
        
        # Create action record with "generating" state
        action_id = str(uuid.uuid4())
        action_data = {
            "id": action_id,
            "followup_id": followup_id,
            "organization_id": organization_id,
            "user_id": user_id,
            "action_type": request.action_type.value,
            "content": None,  # Will be filled by background task
            "metadata": {"status": "generating"},
            "language": language,
        }
        
        insert_result = supabase.table("followup_actions").insert(action_data).execute()
        
        if not insert_result.data:
            raise HTTPException(status_code=500, detail="Failed to create action")
        
        # Trigger generation via Inngest (if enabled) or BackgroundTasks (fallback)
        use_inngest = use_inngest_for("followup_actions")
        logger.info(f"Action {action_id}: use_inngest={use_inngest}")
        
        if use_inngest:
            event_sent = await send_event(
                Events.FOLLOWUP_ACTION_REQUESTED,
                {
                    "action_id": action_id,
                    "followup_id": followup_id,
                    "action_type": request.action_type.value,
                    "user_id": user_id,
                    "language": language
                },
                user={"id": user_id}
            )
            
            if event_sent:
                logger.info(f"Action {action_id} triggered via Inngest (event: {Events.FOLLOWUP_ACTION_REQUESTED})")
            else:
                # Fallback to BackgroundTasks if Inngest fails
                logger.warning(f"Action {action_id}: Inngest event failed, falling back to BackgroundTasks")
                background_tasks.add_task(
                    generate_action_content,
                    action_id=action_id,
                    followup_id=followup_id,
                    action_type=request.action_type,
                    user_id=user_id,
                    language=language,
                )
        else:
            # Use BackgroundTasks (legacy/fallback)
            logger.info(f"Action {action_id}: Using BackgroundTasks (Inngest disabled for followup_actions)")
            background_tasks.add_task(
                generate_action_content,
                action_id=action_id,
                followup_id=followup_id,
                action_type=request.action_type,
                user_id=user_id,
                language=language,
            )
        
        return FollowupActionResponse.from_db(insert_result.data[0], locale)
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error generating action: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/{followup_id}/actions/{action_id}", response_model=FollowupActionResponse)
async def get_action(
    followup_id: str,
    action_id: str,
    locale: str = "en",
    current_user: dict = Depends(get_current_user)
):
    """Get a specific action"""
    try:
        user_id = current_user.get("sub")
        supabase = get_supabase_service()
        
        result = supabase.table("followup_actions").select("*").eq("id", action_id).eq("followup_id", followup_id).eq("user_id", user_id).execute()
        
        if not result.data:
            raise HTTPException(status_code=404, detail="Action not found")
        
        return FollowupActionResponse.from_db(result.data[0], locale)
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting action: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.patch("/{followup_id}/actions/{action_id}", response_model=FollowupActionResponse)
async def update_action(
    followup_id: str,
    action_id: str,
    request: FollowupActionUpdate,
    locale: str = "en",
    current_user: dict = Depends(get_current_user)
):
    """Update an action (edit content)"""
    try:
        user_id = current_user.get("sub")
        supabase = get_supabase_service()
        
        # Verify ownership
        existing = supabase.table("followup_actions").select("id").eq("id", action_id).eq("followup_id", followup_id).eq("user_id", user_id).execute()
        
        if not existing.data:
            raise HTTPException(status_code=404, detail="Action not found")
        
        # Build update data
        update_data = {}
        if request.content is not None:
            update_data["content"] = request.content
        if request.metadata is not None:
            update_data["metadata"] = request.metadata
        
        if not update_data:
            raise HTTPException(status_code=400, detail="No fields to update")
        
        # Update
        result = supabase.table("followup_actions").update(update_data).eq("id", action_id).execute()
        
        if not result.data:
            raise HTTPException(status_code=500, detail="Failed to update action")
        
        return FollowupActionResponse.from_db(result.data[0], locale)
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error updating action: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.delete("/{followup_id}/actions/{action_id}")
async def delete_action(
    followup_id: str,
    action_id: str,
    current_user: dict = Depends(get_current_user)
):
    """Delete an action"""
    try:
        user_id = current_user.get("sub")
        supabase = get_supabase_service()
        
        # Verify ownership
        existing = supabase.table("followup_actions").select("id").eq("id", action_id).eq("followup_id", followup_id).eq("user_id", user_id).execute()
        
        if not existing.data:
            raise HTTPException(status_code=404, detail="Action not found")
        
        # Delete
        supabase.table("followup_actions").delete().eq("id", action_id).execute()
        
        return {"success": True, "message": "Action deleted"}
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error deleting action: {e}")
        raise HTTPException(status_code=500, detail=str(e))


async def generate_action_content(
    action_id: str,
    followup_id: str,
    action_type: ActionType,
    user_id: str,
    language: str,
):
    """Background task to generate action content using Claude"""
    try:
        # Import here to avoid circular imports
        from app.services.action_generator import ActionGeneratorService
        from app.services.credit_service import get_credit_service
        from app.services.api_usage_service import get_api_usage_service
        
        supabase = get_supabase_service()
        
        # Get organization_id from followup
        followup_result = supabase.table("followups").select("organization_id").eq("id", followup_id).single().execute()
        organization_id = followup_result.data.get("organization_id") if followup_result.data else None
        
        generator = ActionGeneratorService()
        
        # Generate content
        content, metadata = await generator.generate(
            action_id=action_id,
            followup_id=followup_id,
            action_type=action_type,
            user_id=user_id,
            language=language,
        )
        
        # Update action with generated content
        supabase.table("followup_actions").update({
            "content": content,
            "metadata": metadata,
        }).eq("id", action_id).execute()
        
        # Log API usage and consume credits (if org_id available)
        if organization_id:
            try:
                credit_service = get_credit_service()
                await credit_service.consume_credits(
                    organization_id=organization_id,
                    action="followup_action",
                    user_id=user_id,
                    metadata={"action_id": action_id, "action_type": action_type.value}
                )
            except Exception as credit_err:
                logger.warning(f"Credit consumption failed: {credit_err}")
            
            # Log actual token usage from metadata
            token_stats = metadata.get("token_stats", {})
            if token_stats:
                try:
                    usage_service = get_api_usage_service()
                    await usage_service.log_llm_usage(
                        organization_id=organization_id,
                        provider="anthropic",
                        model="claude-sonnet-4-20250514",
                        input_tokens=token_stats.get("input_tokens", 0),
                        output_tokens=token_stats.get("output_tokens", 0),
                        user_id=user_id,
                        service=f"followup_action_{action_type.value}",
                        credits_consumed=0,
                        metadata={"action_id": action_id, "followup_id": followup_id}
                    )
                except Exception as usage_err:
                    logger.warning(f"API usage logging failed: {usage_err}")
        
        logger.info(f"Generated {action_type.value} for followup {followup_id}")
        
    except Exception as e:
        logger.error(f"Error generating action content: {e}")
        
        # Update action with error state
        try:
            supabase = get_supabase_service()
            supabase.table("followup_actions").update({
                "metadata": {"status": "error", "error": str(e)},
            }).eq("id", action_id).execute()
        except:
            pass

