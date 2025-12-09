-- =====================================================
-- FINAL FIX - Remaining Performance Issues
-- =====================================================

-- -----------------------------------------------------
-- FIX 1: Users table policy (missing "select" wrapper)
-- -----------------------------------------------------
DROP POLICY IF EXISTS "Users can view own data" ON users;
CREATE POLICY "Users can view own data" ON users
    FOR SELECT USING (id = (select auth.uid()));

-- -----------------------------------------------------
-- FIX 2: Remove duplicate indexes
-- Keep the newer, more descriptive names
-- -----------------------------------------------------

-- organization_members: keep idx_organization_members_user_id
DROP INDEX IF EXISTS idx_org_members_user_id;

-- sales_profiles: keep idx_sales_profiles_user_id and idx_sales_profiles_org_id
DROP INDEX IF EXISTS idx_sales_profiles_user;
DROP INDEX IF EXISTS idx_sales_profiles_org;

-- research_briefs: keep idx_research_briefs_org_id
DROP INDEX IF EXISTS idx_research_briefs_org;

-- followups: keep idx_followups_org_id
DROP INDEX IF EXISTS idx_followups_org;

-- knowledge_base_files: keep idx_knowledge_base_files_org_id
DROP INDEX IF EXISTS idx_kb_files_org;

-- followup_actions: keep idx_followup_actions_followup_id
DROP INDEX IF EXISTS idx_followup_actions_followup;

-- =====================================================
-- DONE! All performance warnings should now be resolved.
-- =====================================================

