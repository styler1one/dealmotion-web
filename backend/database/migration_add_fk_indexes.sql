-- =====================================================
-- ADD INDEXES FOR UNINDEXED FOREIGN KEYS
-- =====================================================
-- These indexes speed up JOINs and lookups on foreign key columns

-- coach_behavior_events.organization_id
CREATE INDEX IF NOT EXISTS idx_coach_behavior_events_org 
    ON coach_behavior_events(organization_id);

-- coach_suggestions.organization_id
CREATE INDEX IF NOT EXISTS idx_coach_suggestions_org 
    ON coach_suggestions(organization_id);

-- coach_user_patterns.organization_id
CREATE INDEX IF NOT EXISTS idx_coach_user_patterns_org 
    ON coach_user_patterns(organization_id);

-- deals.created_by
CREATE INDEX IF NOT EXISTS idx_deals_created_by 
    ON deals(created_by);

-- followup_actions.organization_id
CREATE INDEX IF NOT EXISTS idx_followup_actions_org 
    ON followup_actions(organization_id);

-- icps.org_id
CREATE INDEX IF NOT EXISTS idx_icps_org 
    ON icps(org_id);

-- icps.product_id
CREATE INDEX IF NOT EXISTS idx_icps_product 
    ON icps(product_id);

-- meetings.created_by
CREATE INDEX IF NOT EXISTS idx_meetings_created_by 
    ON meetings(created_by);

-- organization_subscriptions.plan_id
CREATE INDEX IF NOT EXISTS idx_org_subs_plan 
    ON organization_subscriptions(plan_id);

-- personas.icp_id
CREATE INDEX IF NOT EXISTS idx_personas_icp 
    ON personas(icp_id);

-- personas.org_id
CREATE INDEX IF NOT EXISTS idx_personas_org 
    ON personas(org_id);

-- products.org_id
CREATE INDEX IF NOT EXISTS idx_products_org 
    ON products(org_id);

-- prospect_activities.created_by
CREATE INDEX IF NOT EXISTS idx_prospect_activities_created_by 
    ON prospect_activities(created_by);

-- =====================================================
-- Done! All foreign keys now have covering indexes.
-- =====================================================

