"""
Settings Router - API endpoints for user settings
"""
from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field
from typing import Optional
from app.deps import get_current_user
from app.database import get_supabase_service
from app.i18n.config import SUPPORTED_LANGUAGES, DEFAULT_LANGUAGE

# Use centralized database module
supabase = get_supabase_service()

router = APIRouter(prefix="/api/v1/settings", tags=["settings"])


# ==========================================
# Pydantic Models
# ==========================================

class UserSettingsResponse(BaseModel):
    """User settings response."""
    app_language: str = Field(default=DEFAULT_LANGUAGE, description="UI language")
    output_language: str = Field(default=DEFAULT_LANGUAGE, description="Default AI output language")
    email_language: str = Field(default=DEFAULT_LANGUAGE, description="Default email generation language")


class UserSettingsUpdateRequest(BaseModel):
    """Request for updating user settings."""
    app_language: Optional[str] = Field(None, description="UI language")
    output_language: Optional[str] = Field(None, description="Default AI output language")
    email_language: Optional[str] = Field(None, description="Default email generation language")


def validate_language(lang: str) -> bool:
    """Validate if language code is supported."""
    return lang in SUPPORTED_LANGUAGES


# ==========================================
# Settings Endpoints
# ==========================================

@router.get("", response_model=UserSettingsResponse)
async def get_settings(
    current_user: dict = Depends(get_current_user)
):
    """
    Get current user's settings.
    
    Returns settings from user_settings table or defaults if not found.
    """
    try:
        user_id = current_user["sub"]
        
        # Try to get existing settings
        result = supabase.table("user_settings").select("*").eq("user_id", user_id).execute()
        
        if result.data and len(result.data) > 0:
            settings = result.data[0]
            return UserSettingsResponse(
                app_language=settings.get("app_language", DEFAULT_LANGUAGE),
                output_language=settings.get("output_language", DEFAULT_LANGUAGE),
                email_language=settings.get("email_language", DEFAULT_LANGUAGE)
            )
        
        # Return defaults if no settings found
        return UserSettingsResponse()
        
    except Exception as e:
        print(f"Error getting settings: {str(e)}")
        # Return defaults on error
        return UserSettingsResponse()


@router.patch("", response_model=UserSettingsResponse)
async def update_settings(
    updates: UserSettingsUpdateRequest,
    current_user: dict = Depends(get_current_user)
):
    """
    Update current user's settings.
    
    Creates settings record if it doesn't exist (upsert).
    """
    try:
        user_id = current_user["sub"]
        
        # Build update data, only including non-None values
        update_data = {}
        
        if updates.app_language is not None:
            if not validate_language(updates.app_language):
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=f"Invalid app_language: {updates.app_language}. Supported: {SUPPORTED_LANGUAGES}"
                )
            update_data["app_language"] = updates.app_language
            
        if updates.output_language is not None:
            if not validate_language(updates.output_language):
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=f"Invalid output_language: {updates.output_language}. Supported: {SUPPORTED_LANGUAGES}"
                )
            update_data["output_language"] = updates.output_language
            
        if updates.email_language is not None:
            if not validate_language(updates.email_language):
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=f"Invalid email_language: {updates.email_language}. Supported: {SUPPORTED_LANGUAGES}"
                )
            update_data["email_language"] = updates.email_language
        
        if not update_data:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="No valid fields to update"
            )
        
        # Check if settings exist
        existing = supabase.table("user_settings").select("id").eq("user_id", user_id).execute()
        
        if existing.data and len(existing.data) > 0:
            # Update existing
            result = supabase.table("user_settings").update(update_data).eq("user_id", user_id).execute()
        else:
            # Insert new with defaults
            insert_data = {
                "user_id": user_id,
                "app_language": update_data.get("app_language", DEFAULT_LANGUAGE),
                "output_language": update_data.get("output_language", DEFAULT_LANGUAGE),
                "email_language": update_data.get("email_language", DEFAULT_LANGUAGE)
            }
            result = supabase.table("user_settings").insert(insert_data).execute()
        
        if result.data and len(result.data) > 0:
            settings = result.data[0]
            return UserSettingsResponse(
                app_language=settings.get("app_language", DEFAULT_LANGUAGE),
                output_language=settings.get("output_language", DEFAULT_LANGUAGE),
                email_language=settings.get("email_language", DEFAULT_LANGUAGE)
            )
        
        # Fetch and return current settings
        return await get_settings(current_user)
        
    except HTTPException:
        raise
    except Exception as e:
        print(f"Error updating settings: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to update settings: {str(e)}"
        )

