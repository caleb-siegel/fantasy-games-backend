#!/usr/bin/env python3
"""
SQL migration script to add setup fields to existing leagues.
This script adds the new columns directly to the database.
"""

import os
import sys
import psycopg2
from psycopg2.extensions import ISOLATION_LEVEL_AUTOCOMMIT

def get_db_connection():
    """Get database connection from environment variables."""
    # Load environment variables from .env file
    from dotenv import load_dotenv
    load_dotenv()
    
    # Get database URL from environment
    database_url = os.getenv('DATABASE_URL')
    
    if database_url:
        # Parse the DATABASE_URL (format: postgresql://user:password@host:port/database)
        import urllib.parse
        parsed = urllib.parse.urlparse(database_url)
        
        return psycopg2.connect(
            host=parsed.hostname,
            port=parsed.port,
            database=parsed.path[1:],  # Remove leading slash
            user=parsed.username,
            password=parsed.password
        )
    else:
        # Fallback to individual environment variables
        return psycopg2.connect(
            host=os.getenv('DB_HOST', 'localhost'),
            port=os.getenv('DB_PORT', '5432'),
            database=os.getenv('DB_NAME', 'fantasy_betting'),
            user=os.getenv('DB_USER', 'postgres'),
            password=os.getenv('DB_PASSWORD', '')
        )

def migrate_league_setup():
    """Add setup fields to existing leagues."""
    try:
        conn = get_db_connection()
        conn.set_isolation_level(ISOLATION_LEVEL_AUTOCOMMIT)
        cursor = conn.cursor()
        
        print("Adding new columns to leagues table...")
        
        # Add is_setup_complete column
        try:
            cursor.execute("""
                ALTER TABLE leagues 
                ADD COLUMN is_setup_complete BOOLEAN NOT NULL DEFAULT FALSE
            """)
            print("✅ Added is_setup_complete column")
        except psycopg2.errors.DuplicateColumn:
            print("⚠️  is_setup_complete column already exists")
        
        # Add setup_completed_at column
        try:
            cursor.execute("""
                ALTER TABLE leagues 
                ADD COLUMN setup_completed_at TIMESTAMP
            """)
            print("✅ Added setup_completed_at column")
        except psycopg2.errors.DuplicateColumn:
            print("⚠️  setup_completed_at column already exists")
        
        # Verify the columns exist
        cursor.execute("""
            SELECT column_name, data_type, is_nullable, column_default
            FROM information_schema.columns 
            WHERE table_name = 'leagues' 
            AND column_name IN ('is_setup_complete', 'setup_completed_at')
        """)
        
        columns = cursor.fetchall()
        print(f"\n📋 Current league table columns:")
        for col in columns:
            print(f"  - {col[0]}: {col[1]} (nullable: {col[2]}, default: {col[3]})")
        
        cursor.close()
        conn.close()
        
        print("\n✅ Migration completed successfully!")
        
    except Exception as e:
        print(f"❌ Error during migration: {e}")
        sys.exit(1)

if __name__ == "__main__":
    migrate_league_setup()
