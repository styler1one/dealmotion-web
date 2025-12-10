"""
Recordings Router - Unified view of all meeting recordings
Combines data from: mobile_recordings, external_recordings, followups (with audio)

This is a READ-ONLY endpoint that aggregates recordings from multiple sources.
"""
from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel
from typing import Optional, List, Tuple
from datetime import datetime
import logging

from app.deps import get_current_user, get_user_org
from app.database import get_supabase_service

supabase = get_supabase_service()
logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1/recordings", tags=["recordings"])


# ==========================================
# Pydantic Models
# ==========================================

class UnifiedRecording(BaseModel):
    """A unified recording from any source."""
    id: str
    source: str  # 'mobile', 'fireflies', 'teams', 'zoom', 'web_upload'
    source_table: str  # 'mobile_recordings', 'external_recordings', 'followups'
    
    # Basic info
    title: Optional[str] = None
    prospect_id: Optional[str] = None
    prospect_name: Optional[str] = None
    
    # Recording details
    duration_seconds: Optional[int] = None
    file_size_bytes: Optional[int] = None
    
    # Status
    status: str  # 'pending', 'processing', 'completed', 'failed', 'imported'
    error: Optional[str] = None
    
    # Links
    followup_id: Optional[str] = None  # Link to followup if processed
    audio_url: Optional[str] = None
    
    # Timestamps
    recorded_at: Optional[datetime] = None
    created_at: datetime
    processed_at: Optional[datetime] = None


class RecordingsListResponse(BaseModel):
    """Response for recordings list."""
    recordings: List[UnifiedRecording]
    total: int
    sources: dict  # Count per source


class RecordingsStatsResponse(BaseModel):
    """Statistics about recordings."""
    total_recordings: int
    pending_count: int
    processing_count: int
    completed_count: int
    failed_count: int
    by_source: dict


# ==========================================
# Helper Functions
# ==========================================

def map_mobile_recording(row: dict, prospect_map: dict) -> UnifiedRecording:
    """Map mobile_recordings row to UnifiedRecording."""
    prospect_name = None
    if row.get("prospect_id") and row["prospect_id"] in prospect_map:
        prospect_name = prospect_map[row["prospect_id"]]
    
    return UnifiedRecording(
        id=row["id"],
        source=row.get("source", "mobile"),
        source_table="mobile_recordings",
        title=row.get("original_filename"),
        prospect_id=row.get("prospect_id"),
        prospect_name=prospect_name,
        duration_seconds=row.get("duration_seconds"),
        file_size_bytes=row.get("file_size_bytes"),
        status=row.get("status", "pending"),
        error=row.get("error"),
        followup_id=row.get("followup_id"),
        audio_url=None,  # Not directly accessible
        recorded_at=None,
        created_at=row["created_at"],
        processed_at=row.get("processed_at"),
    )


def map_external_recording(row: dict, prospect_map: dict) -> UnifiedRecording:
    """Map external_recordings row to UnifiedRecording."""
    prospect_name = None
    prospect_id = row.get("matched_prospect_id")
    if prospect_id and prospect_id in prospect_map:
        prospect_name = prospect_map[prospect_id]
    
    # Map import_status to unified status
    import_status = row.get("import_status", "pending")
    status_map = {
        "pending": "pending",
        "imported": "completed",
        "skipped": "completed",
        "failed": "failed",
    }
    status = status_map.get(import_status, "pending")
    
    return UnifiedRecording(
        id=row["id"],
        source=row.get("provider", "external"),
        source_table="external_recordings",
        title=row.get("title"),
        prospect_id=prospect_id,
        prospect_name=prospect_name,
        duration_seconds=row.get("duration_seconds"),
        file_size_bytes=None,
        status=status,
        error=row.get("import_error"),
        followup_id=row.get("imported_followup_id"),
        audio_url=row.get("audio_url"),
        recorded_at=row.get("recording_date"),
        created_at=row["created_at"],
        processed_at=None,
    )


def map_followup_recording(row: dict) -> UnifiedRecording:
    """Map followups row (with audio) to UnifiedRecording."""
    # Only include followups that have audio (direct uploads)
    status_map = {
        "uploading": "processing",
        "transcribing": "processing",
        "summarizing": "processing",
        "completed": "completed",
        "failed": "failed",
    }
    
    return UnifiedRecording(
        id=row["id"],
        source="web_upload",
        source_table="followups",
        title=row.get("meeting_subject") or row.get("audio_filename"),
        prospect_id=row.get("prospect_id"),
        prospect_name=row.get("prospect_company_name"),
        duration_seconds=row.get("audio_duration_seconds"),
        file_size_bytes=row.get("audio_size_bytes"),
        status=status_map.get(row.get("status", "completed"), "completed"),
        error=row.get("error_message"),
        followup_id=row["id"],  # It IS the followup
        audio_url=row.get("audio_url"),
        recorded_at=row.get("meeting_date"),
        created_at=row["created_at"],
        processed_at=row.get("completed_at"),
    )


# ==========================================
# Endpoints
# ==========================================

@router.get("", response_model=RecordingsListResponse)
async def list_recordings(
    source: Optional[str] = Query(None, description="Filter by source: mobile, fireflies, teams, zoom, web_upload"),
    status: Optional[str] = Query(None, description="Filter by status: pending, processing, completed, failed"),
    prospect_id: Optional[str] = Query(None, description="Filter by prospect"),
    limit: int = Query(50, ge=1, le=100),
    offset: int = Query(0, ge=0),
    user: dict = Depends(get_current_user),
    user_org: Tuple[str, str] = Depends(get_user_org),
):
    """
    Get unified list of all recordings from all sources.
    Combines mobile_recordings, external_recordings, and followups with audio.
    """
    user_id, org_id = user_org
    
    if not user_id or not org_id:
        return RecordingsListResponse(recordings=[], total=0, sources={})
    
    all_recordings: List[UnifiedRecording] = []
    sources_count = {
        "mobile": 0,
        "fireflies": 0,
        "teams": 0,
        "zoom": 0,
        "web_upload": 0,
    }
    
    try:
        # Collect all prospect IDs first, then batch fetch names
        prospect_ids = set()
        
        # 1. Fetch mobile recordings
        if source is None or source == "mobile":
            mobile_query = supabase.table("mobile_recordings").select(
                "id, organization_id, user_id, prospect_id, storage_path, original_filename, "
                "file_size_bytes, duration_seconds, local_recording_id, source, status, error, "
                "followup_id, created_at, updated_at, processed_at"
            ).eq("organization_id", org_id).order("created_at", desc=True)
            
            if status:
                mobile_query = mobile_query.eq("status", status)
            if prospect_id:
                mobile_query = mobile_query.eq("prospect_id", prospect_id)
            
            mobile_result = mobile_query.execute()
            
            for row in mobile_result.data or []:
                if row.get("prospect_id"):
                    prospect_ids.add(row["prospect_id"])
        
        # 2. Fetch external recordings (Fireflies, Teams, Zoom)
        if source is None or source in ["fireflies", "teams", "zoom"]:
            external_query = supabase.table("external_recordings").select(
                "id, organization_id, user_id, provider, external_id, title, recording_date, "
                "duration_seconds, participants, audio_url, transcript_url, transcript_text, "
                "matched_meeting_id, matched_prospect_id, match_confidence, import_status, "
                "imported_followup_id, import_error, created_at, updated_at"
            ).eq("organization_id", org_id).order("created_at", desc=True)
            
            if source in ["fireflies", "teams", "zoom"]:
                external_query = external_query.eq("provider", source)
            if prospect_id:
                external_query = external_query.eq("matched_prospect_id", prospect_id)
            
            external_result = external_query.execute()
            
            for row in external_result.data or []:
                if row.get("matched_prospect_id"):
                    prospect_ids.add(row["matched_prospect_id"])
        
        # 3. Fetch followups with audio (web uploads)
        if source is None or source == "web_upload":
            followup_query = supabase.table("followups").select(
                "id, organization_id, user_id, prospect_id, prospect_company_name, "
                "meeting_subject, meeting_date, audio_url, audio_filename, audio_size_bytes, "
                "audio_duration_seconds, status, error_message, created_at, completed_at"
            ).eq("organization_id", org_id).not_.is_("audio_url", "null").order("created_at", desc=True)
            
            if prospect_id:
                followup_query = followup_query.eq("prospect_id", prospect_id)
            
            # Filter by status if provided
            if status == "pending":
                followup_query = followup_query.eq("status", "uploading")
            elif status == "processing":
                followup_query = followup_query.in_("status", ["transcribing", "summarizing"])
            elif status == "completed":
                followup_query = followup_query.eq("status", "completed")
            elif status == "failed":
                followup_query = followup_query.eq("status", "failed")
            
            followup_result = followup_query.execute()
            
            for row in followup_result.data or []:
                if row.get("prospect_id"):
                    prospect_ids.add(row["prospect_id"])
        
        # Batch fetch prospect names
        prospect_map = {}
        if prospect_ids:
            prospects_result = supabase.table("prospects").select(
                "id, company_name"
            ).in_("id", list(prospect_ids)).execute()
            
            prospect_map = {p["id"]: p["company_name"] for p in prospects_result.data or []}
        
        # Now map all recordings
        if source is None or source == "mobile":
            for row in mobile_result.data or []:
                rec = map_mobile_recording(row, prospect_map)
                all_recordings.append(rec)
                sources_count["mobile"] += 1
        
        if source is None or source in ["fireflies", "teams", "zoom"]:
            for row in external_result.data or []:
                rec = map_external_recording(row, prospect_map)
                all_recordings.append(rec)
                sources_count[rec.source] = sources_count.get(rec.source, 0) + 1
        
        if source is None or source == "web_upload":
            for row in followup_result.data or []:
                rec = map_followup_recording(row)
                all_recordings.append(rec)
                sources_count["web_upload"] += 1
        
        # Sort all by recorded_at (or created_at as fallback) descending - newest first
        all_recordings.sort(
            key=lambda r: r.recorded_at or r.created_at, 
            reverse=True
        )
        
        # Apply pagination
        total = len(all_recordings)
        paginated = all_recordings[offset:offset + limit]
        
        return RecordingsListResponse(
            recordings=paginated,
            total=total,
            sources=sources_count,
        )
        
    except Exception as e:
        logger.error(f"Error fetching recordings: {e}")
        return RecordingsListResponse(recordings=[], total=0, sources={})


@router.get("/stats", response_model=RecordingsStatsResponse)
async def get_recordings_stats(
    user: dict = Depends(get_current_user),
    user_org: Tuple[str, str] = Depends(get_user_org),
):
    """
    Get statistics about recordings across all sources.
    """
    user_id, org_id = user_org
    
    if not user_id or not org_id:
        return RecordingsStatsResponse(
            total_recordings=0,
            pending_count=0,
            processing_count=0,
            completed_count=0,
            failed_count=0,
            by_source={},
        )
    
    try:
        stats = {
            "total": 0,
            "pending": 0,
            "processing": 0,
            "completed": 0,
            "failed": 0,
            "by_source": {},
        }
        
        # Mobile recordings stats
        mobile_result = supabase.table("mobile_recordings").select(
            "status", count="exact"
        ).eq("organization_id", org_id).execute()
        
        mobile_count = len(mobile_result.data or [])
        stats["by_source"]["mobile"] = mobile_count
        stats["total"] += mobile_count
        
        for row in mobile_result.data or []:
            s = row.get("status", "pending")
            if s == "pending":
                stats["pending"] += 1
            elif s == "processing":
                stats["processing"] += 1
            elif s == "completed":
                stats["completed"] += 1
            elif s == "failed":
                stats["failed"] += 1
        
        # External recordings stats
        external_result = supabase.table("external_recordings").select(
            "provider, import_status"
        ).eq("organization_id", org_id).execute()
        
        for row in external_result.data or []:
            provider = row.get("provider", "external")
            stats["by_source"][provider] = stats["by_source"].get(provider, 0) + 1
            stats["total"] += 1
            
            import_status = row.get("import_status", "pending")
            if import_status == "pending":
                stats["pending"] += 1
            elif import_status == "imported":
                stats["completed"] += 1
            elif import_status == "failed":
                stats["failed"] += 1
        
        # Followups with audio stats
        followup_result = supabase.table("followups").select(
            "status"
        ).eq("organization_id", org_id).not_.is_("audio_url", "null").execute()
        
        web_count = len(followup_result.data or [])
        stats["by_source"]["web_upload"] = web_count
        stats["total"] += web_count
        
        for row in followup_result.data or []:
            s = row.get("status", "completed")
            if s == "uploading":
                stats["pending"] += 1
            elif s in ["transcribing", "summarizing"]:
                stats["processing"] += 1
            elif s == "completed":
                stats["completed"] += 1
            elif s == "failed":
                stats["failed"] += 1
        
        return RecordingsStatsResponse(
            total_recordings=stats["total"],
            pending_count=stats["pending"],
            processing_count=stats["processing"],
            completed_count=stats["completed"],
            failed_count=stats["failed"],
            by_source=stats["by_source"],
        )
        
    except Exception as e:
        logger.error(f"Error fetching recordings stats: {e}")
        return RecordingsStatsResponse(
            total_recordings=0,
            pending_count=0,
            processing_count=0,
            completed_count=0,
            failed_count=0,
            by_source={},
        )


# ==========================================
# Transcript Endpoint
# ==========================================

class TranscriptResponse(BaseModel):
    """Response for transcript detail."""
    id: str
    title: Optional[str] = None
    transcript_text: Optional[str] = None
    recording_date: Optional[datetime] = None
    duration_seconds: Optional[int] = None
    participants: List[str] = []
    provider: str


@router.get("/transcript/{recording_id}")
async def get_recording_transcript(
    recording_id: str,
    user: dict = Depends(get_current_user),
    user_org: Tuple[str, str] = Depends(get_user_org),
) -> TranscriptResponse:
    """
    Get the transcript for an external recording (Fireflies, Teams, Zoom).
    """
    user_id, org_id = user_org
    
    try:
        # Fetch from external_recordings
        result = supabase.table("external_recordings").select(
            "id, title, transcript_text, recording_date, duration_seconds, participants, provider"
        ).eq("id", recording_id).eq("organization_id", org_id).single().execute()
        
        if not result.data:
            logger.warning(f"Recording {recording_id} not found for org {org_id}")
            return TranscriptResponse(
                id=recording_id,
                title="Not Found",
                transcript_text=None,
                recording_date=None,
                duration_seconds=None,
                participants=[],
                provider="unknown"
            )
        
        row = result.data
        return TranscriptResponse(
            id=row["id"],
            title=row.get("title"),
            transcript_text=row.get("transcript_text"),
            recording_date=row.get("recording_date"),
            duration_seconds=row.get("duration_seconds"),
            participants=row.get("participants") or [],
            provider=row.get("provider", "unknown")
        )
        
    except Exception as e:
        logger.error(f"Error fetching transcript for {recording_id}: {e}")
        return TranscriptResponse(
            id=recording_id,
            title="Error",
            transcript_text=None,
            recording_date=None,
            duration_seconds=None,
            participants=[],
            provider="unknown"
        )

