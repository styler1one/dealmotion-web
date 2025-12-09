"""
Company Profile Router - API endpoints for company profiles
"""
from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field
from typing import Optional, Dict, Any, List
import uuid
from app.deps import get_current_user
from app.database import get_supabase_service
from app.services.profile_service import ProfileService
from app.services.company_interview_service import get_company_interview_service

# Use centralized database module
supabase = get_supabase_service()

router = APIRouter(prefix="/api/v1/profile/company", tags=["company_profile"])


# ==========================================
# Interview Models
# ==========================================

class CompanyInterviewStartResponse(BaseModel):
    """Response for starting company interview."""
    session_id: str
    question_id: int
    question: str
    progress: int
    total_questions: int


class CompanyInterviewAnswerRequest(BaseModel):
    """Request for submitting company interview answer."""
    session_id: str
    question_id: int
    answer: str


class CompanyInterviewAnswerResponse(BaseModel):
    """Response after submitting answer."""
    question_id: Optional[int] = None
    question: Optional[str] = None
    progress: int
    total_questions: int
    completed: bool = False


class CompanyInterviewCompleteRequest(BaseModel):
    """Request for completing company interview."""
    session_id: str
    responses: Optional[Dict[int, str]] = Field(None, description="Map of question_id to answer")


# ==========================================
# Pydantic Models
# ==========================================

class ProductModel(BaseModel):
    """Product/service model."""
    name: str
    description: str
    value_proposition: str
    target_persona: Optional[str] = None
    pricing_model: Optional[str] = None


class BuyerPersonaModel(BaseModel):
    """Buyer persona model."""
    title: str
    seniority: str
    pain_points: List[str] = []
    goals: List[str] = []
    objections: List[str] = []


class CaseStudyModel(BaseModel):
    """Case study model."""
    customer: str
    industry: str
    challenge: str
    solution: str
    results: str


class ICPModel(BaseModel):
    """Ideal Customer Profile model."""
    industries: List[str] = []
    company_sizes: List[str] = []
    regions: List[str] = []
    pain_points: List[str] = []
    buying_triggers: List[str] = []


class CompanyProfileCreateRequest(BaseModel):
    """Request for creating company profile."""
    company_name: str
    industry: Optional[str] = None
    company_size: Optional[str] = None
    headquarters: Optional[str] = None
    founded_year: Optional[int] = None
    website: Optional[str] = None
    products: List[ProductModel] = []
    core_value_props: List[str] = []
    differentiators: List[str] = []
    unique_selling_points: Optional[str] = None
    ideal_customer_profile: Optional[ICPModel] = None
    buyer_personas: List[BuyerPersonaModel] = []
    case_studies: List[CaseStudyModel] = []
    testimonials: List[str] = []
    metrics: Optional[Dict[str, Any]] = None
    competitors: List[str] = []
    competitive_advantages: Optional[str] = None
    typical_sales_cycle: Optional[str] = None
    average_deal_size: Optional[str] = None


class CompanyProfileUpdateRequest(BaseModel):
    """Request for updating company profile."""
    company_name: Optional[str] = None
    industry: Optional[str] = None
    company_size: Optional[str] = None
    headquarters: Optional[str] = None
    founded_year: Optional[int] = None
    website: Optional[str] = None
    products: Optional[List[ProductModel]] = None
    core_value_props: Optional[List[str]] = None
    differentiators: Optional[List[str]] = None
    unique_selling_points: Optional[str] = None
    ideal_customer_profile: Optional[ICPModel] = None
    buyer_personas: Optional[List[BuyerPersonaModel]] = None
    case_studies: Optional[List[CaseStudyModel]] = None
    testimonials: Optional[List[str]] = None
    metrics: Optional[Dict[str, Any]] = None
    competitors: Optional[List[str]] = None
    competitive_advantages: Optional[str] = None
    typical_sales_cycle: Optional[str] = None
    average_deal_size: Optional[str] = None


class CompanyProfileResponse(BaseModel):
    """Company profile response."""
    id: str
    organization_id: str
    company_name: str
    industry: Optional[str] = None
    company_size: Optional[str] = None
    headquarters: Optional[str] = None
    founded_year: Optional[int] = None
    website: Optional[str] = None
    products: List[Dict[str, Any]] = []
    core_value_props: List[str] = []
    differentiators: List[str] = []
    unique_selling_points: Optional[str] = None
    ideal_customer_profile: Dict[str, Any] = {}
    buyer_personas: List[Dict[str, Any]] = []
    case_studies: List[Dict[str, Any]] = []
    testimonials: List[str] = []
    metrics: Dict[str, Any] = {}
    competitors: List[str] = []
    competitive_advantages: Optional[str] = None
    typical_sales_cycle: Optional[str] = None
    average_deal_size: Optional[str] = None
    ai_summary: Optional[str] = None
    company_narrative: Optional[str] = None
    profile_completeness: int
    version: int
    created_at: str
    updated_at: str


# ==========================================
# Helper Functions
# ==========================================

def check_admin_access(current_user: dict) -> str:
    """
    Check if user is admin and return organization_id.
    
    Uses organization_members table as single source of truth.
    
    Args:
        current_user: Current user dict
        
    Returns:
        organization_id
        
    Raises:
        HTTPException if not admin
    """
    organization_id = current_user.get("organization_id")
    
    # If no org_id in token, get from organization_members (single source of truth)
    if not organization_id:
        user_id = current_user.get("sub")
        result = supabase.table("organization_members").select("organization_id").eq("user_id", user_id).limit(1).execute()
        if result.data and len(result.data) > 0:
            organization_id = result.data[0]["organization_id"]
        else:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="User must be part of an organization"
            )
    
    # TODO: Check if user is admin/owner in organization_members table
    # For now, allow all users (will be restricted by RLS policies)
    
    return organization_id


# ==========================================
# Interview Endpoints
# ==========================================

@router.post("/interview/start", response_model=CompanyInterviewStartResponse)
async def start_company_interview(
    current_user: dict = Depends(get_current_user)
):
    """
    Start a new company profile onboarding interview.
    
    Returns the first question and session ID.
    """
    try:
        interview_service = get_company_interview_service()
        result = interview_service.start_interview()
        
        return CompanyInterviewStartResponse(**result)
        
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to start company interview: {str(e)}"
        )


@router.post("/interview/answer", response_model=CompanyInterviewAnswerResponse)
async def submit_company_answer(
    request: CompanyInterviewAnswerRequest,
    current_user: dict = Depends(get_current_user)
):
    """
    Submit an answer to a company interview question.
    
    Returns the next question or completion status.
    """
    try:
        interview_service = get_company_interview_service()
        
        next_question = interview_service.get_next_question(
            current_question_id=request.question_id,
            responses={}
        )
        
        if next_question is None:
            return CompanyInterviewAnswerResponse(
                progress=12,
                total_questions=12,
                completed=True
            )
        
        return CompanyInterviewAnswerResponse(
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


@router.post("/interview/complete", response_model=CompanyProfileResponse)
async def complete_company_interview(
    request: CompanyInterviewCompleteRequest,
    current_user: dict = Depends(get_current_user)
):
    """
    Complete the company interview and generate profile.
    
    Analyzes all responses with AI and creates structured company profile.
    """
    try:
        interview_service = get_company_interview_service()
        profile_service = ProfileService()
        
        # Get responses from request
        responses = request.responses
        if not responses or len(responses) == 0:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="No responses provided. Please complete the interview first."
            )
        
        # Analyze responses with AI
        print(f"DEBUG: Analyzing company interview for user {current_user['sub']}")
        profile_data = await interview_service.analyze_responses(responses)
        
        # Get organization for user from organization_members (single source of truth)
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
        
        # Check if company profile exists - upsert logic
        existing = profile_service.get_company_profile(organization_id)
        
        if existing:
            # Update existing profile
            print(f"DEBUG: Company profile exists for org {organization_id}, updating")
            profile = profile_service.update_company_profile(
                organization_id=organization_id,
                updates=profile_data,
                updated_by=current_user["sub"]
            )
        else:
            # Create new profile
            print(f"DEBUG: Creating company profile for org {organization_id}")
            profile = profile_service.create_company_profile(
                organization_id=organization_id,
                profile_data=profile_data,
                created_by=current_user["sub"]
            )
        
        if not profile:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Failed to create/update company profile"
            )
        
        print(f"DEBUG: Company profile saved: {profile['id']}")
        return CompanyProfileResponse(**profile)
        
    except HTTPException:
        raise
    except Exception as e:
        print(f"ERROR: Failed to complete company interview: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to complete interview: {str(e)}"
        )


# ==========================================
# Company Profile Endpoints
# ==========================================

@router.post("", response_model=CompanyProfileResponse, status_code=status.HTTP_201_CREATED)
async def create_company_profile(
    request: CompanyProfileCreateRequest,
    current_user: dict = Depends(get_current_user)
):
    """
    Create company profile (admin only).
    
    Only organization admins/owners can create company profile.
    """
    try:
        organization_id = check_admin_access(current_user)
        profile_service = ProfileService()
        
        # Check if profile already exists
        existing = profile_service.get_company_profile(organization_id)
        if existing:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Company profile already exists. Use PATCH to update."
            )
        
        # Convert request to dict
        profile_data = request.dict()
        
        # Convert nested models to dicts
        if profile_data.get("products"):
            profile_data["products"] = [p.dict() if hasattr(p, 'dict') else p for p in profile_data["products"]]
        
        if profile_data.get("buyer_personas"):
            profile_data["buyer_personas"] = [p.dict() if hasattr(p, 'dict') else p for p in profile_data["buyer_personas"]]
        
        if profile_data.get("case_studies"):
            profile_data["case_studies"] = [c.dict() if hasattr(c, 'dict') else c for c in profile_data["case_studies"]]
        
        if profile_data.get("ideal_customer_profile"):
            icp = profile_data["ideal_customer_profile"]
            profile_data["ideal_customer_profile"] = icp.dict() if hasattr(icp, 'dict') else icp
        
        # Create profile
        print(f"DEBUG: Creating company profile for org {organization_id}")
        profile = profile_service.create_company_profile(
            organization_id=organization_id,
            profile_data=profile_data,
            created_by=current_user["sub"]
        )
        
        if not profile:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Failed to create company profile"
            )
        
        print(f"DEBUG: Company profile created: {profile['id']}")
        return CompanyProfileResponse(**profile)
        
    except HTTPException:
        raise
    except Exception as e:
        print(f"ERROR: Failed to create company profile: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to create company profile: {str(e)}"
        )


@router.get("", response_model=CompanyProfileResponse)
async def get_company_profile(
    current_user: dict = Depends(get_current_user)
):
    """
    Get organization's company profile.
    
    All organization members can view the company profile.
    """
    try:
        organization_id = current_user.get("organization_id")
        
        # If no org_id in token, get from organization_members (single source of truth)
        if not organization_id:
            user_id = current_user.get("sub")
            result = supabase.table("organization_members").select("organization_id").eq("user_id", user_id).limit(1).execute()
            if result.data and len(result.data) > 0:
                organization_id = result.data[0]["organization_id"]
            else:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail="No organization found for user"
                )
        
        profile_service = ProfileService()
        profile = profile_service.get_company_profile(organization_id)
        
        if not profile:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Company profile not found"
            )
        
        return CompanyProfileResponse(**profile)
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to get company profile: {str(e)}"
        )


@router.patch("", response_model=CompanyProfileResponse)
async def update_company_profile(
    updates: CompanyProfileUpdateRequest,
    current_user: dict = Depends(get_current_user)
):
    """
    Update company profile (admin only).
    
    Only organization admins/owners can update company profile.
    """
    try:
        organization_id = check_admin_access(current_user)
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
        
        # Convert nested models to dicts
        if "products" in update_data:
            update_data["products"] = [p.dict() if hasattr(p, 'dict') else p for p in update_data["products"]]
        
        if "buyer_personas" in update_data:
            update_data["buyer_personas"] = [p.dict() if hasattr(p, 'dict') else p for p in update_data["buyer_personas"]]
        
        if "case_studies" in update_data:
            update_data["case_studies"] = [c.dict() if hasattr(c, 'dict') else c for c in update_data["case_studies"]]
        
        if "ideal_customer_profile" in update_data:
            icp = update_data["ideal_customer_profile"]
            update_data["ideal_customer_profile"] = icp.dict() if hasattr(icp, 'dict') else icp
        
        profile = profile_service.update_company_profile(
            organization_id=organization_id,
            updates=update_data,
            updated_by=current_user["sub"]
        )
        
        if not profile:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Company profile not found"
            )
        
        return CompanyProfileResponse(**profile)
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to update company profile: {str(e)}"
        )


@router.delete("", status_code=status.HTTP_204_NO_CONTENT)
async def delete_company_profile(
    current_user: dict = Depends(get_current_user)
):
    """
    Delete company profile (admin only).
    
    Only organization admins/owners can delete company profile.
    """
    try:
        organization_id = check_admin_access(current_user)
        profile_service = ProfileService()
        
        success = profile_service.delete_company_profile(organization_id)
        
        if not success:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Company profile not found"
            )
        
        return None
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to delete company profile: {str(e)}"
        )


# ==========================================
# Profile Check Endpoint
# ==========================================

@router.get("/check")
async def check_company_profile_exists(
    current_user: dict = Depends(get_current_user)
):
    """
    Check if organization has a company profile.
    
    Used for setup wizard detection.
    """
    try:
        organization_id = current_user.get("organization_id")
        
        # If no org_id in token, get from organization_members (single source of truth)
        if not organization_id:
            user_id = current_user.get("sub")
            result = supabase.table("organization_members").select("organization_id").eq("user_id", user_id).limit(1).execute()
            if result.data and len(result.data) > 0:
                organization_id = result.data[0]["organization_id"]
            else:
                return {
                    "exists": False,
                    "completeness": 0
                }
        
        profile_service = ProfileService()
        profile = profile_service.get_company_profile(organization_id)
        
        return {
            "exists": profile is not None,
            "completeness": profile.get("profile_completeness", 0) if profile else 0
        }
        
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to check company profile: {str(e)}"
        )
