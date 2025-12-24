"""
Profile Service - CRUD operations for sales and company profiles
"""
from typing import Optional, Dict, Any, List
from datetime import datetime
from supabase import Client
from app.database import get_supabase_service
import json


class ProfileService:
    """Service for managing sales and company profiles."""
    
    def __init__(self):
        """Initialize Supabase client using centralized module."""
        self.client: Client = get_supabase_service()
    
    # ==========================================
    # Sales Profile Methods
    # ==========================================
    
    def get_sales_profile(self, user_id: str, organization_id: str = None) -> Optional[Dict[str, Any]]:
        """
        Get sales profile for a user.
        
        Args:
            user_id: User ID
            organization_id: Optional organization ID to filter by
            
        Returns:
            Profile dict or None if not found
        """
        try:
            query = self.client.table("sales_profiles")\
                .select("*")\
                .eq("user_id", user_id)
            
            if organization_id:
                query = query.eq("organization_id", organization_id)
            
            response = query.execute()
            
            if response.data and len(response.data) > 0:
                return response.data[0]
            return None
            
        except Exception as e:
            print(f"Error getting sales profile: {str(e)}")
            return None
    
    def create_sales_profile(
        self,
        user_id: str,
        organization_id: str,
        profile_data: Dict[str, Any]
    ) -> Optional[Dict[str, Any]]:
        """
        Create or update a sales profile (upsert).
        
        Args:
            user_id: User ID
            organization_id: Organization ID
            profile_data: Profile data dict
            
        Returns:
            Created/updated profile dict or None if error
        """
        try:
            # Check if profile already exists for this user+org combination
            existing = self.get_sales_profile(user_id, organization_id)
            
            if existing:
                # Update existing profile
                print(f"Profile exists for user {user_id} in org {organization_id}, updating instead of creating")
                return self.update_sales_profile(user_id, profile_data, organization_id)
            
            # Prepare data for new profile
            data = {
                "user_id": user_id,
                "organization_id": organization_id,
                **profile_data
            }
            
            # Calculate completeness
            completeness = self._calculate_sales_completeness(data)
            data["profile_completeness"] = completeness
            
            # Insert new profile
            response = self.client.table("sales_profiles")\
                .insert(data)\
                .execute()
            
            if response.data and len(response.data) > 0:
                profile = response.data[0]
                
                # Sync full_name to users table if present
                if profile_data.get("full_name"):
                    try:
                        self.client.table("users").update({
                            "full_name": profile_data["full_name"]
                        }).eq("id", user_id).execute()
                    except Exception as sync_error:
                        print(f"Warning: Failed to sync full_name to users table: {sync_error}")
                
                # Create version record
                self._create_version_record(
                    profile_type="sales",
                    profile_id=profile["id"],
                    version=1,
                    data=profile,
                    changed_by=user_id,
                    change_summary="Initial profile creation"
                )
                
                return profile
            return None
            
        except Exception as e:
            print(f"Error creating sales profile: {str(e)}")
            return None
    
    def update_sales_profile(
        self,
        user_id: str,
        updates: Dict[str, Any],
        organization_id: str = None
    ) -> Optional[Dict[str, Any]]:
        """
        Update a sales profile.
        
        Args:
            user_id: User ID
            updates: Fields to update
            organization_id: Optional organization ID to filter by
            
        Returns:
            Updated profile dict or None if error
        """
        try:
            # Get current profile
            current = self.get_sales_profile(user_id, organization_id)
            if not current:
                return None
            
            # Calculate new completeness
            updated_data = {**current, **updates}
            completeness = self._calculate_sales_completeness(updated_data)
            updates["profile_completeness"] = completeness
            
            # Increment version
            new_version = current.get("version", 1) + 1
            updates["version"] = new_version
            
            # Update using the profile's ID for precision
            response = self.client.table("sales_profiles")\
                .update(updates)\
                .eq("id", current["id"])\
                .execute()
            
            if response.data and len(response.data) > 0:
                profile = response.data[0]
                
                # Sync full_name to users table if it was updated
                if "full_name" in updates and updates["full_name"]:
                    try:
                        self.client.table("users").update({
                            "full_name": updates["full_name"]
                        }).eq("id", user_id).execute()
                    except Exception as sync_error:
                        print(f"Warning: Failed to sync full_name to users table: {sync_error}")
                
                # Create version record
                self._create_version_record(
                    profile_type="sales",
                    profile_id=profile["id"],
                    version=new_version,
                    data=profile,
                    changed_by=user_id,
                    change_summary="Profile updated"
                )
                
                return profile
            return None
            
        except Exception as e:
            print(f"Error updating sales profile: {str(e)}")
            return None
    
    def delete_sales_profile(self, user_id: str) -> bool:
        """
        Delete a sales profile.
        
        Args:
            user_id: User ID
            
        Returns:
            True if deleted, False otherwise
        """
        try:
            response = self.client.table("sales_profiles")\
                .delete()\
                .eq("user_id", user_id)\
                .execute()
            
            return True
            
        except Exception as e:
            print(f"Error deleting sales profile: {str(e)}")
            return False
    
    # ==========================================
    # Company Profile Methods
    # ==========================================
    
    def get_company_profile(self, organization_id: str) -> Optional[Dict[str, Any]]:
        """
        Get company profile for an organization.
        
        Args:
            organization_id: Organization ID
            
        Returns:
            Profile dict or None if not found
        """
        try:
            response = self.client.table("company_profiles")\
                .select("*")\
                .eq("organization_id", organization_id)\
                .execute()
            
            if response.data and len(response.data) > 0:
                return response.data[0]
            return None
            
        except Exception as e:
            print(f"Error getting company profile: {str(e)}")
            return None
    
    def create_company_profile(
        self,
        organization_id: str,
        profile_data: Dict[str, Any],
        created_by: str
    ) -> Optional[Dict[str, Any]]:
        """
        Create a new company profile.
        
        Args:
            organization_id: Organization ID
            profile_data: Profile data dict
            created_by: User ID who created it
            
        Returns:
            Created profile dict or None if error
        """
        try:
            # Prepare data
            data = {
                "organization_id": organization_id,
                **profile_data
            }
            
            # Calculate completeness
            completeness = self._calculate_company_completeness(data)
            data["profile_completeness"] = completeness
            
            # Insert
            response = self.client.table("company_profiles")\
                .insert(data)\
                .execute()
            
            if response.data and len(response.data) > 0:
                profile = response.data[0]
                
                # Create version record
                self._create_version_record(
                    profile_type="company",
                    profile_id=profile["id"],
                    version=1,
                    data=profile,
                    changed_by=created_by,
                    change_summary="Initial company profile creation"
                )
                
                return profile
            return None
            
        except Exception as e:
            print(f"Error creating company profile: {str(e)}")
            return None
    
    def update_company_profile(
        self,
        organization_id: str,
        updates: Dict[str, Any],
        updated_by: str
    ) -> Optional[Dict[str, Any]]:
        """
        Update a company profile.
        
        Args:
            organization_id: Organization ID
            updates: Fields to update
            updated_by: User ID who updated it
            
        Returns:
            Updated profile dict or None if error
        """
        try:
            # Get current profile
            current = self.get_company_profile(organization_id)
            if not current:
                return None
            
            # Calculate new completeness
            updated_data = {**current, **updates}
            completeness = self._calculate_company_completeness(updated_data)
            updates["profile_completeness"] = completeness
            
            # Increment version
            new_version = current.get("version", 1) + 1
            updates["version"] = new_version
            
            # Update
            response = self.client.table("company_profiles")\
                .update(updates)\
                .eq("organization_id", organization_id)\
                .execute()
            
            if response.data and len(response.data) > 0:
                profile = response.data[0]
                
                # Create version record
                self._create_version_record(
                    profile_type="company",
                    profile_id=profile["id"],
                    version=new_version,
                    data=profile,
                    changed_by=updated_by,
                    change_summary="Company profile updated"
                )
                
                return profile
            return None
            
        except Exception as e:
            print(f"Error updating company profile: {str(e)}")
            return None
    
    def delete_company_profile(self, organization_id: str) -> bool:
        """
        Delete a company profile.
        
        Args:
            organization_id: Organization ID
            
        Returns:
            True if deleted, False otherwise
        """
        try:
            response = self.client.table("company_profiles")\
                .delete()\
                .eq("organization_id", organization_id)\
                .execute()
            
            return True
            
        except Exception as e:
            print(f"Error deleting company profile: {str(e)}")
            return False
    
    # ==========================================
    # Profile Versions
    # ==========================================
    
    def get_profile_versions(
        self,
        profile_type: str,
        profile_id: str,
        limit: int = 10
    ) -> List[Dict[str, Any]]:
        """
        Get version history for a profile.
        
        Args:
            profile_type: 'sales' or 'company'
            profile_id: Profile ID
            limit: Max number of versions to return
            
        Returns:
            List of version dicts
        """
        try:
            response = self.client.table("profile_versions")\
                .select("*")\
                .eq("profile_type", profile_type)\
                .eq("profile_id", profile_id)\
                .order("created_at", desc=True)\
                .limit(limit)\
                .execute()
            
            return response.data if response.data else []
            
        except Exception as e:
            print(f"Error getting profile versions: {str(e)}")
            return []
    
    def _create_version_record(
        self,
        profile_type: str,
        profile_id: str,
        version: int,
        data: Dict[str, Any],
        changed_by: str,
        change_summary: str
    ) -> bool:
        """Create a version record for audit trail."""
        try:
            version_data = {
                "profile_type": profile_type,
                "profile_id": profile_id,
                "version": version,
                "data": data,
                "changed_by": changed_by,
                "change_summary": change_summary
            }
            
            self.client.table("profile_versions")\
                .insert(version_data)\
                .execute()
            
            return True
            
        except Exception as e:
            print(f"Error creating version record: {str(e)}")
            return False
    
    # ==========================================
    # Completeness Calculation
    # ==========================================
    
    def _calculate_sales_completeness(self, profile: Dict[str, Any]) -> int:
        """
        Calculate completeness score for sales profile.
        
        Args:
            profile: Profile data dict
            
        Returns:
            Completeness score (0-100)
        """
        completeness = 0
        
        # Required fields (20 points each)
        if profile.get("full_name"):
            completeness += 20
        
        if profile.get("sales_methodology"):
            completeness += 20
        
        if profile.get("communication_style"):
            completeness += 20
        
        # Optional but important fields (10 points each)
        if profile.get("strengths") and len(profile.get("strengths", [])) > 0:
            completeness += 10
        
        if profile.get("target_industries") and len(profile.get("target_industries", [])) > 0:
            completeness += 10
        
        if profile.get("quarterly_goals"):
            completeness += 10
        
        if profile.get("ai_summary"):
            completeness += 10
        
        return min(completeness, 100)
    
    def _calculate_company_completeness(self, profile: Dict[str, Any]) -> int:
        """
        Calculate completeness score for company profile.
        
        Args:
            profile: Profile data dict
            
        Returns:
            Completeness score (0-100)
        """
        completeness = 0
        
        # Required fields (15 points each)
        if profile.get("company_name"):
            completeness += 15
        
        if profile.get("industry"):
            completeness += 15
        
        if profile.get("products") and len(profile.get("products", [])) > 0:
            completeness += 15
        
        if profile.get("core_value_props") and len(profile.get("core_value_props", [])) > 0:
            completeness += 15
        
        # Optional but important fields (10 points each)
        icp = profile.get("ideal_customer_profile", {})
        if icp and icp != {}:
            completeness += 10
        
        if profile.get("buyer_personas") and len(profile.get("buyer_personas", [])) > 0:
            completeness += 10
        
        if profile.get("case_studies") and len(profile.get("case_studies", [])) > 0:
            completeness += 10
        
        if profile.get("ai_summary"):
            completeness += 10
        
        return min(completeness, 100)
