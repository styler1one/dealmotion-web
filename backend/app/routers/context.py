"""
Context Router - Internal API for agents to get user context
"""
from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from typing import Dict, Any
from app.deps import get_current_user
from app.services.context_service import ContextService


router = APIRouter(prefix="/api/v1/context", tags=["context"])


# ==========================================
# Pydantic Models
# ==========================================

class ContextResponse(BaseModel):
    """Full context response."""
    sales_profile: Dict[str, Any] | None
    company_profile: Dict[str, Any] | None
    kb_summary: Dict[str, Any]


class ContextSummaryResponse(BaseModel):
    """Context summary response."""
    has_sales_profile: bool
    sales_profile_completeness: int
    has_company_profile: bool
    company_profile_completeness: int
    has_knowledge_base: bool
    kb_document_count: int
    context_quality: str


class ContextPromptResponse(BaseModel):
    """Context formatted for prompt."""
    context: str
    token_estimate: int


# ==========================================
# Context Endpoints
# ==========================================

@router.get("", response_model=ContextResponse)
async def get_context(
    current_user: dict = Depends(get_current_user)
):
    """
    Get full user context.
    
    Returns sales profile, company profile, and KB summary.
    Used by AI agents to get personalization context.
    """
    try:
        organization_id = current_user.get("organization_id")
        if not organization_id:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="User must be part of an organization"
            )
        
        context_service = ContextService()
        context = context_service.get_user_context(
            user_id=current_user["sub"],
            organization_id=organization_id
        )
        
        return ContextResponse(**context)
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to get context: {str(e)}"
        )


@router.get("/summary", response_model=ContextSummaryResponse)
async def get_context_summary(
    current_user: dict = Depends(get_current_user)
):
    """
    Get context summary.
    
    Returns availability and completeness of each context component.
    Useful for UI to show profile status.
    """
    try:
        organization_id = current_user.get("organization_id")
        if not organization_id:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="User must be part of an organization"
            )
        
        context_service = ContextService()
        summary = context_service.get_context_summary(
            user_id=current_user["sub"],
            organization_id=organization_id
        )
        
        return ContextSummaryResponse(**summary)
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to get context summary: {str(e)}"
        )


@router.get("/prompt", response_model=ContextPromptResponse)
async def get_context_for_prompt(
    max_tokens: int = 2000,
    current_user: dict = Depends(get_current_user)
):
    """
    Get context formatted for AI prompt injection.
    
    Returns formatted context string optimized for AI prompts.
    Used by agents to inject context into prompts.
    
    Args:
        max_tokens: Maximum tokens to use (default: 2000)
    """
    try:
        organization_id = current_user.get("organization_id")
        if not organization_id:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="User must be part of an organization"
            )
        
        context_service = ContextService()
        context_str = context_service.get_context_for_prompt(
            user_id=current_user["sub"],
            organization_id=organization_id,
            max_tokens=max_tokens
        )
        
        # Rough token estimate (4 chars = 1 token)
        token_estimate = len(context_str) // 4
        
        return ContextPromptResponse(
            context=context_str,
            token_estimate=token_estimate
        )
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to get context for prompt: {str(e)}"
        )


@router.post("/invalidate", status_code=status.HTTP_204_NO_CONTENT)
async def invalidate_context_cache(
    current_user: dict = Depends(get_current_user)
):
    """
    Invalidate cached context.
    
    Call this after updating profile to force cache refresh.
    """
    try:
        organization_id = current_user.get("organization_id")
        if not organization_id:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="User must be part of an organization"
            )
        
        context_service = ContextService()
        context_service.invalidate_cache(
            user_id=current_user["sub"],
            organization_id=organization_id
        )
        
        return None
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to invalidate cache: {str(e)}"
        )
