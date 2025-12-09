-- Migration: Auto-create organization for new users
-- Created: 3 December 2025
-- 
-- PROBLEM: New users get "User not in any organization" error
-- SOLUTION: Automatically create an organization when a user signs up
--
-- Run this migration in Supabase SQL Editor

-- ============================================
-- 1. ENSURE public.users TABLE EXISTS AND IS SYNCED
-- ============================================

-- Some Supabase setups have a public.users table that syncs with auth.users
-- The organization_members FK may reference this table

-- First, create public.users table if it doesn't exist
CREATE TABLE IF NOT EXISTS public.users (
    id UUID PRIMARY KEY REFERENCES auth.users(id) ON DELETE CASCADE,
    email TEXT,
    created_at TIMESTAMPTZ DEFAULT NOW()
);

-- Sync ALL existing auth.users to public.users (this fixes the FK issue)
INSERT INTO public.users (id, email, created_at)
SELECT id, email, created_at
FROM auth.users
ON CONFLICT (id) DO UPDATE SET email = EXCLUDED.email;

-- ============================================
-- 2. FUNCTION: Create organization for new user
-- ============================================

CREATE OR REPLACE FUNCTION public.handle_new_user()
RETURNS TRIGGER AS $$
DECLARE
    new_org_id UUID;
    user_email TEXT;
    org_name TEXT;
BEGIN
    -- Get user email for org name
    user_email := NEW.email;
    
    -- First, ensure user exists in public.users (for FK compatibility)
    INSERT INTO public.users (id, email, created_at)
    VALUES (NEW.id, NEW.email, NEW.created_at)
    ON CONFLICT (id) DO UPDATE SET email = NEW.email;
    
    -- Generate organization name from email (use part before @)
    org_name := COALESCE(
        SPLIT_PART(user_email, '@', 1) || '''s Workspace',
        'My Workspace'
    );
    
    -- Create a new organization for this user
    INSERT INTO public.organizations (name, slug)
    VALUES (
        org_name,
        -- Generate unique slug from user ID
        'org-' || SUBSTR(NEW.id::TEXT, 1, 8)
    )
    RETURNING id INTO new_org_id;
    
    -- Add user as owner of the organization
    INSERT INTO public.organization_members (organization_id, user_id, role)
    VALUES (new_org_id, NEW.id, 'owner');
    
    -- Create a FREE subscription for the organization
    INSERT INTO public.organization_subscriptions (organization_id, plan_id, status)
    VALUES (new_org_id, 'free', 'active')
    ON CONFLICT (organization_id) DO NOTHING;
    
    RETURN NEW;
EXCEPTION
    WHEN OTHERS THEN
        -- Log error but don't fail user creation
        RAISE WARNING 'Error in handle_new_user: %', SQLERRM;
        RETURN NEW;
END;
$$ LANGUAGE plpgsql SECURITY DEFINER;

-- ============================================
-- 3. TRIGGERS: Auto-create org on user signup
-- ============================================

-- Drop existing triggers if they exist
DROP TRIGGER IF EXISTS on_auth_user_created ON auth.users;
DROP TRIGGER IF EXISTS sync_auth_user_to_public ON auth.users;

-- Create trigger for new user organization
CREATE TRIGGER on_auth_user_created
    AFTER INSERT ON auth.users
    FOR EACH ROW
    EXECUTE FUNCTION public.handle_new_user();

-- ============================================
-- 4. FIX EXISTING USERS WITHOUT ORGANIZATION
-- ============================================

-- Create organizations for existing users who don't have one
DO $$
DECLARE
    user_record RECORD;
    new_org_id UUID;
    org_name TEXT;
BEGIN
    -- Find all users without an organization
    -- Use public.users to ensure FK compatibility
    FOR user_record IN 
        SELECT u.id, u.email
        FROM public.users u
        LEFT JOIN public.organization_members om ON om.user_id = u.id
        WHERE om.id IS NULL
    LOOP
        -- Generate organization name
        org_name := COALESCE(
            SPLIT_PART(user_record.email, '@', 1) || '''s Workspace',
            'My Workspace'
        );
        
        -- Create organization
        INSERT INTO public.organizations (name, slug)
        VALUES (
            org_name,
            'org-' || SUBSTR(user_record.id::TEXT, 1, 8)
        )
        RETURNING id INTO new_org_id;
        
        -- Add user as owner
        INSERT INTO public.organization_members (organization_id, user_id, role)
        VALUES (new_org_id, user_record.id, 'owner');
        
        -- Create FREE subscription
        INSERT INTO public.organization_subscriptions (organization_id, plan_id, status)
        VALUES (new_org_id, 'free', 'active')
        ON CONFLICT (organization_id) DO NOTHING;
        
        RAISE NOTICE 'Created organization for user: %', user_record.email;
    END LOOP;
END $$;

-- ============================================
-- 5. VERIFY THE FIX
-- ============================================

-- Check that all users now have an organization
-- SELECT 
--     au.email,
--     o.name as org_name,
--     om.role
-- FROM auth.users au
-- LEFT JOIN public.organization_members om ON om.user_id = au.id
-- LEFT JOIN public.organizations o ON o.id = om.organization_id
-- ORDER BY au.created_at DESC;

-- ============================================
-- DONE!
-- ============================================
-- After running this migration:
-- 1. All existing users will have an organization
-- 2. All new users will automatically get an organization
-- 3. All organizations will have a FREE subscription
