"""
Transcription Service - Audio to text using Deepgram

Handles audio file transcription with speaker diarization.
Falls back to OpenAI Whisper if Deepgram is not configured.

Includes automatic webm -> mp3 conversion for browser recordings.
"""

import os
import logging
import httpx
import subprocess
import tempfile
from typing import Dict, Any, Optional, List
from dataclasses import dataclass

logger = logging.getLogger(__name__)

# Timeout for transcription API calls (5 minutes for long audio)
TRANSCRIPTION_TIMEOUT = 300


@dataclass
class TranscriptionSegment:
    """A segment of transcribed audio with speaker info"""
    speaker: str
    start: float
    end: float
    text: str


@dataclass 
class TranscriptionResult:
    """Complete transcription result"""
    full_text: str
    segments: List[TranscriptionSegment]
    speaker_count: int
    duration_seconds: float
    confidence: float


class TranscriptionService:
    """Service for transcribing audio files"""
    
    def __init__(self):
        self.deepgram_api_key = os.getenv("DEEPGRAM_API_KEY")
        self.openai_api_key = os.getenv("OPENAI_API_KEY")
        
        if not self.deepgram_api_key and not self.openai_api_key:
            logger.warning("No transcription API key configured (DEEPGRAM_API_KEY or OPENAI_API_KEY)")
    
    async def transcribe_audio(
        self,
        audio_url: str,
        language: str = "en"
    ) -> TranscriptionResult:
        """
        Transcribe audio from URL
        
        Args:
            audio_url: URL to audio file (Supabase Storage)
            language: Language code (default: Dutch)
            
        Returns:
            TranscriptionResult with full text and segments
        """
        if self.deepgram_api_key:
            return await self._transcribe_with_deepgram(audio_url, language)
        elif self.openai_api_key:
            return await self._transcribe_with_whisper(audio_url, language)
        else:
            raise ValueError("No transcription API configured")
    
    async def transcribe_audio_bytes(
        self,
        audio_data: bytes,
        filename: str,
        language: str = "en"
    ) -> TranscriptionResult:
        """
        Transcribe audio from bytes
        
        Args:
            audio_data: Raw audio bytes
            filename: Original filename (for mime type detection)
            language: Language code
            
        Returns:
            TranscriptionResult
        """
        if self.deepgram_api_key:
            return await self._transcribe_bytes_deepgram(audio_data, filename, language)
        elif self.openai_api_key:
            return await self._transcribe_bytes_whisper(audio_data, filename, language)
        else:
            raise ValueError("No transcription API configured")
    
    async def _transcribe_with_deepgram(
        self,
        audio_url: str,
        language: str
    ) -> TranscriptionResult:
        """Transcribe using Deepgram API from URL"""
        
        url = "https://api.deepgram.com/v1/listen"
        
        params = {
            "model": "nova-3",  # Nova-3 Multilingual for best accuracy
            "language": language,
            "smart_format": "true",
            "diarize": "true",
            "punctuate": "true",
            "paragraphs": "true",
            "utterances": "true",
        }
        
        headers = {
            "Authorization": f"Token {self.deepgram_api_key}",
            "Content-Type": "application/json"
        }
        
        payload = {"url": audio_url}
        
        async with httpx.AsyncClient(timeout=300.0) as client:
            response = await client.post(
                url,
                params=params,
                headers=headers,
                json=payload
            )
            response.raise_for_status()
            result = response.json()
        
        return self._parse_deepgram_response(result)
    
    async def _transcribe_bytes_deepgram(
        self,
        audio_data: bytes,
        filename: str,
        language: str
    ) -> TranscriptionResult:
        """Transcribe using Deepgram API from bytes"""
        
        # Convert webm to mp3 for better Deepgram compatibility
        ext = filename.lower().split(".")[-1] if "." in filename else ""
        if ext in ["webm", "ogg"]:
            logger.info(f"Converting {ext} to mp3 for Deepgram compatibility")
            audio_data, filename = self._convert_to_mp3(audio_data, filename)
        
        url = "https://api.deepgram.com/v1/listen"
        
        params = {
            "model": "nova-3",  # Nova-3 Multilingual for best accuracy
            "language": language,
            "smart_format": "true",
            "diarize": "true",
            "punctuate": "true",
            "paragraphs": "true",
            "utterances": "true",
        }
        
        # Detect content type from filename
        content_type = self._get_content_type(filename)
        
        headers = {
            "Authorization": f"Token {self.deepgram_api_key}",
            "Content-Type": content_type
        }
        
        logger.info(f"Sending {len(audio_data)} bytes to Deepgram as {content_type}")
        
        async with httpx.AsyncClient(timeout=300.0) as client:
            response = await client.post(
                url,
                params=params,
                headers=headers,
                content=audio_data
            )
            response.raise_for_status()
            result = response.json()
        
        return self._parse_deepgram_response(result)
    
    def _convert_to_mp3(self, audio_data: bytes, filename: str) -> tuple[bytes, str]:
        """Convert audio to mp3 using ffmpeg for better Deepgram compatibility."""
        try:
            # Create temp files for input and output
            ext = filename.lower().split(".")[-1] if "." in filename else "webm"
            
            with tempfile.NamedTemporaryFile(suffix=f".{ext}", delete=False) as input_file:
                input_file.write(audio_data)
                input_path = input_file.name
            
            output_path = input_path.rsplit(".", 1)[0] + ".mp3"
            
            # Run ffmpeg conversion with high quality for transcription
            result = subprocess.run(
                [
                    "ffmpeg", "-y",  # Overwrite output
                    "-i", input_path,
                    "-acodec", "libmp3lame",
                    "-ab", "192k",   # 192kbps for better quality
                    "-ar", "16000",  # 16kHz - optimal for speech recognition
                    "-ac", "1",      # Mono channel
                    "-af", "highpass=f=200,lowpass=f=3000",  # Focus on voice frequencies
                    output_path
                ],
                capture_output=True,
                timeout=60  # 1 minute timeout
            )
            
            if result.returncode != 0:
                logger.error(f"ffmpeg conversion failed: {result.stderr.decode()}")
                # Return original data if conversion fails
                return audio_data, filename
            
            # Read converted file
            with open(output_path, "rb") as f:
                converted_data = f.read()
            
            # Cleanup temp files
            try:
                os.unlink(input_path)
                os.unlink(output_path)
            except:
                pass
            
            new_filename = filename.rsplit(".", 1)[0] + ".mp3"
            logger.info(f"Converted {filename} ({len(audio_data)} bytes) to {new_filename} ({len(converted_data)} bytes)")
            
            return converted_data, new_filename
            
        except subprocess.TimeoutExpired:
            logger.error("ffmpeg conversion timed out")
            return audio_data, filename
        except FileNotFoundError:
            logger.warning("ffmpeg not found, skipping conversion")
            return audio_data, filename
        except Exception as e:
            logger.error(f"Audio conversion failed: {e}")
            return audio_data, filename
    
    def _parse_deepgram_response(self, result: Dict[str, Any]) -> TranscriptionResult:
        """Parse Deepgram API response into TranscriptionResult"""
        
        # Get the first channel's results
        channels = result.get("results", {}).get("channels", [])
        if not channels:
            return TranscriptionResult(
                full_text="",
                segments=[],
                speaker_count=0,
                duration_seconds=0,
                confidence=0
            )
        
        channel = channels[0]
        alternatives = channel.get("alternatives", [])
        
        if not alternatives:
            return TranscriptionResult(
                full_text="",
                segments=[],
                speaker_count=0,
                duration_seconds=0,
                confidence=0
            )
        
        alternative = alternatives[0]
        
        # Get full transcript
        full_text = alternative.get("transcript", "")
        confidence = alternative.get("confidence", 0)
        
        # Parse utterances for speaker segments
        utterances = result.get("results", {}).get("utterances", [])
        segments = []
        speakers = set()
        
        for utterance in utterances:
            speaker_id = utterance.get("speaker", 0)
            speakers.add(speaker_id)
            
            segment = TranscriptionSegment(
                speaker=f"Speaker {speaker_id + 1}",
                start=utterance.get("start", 0),
                end=utterance.get("end", 0),
                text=utterance.get("transcript", "")
            )
            segments.append(segment)
        
        # Get duration from metadata
        metadata = result.get("metadata", {})
        duration = metadata.get("duration", 0)
        
        return TranscriptionResult(
            full_text=full_text,
            segments=segments,
            speaker_count=len(speakers) if speakers else 1,
            duration_seconds=duration,
            confidence=confidence
        )
    
    async def _transcribe_with_whisper(
        self,
        audio_url: str,
        language: str
    ) -> TranscriptionResult:
        """Transcribe using OpenAI Whisper API from URL"""
        
        # Download audio first
        async with httpx.AsyncClient(timeout=120.0) as client:
            response = await client.get(audio_url)
            response.raise_for_status()
            audio_data = response.content
        
        return await self._transcribe_bytes_whisper(audio_data, "audio.mp3", language)
    
    async def _transcribe_bytes_whisper(
        self,
        audio_data: bytes,
        filename: str,
        language: str
    ) -> TranscriptionResult:
        """Transcribe using OpenAI Whisper API from bytes"""
        
        url = "https://api.openai.com/v1/audio/transcriptions"
        
        headers = {
            "Authorization": f"Bearer {self.openai_api_key}"
        }
        
        # Map language codes
        lang_map = {"nl": "nl", "en": "en", "de": "de", "fr": "fr"}
        whisper_lang = lang_map.get(language, "nl")
        
        files = {
            "file": (filename, audio_data, self._get_content_type(filename)),
            "model": (None, "whisper-1"),
            "language": (None, whisper_lang),
            "response_format": (None, "verbose_json"),
        }
        
        async with httpx.AsyncClient(timeout=300.0) as client:
            response = await client.post(
                url,
                headers=headers,
                files=files
            )
            response.raise_for_status()
            result = response.json()
        
        # Parse Whisper response (no speaker diarization)
        full_text = result.get("text", "")
        duration = result.get("duration", 0)
        
        # Create single segment (Whisper doesn't do diarization)
        segments = []
        if full_text:
            segments.append(TranscriptionSegment(
                speaker="Speaker 1",
                start=0,
                end=duration,
                text=full_text
            ))
        
        return TranscriptionResult(
            full_text=full_text,
            segments=segments,
            speaker_count=1,  # Whisper doesn't identify speakers
            duration_seconds=duration,
            confidence=0.95  # Whisper doesn't return confidence
        )
    
    def _get_content_type(self, filename: str) -> str:
        """Get MIME type from filename"""
        ext = filename.lower().split(".")[-1]
        content_types = {
            "mp3": "audio/mpeg",
            "m4a": "audio/mp4",
            "wav": "audio/wav",
            "webm": "audio/webm",
            "ogg": "audio/ogg",
            "flac": "audio/flac",
        }
        return content_types.get(ext, "audio/mpeg")


# Lazy singleton
_transcription_service: Optional[TranscriptionService] = None

def get_transcription_service() -> TranscriptionService:
    """Get or create transcription service instance"""
    global _transcription_service
    if _transcription_service is None:
        _transcription_service = TranscriptionService()
    return _transcription_service

