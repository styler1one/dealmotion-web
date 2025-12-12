"""
Calendar Router - API endpoints for calendar integration
SPEC-038: Meetings & Calendar Integration
"""
from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field
from typing import Optional, List
from datetime import datetime
import logging

from app.deps import get_current_user, get_user_org
from app.database import get_supabase_service
from app.services.google_calendar import google_calendar_service
from app.services.microsoft_calendar import microsoft_calendar_service
from app.services.calendar_sync import calendar_sync_service
from app.inngest.events import send_event, Events
from typing import Tuple

# Use centralized database module
supabase = get_supabase_service()

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1/calendar", tags=["calendar"])


# ==========================================
# Pydantic Models
# ==========================================

class CalendarProviderStatus(BaseModel):
    """Status of a single calendar provider connection."""
    connected: bool = Field(description="Whether the provider is connected")
    email: Optional[str] = Field(None, description="Connected account email")
    last_sync: Optional[datetime] = Field(None, description="Last successful sync time")
    last_sync_status: Optional[str] = Field(None, description="Status of last sync: success, failed, partial")
    meeting_count: int = Field(default=0, description="Number of synced meetings")
    needs_reauth: bool = Field(default=False, description="Whether reconnection is required")
    sync_enabled: bool = Field(default=True, description="Whether sync is enabled")


class CalendarStatusResponse(BaseModel):
    """Response for calendar connection status."""
    google: CalendarProviderStatus
    microsoft: CalendarProviderStatus


class CalendarAuthUrlResponse(BaseModel):
    """Response containing OAuth authorization URL."""
    auth_url: str = Field(description="URL to redirect user for OAuth")
    state: str = Field(description="State parameter for CSRF protection")


class CalendarCallbackRequest(BaseModel):
    """Request for processing OAuth callback."""
    code: str = Field(description="Authorization code from OAuth provider")
    state: str = Field(description="State parameter for verification")


class CalendarCallbackResponse(BaseModel):
    """Response after successful OAuth callback."""
    success: bool
    email: Optional[str] = Field(None, description="Connected account email")
    provider: str = Field(description="Provider that was connected")


class CalendarSyncResponse(BaseModel):
    """Response after manual calendar sync."""
    synced_meetings: int = Field(description="Total meetings after sync")
    new_meetings: int = Field(description="New meetings added")
    updated_meetings: int = Field(description="Existing meetings updated")
    deleted_meetings: int = Field(description="Meetings removed (cancelled)")


class CalendarDisconnectResponse(BaseModel):
    """Response after disconnecting a calendar."""
    success: bool
    provider: str


# ==========================================
# Helper Functions
# ==========================================

async def get_provider_status(
    user_id: str, 
    organization_id: str, 
    provider: str
) -> CalendarProviderStatus:
    """Get connection status for a specific provider."""
    try:
        # Get connection record
        result = supabase.table("calendar_connections").select(
            "id, email, last_sync_at, last_sync_status, needs_reauth, sync_enabled"
        ).eq("user_id", user_id).eq("provider", provider).execute()
        
        if not result.data or len(result.data) == 0:
            return CalendarProviderStatus(connected=False)
        
        connection = result.data[0]
        
        # Count meetings for this connection
        meetings_result = supabase.table("calendar_meetings").select(
            "id", count="exact"
        ).eq("calendar_connection_id", connection["id"]).eq(
            "status", "confirmed"
        ).execute()
        
        meeting_count = meetings_result.count if meetings_result.count else 0
        
        return CalendarProviderStatus(
            connected=True,
            email=connection.get("email"),
            last_sync=connection.get("last_sync_at"),
            last_sync_status=connection.get("last_sync_status"),
            meeting_count=meeting_count,
            needs_reauth=connection.get("needs_reauth", False),
            sync_enabled=connection.get("sync_enabled", True)
        )
        
    except Exception as e:
        logger.error(f"Error getting provider status for {provider}: {str(e)}")
        return CalendarProviderStatus(connected=False)


# ==========================================
# Calendar Status Endpoints
# ==========================================

@router.get("/status", response_model=CalendarStatusResponse)
async def get_calendar_status(
    user_org: Tuple[str, str] = Depends(get_user_org)
):
    """
    Get status of all calendar connections for the current user.
    
    Returns connection status for Google and Microsoft calendars,
    including sync status and meeting counts.
    """
    user_id, organization_id = user_org
    
    # Get status for each provider in parallel (could optimize with asyncio.gather)
    google_status = await get_provider_status(user_id, organization_id, "google")
    microsoft_status = await get_provider_status(user_id, organization_id, "microsoft")
    
    return CalendarStatusResponse(
        google=google_status,
        microsoft=microsoft_status
    )


# ==========================================
# OAuth Endpoints (Placeholder - to be implemented in Sprint 1.5-1.7)
# ==========================================

@router.get("/auth/google", response_model=CalendarAuthUrlResponse)
async def start_google_auth(
    current_user: dict = Depends(get_current_user)
):
    """
    Start Google Calendar OAuth flow.
    
    Returns the authorization URL to redirect the user to Google's consent screen.
    """
    # Check if Google OAuth is configured
    if not google_calendar_service.is_configured():
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Google Calendar integration is not configured"
        )
    
    user_id = current_user["sub"]
    
    try:
        auth_url, state = google_calendar_service.generate_auth_url(user_id)
        
        return CalendarAuthUrlResponse(
            auth_url=auth_url,
            state=state
        )
    except Exception as e:
        logger.error(f"Failed to generate Google auth URL: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to start Google Calendar authorization"
        )


@router.post("/callback/google", response_model=CalendarCallbackResponse)
async def google_auth_callback(
    callback: CalendarCallbackRequest,
    user_org: Tuple[str, str] = Depends(get_user_org)
):
    """
    Process Google OAuth callback.
    
    Exchanges the authorization code for tokens and stores the connection.
    """
    user_id, organization_id = user_org
    
    # Verify state contains user_id
    if not callback.state.startswith(user_id):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid state parameter"
        )
    
    try:
        # Exchange code for tokens
        tokens = google_calendar_service.exchange_code_for_tokens(callback.code)
        
        if not tokens:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Failed to exchange authorization code"
            )
        
        # Get user email from Google
        email = google_calendar_service.get_user_email(tokens["access_token"])
        
        # Check if connection already exists for this user + provider
        existing = supabase.table("calendar_connections").select("id").eq(
            "user_id", user_id
        ).eq("provider", "google").execute()
        
        # TODO: Implement proper encryption with pgsodium
        # For now, store tokens directly as strings (will be stored as BYTEA)
        connection_data = {
            "organization_id": organization_id,
            "user_id": user_id,
            "provider": "google",
            "access_token_encrypted": tokens["access_token"],
            "refresh_token_encrypted": tokens.get("refresh_token"),
            "token_expires_at": tokens.get("token_expires_at"),
            "email": email,
            "sync_enabled": True,
            "needs_reauth": False,
        }
        
        if existing.data and len(existing.data) > 0:
            # Update existing connection
            result = supabase.table("calendar_connections").update(
                connection_data
            ).eq("id", existing.data[0]["id"]).execute()
        else:
            # Create new connection
            result = supabase.table("calendar_connections").insert(
                connection_data
            ).execute()
        
        if not result.data:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Failed to save calendar connection"
            )
        
        logger.info(f"Google Calendar connected for user {user_id[:8]}..., email: {email}")
        
        # Trigger initial calendar sync via Inngest
        connection_id = result.data[0]["id"]
        await send_event(
            Events.CALENDAR_SYNC_REQUESTED,
            {"connection_id": connection_id}
        )
        logger.info(f"Triggered initial sync for connection {connection_id[:8]}...")
        
        return CalendarCallbackResponse(
            success=True,
            email=email,
            provider="google"
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Google OAuth callback error: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to connect Google Calendar: {str(e)}"
        )


# ==========================================
# Microsoft OAuth Endpoints
# ==========================================

@router.get("/auth/microsoft", response_model=CalendarAuthUrlResponse)
async def start_microsoft_auth(
    current_user: dict = Depends(get_current_user)
):
    """
    Start Microsoft 365 Calendar OAuth flow.
    
    Returns the authorization URL to redirect the user to Microsoft's consent screen.
    """
    # Check if Microsoft OAuth is configured
    if not microsoft_calendar_service.is_configured():
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Microsoft 365 integration is not configured. Please add MICROSOFT_CLIENT_ID and MICROSOFT_CLIENT_SECRET environment variables."
        )
    
    user_id = current_user["sub"]
    
    try:
        auth_url, state = microsoft_calendar_service.generate_auth_url(user_id)
        
        return CalendarAuthUrlResponse(
            auth_url=auth_url,
            state=state
        )
    except Exception as e:
        logger.error(f"Failed to generate Microsoft auth URL: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to start Microsoft Calendar authorization"
        )


@router.post("/callback/microsoft", response_model=CalendarCallbackResponse)
async def microsoft_auth_callback(
    callback: CalendarCallbackRequest,
    user_org: Tuple[str, str] = Depends(get_user_org)
):
    """
    Process Microsoft OAuth callback.
    
    Exchanges the authorization code for tokens and stores the connection.
    """
    user_id, organization_id = user_org
    
    # Verify state contains user_id
    if not callback.state.startswith(user_id):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid state parameter"
        )
    
    try:
        # Exchange code for tokens
        tokens = microsoft_calendar_service.exchange_code_for_tokens(callback.code)
        
        if not tokens:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Failed to exchange authorization code"
            )
        
        # Get user email from Microsoft Graph
        user_info = await microsoft_calendar_service.get_user_info(tokens["access_token"])
        email = user_info.get("email") if user_info else None
        
        # Check if connection already exists for this user + provider
        existing = supabase.table("calendar_connections").select("id").eq(
            "user_id", user_id
        ).eq("provider", "microsoft").execute()
        
        # Store connection
        connection_data = {
            "organization_id": organization_id,
            "user_id": user_id,
            "provider": "microsoft",
            "access_token_encrypted": tokens["access_token"],
            "refresh_token_encrypted": tokens.get("refresh_token"),
            "token_expires_at": None,  # TODO: Calculate from expires_in
            "email": email,
            "sync_enabled": True,
            "needs_reauth": False,
        }
        
        if existing.data and len(existing.data) > 0:
            # Update existing connection
            result = supabase.table("calendar_connections").update(
                connection_data
            ).eq("id", existing.data[0]["id"]).execute()
        else:
            # Create new connection
            result = supabase.table("calendar_connections").insert(
                connection_data
            ).execute()
        
        if not result.data:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Failed to save calendar connection"
            )
        
        logger.info(f"Microsoft Calendar connected for user {user_id[:8]}..., email: {email}")
        
        # Trigger initial calendar sync via Inngest
        connection_id = result.data[0]["id"]
        await send_event(
            Events.CALENDAR_SYNC_REQUESTED,
            {"connection_id": connection_id}
        )
        logger.info(f"Triggered initial sync for Microsoft connection {connection_id[:8]}...")
        
        return CalendarCallbackResponse(
            success=True,
            email=email,
            provider="microsoft"
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Microsoft OAuth callback error: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to connect Microsoft Calendar: {str(e)}"
        )


@router.delete("/disconnect/{provider}")
async def disconnect_calendar(
    provider: str,
    user_org: Tuple[str, str] = Depends(get_user_org)
):
    """
    Disconnect a calendar provider.
    
    Deletes the connection record and all synced meetings.
    Optionally revokes the OAuth tokens.
    """
    user_id, organization_id = user_org
    
    if provider not in ["google", "microsoft"]:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid provider. Must be 'google' or 'microsoft'"
        )
    
    try:
        # Get connection
        connection = supabase.table("calendar_connections").select("id").eq(
            "user_id", user_id
        ).eq("provider", provider).execute()
        
        if not connection.data or len(connection.data) == 0:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"No {provider} calendar connected"
            )
        
        connection_id = connection.data[0]["id"]
        
        # Delete related calendar meetings first (due to foreign key)
        supabase.table("calendar_meetings").delete().eq(
            "calendar_connection_id", connection_id
        ).execute()
        
        # Delete connection
        supabase.table("calendar_connections").delete().eq(
            "id", connection_id
        ).execute()
        
        logger.info(f"Disconnected {provider} calendar for user {user_id[:8]}...")
        
        return {"success": True, "message": f"{provider.capitalize()} Calendar disconnected"}
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Disconnect error for {provider}: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to disconnect {provider} calendar: {str(e)}"
        )


@router.get("/auth/microsoft", response_model=CalendarAuthUrlResponse)
async def start_microsoft_auth(
    current_user: dict = Depends(get_current_user)
):
    """
    Start Microsoft 365 Calendar OAuth flow.
    
    Returns the authorization URL to redirect the user to Microsoft's consent screen.
    """
    # TODO: Implement in Phase 4
    raise HTTPException(
        status_code=status.HTTP_501_NOT_IMPLEMENTED,
        detail="Microsoft OAuth not yet implemented. Coming in Phase 4."
    )


@router.post("/callback/microsoft", response_model=CalendarCallbackResponse)
async def microsoft_auth_callback(
    callback: CalendarCallbackRequest,
    user_org: Tuple[str, str] = Depends(get_user_org)
):
    """
    Process Microsoft OAuth callback.
    
    Exchanges the authorization code for tokens and stores the connection.
    """
    # TODO: Implement in Phase 4
    raise HTTPException(
        status_code=status.HTTP_501_NOT_IMPLEMENTED,
        detail="Microsoft OAuth callback not yet implemented. Coming in Phase 4."
    )


# ==========================================
# Sync Endpoints (Placeholder - to be implemented in Sprint 1.10)
# ==========================================

@router.post("/sync", response_model=CalendarSyncResponse)
async def trigger_calendar_sync(
    user_org: Tuple[str, str] = Depends(get_user_org)
):
    """
    Trigger manual calendar sync for all connected providers.
    
    Fetches latest events from Google/Microsoft and updates local database.
    Post-processing (prospect matching + auto-record) is handled via Inngest
    for reliability and scalability.
    """
    user_id, organization_id = user_org
    
    try:
        # Sync all user calendars
        results = calendar_sync_service.sync_user_calendars(user_id)
        
        # Aggregate results
        total_synced = 0
        total_new = 0
        total_updated = 0
        total_deleted = 0
        
        for provider, result in results.items():
            total_synced += result.synced_meetings
            total_new += result.new_meetings
            total_updated += result.updated_meetings
            total_deleted += result.deleted_meetings
        
        # Trigger Inngest event for post-sync processing
        # This handles: 1) ProspectMatcher  2) Auto-Record scheduling
        # Benefits: fast API response, reliable retries, proper ordering
        try:
            await send_event(
                Events.CALENDAR_SYNC_COMPLETED,
                {
                    "user_id": user_id,
                    "organization_id": organization_id,
                    "new_meetings": total_new,
                    "updated_meetings": total_updated,
                    "deleted_meetings": total_deleted,
                    "total_synced": total_synced,
                }
            )
            logger.info(f"Calendar sync completed for user {user_id[:8]}..., Inngest event sent")
        except Exception as e:
            logger.error(f"Failed to send calendar sync completed event: {e}")
            # Don't fail the sync if event fails - the sync data is still valid
        
        return CalendarSyncResponse(
            synced_meetings=total_synced,
            new_meetings=total_new,
            updated_meetings=total_updated,
            deleted_meetings=total_deleted
        )
        
    except Exception as e:
        logger.error(f"Calendar sync failed: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Sync failed: {str(e)}"
        )


@router.post("/debug/trigger-prospect-matching")
async def trigger_prospect_matching(
    user_org: Tuple[str, str] = Depends(get_user_org)
):
    """
    Debug endpoint: Manually trigger prospect matching for all unlinked meetings.
    Useful for debugging when prospect matching isn't working after sync.
    """
    user_id, organization_id = user_org
    
    try:
        from app.services.prospect_matcher import ProspectMatcher
        from app.database import get_supabase_service
        
        supabase = get_supabase_service()
        
        # Check unlinked meetings
        unlinked = supabase.table("calendar_meetings").select(
            "id, title, attendees, organizer_email"
        ).eq(
            "organization_id", organization_id
        ).is_(
            "prospect_id", "null"
        ).execute()
        
        unlinked_meetings = unlinked.data or []
        
        # Check contacts
        contacts = supabase.table("prospect_contacts").select(
            "id, name, email, prospect_id"
        ).eq(
            "organization_id", organization_id
        ).execute()
        
        contacts_data = contacts.data or []
        
        # Run matching
        matcher = ProspectMatcher(supabase)
        results = await matcher.match_all_unlinked(organization_id)
        
        auto_linked = sum(1 for r in results if r.auto_linked)
        total_matched = sum(1 for r in results if r.best_match is not None)
        
        return {
            "success": True,
            "unlinked_meetings_found": len(unlinked_meetings),
            "contacts_available": len(contacts_data),
            "total_meetings_processed": len(results),
            "auto_linked": auto_linked,
            "matches_found": total_matched,
            "unlinked_meeting_titles": [m["title"] for m in unlinked_meetings[:10]],
            "contact_names": [c.get("name") or c.get("email") for c in contacts_data[:10]],
            "details": [
                {
                    "meeting_title": r.meeting_id[:8] + "...",
                    "auto_linked": r.auto_linked,
                    "best_match": r.best_match.company_name if r.best_match else None,
                    "confidence": r.best_match.confidence if r.best_match else 0,
                    "reason": r.best_match.match_reason if r.best_match else None,
                    "contacts_matched": len(r.matched_contact_ids)
                }
                for r in results[:10]
            ]
        }
        
    except Exception as e:
        logger.error(f"Failed to trigger prospect matching: {e}")
        raise HTTPException(status_code=500, detail=str(e))



