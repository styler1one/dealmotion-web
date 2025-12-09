-- Migration: Security Advisor Fixes
-- Date: 5 December 2025
-- 
-- Fixes:
-- 1. RLS disabled on flow_pack_products (ERROR)
-- 2. Function search_path mutable (WARN) - 8 functions
-- 3. Leaked password protection - manual in Auth settings

-- ============================================
-- 1. FIX: Enable RLS on flow_pack_products
-- ============================================

ALTER TABLE flow_pack_products ENABLE ROW LEVEL SECURITY;

-- Everyone can read flow pack products (public pricing info)
CREATE POLICY "flow_pack_products_select" ON flow_pack_products
    FOR SELECT
    TO authenticated, anon
    USING (is_active = true);

-- Only service role can manage (backend)
-- No policy needed - service role bypasses RLS

-- ============================================
-- 2. FIX: Function search_path mutable
-- Recreate functions with SET search_path = ''
-- ============================================

-- Drop existing functions first
DROP FUNCTION IF EXISTS public.get_flow_pack_balance(UUID);
DROP FUNCTION IF EXISTS public.consume_flow_pack(UUID, INTEGER);
DROP FUNCTION IF EXISTS public.get_style_guide_with_defaults(UUID);
DROP FUNCTION IF EXISTS public.cleanup_old_coach_tips();
DROP FUNCTION IF EXISTS public.increment_flow(UUID);
DROP FUNCTION IF EXISTS public.check_flow_limit(UUID);
DROP FUNCTION IF EXISTS public.check_usage_limit(UUID, TEXT);
-- Note: handle_new_user is a trigger function, need to drop trigger first
DROP TRIGGER IF EXISTS on_auth_user_created ON auth.users;
DROP FUNCTION IF EXISTS public.handle_new_user();

-- 2.1 get_flow_pack_balance
CREATE OR REPLACE FUNCTION public.get_flow_pack_balance(p_organization_id UUID)
RETURNS INTEGER
LANGUAGE plpgsql
SECURITY DEFINER
SET search_path = ''
AS $$
DECLARE
  v_balance INTEGER;
BEGIN
  SELECT COALESCE(SUM(flows_remaining), 0) INTO v_balance
  FROM public.flow_packs
  WHERE organization_id = p_organization_id
    AND status = 'active'
    AND (expires_at IS NULL OR expires_at > NOW());
  
  RETURN v_balance;
END;
$$;

-- 2.2 consume_flow_pack
CREATE OR REPLACE FUNCTION public.consume_flow_pack(p_organization_id UUID, p_amount INTEGER DEFAULT 1)
RETURNS BOOLEAN
LANGUAGE plpgsql
SECURITY DEFINER
SET search_path = ''
AS $$
DECLARE
  v_pack RECORD;
  v_remaining INTEGER;
BEGIN
  v_remaining := p_amount;
  
  FOR v_pack IN 
    SELECT id, flows_remaining
    FROM public.flow_packs
    WHERE organization_id = p_organization_id
      AND status = 'active'
      AND flows_remaining > 0
      AND (expires_at IS NULL OR expires_at > NOW())
    ORDER BY purchased_at ASC
  LOOP
    IF v_remaining <= 0 THEN
      EXIT;
    END IF;
    
    IF v_pack.flows_remaining >= v_remaining THEN
      UPDATE public.flow_packs SET
        flows_remaining = flows_remaining - v_remaining,
        updated_at = NOW(),
        status = CASE WHEN flows_remaining - v_remaining = 0 THEN 'depleted' ELSE 'active' END,
        depleted_at = CASE WHEN flows_remaining - v_remaining = 0 THEN NOW() ELSE NULL END
      WHERE id = v_pack.id;
      
      v_remaining := 0;
    ELSE
      v_remaining := v_remaining - v_pack.flows_remaining;
      
      UPDATE public.flow_packs SET
        flows_remaining = 0,
        status = 'depleted',
        depleted_at = NOW(),
        updated_at = NOW()
      WHERE id = v_pack.id;
    END IF;
  END LOOP;
  
  RETURN v_remaining = 0;
END;
$$;

-- 2.3 get_style_guide_with_defaults
CREATE OR REPLACE FUNCTION public.get_style_guide_with_defaults(p_user_id UUID)
RETURNS JSONB
LANGUAGE plpgsql
SECURITY DEFINER
SET search_path = ''
AS $$
DECLARE
  v_style_guide JSONB;
  v_defaults JSONB;
BEGIN
  v_defaults := jsonb_build_object(
    'tone', 'professional',
    'formality', 'formal',
    'language_style', 'business',
    'persuasion_style', 'balanced',
    'emoji_usage', false,
    'signoff', 'Best regards',
    'writing_length', 'concise'
  );
  
  SELECT COALESCE(style_guide, '{}'::jsonb) INTO v_style_guide
  FROM public.sales_profiles
  WHERE user_id = p_user_id
  LIMIT 1;
  
  IF v_style_guide IS NULL THEN
    RETURN v_defaults;
  END IF;
  
  RETURN v_defaults || v_style_guide;
END;
$$;

-- 2.4 cleanup_old_coach_tips
CREATE OR REPLACE FUNCTION public.cleanup_old_coach_tips()
RETURNS INTEGER
LANGUAGE plpgsql
SECURITY DEFINER
SET search_path = ''
AS $$
DECLARE
  v_deleted INTEGER;
BEGIN
  DELETE FROM public.coach_daily_tips
  WHERE tip_date < CURRENT_DATE - INTERVAL '7 days';
  
  GET DIAGNOSTICS v_deleted = ROW_COUNT;
  RETURN v_deleted;
END;
$$;

-- 2.5 increment_flow
CREATE OR REPLACE FUNCTION public.increment_flow(p_organization_id UUID)
RETURNS BOOLEAN
LANGUAGE plpgsql
SECURITY DEFINER
SET search_path = ''
AS $$
DECLARE
  v_current_month TEXT;
BEGIN
  v_current_month := TO_CHAR(CURRENT_DATE, 'YYYY-MM');
  
  INSERT INTO public.usage_records (organization_id, month, flow_count)
  VALUES (p_organization_id, v_current_month, 1)
  ON CONFLICT (organization_id, month)
  DO UPDATE SET 
    flow_count = public.usage_records.flow_count + 1,
    updated_at = NOW();
  
  RETURN TRUE;
END;
$$;

-- 2.6 check_flow_limit
CREATE OR REPLACE FUNCTION public.check_flow_limit(p_organization_id UUID)
RETURNS BOOLEAN
LANGUAGE plpgsql
SECURITY DEFINER
SET search_path = ''
AS $$
DECLARE
  v_plan_id TEXT;
  v_flow_limit INTEGER;
  v_current_flow_count INTEGER;
  v_current_month TEXT;
BEGIN
  v_current_month := TO_CHAR(CURRENT_DATE, 'YYYY-MM');
  
  -- Get current plan
  SELECT os.plan_id INTO v_plan_id
  FROM public.organization_subscriptions os
  WHERE os.organization_id = p_organization_id
    AND os.status = 'active'
  LIMIT 1;
  
  IF v_plan_id IS NULL THEN
    v_plan_id := 'free';
  END IF;
  
  -- Get flow limit
  SELECT (sp.features->>'flow_limit')::INTEGER INTO v_flow_limit
  FROM public.subscription_plans sp
  WHERE sp.id = v_plan_id;
  
  IF v_flow_limit IS NULL OR v_flow_limit = -1 THEN
    RETURN TRUE; -- Unlimited
  END IF;
  
  -- Get current usage
  SELECT COALESCE(flow_count, 0) INTO v_current_flow_count
  FROM public.usage_records
  WHERE organization_id = p_organization_id
    AND month = v_current_month;
  
  RETURN COALESCE(v_current_flow_count, 0) < v_flow_limit;
END;
$$;

-- 2.7 check_usage_limit
CREATE OR REPLACE FUNCTION public.check_usage_limit(
  p_organization_id UUID,
  p_usage_type TEXT
)
RETURNS BOOLEAN
LANGUAGE plpgsql
SECURITY DEFINER
SET search_path = ''
AS $$
DECLARE
  v_plan_id TEXT;
  v_limit INTEGER;
  v_current_count INTEGER;
  v_current_month TEXT;
BEGIN
  v_current_month := TO_CHAR(CURRENT_DATE, 'YYYY-MM');
  
  -- Get current plan
  SELECT os.plan_id INTO v_plan_id
  FROM public.organization_subscriptions os
  WHERE os.organization_id = p_organization_id
    AND os.status = 'active'
  LIMIT 1;
  
  IF v_plan_id IS NULL THEN
    v_plan_id := 'free';
  END IF;
  
  -- Get limit for usage type
  SELECT (sp.features->>p_usage_type)::INTEGER INTO v_limit
  FROM public.subscription_plans sp
  WHERE sp.id = v_plan_id;
  
  IF v_limit IS NULL OR v_limit = -1 THEN
    RETURN TRUE; -- Unlimited
  END IF;
  
  -- Get current usage
  SELECT COALESCE(
    CASE p_usage_type
      WHEN 'research_limit' THEN research_count
      WHEN 'prep_limit' THEN prep_count
      WHEN 'followup_limit' THEN followup_count
      WHEN 'flow_limit' THEN flow_count
      ELSE 0
    END, 0
  ) INTO v_current_count
  FROM public.usage_records
  WHERE organization_id = p_organization_id
    AND month = v_current_month;
  
  RETURN COALESCE(v_current_count, 0) < v_limit;
END;
$$;

-- 2.8 handle_new_user
CREATE OR REPLACE FUNCTION public.handle_new_user()
RETURNS TRIGGER
LANGUAGE plpgsql
SECURITY DEFINER
SET search_path = ''
AS $$
DECLARE
  v_org_id UUID;
BEGIN
  -- Create organization for new user
  INSERT INTO public.organizations (name)
  VALUES (COALESCE(NEW.raw_user_meta_data->>'full_name', NEW.email))
  RETURNING id INTO v_org_id;
  
  -- Add user to organization
  INSERT INTO public.organization_members (organization_id, user_id, role)
  VALUES (v_org_id, NEW.id, 'owner');
  
  -- Create free subscription
  INSERT INTO public.organization_subscriptions (organization_id, plan_id, status)
  VALUES (v_org_id, 'free', 'active');
  
  -- Sync to public.users
  INSERT INTO public.users (id, email)
  VALUES (NEW.id, NEW.email)
  ON CONFLICT (id) DO UPDATE SET email = NEW.email;
  
  RETURN NEW;
END;
$$;

-- Recreate the trigger
CREATE TRIGGER on_auth_user_created
  AFTER INSERT ON auth.users
  FOR EACH ROW
  EXECUTE FUNCTION public.handle_new_user();

-- ============================================
-- VERIFICATION
-- ============================================

DO $$
BEGIN
    RAISE NOTICE 'Security Fix Migration Complete';
    RAISE NOTICE '- flow_pack_products: RLS enabled';
    RAISE NOTICE '- 8 functions updated with SET search_path = ''''';
    RAISE NOTICE '';
    RAISE NOTICE 'MANUAL ACTION REQUIRED:';
    RAISE NOTICE '- Enable "Leaked Password Protection" in Supabase Auth settings';
END $$;

