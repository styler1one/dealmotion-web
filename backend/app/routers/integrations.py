"""
Integrations Router - API endpoints for recording integrations
SPEC-038: Meetings & Calendar Integration - Phase 3
"""
from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field
from typing import Optional, List, Tuple
from datetime import datetime, timezone
import logging
import httpx

from app.deps import get_current_user, get_user_org
from app.database import get_supabase_service
from app.services.fireflies_service import FirefliesService, sync_fireflies_recordings
from app.services.encryption import encrypt_api_key, is_encryption_secure

# Try to import Inngest for async processing
try:
    from app.inngest.events import send_event, Events
    INNGEST_ENABLED = True
except ImportError:
    INNGEST_ENABLED = False

supabase = get_supabase_service()

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1/integrations", tags=["integrations"])


# ==========================================
# Pydantic Models
# ==========================================

class IntegrationProviderStatus(BaseModel):
    """Status of a single recording integration."""
    connected: bool = Field(description="Whether the provider is connected")
    api_key_set: bool = Field(default=False, description="Whether API key is configured")
    account_email: Optional[str] = Field(None, description="Connected account email")
    account_name: Optional[str] = Field(None, description="Connected account name")
    last_sync: Optional[datetime] = Field(None, description="Last successful sync time")
    last_sync_status: Optional[str] = Field(None, description="Status of last sync")
    pending_recordings: int = Field(default=0, description="Number of pending recordings to import")
    auto_import: bool = Field(default=True, description="Whether auto-import is enabled")


class IntegrationsStatusResponse(BaseModel):
    """Response for all recording integration statuses."""
    fireflies: IntegrationProviderStatus
    zoom: IntegrationProviderStatus
    teams: IntegrationProviderStatus


class FirefliesConnectRequest(BaseModel):
    """Request to connect Fireflies with API key."""
    api_key: str = Field(description="Fireflies API key", min_length=10)


class FirefliesConnectResponse(BaseModel):
    """Response after connecting Fireflies."""
    success: bool
    account_email: Optional[str] = Field(None, description="Connected account email")
    account_name: Optional[str] = Field(None, description="Account name from Fireflies")


class IntegrationDisconnectResponse(BaseModel):
    """Response after disconnecting an integration."""
    success: bool
    provider: str


class ExternalRecordingResponse(BaseModel):
    """External recording from Fireflies/Zoom/Teams."""
    id: str
    provider: str
    external_id: str
    title: Optional[str]
    recording_date: datetime
    duration_seconds: Optional[int]
    participants: List[str] = []
    transcript_available: bool = False
    audio_url: Optional[str] = None
    matched_meeting_id: Optional[str] = None
    matched_prospect_id: Optional[str] = None
    import_status: str


class ExternalRecordingsListResponse(BaseModel):
    """List of external recordings."""
    recordings: List[ExternalRecordingResponse]
    total: int


class FirefliesSyncResponse(BaseModel):
    """Response after Fireflies sync."""
    success: bool
    new_recordings: int = 0
    updated_recordings: int = 0
    skipped_recordings: int = 0
    errors: int = 0


class FirefliesImportRequest(BaseModel):
    """Request to import a Fireflies recording."""
    prospect_id: Optional[str] = Field(None, description="Link to a specific prospect")
    contact_ids: Optional[List[str]] = Field(None, description="Link to specific contacts")
    meeting_prep_id: Optional[str] = Field(None, description="Link to a meeting preparation")
    include_coaching: bool = Field(False, description="Include coaching feedback in analysis")


class FirefliesImportResponse(BaseModel):
    """Response after importing a Fireflies recording."""
    success: bool
    followup_id: Optional[str] = Field(None, description="Created followup record ID")
    message: str


# ==========================================
# Helper Functions
# ==========================================

async def validate_fireflies_api_key(api_key: str) -> dict:
    """
    Validate Fireflies API key by fetching user info.
    Returns user info if valid, raises exception if invalid.
    """
    url = "https://api.fireflies.ai/graphql"
    
    query = """
    query {
        user {
            email
            name
            user_id
        }
    }
    """
    
    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json"
    }
    
    async with httpx.AsyncClient() as client:
        try:
            response = await client.post(
                url,
                json={"query": query},
                headers=headers,
                timeout=10.0
            )
            
            if response.status_code != 200:
                logger.warning(f"Fireflies API returned status {response.status_code}")
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="Invalid Fireflies API key"
                )
            
            data = response.json()
            
            if "errors" in data:
                logger.warning(f"Fireflies API errors: {data['errors']}")
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="Invalid Fireflies API key"
                )
            
            user_data = data.get("data", {}).get("user")
            if not user_data:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="Could not retrieve Fireflies user info"
                )
            
            return user_data
            
        except httpx.RequestError as e:
            logger.error(f"Fireflies API request failed: {e}")
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="Could not connect to Fireflies API"
            )


def get_empty_provider_status() -> IntegrationProviderStatus:
    """Return empty status for a disconnected provider."""
    return IntegrationProviderStatus(
        connected=False,
        api_key_set=False,
        account_email=None,
        account_name=None,
        last_sync=None,
        last_sync_status=None,
        pending_recordings=0,
        auto_import=True
    )


# ==========================================
# Endpoints
# ==========================================

@router.get("/status", response_model=IntegrationsStatusResponse)
async def get_integrations_status(
    user: dict = Depends(get_current_user),
    user_org: Tuple[str, str] = Depends(get_user_org)
):
    """
    Get status of all recording integrations for current user.
    """
    user_id, org_id = user_org  # Unpack tuple (user_id, organization_id)
    
    # Validate user_id is a valid UUID string
    if not user_id or user_id == "None" or len(user_id) < 10:
        logger.warning(f"Invalid user_id in get_integrations_status: {user_id}")
        return IntegrationsStatusResponse(
            fireflies=get_empty_provider_status(),
            zoom=get_empty_provider_status(),
            teams=get_empty_provider_status()
        )
    
    # Initialize empty status for all providers
    fireflies_status = get_empty_provider_status()
    zoom_status = get_empty_provider_status()
    teams_status = get_empty_provider_status()
    
    try:
        # Fetch all integrations for user
        result = supabase.table("recording_integrations").select("*").eq(
            "user_id", user_id
        ).execute()
        
        integrations = result.data or []
        
        for integration in integrations:
            provider = integration.get("provider")
            
            status_obj = IntegrationProviderStatus(
                connected=True,
                api_key_set=bool(integration.get("credentials")),
                account_email=integration.get("account_email"),
                account_name=integration.get("account_name"),
                last_sync=integration.get("last_sync_at"),
                last_sync_status=integration.get("last_sync_status"),
                pending_recordings=0,  # Will be updated below
                auto_import=integration.get("auto_import", True)
            )
            
            if provider == "fireflies":
                fireflies_status = status_obj
            elif provider == "zoom":
                zoom_status = status_obj
            elif provider == "teams":
                teams_status = status_obj
        
        # Count pending recordings per provider
        pending_result = supabase.table("external_recordings").select(
            "provider", count="exact"
        ).eq("user_id", user_id).eq("import_status", "pending").execute()
        
        # Note: Supabase doesn't support group by easily, so we'll do it in Python
        pending_recordings = supabase.table("external_recordings").select(
            "provider"
        ).eq("user_id", user_id).eq("import_status", "pending").execute()
        
        if pending_recordings.data:
            for rec in pending_recordings.data:
                provider = rec.get("provider")
                if provider == "fireflies":
                    fireflies_status.pending_recordings += 1
                elif provider == "zoom":
                    zoom_status.pending_recordings += 1
                elif provider == "teams":
                    teams_status.pending_recordings += 1
        
    except Exception as e:
        logger.error(f"Error fetching integrations status: {e}")
        # Return empty status on error
    
    return IntegrationsStatusResponse(
        fireflies=fireflies_status,
        zoom=zoom_status,
        teams=teams_status
    )


@router.post("/fireflies/connect", response_model=FirefliesConnectResponse)
async def connect_fireflies(
    request: FirefliesConnectRequest,
    user: dict = Depends(get_current_user),
    user_org: Tuple[str, str] = Depends(get_user_org)
):
    """
    Connect Fireflies integration with API key.
    Validates the API key against Fireflies API before saving.
    """
    user_id, org_id = user_org  # Unpack tuple (user_id, organization_id)
    
    # Validate IDs
    if not user_id or not org_id:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid user or organization"
        )
    api_key = request.api_key
    
    # Validate API key with Fireflies
    logger.info(f"Validating Fireflies API key for user {user_id}")
    user_info = await validate_fireflies_api_key(api_key)
    
    account_email = user_info.get("email")
    account_name = user_info.get("name")
    
    # Encrypt credentials for secure storage
    credentials = encrypt_api_key(api_key)
    
    # Log security status (don't log in production)
    if not is_encryption_secure():
        logger.warning(f"API key stored with fallback encoding for user {user_id}. Configure ENCRYPTION_KEY for production.")
    
    try:
        # Check if integration already exists
        existing = supabase.table("recording_integrations").select("id").eq(
            "user_id", user_id
        ).eq("provider", "fireflies").execute()
        
        integration_data = {
            "organization_id": org_id,
            "user_id": user_id,
            "provider": "fireflies",
            "credentials": credentials,
            "account_email": account_email,
            "account_name": account_name,
            "auto_import": True,
            "updated_at": datetime.now(timezone.utc).isoformat()
        }
        
        if existing.data:
            # Update existing integration
            result = supabase.table("recording_integrations").update(
                integration_data
            ).eq("id", existing.data[0]["id"]).execute()
            logger.info(f"Updated Fireflies integration for user {user_id}")
        else:
            # Create new integration
            integration_data["created_at"] = datetime.now(timezone.utc).isoformat()
            result = supabase.table("recording_integrations").insert(
                integration_data
            ).execute()
            logger.info(f"Created Fireflies integration for user {user_id}")
        
        # Trigger initial sync with 90 days of history
        try:
            integration_result = supabase.table("recording_integrations").select("id").eq(
                "user_id", user_id
            ).eq("provider", "fireflies").execute()
            
            if integration_result.data:
                integration_id = integration_result.data[0]["id"]
                # Use the raw API key directly (before encryption) to create service
                service = FirefliesService(api_key)
                
                # Run initial sync (90 days of history)
                logger.info(f"Triggering initial Fireflies sync for user {user_id}")
                stats = await sync_fireflies_recordings(
                    user_id=user_id,
                    org_id=org_id,
                    integration_id=integration_id,
                    service=service,
                    days_back=90  # Initial sync: 90 days of history
                )
                logger.info(f"Initial sync complete: {stats}")
        except Exception as sync_error:
            # Don't fail the connect if sync fails
            logger.warning(f"Initial Fireflies sync failed (non-critical): {sync_error}")
        
        return FirefliesConnectResponse(
            success=True,
            account_email=account_email,
            account_name=account_name
        )
        
    except Exception as e:
        logger.error(f"Error saving Fireflies integration: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to save Fireflies integration"
        )


@router.delete("/fireflies/disconnect", response_model=IntegrationDisconnectResponse)
async def disconnect_fireflies(
    user: dict = Depends(get_current_user),
    user_org: Tuple[str, str] = Depends(get_user_org)
):
    """
    Disconnect Fireflies integration.
    Removes the integration but keeps imported recordings.
    """
    user_id, org_id = user_org  # Unpack tuple
    
    if not user_id:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid user"
        )
    
    try:
        # Delete integration record
        result = supabase.table("recording_integrations").delete().eq(
            "user_id", user_id
        ).eq("provider", "fireflies").execute()
        
        logger.info(f"Disconnected Fireflies for user {user_id}")
        
        return IntegrationDisconnectResponse(
            success=True,
            provider="fireflies"
        )
        
    except Exception as e:
        logger.error(f"Error disconnecting Fireflies: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to disconnect Fireflies"
        )


@router.post("/fireflies/sync", response_model=FirefliesSyncResponse)
async def sync_fireflies(
    user: dict = Depends(get_current_user),
    user_org: Tuple[str, str] = Depends(get_user_org),
    days_back: int = 90
):
    """
    Manually trigger a sync of Fireflies recordings.
    Fetches recent transcripts and saves them to external_recordings.
    Default: 90 days of history.
    """
    # Input validation
    if days_back < 1 or days_back > 365:
        days_back = 90  # Default to 90 if out of range
    
    user_id, org_id = user_org  # Unpack tuple (user_id, organization_id)
    
    if not user_id or not org_id:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid user or organization"
        )
    
    # Get integration record
    result = supabase.table("recording_integrations").select("*").eq(
        "user_id", user_id
    ).eq("provider", "fireflies").execute()
    
    if not result.data:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Fireflies integration not found. Please connect first."
        )
    
    integration = result.data[0]
    integration_id = integration["id"]
    
    # Create service from integration
    service = FirefliesService.from_integration(integration)
    if not service:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid Fireflies credentials"
        )
    
    try:
        # Run sync
        stats = await sync_fireflies_recordings(
            user_id=user_id,
            org_id=org_id,
            integration_id=integration_id,
            service=service,
            days_back=days_back
        )
        
        return FirefliesSyncResponse(
            success=True,
            new_recordings=stats.get("new", 0),
            updated_recordings=stats.get("updated", 0),
            skipped_recordings=stats.get("skipped", 0),
            errors=stats.get("error", 0)
        )
        
    except Exception as e:
        logger.error(f"Fireflies sync failed: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Sync failed: {str(e)}"
        )


@router.get("/fireflies/recordings", response_model=ExternalRecordingsListResponse)
async def get_fireflies_recordings(
    user: dict = Depends(get_current_user),
    user_org: Tuple[str, str] = Depends(get_user_org),
    import_status: Optional[str] = None,
    limit: int = 50
):
    """
    Get external recordings from Fireflies.
    Optionally filter by import status (pending, imported, skipped, failed).
    """
    user_id, org_id = user_org  # Unpack tuple
    
    # Validate user_id
    if not user_id or user_id == "None":
        return ExternalRecordingsListResponse(recordings=[], total=0)
    
    try:
        query = supabase.table("external_recordings").select("*").eq(
            "user_id", user_id
        ).eq("provider", "fireflies").order("recording_date", desc=True).limit(limit)
        
        if import_status:
            query = query.eq("import_status", import_status)
        
        result = query.execute()
        
        recordings = []
        for rec in result.data or []:
            recordings.append(ExternalRecordingResponse(
                id=rec["id"],
                provider=rec["provider"],
                external_id=rec["external_id"],
                title=rec.get("title"),
                recording_date=rec["recording_date"],
                duration_seconds=rec.get("duration_seconds"),
                participants=rec.get("participants") or [],
                transcript_available=bool(rec.get("transcript_text") or rec.get("transcript_url")),
                audio_url=rec.get("audio_url"),
                matched_meeting_id=rec.get("matched_meeting_id"),
                matched_prospect_id=rec.get("matched_prospect_id"),
                import_status=rec["import_status"]
            ))
        
        return ExternalRecordingsListResponse(
            recordings=recordings,
            total=len(recordings)
        )
        
    except Exception as e:
        logger.error(f"Error fetching Fireflies recordings: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to fetch recordings"
        )


@router.post("/fireflies/import/{recording_id}", response_model=FirefliesImportResponse)
async def import_fireflies_recording(
    recording_id: str,
    request: FirefliesImportRequest = FirefliesImportRequest(),
    user: dict = Depends(get_current_user),
    user_org: Tuple[str, str] = Depends(get_user_org)
):
    """
    Import a Fireflies recording into Meeting Analysis.
    Creates a followup record and triggers AI summarization.
    """
    user_id, org_id = user_org  # Unpack tuple (user_id, organization_id)
    
    if not user_id or not org_id:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid user or organization"
        )
    
    try:
        # Get the external recording
        result = supabase.table("external_recordings").select("*").eq(
            "id", recording_id
        ).eq("user_id", user_id).execute()
        
        if not result.data:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Recording not found"
            )
        
        recording = result.data[0]
        
        # Check if already imported
        if recording["import_status"] == "imported":
            return FirefliesImportResponse(
                success=True,
                followup_id=recording.get("imported_followup_id"),
                message="Recording already imported"
            )
        
        # Determine prospect_id
        prospect_id = request.prospect_id or recording.get("matched_prospect_id")
        
        if not prospect_id:
            # Try to find from matched meeting
            if recording.get("matched_meeting_id"):
                meeting_result = supabase.table("calendar_meetings").select(
                    "prospect_id"
                ).eq("id", recording["matched_meeting_id"]).execute()
                
                if meeting_result.data and meeting_result.data[0].get("prospect_id"):
                    prospect_id = meeting_result.data[0]["prospect_id"]
        
        # Get prospect company name for context
        prospect_company = None
        if prospect_id:
            try:
                prospect_result = supabase.table("prospects").select("company_name").eq("id", prospect_id).execute()
                if prospect_result.data:
                    prospect_company = prospect_result.data[0].get("company_name")
            except Exception:
                pass  # Non-critical
        
        # Create followup record (only use columns that exist in the table)
        transcript = recording.get("transcript_text", "")
        title = recording.get("title", "Fireflies Recording")
        calendar_meeting_id = recording.get("matched_meeting_id")  # Get linked calendar meeting
        
        followup_data = {
            "organization_id": org_id,
            "user_id": user_id,
            "prospect_id": prospect_id,
            "meeting_prep_id": request.meeting_prep_id,  # Link to preparation
            "contact_ids": request.contact_ids or [],  # Link to contacts
            "external_recording_id": recording_id,  # Link to external recording (SPEC-038)
            "calendar_meeting_id": calendar_meeting_id,  # Link to calendar meeting (SPEC-038)
            "audio_url": recording.get("audio_url"),
            "transcription_text": transcript[:100000] if transcript else None,  # Limit size
            "meeting_subject": title,  # Use meeting_subject for title
            "include_coaching": request.include_coaching,  # Coaching preference
            "status": "summarizing",  # Valid status: uploading, transcribing, summarizing, completed, failed
            "created_at": datetime.now(timezone.utc).isoformat()
        }
        
        # Insert followup
        followup_result = supabase.table("followups").insert(followup_data).execute()
        
        if not followup_result.data:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Failed to create followup record"
            )
        
        followup_id = followup_result.data[0]["id"]
        
        # Update reverse link in calendar_meetings (SPEC-038)
        if calendar_meeting_id:
            try:
                supabase.table("calendar_meetings").update({
                    "followup_id": followup_id
                }).eq("id", calendar_meeting_id).eq(
                    "organization_id", org_id
                ).execute()
                logger.info(f"Linked followup {followup_id} to calendar meeting {calendar_meeting_id}")
            except Exception as e:
                logger.warning(f"Failed to link followup to calendar meeting: {e}")
        
        # Update external recording status
        supabase.table("external_recordings").update({
            "import_status": "imported",
            "imported_followup_id": followup_id,
            "matched_prospect_id": prospect_id,
            "updated_at": datetime.now(timezone.utc).isoformat()
        }).eq("id", recording_id).execute()
        
        # Trigger AI summarization via Inngest (use existing transcript processing flow)
        if INNGEST_ENABLED and transcript:
            try:
                await send_event(Events.FOLLOWUP_TRANSCRIPT_UPLOADED, {
                    "followup_id": followup_id,
                    "transcription_text": transcript[:100000],  # Limit size
                    "segments": [],  # Fireflies doesn't provide segment format
                    "speaker_count": len(recording.get("participants", [])) or 2,
                    "organization_id": org_id,
                    "user_id": user_id,
                    "meeting_prep_id": request.meeting_prep_id,
                    "prospect_company": prospect_company,
                    "include_coaching": request.include_coaching,
                    "language": "en"
                })
                logger.info(f"Triggered transcript processing for followup {followup_id}")
            except Exception as e:
                logger.warning(f"Failed to trigger transcript processing: {e}")
        
        return FirefliesImportResponse(
            success=True,
            followup_id=followup_id,
            message="Recording imported successfully. AI analysis in progress."
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error importing Fireflies recording: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Import failed: {str(e)}"
        )


# ==========================================
# Teams Endpoints
# ==========================================

class TeamsSyncResponse(BaseModel):
    """Response after Teams sync."""
    success: bool
    total_meetings: int = 0
    recordings_found: int = 0
    transcripts_found: int = 0
    new_recordings: int = 0
    errors: List[str] = []


@router.get("/teams/status")
async def get_teams_status(
    user: dict = Depends(get_current_user),
    user_org: Tuple[str, str] = Depends(get_user_org)
):
    """
    Get Teams integration status.
    Teams uses the Microsoft Calendar connection for authentication.
    """
    user_id, org_id = user_org
    
    # Check if Microsoft Calendar is connected
    connection = supabase.table("calendar_connections").select(
        "id, email, last_sync_at, last_sync_status"
    ).eq("user_id", user_id).eq("provider", "microsoft").execute()
    
    if not connection.data:
        return {
            "connected": False,
            "message": "Connect Microsoft 365 Calendar first to enable Teams recordings"
        }
    
    # Count pending Teams recordings
    pending = supabase.table("external_recordings").select(
        "id", count="exact"
    ).eq("user_id", user_id).eq("source", "teams").eq("status", "pending").execute()
    
    return {
        "connected": True,
        "email": connection.data[0].get("email"),
        "pending_recordings": pending.count or 0,
        "last_sync": connection.data[0].get("last_sync_at"),
        "message": "Microsoft 365 connected. Teams recordings available."
    }


@router.post("/teams/sync", response_model=TeamsSyncResponse)
async def sync_teams_recordings(
    days_back: int = 30,
    user: dict = Depends(get_current_user),
    user_org: Tuple[str, str] = Depends(get_user_org)
):
    """
    Sync Teams recordings from Microsoft Graph API.
    Requires Microsoft 365 Calendar to be connected.
    """
    from app.services.teams_service import teams_service
    from app.services.calendar_sync import CalendarSyncService
    
    user_id, org_id = user_org
    
    # Validate days_back
    if days_back < 1 or days_back > 365:
        days_back = 30
    
    # Get Microsoft Calendar connection
    connection = supabase.table("calendar_connections").select("*").eq(
        "user_id", user_id
    ).eq("provider", "microsoft").execute()
    
    if not connection.data:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Microsoft 365 Calendar not connected. Connect in Settings first."
        )
    
    conn = connection.data[0]
    
    # Get access token
    sync_service = CalendarSyncService()
    access_token = sync_service._decode_token(conn.get("access_token_encrypted"))
    
    if not access_token:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Microsoft access token not available. Please reconnect Microsoft 365."
        )
    
    # Try to refresh token if we have a refresh token
    refresh_token = sync_service._decode_token(conn.get("refresh_token_encrypted")) if conn.get("refresh_token_encrypted") else None
    
    if refresh_token:
        from app.services.microsoft_calendar import microsoft_calendar_service
        new_tokens = microsoft_calendar_service.refresh_access_token(refresh_token)
        if new_tokens:
            access_token = new_tokens["access_token"]
            # Update stored tokens
            supabase.table("calendar_connections").update({
                "access_token_encrypted": access_token,
                "refresh_token_encrypted": new_tokens.get("refresh_token", refresh_token),
            }).eq("id", conn["id"]).execute()
    
    try:
        # Sync Teams recordings
        result = await teams_service.sync_teams_recordings(
            user_id=user_id,
            organization_id=org_id,
            access_token=access_token,
            days_back=days_back
        )
        
        # Update connection sync status
        supabase.table("calendar_connections").update({
            "last_sync_at": datetime.now(timezone.utc).isoformat(),
            "last_sync_status": "success" if not result["errors"] else "failed",
        }).eq("id", conn["id"]).execute()
        
        return TeamsSyncResponse(
            success=True,
            total_meetings=result.get("total_meetings", 0),
            recordings_found=result.get("recordings_found", 0),
            transcripts_found=result.get("transcripts_found", 0),
            new_recordings=result.get("new_recordings", 0),
            errors=result.get("errors", [])
        )
        
    except Exception as e:
        logger.error(f"Teams sync failed: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Teams sync failed: {str(e)}"
        )


@router.get("/teams/recordings")
async def get_teams_recordings(
    status_filter: Optional[str] = None,
    limit: int = 50,
    user: dict = Depends(get_current_user),
    user_org: Tuple[str, str] = Depends(get_user_org)
):
    """
    Get Teams recordings for the current user.
    """
    user_id, org_id = user_org
    
    query = supabase.table("external_recordings").select("*").eq(
        "user_id", user_id
    ).eq("source", "teams").order("meeting_time", desc=True).limit(limit)
    
    if status_filter:
        query = query.eq("status", status_filter)
    
    result = query.execute()
    
    recordings = []
    for rec in result.data or []:
        recordings.append({
            "id": rec.get("id"),
            "external_id": rec.get("external_id"),
            "title": rec.get("title"),
            "meeting_time": rec.get("meeting_time"),
            "duration": rec.get("duration"),
            "participants": rec.get("participants", []),
            "transcript_available": rec.get("transcript_available", False),
            "status": rec.get("status"),
            "imported_followup_id": rec.get("imported_followup_id"),
        })
    
    return {
        "recordings": recordings,
        "total": len(recordings)
    }


@router.post("/teams/recordings/{recording_id}/import")
async def import_teams_recording(
    recording_id: str,
    prospect_id: Optional[str] = None,
    contact_ids: Optional[List[str]] = None,
    meeting_prep_id: Optional[str] = None,
    user: dict = Depends(get_current_user),
    user_org: Tuple[str, str] = Depends(get_user_org)
):
    """
    Import a Teams recording for AI analysis.
    Creates a followup record and triggers summarization.
    """
    user_id, org_id = user_org
    
    # Get the recording
    recording = supabase.table("external_recordings").select("*").eq(
        "id", recording_id
    ).eq("user_id", user_id).eq("source", "teams").execute()
    
    if not recording.data:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Teams recording not found"
        )
    
    rec = recording.data[0]
    
    # Check if already imported
    if rec.get("imported_followup_id"):
        return {
            "success": True,
            "followup_id": rec.get("imported_followup_id"),
            "message": "Recording already imported"
        }
    
    try:
        # Get linked calendar meeting
        calendar_meeting_id = rec.get("matched_meeting_id")
        
        # Create followup record
        followup_data = {
            "user_id": user_id,
            "organization_id": org_id,
            "external_recording_id": recording_id,  # Link to external recording (SPEC-038)
            "calendar_meeting_id": calendar_meeting_id,  # Link to calendar meeting (SPEC-038)
            "meeting_subject": rec.get("title") or "Teams Meeting",
            "meeting_date": rec.get("meeting_time"),
            "meeting_duration": rec.get("duration"),
            "transcription_text": rec.get("transcript_text"),
            "status": "summarizing" if rec.get("transcript_text") else "pending",
            "prospect_id": prospect_id,
            "meeting_prep_id": meeting_prep_id,
            "contact_ids": contact_ids or [],
        }
        
        result = supabase.table("followups").insert(followup_data).execute()
        
        if not result.data:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Failed to create followup record"
            )
        
        followup_id = result.data[0]["id"]
        
        # Update reverse link in calendar_meetings (SPEC-038)
        if calendar_meeting_id:
            try:
                supabase.table("calendar_meetings").update({
                    "followup_id": followup_id
                }).eq("id", calendar_meeting_id).eq(
                    "organization_id", org_id
                ).execute()
                logger.info(f"Linked followup {followup_id} to calendar meeting {calendar_meeting_id}")
            except Exception as e:
                logger.warning(f"Failed to link followup to calendar meeting: {e}")
        
        # Update external_recordings
        supabase.table("external_recordings").update({
            "imported_followup_id": followup_id,
            "status": "imported"
        }).eq("id", recording_id).execute()
        
        # Trigger AI analysis if transcript is available
        if rec.get("transcript_text") and INNGEST_ENABLED:
            await send_event(
                Events.FOLLOWUP_TRANSCRIPT_UPLOADED,
                {
                    "followup_id": followup_id,
                    "user_id": user_id,
                    "organization_id": org_id,
                }
            )
            logger.info(f"Triggered AI analysis for Teams recording {recording_id}")
        
        return {
            "success": True,
            "followup_id": followup_id,
            "message": "Teams recording imported successfully"
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error importing Teams recording: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Import failed: {str(e)}"
        )

