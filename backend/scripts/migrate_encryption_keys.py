"""
Migration Script: Re-encrypt credentials with new ENCRYPTION_KEY

This script migrates encrypted data from the legacy key (derived from SECRET_KEY)
to the new dedicated ENCRYPTION_KEY.

Tables affected:
- integrations (credentials JSONB) - Fireflies, Zoom, Teams API keys
- calendar_connections (access_token_encrypted, refresh_token_encrypted) - OAuth tokens

Usage:
    # Dry run (shows what would be migrated)
    python scripts/migrate_encryption_keys.py --dry-run

    # Actually perform migration
    python scripts/migrate_encryption_keys.py

Requirements:
    - Both ENCRYPTION_KEY and SECRET_KEY/SUPABASE_JWT_SECRET must be set
    - Run from backend directory: cd backend && python scripts/migrate_encryption_keys.py
"""
import os
import sys
import json
import argparse
import logging

# Add parent directory to path for imports
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.database import get_supabase_service
from app.services.encryption import (
    decrypt_api_key,
    encrypt_api_key,
    decrypt_token,
    encrypt_token,
    needs_reencryption_api_key,
    get_encryption_key_count,
    has_legacy_keys,
)

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


def migrate_integrations(supabase, dry_run: bool = True) -> dict:
    """
    Migrate integrations table credentials.
    
    Returns:
        dict with migration stats
    """
    stats = {
        "total": 0,
        "needs_migration": 0,
        "migrated": 0,
        "failed": 0,
        "already_ok": 0,
    }
    
    logger.info("Checking integrations table...")
    
    # Fetch all integrations with credentials
    result = supabase.table("integrations").select(
        "id, provider, credentials, organization_id"
    ).execute()
    
    integrations = result.data or []
    stats["total"] = len(integrations)
    
    for integration in integrations:
        int_id = integration["id"]
        provider = integration["provider"]
        credentials = integration.get("credentials")
        
        if not credentials:
            logger.debug(f"Integration {int_id} ({provider}): No credentials, skipping")
            continue
        
        # Check if re-encryption is needed
        if needs_reencryption_api_key(credentials):
            stats["needs_migration"] += 1
            logger.info(f"Integration {int_id} ({provider}): Needs migration")
            
            if dry_run:
                continue
            
            # Re-encrypt
            new_credentials = encrypt_api_key(decrypt_api_key(credentials))
            if new_credentials:
                try:
                    supabase.table("integrations").update({
                        "credentials": new_credentials
                    }).eq("id", int_id).execute()
                    stats["migrated"] += 1
                    logger.info(f"Integration {int_id} ({provider}): Migrated successfully")
                except Exception as e:
                    stats["failed"] += 1
                    logger.error(f"Integration {int_id} ({provider}): Migration failed - {e}")
            else:
                stats["failed"] += 1
                logger.error(f"Integration {int_id} ({provider}): Could not decrypt/re-encrypt")
        else:
            # Check if credentials can be decrypted at all
            decrypted = decrypt_api_key(credentials)
            if decrypted:
                stats["already_ok"] += 1
                logger.debug(f"Integration {int_id} ({provider}): Already using primary key")
            else:
                stats["failed"] += 1
                logger.warning(f"Integration {int_id} ({provider}): Cannot decrypt with any key")
    
    return stats


def migrate_calendar_connections(supabase, dry_run: bool = True) -> dict:
    """
    Migrate calendar_connections table tokens.
    
    Returns:
        dict with migration stats
    """
    stats = {
        "total": 0,
        "needs_migration": 0,
        "migrated": 0,
        "failed": 0,
        "already_ok": 0,
    }
    
    logger.info("Checking calendar_connections table...")
    
    # Fetch all calendar connections
    result = supabase.table("calendar_connections").select(
        "id, provider, user_id, access_token_encrypted, refresh_token_encrypted"
    ).execute()
    
    connections = result.data or []
    stats["total"] = len(connections)
    
    for conn in connections:
        conn_id = conn["id"]
        provider = conn["provider"]
        access_token = conn.get("access_token_encrypted")
        refresh_token = conn.get("refresh_token_encrypted")
        
        needs_migration = False
        new_access = None
        new_refresh = None
        
        # Check access token
        if access_token:
            # Handle bytes/string conversion
            if isinstance(access_token, bytes):
                access_token = access_token.decode('utf-8')
            
            # Check if it's already encrypted with fernet: prefix
            if access_token.startswith('fernet:'):
                # Try to decrypt - if it fails with primary but works with legacy, needs migration
                decrypted = decrypt_token(access_token)
                if decrypted:
                    # Check if we used legacy key (by trying primary only)
                    from app.services.encryption import _ALL_FERNETS, InvalidToken
                    if _ALL_FERNETS:
                        try:
                            _ALL_FERNETS[0].decrypt(access_token[7:].encode())
                        except InvalidToken:
                            needs_migration = True
                            new_access = encrypt_token(decrypted)
            elif access_token.startswith('ya29') or access_token.startswith('eyJ'):
                # Plain text legacy token - should be encrypted
                needs_migration = True
                new_access = encrypt_token(access_token)
        
        # Check refresh token
        if refresh_token:
            if isinstance(refresh_token, bytes):
                refresh_token = refresh_token.decode('utf-8')
            
            if refresh_token.startswith('fernet:'):
                decrypted = decrypt_token(refresh_token)
                if decrypted:
                    from app.services.encryption import _ALL_FERNETS, InvalidToken
                    if _ALL_FERNETS:
                        try:
                            _ALL_FERNETS[0].decrypt(refresh_token[7:].encode())
                        except InvalidToken:
                            needs_migration = True
                            new_refresh = encrypt_token(decrypted)
            elif refresh_token and not refresh_token.startswith('fernet:') and not refresh_token.startswith('base64:'):
                # Plain text legacy token
                needs_migration = True
                new_refresh = encrypt_token(refresh_token)
        
        if needs_migration:
            stats["needs_migration"] += 1
            logger.info(f"Calendar {conn_id} ({provider}): Needs migration")
            
            if dry_run:
                continue
            
            # Build update
            update_data = {}
            if new_access:
                update_data["access_token_encrypted"] = new_access
            if new_refresh:
                update_data["refresh_token_encrypted"] = new_refresh
            
            if update_data:
                try:
                    supabase.table("calendar_connections").update(
                        update_data
                    ).eq("id", conn_id).execute()
                    stats["migrated"] += 1
                    logger.info(f"Calendar {conn_id} ({provider}): Migrated successfully")
                except Exception as e:
                    stats["failed"] += 1
                    logger.error(f"Calendar {conn_id} ({provider}): Migration failed - {e}")
        else:
            stats["already_ok"] += 1
    
    return stats


def main():
    parser = argparse.ArgumentParser(
        description="Migrate encrypted credentials to new ENCRYPTION_KEY"
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Show what would be migrated without making changes"
    )
    args = parser.parse_args()
    
    # Check encryption setup
    key_count = get_encryption_key_count()
    logger.info(f"Encryption keys available: {key_count}")
    
    if key_count == 0:
        logger.error("No encryption keys found! Set ENCRYPTION_KEY and/or SECRET_KEY")
        sys.exit(1)
    
    if not has_legacy_keys():
        logger.warning("No legacy keys found. Make sure SECRET_KEY or SUPABASE_JWT_SECRET is set.")
        logger.warning("If this is a fresh install, no migration is needed.")
        if key_count == 1:
            logger.info("Only primary key available - migration not applicable")
            sys.exit(0)
    
    logger.info(f"Mode: {'DRY RUN' if args.dry_run else 'LIVE MIGRATION'}")
    if args.dry_run:
        logger.info("No changes will be made to the database")
    
    # Get database connection
    supabase = get_supabase_service()
    
    # Migrate integrations
    logger.info("\n" + "=" * 50)
    logger.info("INTEGRATIONS TABLE")
    logger.info("=" * 50)
    int_stats = migrate_integrations(supabase, dry_run=args.dry_run)
    logger.info(f"Results: {json.dumps(int_stats, indent=2)}")
    
    # Migrate calendar connections
    logger.info("\n" + "=" * 50)
    logger.info("CALENDAR CONNECTIONS TABLE")
    logger.info("=" * 50)
    cal_stats = migrate_calendar_connections(supabase, dry_run=args.dry_run)
    logger.info(f"Results: {json.dumps(cal_stats, indent=2)}")
    
    # Summary
    logger.info("\n" + "=" * 50)
    logger.info("MIGRATION SUMMARY")
    logger.info("=" * 50)
    
    total_needs = int_stats["needs_migration"] + cal_stats["needs_migration"]
    total_migrated = int_stats["migrated"] + cal_stats["migrated"]
    total_failed = int_stats["failed"] + cal_stats["failed"]
    
    logger.info(f"Records needing migration: {total_needs}")
    
    if args.dry_run:
        logger.info("Run without --dry-run to perform actual migration")
    else:
        logger.info(f"Successfully migrated: {total_migrated}")
        logger.info(f"Failed: {total_failed}")
        
        if total_failed > 0:
            logger.warning("Some records failed to migrate. Check logs above.")
            sys.exit(1)
    
    logger.info("Migration check complete!")


if __name__ == "__main__":
    main()

