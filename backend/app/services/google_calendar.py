"""
Google Calendar Service - OAuth and Calendar API integration
SPEC-038: Meetings & Calendar Integration
"""
import os
import secrets
import logging
from typing import Optional, Tuple
from urllib.parse import urlencode

from google_auth_oauthlib.flow import Flow
from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build

logger = logging.getLogger(__name__)

# OAuth Configuration
GOOGLE_CLIENT_ID = os.getenv("GOOGLE_CLIENT_ID")
GOOGLE_CLIENT_SECRET = os.getenv("GOOGLE_CLIENT_SECRET")

# Scopes required for calendar read access
CALENDAR_SCOPES = [
    "https://www.googleapis.com/auth/calendar.readonly",
    "https://www.googleapis.com/auth/calendar.events.readonly",
    "https://www.googleapis.com/auth/userinfo.email",
    "openid"
]

# Redirect URI for OAuth callback - points to frontend callback page
REDIRECT_URI = os.getenv(
    "GOOGLE_CALENDAR_REDIRECT_URI",
    "https://dealmotion.ai/auth/calendar/callback"
)


class GoogleCalendarService:
    """Service for Google Calendar OAuth and API operations."""
    
    def __init__(self):
        """Initialize the Google Calendar service."""
        if not GOOGLE_CLIENT_ID or not GOOGLE_CLIENT_SECRET:
            logger.warning("Google OAuth credentials not configured")
    
    def generate_auth_url(self, user_id: str) -> Tuple[str, str]:
        """
        Generate the Google OAuth authorization URL.
        
        Args:
            user_id: The DealMotion user ID to include in state
            
        Returns:
            Tuple of (auth_url, state_token)
        """
        # Generate a secure state token that includes user_id
        state_token = f"{user_id}:{secrets.token_urlsafe(32)}"
        
        # Build OAuth URL manually for more control
        params = {
            "client_id": GOOGLE_CLIENT_ID,
            "redirect_uri": REDIRECT_URI,
            "response_type": "code",
            "scope": " ".join(CALENDAR_SCOPES),
            "access_type": "offline",  # Get refresh token
            "prompt": "consent",  # Force consent to get refresh token
            "state": state_token,
        }
        
        auth_url = f"https://accounts.google.com/o/oauth2/v2/auth?{urlencode(params)}"
        
        logger.info(f"Generated Google OAuth URL for user {user_id[:8]}...")
        
        return auth_url, state_token
    
    def exchange_code_for_tokens(self, code: str) -> Optional[dict]:
        """
        Exchange authorization code for access and refresh tokens.
        
        Args:
            code: The authorization code from Google
            
        Returns:
            Dictionary with tokens or None if failed
        """
        try:
            # Create OAuth flow
            flow = Flow.from_client_config(
                {
                    "web": {
                        "client_id": GOOGLE_CLIENT_ID,
                        "client_secret": GOOGLE_CLIENT_SECRET,
                        "auth_uri": "https://accounts.google.com/o/oauth2/v2/auth",
                        "token_uri": "https://oauth2.googleapis.com/token",
                        "redirect_uris": [REDIRECT_URI],
                    }
                },
                scopes=CALENDAR_SCOPES,
                redirect_uri=REDIRECT_URI
            )
            
            # Exchange the code
            flow.fetch_token(code=code)
            credentials = flow.credentials
            
            return {
                "access_token": credentials.token,
                "refresh_token": credentials.refresh_token,
                "token_expires_at": credentials.expiry.isoformat() if credentials.expiry else None,
                "scopes": list(credentials.scopes) if credentials.scopes else CALENDAR_SCOPES,
            }
            
        except Exception as e:
            logger.error(f"Failed to exchange code for tokens: {str(e)}")
            return None
    
    def get_user_email(self, access_token: str) -> Optional[str]:
        """
        Get the user's email from the access token.
        
        Args:
            access_token: The Google access token
            
        Returns:
            User email or None if failed
        """
        try:
            credentials = Credentials(token=access_token)
            service = build("oauth2", "v2", credentials=credentials)
            user_info = service.userinfo().get().execute()
            return user_info.get("email")
        except Exception as e:
            logger.error(f"Failed to get user email: {str(e)}")
            return None
    
    def refresh_access_token(self, refresh_token: str) -> Optional[dict]:
        """
        Refresh an expired access token.
        
        Args:
            refresh_token: The refresh token
            
        Returns:
            Dictionary with new tokens or None if failed
        """
        try:
            import google.auth.transport.requests
            
            credentials = Credentials(
                token=None,
                refresh_token=refresh_token,
                token_uri="https://oauth2.googleapis.com/token",
                client_id=GOOGLE_CLIENT_ID,
                client_secret=GOOGLE_CLIENT_SECRET,
            )
            
            request = google.auth.transport.requests.Request()
            credentials.refresh(request)
            
            return {
                "access_token": credentials.token,
                "token_expires_at": credentials.expiry.isoformat() if credentials.expiry else None,
            }
            
        except Exception as e:
            logger.error(f"Failed to refresh token: {str(e)}")
            return None
    
    def is_configured(self) -> bool:
        """Check if Google OAuth is properly configured."""
        return bool(GOOGLE_CLIENT_ID and GOOGLE_CLIENT_SECRET)


# Singleton instance
google_calendar_service = GoogleCalendarService()

