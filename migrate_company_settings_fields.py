#!/usr/bin/env python3
"""
Database migration script to add new company settings fields.

This script adds the following new columns to the company_settings table:
- company_settings.company_bank (String)
- company_settings.company_bank_account (String)
- company_settings.marketing_messages (Text)

Run this script from the project root directory.
"""

import sqlite3
import os
import sys
from pathlib import Path

def get_database_path():
    """Get the path to the SQLite database."""
    # Try to find the database in the instance folder
    instance_dir = Path(__file__).parent / 'instance'
    db_path = instance_dir / 'billipocket.db'
    
    if db_path.exists():
        return str(db_path)
    
    # Fallback to current directory
    fallback_path = Path(__file__).parent / 'billipocket.db'
    if fallback_path.exists():
        return str(fallback_path)
    
    print("Error: Could not find billipocket.db")
    print(f"Looked in: {db_path} and {fallback_path}")
    return None

def backup_database(db_path):
    """Create a backup of the database before migration."""
    import shutil
    from datetime import datetime
    
    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
    backup_path = f"{db_path}_backup_company_settings_{timestamp}"
    
    try:
        shutil.copy2(db_path, backup_path)
        print(f"✅ Database backup created: {backup_path}")
        return backup_path
    except Exception as e:
        print(f"❌ Failed to create backup: {e}")
        return None

def check_existing_columns(cursor):
    """Check which columns already exist."""
    # Get company_settings table schema
    cursor.execute("PRAGMA table_info(company_settings)")
    settings_columns = [row[1] for row in cursor.fetchall()]
    
    return settings_columns

def migrate_database(db_path):
    """Apply the migration to add new fields."""
    print(f"🔄 Starting migration on database: {db_path}")
    
    try:
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        
        # Check existing columns
        settings_columns = check_existing_columns(cursor)
        
        print(f"📋 Current company_settings columns: {len(settings_columns)} columns")
        
        # Add new columns to company_settings table
        new_settings_columns = [
            ('company_bank', 'TEXT DEFAULT ""'),
            ('company_bank_account', 'TEXT DEFAULT ""'),
            ('marketing_messages', 'TEXT DEFAULT ""')
        ]
        
        print("\n🔧 Adding new company_settings columns...")
        for column_name, column_def in new_settings_columns:
            if column_name not in settings_columns:
                sql = f"ALTER TABLE company_settings ADD COLUMN {column_name} {column_def}"
                print(f"   Adding: {column_name}")
                cursor.execute(sql)
            else:
                print(f"   ⏭️  Skipping {column_name} (already exists)")
        
        # Commit the changes
        conn.commit()
        
        # Verify the migration
        print("\n✅ Verifying migration...")
        settings_columns_after = check_existing_columns(cursor)
        
        # Check if all new columns were added
        expected_columns = [col[0] for col in new_settings_columns]
        missing_columns = [col for col in expected_columns if col not in settings_columns_after]
        
        if missing_columns:
            print(f"❌ Missing columns: {missing_columns}")
            return False
        
        print(f"✅ Migration successful!")
        print(f"   Company settings columns: {len(settings_columns)} → {len(settings_columns_after)}")
        
        return True
        
    except Exception as e:
        print(f"❌ Migration failed: {e}")
        conn.rollback()
        return False
        
    finally:
        conn.close()

def main():
    """Main migration function."""
    print("🚀 BilliPocket Database Migration")
    print("=" * 50)
    print("Adding new company settings fields:")
    print("  • company_bank")
    print("  • company_bank_account") 
    print("  • marketing_messages")
    print("=" * 50)
    
    # Get database path
    db_path = get_database_path()
    if not db_path:
        return 1
    
    print(f"📍 Database location: {db_path}")
    
    # Create backup
    backup_path = backup_database(db_path)
    if not backup_path:
        print("❌ Cannot proceed without backup")
        return 1
    
    # Ask for confirmation (skip in non-interactive mode)
    try:
        confirm = input("\nProceed with migration? [y/N]: ").strip().lower()
        if confirm not in ('y', 'yes'):
            print("❌ Migration cancelled")
            return 1
    except EOFError:
        # Non-interactive mode, proceed automatically
        print("\nNon-interactive mode detected - proceeding with migration...")
    
    # Run migration
    success = migrate_database(db_path)
    
    if success:
        print("\n🎉 Migration completed successfully!")
        print("You can now start the Flask application with the new company settings layout.")
        return 0
    else:
        print(f"\n💥 Migration failed!")
        print(f"Your original database is safe at: {backup_path}")
        print("Please check the error messages above and try again.")
        return 1

if __name__ == '__main__':
    sys.exit(main())