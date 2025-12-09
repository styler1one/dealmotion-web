"""
Admin Notes Router
==================

Endpoints for managing internal admin notes on users and organizations.
"""

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from pydantic import BaseModel
from typing import Optional, List
from uuid import UUID
from datetime import datetime

from app.deps import get_admin_user, require_admin_role, AdminContext
from app.database import get_supabase_service
from .models import CamelModel
from .utils import log_admin_action

router = APIRouter(prefix="/notes", tags=["admin-notes"])


# ============================================================
# Models (with camelCase serialization)
# ============================================================

class NoteCreate(BaseModel):
    target_type: str  # 'user' or 'organization'
    target_id: str
    content: str
    is_pinned: bool = False


class NoteUpdate(BaseModel):
    content: Optional[str] = None
    is_pinned: Optional[bool] = None


class NoteResponse(CamelModel):
    id: str
    target_type: str
    target_id: str
    target_identifier: Optional[str] = None
    content: str
    is_pinned: bool
    admin_id: str
    admin_email: str
    created_at: datetime
    updated_at: datetime


class NoteListResponse(CamelModel):
    notes: List[NoteResponse]
    total: int


# ============================================================
# Endpoints
# ============================================================

@router.get("", response_model=NoteListResponse)
async def list_notes(
    target_type: Optional[str] = Query(None, description="Filter by target type"),
    target_id: Optional[str] = Query(None, description="Filter by target ID"),
    admin: AdminContext = Depends(get_admin_user)
):
    """
    List admin notes with optional filtering.
    
    Query params:
    - target_type: 'user' or 'organization'
    - target_id: UUID of the target
    """
    supabase = get_supabase_service()
    
    query = supabase.table("admin_notes") \
        .select("*, admin_users(user_id)", count="exact")
    
    if target_type:
        query = query.eq("target_type", target_type)
    
    if target_id:
        query = query.eq("target_id", target_id)
    
    result = query \
        .order("is_pinned", desc=True) \
        .order("created_at", desc=True) \
        .execute()
    
    # Batch fetch admin emails to avoid N+1 queries
    admin_user_ids = set()
    for note in (result.data or []):
        if note.get("admin_users") and note["admin_users"].get("user_id"):
            admin_user_ids.add(note["admin_users"]["user_id"])
    
    admin_emails = {}
    if admin_user_ids:
        emails_result = supabase.table("users") \
            .select("id, email") \
            .in_("id", list(admin_user_ids)) \
            .execute()
        for user in (emails_result.data or []):
            admin_emails[user["id"]] = user["email"]
    
    notes = []
    for note in (result.data or []):
        admin_user_id = note["admin_users"]["user_id"] if note.get("admin_users") else None
        admin_email = admin_emails.get(admin_user_id, "Unknown")
        
        notes.append(NoteResponse(
            id=note["id"],
            target_type=note["target_type"],
            target_id=note["target_id"],
            target_identifier=note.get("target_identifier"),
            content=note["content"],
            is_pinned=note["is_pinned"],
            admin_id=note["admin_user_id"],
            admin_email=admin_email,
            created_at=note["created_at"],
            updated_at=note["updated_at"]
        ))
    
    return NoteListResponse(notes=notes, total=result.count or len(notes))


@router.post("", response_model=NoteResponse)
async def create_note(
    data: NoteCreate,
    request: Request,
    admin: AdminContext = Depends(require_admin_role("super_admin", "admin", "support"))
):
    """Create a new admin note."""
    supabase = get_supabase_service()
    
    # Validate target type
    if data.target_type not in ("user", "organization"):
        raise HTTPException(status_code=400, detail="Invalid target_type")
    
    # Get target identifier
    target_identifier = None
    if data.target_type == "user":
        user_result = supabase.table("users") \
            .select("email") \
            .eq("id", data.target_id) \
            .maybe_single() \
            .execute()
        if user_result.data:
            target_identifier = user_result.data["email"]
    elif data.target_type == "organization":
        org_result = supabase.table("organizations") \
            .select("name") \
            .eq("id", data.target_id) \
            .maybe_single() \
            .execute()
        if org_result.data:
            target_identifier = org_result.data["name"]
    
    # Create note
    result = supabase.table("admin_notes").insert({
        "target_type": data.target_type,
        "target_id": data.target_id,
        "target_identifier": target_identifier,
        "content": data.content,
        "is_pinned": data.is_pinned,
        "admin_user_id": admin.admin_id
    }).execute()
    
    if not result.data:
        raise HTTPException(status_code=500, detail="Failed to create note")
    
    note = result.data[0]
    
    # Log action
    await log_admin_action(
        admin_id=admin.admin_id,
        action="note.create",
        target_type=data.target_type,
        target_id=UUID(data.target_id),
        target_identifier=target_identifier,
        details={"is_pinned": data.is_pinned},
        request=request
    )
    
    return NoteResponse(
        id=note["id"],
        target_type=note["target_type"],
        target_id=note["target_id"],
        target_identifier=note.get("target_identifier"),
        content=note["content"],
        is_pinned=note["is_pinned"],
        admin_id=note["admin_user_id"],
        admin_email=admin.email or "Unknown",
        created_at=note["created_at"],
        updated_at=note["updated_at"]
    )


@router.patch("/{note_id}", response_model=NoteResponse)
async def update_note(
    note_id: str,
    data: NoteUpdate,
    request: Request,
    admin: AdminContext = Depends(require_admin_role("super_admin", "admin", "support"))
):
    """Update an existing note (only author can update)."""
    supabase = get_supabase_service()
    
    # Get existing note
    existing = supabase.table("admin_notes") \
        .select("*, admin_users(user_id)") \
        .eq("id", note_id) \
        .maybe_single() \
        .execute()
    
    if not existing.data:
        raise HTTPException(status_code=404, detail="Note not found")
    
    # Check ownership (only author can update)
    if existing.data["admin_user_id"] != admin.admin_id:
        raise HTTPException(status_code=403, detail="You can only edit your own notes")
    
    # Build update data
    update_data = {}
    if data.content is not None:
        update_data["content"] = data.content
    if data.is_pinned is not None:
        update_data["is_pinned"] = data.is_pinned
    
    if not update_data:
        raise HTTPException(status_code=400, detail="No updates provided")
    
    # Update note
    result = supabase.table("admin_notes") \
        .update(update_data) \
        .eq("id", note_id) \
        .execute()
    
    if not result.data:
        raise HTTPException(status_code=500, detail="Failed to update note")
    
    note = result.data[0]
    
    # Log action
    await log_admin_action(
        admin_id=admin.admin_id,
        action="note.update",
        target_type=note["target_type"],
        target_id=UUID(note["target_id"]),
        target_identifier=note.get("target_identifier"),
        details=update_data,
        request=request
    )
    
    return NoteResponse(
        id=note["id"],
        target_type=note["target_type"],
        target_id=note["target_id"],
        target_identifier=note.get("target_identifier"),
        content=note["content"],
        is_pinned=note["is_pinned"],
        admin_id=note["admin_user_id"],
        admin_email=admin.email or "Unknown",
        created_at=note["created_at"],
        updated_at=note["updated_at"]
    )


@router.delete("/{note_id}")
async def delete_note(
    note_id: str,
    request: Request,
    admin: AdminContext = Depends(require_admin_role("super_admin", "admin", "support"))
):
    """Delete a note (only author can delete)."""
    supabase = get_supabase_service()
    
    # Get existing note
    existing = supabase.table("admin_notes") \
        .select("*") \
        .eq("id", note_id) \
        .maybe_single() \
        .execute()
    
    if not existing.data:
        raise HTTPException(status_code=404, detail="Note not found")
    
    # Check ownership
    if existing.data["admin_user_id"] != admin.admin_id and admin.role != "super_admin":
        raise HTTPException(status_code=403, detail="You can only delete your own notes")
    
    note = existing.data
    
    # Delete note
    supabase.table("admin_notes").delete().eq("id", note_id).execute()
    
    # Log action
    await log_admin_action(
        admin_id=admin.admin_id,
        action="note.delete",
        target_type=note["target_type"],
        target_id=UUID(note["target_id"]),
        target_identifier=note.get("target_identifier"),
        request=request
    )
    
    return {"success": True, "message": "Note deleted"}

