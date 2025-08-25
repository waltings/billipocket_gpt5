#!/usr/bin/env python3
"""
Migration script to add PDF template-specific logo columns to company_settings table.
"""
import os
import sys
import sqlite3
from datetime import datetime

def get_db_path():
    """Get the database path from instance or current directory."""
    instance_db = os.path.join('instance', 'billipocket.db')
    current_db = 'billipocket.db'
    
    if os.path.exists(instance_db):
        return instance_db
    elif os.path.exists(current_db):
        return current_db
    else:
        raise FileNotFoundError("Database file not found in instance/ or current directory")

def backup_database(db_path):
    """Create a backup of the database before migration."""
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    backup_path = f"{db_path}_backup_template_logos_{timestamp}"
    
    import shutil
    shutil.copy2(db_path, backup_path)
    print(f"Database backed up to: {backup_path}")
    return backup_path

def check_columns_exist(cursor):
    """Check if the new columns already exist."""
    cursor.execute("PRAGMA table_info(company_settings)")
    columns = [row[1] for row in cursor.fetchall()]
    
    new_columns = [
        'logo_standard_url',
        'logo_modern_url', 
        'logo_elegant_url',
        'logo_minimal_url',
        'logo_classic_url'
    ]
    
    existing_new_columns = [col for col in new_columns if col in columns]
    missing_columns = [col for col in new_columns if col not in columns]
    
    return existing_new_columns, missing_columns

def add_template_logo_columns(db_path):
    """Add PDF template-specific logo columns to company_settings table."""
    
    try:
        # Backup database
        backup_path = backup_database(db_path)
        
        # Connect to database
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        
        # Check which columns need to be added
        existing_columns, missing_columns = check_columns_exist(cursor)
        
        if existing_columns:
            print(f"The following columns already exist: {', '.join(existing_columns)}")
        
        if not missing_columns:
            print("All template logo columns already exist. No migration needed.")
            conn.close()
            return True
        
        print(f"Adding missing columns: {', '.join(missing_columns)}")
        
        # Add missing columns
        for column in missing_columns:
            sql = f"ALTER TABLE company_settings ADD COLUMN {column} VARCHAR(500) DEFAULT ''"
            print(f"Executing: {sql}")
            cursor.execute(sql)
        
        # Commit changes
        conn.commit()
        
        # Verify the changes
        existing_columns, missing_columns = check_columns_exist(cursor)
        
        if not missing_columns:
            print("✅ Migration successful! All template logo columns added.")
        else:
            print(f"❌ Migration incomplete. Missing columns: {', '.join(missing_columns)}")
            return False
            
        conn.close()
        return True
        
    except Exception as e:
        print(f"❌ Migration failed: {str(e)}")
        if 'conn' in locals():
            conn.rollback()
            conn.close()
        return False

def main():
    """Run the migration."""
    print("🔄 Starting template logos migration...")
    
    try:
        db_path = get_db_path()
        print(f"Using database: {db_path}")
        
        if add_template_logo_columns(db_path):
            print("🎉 Migration completed successfully!")
            return 0
        else:
            print("💥 Migration failed!")
            return 1
            
    except Exception as e:
        print(f"💥 Migration error: {str(e)}")
        return 1

if __name__ == '__main__':
    exit(main())