"""
Inngest Event Helpers.

Provides helper functions to send events from routers to Inngest.
Falls back to BackgroundTasks if Inngest is not available.
"""

import os
import logging
from typing import Optional, Any
from functools import wraps
import inngest

logger = logging.getLogger(__name__)

# Check if Inngest is enabled
INNGEST_ENABLED = os.getenv("INNGEST_ENABLED", "true").lower() == "true"

# Lazy import to avoid circular imports
_inngest_client = None


def get_inngest_client():
    """Lazy load the Inngest client."""
    global _inngest_client
    if _inngest_client is None:
        try:
            from app.inngest.client import inngest_client
            _inngest_client = inngest_client
        except ImportError:
            logger.warning("Inngest client not available")
            _inngest_client = False
    return _inngest_client if _inngest_client else None


async def send_event(
    event_name: str,
    data: dict,
    user: Optional[dict] = None
) -> bool:
    """
    Send an event to Inngest.
    
    Args:
        event_name: The event name (e.g., "dealmotion/research.requested")
        data: Event data payload
        user: Optional user context
        
    Returns:
        True if event was sent successfully, False otherwise
    """
    if not INNGEST_ENABLED:
        logger.debug(f"Inngest disabled, skipping event: {event_name}")
        return False
    
    client = get_inngest_client()
    if not client:
        logger.warning(f"Inngest client not available, cannot send: {event_name}")
        return False
    
    try:
        # Create Inngest Event object (required by SDK)
        # Only pass user if it's a valid dict (Inngest SDK requires dict, not None)
        event_kwargs = {
            "name": event_name,
            "data": data,
        }
        if user is not None:
            event_kwargs["user"] = user
        
        event = inngest.Event(**event_kwargs)
        
        await client.send(event)
        logger.info(f"Inngest event sent: {event_name}")
        return True
        
    except Exception as e:
        logger.error(f"Failed to send Inngest event {event_name}: {e}")
        return False


def send_event_sync(
    event_name: str,
    data: dict,
    user: Optional[dict] = None
) -> bool:
    """
    Send an event to Inngest (synchronous version).
    
    Use this in synchronous contexts. For async code, use send_event().
    """
    import asyncio
    
    try:
        loop = asyncio.get_event_loop()
        if loop.is_running():
            # If we're in an async context, create a new task
            asyncio.create_task(send_event(event_name, data, user))
            return True
        else:
            return loop.run_until_complete(send_event(event_name, data, user))
    except RuntimeError:
        # No event loop, create one
        return asyncio.run(send_event(event_name, data, user))


# =============================================================================
# Event Constants
# =============================================================================

class Events:
    """Event name constants for type safety."""
    
    # Research Agent
    RESEARCH_REQUESTED = "dealmotion/research.requested"
    RESEARCH_COMPLETED = "dealmotion/research.completed"
    RESEARCH_FAILED = "dealmotion/research.failed"
    
    # Preparation Agent
    PREP_REQUESTED = "dealmotion/prep.requested"
    PREP_COMPLETED = "dealmotion/prep.completed"
    PREP_FAILED = "dealmotion/prep.failed"
    
    # Follow-up Agent
    FOLLOWUP_AUDIO_UPLOADED = "dealmotion/followup.audio.uploaded"
    FOLLOWUP_TRANSCRIPT_UPLOADED = "dealmotion/followup.transcript.uploaded"
    FOLLOWUP_TRANSCRIBED = "dealmotion/followup.transcribed"
    FOLLOWUP_COMPLETED = "dealmotion/followup.completed"
    FOLLOWUP_FAILED = "dealmotion/followup.failed"
    
    # AI Notetaker
    AI_NOTETAKER_RECORDING_COMPLETE = "dealmotion/ai-notetaker.recording.complete"
    AI_NOTETAKER_EMAIL_RECEIVED = "dealmotion/ai-notetaker.email.received"
    
    # Follow-up Actions
    FOLLOWUP_ACTION_REQUESTED = "dealmotion/followup.action.requested"
    FOLLOWUP_ACTION_COMPLETED = "dealmotion/followup.action.completed"
    
    # Contact Analysis
    CONTACT_ADDED = "dealmotion/contact.added"
    CONTACT_ANALYZED = "dealmotion/contact.analyzed"
    
    # Knowledge Base
    KNOWLEDGE_FILE_UPLOADED = "dealmotion/knowledge.file.uploaded"
    KNOWLEDGE_FILE_PROCESSED = "dealmotion/knowledge.file.processed"
    KNOWLEDGE_FILE_FAILED = "dealmotion/knowledge.file.failed"
    
    # Coach
    COACH_INSIGHT_REQUESTED = "dealmotion/coach.insight.requested"
    
    # Deal/Prospect events (future automation)
    DEAL_CREATED = "dealmotion/deal.created"
    DEAL_STAGE_CHANGED = "dealmotion/deal.stage.changed"
    MEETING_SCHEDULED = "dealmotion/meeting.scheduled"
    MEETING_COMPLETED = "dealmotion/meeting.completed"
    
    # Calendar Integration
    CALENDAR_SYNC_REQUESTED = "dealmotion/calendar.sync.requested"
    CALENDAR_SYNC_COMPLETED = "dealmotion/calendar.sync.completed"
    
    # Fireflies Integration
    FIREFLIES_SYNC_REQUESTED = "dealmotion/fireflies.sync.requested"
    FIREFLIES_SYNC_COMPLETED = "dealmotion/fireflies.sync.completed"
    
    # Follow-up Summarize (for imported transcripts)
    FOLLOWUP_SUMMARIZE = "dealmotion/followup.summarize"


# =============================================================================
# Feature Flag Helper
# =============================================================================

def use_inngest_for(feature: str) -> bool:
    """
    Check if Inngest should be used for a specific feature.
    
    This allows gradual rollout of Inngest per feature.
    
    Args:
        feature: Feature name (e.g., "research", "preparation", "followup")
        
    Returns:
        True if Inngest should be used for this feature
    """
    if not INNGEST_ENABLED:
        logger.debug(f"use_inngest_for({feature}): INNGEST_ENABLED={INNGEST_ENABLED}")
        return False
    
    # Check feature-specific flag
    env_key = f"INNGEST_FEATURE_{feature.upper()}"
    feature_flag = os.getenv(env_key, "true")
    result = feature_flag.lower() == "true"
    
    logger.debug(f"use_inngest_for({feature}): {env_key}={feature_flag} -> {result}")
    return result

