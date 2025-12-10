"""
Inngest Functions Registry.

This module exports all Inngest functions for registration with the serve endpoint.
"""

from .research import research_company_fn
from .preparation import preparation_meeting_fn
from .followup import process_followup_audio_fn, process_followup_transcript_fn
from .contacts import analyze_contact_fn
from .followup_actions import generate_followup_action_fn
from .knowledge_base import process_knowledge_file_fn
from .calendar import sync_all_calendars_fn, sync_calendar_connection_fn
from .fireflies import sync_all_fireflies_fn, sync_fireflies_user_fn
from .ai_notetaker import process_ai_notetaker_recording_fn

# All functions to register with Inngest
all_functions = [
    research_company_fn,
    preparation_meeting_fn,
    process_followup_audio_fn,
    process_followup_transcript_fn,
    analyze_contact_fn,
    generate_followup_action_fn,
    process_knowledge_file_fn,
    sync_all_calendars_fn,
    sync_calendar_connection_fn,
    sync_all_fireflies_fn,
    sync_fireflies_user_fn,
    process_ai_notetaker_recording_fn,
]

__all__ = [
    "all_functions",
    "research_company_fn",
    "preparation_meeting_fn",
    "process_followup_audio_fn",
    "process_followup_transcript_fn",
    "analyze_contact_fn",
    "generate_followup_action_fn",
    "process_knowledge_file_fn",
    "sync_all_calendars_fn",
    "sync_calendar_connection_fn",
    "sync_all_fireflies_fn",
    "sync_fireflies_user_fn",
    "process_ai_notetaker_recording_fn",
]

