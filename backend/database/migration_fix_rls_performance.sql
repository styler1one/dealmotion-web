-- =====================================================
-- FIX RLS PERFORMANCE ISSUES
-- =====================================================
-- This migration fixes two types of performance issues:
-- 1. auth_rls_initplan: Replace auth.uid() with (select auth.uid())
-- 2. multiple_permissive_policies: Consolidate duplicate policies
-- 
-- Run this in Supabase SQL Editor
-- =====================================================

-- =====================================================
-- PART 1: FIX auth_rls_initplan ISSUES
-- Replace auth.uid() with (select auth.uid()) for all policies
-- This prevents re-evaluation for each row
-- =====================================================

-- -----------------------------------------------------
-- TABLE: users
-- -----------------------------------------------------
DROP POLICY IF EXISTS "Users can view own profile" ON users;
DROP POLICY IF EXISTS "Users can update own profile" ON users;
DROP POLICY IF EXISTS "Users can view own data" ON users;

-- Consolidate into single policies (also fixes multiple_permissive_policies)
CREATE POLICY "Users can view own data" ON users
    FOR SELECT USING (auth.uid() = id);

CREATE POLICY "Users can update own data" ON users
    FOR UPDATE USING ((select auth.uid()) = id);

-- -----------------------------------------------------
-- TABLE: organizations
-- -----------------------------------------------------
DROP POLICY IF EXISTS "Members can view their organizations" ON organizations;
CREATE POLICY "Members can view their organizations" ON organizations
    FOR SELECT USING (
        id IN (
            SELECT organization_id 
            FROM organization_members 
            WHERE user_id = (select auth.uid())
        )
    );

-- -----------------------------------------------------
-- TABLE: organization_members
-- -----------------------------------------------------
DROP POLICY IF EXISTS "Users can view their own memberships" ON organization_members;
CREATE POLICY "Users can view their own memberships" ON organization_members
    FOR SELECT USING (user_id = (select auth.uid()));

-- -----------------------------------------------------
-- TABLE: knowledge_base_files
-- -----------------------------------------------------
DROP POLICY IF EXISTS "Users can view own org files" ON knowledge_base_files;
DROP POLICY IF EXISTS "Users can insert own org files" ON knowledge_base_files;
DROP POLICY IF EXISTS "Users can update own org files" ON knowledge_base_files;
DROP POLICY IF EXISTS "Users can delete own org files" ON knowledge_base_files;

CREATE POLICY "Users can view own org files" ON knowledge_base_files
    FOR SELECT USING (
        organization_id IN (
            SELECT organization_id 
            FROM organization_members 
            WHERE user_id = (select auth.uid())
        )
    );

CREATE POLICY "Users can insert own org files" ON knowledge_base_files
    FOR INSERT WITH CHECK (
        organization_id IN (
            SELECT organization_id 
            FROM organization_members 
            WHERE user_id = (select auth.uid())
        )
    );

CREATE POLICY "Users can update own org files" ON knowledge_base_files
    FOR UPDATE USING (
        organization_id IN (
            SELECT organization_id 
            FROM organization_members 
            WHERE user_id = (select auth.uid())
        )
    );

CREATE POLICY "Users can delete own org files" ON knowledge_base_files
    FOR DELETE USING (
        organization_id IN (
            SELECT organization_id 
            FROM organization_members 
            WHERE user_id = (select auth.uid())
        )
    );

-- -----------------------------------------------------
-- TABLE: knowledge_base_chunks
-- -----------------------------------------------------
DROP POLICY IF EXISTS "Users can view own org chunks" ON knowledge_base_chunks;
DROP POLICY IF EXISTS "Users can insert own org chunks" ON knowledge_base_chunks;
DROP POLICY IF EXISTS "Users can update own org chunks" ON knowledge_base_chunks;
DROP POLICY IF EXISTS "Users can delete own org chunks" ON knowledge_base_chunks;

CREATE POLICY "Users can view own org chunks" ON knowledge_base_chunks
    FOR SELECT USING (
        file_id IN (
            SELECT id FROM knowledge_base_files 
            WHERE organization_id IN (
                SELECT organization_id 
                FROM organization_members 
                WHERE user_id = (select auth.uid())
            )
        )
    );

CREATE POLICY "Users can insert own org chunks" ON knowledge_base_chunks
    FOR INSERT WITH CHECK (
        file_id IN (
            SELECT id FROM knowledge_base_files 
            WHERE organization_id IN (
                SELECT organization_id 
                FROM organization_members 
                WHERE user_id = (select auth.uid())
            )
        )
    );

CREATE POLICY "Users can update own org chunks" ON knowledge_base_chunks
    FOR UPDATE USING (
        file_id IN (
            SELECT id FROM knowledge_base_files 
            WHERE organization_id IN (
                SELECT organization_id 
                FROM organization_members 
                WHERE user_id = (select auth.uid())
            )
        )
    );

CREATE POLICY "Users can delete own org chunks" ON knowledge_base_chunks
    FOR DELETE USING (
        file_id IN (
            SELECT id FROM knowledge_base_files 
            WHERE organization_id IN (
                SELECT organization_id 
                FROM organization_members 
                WHERE user_id = (select auth.uid())
            )
        )
    );

-- -----------------------------------------------------
-- TABLE: sales_profiles
-- -----------------------------------------------------
DROP POLICY IF EXISTS "Users can view own profile" ON sales_profiles;
DROP POLICY IF EXISTS "Users can insert own profile" ON sales_profiles;
DROP POLICY IF EXISTS "Users can update own profile" ON sales_profiles;
DROP POLICY IF EXISTS "Users can delete own profile" ON sales_profiles;
DROP POLICY IF EXISTS "Admins can view org profiles" ON sales_profiles;

-- Consolidate view policies (also fixes multiple_permissive_policies)
CREATE POLICY "Users can view profiles" ON sales_profiles
    FOR SELECT USING (
        user_id = (select auth.uid())
        OR
        organization_id IN (
            SELECT organization_id 
            FROM organization_members 
            WHERE user_id = (select auth.uid()) AND role = 'admin'
        )
    );

CREATE POLICY "Users can insert own profile" ON sales_profiles
    FOR INSERT WITH CHECK (user_id = (select auth.uid()));

CREATE POLICY "Users can update own profile" ON sales_profiles
    FOR UPDATE USING (user_id = (select auth.uid()));

CREATE POLICY "Users can delete own profile" ON sales_profiles
    FOR DELETE USING (user_id = (select auth.uid()));

-- -----------------------------------------------------
-- TABLE: company_profiles
-- -----------------------------------------------------
DROP POLICY IF EXISTS "Org members can view company profile" ON company_profiles;
DROP POLICY IF EXISTS "Org admins can insert company profile" ON company_profiles;
DROP POLICY IF EXISTS "Org admins can update company profile" ON company_profiles;
DROP POLICY IF EXISTS "Org admins can delete company profile" ON company_profiles;

CREATE POLICY "Org members can view company profile" ON company_profiles
    FOR SELECT USING (
        organization_id IN (
            SELECT organization_id 
            FROM organization_members 
            WHERE user_id = (select auth.uid())
        )
    );

CREATE POLICY "Org admins can insert company profile" ON company_profiles
    FOR INSERT WITH CHECK (
        organization_id IN (
            SELECT organization_id 
            FROM organization_members 
            WHERE user_id = (select auth.uid()) AND role = 'admin'
        )
    );

CREATE POLICY "Org admins can update company profile" ON company_profiles
    FOR UPDATE USING (
        organization_id IN (
            SELECT organization_id 
            FROM organization_members 
            WHERE user_id = (select auth.uid()) AND role = 'admin'
        )
    );

CREATE POLICY "Org admins can delete company profile" ON company_profiles
    FOR DELETE USING (
        organization_id IN (
            SELECT organization_id 
            FROM organization_members 
            WHERE user_id = (select auth.uid()) AND role = 'admin'
        )
    );

-- -----------------------------------------------------
-- TABLE: profile_versions
-- -----------------------------------------------------
DROP POLICY IF EXISTS "Users can view own profile versions" ON profile_versions;
CREATE POLICY "Users can view own profile versions" ON profile_versions
    FOR SELECT USING (
        (profile_type = 'sales' AND profile_id IN (
            SELECT id FROM sales_profiles 
            WHERE user_id = (select auth.uid())
        ))
        OR
        (profile_type = 'company' AND profile_id IN (
            SELECT id FROM company_profiles 
            WHERE organization_id IN (
                SELECT organization_id 
                FROM organization_members 
                WHERE user_id = (select auth.uid())
            )
        ))
    );

-- -----------------------------------------------------
-- TABLE: research_briefs
-- -----------------------------------------------------
DROP POLICY IF EXISTS "Users can view own org research" ON research_briefs;
DROP POLICY IF EXISTS "Users can insert own org research" ON research_briefs;
DROP POLICY IF EXISTS "Users can update own org research" ON research_briefs;
DROP POLICY IF EXISTS "Users can delete own org research" ON research_briefs;

CREATE POLICY "Users can view own org research" ON research_briefs
    FOR SELECT USING (
        organization_id IN (
            SELECT organization_id 
            FROM organization_members 
            WHERE user_id = (select auth.uid())
        )
    );

CREATE POLICY "Users can insert own org research" ON research_briefs
    FOR INSERT WITH CHECK (
        organization_id IN (
            SELECT organization_id 
            FROM organization_members 
            WHERE user_id = (select auth.uid())
        )
    );

CREATE POLICY "Users can update own org research" ON research_briefs
    FOR UPDATE USING (
        organization_id IN (
            SELECT organization_id 
            FROM organization_members 
            WHERE user_id = (select auth.uid())
        )
    );

CREATE POLICY "Users can delete own org research" ON research_briefs
    FOR DELETE USING (
        organization_id IN (
            SELECT organization_id 
            FROM organization_members 
            WHERE user_id = (select auth.uid())
        )
    );

-- -----------------------------------------------------
-- TABLE: research_sources
-- -----------------------------------------------------
DROP POLICY IF EXISTS "Users can view own org research sources" ON research_sources;
DROP POLICY IF EXISTS "Users can insert research sources" ON research_sources;

CREATE POLICY "Users can view own org research sources" ON research_sources
    FOR SELECT USING (
        research_id IN (
            SELECT id FROM research_briefs 
            WHERE organization_id IN (
                SELECT organization_id 
                FROM organization_members 
                WHERE user_id = (select auth.uid())
            )
        )
    );

CREATE POLICY "Users can insert research sources" ON research_sources
    FOR INSERT WITH CHECK (
        research_id IN (
            SELECT id FROM research_briefs 
            WHERE organization_id IN (
                SELECT organization_id 
                FROM organization_members 
                WHERE user_id = (select auth.uid())
            )
        )
    );

