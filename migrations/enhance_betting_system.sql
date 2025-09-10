-- Migration to enhance betting system with proper budget tracking, lock times, and odds snapshotting
-- Run this migration to add the necessary fields for improved betting flow

-- Add new columns to bets table
ALTER TABLE bets ADD COLUMN locked_at TIMESTAMP NULL;
ALTER TABLE bets ADD COLUMN odds_snapshot_decimal DECIMAL(10,3) NULL;
ALTER TABLE bets ADD COLUMN odds_snapshot_american INTEGER NULL;
ALTER TABLE bets ADD COLUMN bookmaker_snapshot VARCHAR(50) NULL;
ALTER TABLE bets ADD COLUMN week INTEGER NULL;

-- Add new columns to betting_options table for better tracking
ALTER TABLE betting_options ADD COLUMN is_locked BOOLEAN DEFAULT FALSE;
ALTER TABLE betting_options ADD COLUMN locked_at TIMESTAMP NULL;

-- Create index for better performance
CREATE INDEX idx_bets_user_week ON bets(user_id, week);
CREATE INDEX idx_bets_locked_at ON bets(locked_at);
CREATE INDEX idx_betting_options_locked ON betting_options(is_locked);

-- Update existing bets to have week information (this will need to be populated based on matchup data)
-- For now, we'll set a default week - this should be updated based on your data
UPDATE bets SET week = 1 WHERE week IS NULL;

-- Add constraint to ensure week is not null for new bets
ALTER TABLE bets ALTER COLUMN week SET NOT NULL;
