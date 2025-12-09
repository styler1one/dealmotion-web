from fastapi import Depends, HTTPException, status, Request
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from typing import Tuple, Optional, List
from dataclasses import dataclass
from datetime import datetime
import jwt
import os
from dotenv import load_dotenv

load_dotenv()

security = HTTPBearer()


# ============================================================
# Admin Types
# ============================================================

@dataclass
class AdminContext:
    """Context for authenticated admin users."""
    user_id: str
    admin_id: str
    role: str  # 'super_admin', 'admin', 'support', 'viewer'
    is_active: bool
    email: Optional[str] = None
    
    def can_manage_users(self) -> bool:
        """Check if admin can manage (edit) users."""
        return self.role in ('super_admin', 'admin', 'support')
    
    def can_view_billing(self) -> bool:
        """Check if admin can view billing data."""
        return self.role in ('super_admin', 'admin')
    
    def can_manage_admins(self) -> bool:
        """Check if admin can add/remove other admins."""
        return self.role == 'super_admin'
    
    def can_perform_action(self) -> bool:
        """Check if admin can perform actions (reset flows, etc)."""
        return self.role in ('super_admin', 'admin', 'support')

# Lazy import to avoid circular imports
_supabase_service = None

def _get_supabase():
    """Lazy load supabase service client."""
    global _supabase_service
    if _supabase_service is None:
        from app.database import get_supabase_service
        _supabase_service = get_supabase_service()
    return _supabase_service

def get_auth_token(credentials: HTTPAuthorizationCredentials = Depends(security)) -> str:
    """
    Returns the raw JWT token from the Authorization header.
    """
    return credentials.credentials

def get_current_user(credentials: HTTPAuthorizationCredentials = Depends(security)):
    """
    Verifies the Supabase JWT token and returns the user payload.
    """
    token = credentials.credentials
    
    try:
        # Supabase signs tokens with HS256 and the JWT secret
        # Note: This is NOT the service_role key, but the JWT secret from Supabase settings
        payload = jwt.decode(
            token, 
            os.getenv("SUPABASE_JWT_SECRET"), 
            algorithms=["HS256"],
            audience="authenticated",
            options={"verify_aud": False} # Audience might vary
        )
        return payload
    except jwt.ExpiredSignatureError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token expired",
            headers={"WWW-Authenticate": "Bearer"},
        )
    except jwt.InvalidTokenError as e:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=f"Invalid token: {str(e)}",
            headers={"WWW-Authenticate": "Bearer"},
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=f"Could not validate credentials: {str(e)}",
            headers={"WWW-Authenticate": "Bearer"},
        )


async def get_user_org(current_user: dict = Depends(get_current_user)) -> Tuple[str, str]:
    """
    Get user_id and organization_id from authenticated user.
    
    Returns:
        Tuple of (user_id, organization_id)
        
    Raises:
        HTTPException 401: If user token is invalid
        HTTPException 403: If user has no organization
    """
    user_id = current_user.get("sub")
    if not user_id:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid user token"
        )
    
    supabase = _get_supabase()
    org_result = supabase.table("organization_members").select("organization_id").eq("user_id", user_id).limit(1).execute()
    
    if not org_result.data:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="User has no organization"
        )
    
    return user_id, org_result.data[0]["organization_id"]


def get_organization_id(user_id: str) -> str:
    """
    Get organization ID for a user. Synchronous version.
    
    Use this in background tasks where you already have the user_id.
    For route handlers, prefer get_user_org() dependency.
    """
    supabase = _get_supabase()
    response = supabase.table("organization_members").select("organization_id").eq("user_id", user_id).limit(1).execute()
    
    if not response.data:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="User not in any organization"
        )
    
    return response.data[0]["organization_id"]


# ============================================================
# Admin Dependencies
# ============================================================

async def get_admin_user(
    current_user: dict = Depends(get_current_user),
    request: Request = None
) -> AdminContext:
    """
    Verify admin access and return admin context.
    
    Raises:
        HTTPException 403: If user is not an active admin
    """
    user_id = current_user.get("sub")
    if not user_id:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid user token"
        )
    
    supabase = _get_supabase()
    
    # Check if user is an admin
    try:
        result = supabase.table("admin_users") \
            .select("id, role, is_active") \
            .eq("user_id", user_id) \
            .eq("is_active", True) \
            .maybe_single() \
            .execute()
    except Exception:
        result = None
    
    if not result or not result.data:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Admin access required"
        )
    
    admin_data = result.data
    
    # Update last_admin_login_at
    supabase.table("admin_users") \
        .update({"last_admin_login_at": datetime.utcnow().isoformat()}) \
        .eq("id", admin_data["id"]) \
        .execute()
    
    # Get user email for context
    email = current_user.get("email")
    
    return AdminContext(
        user_id=user_id,
        admin_id=admin_data["id"],
        role=admin_data["role"],
        is_active=admin_data["is_active"],
        email=email
    )


def require_admin_role(*allowed_roles: str):
    """
    Dependency factory that requires specific admin roles.
    
    Usage:
        @router.post("/action")
        async def do_action(admin: AdminContext = Depends(require_admin_role("super_admin", "admin"))):
            ...
    
    Args:
        allowed_roles: Tuple of allowed role names
    
    Returns:
        Dependency that validates admin has one of the allowed roles
    """
    async def dependency(admin: AdminContext = Depends(get_admin_user)) -> AdminContext:
        if admin.role not in allowed_roles:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"This action requires one of these roles: {', '.join(allowed_roles)}"
            )
        return admin
    return dependency


async def get_optional_admin(
    credentials: HTTPAuthorizationCredentials = Depends(security)
) -> Optional[AdminContext]:
    """
    Get admin context if user is an admin, otherwise return None.
    Useful for endpoints that behave differently for admins.
    """
    try:
        token = credentials.credentials
        payload = jwt.decode(
            token, 
            os.getenv("SUPABASE_JWT_SECRET"), 
            algorithms=["HS256"],
            audience="authenticated",
            options={"verify_aud": False}
        )
        user_id = payload.get("sub")
        
        if not user_id:
            return None
        
        supabase = _get_supabase()
        result = supabase.table("admin_users") \
            .select("id, role, is_active") \
            .eq("user_id", user_id) \
            .eq("is_active", True) \
            .maybe_single() \
            .execute()
        
        if not result.data:
            return None
        
        return AdminContext(
            user_id=user_id,
            admin_id=result.data["id"],
            role=result.data["role"],
            is_active=result.data["is_active"],
            email=payload.get("email")
        )
    except Exception:
        return None
