#!/usr/bin/env python3
"""
Migration script to add note_labels table and create default labels.
Run this script to add the NoteLabel functionality to existing installations.
"""
import os
import sys

# Add the app directory to the path
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from app import create_app
from app.models import db, NoteLabel
from app.logging_config import get_logger

logger = get_logger(__name__)

def create_note_labels_table():
    """Create the note_labels table if it doesn't exist."""
    try:
        # Try to create all tables (will only create missing ones)
        db.create_all()
        logger.info("Database tables created/verified successfully")
        return True
    except Exception as e:
        logger.error(f"Error creating tables: {e}")
        return False

def create_default_note_labels():
    """Create default note labels."""
    try:
        # Check if any labels already exist
        existing_labels = NoteLabel.query.count()
        if existing_labels > 0:
            logger.info(f"Note labels already exist ({existing_labels} labels found), skipping default creation")
            return True
        
        # Create default labels
        default_labels = NoteLabel.create_default_labels()
        logger.info(f"Created {len(default_labels)} default note labels")
        
        return True
    except Exception as e:
        logger.error(f"Error creating default note labels: {e}")
        return False

def main():
    """Run the migration."""
    print("🔄 Starting NoteLabel migration...")
    
    # Create Flask app
    app = create_app()
    
    with app.app_context():
        # Step 1: Create table
        print("📋 Creating note_labels table...")
        if not create_note_labels_table():
            print("❌ Failed to create note_labels table")
            return False
        print("✅ Note labels table created successfully")
        
        # Step 2: Create default labels
        print("📝 Creating default note labels...")
        if not create_default_note_labels():
            print("❌ Failed to create default note labels")
            return False
        print("✅ Default note labels created successfully")
        
        # Show created labels
        labels = NoteLabel.query.all()
        print(f"\n📊 Available note labels:")
        for label in labels:
            status = "🌟 (default)" if label.is_default else "📌"
            print(f"   {status} {label.name}")
        
        print(f"\n🎉 Migration completed successfully!")
        print(f"   - Table 'note_labels' created")
        print(f"   - {len(labels)} default labels added")
        print(f"   - Go to Settings page to manage labels")
        
        return True

if __name__ == "__main__":
    success = main()
    if not success:
        sys.exit(1)