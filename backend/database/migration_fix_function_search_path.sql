-- ============================================================
-- Migration: Fix Function Search Path Warnings
-- Date: 19 December 2025
-- 
-- Fixes 3 Supabase SQL Linter warnings:
-- function_search_path_mutable: Functions without search_path set
-- 
-- Functions affected:
-- - update_autopilot_updated_at
-- - update_updated_at_column  
-- - handle_new_user
-- ============================================================

-- ============================================================
-- 1. UPDATE_AUTOPILOT_UPDATED_AT
-- ============================================================
CREATE OR REPLACE FUNCTION public.update_autopilot_updated_at()
RETURNS TRIGGER
LANGUAGE plpgsql
SECURITY INVOKER
SET search_path = ''
AS $$
BEGIN
    NEW.updated_at = NOW();
    RETURN NEW;
END;
$$;

-- ============================================================
-- 2. UPDATE_UPDATED_AT_COLUMN
-- ============================================================
CREATE OR REPLACE FUNCTION public.update_updated_at_column()
RETURNS TRIGGER
LANGUAGE plpgsql
SECURITY INVOKER
SET search_path = ''
AS $$
BEGIN
    NEW.updated_at = NOW();
    RETURN NEW;
END;
$$;

-- ============================================================
-- 3. HANDLE_NEW_USER (auto-create organization on signup)
-- ============================================================
CREATE OR REPLACE FUNCTION public.handle_new_user()
RETURNS TRIGGER AS $$
DECLARE
  new_org_id UUID;
  free_plan_id TEXT := 'free';
BEGIN
  -- Create personal organization
  INSERT INTO public.organizations (name, slug)
  VALUES (
    'Personal - ' || COALESCE(NEW.email, NEW.id::TEXT),
    'personal-' || NEW.id::TEXT
  )
  RETURNING id INTO new_org_id;
  
  -- Add user as owner
  INSERT INTO public.organization_members (organization_id, user_id, role)
  VALUES (new_org_id, NEW.id, 'owner');
  
  -- Create free subscription
  INSERT INTO public.organization_subscriptions (organization_id, plan_id, status)
  VALUES (new_org_id, free_plan_id, 'active');
  
  -- Create initial usage record
  INSERT INTO public.usage_records (organization_id, period_start, period_end)
  VALUES (new_org_id, date_trunc('month', NOW()), date_trunc('month', NOW()) + INTERVAL '1 month');
  
  RETURN NEW;
END;
$$ LANGUAGE plpgsql SECURITY DEFINER SET search_path = '';

-- ============================================================
-- DONE
-- ============================================================
-- After running, check Supabase Linter again.
-- The 3 function_search_path_mutable warnings should be gone.
--
-- For the last warning (auth_leaked_password_protection):
-- Go to Supabase Dashboard > Authentication > Providers > Password
-- Enable "Leaked password protection"
-- ============================================================
