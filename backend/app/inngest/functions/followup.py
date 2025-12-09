"""
Follow-up Agent Inngest Functions.

Handles post-meeting follow-up workflows with full observability and automatic retries.

Events:
- dealmotion/followup.audio.uploaded: Triggers audio processing (transcribe + summarize)
- dealmotion/followup.transcript.uploaded: Triggers transcript processing (summarize only)
- dealmotion/followup.completed: Emitted when follow-up is done

Note: Email generation is handled separately via Follow-up Actions system.
"""

import logging
from typing import Optional, List, Dict, Any
from datetime import datetime
import inngest
from inngest import NonRetriableError, TriggerEvent

from app.inngest.client import inngest_client
from app.database import get_supabase_service
from app.services.transcription_service import get_transcription_service
from app.services.followup_generator import get_followup_generator
from app.services.prospect_context_service import get_prospect_context_service

logger = logging.getLogger(__name__)

# Database client
supabase = get_supabase_service()


# =============================================================================
# Function 1: Process Audio Upload (Transcribe + Summarize)
# =============================================================================

@inngest_client.create_function(
    fn_id="followup-process-audio",
    trigger=TriggerEvent(event="dealmotion/followup.audio.uploaded"),
    retries=2,
)
async def process_followup_audio_fn(ctx, step):
    """
    Process uploaded audio file: transcribe and generate summary.
    
    Steps:
    1. Update status to 'transcribing'
    2. Download audio from storage and transcribe
    3. Update status to 'summarizing'
    4. Get prospect context
    5. Generate summary with AI
    6. Extract action items
    7. Save results
    8. Emit completion event
    """
    event_data = ctx.event.data
    followup_id = event_data["followup_id"]
    storage_path = event_data["storage_path"]  # Path in Supabase Storage
    filename = event_data["filename"]
    organization_id = event_data["organization_id"]
    user_id = event_data["user_id"]
    meeting_prep_id = event_data.get("meeting_prep_id")
    prospect_company = event_data.get("prospect_company")
    include_coaching = event_data.get("include_coaching", False)
    language = event_data.get("language", "en")
    
    logger.info(f"Starting Inngest followup audio processing for {followup_id}")
    
    # Step 1: Update status to transcribing
    await step.run("update-status-transcribing", update_followup_status, followup_id, "transcribing")
    
    # Step 2: Download audio from storage and transcribe
    transcription_result = await step.run(
        "transcribe-audio",
        transcribe_audio_from_storage,
        storage_path, filename, language
    )
    
    # Validate transcription result
    if not transcription_result.get("full_text"):
        logger.error(f"Transcription returned empty text for followup {followup_id}")
        # Update status to failed and stop processing
        await step.run(
            "mark-failed-empty-transcription",
            mark_transcription_failed,
            followup_id, "Transcription returned empty text - audio may be too short, silent, or in unsupported format"
        )
        return {
            "followup_id": followup_id,
            "status": "failed",
            "error": "Empty transcription"
        }
    
    # Step 3: Update with transcription and change status
    await step.run(
        "save-transcription",
        save_transcription,
        followup_id, transcription_result
    )
    
    # Step 4: Get prospect context
    prospect_context = await step.run(
        "get-prospect-context",
        get_prospect_context,
        prospect_company, organization_id, user_id, meeting_prep_id
    )
    
    # Step 5: Generate summary
    summary = await step.run(
        "generate-summary",
        generate_followup_summary,
        transcription_result["full_text"], prospect_context, include_coaching, language, prospect_company
    )
    
    # Step 6: Extract action items
    action_items = await step.run(
        "extract-action-items",
        extract_action_items,
        transcription_result["full_text"], summary.get("executive_summary"), language
    )
    
    # Step 7: Save results (WITHOUT email - that's done via Actions)
    await step.run(
        "save-results",
        save_followup_results,
        followup_id, summary, action_items, include_coaching
    )
    
    # Step 8: Emit completion event
    await step.send_event(
        "emit-completion",
        inngest.Event(
            name="dealmotion/followup.completed",
            data={
                "followup_id": followup_id,
                "prospect_company": prospect_company,
                "organization_id": organization_id,
                "user_id": user_id,
                "success": True
            }
        )
    )
    
    logger.info(f"Followup audio processing completed for {followup_id}")
    
    return {
        "followup_id": followup_id,
        "status": "completed"
    }


# =============================================================================
# Function 2: Process Transcript Upload (Summarize only, no transcription)
# =============================================================================

@inngest_client.create_function(
    fn_id="followup-process-transcript",
    trigger=TriggerEvent(event="dealmotion/followup.transcript.uploaded"),
    retries=2,
)
async def process_followup_transcript_fn(ctx, step):
    """
    Process uploaded transcript: generate summary.
    
    Steps:
    1. Update status to 'summarizing'
    2. Get prospect context
    3. Generate summary with AI
    4. Extract action items
    5. Save results
    6. Emit completion event
    """
    event_data = ctx.event.data
    followup_id = event_data["followup_id"]
    transcription_text = event_data["transcription_text"]
    segments = event_data.get("segments", [])
    speaker_count = event_data.get("speaker_count", 1)
    organization_id = event_data["organization_id"]
    user_id = event_data["user_id"]
    meeting_prep_id = event_data.get("meeting_prep_id")
    prospect_company = event_data.get("prospect_company")
    include_coaching = event_data.get("include_coaching", False)
    language = event_data.get("language", "en")
    estimated_duration = event_data.get("estimated_duration")
    
    logger.info(f"Starting Inngest followup transcript processing for {followup_id}")
    
    # Step 1: Update status to summarizing and save transcript
    await step.run(
        "save-transcript-and-status",
        save_transcript_data,
        followup_id, transcription_text, segments, speaker_count, estimated_duration
    )
    
    # Step 2: Get prospect context
    prospect_context = await step.run(
        "get-prospect-context",
        get_prospect_context,
        prospect_company, organization_id, user_id, meeting_prep_id
    )
    
    # Step 3: Generate summary
    summary = await step.run(
        "generate-summary",
        generate_followup_summary,
        transcription_text, prospect_context, include_coaching, language, prospect_company
    )
    
    # Step 4: Extract action items
    action_items = await step.run(
        "extract-action-items",
        extract_action_items,
        transcription_text, summary.get("executive_summary"), language
    )
    
    # Step 5: Save results (WITHOUT email - that's done via Actions)
    await step.run(
        "save-results",
        save_followup_results,
        followup_id, summary, action_items, include_coaching
    )
    
    # Step 6: Emit completion event
    await step.send_event(
        "emit-completion",
        inngest.Event(
            name="dealmotion/followup.completed",
            data={
                "followup_id": followup_id,
                "prospect_company": prospect_company,
                "organization_id": organization_id,
                "user_id": user_id,
                "success": True
            }
        )
    )
    
    logger.info(f"Followup transcript processing completed for {followup_id}")
    
    return {
        "followup_id": followup_id,
        "status": "completed"
    }


# =============================================================================
# Step Functions (each is a discrete, retriable unit of work)
# =============================================================================

async def update_followup_status(followup_id: str, status: str) -> dict:
    """Update followup status in database."""
    supabase.table("followups").update({
        "status": status
    }).eq("id", followup_id).execute()
    return {"updated": True, "status": status}


async def mark_transcription_failed(followup_id: str, error_message: str) -> dict:
    """Mark followup as failed due to transcription error."""
    supabase.table("followups").update({
        "status": "failed",
        "error_message": error_message
    }).eq("id", followup_id).execute()
    logger.error(f"Followup {followup_id} marked as failed: {error_message}")
    return {"updated": True, "status": "failed"}


async def transcribe_audio_from_storage(storage_path: str, filename: str, language: str) -> dict:
    """Download audio from Supabase Storage and transcribe."""
    try:
        # Download audio from storage
        logger.info(f"Downloading audio from storage: {storage_path}")
        response = supabase.storage.from_("followup-audio").download(storage_path)
        audio_bytes = response
        
        if not audio_bytes:
            logger.error(f"Downloaded empty audio file from {storage_path}")
            raise NonRetriableError(f"Empty audio file downloaded from storage")
        
        logger.info(f"Downloaded {len(audio_bytes)} bytes, starting transcription for {filename}")
        
        transcription_service = get_transcription_service()
        result = await transcription_service.transcribe_audio_bytes(
            audio_bytes,
            filename,
            language=language
        )
        
        if not result.full_text:
            logger.warning(f"Transcription returned empty text for {filename}")
        else:
            logger.info(f"Transcription successful: {len(result.full_text)} chars, {result.speaker_count} speakers")
        
        # Convert segments to dict format
        segments = [
            {
                "speaker": seg.speaker,
                "start": seg.start,
                "end": seg.end,
                "text": seg.text
            }
            for seg in result.segments
        ]
        
        return {
            "full_text": result.full_text,
            "segments": segments,
            "speaker_count": result.speaker_count,
            "duration_seconds": int(result.duration_seconds)
        }
    except NonRetriableError:
        raise
    except Exception as e:
        logger.error(f"Transcription failed for {storage_path}: {e}", exc_info=True)
        raise NonRetriableError(f"Transcription failed: {e}")


async def save_transcription(followup_id: str, transcription_result: dict) -> dict:
    """Save transcription results and update status."""
    supabase.table("followups").update({
        "status": "summarizing",
        "transcription_text": transcription_result["full_text"],
        "transcription_segments": transcription_result["segments"],
        "speaker_count": transcription_result["speaker_count"],
        "audio_duration_seconds": transcription_result.get("duration_seconds")
    }).eq("id", followup_id).execute()
    return {"saved": True}


async def save_transcript_data(
    followup_id: str,
    transcription_text: str,
    segments: list,
    speaker_count: int,
    estimated_duration: Optional[float]
) -> dict:
    """Save transcript data and update status to summarizing."""
    supabase.table("followups").update({
        "status": "summarizing",
        "transcription_text": transcription_text,
        "transcription_segments": segments,
        "speaker_count": speaker_count,
        "audio_duration_seconds": int(estimated_duration) if estimated_duration else None
    }).eq("id", followup_id).execute()
    return {"saved": True}


async def get_prospect_context(
    prospect_company: Optional[str],
    organization_id: str,
    user_id: str,
    meeting_prep_id: Optional[str]
) -> Optional[dict]:
    """Get full prospect context using unified service."""
    try:
        context_service = get_prospect_context_service()
        context = await context_service.get_full_prospect_context(
            prospect_company=prospect_company or "Unknown",
            organization_id=organization_id,
            user_id=user_id,
            meeting_prep_id=meeting_prep_id,
            include_kb=True,
            max_kb_chunks=5
        )
        logger.info(
            f"Got prospect context: {context.get('context_completeness', 0)}% complete"
        )
        return context
    except Exception as e:
        logger.warning(f"Could not get prospect context: {e}")
        return None


async def generate_followup_summary(
    transcription_text: str,
    prospect_context: Optional[dict],
    include_coaching: bool,
    language: str,
    prospect_company: Optional[str]
) -> dict:
    """Generate meeting summary with AI."""
    try:
        followup_generator = get_followup_generator()
        summary = await followup_generator.generate_summary(
            transcription=transcription_text,
            prospect_context=prospect_context,
            include_coaching=include_coaching,
            language=language,
            prospect_company=prospect_company
        )
        logger.info(f"Generated summary for {prospect_company or 'unknown'}")
        return summary
    except Exception as e:
        logger.error(f"Summary generation failed: {e}")
        raise NonRetriableError(f"Summary generation failed: {e}")


async def extract_action_items(
    transcription_text: str,
    executive_summary: Optional[str],
    language: str
) -> List[Dict[str, Any]]:
    """Extract action items from transcription."""
    try:
        followup_generator = get_followup_generator()
        action_items = await followup_generator.extract_action_items(
            transcription=transcription_text,
            summary=executive_summary,
            language=language
        )
        logger.info(f"Extracted {len(action_items)} action items")
        return action_items
    except Exception as e:
        logger.error(f"Action item extraction failed: {e}")
        # Return empty list on failure, don't fail the whole workflow
        return []


async def save_followup_results(
    followup_id: str,
    summary: dict,
    action_items: List[dict],
    include_coaching: bool
) -> dict:
    """Save all followup results to database (without email - handled by Actions)."""
    try:
        update_data = {
            "status": "completed",
            "executive_summary": summary.get("executive_summary", ""),
            "key_points": summary.get("key_points", []),
            "concerns": summary.get("concerns", []),
            "decisions": summary.get("decisions", []),
            "next_steps": summary.get("next_steps", []),
            "action_items": action_items,
            "completed_at": datetime.utcnow().isoformat(),
            # Enhanced follow-up fields
            "commercial_signals": summary.get("commercial_signals", {}),
            "observations": summary.get("observations", {}),
            "full_summary_content": summary.get("full_content", "")
        }
        
        # Only save coaching if requested
        if include_coaching:
            update_data["coaching_feedback"] = summary.get("coaching_feedback", {})
            update_data["include_coaching"] = True
        
        supabase.table("followups").update(update_data).eq("id", followup_id).execute()
        
        logger.info(f"Saved followup results for {followup_id}")
        return {"saved": True}
    except Exception as e:
        logger.error(f"Failed to save followup results: {e}")
        # Mark as failed
        supabase.table("followups").update({
            "status": "failed",
            "error_message": str(e)
        }).eq("id", followup_id).execute()
        raise NonRetriableError(f"Failed to save results: {e}")

