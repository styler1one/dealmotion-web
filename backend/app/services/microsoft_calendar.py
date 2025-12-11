"""
Microsoft Calendar Service - OAuth and Microsoft Graph API integration
SPEC-038: Meetings & Calendar Integration - Phase 4
"""
import os
import secrets
import logging
from typing import Optional, Tuple, List
from urllib.parse import urlencode
from datetime import datetime, timezone
import httpx
import msal

logger = logging.getLogger(__name__)

# OAuth Configuration
MICROSOFT_CLIENT_ID = os.getenv("MICROSOFT_CLIENT_ID")
MICROSOFT_CLIENT_SECRET = os.getenv("MICROSOFT_CLIENT_SECRET")
MICROSOFT_TENANT_ID = os.getenv("MICROSOFT_TENANT_ID", "common")  # "common" for multi-tenant

# Scopes required for calendar access
# Note: offline_access is automatically added by MSAL for refresh tokens
# Note: Teams transcript permissions require admin consent, so we use the basic
# calendar scopes and fetch Teams recordings differently
CALENDAR_SCOPES = [
    "https://graph.microsoft.com/Calendars.Read",
    "https://graph.microsoft.com/User.Read",
]

# Redirect URI for OAuth callback - points to frontend callback page
REDIRECT_URI = os.getenv(
    "MICROSOFT_CALENDAR_REDIRECT_URI",
    "https://dealmotion.ai/auth/calendar/microsoft/callback"
)

# Microsoft Graph API base URL
GRAPH_API_BASE = "https://graph.microsoft.com/v1.0"

# Microsoft OAuth endpoints
AUTHORITY = f"https://login.microsoftonline.com/{MICROSOFT_TENANT_ID}"


class MicrosoftCalendarService:
    """Service for Microsoft Calendar OAuth and API operations."""
    
    def __init__(self):
        """Initialize the Microsoft Calendar service."""
        if not MICROSOFT_CLIENT_ID or not MICROSOFT_CLIENT_SECRET:
            logger.warning("Microsoft OAuth credentials not configured")
        
        # Initialize MSAL confidential client
        self.msal_app = None
        if MICROSOFT_CLIENT_ID and MICROSOFT_CLIENT_SECRET:
            self.msal_app = msal.ConfidentialClientApplication(
                MICROSOFT_CLIENT_ID,
                authority=AUTHORITY,
                client_credential=MICROSOFT_CLIENT_SECRET,
            )
    
    def generate_auth_url(self, user_id: str) -> Tuple[str, str]:
        """
        Generate the Microsoft OAuth authorization URL.
        
        Args:
            user_id: The DealMotion user ID to include in state
            
        Returns:
            Tuple of (auth_url, state_token)
        """
        # Generate a secure state token that includes user_id
        state_token = f"{user_id}:{secrets.token_urlsafe(32)}"
        
        if self.msal_app:
            auth_url = self.msal_app.get_authorization_request_url(
                scopes=CALENDAR_SCOPES,
                redirect_uri=REDIRECT_URI,
                state=state_token,
            )
        else:
            # Fallback: build URL manually if MSAL not initialized
            params = {
                "client_id": MICROSOFT_CLIENT_ID,
                "redirect_uri": REDIRECT_URI,
                "response_type": "code",
                "scope": " ".join(CALENDAR_SCOPES),
                "response_mode": "query",
                "state": state_token,
            }
            auth_url = f"{AUTHORITY}/oauth2/v2.0/authorize?{urlencode(params)}"
        
        logger.info(f"Generated Microsoft OAuth URL for user {user_id[:8]}...")
        
        return auth_url, state_token
    
    def exchange_code_for_tokens(self, code: str) -> Optional[dict]:
        """
        Exchange authorization code for access and refresh tokens.
        
        Args:
            code: The authorization code from Microsoft
            
        Returns:
            Dictionary with tokens or None if failed
        """
        try:
            if not self.msal_app:
                logger.error("MSAL app not initialized")
                return None
            
            result = self.msal_app.acquire_token_by_authorization_code(
                code=code,
                scopes=CALENDAR_SCOPES,
                redirect_uri=REDIRECT_URI,
            )
            
            if "error" in result:
                logger.error(f"Token exchange error: {result.get('error_description', result.get('error'))}")
                return None
            
            return {
                "access_token": result.get("access_token"),
                "refresh_token": result.get("refresh_token"),
                "expires_in": result.get("expires_in", 3600),
                "token_type": result.get("token_type", "Bearer"),
            }
            
        except Exception as e:
            logger.error(f"Error exchanging code for tokens: {e}")
            return None
    
    def refresh_access_token(self, refresh_token: str) -> Optional[dict]:
        """
        Refresh the access token using a refresh token.
        
        Args:
            refresh_token: The refresh token
            
        Returns:
            Dictionary with new tokens or None if failed
        """
        try:
            if not self.msal_app:
                logger.error("MSAL app not initialized")
                return None
            
            result = self.msal_app.acquire_token_by_refresh_token(
                refresh_token=refresh_token,
                scopes=CALENDAR_SCOPES,
            )
            
            if "error" in result:
                logger.error(f"Token refresh error: {result.get('error_description', result.get('error'))}")
                return None
            
            return {
                "access_token": result.get("access_token"),
                "refresh_token": result.get("refresh_token", refresh_token),  # May not always be returned
                "expires_in": result.get("expires_in", 3600),
            }
            
        except Exception as e:
            logger.error(f"Error refreshing access token: {e}")
            return None
    
    async def get_user_info(self, access_token: str) -> Optional[dict]:
        """
        Get the user's email and name from Microsoft Graph.
        
        Args:
            access_token: Valid access token
            
        Returns:
            Dictionary with email and name or None
        """
        try:
            async with httpx.AsyncClient() as client:
                response = await client.get(
                    f"{GRAPH_API_BASE}/me",
                    headers={"Authorization": f"Bearer {access_token}"},
                    timeout=10.0
                )
                
                if response.status_code != 200:
                    logger.error(f"Failed to get user info: {response.status_code}")
                    return None
                
                data = response.json()
                return {
                    "email": data.get("mail") or data.get("userPrincipalName"),
                    "name": data.get("displayName"),
                }
                
        except Exception as e:
            logger.error(f"Error getting user info: {e}")
            return None
    
    async def fetch_calendar_events(
        self,
        access_token: str,
        from_date: datetime,
        to_date: datetime
    ) -> List[dict]:
        """
        Fetch calendar events from Microsoft Graph API.
        
        Args:
            access_token: Valid access token
            from_date: Start date for events
            to_date: End date for events
            
        Returns:
            List of calendar events
        """
        events = []
        
        try:
            # Format dates for Microsoft Graph API
            start_datetime = from_date.strftime("%Y-%m-%dT%H:%M:%SZ")
            end_datetime = to_date.strftime("%Y-%m-%dT%H:%M:%SZ")
            
            async with httpx.AsyncClient() as client:
                # Use calendarView for recurring events expansion
                url = f"{GRAPH_API_BASE}/me/calendarView"
                params = {
                    "startDateTime": start_datetime,
                    "endDateTime": end_datetime,
                    "$select": "id,subject,start,end,organizer,attendees,location,isAllDay,isCancelled,webLink,onlineMeeting,isOnlineMeeting,onlineMeetingUrl,body",
                    "$orderby": "start/dateTime",
                    "$top": 250,  # Max per page
                }
                
                response = await client.get(
                    url,
                    params=params,
                    headers={"Authorization": f"Bearer {access_token}"},
                    timeout=30.0
                )
                
                if response.status_code != 200:
                    logger.error(f"Failed to fetch events: {response.status_code} - {response.text}")
                    return []
                
                data = response.json()
                events = data.get("value", [])
                
                # Handle pagination
                next_link = data.get("@odata.nextLink")
                while next_link:
                    response = await client.get(
                        next_link,
                        headers={"Authorization": f"Bearer {access_token}"},
                        timeout=30.0
                    )
                    if response.status_code != 200:
                        break
                    
                    data = response.json()
                    events.extend(data.get("value", []))
                    next_link = data.get("@odata.nextLink")
                
                logger.info(f"Fetched {len(events)} events from Microsoft Calendar")
                return events
                
        except Exception as e:
            logger.error(f"Error fetching calendar events: {e}")
            return []
    
    def is_configured(self) -> bool:
        """Check if Microsoft OAuth is properly configured."""
        return bool(MICROSOFT_CLIENT_ID and MICROSOFT_CLIENT_SECRET)
    
    def parse_event_to_meeting(self, event: dict, connection_id: str, user_id: str, org_id: str) -> dict:
        """
        Parse a Microsoft Graph event into our CalendarMeeting format.
        
        Args:
            event: Microsoft Graph event object
            connection_id: Calendar connection ID
            user_id: User ID
            org_id: Organization ID
            
        Returns:
            Dictionary matching calendar_meetings schema
        """
        # Parse start/end times
        start = event.get("start", {})
        end = event.get("end", {})
        
        start_time = start.get("dateTime")
        end_time = end.get("dateTime")
        timezone_str = start.get("timeZone", "UTC")
        
        # Parse attendees
        attendees = []
        for attendee in event.get("attendees", []):
            email_address = attendee.get("emailAddress", {})
            attendees.append({
                "email": email_address.get("address"),
                "name": email_address.get("name"),
                "response_status": attendee.get("status", {}).get("response", "none"),
                "is_organizer": False,
            })
        
        # Add organizer
        organizer = event.get("organizer", {}).get("emailAddress", {})
        if organizer.get("address"):
            attendees.insert(0, {
                "email": organizer.get("address"),
                "name": organizer.get("name"),
                "response_status": "accepted",
                "is_organizer": True,
            })
        
        # Parse location
        location = event.get("location", {})
        location_str = location.get("displayName") or ""
        
        # Check if it's a Teams meeting - multiple ways to detect
        is_online = False
        meeting_url = None
        
        # Method 1: onlineMeeting object with joinUrl
        online_meeting = event.get("onlineMeeting")
        if online_meeting and isinstance(online_meeting, dict):
            meeting_url = online_meeting.get("joinUrl")
            if meeting_url:
                is_online = True
        
        # Method 2: isOnlineMeeting flag with onlineMeetingUrl
        if not meeting_url and event.get("isOnlineMeeting"):
            meeting_url = event.get("onlineMeetingUrl")
            if meeting_url:
                is_online = True
        
        # Method 3: Check location for Teams URL
        if not meeting_url and location_str:
            if "teams.microsoft.com" in location_str.lower():
                # Try to extract URL from location
                import re
                url_match = re.search(r'https://teams\.microsoft\.com/l/meetup-join/[^\s<>"]+', location_str)
                if url_match:
                    meeting_url = url_match.group(0)
                    is_online = True
        
        # Method 4: Check body/description for Teams URL (if available)
        body = event.get("body", {})
        body_content = body.get("content", "") if isinstance(body, dict) else ""
        if not meeting_url and body_content and "teams.microsoft.com" in body_content.lower():
            import re
            url_match = re.search(r'https://teams\.microsoft\.com/l/meetup-join/[^\s<>"\']+', body_content)
            if url_match:
                meeting_url = url_match.group(0)
                is_online = True
        
        logger.debug(f"Event '{event.get('subject')}': is_online={is_online}, meeting_url={meeting_url[:50] if meeting_url else None}")
        
        # Determine status
        status = "confirmed"
        if event.get("isCancelled"):
            status = "cancelled"
        
        return {
            "calendar_connection_id": connection_id,
            "organization_id": org_id,
            "user_id": user_id,
            "external_id": event.get("id"),
            "title": event.get("subject") or "No Title",
            "start_time": start_time,
            "end_time": end_time,
            "timezone": timezone_str,
            "location": location_str[:500] if location_str else None,  # Limit length
            "is_online": is_online,
            "meeting_url": meeting_url,
            "attendees": attendees,
            "status": status,
            "is_all_day": event.get("isAllDay", False),
            "recurrence_rule": None,  # Graph API expands recurring events
            "external_link": event.get("webLink"),
        }


# Singleton instance
microsoft_calendar_service = MicrosoftCalendarService()

