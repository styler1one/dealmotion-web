"""
Transcript Parser Service

Parses transcript files in various formats:
- Plain text (.txt)
- Markdown (.md)
- Word documents (.docx)
- SRT subtitles (.srt)
"""

import re
import logging
from typing import List, Dict, Any, Optional
from dataclasses import dataclass
from io import BytesIO

logger = logging.getLogger(__name__)


@dataclass
class TranscriptSegment:
    """A segment of transcript with optional speaker and timing"""
    speaker: Optional[str]
    start: Optional[float]
    end: Optional[float]
    text: str


@dataclass
class ParsedTranscript:
    """Parsed transcript result"""
    full_text: str
    segments: List[TranscriptSegment]
    speaker_count: int
    estimated_duration: Optional[float]


class TranscriptParser:
    """Service for parsing transcript files"""
    
    def parse_file(self, file_data: bytes, filename: str) -> ParsedTranscript:
        """
        Parse a transcript file based on its extension
        
        Args:
            file_data: Raw file bytes
            filename: Original filename for type detection
            
        Returns:
            ParsedTranscript with full text and segments
        """
        ext = filename.lower().split(".")[-1]
        
        if ext == "txt":
            return self._parse_text(file_data)
        elif ext == "md":
            return self._parse_markdown(file_data)
        elif ext == "docx":
            return self._parse_docx(file_data)
        elif ext == "srt":
            return self._parse_srt(file_data)
        else:
            # Default to plain text
            return self._parse_text(file_data)
    
    def _parse_text(self, file_data: bytes) -> ParsedTranscript:
        """Parse plain text transcript"""
        try:
            text = file_data.decode("utf-8")
        except UnicodeDecodeError:
            text = file_data.decode("latin-1")
        
        # Try to detect speaker patterns like "Speaker 1:", "John:", "[Sales Rep]"
        segments = self._extract_speaker_segments(text)
        speakers = set(seg.speaker for seg in segments if seg.speaker)
        
        return ParsedTranscript(
            full_text=text.strip(),
            segments=segments,
            speaker_count=len(speakers) if speakers else 1,
            estimated_duration=None
        )
    
    def _parse_markdown(self, file_data: bytes) -> ParsedTranscript:
        """Parse markdown transcript"""
        try:
            text = file_data.decode("utf-8")
        except UnicodeDecodeError:
            text = file_data.decode("latin-1")
        
        # Remove markdown formatting
        text = re.sub(r'#{1,6}\s+', '', text)  # Headers
        text = re.sub(r'\*\*([^*]+)\*\*', r'\1', text)  # Bold
        text = re.sub(r'\*([^*]+)\*', r'\1', text)  # Italic
        text = re.sub(r'`([^`]+)`', r'\1', text)  # Code
        
        segments = self._extract_speaker_segments(text)
        speakers = set(seg.speaker for seg in segments if seg.speaker)
        
        return ParsedTranscript(
            full_text=text.strip(),
            segments=segments,
            speaker_count=len(speakers) if speakers else 1,
            estimated_duration=None
        )
    
    def _parse_docx(self, file_data: bytes) -> ParsedTranscript:
        """Parse Word document transcript"""
        try:
            from docx import Document
            doc = Document(BytesIO(file_data))
            
            paragraphs = []
            for para in doc.paragraphs:
                if para.text.strip():
                    paragraphs.append(para.text.strip())
            
            text = "\n\n".join(paragraphs)
            segments = self._extract_speaker_segments(text)
            speakers = set(seg.speaker for seg in segments if seg.speaker)
            
            return ParsedTranscript(
                full_text=text,
                segments=segments,
                speaker_count=len(speakers) if speakers else 1,
                estimated_duration=None
            )
        except ImportError:
            logger.warning("python-docx not installed, treating as text")
            return self._parse_text(file_data)
        except Exception as e:
            logger.error(f"Error parsing docx: {e}")
            return self._parse_text(file_data)
    
    def _parse_srt(self, file_data: bytes) -> ParsedTranscript:
        """Parse SRT subtitle file"""
        try:
            text = file_data.decode("utf-8")
        except UnicodeDecodeError:
            text = file_data.decode("latin-1")
        
        segments = []
        full_text_parts = []
        max_end_time = 0
        
        # SRT format: index, timestamp, text, blank line
        pattern = r'(\d+)\n(\d{2}:\d{2}:\d{2},\d{3}) --> (\d{2}:\d{2}:\d{2},\d{3})\n(.*?)(?=\n\n|\Z)'
        matches = re.findall(pattern, text, re.DOTALL)
        
        for match in matches:
            index, start_time, end_time, subtitle_text = match
            
            # Parse timestamps
            start_seconds = self._srt_time_to_seconds(start_time)
            end_seconds = self._srt_time_to_seconds(end_time)
            max_end_time = max(max_end_time, end_seconds)
            
            # Clean text
            subtitle_text = subtitle_text.strip().replace('\n', ' ')
            
            # Try to extract speaker from text like "[Speaker 1] Hello"
            speaker = None
            speaker_match = re.match(r'\[([^\]]+)\]\s*(.+)', subtitle_text)
            if speaker_match:
                speaker = speaker_match.group(1)
                subtitle_text = speaker_match.group(2)
            
            segments.append(TranscriptSegment(
                speaker=speaker,
                start=start_seconds,
                end=end_seconds,
                text=subtitle_text
            ))
            full_text_parts.append(subtitle_text)
        
        speakers = set(seg.speaker for seg in segments if seg.speaker)
        
        return ParsedTranscript(
            full_text=" ".join(full_text_parts),
            segments=segments,
            speaker_count=len(speakers) if speakers else 1,
            estimated_duration=max_end_time if max_end_time > 0 else None
        )
    
    def _srt_time_to_seconds(self, time_str: str) -> float:
        """Convert SRT timestamp to seconds"""
        # Format: HH:MM:SS,mmm
        parts = time_str.replace(',', '.').split(':')
        hours = int(parts[0])
        minutes = int(parts[1])
        seconds = float(parts[2])
        return hours * 3600 + minutes * 60 + seconds
    
    def _extract_speaker_segments(self, text: str) -> List[TranscriptSegment]:
        """
        Try to extract speaker-labeled segments from text
        
        Supports patterns like:
        - "Speaker 1: Hello"
        - "John: Hello"
        - "[Sales Rep] Hello"
        - "**John**: Hello"
        """
        segments = []
        
        # Pattern for "Name:" or "[Name]" at start of line
        pattern = r'^(?:\[([^\]]+)\]|([A-Za-z0-9\s]+):)\s*(.+?)(?=^(?:\[|[A-Za-z0-9\s]+:)|\Z)'
        matches = re.findall(pattern, text, re.MULTILINE | re.DOTALL)
        
        if matches:
            for match in matches:
                speaker = match[0] or match[1]
                content = match[2].strip()
                if speaker and content:
                    segments.append(TranscriptSegment(
                        speaker=speaker.strip(),
                        start=None,
                        end=None,
                        text=content
                    ))
        
        # If no speaker patterns found, treat whole text as one segment
        if not segments:
            segments.append(TranscriptSegment(
                speaker=None,
                start=None,
                end=None,
                text=text.strip()
            ))
        
        return segments


# Singleton
_transcript_parser: Optional[TranscriptParser] = None

def get_transcript_parser() -> TranscriptParser:
    """Get or create transcript parser instance"""
    global _transcript_parser
    if _transcript_parser is None:
        _transcript_parser = TranscriptParser()
    return _transcript_parser

