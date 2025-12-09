// Supported locales
export const locales = ['nl', 'en', 'de', 'fr', 'es', 'hi', 'ar'] as const;
export type Locale = (typeof locales)[number];

// Default locale (English for international app)
export const defaultLocale: Locale = 'en';

// RTL locales
export const rtlLocales: Locale[] = ['ar'];

// Check if locale is RTL
export function isRtlLocale(locale: Locale): boolean {
  return rtlLocales.includes(locale);
}

// Get direction for locale
export function getDirection(locale: Locale): 'ltr' | 'rtl' {
  return isRtlLocale(locale) ? 'rtl' : 'ltr';
}

// Locale display names (in their own language)
export const localeNames: Record<Locale, string> = {
  nl: 'Nederlands',
  en: 'English',
  de: 'Deutsch',
  fr: 'Français',
  es: 'Español',
  hi: 'हिन्दी',
  ar: 'العربية',
};

// Locale flags (emoji)
export const localeFlags: Record<Locale, string> = {
  nl: '🇳🇱',
  en: '🇬🇧',
  de: '🇩🇪',
  fr: '🇫🇷',
  es: '🇪🇸',
  hi: '🇮🇳',
  ar: '🇸🇦',
};

