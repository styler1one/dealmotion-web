"""
Encryption Service - Secure storage of sensitive data like API keys.

Uses Fernet symmetric encryption with a key derived from environment variable.
Falls back to base64 encoding if cryptography is not available (dev mode warning).
"""
import os
import base64
import logging
from typing import Optional

logger = logging.getLogger(__name__)

# Try to import cryptography for proper encryption
try:
    from cryptography.fernet import Fernet
    from cryptography.hazmat.primitives import hashes
    from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC
    CRYPTO_AVAILABLE = True
except ImportError:
    CRYPTO_AVAILABLE = False
    logger.warning("cryptography package not installed. Using base64 encoding (NOT secure for production!)")


def _get_encryption_key() -> Optional[bytes]:
    """
    Get or derive encryption key from environment.
    Uses ENCRYPTION_KEY env var, or derives from SECRET_KEY.
    """
    # First try dedicated encryption key
    encryption_key = os.getenv("ENCRYPTION_KEY")
    if encryption_key:
        # If it's already a valid Fernet key (44 chars base64), use directly
        if len(encryption_key) == 44:
            return encryption_key.encode()
        # Otherwise derive from it
        return _derive_key(encryption_key)
    
    # Fall back to SECRET_KEY
    secret_key = os.getenv("SECRET_KEY") or os.getenv("SUPABASE_JWT_SECRET")
    if secret_key:
        return _derive_key(secret_key)
    
    logger.warning("No encryption key found in environment. Using fallback (NOT secure!)")
    return None


def _derive_key(password: str) -> bytes:
    """Derive a Fernet-compatible key from a password string."""
    if not CRYPTO_AVAILABLE:
        return None
    
    # Use a fixed salt (in production, could use per-user salt stored separately)
    salt = b"dealmotion_api_key_salt_v1"
    
    kdf = PBKDF2HMAC(
        algorithm=hashes.SHA256(),
        length=32,
        salt=salt,
        iterations=100000,
    )
    
    key = base64.urlsafe_b64encode(kdf.derive(password.encode()))
    return key


# Initialize encryption key at module load
_ENCRYPTION_KEY = _get_encryption_key()
_FERNET = Fernet(_ENCRYPTION_KEY) if CRYPTO_AVAILABLE and _ENCRYPTION_KEY else None


def encrypt_api_key(api_key: str) -> dict:
    """
    Encrypt an API key for secure storage.
    
    Returns:
        dict with 'encrypted_key' and 'encryption_type'
    """
    if _FERNET:
        # Use Fernet encryption
        encrypted = _FERNET.encrypt(api_key.encode())
        return {
            "encrypted_key": encrypted.decode(),
            "encryption_type": "fernet"
        }
    else:
        # Fallback to base64 (NOT secure, only for development)
        logger.warning("Using base64 encoding for API key (not secure!)")
        encoded = base64.b64encode(api_key.encode()).decode()
        return {
            "api_key": encoded,
            "key_type": "base64"
        }


def decrypt_api_key(credentials: dict) -> Optional[str]:
    """
    Decrypt an API key from stored credentials.
    
    Args:
        credentials: dict containing encrypted key data
        
    Returns:
        Decrypted API key string, or None if decryption fails
    """
    if not credentials:
        return None
    
    encryption_type = credentials.get("encryption_type") or credentials.get("key_type")
    
    if encryption_type == "fernet":
        if not _FERNET:
            logger.error("Cannot decrypt Fernet-encrypted key: encryption not available")
            return None
        
        try:
            encrypted_key = credentials.get("encrypted_key")
            if not encrypted_key:
                return None
            decrypted = _FERNET.decrypt(encrypted_key.encode())
            return decrypted.decode()
        except Exception as e:
            logger.error(f"Failed to decrypt API key: {e}")
            return None
    
    elif encryption_type == "base64":
        # Legacy base64 encoding
        encoded_key = credentials.get("api_key")
        if not encoded_key:
            return None
        try:
            return base64.b64decode(encoded_key.encode()).decode()
        except Exception as e:
            logger.error(f"Failed to decode base64 API key: {e}")
            return None
    
    else:
        logger.warning(f"Unknown encryption type: {encryption_type}")
        return None


def is_encryption_secure() -> bool:
    """Check if we're using secure encryption (vs fallback base64)."""
    return _FERNET is not None


# =============================================================================
# OAuth Token Encryption (for calendar connections, etc.)
# =============================================================================

def encrypt_token(token: str) -> str:
    """
    Encrypt an OAuth token for secure database storage.
    
    Args:
        token: Plain text OAuth token (access_token or refresh_token)
        
    Returns:
        Encrypted token string (Fernet encrypted, or base64 with prefix for fallback)
    """
    if not token:
        return ""
    
    if _FERNET:
        # Use Fernet encryption - prefix with 'fernet:' for identification
        encrypted = _FERNET.encrypt(token.encode())
        return f"fernet:{encrypted.decode()}"
    else:
        # Fallback to base64 with prefix (NOT secure, only for development)
        logger.warning("Using base64 encoding for OAuth token (not secure!)")
        encoded = base64.b64encode(token.encode()).decode()
        return f"base64:{encoded}"


def decrypt_token(encrypted_token: str) -> Optional[str]:
    """
    Decrypt an OAuth token from database storage.
    
    Handles multiple formats:
    - 'fernet:...' - Fernet encrypted
    - 'base64:...' - Base64 encoded (legacy/fallback)
    - Plain text - Legacy unencrypted tokens (for backwards compatibility)
    
    Args:
        encrypted_token: Encrypted token string from database
        
    Returns:
        Decrypted token string, or None if decryption fails
    """
    if not encrypted_token:
        return None
    
    # Handle bytes from BYTEA column
    if isinstance(encrypted_token, bytes):
        encrypted_token = encrypted_token.decode('utf-8')
    
    # Handle PostgreSQL hex format
    if encrypted_token.startswith('\\x'):
        try:
            hex_data = encrypted_token[2:]
            encrypted_token = bytes.fromhex(hex_data).decode('utf-8')
        except Exception as e:
            logger.error(f"Failed to decode hex token: {e}")
            return None
    
    # Check for encryption prefix
    if encrypted_token.startswith('fernet:'):
        if not _FERNET:
            logger.error("Cannot decrypt Fernet-encrypted token: encryption not available")
            return None
        try:
            encrypted_data = encrypted_token[7:]  # Remove 'fernet:' prefix
            decrypted = _FERNET.decrypt(encrypted_data.encode())
            return decrypted.decode()
        except Exception as e:
            logger.error(f"Failed to decrypt Fernet token: {e}")
            return None
    
    elif encrypted_token.startswith('base64:'):
        try:
            encoded_data = encrypted_token[7:]  # Remove 'base64:' prefix
            return base64.b64decode(encoded_data.encode()).decode()
        except Exception as e:
            logger.error(f"Failed to decode base64 token: {e}")
            return None
    
    else:
        # Legacy: plain text token or old base64 format
        # Check if it looks like a valid OAuth token (Google starts with 'ya29', MS varies)
        if encrypted_token.startswith('ya29') or encrypted_token.startswith('eyJ'):
            logger.warning("Found unencrypted OAuth token - consider re-authenticating")
            return encrypted_token
        
        # Try base64 decode for very old legacy data
        try:
            padding_needed = len(encrypted_token) % 4
            if padding_needed:
                padded = encrypted_token + '=' * (4 - padding_needed)
            else:
                padded = encrypted_token
            decoded = base64.b64decode(padded).decode('utf-8')
            if decoded.startswith('ya29') or decoded.startswith('eyJ'):
                return decoded
        except (ValueError, UnicodeDecodeError):
            pass
        
        # Return as-is if we can't determine the format
        return encrypted_token
