"""
Microsoft Teams Service - Fetch Teams meeting recordings and transcripts
SPEC-038: Meetings & Calendar Integration - Phase 4 Sprint 4.4
"""
import logging
from typing import Optional, List, Dict, Any
from datetime import datetime, timedelta, timezone
import httpx

from app.database import get_supabase_service

logger = logging.getLogger(__name__)

# Microsoft Graph API base URL
GRAPH_API_BASE = "https://graph.microsoft.com/v1.0"
GRAPH_API_BETA = "https://graph.microsoft.com/beta"  # Some Teams features are beta-only


class TeamsService:
    """Service for fetching Microsoft Teams recordings and transcripts."""
    
    def __init__(self):
        self.supabase = get_supabase_service()
    
    async def fetch_online_meetings(
        self,
        access_token: str,
        from_date: datetime,
        to_date: datetime
    ) -> List[dict]:
        """
        Fetch online meetings from Microsoft Graph API.
        
        Note: This fetches meetings the user has organized or been invited to.
        
        Args:
            access_token: Valid access token with OnlineMeetings.Read scope
            from_date: Start date for meetings
            to_date: End date for meetings
            
        Returns:
            List of online meetings
        """
        meetings = []
        
        try:
            async with httpx.AsyncClient() as client:
                # First, get the user's ID
                user_response = await client.get(
                    f"{GRAPH_API_BASE}/me",
                    headers={"Authorization": f"Bearer {access_token}"},
                    timeout=10.0
                )
                
                if user_response.status_code != 200:
                    logger.error(f"Failed to get user info: {user_response.status_code}")
                    return []
                
                user_id = user_response.json().get("id")
                
                # Fetch online meetings
                # Note: /me/onlineMeetings only returns meetings created by the user
                url = f"{GRAPH_API_BASE}/me/onlineMeetings"
                
                response = await client.get(
                    url,
                    headers={"Authorization": f"Bearer {access_token}"},
                    timeout=30.0
                )
                
                if response.status_code != 200:
                    logger.warning(f"Failed to fetch online meetings: {response.status_code} - {response.text}")
                    # This might fail if user hasn't created any meetings, that's okay
                    return []
                
                data = response.json()
                meetings = data.get("value", [])
                
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
                    meetings.extend(data.get("value", []))
                    next_link = data.get("@odata.nextLink")
                
                logger.info(f"Fetched {len(meetings)} online meetings from Teams")
                return meetings
                
        except Exception as e:
            logger.error(f"Error fetching online meetings: {e}")
            return []
    
    async def fetch_meeting_transcripts(
        self,
        access_token: str,
        meeting_id: str
    ) -> List[dict]:
        """
        Fetch transcripts for a specific online meeting.
        
        Args:
            access_token: Valid access token with OnlineMeetingTranscript.Read.All scope
            meeting_id: The online meeting ID
            
        Returns:
            List of transcript metadata
        """
        try:
            async with httpx.AsyncClient() as client:
                # Use beta API for transcripts (more complete)
                url = f"{GRAPH_API_BETA}/me/onlineMeetings/{meeting_id}/transcripts"
                
                response = await client.get(
                    url,
                    headers={"Authorization": f"Bearer {access_token}"},
                    timeout=30.0
                )
                
                if response.status_code == 404:
                    # No transcripts available
                    return []
                
                if response.status_code != 200:
                    logger.warning(f"Failed to fetch transcripts for meeting {meeting_id}: {response.status_code}")
                    return []
                
                data = response.json()
                return data.get("value", [])
                
        except Exception as e:
            logger.error(f"Error fetching transcripts for meeting {meeting_id}: {e}")
            return []
    
    async def fetch_transcript_content(
        self,
        access_token: str,
        meeting_id: str,
        transcript_id: str
    ) -> Optional[str]:
        """
        Fetch the actual transcript content.
        
        Args:
            access_token: Valid access token
            meeting_id: The online meeting ID
            transcript_id: The transcript ID
            
        Returns:
            Transcript text content or None
        """
        try:
            async with httpx.AsyncClient() as client:
                # Request VTT format for the transcript
                url = f"{GRAPH_API_BETA}/me/onlineMeetings/{meeting_id}/transcripts/{transcript_id}/content"
                params = {"$format": "text/vtt"}
                
                response = await client.get(
                    url,
                    params=params,
                    headers={"Authorization": f"Bearer {access_token}"},
                    timeout=60.0
                )
                
                if response.status_code != 200:
                    logger.warning(f"Failed to fetch transcript content: {response.status_code}")
                    return None
                
                # Parse VTT to plain text
                vtt_content = response.text
                return self._parse_vtt_to_text(vtt_content)
                
        except Exception as e:
            logger.error(f"Error fetching transcript content: {e}")
            return None
    
    def _parse_vtt_to_text(self, vtt_content: str) -> str:
        """
        Parse VTT (WebVTT) format to plain text.
        
        Args:
            vtt_content: VTT formatted transcript
            
        Returns:
            Plain text transcript
        """
        lines = vtt_content.split('\n')
        text_lines = []
        
        for line in lines:
            # Skip VTT header, timestamps, and empty lines
            line = line.strip()
            if not line:
                continue
            if line.startswith('WEBVTT'):
                continue
            if line.startswith('NOTE'):
                continue
            if '-->' in line:  # Timestamp line
                continue
            if line.isdigit():  # Cue number
                continue
            
            # This is actual transcript text
            # Remove speaker tags like <v Speaker Name>
            if '<v ' in line:
                # Extract speaker and text
                import re
                match = re.match(r'<v ([^>]+)>(.+)', line)
                if match:
                    speaker = match.group(1)
                    text = match.group(2).replace('</v>', '').strip()
                    text_lines.append(f"{speaker}: {text}")
                else:
                    text_lines.append(line)
            else:
                text_lines.append(line)
        
        return '\n'.join(text_lines)
    
    async def fetch_meeting_recordings(
        self,
        access_token: str,
        meeting_id: str
    ) -> List[dict]:
        """
        Fetch recordings for a specific online meeting.
        
        Note: Recording content is stored in OneDrive/SharePoint.
        This returns recording metadata with download URLs.
        
        Args:
            access_token: Valid access token
            meeting_id: The online meeting ID
            
        Returns:
            List of recording metadata
        """
        try:
            async with httpx.AsyncClient() as client:
                url = f"{GRAPH_API_BETA}/me/onlineMeetings/{meeting_id}/recordings"
                
                response = await client.get(
                    url,
                    headers={"Authorization": f"Bearer {access_token}"},
                    timeout=30.0
                )
                
                if response.status_code == 404:
                    # No recordings available
                    return []
                
                if response.status_code != 200:
                    logger.warning(f"Failed to fetch recordings for meeting {meeting_id}: {response.status_code}")
                    return []
                
                data = response.json()
                return data.get("value", [])
                
        except Exception as e:
            logger.error(f"Error fetching recordings for meeting {meeting_id}: {e}")
            return []
    
    async def sync_teams_recordings(
        self,
        user_id: str,
        organization_id: str,
        access_token: str,
        days_back: int = 30
    ) -> Dict[str, Any]:
        """
        Sync Teams recordings for a user to external_recordings table.
        
        Args:
            user_id: DealMotion user ID
            organization_id: Organization ID
            access_token: Valid Microsoft access token
            days_back: Number of days to look back
            
        Returns:
            Dict with sync results
        """
        result = {
            "total_meetings": 0,
            "recordings_found": 0,
            "transcripts_found": 0,
            "new_recordings": 0,
            "errors": []
        }
        
        try:
            from_date = datetime.now(timezone.utc) - timedelta(days=days_back)
            to_date = datetime.now(timezone.utc)
            
            # Fetch online meetings
            meetings = await self.fetch_online_meetings(access_token, from_date, to_date)
            result["total_meetings"] = len(meetings)
            
            for meeting in meetings:
                meeting_id = meeting.get("id")
                if not meeting_id:
                    continue
                
                try:
                    # Check for transcripts
                    transcripts = await self.fetch_meeting_transcripts(access_token, meeting_id)
                    
                    for transcript in transcripts:
                        result["transcripts_found"] += 1
                        transcript_id = transcript.get("id")
                        
                        # Check if already imported
                        existing = self.supabase.table("external_recordings").select("id").eq(
                            "external_id", f"teams_{meeting_id}_{transcript_id}"
                        ).eq("user_id", user_id).execute()
                        
                        if existing.data and len(existing.data) > 0:
                            continue  # Already imported
                        
                        # Fetch transcript content
                        transcript_text = await self.fetch_transcript_content(
                            access_token, meeting_id, transcript_id
                        )
                        
                        # Parse meeting time
                        created_time = transcript.get("createdDateTime")
                        meeting_time = None
                        if created_time:
                            try:
                                meeting_time = datetime.fromisoformat(created_time.replace("Z", "+00:00"))
                            except:
                                pass
                        
                        # Calculate duration from meeting if available
                        duration_seconds = 0
                        if meeting.get("startDateTime") and meeting.get("endDateTime"):
                            try:
                                start = datetime.fromisoformat(meeting["startDateTime"].replace("Z", "+00:00"))
                                end = datetime.fromisoformat(meeting["endDateTime"].replace("Z", "+00:00"))
                                duration_seconds = int((end - start).total_seconds())
                            except:
                                pass
                        
                        # Insert into external_recordings
                        recording_data = {
                            "user_id": user_id,
                            "organization_id": organization_id,
                            "source": "teams",
                            "external_id": f"teams_{meeting_id}_{transcript_id}",
                            "title": meeting.get("subject") or "Teams Meeting",
                            "meeting_time": meeting_time.isoformat() if meeting_time else None,
                            "duration": duration_seconds,
                            "participants": self._extract_participants(meeting),
                            "transcript_text": transcript_text,
                            "transcript_available": bool(transcript_text),
                            "status": "pending",
                            "raw_data": {
                                "meeting": meeting,
                                "transcript_meta": transcript,
                            }
                        }
                        
                        self.supabase.table("external_recordings").insert(recording_data).execute()
                        result["new_recordings"] += 1
                        
                        logger.info(f"Imported Teams transcript for meeting: {meeting.get('subject')}")
                    
                    # Also check for recordings (video/audio files)
                    recordings = await self.fetch_meeting_recordings(access_token, meeting_id)
                    result["recordings_found"] += len(recordings)
                    
                    # Note: We primarily use transcripts since they're more useful for analysis
                    # Video recordings would need to be transcribed separately
                    
                except Exception as meeting_error:
                    logger.error(f"Error processing meeting {meeting_id}: {meeting_error}")
                    result["errors"].append(f"Meeting {meeting_id}: {str(meeting_error)}")
            
            logger.info(
                f"Teams sync complete: {result['total_meetings']} meetings, "
                f"{result['transcripts_found']} transcripts, "
                f"{result['new_recordings']} new imports"
            )
            
            return result
            
        except Exception as e:
            logger.error(f"Teams sync failed: {e}")
            result["errors"].append(str(e))
            return result
    
    def _extract_participants(self, meeting: dict) -> List[dict]:
        """Extract participant list from meeting data."""
        participants = []
        
        # Get organizer
        organizer = meeting.get("participants", {}).get("organizer", {})
        if organizer:
            identity = organizer.get("identity", {}).get("user", {})
            if identity:
                participants.append({
                    "name": identity.get("displayName"),
                    "email": identity.get("id"),  # Graph returns user ID, not email
                    "role": "organizer"
                })
        
        # Get attendees
        attendees = meeting.get("participants", {}).get("attendees", [])
        for attendee in attendees:
            identity = attendee.get("identity", {}).get("user", {})
            if identity:
                participants.append({
                    "name": identity.get("displayName"),
                    "email": identity.get("id"),
                    "role": "attendee"
                })
        
        return participants


# Singleton instance
teams_service = TeamsService()

