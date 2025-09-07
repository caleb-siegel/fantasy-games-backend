#!/usr/bin/env python3
"""
Database initialization script for production deployment.
Run this script to set up the database schema.
"""

import os
import sys
from app import create_app, db

def init_db():
    """Initialize the database with all tables."""
    app = create_app()
    
    with app.app_context():
        try:
            # Create all tables
            db.create_all()
            print("✅ Database tables created successfully!")
            
            # You can add initial data here if needed
            # Example: create admin user, default leagues, etc.
            
        except Exception as e:
            print(f"❌ Error creating database tables: {e}")
            sys.exit(1)

if __name__ == "__main__":
    init_db()
