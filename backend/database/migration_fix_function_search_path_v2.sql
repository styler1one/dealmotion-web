-- ============================================================
-- Migration: Fix Function Search Path Warnings V2
-- Date: 23 December 2025
-- 
-- Fixes Supabase Advisor warnings for functions without search_path set
-- 
-- Functions affected:
-- - update_prospecting_feedback_type
-- - update_profile_chat_sessions_updated_at
-- - update_affiliate_updated_at
-- - generate_affiliate_code
-- - get_affiliate_stats
-- - process_affiliate_referral
-- - handle_new_user
-- ============================================================

-- ============================================================
-- 1. update_prospecting_feedback_type
-- ============================================================
CREATE OR REPLACE FUNCTION public.update_prospecting_feedback_type()
RETURNS TRIGGER
LANGUAGE plpgsql
SECURITY INVOKER
SET search_path = ''
AS $$
BEGIN
    IF NEW.imported_at IS NOT NULL AND OLD.imported_at IS NULL THEN
        NEW.feedback_type := 'imported';
    ELSIF NEW.rejected_at IS NOT NULL AND OLD.rejected_at IS NULL THEN
        NEW.feedback_type := 'rejected';
    END IF;
    RETURN NEW;
END;
$$;

-- ============================================================
-- 2. update_profile_chat_sessions_updated_at
-- ============================================================
CREATE OR REPLACE FUNCTION public.update_profile_chat_sessions_updated_at()
RETURNS TRIGGER
LANGUAGE plpgsql
SECURITY INVOKER
SET search_path = ''
AS $$
BEGIN
    NEW.updated_at = NOW();
    NEW.last_activity_at = NOW();
    RETURN NEW;
END;
$$;

-- ============================================================
-- 3. update_affiliate_updated_at
-- ============================================================
CREATE OR REPLACE FUNCTION public.update_affiliate_updated_at()
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
-- 4. generate_affiliate_code
-- ============================================================
CREATE OR REPLACE FUNCTION public.generate_affiliate_code(p_user_id UUID)
RETURNS TEXT
LANGUAGE plpgsql
SECURITY INVOKER
SET search_path = ''
AS $$
DECLARE
    v_code TEXT;
    v_exists BOOLEAN;
    v_attempts INTEGER := 0;
BEGIN
    -- Try to generate a unique code
    LOOP
        -- Generate a random alphanumeric code
        v_code := 'AFF_' || UPPER(SUBSTRING(MD5(RANDOM()::TEXT || p_user_id::TEXT) FROM 1 FOR 6));
        
        -- Check if it exists
        SELECT EXISTS(SELECT 1 FROM public.affiliates WHERE affiliate_code = v_code) INTO v_exists;
        
        -- Exit if unique or too many attempts
        v_attempts := v_attempts + 1;
        EXIT WHEN NOT v_exists OR v_attempts > 10;
    END LOOP;
    
    IF v_exists THEN
        -- Fallback: use user_id suffix
        v_code := 'AFF_' || UPPER(SUBSTRING(p_user_id::TEXT FROM 1 FOR 8));
    END IF;
    
    RETURN v_code;
END;
$$;

-- ============================================================
-- 5. get_affiliate_stats
-- ============================================================
CREATE OR REPLACE FUNCTION public.get_affiliate_stats(p_affiliate_id UUID)
RETURNS TABLE(
    total_clicks BIGINT,
    total_signups BIGINT,
    total_conversions BIGINT,
    conversion_rate DECIMAL,
    total_earned_cents BIGINT,
    total_paid_cents BIGINT,
    current_balance_cents BIGINT,
    pending_commissions_cents BIGINT,
    this_month_earned_cents BIGINT
)
LANGUAGE plpgsql
SECURITY INVOKER
SET search_path = ''
AS $$
BEGIN
    RETURN QUERY
    SELECT 
        a.total_clicks::BIGINT,
        a.total_signups::BIGINT,
        a.total_conversions::BIGINT,
        CASE WHEN a.total_signups > 0 
            THEN ROUND((a.total_conversions::DECIMAL / a.total_signups) * 100, 2)
            ELSE 0 
        END as conversion_rate,
        a.total_earned_cents::BIGINT,
        a.total_paid_cents::BIGINT,
        a.current_balance_cents::BIGINT,
        COALESCE((
            SELECT SUM(commission_amount_cents)::BIGINT 
            FROM public.affiliate_commissions 
            WHERE affiliate_id = p_affiliate_id AND status = 'pending'
        ), 0) as pending_commissions_cents,
        COALESCE((
            SELECT SUM(commission_amount_cents)::BIGINT 
            FROM public.affiliate_commissions 
            WHERE affiliate_id = p_affiliate_id 
            AND created_at >= DATE_TRUNC('month', NOW())
        ), 0) as this_month_earned_cents
    FROM public.affiliates a
    WHERE a.id = p_affiliate_id;
END;
$$;

-- ============================================================
-- 6. process_affiliate_referral
-- ============================================================
CREATE OR REPLACE FUNCTION public.process_affiliate_referral(
    p_user_id UUID,
    p_email TEXT,
    p_organization_id UUID,
    p_affiliate_code TEXT,
    p_click_id TEXT
)
RETURNS UUID
LANGUAGE plpgsql
SECURITY DEFINER
SET search_path = ''
AS $$
DECLARE
    v_affiliate_id UUID;
    v_click_uuid UUID;
    v_referral_id UUID;
BEGIN
    -- Skip if no affiliate code
    IF p_affiliate_code IS NULL OR p_affiliate_code = '' THEN
        RETURN NULL;
    END IF;
    
    -- Find the affiliate by code
    SELECT id INTO v_affiliate_id
    FROM public.affiliates
    WHERE affiliate_code = p_affiliate_code
    AND status = 'active';
    
    IF v_affiliate_id IS NULL THEN
        -- Invalid or inactive affiliate code
        RAISE WARNING 'Invalid affiliate code during signup: %', p_affiliate_code;
        RETURN NULL;
    END IF;
    
    -- Check for self-referral (user trying to refer themselves)
    IF EXISTS (SELECT 1 FROM public.affiliates WHERE id = v_affiliate_id AND user_id = p_user_id) THEN
        RAISE WARNING 'Self-referral blocked: %', p_user_id;
        RETURN NULL;
    END IF;
    
    -- Check if user was already referred
    IF EXISTS (SELECT 1 FROM public.affiliate_referrals WHERE referred_user_id = p_user_id) THEN
        RAISE WARNING 'User already referred: %', p_user_id;
        RETURN NULL;
    END IF;
    
    -- Find and update the click record if provided
    IF p_click_id IS NOT NULL AND p_click_id != '' THEN
        SELECT id INTO v_click_uuid
        FROM public.affiliate_clicks
        WHERE click_id = p_click_id
        AND affiliate_id = v_affiliate_id
        AND converted_to_signup = FALSE;
        
        IF v_click_uuid IS NOT NULL THEN
            -- Mark click as converted
            UPDATE public.affiliate_clicks
            SET converted_to_signup = TRUE,
                signup_user_id = p_user_id,
                converted_at = NOW()
            WHERE id = v_click_uuid;
        END IF;
    END IF;
    
    -- Create the referral record
    INSERT INTO public.affiliate_referrals (
        affiliate_id,
        click_id,
        referred_user_id,
        referred_organization_id,
        referred_email,
        signup_at
    )
    VALUES (
        v_affiliate_id,
        v_click_uuid,
        p_user_id,
        p_organization_id,
        p_email,
        NOW()
    )
    RETURNING id INTO v_referral_id;
    
    -- Update affiliate signup count
    UPDATE public.affiliates
    SET total_signups = total_signups + 1,
        updated_at = NOW()
    WHERE id = v_affiliate_id;
    
    -- Update users table with referral info
    UPDATE public.users
    SET referred_by_affiliate_id = v_affiliate_id,
        referral_source = 'affiliate_' || p_affiliate_code
    WHERE id = p_user_id;
    
    RETURN v_referral_id;
END;
$$;

-- ============================================================
-- 7. handle_new_user (auto-create organization on signup)
-- ============================================================
CREATE OR REPLACE FUNCTION public.handle_new_user()
RETURNS TRIGGER
LANGUAGE plpgsql
SECURITY DEFINER
SET search_path = ''
AS $$
DECLARE
  new_org_id UUID;
  free_plan_id TEXT := 'free';
  v_affiliate_code TEXT;
  v_click_id TEXT;
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
  
  -- Process affiliate referral if code was provided in raw_user_meta_data
  v_affiliate_code := NEW.raw_user_meta_data->>'affiliate_code';
  v_click_id := NEW.raw_user_meta_data->>'affiliate_click_id';
  
  IF v_affiliate_code IS NOT NULL AND v_affiliate_code != '' THEN
    PERFORM public.process_affiliate_referral(
      NEW.id,
      NEW.email,
      new_org_id,
      v_affiliate_code,
      v_click_id
    );
  END IF;
  
  RETURN NEW;
END;
$$;

-- ============================================================
-- DONE
-- ============================================================
-- After running, check Supabase Advisor again.
-- The function_search_path_mutable warnings should be gone.
--
-- For auth_leaked_password_protection warning:
-- Go to Supabase Dashboard > Authentication > Providers > Email
-- Enable "Leaked password protection"
-- ============================================================
