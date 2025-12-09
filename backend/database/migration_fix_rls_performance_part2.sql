-- =====================================================
-- FIX RLS PERFORMANCE ISSUES - PART 2
-- =====================================================
-- Continue from Part 1
-- =====================================================

-- -----------------------------------------------------
-- TABLE: meeting_preps
-- -----------------------------------------------------
DROP POLICY IF EXISTS "Users can view own org preps" ON meeting_preps;
DROP POLICY IF EXISTS "Users can insert own org preps" ON meeting_preps;
DROP POLICY IF EXISTS "Users can update own org preps" ON meeting_preps;
DROP POLICY IF EXISTS "Users can delete own org preps" ON meeting_preps;

CREATE POLICY "Users can view own org preps" ON meeting_preps
    FOR SELECT USING (
        organization_id IN (
            SELECT organization_id 
            FROM organization_members 
            WHERE user_id = (select auth.uid())
        )
    );

CREATE POLICY "Users can insert own org preps" ON meeting_preps
    FOR INSERT WITH CHECK (
        organization_id IN (
            SELECT organization_id 
            FROM organization_members 
            WHERE user_id = (select auth.uid())
        )
    );

CREATE POLICY "Users can update own org preps" ON meeting_preps
    FOR UPDATE USING (
        organization_id IN (
            SELECT organization_id 
            FROM organization_members 
            WHERE user_id = (select auth.uid())
        )
    );

CREATE POLICY "Users can delete own org preps" ON meeting_preps
    FOR DELETE USING (
        organization_id IN (
            SELECT organization_id 
            FROM organization_members 
            WHERE user_id = (select auth.uid())
        )
    );

-- -----------------------------------------------------
-- TABLE: followups
-- -----------------------------------------------------
DROP POLICY IF EXISTS "Users can view own org followups" ON followups;
DROP POLICY IF EXISTS "Users can insert own org followups" ON followups;
DROP POLICY IF EXISTS "Users can update own org followups" ON followups;
DROP POLICY IF EXISTS "Users can delete own org followups" ON followups;

CREATE POLICY "Users can view own org followups" ON followups
    FOR SELECT USING (
        organization_id IN (
            SELECT organization_id 
            FROM organization_members 
            WHERE user_id = (select auth.uid())
        )
    );

CREATE POLICY "Users can insert own org followups" ON followups
    FOR INSERT WITH CHECK (
        organization_id IN (
            SELECT organization_id 
            FROM organization_members 
            WHERE user_id = (select auth.uid())
        )
    );

CREATE POLICY "Users can update own org followups" ON followups
    FOR UPDATE USING (
        organization_id IN (
            SELECT organization_id 
            FROM organization_members 
            WHERE user_id = (select auth.uid())
        )
    );

CREATE POLICY "Users can delete own org followups" ON followups
    FOR DELETE USING (
        organization_id IN (
            SELECT organization_id 
            FROM organization_members 
            WHERE user_id = (select auth.uid())
        )
    );

-- -----------------------------------------------------
-- TABLE: followup_actions
-- -----------------------------------------------------
DROP POLICY IF EXISTS "Users can view own followup actions" ON followup_actions;
DROP POLICY IF EXISTS "Users can insert own followup actions" ON followup_actions;
DROP POLICY IF EXISTS "Users can update own followup actions" ON followup_actions;
DROP POLICY IF EXISTS "Users can delete own followup actions" ON followup_actions;

CREATE POLICY "Users can view own followup actions" ON followup_actions
    FOR SELECT USING (
        followup_id IN (
            SELECT id FROM followups 
            WHERE organization_id IN (
                SELECT organization_id 
                FROM organization_members 
                WHERE user_id = (select auth.uid())
            )
        )
    );

CREATE POLICY "Users can insert own followup actions" ON followup_actions
    FOR INSERT WITH CHECK (
        followup_id IN (
            SELECT id FROM followups 
            WHERE organization_id IN (
                SELECT organization_id 
                FROM organization_members 
                WHERE user_id = (select auth.uid())
            )
        )
    );

CREATE POLICY "Users can update own followup actions" ON followup_actions
    FOR UPDATE USING (
        followup_id IN (
            SELECT id FROM followups 
            WHERE organization_id IN (
                SELECT organization_id 
                FROM organization_members 
                WHERE user_id = (select auth.uid())
            )
        )
    );

CREATE POLICY "Users can delete own followup actions" ON followup_actions
    FOR DELETE USING (
        followup_id IN (
            SELECT id FROM followups 
            WHERE organization_id IN (
                SELECT organization_id 
                FROM organization_members 
                WHERE user_id = (select auth.uid())
            )
        )
    );

-- -----------------------------------------------------
-- TABLE: prospect_contacts
-- -----------------------------------------------------
DROP POLICY IF EXISTS "Users can view own org contacts" ON prospect_contacts;
DROP POLICY IF EXISTS "Users can insert own org contacts" ON prospect_contacts;
DROP POLICY IF EXISTS "Users can update own org contacts" ON prospect_contacts;
DROP POLICY IF EXISTS "Users can delete own org contacts" ON prospect_contacts;
DROP POLICY IF EXISTS "Service role full access to contacts" ON prospect_contacts;

-- Consolidate into single policies (also fixes multiple_permissive_policies)
-- Note: Service role bypasses RLS anyway, so we don't need a separate policy
CREATE POLICY "Users can view own org contacts" ON prospect_contacts
    FOR SELECT USING (
        organization_id IN (
            SELECT organization_id 
            FROM organization_members 
            WHERE user_id = (select auth.uid())
        )
    );

CREATE POLICY "Users can insert own org contacts" ON prospect_contacts
    FOR INSERT WITH CHECK (
        organization_id IN (
            SELECT organization_id 
            FROM organization_members 
            WHERE user_id = (select auth.uid())
        )
    );

CREATE POLICY "Users can update own org contacts" ON prospect_contacts
    FOR UPDATE USING (
        organization_id IN (
            SELECT organization_id 
            FROM organization_members 
            WHERE user_id = (select auth.uid())
        )
    );

CREATE POLICY "Users can delete own org contacts" ON prospect_contacts
    FOR DELETE USING (
        organization_id IN (
            SELECT organization_id 
            FROM organization_members 
            WHERE user_id = (select auth.uid())
        )
    );

-- -----------------------------------------------------
-- TABLE: user_settings
-- -----------------------------------------------------
DROP POLICY IF EXISTS "Users can read own settings" ON user_settings;
DROP POLICY IF EXISTS "Users can insert own settings" ON user_settings;
DROP POLICY IF EXISTS "Users can update own settings" ON user_settings;
DROP POLICY IF EXISTS "Users can delete own settings" ON user_settings;

CREATE POLICY "Users can read own settings" ON user_settings
    FOR SELECT USING (user_id = (select auth.uid()));

CREATE POLICY "Users can insert own settings" ON user_settings
    FOR INSERT WITH CHECK (user_id = (select auth.uid()));

CREATE POLICY "Users can update own settings" ON user_settings
    FOR UPDATE USING (user_id = (select auth.uid()));

CREATE POLICY "Users can delete own settings" ON user_settings
    FOR DELETE USING (user_id = (select auth.uid()));

-- -----------------------------------------------------
-- TABLE: organization_subscriptions
-- -----------------------------------------------------
DROP POLICY IF EXISTS "Subscriptions viewable by org members" ON organization_subscriptions;
CREATE POLICY "Subscriptions viewable by org members" ON organization_subscriptions
    FOR SELECT USING (
        organization_id IN (
            SELECT organization_id 
            FROM organization_members 
            WHERE user_id = (select auth.uid())
        )
    );

-- -----------------------------------------------------
-- TABLE: usage_records
-- -----------------------------------------------------
DROP POLICY IF EXISTS "Usage viewable by org members" ON usage_records;
CREATE POLICY "Usage viewable by org members" ON usage_records
    FOR SELECT USING (
        organization_id IN (
            SELECT organization_id 
            FROM organization_members 
            WHERE user_id = (select auth.uid())
        )
    );

-- -----------------------------------------------------
-- TABLE: payment_history
-- -----------------------------------------------------
DROP POLICY IF EXISTS "Payments viewable by org admins" ON payment_history;
CREATE POLICY "Payments viewable by org admins" ON payment_history
    FOR SELECT USING (
        organization_id IN (
            SELECT organization_id 
            FROM organization_members 
            WHERE user_id = (select auth.uid()) AND role = 'admin'
        )
    );

-- -----------------------------------------------------
-- TABLE: coach_settings
-- -----------------------------------------------------
DROP POLICY IF EXISTS "Users manage own coach settings" ON coach_settings;
CREATE POLICY "Users manage own coach settings" ON coach_settings
    FOR ALL USING (user_id = (select auth.uid()));

-- -----------------------------------------------------
-- TABLE: coach_behavior_events
-- -----------------------------------------------------
DROP POLICY IF EXISTS "Users view own behavior events" ON coach_behavior_events;
DROP POLICY IF EXISTS "Users insert own behavior events" ON coach_behavior_events;

CREATE POLICY "Users view own behavior events" ON coach_behavior_events
    FOR SELECT USING (user_id = (select auth.uid()));

CREATE POLICY "Users insert own behavior events" ON coach_behavior_events
    FOR INSERT WITH CHECK (user_id = (select auth.uid()));

-- -----------------------------------------------------
-- TABLE: coach_user_patterns
-- -----------------------------------------------------
DROP POLICY IF EXISTS "Users view own patterns" ON coach_user_patterns;
DROP POLICY IF EXISTS "Service manages patterns" ON coach_user_patterns;

-- Consolidate into single policy (also fixes multiple_permissive_policies)
-- Note: Service role bypasses RLS anyway
CREATE POLICY "Users view own patterns" ON coach_user_patterns
    FOR SELECT USING (user_id = (select auth.uid()));

-- -----------------------------------------------------
-- TABLE: coach_suggestions
-- -----------------------------------------------------
DROP POLICY IF EXISTS "Users manage own suggestions" ON coach_suggestions;
CREATE POLICY "Users manage own suggestions" ON coach_suggestions
    FOR ALL USING (user_id = (select auth.uid()));

-- -----------------------------------------------------
-- TABLE: coach_success_patterns
-- -----------------------------------------------------
DROP POLICY IF EXISTS "Org members view success patterns" ON coach_success_patterns;
CREATE POLICY "Org members view success patterns" ON coach_success_patterns
    FOR SELECT USING (
        organization_id IN (
            SELECT organization_id 
            FROM organization_members 
            WHERE user_id = (select auth.uid())
        )
    );


-- =====================================================
-- PART 2: ADD INDEXES FOR OPTIMIZED RLS SUBQUERIES
-- =====================================================
-- These indexes improve the performance of the subqueries used in RLS policies

-- Index for organization_members lookups (most common pattern)
CREATE INDEX IF NOT EXISTS idx_organization_members_user_id 
    ON organization_members(user_id);

CREATE INDEX IF NOT EXISTS idx_organization_members_user_org 
    ON organization_members(user_id, organization_id);

CREATE INDEX IF NOT EXISTS idx_organization_members_user_role 
    ON organization_members(user_id, role);

-- Index for knowledge_base_files lookups
CREATE INDEX IF NOT EXISTS idx_knowledge_base_files_org_id 
    ON knowledge_base_files(organization_id);

-- Index for research_briefs lookups
CREATE INDEX IF NOT EXISTS idx_research_briefs_org_id 
    ON research_briefs(organization_id);

-- Index for followups lookups
CREATE INDEX IF NOT EXISTS idx_followups_org_id 
    ON followups(organization_id);

-- Index for followup_actions lookups
CREATE INDEX IF NOT EXISTS idx_followup_actions_followup_id 
    ON followup_actions(followup_id);

-- Index for sales_profiles lookups
CREATE INDEX IF NOT EXISTS idx_sales_profiles_user_id 
    ON sales_profiles(user_id);

CREATE INDEX IF NOT EXISTS idx_sales_profiles_org_id 
    ON sales_profiles(organization_id);


-- =====================================================
-- VERIFICATION QUERY
-- =====================================================
-- Run this after the migration to verify policies are updated:
/*
SELECT schemaname, tablename, policyname, 
       CASE WHEN qual LIKE '%select auth.uid()%' THEN '✅ Optimized' ELSE '❌ Needs fix' END as status
FROM pg_policies 
WHERE schemaname = 'public' 
ORDER BY tablename, policyname;
*/

