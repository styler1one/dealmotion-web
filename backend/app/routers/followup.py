"""
Follow-up Router - API endpoints for post-meeting follow-ups

Handles audio upload, transcription, summary generation, and email drafts.
"""

from fastapi import APIRouter, HTTPException, Depends, UploadFile, File, Form, BackgroundTasks, Request
from pydantic import BaseModel
from typing import Optional, List, Dict, Any
from datetime import datetime
import logging
import uuid
import asyncio
from slowapi import Limiter
from slowapi.util import get_remote_address

from app.deps import get_current_user
from app.database import get_supabase_service
from app.utils.errors import handle_exception

# Rate limiter
limiter = Limiter(key_func=get_remote_address)
from app.services.transcription_service import get_transcription_service
from app.services.followup_generator import get_followup_generator
from app.services.transcript_parser import get_transcript_parser
from app.services.prospect_context_service import get_prospect_context_service
from app.services.prospect_service import get_prospect_service
from app.services.usage_service import get_usage_service

# Inngest integration
from app.inngest.events import send_event, use_inngest_for, Events

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/followup", tags=["followup"])

# Use centralized database module
supabase = get_supabase_service()


# Request/Response models
class FollowupResponse(BaseModel):
    id: str
    status: str
    message: str


class FollowupDetail(BaseModel):
    id: str
    organization_id: str
    user_id: str
    meeting_prep_id: Optional[str]
    audio_url: Optional[str]
    audio_filename: Optional[str]
    transcription_text: Optional[str]
    transcription_segments: List[Dict[str, Any]]
    speaker_count: int
    executive_summary: Optional[str]
    key_points: List[str]
    concerns: List[str]
    decisions: List[str]
    next_steps: List[str]
    action_items: List[Dict[str, Any]]
    email_draft: Optional[str]
    email_tone: str
    meeting_date: Optional[str]
    prospect_company_name: Optional[str]
    status: str
    error_message: Optional[str]
    created_at: str
    completed_at: Optional[str]
    # Enhanced follow-up fields
    commercial_signals: Optional[Dict[str, Any]] = None
    observations: Optional[Dict[str, Any]] = None
    coaching_feedback: Optional[Dict[str, Any]] = None
    full_summary_content: Optional[str] = None


class UpdateFollowupRequest(BaseModel):
    action_items: Optional[List[Dict[str, Any]]] = None
    email_draft: Optional[str] = None
    email_tone: Optional[str] = None
    meeting_subject: Optional[str] = None
    executive_summary: Optional[str] = None
    full_summary_content: Optional[str] = None


class RegenerateEmailRequest(BaseModel):
    tone: str = "professional"


# Background task for processing (sync wrapper for BackgroundTasks)
def process_followup_background(
    followup_id: str,
    audio_data: bytes,
    filename: str,
    organization_id: str,
    user_id: str,
    meeting_prep_id: Optional[str] = None,
    prospect_company: Optional[str] = None,
    language: str = "en"  # i18n: output language (default: English)
):
    """Background task to process audio and generate follow-up content.
    
    This is a sync function that runs async code via asyncio.run().
    This pattern ensures BackgroundTasks properly runs it in a separate thread.
    """
    asyncio.run(_process_followup_async(
        followup_id, audio_data, filename, organization_id, user_id,
        meeting_prep_id, prospect_company, language
    ))


async def _process_followup_async(
    followup_id: str,
    audio_data: bytes,
    filename: str,
    organization_id: str,
    user_id: str,
    meeting_prep_id: Optional[str] = None,
    prospect_company: Optional[str] = None,
    language: str = "en"
):
    """Actual async processing logic for follow-up"""
    try:
        # Update status to transcribing
        supabase.table("followups").update({
            "status": "transcribing"
        }).eq("id", followup_id).execute()
        
        # Step 1: Upload audio to Supabase Storage
        storage_path = f"{organization_id}/{followup_id}/{filename}"
        
        supabase.storage.from_("followup-audio").upload(
            storage_path,
            audio_data,
            {"content-type": _get_content_type(filename)}
        )
        
        # Get public URL (signed URL for private bucket)
        audio_url = supabase.storage.from_("followup-audio").create_signed_url(
            storage_path,
            expires_in=86400 * 7  # 7 days
        )
        audio_url = audio_url.get("signedURL", "")
        
        # Update with audio URL
        supabase.table("followups").update({
            "audio_url": audio_url,
            "audio_filename": filename,
            "audio_size_bytes": len(audio_data)
        }).eq("id", followup_id).execute()
        
        # Step 2: Transcribe audio
        transcription_service = get_transcription_service()
        transcription_result = await transcription_service.transcribe_audio_bytes(
            audio_data,
            filename,
            language=language  # Use the language from request
        )
        
        # Convert segments to dict format
        segments = [
            {
                "speaker": seg.speaker,
                "start": seg.start,
                "end": seg.end,
                "text": seg.text
            }
            for seg in transcription_result.segments
        ]
        
        # Update with transcription
        supabase.table("followups").update({
            "status": "summarizing",
            "transcription_text": transcription_result.full_text,
            "transcription_segments": segments,
            "speaker_count": transcription_result.speaker_count,
            "audio_duration_seconds": int(transcription_result.duration_seconds)
        }).eq("id", followup_id).execute()
        
        # Step 3: Get FULL prospect context using new unified service
        prospect_context = None
        
        try:
            context_service = get_prospect_context_service()
            prospect_context = await context_service.get_full_prospect_context(
                prospect_company=prospect_company or "Unknown",
                organization_id=organization_id,
                user_id=user_id,
                meeting_prep_id=meeting_prep_id,
                include_kb=True,
                max_kb_chunks=5
            )
            logger.info(
                f"Got full prospect context: {prospect_context.get('context_completeness', 0)}% complete, "
                f"sources: {prospect_context.get('available_sources', [])}"
            )
        except Exception as e:
            logger.warning(f"Could not get full prospect context: {e}")
            # Fall back to basic context
            prospect_context = None
        
        # Step 4: Generate summary with full context (including enhanced sections)
        followup_generator = get_followup_generator()
        
        summary = await followup_generator.generate_summary(
            transcription=transcription_result.full_text,
            prospect_context=prospect_context,
            language=language,
            prospect_company=prospect_company
        )
        
        # Step 5: Extract action items
        action_items = await followup_generator.extract_action_items(
            transcription=transcription_result.full_text,
            summary=summary.get("executive_summary"),
            language=language  # i18n: output language
        )
        
        # Step 6: Generate email draft with full context
        email_draft = await followup_generator.generate_email_draft(
            summary=summary,
            action_items=action_items,
            prospect_context=prospect_context,
            language=language,  # i18n: output language
            prospect_company=prospect_company,
            tone="professional"
        )
        
        # Step 7: Save all results
        update_data = {
            "status": "completed",
            "executive_summary": summary.get("executive_summary", ""),
            "key_points": summary.get("key_points", []),
            "concerns": summary.get("concerns", []),
            "decisions": summary.get("decisions", []),
            "next_steps": summary.get("next_steps", []),
            "action_items": action_items,
            "email_draft": email_draft,
            "completed_at": datetime.utcnow().isoformat(),
            "commercial_signals": summary.get("commercial_signals", {}),
            "observations": summary.get("observations", {}),
            "full_summary_content": summary.get("full_content", "")
        }
        
        supabase.table("followups").update(update_data).eq("id", followup_id).execute()
        
        logger.info(f"Successfully processed followup {followup_id}")
        
    except Exception as e:
        logger.error(f"Error processing followup {followup_id}: {e}")
        supabase.table("followups").update({
            "status": "failed",
            "error_message": str(e)
        }).eq("id", followup_id).execute()


def _get_content_type(filename: str) -> str:
    """Get MIME type from filename"""
    ext = filename.lower().split(".")[-1]
    content_types = {
        "mp3": "audio/mpeg",
        "m4a": "audio/mp4",
        "wav": "audio/wav",
        "webm": "audio/webm",
    }
    return content_types.get(ext, "audio/mpeg")


# API Endpoints

@router.post("/upload", response_model=FollowupResponse, status_code=202)
@limiter.limit("5/minute")
async def upload_audio(
    request: Request,  # Required for rate limiting
    background_tasks: BackgroundTasks,
    file: UploadFile = File(...),
    meeting_prep_id: Optional[str] = Form(None),
    prospect_company_name: Optional[str] = Form(None),
    meeting_date: Optional[str] = Form(None),
    meeting_subject: Optional[str] = Form(None),
    contact_ids: Optional[str] = Form(None),  # Comma-separated contact UUIDs
    deal_id: Optional[str] = Form(None),  # Optional deal to link this follow-up to
    calendar_meeting_id: Optional[str] = Form(None),  # Link to calendar meeting (SPEC-038)
    language: str = Form("en"),  # i18n: output language (default: English)
    current_user: dict = Depends(get_current_user)
):
    """
    Upload audio file for transcription and follow-up generation.
    
    Rate limited to 5 requests per minute.
    
    Returns immediately with followup ID, processing happens in background
    """
    try:
        # Get user ID from JWT
        user_id = current_user.get("sub") or current_user.get("id")
        if not user_id:
            raise HTTPException(status_code=401, detail="Could not get user ID")
        
        # Validate file type (check base MIME type, ignoring codec parameters)
        allowed_base_types = ["audio/mpeg", "audio/mp4", "audio/wav", "audio/webm", "audio/x-m4a", "audio/ogg"]
        content_type = file.content_type or ""
        # Extract base type (e.g., "audio/webm" from "audio/webm;codecs=opus")
        base_type = content_type.split(";")[0].strip()
        if base_type not in allowed_base_types:
            raise HTTPException(
                status_code=400,
                detail=f"Invalid file type: {content_type}. Allowed: mp3, m4a, wav, webm, ogg"
            )
        
        # Get user's organization
        org_response = supabase.table("organization_members").select(
            "organization_id"
        ).eq("user_id", user_id).limit(1).execute()
        
        if not org_response.data:
            raise HTTPException(status_code=404, detail="User not in any organization")
        
        organization_id = org_response.data[0]["organization_id"]
        
        # Check subscription limit (v3: includes flow pack balance)
        usage_service = get_usage_service()
        limit_check = await usage_service.check_flow_limit(organization_id)
        if not limit_check.get("allowed"):
            raise HTTPException(
                status_code=402,  # Payment Required
                detail={
                    "error": "limit_exceeded",
                    "message": "You have reached your follow-up limit for this month",
                    "current": limit_check.get("current", 0),
                    "limit": limit_check.get("limit", 0),
                    "flow_pack_balance": limit_check.get("flow_pack_balance", 0),
                    "upgrade_url": "/pricing"
                }
            )
        
        # Track whether we should use flow pack for this upload
        use_flow_pack = limit_check.get("using_flow_pack", False)
        
        # Check credits BEFORE starting (v4: credit-based system)
        # Minimum check: ~3 credits for 5-min transcription + summary
        from app.services.credit_service import get_credit_service
        credit_service = get_credit_service()
        has_credits, credit_balance = await credit_service.check_credits(
            organization_id=organization_id,
            action="followup_start"
        )
        if not has_credits:
            raise HTTPException(
                status_code=402,
                detail={
                    "error": "insufficient_credits",
                    "message": "Not enough credits for follow-up processing",
                    "required": credit_balance.get("required_credits", 3),
                    "available": credit_balance.get("total_credits_available", 0),
                    "action": "followup_start"
                }
            )
        
        # Read file data
        audio_data = await file.read()
        
        # Check file size (50MB limit)
        if len(audio_data) > 50 * 1024 * 1024:
            raise HTTPException(status_code=413, detail="File too large. Max 50MB.")
        
        # Get or create prospect (NEW!)
        prospect_id = None
        if prospect_company_name:
            prospect_service = get_prospect_service()
            prospect_id = prospect_service.get_or_create_prospect(
                organization_id=organization_id,
                company_name=prospect_company_name
            )
        
        # Parse contact_ids from comma-separated string
        parsed_contact_ids = []
        if contact_ids:
            parsed_contact_ids = [cid.strip() for cid in contact_ids.split(",") if cid.strip()]
        
        # Create followup record with prospect_id and contact_ids
        followup_data = {
            "organization_id": organization_id,
            "user_id": user_id,
            "prospect_id": prospect_id,  # Link to prospect!
            "meeting_prep_id": meeting_prep_id,
            "calendar_meeting_id": calendar_meeting_id,  # Link to calendar meeting (SPEC-038)
            "prospect_company_name": prospect_company_name,
            "meeting_date": meeting_date,
            "meeting_subject": meeting_subject,
            "deal_id": deal_id,  # Link to deal (optional)
            "status": "uploading",
            "audio_filename": file.filename,
            "contact_ids": parsed_contact_ids  # Store linked contacts
        }
        
        response = supabase.table("followups").insert(followup_data).execute()
        
        if not response.data:
            raise HTTPException(status_code=500, detail="Failed to create followup")
        
        followup = response.data[0]
        followup_id = followup["id"]
        
        # Update reverse link in calendar_meetings (SPEC-038)
        if calendar_meeting_id:
            try:
                supabase.table("calendar_meetings").update({
                    "followup_id": followup_id
                }).eq("id", calendar_meeting_id).eq(
                    "organization_id", organization_id
                ).execute()
                logger.info(f"Linked followup {followup_id} to calendar meeting {calendar_meeting_id}")
            except Exception as e:
                logger.warning(f"Failed to link followup to calendar meeting: {e}")
        
        # Upload audio to storage first
        storage_path = f"{organization_id}/{followup_id}/{file.filename}"
        
        supabase.storage.from_("followup-audio").upload(
            storage_path,
            audio_data,
            {"content-type": _get_content_type(file.filename)}
        )
        
        # Get signed URL for the audio
        audio_url = supabase.storage.from_("followup-audio").create_signed_url(
            storage_path,
            expires_in=86400 * 7  # 7 days
        )
        audio_url = audio_url.get("signedURL", "")
        
        # Update with audio URL
        supabase.table("followups").update({
            "audio_url": audio_url,
            "audio_filename": file.filename,
            "audio_size_bytes": len(audio_data)
        }).eq("id", followup_id).execute()
        
        # Start processing via Inngest (if enabled) or BackgroundTasks (fallback)
        if use_inngest_for("followup"):
            event_sent = await send_event(
                Events.FOLLOWUP_AUDIO_UPLOADED,
                {
                    "followup_id": followup_id,
                    "storage_path": storage_path,
                    "filename": file.filename,
                    "organization_id": organization_id,
                    "user_id": user_id,
                    "meeting_prep_id": meeting_prep_id,
                    "prospect_company": prospect_company_name,
                    "language": language
                },
                user={"id": user_id}
            )
            
            if event_sent:
                logger.info(f"Followup {followup_id} triggered via Inngest")
            else:
                # Fallback to BackgroundTasks if Inngest fails
                logger.warning(f"Inngest event failed, falling back to BackgroundTasks for followup {followup_id}")
                background_tasks.add_task(
                    process_followup_background,
                    followup_id,
                    audio_data,
                    file.filename,
                    organization_id,
                    user_id,
                    meeting_prep_id,
                    prospect_company_name,
                    language
                )
        else:
            # Use BackgroundTasks (legacy/fallback)
            background_tasks.add_task(
                process_followup_background,
                followup_id,
                audio_data,
                file.filename,
                organization_id,
                user_id,
                meeting_prep_id,
                prospect_company_name,
                language
            )
            logger.info(f"Followup {followup_id} triggered via BackgroundTasks")
        
        # Increment usage counter
        await usage_service.increment_usage(organization_id, "followup")
        
        logger.info(f"Created followup {followup_id} for prospect {prospect_id}")
        
        return FollowupResponse(
            id=followup_id,
            status="uploading",
            message="Audio uploaded, processing started"
        )
        
    except HTTPException:
        raise
    except Exception as e:
        raise handle_exception(e, "followup_upload", user_id=user_id)


# Background task for transcript processing (sync wrapper for BackgroundTasks)
def process_transcript_background(
    followup_id: str,
    transcription_text: str,
    segments: list,
    speaker_count: int,
    organization_id: str,
    user_id: str,
    meeting_prep_id: Optional[str] = None,
    prospect_company: Optional[str] = None,
    estimated_duration: Optional[float] = None,
    language: str = "en"
):
    """Background task to process transcript and generate follow-up content.
    
    This is a sync function that runs async code via asyncio.run().
    This pattern ensures BackgroundTasks properly runs it in a separate thread.
    """
    asyncio.run(_process_transcript_async(
        followup_id, transcription_text, segments, speaker_count,
        organization_id, user_id, meeting_prep_id, prospect_company,
        estimated_duration, language
    ))


async def _process_transcript_async(
    followup_id: str,
    transcription_text: str,
    segments: list,
    speaker_count: int,
    organization_id: str,
    user_id: str,
    meeting_prep_id: Optional[str] = None,
    prospect_company: Optional[str] = None,
    estimated_duration: Optional[float] = None,
    language: str = "en"
):
    """Actual async processing logic for transcript"""
    try:
        # Update status to summarizing
        supabase.table("followups").update({
            "status": "summarizing",
            "transcription_text": transcription_text,
            "transcription_segments": segments,
            "speaker_count": speaker_count,
            "audio_duration_seconds": int(estimated_duration) if estimated_duration else None
        }).eq("id", followup_id).execute()
        
        # Get FULL prospect context using new unified service
        prospect_context = None
        
        try:
            context_service = get_prospect_context_service()
            prospect_context = await context_service.get_full_prospect_context(
                prospect_company=prospect_company or "Unknown",
                organization_id=organization_id,
                user_id=user_id,
                meeting_prep_id=meeting_prep_id,
                include_kb=True,
                max_kb_chunks=5
            )
            logger.info(
                f"Got full prospect context for transcript: {prospect_context.get('context_completeness', 0)}% complete"
            )
        except Exception as e:
            logger.warning(f"Could not get full prospect context: {e}")
            prospect_context = None
        
        # Generate summary with full context (including enhanced sections)
        followup_generator = get_followup_generator()
        
        summary = await followup_generator.generate_summary(
            transcription=transcription_text,
            prospect_context=prospect_context,
            language=language,
            prospect_company=prospect_company
        )
        
        # Extract action items
        action_items = await followup_generator.extract_action_items(
            transcription=transcription_text,
            summary=summary.get("executive_summary"),
            language=language
        )
        
        # Generate email draft with full context
        email_draft = await followup_generator.generate_email_draft(
            summary=summary,
            action_items=action_items,
            prospect_context=prospect_context,
            language=language,
            prospect_company=prospect_company,
            tone="professional"
        )
        
        # Save all results
        update_data = {
            "status": "completed",
            "executive_summary": summary.get("executive_summary", ""),
            "key_points": summary.get("key_points", []),
            "concerns": summary.get("concerns", []),
            "decisions": summary.get("decisions", []),
            "next_steps": summary.get("next_steps", []),
            "action_items": action_items,
            "email_draft": email_draft,
            "completed_at": datetime.utcnow().isoformat(),
            "commercial_signals": summary.get("commercial_signals", {}),
            "observations": summary.get("observations", {}),
            "full_summary_content": summary.get("full_content", "")
        }
        
        supabase.table("followups").update(update_data).eq("id", followup_id).execute()
        
        logger.info(f"Successfully processed transcript followup {followup_id}")
        
    except Exception as e:
        logger.error(f"Error processing transcript followup {followup_id}: {e}")
        supabase.table("followups").update({
            "status": "failed",
            "error_message": str(e)
        }).eq("id", followup_id).execute()


@router.post("/upload-transcript", response_model=FollowupResponse, status_code=202)
@limiter.limit("5/minute")
async def upload_transcript(
    request: Request,  # Required for rate limiting
    background_tasks: BackgroundTasks,
    file: UploadFile = File(...),
    meeting_prep_id: Optional[str] = Form(None),
    prospect_company_name: Optional[str] = Form(None),
    meeting_date: Optional[str] = Form(None),
    meeting_subject: Optional[str] = Form(None),
    contact_ids: Optional[str] = Form(None),  # Comma-separated contact UUIDs
    deal_id: Optional[str] = Form(None),  # Optional deal to link this follow-up to
    language: str = Form("en"),  # i18n: output language (default: English)
    current_user: dict = Depends(get_current_user)
):
    """
    Upload transcript file for summary and follow-up generation.
    
    Rate limited to 5 requests per minute.
    
    Supports: .txt, .md, .docx, .srt files
    Returns immediately with followup ID, processing happens in background
    """
    try:
        # Get user ID from JWT
        user_id = current_user.get("sub") or current_user.get("id")
        if not user_id:
            raise HTTPException(status_code=401, detail="Could not get user ID")
        
        # Validate file type
        allowed_extensions = ["txt", "md", "docx", "srt"]
        file_ext = file.filename.lower().split(".")[-1] if file.filename else ""
        if file_ext not in allowed_extensions:
            raise HTTPException(
                status_code=400,
                detail=f"Invalid file type. Allowed: {', '.join(allowed_extensions)}"
            )
        
        # Get user's organization
        org_response = supabase.table("organization_members").select(
            "organization_id"
        ).eq("user_id", user_id).limit(1).execute()
        
        if not org_response.data:
            raise HTTPException(status_code=404, detail="User not in any organization")
        
        organization_id = org_response.data[0]["organization_id"]
        
        # Check subscription limit (v3: includes flow pack balance)
        usage_service = get_usage_service()
        limit_check = await usage_service.check_flow_limit(organization_id)
        if not limit_check.get("allowed"):
            raise HTTPException(
                status_code=402,  # Payment Required
                detail={
                    "error": "limit_exceeded",
                    "message": "You have reached your follow-up limit for this month",
                    "current": limit_check.get("current", 0),
                    "limit": limit_check.get("limit", 0),
                    "flow_pack_balance": limit_check.get("flow_pack_balance", 0),
                    "upgrade_url": "/pricing"
                }
            )
        
        # Track whether we should use flow pack for this upload
        use_flow_pack = limit_check.get("using_flow_pack", False)
        
        # Check credits BEFORE starting (v4: credit-based system)
        # For transcript upload: only summary needed (2 credits)
        from app.services.credit_service import get_credit_service
        credit_service = get_credit_service()
        has_credits, credit_balance = await credit_service.check_credits(
            organization_id=organization_id,
            action="followup"  # 2 credits for summary
        )
        if not has_credits:
            raise HTTPException(
                status_code=402,
                detail={
                    "error": "insufficient_credits",
                    "message": "Not enough credits for follow-up processing",
                    "required": credit_balance.get("required_credits", 2),
                    "available": credit_balance.get("total_credits_available", 0),
                    "action": "followup"
                }
            )
        
        # Read file data
        file_data = await file.read()
        
        # Check file size (10MB limit for text files)
        if len(file_data) > 10 * 1024 * 1024:
            raise HTTPException(status_code=413, detail="File too large. Max 10MB.")
        
        # Parse transcript
        parser = get_transcript_parser()
        parsed = parser.parse_file(file_data, file.filename)
        
        # Convert segments to dict format
        segments = [
            {
                "speaker": seg.speaker,
                "start": seg.start,
                "end": seg.end,
                "text": seg.text
            }
            for seg in parsed.segments
        ]
        
        # Get or create prospect (NEW!)
        prospect_id = None
        if prospect_company_name:
            prospect_service = get_prospect_service()
            prospect_id = prospect_service.get_or_create_prospect(
                organization_id=organization_id,
                company_name=prospect_company_name
            )
        
        # Parse contact_ids from comma-separated string
        parsed_contact_ids = []
        if contact_ids:
            parsed_contact_ids = [cid.strip() for cid in contact_ids.split(",") if cid.strip()]
        
        # Create followup record with prospect_id and contact_ids
        followup_data = {
            "organization_id": organization_id,
            "user_id": user_id,
            "prospect_id": prospect_id,  # Link to prospect!
            "meeting_prep_id": meeting_prep_id,
            "prospect_company_name": prospect_company_name,
            "meeting_date": meeting_date,
            "meeting_subject": meeting_subject,
            "deal_id": deal_id,  # Link to deal (optional)
            "status": "summarizing",
            "audio_filename": file.filename,  # Store transcript filename
            "contact_ids": parsed_contact_ids  # Store linked contacts
        }
        
        response = supabase.table("followups").insert(followup_data).execute()
        
        if not response.data:
            raise HTTPException(status_code=500, detail="Failed to create followup")
        
        followup = response.data[0]
        followup_id = followup["id"]
        
        # Start processing via Inngest (if enabled) or BackgroundTasks (fallback)
        if use_inngest_for("followup"):
            event_sent = await send_event(
                Events.FOLLOWUP_TRANSCRIPT_UPLOADED,
                {
                    "followup_id": followup_id,
                    "transcription_text": parsed.full_text,
                    "segments": segments,
                    "speaker_count": parsed.speaker_count,
                    "organization_id": organization_id,
                    "user_id": user_id,
                    "meeting_prep_id": meeting_prep_id,
                    "prospect_company": prospect_company_name,
                    "language": language,
                    "estimated_duration": parsed.estimated_duration
                },
                user={"id": user_id}
            )
            
            if event_sent:
                logger.info(f"Transcript followup {followup_id} triggered via Inngest")
            else:
                # Fallback to BackgroundTasks if Inngest fails
                logger.warning(f"Inngest event failed, falling back to BackgroundTasks for followup {followup_id}")
                background_tasks.add_task(
                    process_transcript_background,
                    followup_id,
                    parsed.full_text,
                    segments,
                    parsed.speaker_count,
                    organization_id,
                    user_id,
                    meeting_prep_id,
                    prospect_company_name,
                    parsed.estimated_duration,
                    language
                )
        else:
            # Use BackgroundTasks (legacy/fallback)
            background_tasks.add_task(
                process_transcript_background,
                followup_id,
                parsed.full_text,
                segments,
                parsed.speaker_count,
                organization_id,
                user_id,
                meeting_prep_id,
                prospect_company_name,
                parsed.estimated_duration,
                language
            )
            logger.info(f"Transcript followup {followup_id} triggered via BackgroundTasks")
        
        # Increment usage counter
        await usage_service.increment_usage(organization_id, "followup")
        
        logger.info(f"Created transcript followup {followup_id} for prospect {prospect_id}, language={language}")
        
        return FollowupResponse(
            id=followup_id,
            status="summarizing",
            message="Transcript uploaded, generating summary..."
        )
        
    except HTTPException:
        raise
    except Exception as e:
        raise handle_exception(e, "transcript_upload", user_id=user_id)


@router.get("/list", response_model=List[Dict[str, Any]])
async def list_followups(
    limit: int = 20,
    offset: int = 0,
    current_user: dict = Depends(get_current_user)
):
    """List all follow-ups for the user's organization"""
    try:
        user_id = current_user.get("sub") or current_user.get("id")
        
        # Get organization
        org_response = supabase.table("organization_members").select(
            "organization_id"
        ).eq("user_id", user_id).limit(1).execute()
        
        if not org_response.data:
            raise HTTPException(status_code=404, detail="User not in any organization")
        
        organization_id = org_response.data[0]["organization_id"]
        
        # Get followups
        response = supabase.table("followups").select(
            "id, prospect_company_name, meeting_subject, meeting_date, status, "
            "executive_summary, audio_duration_seconds, created_at, completed_at"
        ).eq(
            "organization_id", organization_id
        ).order(
            "created_at", desc=True
        ).range(offset, offset + limit - 1).execute()
        
        return response.data or []
        
    except HTTPException:
        raise
    except Exception as e:
        raise handle_exception(e, "list_followups", user_id=user_id)


@router.get("/{followup_id}", response_model=Dict[str, Any])
async def get_followup(
    followup_id: str,
    current_user: dict = Depends(get_current_user)
):
    """Get a specific follow-up by ID"""
    try:
        user_id = current_user.get("sub") or current_user.get("id")
        
        # Get organization
        org_response = supabase.table("organization_members").select(
            "organization_id"
        ).eq("user_id", user_id).limit(1).execute()
        
        if not org_response.data:
            raise HTTPException(status_code=404, detail="User not in any organization")
        
        organization_id = org_response.data[0]["organization_id"]
        
        # Get followup
        response = supabase.table("followups").select("*").eq(
            "id", followup_id
        ).eq(
            "organization_id", organization_id
        ).limit(1).execute()
        
        if not response.data:
            raise HTTPException(status_code=404, detail="Follow-up not found")
        
        return response.data[0]
        
    except HTTPException:
        raise
    except Exception as e:
        raise handle_exception(e, "get_followup", user_id=user_id, resource_id=followup_id)


@router.patch("/{followup_id}", response_model=Dict[str, Any])
async def update_followup(
    followup_id: str,
    request: UpdateFollowupRequest,
    current_user: dict = Depends(get_current_user)
):
    """Update a follow-up (action items, email draft, etc.)"""
    try:
        user_id = current_user.get("sub") or current_user.get("id")
        
        # Get organization
        org_response = supabase.table("organization_members").select(
            "organization_id"
        ).eq("user_id", user_id).limit(1).execute()
        
        if not org_response.data:
            raise HTTPException(status_code=404, detail="User not in any organization")
        
        organization_id = org_response.data[0]["organization_id"]
        
        # Build update data
        update_data = {}
        if request.action_items is not None:
            update_data["action_items"] = request.action_items
        if request.email_draft is not None:
            update_data["email_draft"] = request.email_draft
        if request.email_tone is not None:
            update_data["email_tone"] = request.email_tone
        if request.meeting_subject is not None:
            update_data["meeting_subject"] = request.meeting_subject
        if request.executive_summary is not None:
            update_data["executive_summary"] = request.executive_summary
        if request.full_summary_content is not None:
            update_data["full_summary_content"] = request.full_summary_content
        
        if not update_data:
            raise HTTPException(status_code=400, detail="No fields to update")
        
        # Update
        response = supabase.table("followups").update(update_data).eq(
            "id", followup_id
        ).eq(
            "organization_id", organization_id
        ).execute()
        
        if not response.data:
            raise HTTPException(status_code=404, detail="Follow-up not found")
        
        return response.data[0]
        
    except HTTPException:
        raise
    except Exception as e:
        raise handle_exception(e, "update_followup", user_id=user_id, resource_id=followup_id)


@router.delete("/{followup_id}")
async def delete_followup(
    followup_id: str,
    current_user: dict = Depends(get_current_user)
):
    """Delete a follow-up"""
    from app.services.coach_cleanup import cleanup_suggestions_for_entity
    
    try:
        user_id = current_user.get("sub") or current_user.get("id")
        
        # Get organization
        org_response = supabase.table("organization_members").select(
            "organization_id"
        ).eq("user_id", user_id).limit(1).execute()
        
        if not org_response.data:
            raise HTTPException(status_code=404, detail="User not in any organization")
        
        organization_id = org_response.data[0]["organization_id"]
        
        # Get followup to delete audio file
        followup_response = supabase.table("followups").select(
            "audio_filename"
        ).eq("id", followup_id).eq("organization_id", organization_id).limit(1).execute()
        
        if followup_response.data and followup_response.data[0].get("audio_filename"):
            # Delete audio file from storage
            storage_path = f"{organization_id}/{followup_id}/{followup_response.data[0]['audio_filename']}"
            try:
                supabase.storage.from_("followup-audio").remove([storage_path])
            except Exception as e:
                logger.warning(f"Could not delete audio file: {e}")
        
        # Clean up related coach suggestions
        await cleanup_suggestions_for_entity(supabase, "followup", followup_id, user_id)
        
        # Delete followup record
        response = supabase.table("followups").delete().eq(
            "id", followup_id
        ).eq(
            "organization_id", organization_id
        ).execute()
        
        return {"message": "Follow-up deleted"}
        
    except HTTPException:
        raise
    except Exception as e:
        raise handle_exception(e, "delete_followup", user_id=user_id, resource_id=followup_id)


@router.post("/{followup_id}/regenerate-email", response_model=Dict[str, Any])
async def regenerate_email(
    followup_id: str,
    request: RegenerateEmailRequest,
    current_user: dict = Depends(get_current_user)
):
    """Regenerate the email draft with different tone"""
    try:
        user_id = current_user.get("sub") or current_user.get("id")
        
        # Get organization
        org_response = supabase.table("organization_members").select(
            "organization_id"
        ).eq("user_id", user_id).limit(1).execute()
        
        if not org_response.data:
            raise HTTPException(status_code=404, detail="User not in any organization")
        
        organization_id = org_response.data[0]["organization_id"]
        
        # Get followup
        followup_response = supabase.table("followups").select("*").eq(
            "id", followup_id
        ).eq(
            "organization_id", organization_id
        ).limit(1).execute()
        
        if not followup_response.data:
            raise HTTPException(status_code=404, detail="Follow-up not found")
        
        followup = followup_response.data[0]
        
        if followup["status"] != "completed":
            raise HTTPException(status_code=400, detail="Follow-up not yet completed")
        
        # Get full prospect context for regeneration
        prospect_context = None
        prospect_company = followup.get("prospect_company_name")
        
        try:
            context_service = get_prospect_context_service()
            prospect_context = await context_service.get_full_prospect_context(
                prospect_company=prospect_company or "Unknown",
                organization_id=organization_id,
                user_id=user_id,
                meeting_prep_id=followup.get("meeting_prep_id"),
                include_kb=True,
                max_kb_chunks=3
            )
        except Exception as e:
            logger.warning(f"Could not get prospect context for email regen: {e}")
        
        # Regenerate email with full context
        followup_generator = get_followup_generator()
        
        summary = {
            "executive_summary": followup.get("executive_summary", ""),
            "key_points": followup.get("key_points", []),
            "next_steps": followup.get("next_steps", [])
        }
        
        email_draft = await followup_generator.generate_email_draft(
            summary=summary,
            action_items=followup.get("action_items", []),
            prospect_context=prospect_context,
            prospect_company=prospect_company,
            tone=request.tone
        )
        
        # Update followup
        supabase.table("followups").update({
            "email_draft": email_draft,
            "email_tone": request.tone
        }).eq("id", followup_id).execute()
        
        return {
            "email_draft": email_draft,
            "email_tone": request.tone
        }
        
    except HTTPException:
        raise
    except Exception as e:
        raise handle_exception(e, "regenerate_email", user_id=user_id, resource_id=followup_id)

