-- ============================================================
-- MIGRATION: Cleanup Orphaned Coach Suggestions
-- Date: 2025-12-04
-- 
-- This script removes coach suggestions that reference deleted entities.
-- Run this once to clean up existing orphaned data.
-- ============================================================

-- 1. Delete suggestions referencing non-existent research briefs
DELETE FROM coach_suggestions cs
WHERE cs.suggestion_type IN ('add_contacts', 'overdue_prospect')
  AND cs.related_entity_id IS NOT NULL
  AND NOT EXISTS (
    SELECT 1 FROM research_briefs rb 
    WHERE rb.id = cs.related_entity_id::uuid
  );

-- 2. Delete suggestions referencing non-existent meeting preps
DELETE FROM coach_suggestions cs
WHERE cs.suggestion_type IN ('create_prep', 'needs_followup')
  AND cs.related_entity_id IS NOT NULL
  AND NOT EXISTS (
    SELECT 1 FROM meeting_preps mp 
    WHERE mp.id = cs.related_entity_id::uuid
  );

-- 3. Delete suggestions referencing non-existent followups
DELETE FROM coach_suggestions cs
WHERE cs.suggestion_type IN ('generate_action', 'create_followup')
  AND cs.related_entity_id IS NOT NULL
  AND NOT EXISTS (
    SELECT 1 FROM followups f 
    WHERE f.id = cs.related_entity_id::uuid
  );

-- 4. Show remaining suggestions count
SELECT 
  suggestion_type,
  COUNT(*) as count
FROM coach_suggestions
GROUP BY suggestion_type
ORDER BY count DESC;

