"""
Internationalization (i18n) module for DealMotion.

Provides:
- Language constants and utilities
- Prompt templates per language
- Language detection helpers
"""

from .config import (
    SUPPORTED_LANGUAGES,
    DEFAULT_LANGUAGE,
    RTL_LANGUAGES,
    is_supported_language,
    is_rtl_language,
    get_language_name,
)

from .utils import (
    get_language_instruction,
    resolve_working_language,
    resolve_client_language,
)

__all__ = [
    "SUPPORTED_LANGUAGES",
    "DEFAULT_LANGUAGE",
    "RTL_LANGUAGES",
    "is_supported_language",
    "is_rtl_language",
    "get_language_name",
    "get_language_instruction",
    "resolve_working_language",
    "resolve_client_language",
]

