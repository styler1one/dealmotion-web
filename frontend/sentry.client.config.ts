// This file configures the initialization of Sentry on the client.
// The config you add here will be used whenever a users loads a page in their browser.
// https://docs.sentry.io/platforms/javascript/guides/nextjs/

import * as Sentry from "@sentry/nextjs";

Sentry.init({
  dsn: process.env.NEXT_PUBLIC_SENTRY_DSN,

  // Only enable in production
  enabled: process.env.NODE_ENV === "production",

  // Adjust this value in production, or use tracesSampler for greater control
  tracesSampleRate: 0.1,

  // Setting this option to true will print useful information to the console while you're setting up Sentry.
  debug: false,

  // Replay configuration for session recording (optional - costs extra)
  replaysOnErrorSampleRate: 1.0,
  replaysSessionSampleRate: 0.1,

  integrations: [
    Sentry.replayIntegration({
      // Mask all text content for privacy
      maskAllText: true,
      blockAllMedia: true,
    }),
  ],

  // Filter out common non-actionable errors
  ignoreErrors: [
    // Browser extensions
    "top.GLOBALS",
    "originalCreateNotification",
    "canvas.contentDocument",
    "MyApp_RemoveAllHighlights",
    "http://tt.teleportatic.com",
    "jigsaw is not defined",
    "ComboSearch is not defined",
    "atomicFindClose",
    "fb_xd_fragment",
    // Common network errors
    "Failed to fetch",
    "Load failed",
    "NetworkError",
    "ChunkLoadError",
    // User-triggered cancellations
    "AbortError",
    "The operation was aborted",
  ],

  // Add user context when available
  beforeSend(event) {
    // You can modify the event here before it's sent
    return event;
  },
});

