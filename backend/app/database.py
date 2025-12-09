"""
Centralized database client management.

This module provides singleton Supabase client instances to avoid
creating multiple connections throughout the application.
"""
import os
from functools import lru_cache
from supabase import create_client, Client
from dotenv import load_dotenv

load_dotenv()


class DatabaseConfig:
    """Configuration for database connections."""
    
    def __init__(self):
        self.supabase_url = os.getenv("SUPABASE_URL")
        self.supabase_anon_key = os.getenv("SUPABASE_KEY")
        self.supabase_service_key = os.getenv("SUPABASE_SERVICE_ROLE_KEY")
        
        # Validate required environment variables
        if not self.supabase_url:
            raise ValueError("SUPABASE_URL environment variable is required")
        if not self.supabase_anon_key:
            raise ValueError("SUPABASE_KEY environment variable is required")
    
    @property
    def service_key(self) -> str:
        """Get service key, falling back to anon key if not set."""
        return self.supabase_service_key or self.supabase_anon_key


# Singleton config instance
_config: DatabaseConfig = None


def get_config() -> DatabaseConfig:
    """Get the database configuration singleton."""
    global _config
    if _config is None:
        _config = DatabaseConfig()
    return _config


@lru_cache(maxsize=1)
def get_supabase_service() -> Client:
    """
    Get the Supabase service client (bypasses RLS).
    
    Use this for background tasks and admin operations.
    This client uses the service role key.
    
    Returns:
        Supabase Client with service role permissions
    """
    config = get_config()
    return create_client(config.supabase_url, config.service_key)


def get_user_client(user_token: str) -> Client:
    """
    Create a Supabase client with user's JWT token for RLS.
    
    Use this for user-facing operations where RLS should apply.
    
    Args:
        user_token: The user's JWT token from the Authorization header
        
    Returns:
        Supabase Client with user's permissions (RLS applies)
    """
    config = get_config()
    client = create_client(config.supabase_url, config.supabase_anon_key)
    client.postgrest.auth(user_token)
    return client


# Convenience exports
def get_supabase_url() -> str:
    """Get the Supabase URL."""
    return get_config().supabase_url


def get_supabase_anon_key() -> str:
    """Get the Supabase anon key."""
    return get_config().supabase_anon_key

