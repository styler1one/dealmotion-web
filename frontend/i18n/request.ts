import { getRequestConfig } from 'next-intl/server';
import { cookies, headers } from 'next/headers';
import { defaultLocale, locales, type Locale } from './config';

export default getRequestConfig(async () => {
  // Try to get locale from cookie first
  const cookieStore = await cookies();
  const localeCookie = cookieStore.get('NEXT_LOCALE')?.value;
  
  // Validate and use cookie value, or fall back to default
  let locale: Locale = defaultLocale;
  if (localeCookie && locales.includes(localeCookie as Locale)) {
    locale = localeCookie as Locale;
  } else {
    // Try Accept-Language header as fallback
    const headerStore = await headers();
    const acceptLanguage = headerStore.get('accept-language');
    if (acceptLanguage) {
      // Parse Accept-Language header (e.g., "nl-NL,nl;q=0.9,en;q=0.8")
      const preferred = acceptLanguage.split(',')[0]?.split('-')[0]?.toLowerCase();
      if (preferred && locales.includes(preferred as Locale)) {
        locale = preferred as Locale;
      }
    }
  }
  
  return {
    locale,
    messages: (await import(`../messages/${locale}.json`)).default,
  };
});

