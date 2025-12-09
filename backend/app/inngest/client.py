"""
Inngest Client Configuration.

Configures the Inngest client with proper credentials and settings.
"""

import os
import logging
from inngest import Inngest

logger = logging.getLogger(__name__)

# Determine if we're in development mode
IS_DEV = os.getenv("INNGEST_DEV", "true").lower() == "true"
ENVIRONMENT = os.getenv("ENVIRONMENT", "development")

# Create Inngest client
inngest_client = Inngest(
    app_id="dealmotion",
    # Event key is required for sending events in production
    # In dev mode, it can be omitted
    event_key=os.getenv("INNGEST_EVENT_KEY"),
    # Signing key for webhook verification
    signing_key=os.getenv("INNGEST_SIGNING_KEY"),
    # Enable dev mode for local development
    is_production=ENVIRONMENT == "production",
)

logger.info(f"Inngest client initialized (dev={IS_DEV}, env={ENVIRONMENT})")


def get_inngest_client() -> Inngest:
    """Get the Inngest client instance."""
    return inngest_client

