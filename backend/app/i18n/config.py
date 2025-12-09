"""
i18n configuration for DealMotion backend.
"""

from typing import List, Optional

# Supported language codes (ISO 639-1)
SUPPORTED_LANGUAGES: List[str] = ["nl", "en", "de", "fr", "es", "hi", "ar"]

# Default language (English for international app)
DEFAULT_LANGUAGE: str = "en"

# Right-to-left languages
RTL_LANGUAGES: List[str] = ["ar"]

# Language display names
LANGUAGE_NAMES = {
    "nl": "Nederlands",
    "en": "English",
    "de": "Deutsch",
    "fr": "Français",
    "es": "Español",
    "hi": "हिन्दी",
    "ar": "العربية",
}

# Language names in English (for logging/admin)
LANGUAGE_NAMES_EN = {
    "nl": "Dutch",
    "en": "English",
    "de": "German",
    "fr": "French",
    "es": "Spanish",
    "hi": "Hindi",
    "ar": "Arabic",
}


def is_supported_language(language: Optional[str]) -> bool:
    """Check if a language code is supported."""
    return language in SUPPORTED_LANGUAGES if language else False


def is_rtl_language(language: str) -> bool:
    """Check if a language is right-to-left."""
    return language in RTL_LANGUAGES


def get_language_name(language: str, in_english: bool = False) -> str:
    """Get the display name for a language."""
    if in_english:
        return LANGUAGE_NAMES_EN.get(language, language)
    return LANGUAGE_NAMES.get(language, language)

