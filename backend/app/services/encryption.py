"""
Encryption Service - Secure storage of sensitive data like API keys.

Uses Fernet symmetric encryption with a key derived from environment variable.
Falls back to base64 encoding if cryptography is not available (dev mode warning).

Supports dual-key decryption for migration from legacy keys (derived from SECRET_KEY)
to new dedicated ENCRYPTION_KEY.
"""
import os
import base64
import logging
from typing import Optional, List

logger = logging.getLogger(__name__)

# Try to import cryptography for proper encryption
try:
    from cryptography.fernet import Fernet, InvalidToken
    from cryptography.hazmat.primitives import hashes
    from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC
    CRYPTO_AVAILABLE = True
except ImportError:
    CRYPTO_AVAILABLE = False
    InvalidToken = Exception  # Fallback for type hints
    logger.warning("cryptography package not installed. Using base64 encoding (NOT secure for production!)")


def _derive_key(password: str) -> Optional[bytes]:
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


def _get_primary_encryption_key() -> Optional[bytes]:
    """
    Get the primary encryption key (new ENCRYPTION_KEY).
    This is used for all new encryptions.
    """
    encryption_key = os.getenv("ENCRYPTION_KEY")
    if encryption_key:
        # If it's already a valid Fernet key (44 chars base64), use directly
        if len(encryption_key) == 44:
            return encryption_key.encode()
        # Otherwise derive from it
        return _derive_key(encryption_key)
    return None


def _get_legacy_encryption_key() -> Optional[bytes]:
    """
    Get the legacy encryption key (derived from SECRET_KEY/SUPABASE_JWT_SECRET).
    Used for backwards compatibility with data encrypted before ENCRYPTION_KEY was added.
    """
    secret_key = os.getenv("SECRET_KEY") or os.getenv("SUPABASE_JWT_SECRET")
    if secret_key:
        return _derive_key(secret_key)
    return None


def _get_all_encryption_keys() -> List[bytes]:
    """
    Get all available encryption keys in priority order.
    First key is used for encryption, all keys are tried for decryption.
    """
    keys = []
    
    # Primary key (new ENCRYPTION_KEY)
    primary = _get_primary_encryption_key()
    if primary:
        keys.append(primary)
    
    # Legacy key (derived from SECRET_KEY)
    legacy = _get_legacy_encryption_key()
    if legacy and legacy not in keys:
        keys.append(legacy)
    
    return keys


# Initialize encryption keys at module load
_ALL_KEYS = _get_all_encryption_keys()
_PRIMARY_KEY = _ALL_KEYS[0] if _ALL_KEYS else None
_FERNET = Fernet(_PRIMARY_KEY) if CRYPTO_AVAILABLE and _PRIMARY_KEY else None

# Create Fernet instances for all keys (for decryption fallback)
_ALL_FERNETS: List[Fernet] = []
if CRYPTO_AVAILABLE:
    for key in _ALL_KEYS:
        try:
            _ALL_FERNETS.append(Fernet(key))
        except Exception as e:
            logger.warning(f"Failed to create Fernet instance for key: {e}")

if len(_ALL_KEYS) > 1:
    logger.info(f"Encryption service initialized with {len(_ALL_KEYS)} keys (primary + {len(_ALL_KEYS)-1} legacy)")
elif len(_ALL_KEYS) == 1:
    logger.info("Encryption service initialized with primary key")
else:
    logger.warning("No encryption key found in environment. Using fallback (NOT secure!)")


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
    
    Tries all available encryption keys (primary + legacy) for decryption,
    enabling migration from old keys to new keys.
    
    Args:
        credentials: dict containing encrypted key data
        
    Returns:
        Decrypted API key string, or None if decryption fails
    """
    if not credentials:
        return None
    
    encryption_type = credentials.get("encryption_type") or credentials.get("key_type")
    
    if encryption_type == "fernet":
        if not _ALL_FERNETS:
            logger.error("Cannot decrypt Fernet-encrypted key: encryption not available")
            return None
        
        encrypted_key = credentials.get("encrypted_key")
        if not encrypted_key:
            return None
        
        # Try all available keys (primary first, then legacy)
        for i, fernet in enumerate(_ALL_FERNETS):
            try:
                decrypted = fernet.decrypt(encrypted_key.encode())
                if i > 0:
                    logger.info(f"Decrypted API key using legacy key #{i} - consider re-encrypting")
                return decrypted.decode()
            except InvalidToken:
                continue  # Try next key
            except Exception as e:
                logger.debug(f"Decryption attempt {i} failed: {e}")
                continue
        
        logger.error("Failed to decrypt API key with any available key")
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
        if not _ALL_FERNETS:
            logger.error("Cannot decrypt Fernet-encrypted token: encryption not available")
            return None
        
        encrypted_data = encrypted_token[7:]  # Remove 'fernet:' prefix
        
        # Try all available keys (primary first, then legacy)
        for i, fernet in enumerate(_ALL_FERNETS):
            try:
                decrypted = fernet.decrypt(encrypted_data.encode())
                if i > 0:
                    logger.info(f"Decrypted OAuth token using legacy key #{i} - consider re-encrypting")
                return decrypted.decode()
            except InvalidToken:
                continue  # Try next key
            except Exception as e:
                logger.debug(f"Token decryption attempt {i} failed: {e}")
                continue
        
        logger.error("Failed to decrypt Fernet token with any available key")
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


# =============================================================================
# Migration Functions - For re-encrypting data with new keys
# =============================================================================

def needs_reencryption_api_key(credentials: dict) -> bool:
    """
    Check if an API key needs to be re-encrypted with the primary key.
    Returns True if decryption works but required a legacy key.
    """
    if not credentials or not _ALL_FERNETS or len(_ALL_FERNETS) < 2:
        return False
    
    encryption_type = credentials.get("encryption_type") or credentials.get("key_type")
    if encryption_type != "fernet":
        return False
    
    encrypted_key = credentials.get("encrypted_key")
    if not encrypted_key:
        return False
    
    # Try with primary key first
    try:
        _ALL_FERNETS[0].decrypt(encrypted_key.encode())
        return False  # Primary key works, no re-encryption needed
    except InvalidToken:
        pass
    
    # Try legacy keys
    for fernet in _ALL_FERNETS[1:]:
        try:
            fernet.decrypt(encrypted_key.encode())
            return True  # Legacy key works, needs re-encryption
        except InvalidToken:
            continue
    
    return False  # No key works


def reencrypt_api_key(credentials: dict) -> Optional[dict]:
    """
    Re-encrypt an API key with the primary key.
    
    Args:
        credentials: dict containing encrypted key data
        
    Returns:
        New credentials dict with re-encrypted key, or None if failed
    """
    # First decrypt with any available key
    decrypted = decrypt_api_key(credentials)
    if not decrypted:
        return None
    
    # Re-encrypt with primary key
    return encrypt_api_key(decrypted)


def reencrypt_token(encrypted_token: str) -> Optional[str]:
    """
    Re-encrypt an OAuth token with the primary key.
    
    Args:
        encrypted_token: Encrypted token string
        
    Returns:
        Re-encrypted token string, or None if failed
    """
    # First decrypt with any available key
    decrypted = decrypt_token(encrypted_token)
    if not decrypted:
        return None
    
    # Re-encrypt with primary key
    return encrypt_token(decrypted)


def get_encryption_key_count() -> int:
    """Get the number of available encryption keys."""
    return len(_ALL_KEYS)


def has_legacy_keys() -> bool:
    """Check if legacy keys are available for migration."""
    return len(_ALL_KEYS) > 1
