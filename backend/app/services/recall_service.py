"""
Recall.ai Service - AI Notetaker Integration

This service handles communication with Recall.ai API for scheduling
meeting bots that automatically join, record, and transcribe meetings.

SPEC-043: AI Notetaker / Recall.ai Integration
"""

import os
import re
import httpx
from datetime import datetime
from typing import Optional, Dict, Any, List
from pydantic import BaseModel
import logging

logger = logging.getLogger(__name__)

# Configuration
RECALL_API_KEY = os.getenv("RECALL_API_KEY", "")
RECALL_API_BASE = "https://api.recall.ai/api/v1"
AI_NOTETAKER_NAME = os.getenv("AI_NOTETAKER_NAME", "DealMotion AI Notes")


class RecallBotConfig(BaseModel):
    """Configuration for creating a Recall.ai bot."""
    meeting_url: str
    bot_name: str = AI_NOTETAKER_NAME
    join_at: Optional[datetime] = None  # None = join immediately
    recording_mode: str = "audio_only"  # audio_only, speaker_view, gallery_view
    transcription_provider: str = "default"


class RecallBotResponse(BaseModel):
    """Response from Recall.ai bot creation."""
    id: str
    meeting_url: str
    status: str
    bot_name: str


class RecallRecordingInfo(BaseModel):
    """Recording information from Recall.ai webhook."""
    bot_id: str
    recording_url: Optional[str] = None
    duration_seconds: Optional[int] = None
    participants: List[str] = []
    transcript: Optional[Dict[str, Any]] = None


class RecallService:
    """Service for interacting with Recall.ai API."""
    
    def __init__(self):
        self.api_key = RECALL_API_KEY
        self.base_url = RECALL_API_BASE
        self.headers = {
            "Authorization": f"Token {self.api_key}",
            "Content-Type": "application/json"
        }
    
    def is_configured(self) -> bool:
        """Check if Recall.ai is properly configured."""
        return bool(self.api_key)
    
    def validate_meeting_url(self, url: str) -> tuple[bool, str, Optional[str]]:
        """
        Validate if a meeting URL is supported.
        
        Returns:
            tuple: (is_valid, platform, error_message)
        """
        url = url.strip()
        
        # Microsoft Teams
        if "teams.microsoft.com" in url or "teams.live.com" in url:
            return True, "teams", None
        
        # Google Meet
        if "meet.google.com" in url:
            return True, "meet", None
        
        # Zoom
        if "zoom.us" in url or "zoomgov.com" in url:
            return True, "zoom", None
        
        # Webex
        if "webex.com" in url:
            return True, "webex", None
        
        return False, "", "Unsupported meeting platform. Supported: Teams, Google Meet, Zoom, Webex"
    
    async def create_bot(self, config: RecallBotConfig) -> Dict[str, Any]:
        """
        Create a new bot to join a meeting.
        
        Args:
            config: Bot configuration including meeting URL and schedule
            
        Returns:
            Dict with bot ID and status
        """
        if not self.is_configured():
            raise ValueError("Recall.ai API key not configured")
        
        # Validate meeting URL
        is_valid, platform, error = self.validate_meeting_url(config.meeting_url)
        if not is_valid:
            raise ValueError(error)
        
        payload = {
            "meeting_url": config.meeting_url,
            "bot_name": config.bot_name,
            "recording_mode": config.recording_mode,
            "transcription_options": {
                "provider": config.transcription_provider
            }
        }
        
        # Add join_at if scheduling for later
        if config.join_at:
            payload["join_at"] = config.join_at.isoformat()
        
        try:
            async with httpx.AsyncClient(timeout=30.0) as client:
                response = await client.post(
                    f"{self.base_url}/bot",
                    headers=self.headers,
                    json=payload
                )
                
                if response.status_code == 201:
                    data = response.json()
                    logger.info(f"Created Recall.ai bot: {data.get('id')}")
                    return {
                        "success": True,
                        "bot_id": data.get("id"),
                        "status": data.get("status", {}).get("code", "ready"),
                        "platform": platform,
                        "meeting_url": config.meeting_url
                    }
                else:
                    error_detail = response.text
                    logger.error(f"Recall.ai bot creation failed: {response.status_code} - {error_detail}")
                    return {
                        "success": False,
                        "error": f"Failed to create bot: {response.status_code}",
                        "detail": error_detail
                    }
                    
        except httpx.TimeoutException:
            logger.error("Recall.ai API timeout")
            return {
                "success": False,
                "error": "Recall.ai API timeout"
            }
        except Exception as e:
            logger.error(f"Recall.ai API error: {e}")
            return {
                "success": False,
                "error": str(e)
            }
    
    async def cancel_bot(self, bot_id: str) -> Dict[str, Any]:
        """
        Cancel a scheduled bot.
        
        Args:
            bot_id: The Recall.ai bot ID
            
        Returns:
            Dict with success status
        """
        if not self.is_configured():
            raise ValueError("Recall.ai API key not configured")
        
        try:
            async with httpx.AsyncClient(timeout=30.0) as client:
                response = await client.delete(
                    f"{self.base_url}/bot/{bot_id}",
                    headers=self.headers
                )
                
                if response.status_code in [200, 204]:
                    logger.info(f"Cancelled Recall.ai bot: {bot_id}")
                    return {"success": True}
                else:
                    logger.error(f"Failed to cancel bot: {response.status_code}")
                    return {
                        "success": False,
                        "error": f"Failed to cancel: {response.status_code}"
                    }
                    
        except Exception as e:
            logger.error(f"Error cancelling bot: {e}")
            return {
                "success": False,
                "error": str(e)
            }
    
    async def get_bot_status(self, bot_id: str) -> Dict[str, Any]:
        """
        Get the current status of a bot.
        
        Args:
            bot_id: The Recall.ai bot ID
            
        Returns:
            Dict with bot status information
        """
        if not self.is_configured():
            raise ValueError("Recall.ai API key not configured")
        
        try:
            async with httpx.AsyncClient(timeout=30.0) as client:
                response = await client.get(
                    f"{self.base_url}/bot/{bot_id}",
                    headers=self.headers
                )
                
                if response.status_code == 200:
                    data = response.json()
                    return {
                        "success": True,
                        "bot_id": bot_id,
                        "status": data.get("status", {}).get("code", "unknown"),
                        "recording": data.get("recording"),
                        "transcript": data.get("transcript")
                    }
                else:
                    return {
                        "success": False,
                        "error": f"Failed to get status: {response.status_code}"
                    }
                    
        except Exception as e:
            logger.error(f"Error getting bot status: {e}")
            return {
                "success": False,
                "error": str(e)
            }
    
    async def download_recording(self, recording_url: str) -> Optional[bytes]:
        """
        Download a recording from Recall.ai.
        
        Args:
            recording_url: The URL to download the recording from
            
        Returns:
            Recording bytes or None if failed
        """
        try:
            async with httpx.AsyncClient(timeout=300.0) as client:  # 5 min timeout for large files
                response = await client.get(
                    recording_url,
                    headers=self.headers
                )
                
                if response.status_code == 200:
                    return response.content
                else:
                    logger.error(f"Failed to download recording: {response.status_code}")
                    return None
                    
        except Exception as e:
            logger.error(f"Error downloading recording: {e}")
            return None
    
    def parse_webhook_event(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        """
        Parse a webhook event from Recall.ai.
        
        Args:
            payload: The webhook payload
            
        Returns:
            Parsed event data
        """
        event_type = payload.get("event", "")
        data = payload.get("data", {})
        
        # Map Recall.ai status codes to our status values
        status_map = {
            "ready": "scheduled",
            "joining_call": "joining",
            "in_waiting_room": "waiting_room",
            "in_call_not_recording": "joining",
            "in_call_recording": "recording",
            "call_ended": "processing",
            "done": "complete",
            "fatal": "error",
            "analysis_done": "complete"
        }
        
        result = {
            "event_type": event_type,
            "bot_id": data.get("bot_id"),
            "status": status_map.get(data.get("status", {}).get("code", ""), "unknown"),
            "raw_status": data.get("status", {}).get("code", "")
        }
        
        # Add recording info if available
        if "recording" in data:
            result["recording_url"] = data["recording"].get("download_url")
            result["duration_seconds"] = data["recording"].get("duration_seconds")
        
        # Add transcript if available
        if "transcript" in data:
            result["transcript"] = data["transcript"]
        
        # Add participants if available
        if "participants" in data:
            result["participants"] = [p.get("name", "Unknown") for p in data["participants"]]
        
        return result


# Singleton instance
recall_service = RecallService()

