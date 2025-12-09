"""
Dashboard Router
TASK-041 / SPEC-036

Provides dashboard-specific endpoints like activity feed.
"""

from fastapi import APIRouter, Depends, HTTPException
from typing import List, Optional
from datetime import datetime
import logging

from app.deps import get_current_user
from app.database import get_supabase_service

logger = logging.getLogger(__name__)
router = APIRouter()


@router.get("/activity")
async def get_recent_activity(
    limit: int = 5,
    current_user: dict = Depends(get_current_user)
):
    """
    Get recent activities across all prospects for dashboard.
    Returns a unified activity feed from research, prep, and followup.
    """
    supabase = get_supabase_service()
    user_id = current_user["sub"]
    
    try:
        # Get organization ID
        org_result = supabase.table("organization_members") \
            .select("organization_id") \
            .eq("user_id", user_id) \
            .limit(1) \
            .execute()
        
        if not org_result.data:
            return {"activities": [], "count": 0}
        
        organization_id = org_result.data[0]["organization_id"]
        
        activities = []
        
        # Get recent completed research
        research_result = supabase.table("research_briefs") \
            .select("id, company_name, status, created_at") \
            .eq("organization_id", organization_id) \
            .eq("status", "completed") \
            .order("created_at", desc=True) \
            .limit(limit) \
            .execute()
        
        for r in (research_result.data or []):
            activities.append({
                "id": f"research-{r['id']}",
                "type": "research_completed",
                "company": r["company_name"],
                "timestamp": r["created_at"],
                "icon": "search",
                "color": "blue"
            })
        
        # Get recent completed preps
        prep_result = supabase.table("meeting_preps") \
            .select("id, prospect_company_name, status, created_at") \
            .eq("organization_id", organization_id) \
            .eq("status", "completed") \
            .order("created_at", desc=True) \
            .limit(limit) \
            .execute()
        
        for p in (prep_result.data or []):
            activities.append({
                "id": f"prep-{p['id']}",
                "type": "prep_generated",
                "company": p["prospect_company_name"],
                "timestamp": p["created_at"],
                "icon": "fileText",
                "color": "green"
            })
        
        # Get recent completed followups
        followup_result = supabase.table("followups") \
            .select("id, prospect_company_name, meeting_subject, status, created_at, updated_at") \
            .eq("organization_id", organization_id) \
            .eq("status", "completed") \
            .order("updated_at", desc=True) \
            .limit(limit) \
            .execute()
        
        for f in (followup_result.data or []):
            company = f["prospect_company_name"] or f["meeting_subject"] or "Meeting"
            activities.append({
                "id": f"followup-{f['id']}",
                "type": "followup_created",
                "company": company,
                "timestamp": f["updated_at"] or f["created_at"],
                "icon": "mail",
                "color": "orange"
            })
        
        # Get recent contacts added (join with prospects to get company name)
        contacts_result = supabase.table("prospect_contacts") \
            .select("id, name, created_at, prospects(company_name)") \
            .eq("organization_id", organization_id) \
            .order("created_at", desc=True) \
            .limit(limit) \
            .execute()
        
        for c in (contacts_result.data or []):
            company_name = c.get("prospects", {}).get("company_name", "Unknown") if c.get("prospects") else "Unknown"
            activities.append({
                "id": f"contact-{c['id']}",
                "type": "contact_added",
                "company": company_name,
                "contact_name": c.get("name", "Unknown"),
                "timestamp": c["created_at"],
                "icon": "userPlus",
                "color": "purple"
            })
        
        # Sort all activities by timestamp (most recent first)
        activities.sort(key=lambda x: x["timestamp"], reverse=True)
        
        # Limit to requested number
        activities = activities[:limit]
        
        return {
            "activities": activities,
            "count": len(activities)
        }
        
    except Exception as e:
        logger.error(f"Error fetching dashboard activity: {e}")
        raise HTTPException(status_code=500, detail=str(e))

