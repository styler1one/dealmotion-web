from fastapi import APIRouter, Depends
from app.deps import get_current_user

router = APIRouter()

@router.get("/me")
def read_users_me(current_user: dict = Depends(get_current_user)):
    """
    Returns the current authenticated user's profile.
    """
    return {
        "id": current_user.get("sub"),
        "email": current_user.get("email"),
        "role": current_user.get("role"),
        "metadata": current_user.get("user_metadata")
    }
