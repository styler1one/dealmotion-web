-- Fix activity triggers to include organization_id
-- The prospect_activities table requires organization_id (NOT NULL)
-- But the triggers were not including it in the INSERT

-- Fix log_followup_activity trigger
CREATE OR REPLACE FUNCTION log_followup_activity()
RETURNS TRIGGER AS $$
BEGIN
    INSERT INTO public.prospect_activities (
        prospect_id,
        organization_id,
        activity_type,
        title,
        description,
        metadata
    )
    SELECT 
        NEW.prospect_id,
        NEW.organization_id,
        'followup_created',
        'Follow-up Brief',
        'Status: ' || NEW.status,
        jsonb_build_object('followup_id', NEW.id, 'status', NEW.status)
    WHERE NEW.prospect_id IS NOT NULL AND NEW.organization_id IS NOT NULL;
    RETURN NEW;
END;
$$ LANGUAGE plpgsql SET search_path = '';

-- Fix log_research_activity trigger
CREATE OR REPLACE FUNCTION log_research_activity()
RETURNS TRIGGER AS $$
BEGIN
    INSERT INTO public.prospect_activities (
        prospect_id,
        organization_id,
        activity_type,
        title,
        description,
        metadata
    )
    SELECT 
        NEW.prospect_id,
        NEW.organization_id,
        'research_completed',
        'Research Brief',
        'Status: ' || NEW.status,
        jsonb_build_object('research_id', NEW.id, 'status', NEW.status)
    WHERE NEW.prospect_id IS NOT NULL AND NEW.organization_id IS NOT NULL;
    RETURN NEW;
END;
$$ LANGUAGE plpgsql SET search_path = '';

-- Fix log_prep_activity trigger (if it exists)
CREATE OR REPLACE FUNCTION log_prep_activity()
RETURNS TRIGGER AS $$
BEGIN
    INSERT INTO public.prospect_activities (
        prospect_id,
        organization_id,
        activity_type,
        title,
        description,
        metadata
    )
    SELECT 
        NEW.prospect_id,
        NEW.organization_id,
        'prep_created',
        'Meeting Preparation',
        'Status: ' || NEW.status,
        jsonb_build_object('prep_id', NEW.id, 'status', NEW.status)
    WHERE NEW.prospect_id IS NOT NULL AND NEW.organization_id IS NOT NULL;
    RETURN NEW;
END;
$$ LANGUAGE plpgsql SET search_path = '';

