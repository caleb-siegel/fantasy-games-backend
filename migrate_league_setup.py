#!/usr/bin/env python3
"""
Migration script to add setup fields to existing leagues.
Run this script to update existing leagues with the new setup fields.
"""

import os
import sys
from app import create_app, db
from app.models import League

def migrate_league_setup():
    """Add setup fields to existing leagues."""
    app = create_app()
    
    with app.app_context():
        try:
            # Get all existing leagues
            leagues = League.query.all()
            
            print(f"Found {len(leagues)} leagues to migrate...")
            
            for league in leagues:
                # Set default values for new fields if they don't exist
                if not hasattr(league, 'is_setup_complete'):
                    league.is_setup_complete = False
                    print(f"Set is_setup_complete=False for league '{league.name}'")
                
                if not hasattr(league, 'setup_completed_at'):
                    league.setup_completed_at = None
                    print(f"Set setup_completed_at=None for league '{league.name}'")
            
            # Commit changes
            db.session.commit()
            print("✅ Migration completed successfully!")
            
        except Exception as e:
            print(f"❌ Error during migration: {e}")
            db.session.rollback()
            sys.exit(1)

if __name__ == "__main__":
    migrate_league_setup()
