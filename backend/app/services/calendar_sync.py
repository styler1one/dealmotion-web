"""
Calendar Sync Service - Fetches and syncs calendar events
SPEC-038: Meetings & Calendar Integration
"""
import os
import base64
import logging
from datetime import datetime, timedelta, timezone
from typing import Optional, List, Dict, Any
from dataclasses import dataclass
import asyncio

from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError

from app.database import get_supabase_service
from app.services.prospect_matcher import ProspectMatcher
from app.services.microsoft_calendar import microsoft_calendar_service

logger = logging.getLogger(__name__)

# Configuration
GOOGLE_CLIENT_ID = os.getenv("GOOGLE_CLIENT_ID")
GOOGLE_CLIENT_SECRET = os.getenv("GOOGLE_CLIENT_SECRET")
SYNC_DAYS_AHEAD = 14  # Sync meetings for the next 14 days


@dataclass
class SyncResult:
    """Result of a calendar sync operation."""
    synced_meetings: int = 0
    new_meetings: int = 0
    updated_meetings: int = 0
    deleted_meetings: int = 0
    errors: List[str] = None
    
    def __post_init__(self):
        if self.errors is None:
            self.errors = []


@dataclass
class CalendarEvent:
    """Parsed calendar event from Google."""
    external_event_id: str
    title: str
    description: Optional[str]
    start_time: datetime
    end_time: datetime
    original_timezone: Optional[str]
    location: Optional[str]
    is_online: bool
    meeting_url: Optional[str]
    attendees: List[Dict[str, str]]
    organizer_email: Optional[str]
    status: str  # confirmed, tentative, cancelled
    is_recurring: bool
    recurrence_rule: Optional[str]
    recurring_event_id: Optional[str]
    raw_data: Dict[str, Any]


class CalendarSyncService:
    """Service for syncing calendar events from external providers."""
    
    def __init__(self):
        self.supabase = get_supabase_service()
    
    def _decode_token(self, stored_token) -> str:
        """Decode a stored token from database."""
        try:
            # Handle different storage formats
            if stored_token is None:
                return ""
            
            # If it's bytes (from BYTEA column), decode to string
            if isinstance(stored_token, bytes):
                return stored_token.decode('utf-8')
            
            # If it's already a string
            if isinstance(stored_token, str):
                # Check if it's PostgreSQL hex format (starts with \x)
                if stored_token.startswith('\\x'):
                    # Convert hex string to bytes, then to string
                    hex_data = stored_token[2:]  # Remove \x prefix
                    return bytes.fromhex(hex_data).decode('utf-8')
                
                # Check if it looks like a valid token already
                if stored_token.startswith('ya29'):
                    return stored_token
                
                # Try base64 decode for legacy data
                try:
                    padding_needed = len(stored_token) % 4
                    if padding_needed:
                        stored_token_padded = stored_token + '=' * (4 - padding_needed)
                    else:
                        stored_token_padded = stored_token
                    decoded = base64.b64decode(stored_token_padded).decode('utf-8')
                    if decoded.startswith('ya29'):
                        return decoded
                except (ValueError, UnicodeDecodeError):
                    pass
                
                return stored_token
            
            return str(stored_token)
        except Exception as e:
            logger.error(f"Failed to decode token: {e}")
            raise ValueError("Invalid token encoding")
    
    def _get_google_credentials(self, connection: Dict) -> Optional[Credentials]:
        """Build Google credentials from stored connection data."""
        try:
            access_token = self._decode_token(connection["access_token_encrypted"])
            refresh_token = None
            if connection.get("refresh_token_encrypted"):
                refresh_token = self._decode_token(connection["refresh_token_encrypted"])
            
            credentials = Credentials(
                token=access_token,
                refresh_token=refresh_token,
                token_uri="https://oauth2.googleapis.com/token",
                client_id=GOOGLE_CLIENT_ID,
                client_secret=GOOGLE_CLIENT_SECRET,
            )
            
            # Check if token is expired and refresh if needed
            if credentials.expired and credentials.refresh_token:
                import google.auth.transport.requests
                request = google.auth.transport.requests.Request()
                credentials.refresh(request)
                
                # Update stored tokens
                new_access_token = base64.b64encode(credentials.token.encode()).decode()
                self.supabase.table("calendar_connections").update({
                    "access_token_encrypted": new_access_token,
                    "token_expires_at": credentials.expiry.isoformat() if credentials.expiry else None,
                }).eq("id", connection["id"]).execute()
                
                logger.info(f"Refreshed expired token for connection {connection['id']}")
            
            return credentials
            
        except Exception as e:
            logger.error(f"Failed to build Google credentials: {e}")
            # Mark connection as needing reauth
            self.supabase.table("calendar_connections").update({
                "needs_reauth": True,
                "last_sync_status": "failed",
                "last_sync_error": str(e),
            }).eq("id", connection["id"]).execute()
            return None
    
    def _parse_google_event(self, event: Dict, connection_id: str) -> Optional[CalendarEvent]:
        """Parse a Google Calendar event into our format."""
        try:
            # Get start/end times
            start = event.get("start", {})
            end = event.get("end", {})
            
            # Handle all-day events vs timed events
            if "dateTime" in start:
                start_time = datetime.fromisoformat(start["dateTime"].replace("Z", "+00:00"))
                end_time = datetime.fromisoformat(end["dateTime"].replace("Z", "+00:00"))
                original_timezone = start.get("timeZone")
            elif "date" in start:
                # All-day event - use midnight UTC
                start_time = datetime.strptime(start["date"], "%Y-%m-%d").replace(tzinfo=timezone.utc)
                end_time = datetime.strptime(end["date"], "%Y-%m-%d").replace(tzinfo=timezone.utc)
                original_timezone = None
            else:
                logger.warning(f"Event {event.get('id')} has no valid start time")
                return None
            
            # Parse attendees
            attendees = []
            for attendee in event.get("attendees", []):
                attendees.append({
                    "email": attendee.get("email", ""),
                    "name": attendee.get("displayName", ""),
                    "response_status": attendee.get("responseStatus", "needsAction"),
                    "is_organizer": attendee.get("organizer", False),
                })
            
            # Check if it's an online meeting - multiple detection methods
            meeting_url = None
            is_online = False
            
            # Method 1: conferenceData.entryPoints (standard Google Meet)
            conference_data = event.get("conferenceData", {})
            entry_points = conference_data.get("entryPoints", [])
            for ep in entry_points:
                if ep.get("entryPointType") == "video":
                    meeting_url = ep.get("uri")
                    is_online = True
                    break
            
            # Method 2: hangoutLink property (older Google Meet format)
            if not meeting_url and event.get("hangoutLink"):
                meeting_url = event.get("hangoutLink")
                is_online = True
            
            # Method 3: Check location for meeting URLs
            location = event.get("location", "")
            if location and not is_online:
                location_lower = location.lower()
                if any(domain in location_lower for domain in ["meet.google.com", "zoom.us", "teams.microsoft.com", "webex.com"]):
                    # Try to extract clean URL
                    import re
                    url_match = re.search(r'https?://[^\s<>"\']+', location)
                    if url_match:
                        meeting_url = url_match.group(0)
                        is_online = True
                    else:
                        meeting_url = location
                        is_online = True
            
            # Method 4: Check description for meeting URLs
            description = event.get("description", "")
            if description and not is_online:
                desc_lower = description.lower()
                if any(domain in desc_lower for domain in ["meet.google.com", "zoom.us/j/", "teams.microsoft.com/l/meetup", "webex.com"]):
                    import re
                    url_match = re.search(r'https?://(?:meet\.google\.com/[a-z\-]+|zoom\.us/j/\d+|teams\.microsoft\.com/l/meetup-join/[^\s<>"\']+|[^\s<>"\']*webex\.com[^\s<>"\']*)', desc_lower)
                    if url_match:
                        # Get the actual URL with correct casing from original
                        start_idx = desc_lower.find(url_match.group(0)[:20])
                        if start_idx >= 0:
                            actual_match = re.search(r'https?://[^\s<>"\']+', description[start_idx:])
                            if actual_match:
                                meeting_url = actual_match.group(0)
                                is_online = True
            
            logger.debug(f"Event '{event.get('summary')}': is_online={is_online}, url={meeting_url[:50] if meeting_url else None}")
            
            # Handle recurring events
            is_recurring = "recurrence" in event or "recurringEventId" in event
            recurrence_rule = None
            if event.get("recurrence"):
                recurrence_rule = ";".join(event["recurrence"])
            
            return CalendarEvent(
                external_event_id=event["id"],
                title=event.get("summary", "(No title)"),
                description=event.get("description"),
                start_time=start_time,
                end_time=end_time,
                original_timezone=original_timezone,
                location=location if location and not is_online else None,
                is_online=is_online,
                meeting_url=meeting_url,
                attendees=attendees,
                organizer_email=event.get("organizer", {}).get("email"),
                status=event.get("status", "confirmed"),
                is_recurring=is_recurring,
                recurrence_rule=recurrence_rule,
                recurring_event_id=event.get("recurringEventId"),
                raw_data=event,
            )
            
        except Exception as e:
            logger.error(f"Failed to parse event {event.get('id')}: {e}")
            return None
    
    def _fetch_google_events(self, credentials: Credentials) -> List[Dict]:
        """Fetch upcoming events from Google Calendar."""
        try:
            service = build("calendar", "v3", credentials=credentials)
            
            # Fetch events from yesterday (to catch recent meetings) through SYNC_DAYS_AHEAD
            now = datetime.now(timezone.utc)
            # Start from beginning of yesterday to include recent meetings
            from_date = (now - timedelta(days=1)).replace(hour=0, minute=0, second=0, microsecond=0)
            time_min = from_date.strftime("%Y-%m-%dT%H:%M:%SZ")
            time_max = (now + timedelta(days=SYNC_DAYS_AHEAD)).strftime("%Y-%m-%dT%H:%M:%SZ")
            
            events = []
            page_token = None
            
            while True:
                result = service.events().list(
                    calendarId="primary",
                    timeMin=time_min,
                    timeMax=time_max,
                    maxResults=250,
                    singleEvents=True,  # Expand recurring events
                    orderBy="startTime",
                    pageToken=page_token,
                ).execute()
                
                events.extend(result.get("items", []))
                page_token = result.get("nextPageToken")
                
                if not page_token:
                    break
            
            logger.info(f"Fetched {len(events)} events from Google Calendar")
            return events
            
        except HttpError as e:
            logger.error(f"Google Calendar API error: {e}")
            if e.resp.status == 401:
                raise ValueError("Token expired or revoked")
            raise
        except Exception as e:
            logger.error(f"Failed to fetch Google events: {e}")
            raise
    
    def _upsert_meeting(
        self, 
        event: CalendarEvent, 
        connection_id: str, 
        organization_id: str,
        user_id: str
    ) -> str:
        """Insert or update a calendar meeting. Returns 'new', 'updated', or 'unchanged'."""
        try:
            # Check if meeting already exists
            existing = self.supabase.table("calendar_meetings").select("id, status").eq(
                "calendar_connection_id", connection_id
            ).eq(
                "external_event_id", event.external_event_id
            ).execute()
            
            meeting_data = {
                "calendar_connection_id": connection_id,
                "organization_id": organization_id,
                "user_id": user_id,
                "external_event_id": event.external_event_id,
                "title": event.title,
                "description": event.description,
                "start_time": event.start_time.isoformat(),
                "end_time": event.end_time.isoformat(),
                "original_timezone": event.original_timezone,
                "location": event.location,
                "is_online": event.is_online,
                "meeting_url": event.meeting_url,
                "attendees": event.attendees,
                "organizer_email": event.organizer_email,
                "status": event.status,
                "is_recurring": event.is_recurring,
                "recurrence_rule": event.recurrence_rule,
                "recurring_event_id": event.recurring_event_id,
            }
            
            if existing.data and len(existing.data) > 0:
                # Update existing
                self.supabase.table("calendar_meetings").update(
                    meeting_data
                ).eq("id", existing.data[0]["id"]).execute()
                return "updated"
            else:
                # Insert new
                self.supabase.table("calendar_meetings").insert(
                    meeting_data
                ).execute()
                return "new"
                
        except Exception as e:
            logger.error(f"Failed to upsert meeting {event.external_event_id}: {e}")
            raise
    
    def _mark_cancelled_meetings(
        self, 
        connection_id: str, 
        synced_event_ids: List[str]
    ) -> int:
        """Mark meetings as cancelled if they no longer appear in the calendar."""
        try:
            # Get current non-cancelled meetings for this connection
            current = self.supabase.table("calendar_meetings").select("id, external_event_id").eq(
                "calendar_connection_id", connection_id
            ).neq(
                "status", "cancelled"
            ).execute()
            
            cancelled_count = 0
            for meeting in current.data or []:
                if meeting["external_event_id"] not in synced_event_ids:
                    self.supabase.table("calendar_meetings").update({
                        "status": "cancelled"
                    }).eq("id", meeting["id"]).execute()
                    cancelled_count += 1
            
            return cancelled_count
            
        except Exception as e:
            logger.error(f"Failed to mark cancelled meetings: {e}")
            return 0
    
    async def _sync_microsoft_connection(self, conn: Dict, connection_id: str) -> SyncResult:
        """Sync calendar events for a Microsoft connection."""
        result = SyncResult()
        
        try:
            # Get access token
            access_token = self._decode_token(conn.get("access_token_encrypted"))
            refresh_token = self._decode_token(conn.get("refresh_token_encrypted")) if conn.get("refresh_token_encrypted") else None
            
            if not access_token:
                result.errors.append("No access token available")
                return result
            
            # Try to refresh token if we have a refresh token
            # Microsoft tokens expire after 1 hour
            if refresh_token:
                new_tokens = microsoft_calendar_service.refresh_access_token(refresh_token)
                if new_tokens:
                    access_token = new_tokens["access_token"]
                    # Update stored tokens
                    self.supabase.table("calendar_connections").update({
                        "access_token_encrypted": access_token,
                        "refresh_token_encrypted": new_tokens.get("refresh_token", refresh_token),
                    }).eq("id", connection_id).execute()
            
            # Fetch events from Microsoft Graph
            # Start from beginning of yesterday to include recent meetings
            now = datetime.now(timezone.utc)
            from_date = (now - timedelta(days=1)).replace(hour=0, minute=0, second=0, microsecond=0)
            to_date = now + timedelta(days=SYNC_DAYS_AHEAD)
            
            events = await microsoft_calendar_service.fetch_calendar_events(
                access_token, from_date, to_date
            )
            
            if not events:
                logger.info(f"No events fetched from Microsoft for connection {connection_id}")
            
            synced_event_ids = []
            
            # Process each event
            for event_data in events:
                # Parse Microsoft event to our format
                parsed = microsoft_calendar_service.parse_event_to_meeting(
                    event_data, 
                    connection_id, 
                    conn["user_id"], 
                    conn["organization_id"]
                )
                
                if parsed.get("status") == "cancelled":
                    continue
                
                synced_event_ids.append(parsed["external_id"])
                
                try:
                    # Check if meeting already exists
                    existing = self.supabase.table("calendar_meetings").select("id").eq(
                        "calendar_connection_id", connection_id
                    ).eq(
                        "external_event_id", parsed["external_id"]
                    ).execute()
                    
                    # Map parsed data to meeting schema
                    meeting_data = {
                        "calendar_connection_id": connection_id,
                        "organization_id": parsed["organization_id"],
                        "user_id": parsed["user_id"],
                        "external_event_id": parsed["external_id"],
                        "title": parsed["title"],
                        "start_time": parsed["start_time"],
                        "end_time": parsed["end_time"],
                        "original_timezone": parsed.get("timezone"),
                        "location": parsed.get("location"),
                        "is_online": parsed.get("is_online", False),
                        "meeting_url": parsed.get("meeting_url"),
                        "attendees": parsed.get("attendees", []),
                        "status": parsed.get("status", "confirmed"),
                        "is_recurring": False,  # Graph API expands recurring events
                    }
                    
                    if existing.data and len(existing.data) > 0:
                        self.supabase.table("calendar_meetings").update(
                            meeting_data
                        ).eq("id", existing.data[0]["id"]).execute()
                        result.updated_meetings += 1
                    else:
                        self.supabase.table("calendar_meetings").insert(
                            meeting_data
                        ).execute()
                        result.new_meetings += 1
                    
                    result.synced_meetings += 1
                    
                except Exception as e:
                    result.errors.append(f"Failed to save Microsoft event {parsed['external_id']}: {str(e)}")
            
            # Mark meetings that no longer exist as cancelled
            result.deleted_meetings = self._mark_cancelled_meetings(connection_id, synced_event_ids)
            
            return result
            
        except Exception as e:
            logger.error(f"Microsoft sync failed: {e}")
            result.errors.append(str(e))
            return result
    
    def sync_connection(self, connection_id: str) -> SyncResult:
        """Sync calendar events for a specific connection."""
        result = SyncResult()
        
        try:
            # Get connection details
            connection = self.supabase.table("calendar_connections").select(
                "*"
            ).eq("id", connection_id).execute()
            
            if not connection.data or len(connection.data) == 0:
                result.errors.append("Connection not found")
                return result
            
            conn = connection.data[0]
            
            if not conn.get("sync_enabled"):
                result.errors.append("Sync is disabled for this connection")
                return result
            
            provider = conn.get("provider", "google")
            
            # Route to appropriate provider sync
            if provider == "microsoft":
                # Microsoft sync is async, run it properly
                try:
                    loop = asyncio.get_running_loop()
                    # We're already in an async context
                    import concurrent.futures
                    with concurrent.futures.ThreadPoolExecutor() as executor:
                        future = executor.submit(
                            asyncio.run,
                            self._sync_microsoft_connection(conn, connection_id)
                        )
                        result = future.result()
                except RuntimeError:
                    # No running loop
                    result = asyncio.run(self._sync_microsoft_connection(conn, connection_id))
            else:
                # Google sync (existing logic)
                credentials = self._get_google_credentials(conn)
                if not credentials:
                    result.errors.append("Failed to get valid credentials")
                    return result
                
                # Fetch events
                events = self._fetch_google_events(credentials)
                synced_event_ids = []
                
                # Process each event
                for event_data in events:
                    event = self._parse_google_event(event_data, connection_id)
                    if not event:
                        continue
                    
                    if event.status == "cancelled":
                        continue  # Skip cancelled events
                    
                    synced_event_ids.append(event.external_event_id)
                    
                    try:
                        action = self._upsert_meeting(event, connection_id, conn["organization_id"], conn["user_id"])
                        if action == "new":
                            result.new_meetings += 1
                        elif action == "updated":
                            result.updated_meetings += 1
                        result.synced_meetings += 1
                    except Exception as e:
                        result.errors.append(f"Failed to save event {event.external_event_id}: {str(e)}")
                
                # Mark meetings that no longer exist as cancelled
                result.deleted_meetings = self._mark_cancelled_meetings(connection_id, synced_event_ids)
            
            # Update connection sync status
            self.supabase.table("calendar_connections").update({
                "last_sync_at": datetime.utcnow().isoformat(),
                "last_sync_status": "success" if not result.errors else "partial",
                "last_sync_error": "; ".join(result.errors) if result.errors else None,
            }).eq("id", connection_id).execute()
            
            logger.info(
                f"Synced {provider} connection {connection_id}: "
                f"{result.new_meetings} new, {result.updated_meetings} updated, "
                f"{result.deleted_meetings} deleted"
            )
            
            # Run prospect matching on new/updated unlinked meetings
            if result.new_meetings > 0 or result.updated_meetings > 0:
                try:
                    matcher = ProspectMatcher(self.supabase)
                    try:
                        loop = asyncio.get_running_loop()
                        # Already in async context, create task
                        asyncio.create_task(matcher.match_all_unlinked(conn["organization_id"]))
                    except RuntimeError:
                        # No running loop, use asyncio.run()
                        asyncio.run(matcher.match_all_unlinked(conn["organization_id"]))
                    logger.info(f"Ran prospect matching for organization {conn['organization_id']}")
                except Exception as match_error:
                    logger.error(f"Prospect matching failed: {match_error}")
                    # Don't fail the sync for matching errors
            
            return result
            
        except Exception as e:
            logger.error(f"Sync failed for connection {connection_id}: {e}")
            result.errors.append(str(e))
            
            # Update connection with error status
            self.supabase.table("calendar_connections").update({
                "last_sync_at": datetime.utcnow().isoformat(),
                "last_sync_status": "failed",
                "last_sync_error": str(e),
            }).eq("id", connection_id).execute()
            
            return result
    
    def sync_user_calendars(self, user_id: str) -> Dict[str, SyncResult]:
        """Sync all calendar connections for a user."""
        results = {}
        
        try:
            # Get all active connections for user
            connections = self.supabase.table("calendar_connections").select(
                "id, provider"
            ).eq("user_id", user_id).eq("sync_enabled", True).execute()
            
            for conn in connections.data or []:
                results[conn["provider"]] = self.sync_connection(conn["id"])
            
            return results
            
        except Exception as e:
            logger.error(f"Failed to sync calendars for user {user_id}: {e}")
            return results


# Singleton instance
calendar_sync_service = CalendarSyncService()

