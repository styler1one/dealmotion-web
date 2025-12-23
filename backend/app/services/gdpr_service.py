"""
GDPR Service

Handles GDPR compliance operations:
- Account deletion with 48-hour grace period
- Data export in JSON format
- Data summary for transparency
- Billing data anonymization

All operations are audited and logged.
"""

import json
import hashlib
import zipfile
import io
from datetime import datetime, timedelta
from typing import Optional, List, Dict, Any, Tuple
from uuid import UUID
import logging

from supabase import Client

from app.database import get_supabase_service
from app.models.gdpr import (
    DeletionStatus,
    DeletionRequestStatus,
    ExportStatus,
    DeletionResult,
    DataSummaryResponse,
    DataCategorySummary,
    StorageUsageSummary,
    ExportData,
)

logger = logging.getLogger(__name__)

# Grace period for deletion (48 hours)
DELETION_GRACE_PERIOD_HOURS = 48

# Export expiration (7 days)
EXPORT_EXPIRATION_DAYS = 7

# Tables to clean during deletion (in order of dependency)
TABLES_TO_DELETE = [
    # First: tables with no FK dependencies on other user tables
    "coach_suggestions",
    "coach_behavior_events",
    "coach_user_patterns",
    "coach_daily_tips",
    "coach_settings",
    "autopilot_proposals",
    "autopilot_settings",
    "meeting_outcomes",
    "user_prep_preferences",
    "followup_actions",
    "knowledge_base_chunks",
    "knowledge_base_files",
    "prospect_activities",
    "prospect_notes",
    "prospect_contacts",
    "followups",
    "meeting_preps",
    "meetings",
    "deals",
    "research_sources",
    "research_briefs",
    "prospects",
    "external_recordings",
    "scheduled_recordings",
    "mobile_recordings",
    "recording_integrations",
    "calendar_meetings",
    "calendar_connections",
    "profile_versions",
    "company_profiles",
    "sales_profiles",
    "user_settings",
    "admin_notes",  # target_id = user_id
    "credit_transactions",
    "credit_consumption",
    "credit_balances",
    "usage_records",
    "flow_packs",
    "organization_subscriptions",
    "organization_members",
]

# Storage buckets to clean
STORAGE_BUCKETS = [
    "knowledge-base-files",
    "followup-audio",
    "research-pdfs",
    "recordings",
]


class GDPRService:
    """Service for GDPR compliance operations."""
    
    def __init__(self, supabase: Optional[Client] = None):
        self.supabase = supabase or get_supabase_service()
    
    # ============================================================
    # DELETION CHECK
    # ============================================================
    
    async def can_delete_account(
        self, 
        user_id: str
    ) -> Tuple[bool, Optional[str], Optional[datetime]]:
        """
        Check if user can delete their account.
        
        Returns: (can_delete, reason, subscription_end_date)
        """
        try:
            # Check for active paid subscription
            result = self.supabase.rpc(
                "can_user_be_deleted",
                {"p_user_id": user_id}
            ).execute()
            
            if result.data and len(result.data) > 0:
                row = result.data[0]
                if not row.get("can_delete"):
                    # Get subscription end date for context
                    sub_result = self.supabase.table("organization_subscriptions").select(
                        "current_period_end"
                    ).eq(
                        "organization_id",
                        self._get_user_org_id(user_id)
                    ).single().execute()
                    
                    end_date = None
                    if sub_result.data:
                        end_date = sub_result.data.get("current_period_end")
                    
                    return False, row.get("reason"), end_date
            
            return True, None, None
            
        except Exception as e:
            logger.error(f"Error checking deletion eligibility: {e}")
            return False, "Error checking account status", None
    
    # ============================================================
    # DELETION REQUEST
    # ============================================================
    
    async def request_deletion(
        self,
        user_id: str,
        user_email: str,
        reason: Optional[str] = None,
        ip_address: Optional[str] = None,
        user_agent: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Request account deletion with 48-hour grace period.
        
        Returns deletion request details.
        """
        try:
            # Check if deletion is allowed
            can_delete, block_reason, _ = await self.can_delete_account(user_id)
            if not can_delete:
                return {
                    "success": False,
                    "message": block_reason or "Cannot delete account at this time"
                }
            
            # Get organization ID
            org_id = self._get_user_org_id(user_id)
            
            # Calculate scheduled deletion time (48 hours from now)
            scheduled_for = datetime.utcnow() + timedelta(hours=DELETION_GRACE_PERIOD_HOURS)
            
            # Create deletion request
            request_data = {
                "user_id": user_id,
                "user_email": user_email,
                "organization_id": org_id,
                "scheduled_for": scheduled_for.isoformat(),
                "reason": reason,
                "status": DeletionRequestStatus.PENDING.value,
                "ip_address": ip_address,
                "user_agent": user_agent,
            }
            
            result = self.supabase.table("gdpr_deletion_requests").insert(
                request_data
            ).execute()
            
            if not result.data or len(result.data) == 0:
                raise Exception("Failed to create deletion request")
            
            deletion_request = result.data[0]
            
            # Update user status
            self.supabase.table("users").update({
                "deletion_status": DeletionStatus.PENDING_DELETION.value,
                "deletion_requested_at": datetime.utcnow().isoformat(),
                "deletion_scheduled_at": scheduled_for.isoformat(),
                "deletion_reason": reason,
            }).eq("id", user_id).execute()
            
            logger.info(f"Deletion request created for user {user_id}, scheduled for {scheduled_for}")
            
            return {
                "success": True,
                "message": "Account deletion scheduled",
                "deletion_request_id": deletion_request["id"],
                "scheduled_for": scheduled_for,
                "can_cancel_until": scheduled_for,
                "grace_period_hours": DELETION_GRACE_PERIOD_HOURS,
            }
            
        except Exception as e:
            logger.error(f"Error creating deletion request: {e}")
            return {
                "success": False,
                "message": f"Error scheduling deletion: {str(e)}"
            }
    
    async def cancel_deletion(
        self,
        user_id: str,
        reason: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Cancel a pending deletion request."""
        try:
            # Find pending deletion request
            result = self.supabase.table("gdpr_deletion_requests").select("*").eq(
                "user_id", user_id
            ).eq(
                "status", DeletionRequestStatus.PENDING.value
            ).single().execute()
            
            if not result.data:
                return {
                    "success": False,
                    "message": "No pending deletion request found"
                }
            
            # Update deletion request
            self.supabase.table("gdpr_deletion_requests").update({
                "status": DeletionRequestStatus.CANCELLED.value,
                "cancelled_at": datetime.utcnow().isoformat(),
                "cancellation_reason": reason,
            }).eq("id", result.data["id"]).execute()
            
            # Update user status back to active
            self.supabase.table("users").update({
                "deletion_status": DeletionStatus.ACTIVE.value,
                "deletion_requested_at": None,
                "deletion_scheduled_at": None,
                "deletion_reason": None,
            }).eq("id", user_id).execute()
            
            logger.info(f"Deletion cancelled for user {user_id}")
            
            return {
                "success": True,
                "message": "Account deletion cancelled"
            }
            
        except Exception as e:
            logger.error(f"Error cancelling deletion: {e}")
            return {
                "success": False,
                "message": f"Error cancelling deletion: {str(e)}"
            }
    
    async def get_deletion_status(self, user_id: str) -> Dict[str, Any]:
        """Get current deletion status for user."""
        try:
            result = self.supabase.table("gdpr_deletion_requests").select("*").eq(
                "user_id", user_id
            ).order("created_at", desc=True).limit(1).execute()
            
            if not result.data or len(result.data) == 0:
                return {
                    "has_pending_deletion": False,
                    "can_cancel": False,
                }
            
            request = result.data[0]
            is_pending = request["status"] == DeletionRequestStatus.PENDING.value
            
            return {
                "has_pending_deletion": is_pending,
                "deletion_request_id": request["id"],
                "status": request["status"],
                "scheduled_for": request["scheduled_for"],
                "can_cancel": is_pending,
                "requested_at": request["requested_at"],
                "reason": request.get("reason"),
            }
            
        except Exception as e:
            logger.error(f"Error getting deletion status: {e}")
            return {
                "has_pending_deletion": False,
                "can_cancel": False,
            }
    
    # ============================================================
    # DELETION EXECUTION (called by Inngest)
    # ============================================================
    
    async def execute_deletion(self, deletion_request_id: str) -> DeletionResult:
        """
        Execute the actual account deletion.
        Called by Inngest after grace period expires.
        """
        errors = []
        tables_cleaned = []
        storage_deleted = []
        vectors_deleted = []
        billing_anonymized = 0
        auth_deleted = False
        
        try:
            # Get deletion request
            result = self.supabase.table("gdpr_deletion_requests").select("*").eq(
                "id", deletion_request_id
            ).single().execute()
            
            if not result.data:
                raise Exception("Deletion request not found")
            
            request = result.data
            user_id = request["user_id"]
            org_id = request.get("organization_id")
            
            # Mark as processing
            self.supabase.table("gdpr_deletion_requests").update({
                "status": DeletionRequestStatus.PROCESSING.value,
                "processing_started_at": datetime.utcnow().isoformat(),
            }).eq("id", deletion_request_id).execute()
            
            logger.info(f"Starting deletion for user {user_id}")
            
            # 1. Anonymize billing data first (before deleting)
            try:
                billing_anonymized = await self._anonymize_billing_data(
                    user_id, org_id, deletion_request_id
                )
            except Exception as e:
                errors.append(f"Billing anonymization error: {str(e)}")
                logger.error(f"Billing anonymization error: {e}")
            
            # 2. Delete from storage buckets
            for bucket in STORAGE_BUCKETS:
                try:
                    deleted = await self._delete_storage_files(user_id, org_id, bucket)
                    if deleted:
                        storage_deleted.append(bucket)
                except Exception as e:
                    errors.append(f"Storage {bucket} error: {str(e)}")
                    logger.error(f"Storage deletion error for {bucket}: {e}")
            
            # 3. Delete vector embeddings from Pinecone
            try:
                deleted = await self._delete_vector_embeddings(org_id)
                if deleted:
                    vectors_deleted.append(f"kb-{org_id}")
            except Exception as e:
                errors.append(f"Vector deletion error: {str(e)}")
                logger.error(f"Vector deletion error: {e}")
            
            # 4. Delete from database tables
            for table in TABLES_TO_DELETE:
                try:
                    await self._delete_from_table(table, user_id, org_id)
                    tables_cleaned.append(table)
                except Exception as e:
                    errors.append(f"Table {table} error: {str(e)}")
                    logger.error(f"Table deletion error for {table}: {e}")
            
            # 5. Delete organization (if sole owner)
            try:
                await self._delete_organization_if_empty(org_id)
            except Exception as e:
                errors.append(f"Organization cleanup error: {str(e)}")
                logger.error(f"Organization cleanup error: {e}")
            
            # 6. Delete from users table
            try:
                self.supabase.table("users").update({
                    "deletion_status": DeletionStatus.DELETED.value,
                    "deletion_completed_at": datetime.utcnow().isoformat(),
                    "email": f"deleted-{user_id[:8]}@deleted.dealmotion.ai",
                    "full_name": None,
                }).eq("id", user_id).execute()
            except Exception as e:
                errors.append(f"Users table update error: {str(e)}")
                logger.error(f"Users table update error: {e}")
            
            # 7. Delete from Supabase Auth
            try:
                self.supabase.auth.admin.delete_user(user_id)
                auth_deleted = True
            except Exception as e:
                errors.append(f"Auth deletion error: {str(e)}")
                logger.error(f"Auth deletion error: {e}")
            
            # Update deletion request as completed
            success = len(errors) == 0
            self.supabase.table("gdpr_deletion_requests").update({
                "status": DeletionRequestStatus.COMPLETED.value if success else DeletionRequestStatus.FAILED.value,
                "completed_at": datetime.utcnow().isoformat(),
                "deletion_summary": {
                    "tables_cleaned": tables_cleaned,
                    "storage_deleted": storage_deleted,
                    "vectors_deleted": vectors_deleted,
                    "billing_records_anonymized": billing_anonymized,
                    "auth_user_deleted": auth_deleted,
                    "errors": errors,
                },
                "error_message": "; ".join(errors) if errors else None,
                "billing_data_anonymized": billing_anonymized > 0,
            }).eq("id", deletion_request_id).execute()
            
            logger.info(f"Deletion completed for user {user_id}, errors: {len(errors)}")
            
            return DeletionResult(
                success=success,
                tables_cleaned=tables_cleaned,
                storage_deleted=storage_deleted,
                vectors_deleted=vectors_deleted,
                billing_records_anonymized=billing_anonymized,
                auth_user_deleted=auth_deleted,
                errors=errors,
            )
            
        except Exception as e:
            logger.error(f"Fatal deletion error: {e}")
            
            # Mark as failed
            try:
                self.supabase.table("gdpr_deletion_requests").update({
                    "status": DeletionRequestStatus.FAILED.value,
                    "error_message": str(e),
                }).eq("id", deletion_request_id).execute()
            except:
                pass
            
            return DeletionResult(
                success=False,
                tables_cleaned=tables_cleaned,
                storage_deleted=storage_deleted,
                vectors_deleted=vectors_deleted,
                billing_records_anonymized=billing_anonymized,
                auth_user_deleted=auth_deleted,
                errors=[str(e)] + errors,
            )
    
    async def _anonymize_billing_data(
        self, 
        user_id: str, 
        org_id: Optional[str],
        deletion_request_id: str
    ) -> int:
        """Anonymize billing data for retention."""
        count = 0
        
        if not org_id:
            return count
        
        try:
            # Generate hash for this user
            user_hash = hashlib.sha256(
                f"{user_id}-dealmotion-billing-archive-{datetime.utcnow().timestamp()}".encode()
            ).hexdigest()
            
            org_hash = hashlib.sha256(
                f"{org_id}-dealmotion-billing-archive".encode()
            ).hexdigest() if org_id else None
            
            # Get payment history
            payments = self.supabase.table("payment_history").select("*").eq(
                "organization_id", org_id
            ).execute()
            
            if payments.data:
                for payment in payments.data:
                    # Archive the payment
                    self.supabase.table("billing_archive").insert({
                        "user_hash": user_hash,
                        "organization_hash": org_hash,
                        "original_payment_id": payment["id"],
                        "stripe_invoice_id": payment.get("stripe_invoice_id"),
                        "stripe_payment_intent_id": payment.get("stripe_payment_intent_id"),
                        "stripe_charge_id": payment.get("stripe_charge_id"),
                        "amount_cents": payment["amount_cents"],
                        "currency": payment.get("currency", "eur"),
                        "status": payment["status"],
                        "invoice_pdf_url": payment.get("invoice_pdf_url"),
                        "invoice_number": payment.get("invoice_number"),
                        "original_paid_at": payment.get("paid_at"),
                        "original_created_at": payment.get("created_at"),
                        "gdpr_request_id": deletion_request_id,
                    }).execute()
                    count += 1
            
            # Update deletion request with hash
            self.supabase.table("gdpr_deletion_requests").update({
                "billing_retention_hash": user_hash,
            }).eq("id", deletion_request_id).execute()
            
            logger.info(f"Anonymized {count} billing records for user {user_id}")
            
        except Exception as e:
            logger.error(f"Error anonymizing billing data: {e}")
            raise
        
        return count
    
    async def _delete_storage_files(
        self, 
        user_id: str, 
        org_id: Optional[str], 
        bucket: str
    ) -> bool:
        """Delete user files from a storage bucket."""
        try:
            # Try to list and delete files for this user/org
            prefixes_to_try = [
                f"{user_id}/",
                f"{org_id}/" if org_id else None,
            ]
            
            deleted_any = False
            
            for prefix in prefixes_to_try:
                if not prefix:
                    continue
                    
                try:
                    files = self.supabase.storage.from_(bucket).list(prefix)
                    if files:
                        paths = [f"{prefix}{f['name']}" for f in files]
                        if paths:
                            self.supabase.storage.from_(bucket).remove(paths)
                            deleted_any = True
                            logger.info(f"Deleted {len(paths)} files from {bucket}/{prefix}")
                except Exception as e:
                    # Bucket might not exist or be empty
                    logger.debug(f"No files to delete in {bucket}/{prefix}: {e}")
            
            return deleted_any
            
        except Exception as e:
            logger.error(f"Error deleting from storage bucket {bucket}: {e}")
            raise
    
    async def _delete_vector_embeddings(self, org_id: Optional[str]) -> bool:
        """Delete vector embeddings from Pinecone."""
        if not org_id:
            return False
            
        try:
            from app.services.vector_store import VectorStore
            
            vector_store = VectorStore()
            namespace = f"kb-{org_id}"
            
            # Delete all vectors in the namespace
            await vector_store.delete_by_filter(
                namespace=namespace,
                filter={"organization_id": org_id}
            )
            
            logger.info(f"Deleted vectors from namespace {namespace}")
            return True
            
        except Exception as e:
            logger.error(f"Error deleting vectors: {e}")
            # Don't raise - vectors might not exist
            return False
    
    async def _delete_from_table(
        self, 
        table: str, 
        user_id: str, 
        org_id: Optional[str]
    ):
        """Delete records from a table."""
        try:
            # Try user_id first
            try:
                self.supabase.table(table).delete().eq("user_id", user_id).execute()
            except:
                pass
            
            # Then try organization_id
            if org_id:
                try:
                    self.supabase.table(table).delete().eq("organization_id", org_id).execute()
                except:
                    pass
            
            # Special case for admin_notes (target_id)
            if table == "admin_notes":
                try:
                    self.supabase.table(table).delete().eq("target_id", user_id).execute()
                except:
                    pass
                    
        except Exception as e:
            logger.error(f"Error deleting from {table}: {e}")
            raise
    
    async def _delete_organization_if_empty(self, org_id: Optional[str]):
        """Delete organization if no other members remain."""
        if not org_id:
            return
            
        try:
            # Check if any members remain
            members = self.supabase.table("organization_members").select("id").eq(
                "organization_id", org_id
            ).execute()
            
            if not members.data or len(members.data) == 0:
                # Delete the organization
                self.supabase.table("organizations").delete().eq("id", org_id).execute()
                logger.info(f"Deleted empty organization {org_id}")
                
        except Exception as e:
            logger.error(f"Error cleaning up organization: {e}")
            raise
    
    # ============================================================
    # DATA EXPORT
    # ============================================================
    
    async def request_export(
        self,
        user_id: str,
        organization_id: str,
        ip_address: Optional[str] = None,
        user_agent: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Request a data export."""
        try:
            # Check for existing pending export
            existing = self.supabase.table("gdpr_data_exports").select("*").eq(
                "user_id", user_id
            ).in_(
                "status", [ExportStatus.PENDING.value, ExportStatus.PROCESSING.value]
            ).execute()
            
            if existing.data and len(existing.data) > 0:
                return {
                    "success": False,
                    "message": "Export already in progress",
                    "export_id": existing.data[0]["id"],
                }
            
            # Create export request
            expires_at = datetime.utcnow() + timedelta(days=EXPORT_EXPIRATION_DAYS)
            
            result = self.supabase.table("gdpr_data_exports").insert({
                "user_id": user_id,
                "organization_id": organization_id,
                "status": ExportStatus.PENDING.value,
                "expires_at": expires_at.isoformat(),
                "ip_address": ip_address,
                "user_agent": user_agent,
            }).execute()
            
            if not result.data or len(result.data) == 0:
                raise Exception("Failed to create export request")
            
            export_request = result.data[0]
            
            # Estimated completion (usually quick, but set 5 minutes for safety)
            estimated_completion = datetime.utcnow() + timedelta(minutes=5)
            
            logger.info(f"Export requested for user {user_id}")
            
            return {
                "success": True,
                "message": "Data export requested",
                "export_id": export_request["id"],
                "estimated_completion": estimated_completion,
            }
            
        except Exception as e:
            logger.error(f"Error requesting export: {e}")
            return {
                "success": False,
                "message": f"Error requesting export: {str(e)}"
            }
    
    async def generate_export(self, export_id: str) -> bool:
        """
        Generate the actual data export.
        Called by Inngest.
        """
        try:
            # Get export request
            result = self.supabase.table("gdpr_data_exports").select("*").eq(
                "id", export_id
            ).single().execute()
            
            if not result.data:
                raise Exception("Export request not found")
            
            export_request = result.data
            user_id = export_request["user_id"]
            org_id = export_request["organization_id"]
            
            # Mark as processing
            self.supabase.table("gdpr_data_exports").update({
                "status": ExportStatus.PROCESSING.value,
                "processing_started_at": datetime.utcnow().isoformat(),
            }).eq("id", export_id).execute()
            
            logger.info(f"Generating export for user {user_id}")
            
            # Collect all user data
            export_data = await self._collect_export_data(user_id, org_id)
            
            # Create ZIP file
            zip_buffer = io.BytesIO()
            with zipfile.ZipFile(zip_buffer, 'w', zipfile.ZIP_DEFLATED) as zf:
                # Add JSON files
                if export_data.get("profile"):
                    zf.writestr("profile.json", json.dumps(export_data["profile"], indent=2, default=str))
                if export_data.get("account"):
                    zf.writestr("account.json", json.dumps(export_data["account"], indent=2, default=str))
                if export_data.get("company"):
                    zf.writestr("company.json", json.dumps(export_data["company"], indent=2, default=str))
                if export_data.get("content"):
                    for key, value in export_data["content"].items():
                        zf.writestr(f"content/{key}.json", json.dumps(value, indent=2, default=str))
                if export_data.get("activity"):
                    for key, value in export_data["activity"].items():
                        zf.writestr(f"activity/{key}.json", json.dumps(value, indent=2, default=str))
                
                # Add README
                readme = self._generate_export_readme(user_id, export_data)
                zf.writestr("README.txt", readme)
            
            zip_buffer.seek(0)
            zip_data = zip_buffer.read()
            
            # Upload to storage
            storage_path = f"{user_id}/export-{export_id}.zip"
            self.supabase.storage.from_("gdpr-exports").upload(
                storage_path,
                zip_data,
                {"content-type": "application/zip"}
            )
            
            # Create signed URL (7 days)
            signed_url = self.supabase.storage.from_("gdpr-exports").create_signed_url(
                storage_path,
                EXPORT_EXPIRATION_DAYS * 24 * 60 * 60  # seconds
            )
            
            download_url = signed_url.get("signedURL") if isinstance(signed_url, dict) else signed_url.signed_url
            
            # Update export record
            self.supabase.table("gdpr_data_exports").update({
                "status": ExportStatus.READY.value,
                "completed_at": datetime.utcnow().isoformat(),
                "storage_path": storage_path,
                "file_size_bytes": len(zip_data),
                "download_url": download_url,
                "download_expires_at": (datetime.utcnow() + timedelta(days=EXPORT_EXPIRATION_DAYS)).isoformat(),
            }).eq("id", export_id).execute()
            
            logger.info(f"Export generated for user {user_id}, size: {len(zip_data)} bytes")
            
            return True
            
        except Exception as e:
            logger.error(f"Error generating export: {e}")
            
            # Mark as failed
            try:
                self.supabase.table("gdpr_data_exports").update({
                    "status": ExportStatus.FAILED.value,
                    "error_message": str(e),
                }).eq("id", export_id).execute()
            except:
                pass
            
            return False
    
    async def _collect_export_data(self, user_id: str, org_id: str) -> Dict[str, Any]:
        """Collect all user data for export."""
        data = {
            "export_version": "1.0",
            "exported_at": datetime.utcnow().isoformat(),
            "user_id": user_id,
        }
        
        # Profile data
        try:
            user_result = self.supabase.table("users").select("*").eq("id", user_id).single().execute()
            if user_result.data:
                data["account"] = {
                    "email": user_result.data.get("email"),
                    "full_name": user_result.data.get("full_name"),
                    "created_at": user_result.data.get("created_at"),
                }
        except:
            pass
        
        try:
            profile_result = self.supabase.table("sales_profiles").select("*").eq("user_id", user_id).single().execute()
            if profile_result.data:
                # Remove internal IDs
                profile = {k: v for k, v in profile_result.data.items() if k not in ["id", "user_id", "organization_id"]}
                data["profile"] = profile
        except:
            pass
        
        try:
            company_result = self.supabase.table("company_profiles").select("*").eq("organization_id", org_id).single().execute()
            if company_result.data:
                company = {k: v for k, v in company_result.data.items() if k not in ["id", "organization_id"]}
                data["company"] = company
        except:
            pass
        
        # Content data
        content = {}
        
        try:
            prospects = self.supabase.table("prospects").select("*").eq("organization_id", org_id).execute()
            if prospects.data:
                content["prospects"] = [{k: v for k, v in p.items() if k not in ["id", "organization_id"]} for p in prospects.data]
        except:
            pass
        
        try:
            research = self.supabase.table("research_briefs").select("*").eq("organization_id", org_id).execute()
            if research.data:
                content["research"] = [{k: v for k, v in r.items() if k not in ["id", "user_id", "organization_id"]} for r in research.data]
        except:
            pass
        
        try:
            preps = self.supabase.table("meeting_preps").select("*").eq("organization_id", org_id).execute()
            if preps.data:
                content["preparations"] = [{k: v for k, v in p.items() if k not in ["id", "user_id", "organization_id"]} for p in preps.data]
        except:
            pass
        
        try:
            followups = self.supabase.table("followups").select("*").eq("organization_id", org_id).execute()
            if followups.data:
                content["followups"] = [{k: v for k, v in f.items() if k not in ["id", "user_id", "organization_id"]} for f in followups.data]
        except:
            pass
        
        try:
            notes = self.supabase.table("prospect_notes").select("*").eq("user_id", user_id).execute()
            if notes.data:
                content["notes"] = [{k: v for k, v in n.items() if k not in ["id", "user_id", "organization_id", "prospect_id"]} for n in notes.data]
        except:
            pass
        
        if content:
            data["content"] = content
        
        # Activity data
        activity = {}
        
        try:
            settings = self.supabase.table("user_settings").select("*").eq("user_id", user_id).single().execute()
            if settings.data:
                activity["settings"] = {k: v for k, v in settings.data.items() if k not in ["id", "user_id"]}
        except:
            pass
        
        try:
            usage = self.supabase.table("usage_records").select("*").eq("organization_id", org_id).execute()
            if usage.data:
                activity["usage_stats"] = usage.data
        except:
            pass
        
        if activity:
            data["activity"] = activity
        
        return data
    
    def _generate_export_readme(self, user_id: str, data: Dict[str, Any]) -> str:
        """Generate README for export."""
        return f"""DealMotion Data Export
======================

Export Date: {datetime.utcnow().isoformat()}
User ID: {user_id}
Export Version: 1.0

Contents:
---------
- profile.json: Your sales profile information
- account.json: Your account details
- company.json: Your company profile
- content/: Your created content
  - prospects.json: Your prospect data
  - research.json: Research briefs
  - preparations.json: Meeting preparations
  - followups.json: Follow-up summaries
  - notes.json: Your notes
- activity/: Activity and usage data
  - settings.json: Your app settings
  - usage_stats.json: Usage statistics

Data Format: JSON (machine-readable)

If you have questions about this export, contact support@dealmotion.ai

This export was generated pursuant to your rights under the GDPR (General Data Protection Regulation).
"""
    
    async def get_export_status(self, user_id: str, export_id: str) -> Optional[Dict[str, Any]]:
        """Get status of a specific export."""
        try:
            result = self.supabase.table("gdpr_data_exports").select("*").eq(
                "id", export_id
            ).eq(
                "user_id", user_id
            ).single().execute()
            
            if not result.data:
                return None
            
            return result.data
            
        except Exception as e:
            logger.error(f"Error getting export status: {e}")
            return None
    
    async def list_exports(self, user_id: str) -> List[Dict[str, Any]]:
        """List all exports for a user."""
        try:
            result = self.supabase.table("gdpr_data_exports").select("*").eq(
                "user_id", user_id
            ).order("created_at", desc=True).limit(10).execute()
            
            return result.data or []
            
        except Exception as e:
            logger.error(f"Error listing exports: {e}")
            return []
    
    async def record_download(self, user_id: str, export_id: str):
        """Record that an export was downloaded."""
        try:
            self.supabase.table("gdpr_data_exports").update({
                "status": ExportStatus.DOWNLOADED.value,
                "downloaded_at": datetime.utcnow().isoformat(),
                "download_count": self.supabase.table("gdpr_data_exports").select("download_count").eq("id", export_id).single().execute().data.get("download_count", 0) + 1,
            }).eq("id", export_id).eq("user_id", user_id).execute()
        except Exception as e:
            logger.error(f"Error recording download: {e}")
    
    # ============================================================
    # DATA SUMMARY
    # ============================================================
    
    async def get_data_summary(self, user_id: str, user_email: str, organization_id: str) -> DataSummaryResponse:
        """Get summary of stored user data."""
        try:
            # Get user info
            user_result = self.supabase.table("users").select("created_at").eq("id", user_id).single().execute()
            created_at = datetime.fromisoformat(user_result.data["created_at"].replace("Z", "+00:00")) if user_result.data else datetime.utcnow()
            
            # Check profiles
            has_sales = False
            has_company = False
            
            try:
                sp = self.supabase.table("sales_profiles").select("id").eq("user_id", user_id).single().execute()
                has_sales = sp.data is not None
            except:
                pass
            
            try:
                cp = self.supabase.table("company_profiles").select("id").eq("organization_id", organization_id).single().execute()
                has_company = cp.data is not None
            except:
                pass
            
            # Data categories
            categories = []
            
            # Count data in each category
            tables_to_count = [
                ("prospects", "Prospects", "Companies you're researching or selling to"),
                ("prospect_contacts", "Contacts", "People at your prospect companies"),
                ("research_briefs", "Research Briefs", "AI-generated company research"),
                ("meeting_preps", "Meeting Preparations", "AI-generated meeting briefs"),
                ("followups", "Follow-ups", "Meeting recordings and summaries"),
                ("deals", "Deals", "Sales opportunities you're tracking"),
                ("prospect_notes", "Notes", "Your notes on prospects"),
                ("knowledge_base_files", "Knowledge Base Files", "Documents you've uploaded"),
            ]
            
            for table, name, desc in tables_to_count:
                try:
                    if table in ["prospects", "prospect_contacts", "research_briefs", "meeting_preps", "followups", "deals", "knowledge_base_files"]:
                        result = self.supabase.table(table).select("id, updated_at", count="exact").eq("organization_id", organization_id).execute()
                    else:
                        result = self.supabase.table(table).select("id, updated_at", count="exact").eq("user_id", user_id).execute()
                    
                    count = result.count or 0
                    last_updated = None
                    if result.data and len(result.data) > 0:
                        dates = [r.get("updated_at") or r.get("created_at") for r in result.data if r.get("updated_at") or r.get("created_at")]
                        if dates:
                            last_updated = max(dates)
                    
                    categories.append(DataCategorySummary(
                        category=name,
                        description=desc,
                        count=count,
                        last_updated=datetime.fromisoformat(last_updated.replace("Z", "+00:00")) if last_updated else None,
                    ))
                except Exception as e:
                    logger.debug(f"Error counting {table}: {e}")
            
            # Storage usage (simplified - would need storage API)
            storage = []
            total_storage = 0
            
            # Connected services
            calendars = []
            try:
                cal_result = self.supabase.table("calendar_connections").select("provider").eq("user_id", user_id).execute()
                if cal_result.data:
                    calendars = [c["provider"] for c in cal_result.data]
            except:
                pass
            
            integrations = []
            try:
                int_result = self.supabase.table("recording_integrations").select("provider").eq("user_id", user_id).execute()
                if int_result.data:
                    integrations = [i["provider"] for i in int_result.data]
            except:
                pass
            
            # Subscription
            sub_plan = "free"
            sub_status = "active"
            try:
                sub_result = self.supabase.table("organization_subscriptions").select("plan_id, status").eq("organization_id", organization_id).single().execute()
                if sub_result.data:
                    sub_plan = sub_result.data.get("plan_id", "free")
                    sub_status = sub_result.data.get("status", "active")
            except:
                pass
            
            return DataSummaryResponse(
                user_id=user_id,
                email=user_email,
                account_created_at=created_at,
                has_sales_profile=has_sales,
                has_company_profile=has_company,
                data_categories=categories,
                storage_usage=storage,
                total_storage_bytes=total_storage,
                connected_calendars=calendars,
                connected_integrations=integrations,
                subscription_plan=sub_plan,
                subscription_status=sub_status,
                generated_at=datetime.utcnow(),
            )
            
        except Exception as e:
            logger.error(f"Error getting data summary: {e}")
            raise
    
    # ============================================================
    # HELPERS
    # ============================================================
    
    def _get_user_org_id(self, user_id: str) -> Optional[str]:
        """Get user's organization ID."""
        try:
            result = self.supabase.table("organization_members").select(
                "organization_id"
            ).eq("user_id", user_id).limit(1).single().execute()
            
            if result.data:
                return result.data["organization_id"]
            return None
        except:
            return None

