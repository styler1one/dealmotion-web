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
from .calendar_post_sync import process_calendar_post_sync_fn
from .fireflies import sync_all_fireflies_fn, sync_fireflies_user_fn
from .ai_notetaker import process_ai_notetaker_recording_fn
from .email_invite import process_email_invite_fn
from .autopilot_detection import (
    detect_calendar_opportunities_fn,
    detect_meeting_ended_fn,
    detect_silent_prospects_fn,
    detect_incomplete_flow_fn,
    expire_proposals_fn,
)
from .autopilot_execution import execute_proposal_fn

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
    process_calendar_post_sync_fn,
    sync_all_fireflies_fn,
    sync_fireflies_user_fn,
    process_ai_notetaker_recording_fn,
    process_email_invite_fn,
    # Autopilot functions
    detect_calendar_opportunities_fn,
    detect_meeting_ended_fn,
    detect_silent_prospects_fn,
    detect_incomplete_flow_fn,
    expire_proposals_fn,
    execute_proposal_fn,
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
    "process_calendar_post_sync_fn",
    "sync_all_fireflies_fn",
    "sync_fireflies_user_fn",
    "process_ai_notetaker_recording_fn",
    "process_email_invite_fn",
    # Autopilot functions
    "detect_calendar_opportunities_fn",
    "detect_meeting_ended_fn",
    "detect_silent_prospects_fn",
    "detect_incomplete_flow_fn",
    "expire_proposals_fn",
    "execute_proposal_fn",
]

