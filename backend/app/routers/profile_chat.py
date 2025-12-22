"""
Profile Chat Router - API endpoints for dynamic conversational profile completion.

Provides endpoints for:
- Starting a chat session (with LinkedIn/research data)
- Sending messages and getting AI responses
- Getting session status
- Completing and saving the profile
"""

import logging
from typing import Optional, List
from uuid import UUID
from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field

from app.deps import get_current_user
from app.database import get_supabase_service
from app.services.profile_chat_service import get_profile_chat_service, ChatMessage

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/profile/chat", tags=["Profile Chat"])

# Use centralized database module
supabase = get_supabase_service()


# =============================================================================
# Request/Response Models
# =============================================================================

class StartChatRequest(BaseModel):
    """Request to start a new chat session."""
    profile_type: str = Field(..., pattern="^(sales|company)$")
    initial_data: dict = Field(default_factory=dict)
    user_name: Optional[str] = None


class StartChatResponse(BaseModel):
    """Response from starting a chat session."""
    session_id: str
    message: str
    is_complete: bool
    completeness_score: float
    current_profile: dict


class SendMessageRequest(BaseModel):
    """Request to send a message in a chat session."""
    message: str = Field(..., min_length=1, max_length=2000)


class ChatMessageResponse(BaseModel):
    """Response from sending a message."""
    message: str
    is_complete: bool
    completeness_score: float
    fields_updated: List[str]
    current_profile: dict
    suggested_actions: List[str]


class SessionStatusResponse(BaseModel):
    """Status of a chat session."""
    session_id: str
    profile_type: str
    status: str
    completeness_score: float
    message_count: int
    current_profile: dict
    created_at: str
    last_activity_at: str


class CompleteSessionRequest(BaseModel):
    """Request to complete a session and save the profile."""
    save_profile: bool = True


class CompleteSessionResponse(BaseModel):
    """Response from completing a session."""
    success: bool
    profile_id: Optional[str] = None
    message: str


# =============================================================================
# Endpoints
# =============================================================================

@router.post("/start", response_model=StartChatResponse)
async def start_chat_session(
    request: StartChatRequest,
    current_user: dict = Depends(get_current_user)
):
    """
    Start a new chat session for profile completion.
    
    The AI will analyze the initial data and generate a personalized
    opening message with the first question.
    """
    user_id = current_user["id"]
    org_id = current_user.get("organization_id")
    
    if not org_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="User must belong to an organization"
        )
    
    logger.info(f"[PROFILE_CHAT] Starting {request.profile_type} session for user {user_id}")
    
    # Get chat service
    chat_service = get_profile_chat_service()
    
    # Generate opening message
    response = await chat_service.start_session(
        profile_type=request.profile_type,
        initial_data=request.initial_data,
        user_name=request.user_name
    )
    
    # Create session in database
    session_data = {
        "organization_id": org_id,
        "user_id": user_id,
        "profile_type": request.profile_type,
        "initial_data": request.initial_data,
        "current_profile": response.current_profile,
        "messages": [
            {
                "role": "assistant",
                "content": response.message,
                "timestamp": datetime.utcnow().isoformat()
            }
        ],
        "completeness_score": response.completeness_score,
        "status": "completed" if response.is_complete else "active"
    }
    
    result = supabase.table("profile_chat_sessions").insert(session_data).execute()
    
    if not result.data:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to create chat session"
        )
    
    session_id = result.data[0]["id"]
    
    logger.info(f"[PROFILE_CHAT] Created session {session_id}")
    
    return StartChatResponse(
        session_id=session_id,
        message=response.message,
        is_complete=response.is_complete,
        completeness_score=response.completeness_score,
        current_profile=response.current_profile
    )


@router.post("/{session_id}/message", response_model=ChatMessageResponse)
async def send_message(
    session_id: UUID,
    request: SendMessageRequest,
    current_user: dict = Depends(get_current_user)
):
    """
    Send a message in an active chat session.
    
    The AI will:
    1. Extract information from your response
    2. Update the profile
    3. Ask the next relevant question (or complete if done)
    """
    user_id = current_user["id"]
    
    # Get session
    result = supabase.table("profile_chat_sessions").select("*").eq(
        "id", str(session_id)
    ).eq("user_id", user_id).single().execute()
    
    if not result.data:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Chat session not found"
        )
    
    session = result.data
    
    if session["status"] != "active":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Session is {session['status']}, cannot send messages"
        )
    
    logger.info(f"[PROFILE_CHAT] Processing message for session {session_id}")
    
    # Add user message to history
    messages = session.get("messages", [])
    messages.append({
        "role": "user",
        "content": request.message,
        "timestamp": datetime.utcnow().isoformat()
    })
    
    # Process with chat service
    chat_service = get_profile_chat_service()
    
    response = await chat_service.process_message(
        profile_type=session["profile_type"],
        current_profile=session.get("current_profile", {}),
        conversation_history=messages,
        user_message=request.message
    )
    
    # Add AI response to history
    messages.append({
        "role": "assistant",
        "content": response.message,
        "timestamp": datetime.utcnow().isoformat()
    })
    
    # Update session
    update_data = {
        "messages": messages,
        "current_profile": response.current_profile,
        "completeness_score": response.completeness_score,
        "status": "completed" if response.is_complete else "active"
    }
    
    if response.is_complete:
        update_data["completed_at"] = datetime.utcnow().isoformat()
    
    supabase.table("profile_chat_sessions").update(update_data).eq(
        "id", str(session_id)
    ).execute()
    
    return ChatMessageResponse(
        message=response.message,
        is_complete=response.is_complete,
        completeness_score=response.completeness_score,
        fields_updated=response.fields_updated,
        current_profile=response.current_profile,
        suggested_actions=response.suggested_actions
    )


@router.get("/{session_id}", response_model=SessionStatusResponse)
async def get_session_status(
    session_id: UUID,
    current_user: dict = Depends(get_current_user)
):
    """Get the current status of a chat session."""
    user_id = current_user["id"]
    
    result = supabase.table("profile_chat_sessions").select("*").eq(
        "id", str(session_id)
    ).eq("user_id", user_id).single().execute()
    
    if not result.data:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Chat session not found"
        )
    
    session = result.data
    messages = session.get("messages", [])
    
    return SessionStatusResponse(
        session_id=session["id"],
        profile_type=session["profile_type"],
        status=session["status"],
        completeness_score=session.get("completeness_score", 0),
        message_count=len(messages),
        current_profile=session.get("current_profile", {}),
        created_at=session["created_at"],
        last_activity_at=session.get("last_activity_at", session["created_at"])
    )


@router.get("/{session_id}/messages")
async def get_session_messages(
    session_id: UUID,
    current_user: dict = Depends(get_current_user)
):
    """Get all messages from a chat session."""
    user_id = current_user["id"]
    
    result = supabase.table("profile_chat_sessions").select(
        "messages, profile_type, status"
    ).eq("id", str(session_id)).eq("user_id", user_id).single().execute()
    
    if not result.data:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Chat session not found"
        )
    
    return {
        "messages": result.data.get("messages", []),
        "profile_type": result.data["profile_type"],
        "status": result.data["status"]
    }


@router.post("/{session_id}/complete", response_model=CompleteSessionResponse)
async def complete_session(
    session_id: UUID,
    request: CompleteSessionRequest,
    current_user: dict = Depends(get_current_user)
):
    """
    Complete a chat session and optionally save the profile.
    
    This will create/update the actual sales_profiles or company_profiles record.
    """
    user_id = current_user["id"]
    org_id = current_user.get("organization_id")
    
    # Get session
    result = supabase.table("profile_chat_sessions").select("*").eq(
        "id", str(session_id)
    ).eq("user_id", user_id).single().execute()
    
    if not result.data:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Chat session not found"
        )
    
    session = result.data
    profile_data = session.get("current_profile", {})
    profile_type = session["profile_type"]
    
    profile_id = None
    
    if request.save_profile:
        if profile_type == "sales":
            # Save to sales_profiles
            sales_data = {
                "organization_id": org_id,
                "user_id": user_id,
                "full_name": profile_data.get("full_name"),
                "role": profile_data.get("role"),
                "experience_years": profile_data.get("experience_years"),
                "sales_methodology": profile_data.get("sales_methodology"),
                "communication_style": profile_data.get("communication_style"),
                "strengths": profile_data.get("strengths", []),
                "target_industries": profile_data.get("target_industries", []),
                "target_regions": profile_data.get("target_regions", []),
                "target_company_sizes": profile_data.get("target_company_sizes", []),
                "quarterly_goals": profile_data.get("quarterly_goals"),
                "email_tone": profile_data.get("email_tone"),
                "uses_emoji": profile_data.get("uses_emoji", False),
                "email_signoff": profile_data.get("email_signoff"),
                "writing_length_preference": profile_data.get("writing_length_preference"),
                "ai_summary": profile_data.get("ai_summary"),
                "sales_narrative": profile_data.get("sales_narrative"),
                "style_guide": profile_data.get("style_guide"),
                "profile_completeness": int(session.get("completeness_score", 0) * 100)
            }
            
            # Upsert (create or update)
            save_result = supabase.table("sales_profiles").upsert(
                sales_data,
                on_conflict="organization_id,user_id"
            ).execute()
            
            if save_result.data:
                profile_id = save_result.data[0]["id"]
                
        elif profile_type == "company":
            # Save to company_profiles
            company_data = {
                "organization_id": org_id,
                "company_name": profile_data.get("company_name"),
                "industry": profile_data.get("industry"),
                "website": profile_data.get("website"),
                "products": profile_data.get("products", []),
                "core_value_props": profile_data.get("core_value_props", []),
                "differentiators": profile_data.get("differentiators", []),
                "ideal_customer_profile": profile_data.get("ideal_customer_profile", {}),
                "case_studies": profile_data.get("case_studies", []),
                "ai_summary": profile_data.get("ai_summary"),
                "company_narrative": profile_data.get("company_narrative"),
                "profile_completeness": int(session.get("completeness_score", 0) * 100)
            }
            
            save_result = supabase.table("company_profiles").upsert(
                company_data,
                on_conflict="organization_id"
            ).execute()
            
            if save_result.data:
                profile_id = save_result.data[0]["id"]
    
    # Update session as completed
    supabase.table("profile_chat_sessions").update({
        "status": "completed",
        "completed_at": datetime.utcnow().isoformat(),
        "resulting_profile_id": profile_id
    }).eq("id", str(session_id)).execute()
    
    return CompleteSessionResponse(
        success=True,
        profile_id=str(profile_id) if profile_id else None,
        message="Profile saved successfully!" if profile_id else "Session completed"
    )


@router.get("/active/current")
async def get_active_session(
    profile_type: str,
    current_user: dict = Depends(get_current_user)
):
    """Get the user's active chat session for a profile type, if any."""
    user_id = current_user["id"]
    
    result = supabase.table("profile_chat_sessions").select("*").eq(
        "user_id", user_id
    ).eq("profile_type", profile_type).eq("status", "active").order(
        "created_at", desc=True
    ).limit(1).execute()
    
    if result.data:
        session = result.data[0]
        return {
            "has_active_session": True,
            "session_id": session["id"],
            "completeness_score": session.get("completeness_score", 0),
            "message_count": len(session.get("messages", [])),
            "last_activity_at": session.get("last_activity_at")
        }
    
    return {"has_active_session": False}

