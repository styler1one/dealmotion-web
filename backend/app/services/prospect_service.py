"""
Prospect Service - CRUD operations for prospects
Uses the database function get_or_create_prospect for consistency
"""
from typing import Optional, Dict, Any, List
from supabase import Client
import logging
from app.database import get_supabase_service

logger = logging.getLogger(__name__)


class ProspectService:
    """Service for managing prospects."""
    
    def __init__(self):
        """Initialize Supabase client using centralized module."""
        self.client: Client = get_supabase_service()
    
    def get_or_create_prospect(
        self,
        organization_id: str,
        company_name: str
    ) -> Optional[str]:
        """
        Get existing prospect or create new one.
        Uses the database function for atomic operation.
        
        Args:
            organization_id: Organization ID
            company_name: Company name (will be normalized)
            
        Returns:
            Prospect ID (UUID string) or None if error
        """
        try:
            # Call the database function
            result = self.client.rpc(
                'get_or_create_prospect',
                {
                    'p_organization_id': organization_id,
                    'p_company_name': company_name.strip()
                }
            ).execute()
            
            if result.data:
                return result.data
            return None
            
        except Exception as e:
            logger.error(f"Error in get_or_create_prospect: {e}")
            return None
    
    def get_prospect_by_id(
        self,
        prospect_id: str,
        organization_id: str
    ) -> Optional[Dict[str, Any]]:
        """
        Get prospect by ID.
        
        Args:
            prospect_id: Prospect ID
            organization_id: Organization ID (for security)
            
        Returns:
            Prospect dict or None
        """
        try:
            response = self.client.table("prospects")\
                .select("*")\
                .eq("id", prospect_id)\
                .eq("organization_id", organization_id)\
                .execute()
            
            if response.data and len(response.data) > 0:
                return response.data[0]
            return None
            
        except Exception as e:
            logger.error(f"Error getting prospect: {e}")
            return None
    
    def get_prospect_by_name(
        self,
        organization_id: str,
        company_name: str
    ) -> Optional[Dict[str, Any]]:
        """
        Get prospect by company name (normalized).
        
        Args:
            organization_id: Organization ID
            company_name: Company name
            
        Returns:
            Prospect dict or None
        """
        try:
            normalized = company_name.strip().lower()
            
            response = self.client.table("prospects")\
                .select("*")\
                .eq("organization_id", organization_id)\
                .eq("company_name_normalized", normalized)\
                .execute()
            
            if response.data and len(response.data) > 0:
                return response.data[0]
            return None
            
        except Exception as e:
            logger.error(f"Error getting prospect by name: {e}")
            return None
    
    def list_prospects(
        self,
        organization_id: str,
        status: Optional[str] = None,
        limit: int = 50,
        offset: int = 0
    ) -> List[Dict[str, Any]]:
        """
        List prospects for organization.
        
        Args:
            organization_id: Organization ID
            status: Optional status filter
            limit: Max results
            offset: Pagination offset
            
        Returns:
            List of prospect dicts
        """
        try:
            query = self.client.table("prospects")\
                .select("*")\
                .eq("organization_id", organization_id)
            
            if status:
                query = query.eq("status", status)
            
            query = query.order("last_activity_at", desc=True)\
                .range(offset, offset + limit - 1)
            
            response = query.execute()
            return response.data or []
            
        except Exception as e:
            logger.error(f"Error listing prospects: {e}")
            return []
    
    def update_prospect(
        self,
        prospect_id: str,
        organization_id: str,
        updates: Dict[str, Any]
    ) -> Optional[Dict[str, Any]]:
        """
        Update prospect fields.
        
        Args:
            prospect_id: Prospect ID
            organization_id: Organization ID (for security)
            updates: Fields to update
            
        Returns:
            Updated prospect dict or None
        """
        try:
            # Don't allow updating certain fields
            protected_fields = ['id', 'organization_id', 'company_name_normalized', 'created_at']
            for field in protected_fields:
                updates.pop(field, None)
            
            response = self.client.table("prospects")\
                .update(updates)\
                .eq("id", prospect_id)\
                .eq("organization_id", organization_id)\
                .execute()
            
            if response.data and len(response.data) > 0:
                return response.data[0]
            return None
            
        except Exception as e:
            logger.error(f"Error updating prospect: {e}")
            return None
    
    def delete_prospect(
        self,
        prospect_id: str,
        organization_id: str
    ) -> bool:
        """
        Delete prospect.
        
        Args:
            prospect_id: Prospect ID
            organization_id: Organization ID (for security)
            
        Returns:
            True if deleted, False otherwise
        """
        try:
            response = self.client.table("prospects")\
                .delete()\
                .eq("id", prospect_id)\
                .eq("organization_id", organization_id)\
                .execute()
            
            return True
            
        except Exception as e:
            logger.error(f"Error deleting prospect: {e}")
            return False
    
    def get_prospect_with_activity(
        self,
        prospect_id: str,
        organization_id: str
    ) -> Optional[Dict[str, Any]]:
        """
        Get prospect with activity counts.
        
        Args:
            prospect_id: Prospect ID
            organization_id: Organization ID
            
        Returns:
            Prospect dict with activity counts
        """
        try:
            # Get prospect
            prospect = self.get_prospect_by_id(prospect_id, organization_id)
            if not prospect:
                return None
            
            # Get activity counts
            research_count = self.client.table("research_briefs")\
                .select("id", count="exact")\
                .eq("prospect_id", prospect_id)\
                .execute()
            
            prep_count = self.client.table("meeting_preps")\
                .select("id", count="exact")\
                .eq("prospect_id", prospect_id)\
                .execute()
            
            followup_count = self.client.table("followups")\
                .select("id", count="exact")\
                .eq("prospect_id", prospect_id)\
                .execute()
            
            prospect["research_count"] = len(research_count.data) if research_count.data else 0
            prospect["prep_count"] = len(prep_count.data) if prep_count.data else 0
            prospect["followup_count"] = len(followup_count.data) if followup_count.data else 0
            prospect["total_activities"] = (
                prospect["research_count"] + 
                prospect["prep_count"] + 
                prospect["followup_count"]
            )
            
            return prospect
            
        except Exception as e:
            logger.error(f"Error getting prospect with activity: {e}")
            return None


# Singleton instance
_prospect_service: Optional[ProspectService] = None


def get_prospect_service() -> ProspectService:
    """Get singleton ProspectService instance."""
    global _prospect_service
    if _prospect_service is None:
        _prospect_service = ProspectService()
    return _prospect_service


