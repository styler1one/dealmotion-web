"""
Fireflies Service - Integration with Fireflies.ai API
SPEC-038: Meetings & Calendar Integration - Phase 3

Handles:
- Fetching transcripts from Fireflies API
- Syncing recordings to external_recordings table
- Matching with calendar meetings
"""
import httpx
import logging
from datetime import datetime, timedelta, timezone
from typing import Optional, List, Dict, Any

from app.database import get_supabase_service
from app.services.encryption import decrypt_api_key

supabase = get_supabase_service()
logger = logging.getLogger(__name__)

FIREFLIES_API_URL = "https://api.fireflies.ai/graphql"


class FirefliesService:
    """Service for interacting with Fireflies.ai API."""
    
    def __init__(self, api_key: str):
        """Initialize with decrypted API key."""
        self.api_key = api_key
        self.headers = {
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json"
        }
    
    @classmethod
    def from_integration(cls, integration: dict) -> Optional['FirefliesService']:
        """
        Create a FirefliesService from a recording_integration record.
        Handles decryption of the API key using the encryption service.
        """
        credentials = integration.get("credentials", {})
        if not credentials:
            return None
        
        # Use centralized decryption service
        api_key = decrypt_api_key(credentials)
        if not api_key:
            return None
        
        return cls(api_key)
    
    async def get_user_info(self) -> Optional[dict]:
        """Get user info from Fireflies API."""
        query = """
        query {
            user {
                email
                name
                user_id
            }
        }
        """
        
        async with httpx.AsyncClient() as client:
            try:
                response = await client.post(
                    FIREFLIES_API_URL,
                    json={"query": query},
                    headers=self.headers,
                    timeout=10.0
                )
                
                if response.status_code != 200:
                    logger.warning(f"Fireflies API returned {response.status_code}")
                    return None
                
                data = response.json()
                return data.get("data", {}).get("user")
                
            except Exception as e:
                logger.error(f"Failed to get Fireflies user info: {e}")
                return None
    
    async def fetch_transcripts(
        self, 
        limit: int = 50,  # Fireflies API max is 50
        from_date: Optional[datetime] = None
    ) -> List[dict]:
        # Enforce Fireflies API limit
        limit = min(limit, 50)
        """
        Fetch transcripts from Fireflies API.
        
        Args:
            limit: Maximum number of transcripts to fetch
            from_date: Only fetch transcripts after this date
        
        Returns:
            List of transcript objects
        """
        # GraphQL query for transcripts
        query = """
        query Transcripts($limit: Int) {
            transcripts(limit: $limit) {
                id
                title
                date
                duration
                participants
                transcript_url
                audio_url
                summary {
                    overview
                    action_items
                    keywords
                }
                sentences {
                    speaker_name
                    text
                    start_time
                    end_time
                }
            }
        }
        """
        
        variables = {"limit": limit}
        
        async with httpx.AsyncClient() as client:
            try:
                response = await client.post(
                    FIREFLIES_API_URL,
                    json={"query": query, "variables": variables},
                    headers=self.headers,
                    timeout=30.0
                )
                
                if response.status_code != 200:
                    logger.warning(f"Fireflies API returned {response.status_code}")
                    return []
                
                data = response.json()
                
                if "errors" in data:
                    logger.warning(f"Fireflies API errors: {data['errors']}")
                    return []
                
                transcripts = data.get("data", {}).get("transcripts", [])
                
                # Filter by date if specified
                if from_date:
                    from_timestamp = from_date.timestamp() * 1000  # Fireflies uses ms
                    transcripts = [
                        t for t in transcripts 
                        if t.get("date", 0) >= from_timestamp
                    ]
                
                logger.info(f"Fetched {len(transcripts)} transcripts from Fireflies")
                return transcripts
                
            except Exception as e:
                logger.error(f"Failed to fetch Fireflies transcripts: {e}")
                return []
    
    async def get_transcript_detail(self, transcript_id: str) -> Optional[dict]:
        """
        Get detailed transcript including full text.
        
        Args:
            transcript_id: The Fireflies transcript ID
        
        Returns:
            Detailed transcript object or None
        """
        query = """
        query Transcript($transcriptId: String!) {
            transcript(id: $transcriptId) {
                id
                title
                date
                duration
                participants
                transcript_url
                audio_url
                summary {
                    overview
                    action_items
                    keywords
                }
                sentences {
                    speaker_name
                    text
                    start_time
                    end_time
                }
            }
        }
        """
        
        async with httpx.AsyncClient() as client:
            try:
                response = await client.post(
                    FIREFLIES_API_URL,
                    json={
                        "query": query,
                        "variables": {"transcriptId": transcript_id}
                    },
                    headers=self.headers,
                    timeout=30.0
                )
                
                if response.status_code != 200:
                    return None
                
                data = response.json()
                return data.get("data", {}).get("transcript")
                
            except Exception as e:
                logger.error(f"Failed to get transcript detail: {e}")
                return None


async def sync_fireflies_recordings(
    user_id: str,
    org_id: str,
    integration_id: str,
    service: FirefliesService,
    days_back: int = 30
) -> Dict[str, int]:
    """
    Sync recordings from Fireflies to external_recordings table.
    
    Args:
        user_id: The user's ID
        org_id: The organization's ID
        integration_id: The recording_integration ID
        service: Initialized FirefliesService
        days_back: Number of days to look back for recordings
    
    Returns:
        Stats dict with new, updated, skipped counts
    """
    stats = {"new": 0, "updated": 0, "skipped": 0, "error": 0}
    
    # Calculate from_date (timezone-aware)
    from_date = datetime.now(timezone.utc) - timedelta(days=days_back)
    
    # Fetch transcripts from Fireflies (API limit is 50 max)
    transcripts = await service.fetch_transcripts(limit=50, from_date=from_date)
    
    if not transcripts:
        logger.info(f"No transcripts found for user {user_id}")
        return stats
    
    # Get existing external recordings for this integration
    existing_result = supabase.table("external_recordings").select("external_id").eq(
        "integration_id", integration_id
    ).execute()
    existing_ids = {r["external_id"] for r in existing_result.data or []}
    
    # Get calendar meetings for matching
    meetings_result = supabase.table("calendar_meetings").select(
        "id, title, start_time, end_time, attendees, prospect_id"
    ).eq("user_id", user_id).gte(
        "start_time", from_date.isoformat()
    ).execute()
    meetings = meetings_result.data or []
    
    for transcript in transcripts:
        try:
            external_id = transcript.get("id")
            
            if not external_id:
                stats["skipped"] += 1
                continue
            
            # Skip if already imported
            if external_id in existing_ids:
                stats["skipped"] += 1
                continue
            
            # Parse transcript data
            title = transcript.get("title", "Untitled Recording")
            
            # Fireflies date is in milliseconds (convert to timezone-aware UTC)
            date_ms = transcript.get("date", 0)
            recording_date = datetime.fromtimestamp(date_ms / 1000, tz=timezone.utc) if date_ms else datetime.now(timezone.utc)
            
            # Fireflies returns duration in minutes as float, convert to seconds as int
            duration_raw = transcript.get("duration", 0)
            duration_seconds = int(float(duration_raw) * 60) if duration_raw else 0
            participants = transcript.get("participants", [])
            audio_url = transcript.get("audio_url")
            transcript_url = transcript.get("transcript_url")
            
            # Build transcript text from sentences
            sentences = transcript.get("sentences", [])
            transcript_text = "\n".join([
                f"{s.get('speaker_name', 'Speaker')}: {s.get('text', '')}"
                for s in sentences
            ]) if sentences else None
            
            # Try to match with a calendar meeting
            matched_meeting_id = None
            matched_prospect_id = None
            
            for meeting in meetings:
                # Parse meeting times (handle both Z suffix and +00:00)
                start_str = meeting["start_time"].replace("Z", "+00:00")
                end_str = meeting["end_time"].replace("Z", "+00:00")
                meeting_start = datetime.fromisoformat(start_str)
                meeting_end = datetime.fromisoformat(end_str)
                
                # Make recording_date offset-naive for comparison if meeting times are naive
                recording_date_for_comparison = recording_date.replace(tzinfo=None) if meeting_start.tzinfo is None else recording_date
                meeting_start_for_comparison = meeting_start if meeting_start.tzinfo else meeting_start.replace(tzinfo=timezone.utc)
                meeting_end_for_comparison = meeting_end if meeting_end.tzinfo else meeting_end.replace(tzinfo=timezone.utc)
                
                # Check if recording date falls within meeting time (with some tolerance)
                tolerance = timedelta(minutes=15)
                if meeting_start_for_comparison - tolerance <= recording_date <= meeting_end_for_comparison + tolerance:
                    matched_meeting_id = meeting["id"]
                    matched_prospect_id = meeting.get("prospect_id")
                    logger.info(f"Matched transcript '{title}' with meeting '{meeting['title']}'")
                    break
            
            # Insert into external_recordings (without metadata column that doesn't exist)
            record_data = {
                "organization_id": org_id,
                "user_id": user_id,
                "integration_id": integration_id,
                "external_id": external_id,
                "provider": "fireflies",
                "title": title,
                "recording_date": recording_date.isoformat(),
                "duration_seconds": duration_seconds,
                "participants": participants if participants else [],
                "audio_url": audio_url,
                "transcript_text": transcript_text[:50000] if transcript_text else None,  # Limit size
                "matched_meeting_id": matched_meeting_id,
                "matched_prospect_id": matched_prospect_id,
                "import_status": "pending",
                "created_at": datetime.now(timezone.utc).isoformat()
            }
            
            supabase.table("external_recordings").insert(record_data).execute()
            stats["new"] += 1
            logger.info(f"Imported Fireflies transcript: {title}")
            
        except Exception as e:
            logger.error(f"Error importing transcript {transcript.get('id')}: {e}")
            stats["error"] += 1
    
    # Update integration last_sync (use "success" or "failed" per database constraint)
    supabase.table("recording_integrations").update({
        "last_sync_at": datetime.now(timezone.utc).isoformat(),
        "last_sync_status": "success" if stats["error"] == 0 else "failed"
    }).eq("id", integration_id).execute()
    
    logger.info(f"Fireflies sync complete: {stats}")
    return stats

