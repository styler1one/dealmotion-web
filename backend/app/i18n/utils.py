"""
i18n utility functions for DealMotion backend.
"""

from typing import Optional
from .config import SUPPORTED_LANGUAGES, DEFAULT_LANGUAGE


# Language instructions for AI prompts
LANGUAGE_INSTRUCTIONS = {
    "nl": "Schrijf alles in het Nederlands.",
    "en": "Write everything in English.",
    "de": "Schreibe alles auf Deutsch.",
    "fr": "Écris tout en français.",
    "es": "Escribe todo en español.",
    "hi": "सब कुछ हिंदी में लिखें।",
    "ar": "اكتب كل شيء باللغة العربية.",
}

# Conciseness instructions
CONCISE_INSTRUCTIONS = {
    "nl": "Wees bondig en feitelijk.",
    "en": "Be concise and factual.",
    "de": "Sei prägnant und sachlich.",
    "fr": "Sois concis et factuel.",
    "es": "Sé conciso y objetivo.",
    "hi": "संक्षिप्त और तथ्यात्मक रहें।",
    "ar": "كن موجزًا وواقعيًا.",
}


def get_language_instruction(language: str = DEFAULT_LANGUAGE) -> str:
    """
    Get the 'write in X language' instruction for AI prompts.
    
    Args:
        language: ISO 639-1 language code
        
    Returns:
        Language instruction string
    """
    return LANGUAGE_INSTRUCTIONS.get(language, LANGUAGE_INSTRUCTIONS[DEFAULT_LANGUAGE])


def get_concise_instruction(language: str = DEFAULT_LANGUAGE) -> str:
    """
    Get the 'be concise' instruction for AI prompts.
    
    Args:
        language: ISO 639-1 language code
        
    Returns:
        Conciseness instruction string
    """
    return CONCISE_INSTRUCTIONS.get(language, CONCISE_INSTRUCTIONS[DEFAULT_LANGUAGE])


def resolve_working_language(
    request_language: Optional[str] = None,
    user_override: Optional[str] = None,
    org_default: str = DEFAULT_LANGUAGE
) -> str:
    """
    Resolve the working language with fallback chain.
    
    Priority:
    1. Explicit request parameter
    2. User's language override
    3. Organization default
    4. System default (English)
    
    Args:
        request_language: Language specified in API request
        user_override: User's personal language preference
        org_default: Organization's default language
        
    Returns:
        Resolved language code
    """
    if request_language and request_language in SUPPORTED_LANGUAGES:
        return request_language
    if user_override and user_override in SUPPORTED_LANGUAGES:
        return user_override
    if org_default and org_default in SUPPORTED_LANGUAGES:
        return org_default
    return DEFAULT_LANGUAGE


def resolve_client_language(
    email_language: Optional[str] = None,
    prospect_preferred: Optional[str] = None,
    working_language: str = DEFAULT_LANGUAGE
) -> str:
    """
    Resolve the client communication language with fallback chain.
    
    Priority:
    1. Explicit email language parameter
    2. Prospect's preferred language
    3. User's working language
    4. System default (English)
    
    Args:
        email_language: Language specified for this email
        prospect_preferred: Prospect's preferred language
        working_language: User's working language
        
    Returns:
        Resolved language code
    """
    if email_language and email_language in SUPPORTED_LANGUAGES:
        return email_language
    if prospect_preferred and prospect_preferred in SUPPORTED_LANGUAGES:
        return prospect_preferred
    if working_language and working_language in SUPPORTED_LANGUAGES:
        return working_language
    return DEFAULT_LANGUAGE


# Country to language mapping for auto-detection
COUNTRY_LANGUAGE_MAP = {
    # Dutch
    "Netherlands": "nl", "Nederland": "nl", "NL": "nl",
    # English
    "UK": "en", "United Kingdom": "en", "USA": "en",
    "United States": "en", "Canada": "en", "Australia": "en",
    "Ireland": "en", "New Zealand": "en", "Singapore": "en",
    # German
    "Germany": "de", "Deutschland": "de", "Austria": "de",
    "Österreich": "de", "Switzerland": "de", "Schweiz": "de",
    # French
    "France": "fr", "Belgium": "fr", "Belgique": "fr",
    "Luxembourg": "fr", "Monaco": "fr",
    # Spanish
    "Spain": "es", "España": "es", "Mexico": "es", "México": "es",
    "Argentina": "es", "Colombia": "es", "Chile": "es", "Peru": "es",
    # Hindi
    "India": "hi", "भारत": "hi",
    # Arabic
    "Saudi Arabia": "ar", "UAE": "ar", "United Arab Emirates": "ar",
    "Egypt": "ar", "Morocco": "ar", "Qatar": "ar", "Kuwait": "ar",
    "Jordan": "ar", "Lebanon": "ar", "Oman": "ar", "Bahrain": "ar",
}


def suggest_language_from_country(country: Optional[str]) -> str:
    """
    Suggest a language based on country name.
    
    Args:
        country: Country name
        
    Returns:
        Suggested language code (defaults to English for unknown countries)
    """
    if not country:
        return "en"  # Default to English for international
    return COUNTRY_LANGUAGE_MAP.get(country, "en")


# Country name to ISO 3166-1 alpha-2 code mapping
COUNTRY_TO_ISO = {
    # Common countries
    "Netherlands": "NL", "Nederland": "NL",
    "United States": "US", "USA": "US", "United States of America": "US",
    "United Kingdom": "GB", "UK": "GB", "Great Britain": "GB", "England": "GB",
    "Germany": "DE", "Deutschland": "DE",
    "France": "FR",
    "Spain": "ES", "España": "ES",
    "Italy": "IT", "Italia": "IT",
    "Belgium": "BE", "België": "BE", "Belgique": "BE",
    "Austria": "AT", "Österreich": "AT",
    "Switzerland": "CH", "Schweiz": "CH", "Suisse": "CH",
    "Canada": "CA",
    "Australia": "AU",
    "New Zealand": "NZ",
    "Ireland": "IE",
    "India": "IN", "भारत": "IN",
    "China": "CN", "中国": "CN",
    "Japan": "JP", "日本": "JP",
    "South Korea": "KR", "Korea": "KR",
    "Singapore": "SG",
    "Brazil": "BR", "Brasil": "BR",
    "Mexico": "MX", "México": "MX",
    "Argentina": "AR",
    "Colombia": "CO",
    "Chile": "CL",
    "Peru": "PE", "Perú": "PE",
    "Poland": "PL", "Polska": "PL",
    "Sweden": "SE", "Sverige": "SE",
    "Norway": "NO", "Norge": "NO",
    "Denmark": "DK", "Danmark": "DK",
    "Finland": "FI", "Suomi": "FI",
    "Portugal": "PT",
    "Greece": "GR", "Ελλάδα": "GR",
    "Turkey": "TR", "Türkiye": "TR",
    "Russia": "RU", "Россия": "RU",
    "Ukraine": "UA", "Україна": "UA",
    "Czech Republic": "CZ", "Czechia": "CZ",
    "Hungary": "HU", "Magyarország": "HU",
    "Romania": "RO", "România": "RO",
    "South Africa": "ZA",
    "Israel": "IL", "ישראל": "IL",
    "Saudi Arabia": "SA", "المملكة العربية السعودية": "SA",
    "UAE": "AE", "United Arab Emirates": "AE",
    "Egypt": "EG", "مصر": "EG",
    "Morocco": "MA", "المغرب": "MA",
    "Qatar": "QA",
    "Kuwait": "KW",
    "Indonesia": "ID",
    "Malaysia": "MY",
    "Thailand": "TH", "ประเทศไทย": "TH",
    "Vietnam": "VN", "Việt Nam": "VN",
    "Philippines": "PH",
    "Luxembourg": "LU",
}


def get_country_iso_code(country_name: Optional[str]) -> Optional[str]:
    """
    Convert a country name to its 2-letter ISO 3166-1 alpha-2 code.
    
    Used for Claude's web search tool which requires ISO country codes.
    Case-insensitive lookup.
    
    Args:
        country_name: Full country name or common variant
        
    Returns:
        2-letter ISO code or None if not found
    """
    if not country_name:
        return None
    
    country_clean = country_name.strip()
    
    # Check if it's already a 2-letter code
    if len(country_clean) == 2:
        return country_clean.upper()
    
    # Try exact match first
    if country_clean in COUNTRY_TO_ISO:
        return COUNTRY_TO_ISO[country_clean]
    
    # Try case-insensitive lookup
    country_lower = country_clean.lower()
    for name, code in COUNTRY_TO_ISO.items():
        if name.lower() == country_lower:
            return code
    
    return None