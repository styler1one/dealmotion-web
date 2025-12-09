"""
Sales Profile Router - API endpoints for sales rep profiles
"""
from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field
from typing import Optional, Dict, Any, List
import uuid
from app.deps import get_current_user
from app.database import get_supabase_service
from app.services.profile_service import ProfileService
from app.services.interview_service import InterviewService

# Use centralized database module
supabase = get_supabase_service()


router = APIRouter(prefix="/api/v1/profile/sales", tags=["sales_profile"])


# ==========================================
# Pydantic Models
# ==========================================

class InterviewStartResponse(BaseModel):
    """Response for starting interview."""
    session_id: str
    question_id: int
    question: str
    progress: int
    total_questions: int


class InterviewAnswerRequest(BaseModel):
    """Request for submitting interview answer."""
    session_id: str
    question_id: int
    answer: str


class InterviewAnswerResponse(BaseModel):
    """Response after submitting answer."""
    question_id: Optional[int] = None
    question: Optional[str] = None
    progress: int
    total_questions: int
    completed: bool = False


class InterviewCompleteRequest(BaseModel):
    """Request for completing interview."""
    session_id: str
    responses: Optional[Dict[int, str]] = Field(None, description="Map of question_id to answer (optional, will be retrieved from session)")


class SalesProfileResponse(BaseModel):
    """Sales profile response."""
    id: str
    user_id: str
    organization_id: str
    full_name: str
    role: Optional[str] = None
    experience_years: Optional[int] = None
    sales_methodology: Optional[str] = None
    methodology_description: Optional[str] = None
    communication_style: Optional[str] = None
    style_notes: Optional[str] = None
    strengths: List[str] = []
    areas_to_improve: List[str] = []
    target_industries: List[str] = []
    target_regions: List[str] = []
    target_company_sizes: List[str] = []
    quarterly_goals: Optional[str] = None
    preferred_meeting_types: List[str] = []
    ai_summary: Optional[str] = None
    profile_completeness: int
    version: int
    created_at: str
    updated_at: str


class SalesProfileUpdateRequest(BaseModel):
    """Request for updating sales profile."""
    role: Optional[str] = None
    experience_years: Optional[int] = None
    sales_methodology: Optional[str] = None
    methodology_description: Optional[str] = None
    communication_style: Optional[str] = None
    style_notes: Optional[str] = None
    strengths: Optional[List[str]] = None
    areas_to_improve: Optional[List[str]] = None
    target_industries: Optional[List[str]] = None
    target_regions: Optional[List[str]] = None
    target_company_sizes: Optional[List[str]] = None
    quarterly_goals: Optional[str] = None
    preferred_meeting_types: Optional[List[str]] = None


# ==========================================
# Interview Endpoints
# ==========================================

@router.post("/interview/start", response_model=InterviewStartResponse)
async def start_interview(
    current_user: dict = Depends(get_current_user)
):
    """
    Start a new onboarding interview.
    
    Returns the first question and session ID.
    """
    try:
        interview_service = InterviewService()
        result = interview_service.start_interview()
        
        return InterviewStartResponse(**result)
        
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to start interview: {str(e)}"
        )


@router.post("/interview/answer", response_model=InterviewAnswerResponse)
async def submit_answer(
    request: InterviewAnswerRequest,
    current_user: dict = Depends(get_current_user)
):
    """
    Submit an answer to an interview question.
    
    Returns the next question or completion status.
    """
    try:
        interview_service = InterviewService()
        
        # Store answer (in production, store in Redis/cache)
        # For now, we'll just get the next question
        
        next_question = interview_service.get_next_question(
            current_question_id=request.question_id,
            responses={}  # In production, retrieve from cache
        )
        
        if next_question is None:
            # Interview complete - progress equals total questions
            return InterviewAnswerResponse(
                progress=15,
                total_questions=15,
                completed=True
            )
        
        return InterviewAnswerResponse(
            question_id=next_question["question_id"],
            question=next_question["question"],
            progress=next_question["progress"],
            total_questions=next_question["total_questions"],
            completed=False
        )
        
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to submit answer: {str(e)}"
        )


@router.post("/interview/complete", response_model=SalesProfileResponse)
async def complete_interview(
    request: InterviewCompleteRequest,
    current_user: dict = Depends(get_current_user)
):
    """
    Complete the interview and generate profile.
    
    Analyzes all responses with AI and creates structured profile.
    """
    try:
        interview_service = InterviewService()
        profile_service = ProfileService()
        
        # Get responses from request
        responses = request.responses
        if not responses or len(responses) == 0:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="No responses provided. Please complete the interview first."
            )
        
        # Analyze responses with AI
        print(f"DEBUG: Analyzing interview responses for user {current_user['sub']}")
        profile_data = await interview_service.analyze_responses(responses)
        
        # Generate personalization settings
        personalization = await interview_service.generate_personalization_settings(profile_data)
        profile_data["personalization_settings"] = personalization
        
        # Get user's organization from organization_members (single source of truth)
        user_id = current_user.get("sub")
        organization_id = current_user.get("organization_id")
        if not organization_id:
            # Get from organization_members
            org_member_result = supabase.table("organization_members").select("organization_id").eq("user_id", user_id).limit(1).execute()
            
            if org_member_result.data and len(org_member_result.data) > 0:
                organization_id = org_member_result.data[0]["organization_id"]
            else:
                # User not in any organization - create one and add them
                email = current_user.get('email', 'User')
                # Generate slug from email (remove special chars, lowercase)
                slug = email.split('@')[0].lower().replace('.', '-').replace('_', '-')
                
                org_data = {
                    "id": str(uuid.uuid4()),
                    "name": f"Personal - {email}",
                    "slug": slug,
                    "created_at": "now()",
                    "updated_at": "now()"
                }
                org_result = supabase.table("organizations").insert(org_data).execute()
                organization_id = org_result.data[0]["id"] if org_result.data else str(uuid.uuid4())
                
                # Add user to the new organization
                supabase.table("organization_members").insert({
                    "user_id": user_id,
                    "organization_id": organization_id,
                    "role": "owner"
                }).execute()
                print(f"DEBUG: Created organization {organization_id} and added user {user_id}")
        
        # Create profile
        print(f"DEBUG: Creating sales profile for user {current_user['sub']}")
        profile = profile_service.create_sales_profile(
            user_id=current_user["sub"],
            organization_id=organization_id,
            profile_data=profile_data
        )
        
        if not profile:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Failed to create profile"
            )
        
        print(f"DEBUG: Profile created successfully: {profile['id']}")
        return SalesProfileResponse(**profile)
        
    except HTTPException:
        raise
    except Exception as e:
        print(f"ERROR: Failed to complete interview: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to complete interview: {str(e)}"
        )


# ==========================================
# Profile CRUD Endpoints
# ==========================================

@router.get("", response_model=SalesProfileResponse)
async def get_profile(
    current_user: dict = Depends(get_current_user)
):
    """
    Get current user's sales profile.
    """
    try:
        profile_service = ProfileService()
        profile = profile_service.get_sales_profile(current_user["sub"])
        
        if not profile:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Profile not found"
            )
        
        return SalesProfileResponse(**profile)
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to get profile: {str(e)}"
        )


@router.patch("", response_model=SalesProfileResponse)
async def update_profile(
    updates: SalesProfileUpdateRequest,
    current_user: dict = Depends(get_current_user)
):
    """
    Update current user's sales profile.
    """
    try:
        profile_service = ProfileService()
        
        # Convert to dict and remove None values
        update_data = {
            k: v for k, v in updates.dict().items()
            if v is not None
        }
        
        if not update_data:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="No fields to update"
            )
        
        profile = profile_service.update_sales_profile(
            user_id=current_user["sub"],
            updates=update_data
        )
        
        if not profile:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Profile not found"
            )
        
        return SalesProfileResponse(**profile)
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to update profile: {str(e)}"
        )


@router.delete("", status_code=status.HTTP_204_NO_CONTENT)
async def delete_profile(
    current_user: dict = Depends(get_current_user)
):
    """
    Delete current user's sales profile.
    """
    try:
        profile_service = ProfileService()
        success = profile_service.delete_sales_profile(current_user["sub"])
        
        if not success:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Profile not found"
            )
        
        return None
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to delete profile: {str(e)}"
        )


# ==========================================
# Profile Check Endpoint
# ==========================================

@router.get("/check")
async def check_profile_exists(
    current_user: dict = Depends(get_current_user)
):
    """
    Check if user has a profile.
    
    Used for first-time user detection.
    """
    try:
        profile_service = ProfileService()
        profile = profile_service.get_sales_profile(current_user["sub"])
        
        return {
            "exists": profile is not None,
            "completeness": profile.get("profile_completeness", 0) if profile else 0
        }
        
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to check profile: {str(e)}"
        )


# ==========================================
# Style Guide Endpoints
# ==========================================

class StyleGuideRequest(BaseModel):
    """Request for updating style guide."""
    tone: Optional[str] = None  # direct, warm, formal, casual, professional
    formality: Optional[str] = None  # formal, professional, casual
    language_style: Optional[str] = None  # technical, business, simple
    persuasion_style: Optional[str] = None  # logic, story, reference
    emoji_usage: Optional[bool] = None
    signoff: Optional[str] = None
    writing_length: Optional[str] = None  # concise, detailed


class StyleGuideResponse(BaseModel):
    """Style guide response."""
    tone: str = "professional"
    formality: str = "professional"
    language_style: str = "business"
    persuasion_style: str = "logic"
    emoji_usage: bool = False
    signoff: str = "Best regards"
    writing_length: str = "concise"
    confidence_score: float = 0.5
    
    model_config = {"extra": "ignore"}  # Ignore unknown fields from database


@router.get("/style-guide", response_model=StyleGuideResponse)
async def get_style_guide(
    current_user: dict = Depends(get_current_user)
):
    """
    Get the user's communication style guide.
    
    Returns style guide from profile, or defaults if not set.
    """
    try:
        profile_service = ProfileService()
        profile = profile_service.get_sales_profile(current_user["sub"])
        
        if not profile:
            # Return defaults
            return StyleGuideResponse()
        
        # Return style guide if exists, otherwise derive from profile
        style_guide = profile.get("style_guide")
        if style_guide:
            return StyleGuideResponse(**style_guide)
        
        # Derive from existing fields
        communication_style = (profile.get("communication_style") or "").lower()
        
        tone = "professional"
        if "direct" in communication_style:
            tone = "direct"
        elif "warm" in communication_style or "relationship" in communication_style:
            tone = "warm"
        elif "formal" in communication_style:
            tone = "formal"
        elif "casual" in communication_style:
            tone = "casual"
        
        return StyleGuideResponse(
            tone=tone,
            formality="professional",
            language_style="business",
            persuasion_style="logic",
            emoji_usage=profile.get("uses_emoji", False),
            signoff=profile.get("email_signoff", "Best regards"),
            writing_length=profile.get("writing_length_preference", "concise"),
            confidence_score=0.5
        )
        
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to get style guide: {str(e)}"
        )


@router.put("/style-guide", response_model=StyleGuideResponse)
async def update_style_guide(
    request: StyleGuideRequest,
    current_user: dict = Depends(get_current_user)
):
    """
    Update the user's communication style guide.
    
    Allows users to customize their AI output style.
    """
    try:
        profile_service = ProfileService()
        profile = profile_service.get_sales_profile(current_user["sub"])
        
        if not profile:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Profile not found. Complete onboarding first."
            )
        
        # Get existing style guide or create new one
        existing_guide = profile.get("style_guide") or {
            "tone": "professional",
            "formality": "professional",
            "language_style": "business",
            "persuasion_style": "logic",
            "emoji_usage": False,
            "signoff": "Best regards",
            "writing_length": "concise",
            "confidence_score": 0.5
        }
        
        # Update with provided values
        update_data = request.model_dump(exclude_unset=True)
        for key, value in update_data.items():
            if value is not None:
                existing_guide[key] = value
        
        # Set high confidence since user manually configured
        existing_guide["confidence_score"] = 1.0
        
        # Save to profile
        updated = profile_service.update_sales_profile(
            user_id=current_user["sub"],
            updates={"style_guide": existing_guide},
            organization_id=profile.get("organization_id")
        )
        
        if not updated:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Failed to update style guide"
            )
        
        return StyleGuideResponse(**existing_guide)
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to update style guide: {str(e)}"
        )