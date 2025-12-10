"""
AI Notetaker Inngest Functions.

Handles processing of AI Notetaker recordings from Recall.ai.

Events:
- dealmotion/ai-notetaker.recording.complete: Triggered when bot finishes recording

Flow:
1. Fetch recording URL from Recall.ai API
2. Download recording
3. Upload to Supabase Storage
4. Create followup record
5. Trigger transcription pipeline (via FOLLOWUP_AUDIO_UPLOADED)
"""

import logging
from datetime import datetime
from inngest import TriggerEvent

from app.inngest.client import inngest_client
from app.inngest.events import send_event, Events
from app.database import get_supabase_service
from app.services.recall_service import recall_service

logger = logging.getLogger(__name__)


# =============================================================================
# Helper Functions
# =============================================================================

def update_scheduled_recording_status(recording_id: str, status: str, error_message: str = None):
    """Update the status of a scheduled recording."""
    supabase = get_supabase_service()
    update_data = {"status": status}
    if error_message:
        update_data["error_message"] = error_message
    supabase.table("scheduled_recordings").update(update_data).eq("id", recording_id).execute()
    logger.info(f"Updated scheduled_recording {recording_id} status to: {status}")


async def fetch_recording_url(bot_id: str):
    """Fetch recording URL from Recall.ai API."""
    bot_status = await recall_service.get_bot_status(bot_id)
    
    if not bot_status.get("success"):
        raise Exception(f"Failed to get bot status: {bot_status.get('error')}")
    
    recording = bot_status.get("recording") or {}
    if not isinstance(recording, dict):
        recording = {}
    
    recording_url = recording.get("url") or recording.get("download_url")
    duration = recording.get("duration_seconds") or recording.get("duration") or 0
    
    if not recording_url:
        raise Exception(f"No recording URL found. Response: {bot_status}")
    
    return {
        "recording_url": recording_url,
        "duration_seconds": duration
    }


async def download_and_upload_recording(recording_url: str, organization_id: str, recording_id: str):
    """
    Download recording from Recall.ai and upload to Supabase Storage.
    Combined into one step because bytes are not JSON-serializable for Inngest.
    """
    # Download
    audio_data = await recall_service.download_recording(recording_url)
    
    if not audio_data:
        raise Exception("Failed to download recording from Recall.ai")
    
    logger.info(f"Downloaded {len(audio_data)} bytes")
    
    # Upload
    supabase = get_supabase_service()
    storage_path = f"{organization_id}/{recording_id}/recording.mp4"
    
    storage_result = supabase.storage.from_("followup-audio").upload(
        storage_path,
        audio_data,
        {"content-type": "video/mp4"}
    )
    
    if hasattr(storage_result, 'error') and storage_result.error:
        raise Exception(f"Failed to upload to storage: {storage_result.error}")
    
    audio_url = supabase.storage.from_("followup-audio").get_public_url(storage_path)
    logger.info(f"Uploaded to: {audio_url[:50]}...")
    
    return {
        "storage_path": storage_path,
        "audio_url": audio_url
    }


def create_followup_record(organization_id: str, user_id: str, prospect_id: str, meeting_title: str, audio_url: str):
    """Create a followup record for the AI Notetaker recording."""
    supabase = get_supabase_service()
    
    followup_data = {
        "organization_id": organization_id,
        "user_id": user_id,
        "prospect_id": prospect_id,
        "meeting_subject": meeting_title or "AI Notetaker Recording",
        "audio_url": audio_url,
        "status": "pending"
    }
    
    result = supabase.table("followups").insert(followup_data).execute()
    
    if not result.data:
        raise Exception("Failed to create followup record")
    
    followup_id = result.data[0]["id"]
    logger.info(f"Created followup: {followup_id}")
    
    return followup_id


def update_scheduled_recording_complete(recording_id: str, followup_id: str, audio_url: str, duration_seconds: int):
    """Update scheduled recording with completion data."""
    supabase = get_supabase_service()
    
    supabase.table("scheduled_recordings").update({
        "status": "complete",
        "followup_id": followup_id,
        "recording_url": audio_url,
        "duration_seconds": duration_seconds,
        "completed_at": datetime.utcnow().isoformat()
    }).eq("id", recording_id).execute()
    
    logger.info(f"Marked scheduled_recording {recording_id} as complete")


# =============================================================================
# Main Inngest Function
# =============================================================================

@inngest_client.create_function(
    fn_id="ai-notetaker-process-recording",
    trigger=TriggerEvent(event="dealmotion/ai-notetaker.recording.complete"),
    retries=3,  # More retries for network operations
)
async def process_ai_notetaker_recording_fn(ctx, step):
    """
    Process a completed AI Notetaker recording.
    
    Steps:
    1. Fetch recording URL from Recall.ai
    2. Download recording
    3. Upload to Supabase Storage
    4. Create followup record
    5. Trigger transcription pipeline
    """
    event_data = ctx.event.data
    recording_id = event_data["recording_id"]
    bot_id = event_data["bot_id"]
    organization_id = event_data["organization_id"]
    user_id = event_data["user_id"]
    prospect_id = event_data.get("prospect_id")
    meeting_title = event_data.get("meeting_title")
    
    logger.info(f"Starting AI Notetaker processing for recording {recording_id}, bot {bot_id}")
    
    try:
        # Step 1: Fetch recording URL from Recall.ai
        recording_info = await step.run(
            "fetch-recording-url",
            fetch_recording_url,
            bot_id
        )
        
        recording_url = recording_info["recording_url"]
        duration_seconds = recording_info["duration_seconds"]
        
        # Step 2: Download and upload recording (combined - bytes not serializable)
        upload_result = await step.run(
            "download-and-upload",
            download_and_upload_recording,
            recording_url, organization_id, recording_id
        )
        
        storage_path = upload_result["storage_path"]
        audio_url = upload_result["audio_url"]
        
        # Step 3: Create followup record
        followup_id = await step.run(
            "create-followup",
            create_followup_record,
            organization_id, user_id, prospect_id, meeting_title, audio_url
        )
        
        # Step 4: Update scheduled_recording as complete
        await step.run(
            "mark-complete",
            update_scheduled_recording_complete,
            recording_id, followup_id, audio_url, duration_seconds
        )
        
        # Step 5: Trigger transcription pipeline
        await step.run(
            "trigger-transcription",
            send_event,
            Events.FOLLOWUP_AUDIO_UPLOADED,
            {
                "followup_id": followup_id,
                "storage_path": storage_path,
                "filename": "recording.mp4",
                "organization_id": organization_id,
                "user_id": user_id,
            }
        )
        
        logger.info(f"AI Notetaker processing complete for {recording_id} -> followup {followup_id}")
        
        return {
            "recording_id": recording_id,
            "followup_id": followup_id,
            "status": "complete"
        }
        
    except Exception as e:
        logger.error(f"AI Notetaker processing failed for {recording_id}: {e}")
        
        # Mark as error
        await step.run(
            "mark-error",
            update_scheduled_recording_status,
            recording_id, "error", str(e)
        )
        
        raise  # Re-raise for Inngest retry

