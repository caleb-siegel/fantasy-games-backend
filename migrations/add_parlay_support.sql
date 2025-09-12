-- Migration: Add Parlay Bet Support
-- This migration adds tables and columns to support parlay betting functionality

-- Create parlay_bets table to store parlay bet information
CREATE TABLE IF NOT EXISTS parlay_bets (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER NOT NULL,
    matchup_id INTEGER NOT NULL,
    amount DECIMAL(10,2) NOT NULL,
    potential_payout DECIMAL(10,2) NOT NULL,
    decimal_odds DECIMAL(10,4) NOT NULL,
    status VARCHAR(20) DEFAULT 'pending', -- pending, locked, won, lost, cancelled
    week INTEGER NOT NULL,
    locked_at DATETIME NULL,
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    
    FOREIGN KEY (user_id) REFERENCES users(id),
    FOREIGN KEY (matchup_id) REFERENCES matchups(id)
);

-- Create parlay_legs table to store individual legs of parlay bets
CREATE TABLE IF NOT EXISTS parlay_legs (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    parlay_bet_id INTEGER NOT NULL,
    betting_option_id INTEGER NOT NULL,
    leg_number INTEGER NOT NULL,
    american_odds INTEGER NOT NULL,
    decimal_odds DECIMAL(10,4) NOT NULL,
    outcome_name VARCHAR(100) NOT NULL,
    outcome_point DECIMAL(10,2) NULL,
    market_type VARCHAR(20) NOT NULL,
    bookmaker VARCHAR(50) NOT NULL,
    game_id VARCHAR(50) NOT NULL,
    result VARCHAR(20) NULL, -- won, lost, pending, void
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    
    FOREIGN KEY (parlay_bet_id) REFERENCES parlay_bets(id) ON DELETE CASCADE,
    FOREIGN KEY (betting_option_id) REFERENCES betting_options(id)
);

-- Add indexes for better performance
CREATE INDEX IF NOT EXISTS idx_parlay_bets_user_id ON parlay_bets(user_id);
CREATE INDEX IF NOT EXISTS idx_parlay_bets_matchup_id ON parlay_bets(matchup_id);
CREATE INDEX IF NOT EXISTS idx_parlay_bets_week ON parlay_bets(week);
CREATE INDEX IF NOT EXISTS idx_parlay_bets_status ON parlay_bets(status);
CREATE INDEX IF NOT EXISTS idx_parlay_legs_parlay_bet_id ON parlay_legs(parlay_bet_id);
CREATE INDEX IF NOT EXISTS idx_parlay_legs_betting_option_id ON parlay_legs(betting_option_id);

-- Add a column to the existing bets table to track if it's part of a parlay
ALTER TABLE bets ADD COLUMN parlay_bet_id INTEGER NULL;
ALTER TABLE bets ADD COLUMN is_parlay_leg BOOLEAN DEFAULT FALSE;

-- Add foreign key constraint for parlay_bet_id
-- Note: This might fail if there are existing bets, but that's okay for new installations
-- ALTER TABLE bets ADD CONSTRAINT fk_bets_parlay_bet_id FOREIGN KEY (parlay_bet_id) REFERENCES parlay_bets(id);
