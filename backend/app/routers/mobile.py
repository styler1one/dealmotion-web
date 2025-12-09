"""
Mobile API endpoints for the DealMotion mobile recording app.
"""
from datetime import datetime
from typing import Optional, List
from uuid import uuid4

from fastapi import APIRouter, Depends, File, Form, UploadFile, HTTPException, BackgroundTasks
from pydantic import BaseModel

from app.deps import get_current_user, get_user_org
from app.database import get_supabase_service

router = APIRouter()


# ============================================================================
# Models
# ============================================================================

class RecordingUploadResponse(BaseModel):
    """Response after uploading a recording"""
    success: bool
    recording_id: str
    message: str


class RecordingStatus(BaseModel):
    """Status of a recording"""
    id: str
    status: str  # pending, processing, completed, failed
    prospect_id: Optional[str] = None
    prospect_name: Optional[str] = None
    duration_seconds: int
    file_size_bytes: int
    created_at: datetime
    processed_at: Optional[datetime] = None
    followup_id: Optional[str] = None
    error: Optional[str] = None


class PendingRecording(BaseModel):
    """A pending recording that needs to be uploaded"""
    id: str
    local_id: str
    status: str
    created_at: datetime


class RecordingListResponse(BaseModel):
    """List of recordings"""
    recordings: List[RecordingStatus]
    total: int


# ============================================================================
# Endpoints
# ============================================================================

@router.post("/recordings/upload", response_model=RecordingUploadResponse)
async def upload_recording(
    background_tasks: BackgroundTasks,
    file: UploadFile = File(...),
    prospect_id: Optional[str] = Form(None),
    prospect_name: Optional[str] = Form(None),
    duration_seconds: int = Form(...),
    local_recording_id: str = Form(...),
    user_org: tuple = Depends(get_user_org),
):
    """
    Upload a recording from the mobile app.
    
    The recording will be stored and queued for processing (transcription + analysis).
    """
    user_id, organization_id = user_org
    supabase = get_supabase_service()
    
    try:
        # Generate unique ID
        recording_id = str(uuid4())
        
        # Read file content
        file_content = await file.read()
        file_size = len(file_content)
        
        # Validate file size (max 500MB)
        max_size = 500 * 1024 * 1024
        if file_size > max_size:
            raise HTTPException(
                status_code=413,
                detail=f"File too large. Maximum size is 500MB."
            )
        
        # Upload to Supabase Storage
        storage_path = f"recordings/{organization_id}/{recording_id}/{file.filename}"
        
        storage_result = supabase.storage.from_("recordings").upload(
            storage_path,
            file_content,
            {"content-type": file.content_type or "audio/mp4"}
        )
        
        if hasattr(storage_result, 'error') and storage_result.error:
            raise HTTPException(
                status_code=500,
                detail=f"Failed to upload file: {storage_result.error}"
            )
        
        # Create record in database
        recording_data = {
            "id": recording_id,
            "organization_id": organization_id,
            "user_id": user_id,
            "prospect_id": prospect_id,
            "storage_path": storage_path,
            "original_filename": file.filename,
            "file_size_bytes": file_size,
            "duration_seconds": duration_seconds,
            "local_recording_id": local_recording_id,
            "status": "pending",
            "source": "mobile_app",
            "created_at": datetime.utcnow().isoformat(),
        }
        
        # Insert into mobile_recordings table
        result = supabase.table("mobile_recordings").insert(recording_data).execute()
        
        if not result.data:
            raise HTTPException(
                status_code=500,
                detail="Failed to create recording record"
            )
        
        # TODO: Trigger processing via Inngest
        # background_tasks.add_task(trigger_recording_processing, recording_id)
        
        return RecordingUploadResponse(
            success=True,
            recording_id=recording_id,
            message="Recording uploaded successfully. Processing will begin shortly."
        )
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Upload failed: {str(e)}"
        )


@router.get("/recordings", response_model=RecordingListResponse)
async def list_recordings(
    status: Optional[str] = None,
    limit: int = 50,
    offset: int = 0,
    user_org: tuple = Depends(get_user_org),
):
    """
    List recordings for the current user.
    """
    user_id, organization_id = user_org
    supabase = get_supabase_service()
    
    try:
        query = supabase.table("mobile_recordings").select(
            "*"
        ).eq(
            "organization_id", organization_id
        ).eq(
            "user_id", user_id
        ).order(
            "created_at", desc=True
        ).range(offset, offset + limit - 1)
        
        if status:
            query = query.eq("status", status)
        
        result = query.execute()
        
        recordings = []
        for row in result.data or []:
            recordings.append(RecordingStatus(
                id=row["id"],
                status=row["status"],
                prospect_id=row.get("prospect_id"),
                prospect_name=row.get("prospect_name"),
                duration_seconds=row.get("duration_seconds", 0),
                file_size_bytes=row.get("file_size_bytes", 0),
                created_at=row["created_at"],
                processed_at=row.get("processed_at"),
                followup_id=row.get("followup_id"),
                error=row.get("error"),
            ))
        
        # Get total count
        count_result = supabase.table("mobile_recordings").select(
            "id", count="exact"
        ).eq(
            "organization_id", organization_id
        ).eq(
            "user_id", user_id
        ).execute()
        
        total = count_result.count if hasattr(count_result, 'count') else len(recordings)
        
        return RecordingListResponse(
            recordings=recordings,
            total=total
        )
        
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Failed to fetch recordings: {str(e)}"
        )


@router.get("/recordings/{recording_id}", response_model=RecordingStatus)
async def get_recording(
    recording_id: str,
    user_org: tuple = Depends(get_user_org),
):
    """
    Get details of a specific recording.
    """
    user_id, organization_id = user_org
    supabase = get_supabase_service()
    
    try:
        result = supabase.table("mobile_recordings").select(
            "*"
        ).eq(
            "id", recording_id
        ).eq(
            "organization_id", organization_id
        ).single().execute()
        
        if not result.data:
            raise HTTPException(status_code=404, detail="Recording not found")
        
        row = result.data
        return RecordingStatus(
            id=row["id"],
            status=row["status"],
            prospect_id=row.get("prospect_id"),
            prospect_name=row.get("prospect_name"),
            duration_seconds=row.get("duration_seconds", 0),
            file_size_bytes=row.get("file_size_bytes", 0),
            created_at=row["created_at"],
            processed_at=row.get("processed_at"),
            followup_id=row.get("followup_id"),
            error=row.get("error"),
        )
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Failed to fetch recording: {str(e)}"
        )


@router.delete("/recordings/{recording_id}")
async def delete_recording(
    recording_id: str,
    user_org: tuple = Depends(get_user_org),
):
    """
    Delete a recording.
    """
    user_id, organization_id = user_org
    supabase = get_supabase_service()
    
    try:
        # Get recording to find storage path
        result = supabase.table("mobile_recordings").select(
            "storage_path"
        ).eq(
            "id", recording_id
        ).eq(
            "organization_id", organization_id
        ).single().execute()
        
        if not result.data:
            raise HTTPException(status_code=404, detail="Recording not found")
        
        storage_path = result.data.get("storage_path")
        
        # Delete from storage
        if storage_path:
            supabase.storage.from_("recordings").remove([storage_path])
        
        # Delete from database
        supabase.table("mobile_recordings").delete().eq(
            "id", recording_id
        ).eq(
            "organization_id", organization_id
        ).execute()
        
        return {"success": True, "message": "Recording deleted"}
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Failed to delete recording: {str(e)}"
        )


@router.get("/recordings/pending", response_model=List[PendingRecording])
async def get_pending_recordings(
    user_org: tuple = Depends(get_user_org),
):
    """
    Get list of pending recordings that need to be synced.
    Used by mobile app to check which local recordings haven't been uploaded yet.
    """
    user_id, organization_id = user_org
    supabase = get_supabase_service()
    
    try:
        result = supabase.table("mobile_recordings").select(
            "id, local_recording_id, status, created_at"
        ).eq(
            "organization_id", organization_id
        ).eq(
            "user_id", user_id
        ).in_(
            "status", ["pending", "processing"]
        ).order(
            "created_at", desc=True
        ).execute()
        
        return [
            PendingRecording(
                id=row["id"],
                local_id=row["local_recording_id"],
                status=row["status"],
                created_at=row["created_at"],
            )
            for row in result.data or []
        ]
        
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Failed to fetch pending recordings: {str(e)}"
        )

