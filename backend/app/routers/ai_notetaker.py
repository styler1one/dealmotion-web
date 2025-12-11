"""
AI Notetaker Router - Schedule and manage meeting recordings via Recall.ai

SPEC-043: AI Notetaker / Recall.ai Integration

Endpoints:
- POST /schedule - Schedule AI Notetaker for a meeting
- GET /scheduled - List scheduled recordings
- GET /{id} - Get recording details
- DELETE /{id} - Cancel a scheduled recording
- POST /webhook/recall - Handle Recall.ai webhooks
"""

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel, Field
from typing import Optional, List
from datetime import datetime
import logging
import hmac
import hashlib
import os

from app.deps import get_current_user, get_user_org
from app.database import get_supabase_service
from app.services.recall_service import recall_service, RecallBotConfig
from app.inngest.events import send_event, use_inngest_for, Events

logger = logging.getLogger(__name__)

router = APIRouter()

# Environment
RECALL_WEBHOOK_SECRET = os.getenv("RECALL_WEBHOOK_SECRET", "")


# ==========================================
# Request/Response Models
# ==========================================

class ScheduleRecordingRequest(BaseModel):
    """Request to schedule an AI Notetaker for a meeting."""
    meeting_url: str = Field(..., description="Teams/Meet/Zoom meeting URL")
    scheduled_time: Optional[datetime] = Field(None, description="When to join (None = immediately)")
    meeting_title: Optional[str] = Field(None, description="Optional meeting title")
    prospect_id: Optional[str] = Field(None, description="Optional prospect to link to")
    # Context fields (same as regular followup upload)
    meeting_prep_id: Optional[str] = Field(None, description="Link to meeting preparation")
    contact_ids: Optional[List[str]] = Field(None, description="Contact person IDs attending")
    deal_id: Optional[str] = Field(None, description="Optional deal to link to")
    calendar_meeting_id: Optional[str] = Field(None, description="Link to calendar meeting")


class ScheduleRecordingResponse(BaseModel):
    """Response after scheduling a recording."""
    id: str
    recall_bot_id: Optional[str]
    status: str
    meeting_url: str
    meeting_title: Optional[str]
    meeting_platform: str
    scheduled_time: datetime
    prospect_id: Optional[str]
    prospect_name: Optional[str]


class ScheduledRecording(BaseModel):
    """A scheduled or completed recording."""
    id: str
    recall_bot_id: Optional[str]
    status: str
    meeting_url: str
    meeting_title: Optional[str]
    meeting_platform: Optional[str]
    scheduled_time: datetime
    prospect_id: Optional[str]
    prospect_name: Optional[str]
    followup_id: Optional[str]
    duration_seconds: Optional[int]
    created_at: datetime


class ScheduledRecordingsResponse(BaseModel):
    """List of scheduled recordings."""
    recordings: List[ScheduledRecording]


class CancelRecordingResponse(BaseModel):
    """Response after cancelling a recording."""
    success: bool
    message: str


# ==========================================
# Endpoints
# ==========================================

@router.post("/schedule", response_model=ScheduleRecordingResponse)
async def schedule_recording(
    request: ScheduleRecordingRequest,
    current_user: dict = Depends(get_current_user),
    user_org: tuple = Depends(get_user_org),
):
    """
    Schedule AI Notetaker to join a meeting.
    
    The AI Notetaker (DealMotion AI Notes) will automatically join the meeting,
    record the conversation, and trigger transcription + analysis when complete.
    """
    user_id, org_id = user_org
    supabase = get_supabase_service()
    
    # Validate meeting URL
    is_valid, platform, error = recall_service.validate_meeting_url(request.meeting_url)
    if not is_valid:
        raise HTTPException(status_code=400, detail=error)
    
    # Determine scheduled time
    scheduled_time = request.scheduled_time or datetime.utcnow()
    
    # Get prospect name if linked
    prospect_name = None
    if request.prospect_id:
        prospect_result = supabase.table("prospects").select(
            "company_name"
        ).eq("id", request.prospect_id).single().execute()
        if prospect_result.data:
            prospect_name = prospect_result.data.get("company_name")
    
    # Create record in database first (with context fields)
    db_record = {
        "organization_id": org_id,
        "user_id": user_id,
        "meeting_url": request.meeting_url,
        "meeting_title": request.meeting_title,
        "meeting_platform": platform,
        "scheduled_time": scheduled_time.isoformat(),
        "status": "scheduled",
        "prospect_id": request.prospect_id,
        "source": "manual",
        # Context fields (same as regular followup)
        "meeting_prep_id": request.meeting_prep_id,
        "contact_ids": request.contact_ids or [],
        "deal_id": request.deal_id,
        "calendar_meeting_id": request.calendar_meeting_id,
    }
    
    insert_result = supabase.table("scheduled_recordings").insert(db_record).execute()
    
    if not insert_result.data:
        raise HTTPException(status_code=500, detail="Failed to create recording record")
    
    recording_id = insert_result.data[0]["id"]
    recall_bot_id = None
    
    # Schedule with Recall.ai
    if recall_service.is_configured():
        config = RecallBotConfig(
            meeting_url=request.meeting_url,
            join_at=scheduled_time if request.scheduled_time else None
        )
        
        result = await recall_service.create_bot(config)
        
        if result.get("success"):
            recall_bot_id = result.get("bot_id")
            # Update record with Recall.ai bot ID
            supabase.table("scheduled_recordings").update({
                "recall_bot_id": recall_bot_id
            }).eq("id", recording_id).execute()
            
            logger.info(f"Scheduled AI Notetaker for {platform} meeting: {recording_id}")
        else:
            # Update status to error
            supabase.table("scheduled_recordings").update({
                "status": "error",
                "error_message": result.get("error", "Failed to schedule with Recall.ai")
            }).eq("id", recording_id).execute()
            
            raise HTTPException(
                status_code=500, 
                detail=result.get("error", "Failed to schedule with Recall.ai")
            )
    else:
        logger.warning("Recall.ai not configured - recording created but bot not scheduled")
    
    return ScheduleRecordingResponse(
        id=recording_id,
        recall_bot_id=recall_bot_id,
        status="scheduled",
        meeting_url=request.meeting_url,
        meeting_title=request.meeting_title,
        meeting_platform=platform,
        scheduled_time=scheduled_time,
        prospect_id=request.prospect_id,
        prospect_name=prospect_name
    )


@router.get("/scheduled", response_model=ScheduledRecordingsResponse)
async def list_scheduled_recordings(
    status: Optional[str] = None,
    current_user: dict = Depends(get_current_user),
    user_org: tuple = Depends(get_user_org),
):
    """
    List all scheduled/active recordings for the user's organization.
    
    Optionally filter by status: scheduled, joining, recording, processing, complete, error
    """
    user_id, org_id = user_org
    supabase = get_supabase_service()
    
    query = supabase.table("scheduled_recordings").select(
        "id, recall_bot_id, status, meeting_url, meeting_title, meeting_platform, "
        "scheduled_time, prospect_id, followup_id, duration_seconds, created_at, "
        "prospects(company_name)"
    ).eq("organization_id", org_id).order("scheduled_time", desc=True)
    
    if status:
        query = query.eq("status", status)
    else:
        # Default: show non-completed
        query = query.in_("status", ["scheduled", "joining", "waiting_room", "recording", "processing"])
    
    result = query.limit(50).execute()
    
    recordings = []
    for row in result.data or []:
        prospect_name = None
        if row.get("prospects"):
            prospect_name = row["prospects"].get("company_name")
        
        recordings.append(ScheduledRecording(
            id=row["id"],
            recall_bot_id=row.get("recall_bot_id"),
            status=row["status"],
            meeting_url=row["meeting_url"],
            meeting_title=row.get("meeting_title"),
            meeting_platform=row.get("meeting_platform"),
            scheduled_time=row["scheduled_time"],
            prospect_id=row.get("prospect_id"),
            prospect_name=prospect_name,
            followup_id=row.get("followup_id"),
            duration_seconds=row.get("duration_seconds"),
            created_at=row["created_at"]
        ))
    
    return ScheduledRecordingsResponse(recordings=recordings)


@router.get("/{recording_id}", response_model=ScheduledRecording)
async def get_recording(
    recording_id: str,
    current_user: dict = Depends(get_current_user),
    user_org: tuple = Depends(get_user_org),
):
    """Get details of a specific scheduled recording."""
    user_id, org_id = user_org
    supabase = get_supabase_service()
    
    result = supabase.table("scheduled_recordings").select(
        "id, recall_bot_id, status, meeting_url, meeting_title, meeting_platform, "
        "scheduled_time, prospect_id, followup_id, duration_seconds, created_at, "
        "prospects(company_name)"
    ).eq("id", recording_id).eq("organization_id", org_id).single().execute()
    
    if not result.data:
        raise HTTPException(status_code=404, detail="Recording not found")
    
    row = result.data
    prospect_name = None
    if row.get("prospects"):
        prospect_name = row["prospects"].get("company_name")
    
    return ScheduledRecording(
        id=row["id"],
        recall_bot_id=row.get("recall_bot_id"),
        status=row["status"],
        meeting_url=row["meeting_url"],
        meeting_title=row.get("meeting_title"),
        meeting_platform=row.get("meeting_platform"),
        scheduled_time=row["scheduled_time"],
        prospect_id=row.get("prospect_id"),
        prospect_name=prospect_name,
        followup_id=row.get("followup_id"),
        duration_seconds=row.get("duration_seconds"),
        created_at=row["created_at"]
    )


@router.delete("/{recording_id}", response_model=CancelRecordingResponse)
async def cancel_recording(
    recording_id: str,
    current_user: dict = Depends(get_current_user),
    user_org: tuple = Depends(get_user_org),
):
    """
    Cancel a scheduled recording.
    
    This will cancel the bot with Recall.ai and update the status to 'cancelled'.
    """
    user_id, org_id = user_org
    supabase = get_supabase_service()
    
    # Get the recording
    result = supabase.table("scheduled_recordings").select(
        "id, recall_bot_id, status, user_id"
    ).eq("id", recording_id).eq("organization_id", org_id).single().execute()
    
    if not result.data:
        raise HTTPException(status_code=404, detail="Recording not found")
    
    recording = result.data
    
    # Check if user owns this recording
    if recording["user_id"] != user_id:
        raise HTTPException(status_code=403, detail="Not authorized to cancel this recording")
    
    # Check if already cancelled or completed
    if recording["status"] in ["cancelled", "complete", "error"]:
        return CancelRecordingResponse(
            success=False,
            message=f"Recording is already {recording['status']}"
        )
    
    # Cancel with Recall.ai if we have a bot ID
    if recording.get("recall_bot_id") and recall_service.is_configured():
        cancel_result = await recall_service.cancel_bot(recording["recall_bot_id"])
        if not cancel_result.get("success"):
            logger.warning(f"Failed to cancel Recall.ai bot: {cancel_result.get('error')}")
    
    # Update status in database
    supabase.table("scheduled_recordings").update({
        "status": "cancelled"
    }).eq("id", recording_id).execute()
    
    logger.info(f"Cancelled scheduled recording: {recording_id}")
    
    return CancelRecordingResponse(
        success=True,
        message="Recording cancelled"
    )


# ==========================================
# Webhook Handler
# ==========================================

def verify_webhook_signature(payload: bytes, signature: str, msg_id: str = "", timestamp: str = "") -> bool:
    """
    Verify Recall.ai webhook signature using Svix protocol.
    
    Svix signature format:
    - Header: svix-signature (contains "v1,base64signature")
    - Signed message: "{msg_id}.{timestamp}.{payload}"
    - Secret format: "whsec_..." (base64 encoded)
    """
    import base64
    
    if not RECALL_WEBHOOK_SECRET:
        logger.warning("RECALL_WEBHOOK_SECRET not configured - accepting webhook without verification")
        return True
    
    if not signature:
        logger.warning("No signature provided in webhook")
        return False
    
    # Get the secret - Svix secrets start with "whsec_" and are base64 encoded
    secret = RECALL_WEBHOOK_SECRET
    if secret.startswith("whsec_"):
        secret = secret[6:]  # Remove "whsec_" prefix
    
    try:
        secret_bytes = base64.b64decode(secret)
    except Exception:
        # If not base64, use as-is (raw secret)
        secret_bytes = secret.encode()
    
    # Svix signed payload format: "{msg_id}.{timestamp}.{payload}"
    if msg_id and timestamp:
        signed_payload = f"{msg_id}.{timestamp}.".encode() + payload
    else:
        signed_payload = payload
    
    # Calculate expected signature
    expected_signature = hmac.new(
        secret_bytes,
        signed_payload,
        hashlib.sha256
    ).digest()
    
    # Check each signature in the header (format: "v1,sig1 v1,sig2")
    for sig in signature.split(" "):
        if sig.startswith("v1,"):
            sig_base64 = sig[3:]  # Remove "v1," prefix
            try:
                sig_bytes = base64.b64decode(sig_base64)
                if hmac.compare_digest(expected_signature, sig_bytes):
                    logger.info("Svix signature verified ✓")
                    return True
            except Exception:
                continue
    
    logger.warning("Webhook signature verification failed")
    return False


@router.post("/webhook/recall")
async def handle_recall_webhook(
    request: Request,
):
    """
    Handle webhooks from Recall.ai.
    
    Events:
    - bot.status_change: Bot status updates
    - bot.done: Recording complete
    """
    # Get raw body for signature verification
    body = await request.body()
    
    # Svix headers (used by Recall.ai)
    svix_id = request.headers.get("svix-id", "")
    svix_timestamp = request.headers.get("svix-timestamp", "")
    signature = request.headers.get("svix-signature", "")
    
    logger.info(f"Svix headers - id: {svix_id}, ts: {svix_timestamp}, sig: {signature[:40] if signature else 'none'}...")
    
    if not verify_webhook_signature(body, signature, svix_id, svix_timestamp):
        logger.warning("Invalid webhook signature")
        # For now, allow webhooks even with invalid signature if secret not set
        if RECALL_WEBHOOK_SECRET:
            raise HTTPException(status_code=401, detail="Invalid signature")
        else:
            logger.warning("RECALL_WEBHOOK_SECRET not set - accepting webhook anyway")
    
    # Parse payload
    try:
        payload = await request.json()
        logger.info(f"Webhook received: {payload}")
    except Exception as e:
        logger.error(f"Invalid JSON in webhook: {e}")
        raise HTTPException(status_code=400, detail="Invalid JSON")
    
    # Parse using recall_service (handles all payload formats)
    event_data = recall_service.parse_webhook_event(payload)
    bot_id = event_data.get("bot_id")
    
    if not bot_id:
        logger.warning(f"Webhook missing bot_id after parsing. Payload: {payload}")
        return {"status": "ignored", "reason": "no bot_id"}
    
    logger.info(f"Processing webhook for bot: {bot_id}, status: {event_data.get('status')}")
    
    supabase = get_supabase_service()
    
    # Find the recording by Recall bot ID (include all fields needed for Inngest)
    # Use limit(1) and check manually to avoid exception when no rows found
    result = supabase.table("scheduled_recordings").select(
        "id, status, organization_id, user_id, prospect_id, meeting_title, "
        "meeting_prep_id, contact_ids, deal_id, calendar_meeting_id"
    ).eq("recall_bot_id", bot_id).limit(1).execute()
    
    if not result.data or len(result.data) == 0:
        logger.warning(f"Recording not found for bot: {bot_id}")
        return {"status": "ignored", "reason": "recording not found"}
    
    recording = result.data[0]
    recording_id = recording["id"]
    new_status = event_data.get("status")
    
    # Update status
    update_data = {"status": new_status}
    
    if event_data.get("duration_seconds"):
        update_data["duration_seconds"] = event_data["duration_seconds"]
    
    if event_data.get("participants"):
        update_data["participants"] = event_data["participants"]
    
    supabase.table("scheduled_recordings").update(update_data).eq("id", recording_id).execute()
    
    logger.info(f"Updated recording {recording_id} status to: {new_status}")
    
    # If recording is complete, trigger Inngest processing
    if new_status == "complete":
        logger.info(f"Recording complete - triggering Inngest processing for {recording_id}")
        
        # Send Inngest event (handles download, upload, followup creation, transcription)
        if use_inngest_for("followup"):  # Use same feature flag as followup
            try:
                await send_event(
                    Events.AI_NOTETAKER_RECORDING_COMPLETE,
                    {
                        "recording_id": recording_id,
                        "bot_id": bot_id,
                        "organization_id": recording["organization_id"],
                        "user_id": recording["user_id"],
                        "prospect_id": recording.get("prospect_id"),
                        "meeting_title": recording.get("meeting_title"),
                        # Context fields (same as regular followup)
                        "meeting_prep_id": recording.get("meeting_prep_id"),
                        "contact_ids": recording.get("contact_ids") or [],
                        "deal_id": recording.get("deal_id"),
                        "calendar_meeting_id": recording.get("calendar_meeting_id"),
                    }
                )
                logger.info(f"Sent AI_NOTETAKER_RECORDING_COMPLETE event for {recording_id}")
            except Exception as e:
                logger.error(f"Failed to send Inngest event: {e}")
                # Fallback: mark as error
                supabase.table("scheduled_recordings").update({
                    "status": "error",
                    "error_message": f"Failed to trigger processing: {e}"
                }).eq("id", recording_id).execute()
        else:
            logger.warning("Inngest not enabled - cannot process recording")
            supabase.table("scheduled_recordings").update({
                "status": "error",
                "error_message": "Inngest not enabled"
            }).eq("id", recording_id).execute()
    
    return {"status": "ok"}


# ==========================================
# Inbound Email Webhook (Phase 2)
# ==========================================

@router.post("/webhook/inbound-email")
async def handle_inbound_email(request: Request):
    """
    Handle inbound email from SendGrid Inbound Parse.
    
    When a user invites notes@dealmotion.ai to a meeting, this endpoint:
    1. Receives the raw email from SendGrid
    2. Queues it for Inngest processing
    3. Returns quickly to satisfy SendGrid timeout requirements
    
    The actual processing (parse, match user, schedule bot) happens in Inngest.
    
    SendGrid Inbound Parse Configuration:
    - URL: https://api.dealmotion.ai/api/v1/ai-notetaker/webhook/inbound-email
    - Domain: dealmotion.ai (MX record pointing to SendGrid)
    """
    import base64
    
    try:
        # Get raw email data from SendGrid
        # SendGrid sends multipart/form-data with 'email' field containing raw MIME
        form_data = await request.form()
        
        # SendGrid fields: https://docs.sendgrid.com/for-developers/parsing-email/setting-up-the-inbound-parse-webhook
        raw_email = form_data.get("email", "")  # Raw MIME email
        sender = form_data.get("from", "")
        to_address = form_data.get("to", "")
        subject = form_data.get("subject", "")
        
        # Log receipt
        logger.info(f"Received inbound email: from={sender}, to={to_address}, subject={subject[:50] if subject else 'N/A'}")
        
        # Validate it's sent to our notetaker address
        # Includes both main domain and parse subdomain (for forwarding setup)
        notetaker_addresses = [
            "notes@dealmotion.ai", 
            "notes@parse.dealmotion.ai",
            "notetaker@dealmotion.ai", 
            "ai@dealmotion.ai"
        ]
        is_valid_recipient = any(addr in to_address.lower() for addr in notetaker_addresses)
        
        if not is_valid_recipient:
            logger.warning(f"Email not addressed to notetaker: {to_address}")
            return {"status": "ignored", "reason": "not addressed to notetaker"}
        
        # Encode raw email for Inngest (bytes not JSON serializable)
        if isinstance(raw_email, str):
            raw_email_b64 = base64.b64encode(raw_email.encode("utf-8")).decode("utf-8")
        else:
            raw_email_b64 = base64.b64encode(raw_email).decode("utf-8")
        
        # Queue for Inngest processing (fast response for SendGrid)
        await send_event(
            Events.AI_NOTETAKER_EMAIL_RECEIVED,
            {
                "raw_email_b64": raw_email_b64,
                "sender": sender,
                "to_address": to_address,
                "subject": subject,
                "received_at": datetime.utcnow().isoformat(),
            }
        )
        
        logger.info(f"Queued email invite for processing: from={sender}")
        
        return {"status": "queued"}
        
    except Exception as e:
        logger.error(f"Error handling inbound email: {e}")
        # Still return 200 to prevent SendGrid retries on our errors
        return {"status": "error", "message": str(e)}
