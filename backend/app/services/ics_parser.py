"""
ICS Parser Service - Calendar Invite Parsing

Parses .ics calendar invites from inbound emails to extract:
- Meeting URL (Teams/Meet/Zoom)
- Start/End time
- Organizer email
- Meeting title
- Attendees

SPEC-043 Phase 2: Email-based AI Notetaker Invite
"""

import re
import logging
from datetime import datetime, timezone, timedelta
from typing import Optional, List, Dict, Any
from dataclasses import dataclass
from email import message_from_bytes
from email.message import Message
import base64

logger = logging.getLogger(__name__)


@dataclass
class ParsedMeetingInvite:
    """Parsed meeting invite data from ICS."""
    meeting_url: Optional[str] = None
    meeting_platform: Optional[str] = None  # teams, meet, zoom, webex
    title: Optional[str] = None
    description: Optional[str] = None
    start_time: Optional[datetime] = None
    end_time: Optional[datetime] = None
    organizer_email: Optional[str] = None
    organizer_name: Optional[str] = None
    attendees: List[str] = None
    location: Optional[str] = None
    uid: Optional[str] = None  # Unique calendar event ID
    
    def __post_init__(self):
        if self.attendees is None:
            self.attendees = []
    
    def is_valid(self) -> bool:
        """Check if we have minimum required data."""
        return bool(self.meeting_url and self.start_time and self.organizer_email)
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for JSON serialization."""
        return {
            "meeting_url": self.meeting_url,
            "meeting_platform": self.meeting_platform,
            "title": self.title,
            "description": self.description,
            "start_time": self.start_time.isoformat() if self.start_time else None,
            "end_time": self.end_time.isoformat() if self.end_time else None,
            "organizer_email": self.organizer_email,
            "organizer_name": self.organizer_name,
            "attendees": self.attendees,
            "location": self.location,
            "uid": self.uid,
        }


class ICSParser:
    """Parser for ICS calendar files and meeting invites."""
    
    # Patterns for extracting meeting URLs
    MEETING_URL_PATTERNS = [
        # Microsoft Teams
        (r'https://teams\.microsoft\.com/l/meetup-join/[^\s<>"\']+', 'teams'),
        (r'https://teams\.live\.com/meet/[^\s<>"\']+', 'teams'),
        # Google Meet
        (r'https://meet\.google\.com/[a-z]{3}-[a-z]{4}-[a-z]{3}', 'meet'),
        # Zoom
        (r'https://[a-z0-9]+\.zoom\.us/j/[^\s<>"\']+', 'zoom'),
        (r'https://zoom\.us/j/[^\s<>"\']+', 'zoom'),
        # Webex
        (r'https://[a-z0-9]+\.webex\.com/[^\s<>"\']+', 'webex'),
    ]
    
    def parse_ics_content(self, ics_content: str) -> ParsedMeetingInvite:
        """
        Parse ICS content string and extract meeting details.
        
        Args:
            ics_content: Raw ICS file content
            
        Returns:
            ParsedMeetingInvite with extracted data
        """
        invite = ParsedMeetingInvite()
        
        try:
            # Extract VEVENT block - this is where meeting data lives
            # IMPORTANT: ICS files contain VTIMEZONE blocks with DTSTART fields
            # that use epoch dates (1601-01-01) for timezone rules.
            # We must extract from VEVENT only to avoid parsing wrong DTSTART.
            vevent_content = self._extract_vevent(ics_content)
            if not vevent_content:
                logger.warning("No VEVENT block found in ICS, falling back to full content")
                vevent_content = ics_content
            
            # Extract basic fields from VEVENT
            invite.title = self._extract_field(vevent_content, "SUMMARY")
            invite.description = self._extract_field(vevent_content, "DESCRIPTION")
            invite.location = self._extract_field(vevent_content, "LOCATION")
            invite.uid = self._extract_field(vevent_content, "UID")
            
            # Extract times from VEVENT (not VTIMEZONE!) with timezone info
            dtstart_val, dtstart_tz = self._extract_datetime_with_tz(vevent_content, "DTSTART")
            dtend_val, dtend_tz = self._extract_datetime_with_tz(vevent_content, "DTEND")
            
            # Debug logging
            logger.info(f"[ICS-PARSER] Raw DTSTART from VEVENT: '{dtstart_val}' (tz={dtstart_tz})")
            logger.info(f"[ICS-PARSER] Raw DTEND from VEVENT: '{dtend_val}' (tz={dtend_tz})")
            
            invite.start_time = self._parse_datetime(dtstart_val, dtstart_tz)
            invite.end_time = self._parse_datetime(dtend_val, dtend_tz)
            
            logger.info(f"[ICS-PARSER] Parsed start_time: {invite.start_time}")
            logger.info(f"[ICS-PARSER] Parsed end_time: {invite.end_time}")
            
            # Extract organizer
            organizer = self._extract_field(vevent_content, "ORGANIZER")
            if organizer:
                invite.organizer_email = self._extract_email(organizer)
                invite.organizer_name = self._extract_cn(organizer)
            
            # Extract attendees from VEVENT
            invite.attendees = self._extract_attendees(vevent_content)
            
            # Find meeting URL in description, location, or content
            search_text = f"{invite.description or ''} {invite.location or ''} {ics_content}"
            meeting_url, platform = self._find_meeting_url(search_text)
            invite.meeting_url = meeting_url
            invite.meeting_platform = platform
            
            logger.info(f"Parsed ICS: title='{invite.title}', platform={platform}, organizer={invite.organizer_email}, start={invite.start_time}")
            
        except Exception as e:
            logger.error(f"Error parsing ICS content: {e}")
        
        return invite
    
    def _extract_vevent(self, ics_content: str) -> Optional[str]:
        """
        Extract the VEVENT block from ICS content.
        
        This is crucial because ICS files contain VTIMEZONE blocks
        with DTSTART fields using epoch dates (1601-01-01 for Windows).
        We must only parse fields from the VEVENT block for actual meeting data.
        """
        # Match BEGIN:VEVENT ... END:VEVENT block
        pattern = r"BEGIN:VEVENT[\r\n]+(.*?)[\r\n]+END:VEVENT"
        match = re.search(pattern, ics_content, re.DOTALL | re.IGNORECASE)
        if match:
            return match.group(1)
        return None
    
    def parse_email_for_ics(self, raw_email: bytes) -> Optional[ParsedMeetingInvite]:
        """
        Parse a raw email and extract ICS attachment.
        
        Args:
            raw_email: Raw email bytes (from SendGrid Inbound Parse)
            
        Returns:
            ParsedMeetingInvite or None if no valid ICS found
        """
        try:
            msg = message_from_bytes(raw_email)
            
            # Also check the email body for meeting URL (in case no ICS)
            email_body = self._get_email_body(msg)
            
            # Look for ICS attachments
            for part in msg.walk():
                content_type = part.get_content_type()
                filename = part.get_filename() or ""
                
                # Check for ICS content
                if content_type == "text/calendar" or filename.endswith(".ics"):
                    ics_content = part.get_payload(decode=True)
                    if isinstance(ics_content, bytes):
                        ics_content = ics_content.decode("utf-8", errors="ignore")
                    
                    invite = self.parse_ics_content(ics_content)
                    
                    # If no meeting URL in ICS, check email body
                    if not invite.meeting_url and email_body:
                        url, platform = self._find_meeting_url(email_body)
                        if url:
                            invite.meeting_url = url
                            invite.meeting_platform = platform
                    
                    # Get organizer from email headers if not in ICS
                    if not invite.organizer_email:
                        invite.organizer_email = msg.get("From", "")
                        if "<" in invite.organizer_email:
                            invite.organizer_email = self._extract_email(invite.organizer_email)
                    
                    return invite
            
            # No ICS found - try to extract from email body
            if email_body:
                url, platform = self._find_meeting_url(email_body)
                if url:
                    logger.info("No ICS found, but found meeting URL in email body")
                    return ParsedMeetingInvite(
                        meeting_url=url,
                        meeting_platform=platform,
                        organizer_email=self._extract_email(msg.get("From", "")),
                        title=msg.get("Subject", "Meeting"),
                    )
            
            logger.warning("No ICS attachment or meeting URL found in email")
            return None
            
        except Exception as e:
            logger.error(f"Error parsing email for ICS: {e}")
            return None
    
    def _extract_field(self, content: str, field_name: str) -> Optional[str]:
        """Extract a field value from ICS content.
        
        ICS format can have parameters:
        - SUMMARY:Meeting Title (simple)
        - SUMMARY;LANGUAGE=en-GB:Meeting Title (with parameters)
        
        We need to extract the value after the last colon.
        """
        # Handle multi-line values (lines starting with space are continuations)
        # Match FIELDNAME followed by optional params (;...) then : then value
        pattern = rf"^{field_name}(?:;[^:\r\n]*)?:([^\r\n]*(?:\r?\n[ \t][^\r\n]*)*)"
        match = re.search(pattern, content, re.MULTILINE | re.IGNORECASE)
        if match:
            value = match.group(1)
            # Remove line continuations
            value = re.sub(r'\r?\n[ \t]', '', value)
            # Unescape common ICS escapes
            value = value.replace("\\n", "\n").replace("\\,", ",").replace("\\;", ";")
            return value.strip()
        return None
    
    def _extract_datetime_with_tz(self, content: str, field_name: str) -> tuple[Optional[str], Optional[str]]:
        """
        Extract datetime field with timezone info.
        
        Returns (value, tzid) tuple.
        Example: DTSTART;TZID=W. Europe Standard Time:20251211T210000
        Returns: ("20251211T210000", "W. Europe Standard Time")
        """
        # Match FIELDNAME optionally with TZID parameter
        pattern = rf"^{field_name}(?:;TZID=([^:;\r\n]+))?(?:;[^:\r\n]*)?:([^\r\n]*)"
        match = re.search(pattern, content, re.MULTILINE | re.IGNORECASE)
        if match:
            tzid = match.group(1)  # May be None
            value = match.group(2)
            # Clean up line continuations
            value = re.sub(r'\r?\n[ \t]', '', value)
            return value.strip(), tzid
        return None, None
    
    # Common Windows timezone names to UTC offset (in hours)
    # Note: These are standard time offsets; DST handling would need more logic
    WINDOWS_TZ_OFFSETS = {
        "W. Europe Standard Time": 1,  # CET (UTC+1)
        "Central European Standard Time": 1,
        "Romance Standard Time": 1,  # France, etc
        "Central Europe Standard Time": 1,
        "GMT Standard Time": 0,  # UK
        "UTC": 0,
        "Eastern Standard Time": -5,  # US East
        "Pacific Standard Time": -8,  # US West
        "Mountain Standard Time": -7,
        "Central Standard Time": -6,
    }
    
    def _parse_datetime(self, dt_string: Optional[str], tzid: Optional[str] = None) -> Optional[datetime]:
        """Parse ICS datetime string.
        
        ICS datetime formats:
        - YYYYMMDDTHHMMSSZ (UTC)
        - YYYYMMDDTHHMMSS (local/naive)
        - YYYYMMDD (date only)
        
        Args:
            dt_string: The datetime value (e.g. "20251211T210000")
            tzid: Optional timezone ID (e.g. "W. Europe Standard Time")
        """
        if not dt_string:
            return None
        
        try:
            # Check if this is UTC (ends with Z)
            is_utc = dt_string.endswith("Z")
            
            # Remove Z suffix for parsing
            clean_dt = dt_string.replace("Z", "")
            
            parsed_dt = None
            if len(clean_dt) == 8:  # Date only: YYYYMMDD
                parsed_dt = datetime.strptime(clean_dt, "%Y%m%d")
            elif len(clean_dt) == 15:  # DateTime: YYYYMMDDTHHMMSS
                parsed_dt = datetime.strptime(clean_dt, "%Y%m%dT%H%M%S")
            else:
                # Try ISO format
                parsed_dt = datetime.fromisoformat(clean_dt)
            
            if parsed_dt:
                if is_utc:
                    # Explicit UTC
                    parsed_dt = parsed_dt.replace(tzinfo=timezone.utc)
                elif tzid:
                    # Try to convert from Windows timezone to UTC
                    offset_hours = self.WINDOWS_TZ_OFFSETS.get(tzid)
                    if offset_hours is not None:
                        # Create timezone and convert to UTC
                        local_tz = timezone(timedelta(hours=offset_hours))
                        parsed_dt = parsed_dt.replace(tzinfo=local_tz)
                        # Convert to UTC for consistent storage
                        parsed_dt = parsed_dt.astimezone(timezone.utc)
                        logger.info(f"[ICS-PARSER] Converted {dt_string} from {tzid} (UTC{offset_hours:+d}) to UTC: {parsed_dt}")
                    else:
                        logger.warning(f"[ICS-PARSER] Unknown timezone '{tzid}', treating as UTC")
                        parsed_dt = parsed_dt.replace(tzinfo=timezone.utc)
                else:
                    # No timezone info - assume UTC (safer for scheduling)
                    parsed_dt = parsed_dt.replace(tzinfo=timezone.utc)
                    logger.debug(f"[ICS-PARSER] No timezone info, assuming UTC for {dt_string}")
            
            return parsed_dt
        except Exception as e:
            logger.error(f"Could not parse datetime '{dt_string}' (tzid={tzid}): {e}")
            return None
    
    def _extract_email(self, value: str) -> Optional[str]:
        """Extract email address from a string."""
        # Handle formats like: mailto:user@example.com or <user@example.com>
        match = re.search(r'[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}', value)
        if match:
            return match.group(0).lower()
        return None
    
    def _extract_cn(self, value: str) -> Optional[str]:
        """Extract CN (Common Name) from ORGANIZER/ATTENDEE field."""
        match = re.search(r'CN=([^;:]+)', value, re.IGNORECASE)
        if match:
            name = match.group(1).strip('"').strip()
            return name
        return None
    
    def _extract_attendees(self, content: str) -> List[str]:
        """Extract all attendee emails from ICS content."""
        attendees = []
        pattern = r"^ATTENDEE[;:][^\r\n]*"
        for match in re.finditer(pattern, content, re.MULTILINE | re.IGNORECASE):
            email = self._extract_email(match.group(0))
            if email:
                attendees.append(email)
        return attendees
    
    def _find_meeting_url(self, text: str) -> tuple[Optional[str], Optional[str]]:
        """
        Find a meeting URL in text.
        
        Returns:
            tuple: (url, platform) or (None, None)
        """
        for pattern, platform in self.MEETING_URL_PATTERNS:
            match = re.search(pattern, text, re.IGNORECASE)
            if match:
                url = match.group(0)
                # Clean up URL (remove trailing punctuation)
                url = re.sub(r'[.,;>)}\]]+$', '', url)
                return url, platform
        return None, None
    
    def _get_email_body(self, msg: Message) -> str:
        """Extract plain text body from email message."""
        body_parts = []
        
        for part in msg.walk():
            content_type = part.get_content_type()
            if content_type == "text/plain":
                payload = part.get_payload(decode=True)
                if isinstance(payload, bytes):
                    payload = payload.decode("utf-8", errors="ignore")
                body_parts.append(payload)
            elif content_type == "text/html" and not body_parts:
                # Fallback to HTML if no plain text
                payload = part.get_payload(decode=True)
                if isinstance(payload, bytes):
                    payload = payload.decode("utf-8", errors="ignore")
                # Basic HTML tag stripping
                payload = re.sub(r'<[^>]+>', ' ', payload)
                body_parts.append(payload)
        
        return "\n".join(body_parts)


# Singleton instance
ics_parser = ICSParser()

