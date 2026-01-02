-- ============================================================
-- MIGRATION: Admin User Suspend Feature
-- Date: January 2026
-- 
-- Adds columns to support user account suspension from admin panel
-- ============================================================

-- Add suspension columns to users table
ALTER TABLE users ADD COLUMN IF NOT EXISTS is_suspended BOOLEAN DEFAULT false;
ALTER TABLE users ADD COLUMN IF NOT EXISTS suspended_at TIMESTAMP WITH TIME ZONE;
ALTER TABLE users ADD COLUMN IF NOT EXISTS suspended_reason TEXT;

-- Add index for finding suspended users
CREATE INDEX IF NOT EXISTS idx_users_suspended ON users(is_suspended) WHERE is_suspended = true;

-- Comment for documentation
COMMENT ON COLUMN users.is_suspended IS 'Whether the user account is suspended (cannot login)';
COMMENT ON COLUMN users.suspended_at IS 'When the account was suspended';
COMMENT ON COLUMN users.suspended_reason IS 'Admin reason for suspension';

