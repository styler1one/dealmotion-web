/**
 * Language utilities for i18n
 * Maps countries to languages and provides language metadata
 */

export const SUPPORTED_LANGUAGES = ['nl', 'en', 'de', 'fr', 'es', 'hi', 'ar'] as const;
export type SupportedLanguage = typeof SUPPORTED_LANGUAGES[number];

export const LANGUAGE_INFO: Record<SupportedLanguage, {
  name: string;
  nativeName: string;
  flag: string;
  direction: 'ltr' | 'rtl';
}> = {
  nl: { name: 'Dutch', nativeName: 'Nederlands', flag: '🇳🇱', direction: 'ltr' },
  en: { name: 'English', nativeName: 'English', flag: '🇬🇧', direction: 'ltr' },
  de: { name: 'German', nativeName: 'Deutsch', flag: '🇩🇪', direction: 'ltr' },
  fr: { name: 'French', nativeName: 'Français', flag: '🇫🇷', direction: 'ltr' },
  es: { name: 'Spanish', nativeName: 'Español', flag: '🇪🇸', direction: 'ltr' },
  hi: { name: 'Hindi', nativeName: 'हिन्दी', flag: '🇮🇳', direction: 'ltr' },
  ar: { name: 'Arabic', nativeName: 'العربية', flag: '🇸🇦', direction: 'rtl' },
};

// Country to language mapping - matches backend app/i18n/utils.py
const COUNTRY_LANGUAGE_MAP: Record<string, SupportedLanguage> = {
  // Dutch
  'Netherlands': 'nl', 'Nederland': 'nl', 'NL': 'nl', 'the Netherlands': 'nl',
  // English
  'UK': 'en', 'United Kingdom': 'en', 'USA': 'en', 'United States': 'en',
  'Canada': 'en', 'Australia': 'en', 'Ireland': 'en', 'New Zealand': 'en',
  'Singapore': 'en', 'Great Britain': 'en', 'England': 'en',
  // German
  'Germany': 'de', 'Deutschland': 'de', 'Austria': 'de', 'Österreich': 'de',
  'Switzerland': 'de', 'Schweiz': 'de', 'Suisse': 'de',
  // French
  'France': 'fr', 'Belgium': 'fr', 'Belgique': 'fr', 'België': 'fr',
  'Luxembourg': 'fr', 'Monaco': 'fr',
  // Spanish
  'Spain': 'es', 'España': 'es', 'Mexico': 'es', 'México': 'es',
  'Argentina': 'es', 'Colombia': 'es', 'Chile': 'es', 'Peru': 'es', 'Perú': 'es',
  'Venezuela': 'es', 'Ecuador': 'es', 'Bolivia': 'es', 'Uruguay': 'es',
  'Paraguay': 'es', 'Costa Rica': 'es', 'Panama': 'es', 'Panamá': 'es',
  // Hindi
  'India': 'hi', 'भारत': 'hi',
  // Arabic
  'Saudi Arabia': 'ar', 'UAE': 'ar', 'United Arab Emirates': 'ar',
  'Egypt': 'ar', 'Morocco': 'ar', 'Qatar': 'ar', 'Kuwait': 'ar',
  'Jordan': 'ar', 'Lebanon': 'ar', 'Oman': 'ar', 'Bahrain': 'ar',
  'Iraq': 'ar', 'Syria': 'ar', 'Libya': 'ar', 'Tunisia': 'ar', 'Algeria': 'ar',
};

/**
 * Suggest a language based on country name
 * @param country - Country name (case-insensitive)
 * @returns Suggested language code (defaults to 'en' for unknown countries)
 */
export function suggestLanguageFromCountry(country: string | null | undefined): SupportedLanguage {
  if (!country) return 'en';
  
  // Try exact match first
  const exactMatch = COUNTRY_LANGUAGE_MAP[country];
  if (exactMatch) return exactMatch;
  
  // Try case-insensitive match
  const lowerCountry = country.toLowerCase();
  for (const [key, lang] of Object.entries(COUNTRY_LANGUAGE_MAP)) {
    if (key.toLowerCase() === lowerCountry) {
      return lang;
    }
  }
  
  // Try partial match (e.g., "Netherlands" in "The Netherlands")
  for (const [key, lang] of Object.entries(COUNTRY_LANGUAGE_MAP)) {
    if (lowerCountry.includes(key.toLowerCase()) || key.toLowerCase().includes(lowerCountry)) {
      return lang;
    }
  }
  
  // Default to English for international/unknown
  return 'en';
}

/**
 * Get display label for a language
 * @param lang - Language code
 * @param includeFlag - Whether to include the flag emoji
 * @returns Display label like "🇳🇱 Nederlands" or "Nederlands"
 */
export function getLanguageLabel(lang: SupportedLanguage, includeFlag = true): string {
  const info = LANGUAGE_INFO[lang];
  if (!info) return lang;
  return includeFlag ? `${info.flag} ${info.nativeName}` : info.nativeName;
}

/**
 * Check if a language is RTL
 * @param lang - Language code
 * @returns true if the language is right-to-left
 */
export function isRtlLanguage(lang: string): boolean {
  return lang === 'ar';
}

