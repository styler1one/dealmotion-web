"""
Coach Suggestions Cleanup Service

This service handles cleanup of coach suggestions when related entities
(research, preps, followups) are deleted.
"""

import logging
from typing import Optional, List

logger = logging.getLogger(__name__)


async def cleanup_suggestions_for_entity(
    supabase,
    entity_type: str,
    entity_id: str,
    user_id: Optional[str] = None
) -> int:
    """
    Delete coach suggestions related to a deleted entity.
    
    Args:
        supabase: Supabase client
        entity_type: Type of entity ('research', 'prep', 'followup')
        entity_id: ID of the deleted entity
        user_id: Optional user ID to scope the cleanup
        
    Returns:
        Number of suggestions deleted
    """
    try:
        query = supabase.table("coach_suggestions") \
            .delete() \
            .eq("related_entity_id", entity_id)
        
        if user_id:
            query = query.eq("user_id", user_id)
        
        result = query.execute()
        
        deleted_count = len(result.data) if result.data else 0
        
        if deleted_count > 0:
            logger.info(f"Cleaned up {deleted_count} suggestions for deleted {entity_type} {entity_id}")
        
        return deleted_count
        
    except Exception as e:
        logger.warning(f"Failed to cleanup suggestions for {entity_type} {entity_id}: {e}")
        return 0


async def cleanup_orphaned_suggestions(supabase, user_id: str) -> dict:
    """
    Clean up all orphaned suggestions for a user.
    
    This removes suggestions where the related entity no longer exists.
    
    Args:
        supabase: Supabase client
        user_id: User ID
        
    Returns:
        Dict with cleanup stats
    """
    stats = {
        "research_orphans": 0,
        "prep_orphans": 0,
        "followup_orphans": 0,
        "total_cleaned": 0,
    }
    
    try:
        # Get all suggestions with related_entity_id for this user
        suggestions_result = supabase.table("coach_suggestions") \
            .select("id, suggestion_type, related_entity_id") \
            .eq("user_id", user_id) \
            .not_.is_("related_entity_id", "null") \
            .execute()
        
        if not suggestions_result.data:
            return stats
        
        orphan_ids = []
        
        for suggestion in suggestions_result.data:
            entity_id = suggestion.get("related_entity_id")
            suggestion_type = suggestion.get("suggestion_type", "")
            
            if not entity_id:
                continue
            
            # Check if entity exists based on suggestion type
            entity_exists = False
            
            if suggestion_type in ["add_contacts", "overdue_prospect"]:
                # Check research_briefs
                check = supabase.table("research_briefs") \
                    .select("id") \
                    .eq("id", entity_id) \
                    .limit(1) \
                    .execute()
                entity_exists = bool(check.data)
                if not entity_exists:
                    stats["research_orphans"] += 1
                    
            elif suggestion_type in ["create_prep", "needs_followup"]:
                # Check meeting_preps  
                check = supabase.table("meeting_preps") \
                    .select("id") \
                    .eq("id", entity_id) \
                    .limit(1) \
                    .execute()
                entity_exists = bool(check.data)
                if not entity_exists:
                    stats["prep_orphans"] += 1
                    
            elif suggestion_type in ["generate_action", "create_followup"]:
                # Check followups
                check = supabase.table("followups") \
                    .select("id") \
                    .eq("id", entity_id) \
                    .limit(1) \
                    .execute()
                entity_exists = bool(check.data)
                if not entity_exists:
                    stats["followup_orphans"] += 1
            else:
                # Unknown type, skip
                continue
            
            if not entity_exists:
                orphan_ids.append(suggestion["id"])
        
        # Delete orphaned suggestions
        if orphan_ids:
            for orphan_id in orphan_ids:
                supabase.table("coach_suggestions") \
                    .delete() \
                    .eq("id", orphan_id) \
                    .execute()
            
            stats["total_cleaned"] = len(orphan_ids)
            logger.info(f"Cleaned up {len(orphan_ids)} orphaned suggestions for user {user_id}")
        
        return stats
        
    except Exception as e:
        logger.error(f"Error cleaning orphaned suggestions: {e}")
        return stats


def filter_valid_suggestions(suggestions: List[dict], valid_entity_ids: set) -> List[dict]:
    """
    Filter suggestions to only include those with valid entity references.
    
    Args:
        suggestions: List of suggestion dicts
        valid_entity_ids: Set of valid entity IDs
        
    Returns:
        Filtered list of suggestions
    """
    return [
        s for s in suggestions
        if not s.get("related_entity_id") or s.get("related_entity_id") in valid_entity_ids
    ]

