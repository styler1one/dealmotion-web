-- ============================================================
-- Migration: Affiliate Referral Trigger FIX
-- Version: 1.1
-- Date: 24 December 2024
-- 
-- FIX: Add public schema prefix to function calls
-- ============================================================

-- ============================================================
-- 1. RECREATE: process_affiliate_referral in public schema
-- ============================================================

CREATE OR REPLACE FUNCTION public.process_affiliate_referral(
    p_user_id UUID,
    p_email TEXT,
    p_organization_id UUID,
    p_affiliate_code TEXT,
    p_click_id TEXT
)
RETURNS UUID AS $$
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
    ) VALUES (
        v_affiliate_id,
        v_click_uuid,
        p_user_id,
        p_organization_id,
        p_email,
        NOW()
    )
    RETURNING id INTO v_referral_id;
    
    -- Update affiliate stats
    UPDATE public.affiliates
    SET total_signups = COALESCE(total_signups, 0) + 1
    WHERE id = v_affiliate_id;
    
    -- Update user record with affiliate reference (if columns exist)
    BEGIN
        UPDATE public.users
        SET referred_by_affiliate_id = v_affiliate_id,
            referral_click_id = p_click_id
        WHERE id = p_user_id;
    EXCEPTION WHEN undefined_column THEN
        -- Columns don't exist yet, skip
        NULL;
    END;
    
    -- Log event
    INSERT INTO public.affiliate_events (
        affiliate_id,
        event_type,
        event_data,
        actor_type
    ) VALUES (
        v_affiliate_id,
        'referral_signup',
        jsonb_build_object(
            'referral_id', v_referral_id,
            'referred_email', p_email,
            'had_click', v_click_uuid IS NOT NULL
        ),
        'system'
    );
    
    RETURN v_referral_id;
    
EXCEPTION WHEN OTHERS THEN
    -- Log error but don't fail the signup
    RAISE WARNING 'Error processing affiliate referral: %', SQLERRM;
    RETURN NULL;
END;
$$ LANGUAGE plpgsql SECURITY DEFINER;


-- ============================================================
-- 2. UPDATE: handle_new_user with public schema prefix
-- ============================================================

CREATE OR REPLACE FUNCTION public.handle_new_user()
RETURNS TRIGGER AS $$
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
    
    -- Create user record
    INSERT INTO public.users (id, email, full_name)
    VALUES (
        NEW.id, 
        NEW.email, 
        COALESCE(
            NEW.raw_user_meta_data->>'full_name',
            NEW.raw_user_meta_data->>'name',
            split_part(NEW.email, '@', 1)
        )
    )
    ON CONFLICT (id) DO UPDATE SET
        email = EXCLUDED.email,
        full_name = COALESCE(EXCLUDED.full_name, public.users.full_name);
    
    -- Add user as owner
    INSERT INTO public.organization_members (organization_id, user_id, role)
    VALUES (new_org_id, NEW.id, 'owner');
    
    -- Create free subscription
    INSERT INTO public.organization_subscriptions (organization_id, plan_id, status)
    VALUES (new_org_id, free_plan_id, 'active');
    
    -- Create user settings
    INSERT INTO public.user_settings (user_id)
    VALUES (NEW.id)
    ON CONFLICT (user_id) DO NOTHING;
    
    -- =========================================================
    -- AFFILIATE REFERRAL PROCESSING
    -- =========================================================
    -- Extract affiliate data from user metadata (passed during signup)
    v_affiliate_code := NEW.raw_user_meta_data->>'affiliate_code';
    v_click_id := NEW.raw_user_meta_data->>'affiliate_click_id';
    
    -- Process affiliate referral if code is present
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
$$ LANGUAGE plpgsql SECURITY DEFINER;


-- ============================================================
-- VERIFICATION: Test that signup works
-- ============================================================
-- This should NOT fail:
-- SELECT public.process_affiliate_referral(
--     gen_random_uuid(), 
--     'test@test.com', 
--     gen_random_uuid(), 
--     'NONEXISTENT_CODE', 
--     NULL
-- );
-- Should return NULL without error

