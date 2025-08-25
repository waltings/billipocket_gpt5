#!/usr/bin/env python3
"""
Database migration script to create PaymentTerms table and populate with default data.

This script creates the payment_terms table with the following columns:
- id (Primary key)
- name (String, unique)
- days (Integer) 
- is_default (Boolean)
- is_active (Boolean)
- created_at (DateTime)

Run this script from the project root directory.
"""

import sqlite3
import os
import sys
from pathlib import Path
from datetime import datetime

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
    backup_path = f"{db_path}_backup_payment_terms_{timestamp}"
    
    try:
        shutil.copy2(db_path, backup_path)
        print(f"✅ Database backup created: {backup_path}")
        return backup_path
    except Exception as e:
        print(f"❌ Failed to create backup: {e}")
        return None

def check_table_exists(cursor, table_name):
    """Check if a table already exists."""
    cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name=?", (table_name,))
    return cursor.fetchone() is not None

def create_payment_terms_table(cursor):
    """Create the payment_terms table."""
    print("🔧 Creating payment_terms table...")
    
    cursor.execute("""
        CREATE TABLE payment_terms (
            id INTEGER PRIMARY KEY,
            name VARCHAR(50) NOT NULL UNIQUE,
            days INTEGER NOT NULL,
            is_default BOOLEAN NOT NULL DEFAULT 0,
            is_active BOOLEAN NOT NULL DEFAULT 1,
            created_at DATETIME DEFAULT CURRENT_TIMESTAMP
        )
    """)
    
    # Create indexes
    cursor.execute("CREATE INDEX idx_payment_terms_name ON payment_terms(name)")
    cursor.execute("CREATE INDEX idx_payment_terms_days ON payment_terms(days)")
    cursor.execute("CREATE INDEX idx_payment_terms_default ON payment_terms(is_default)")
    cursor.execute("CREATE INDEX idx_payment_terms_active ON payment_terms(is_active)")
    
    print("   ✅ payment_terms table created")
    print("   ✅ Indexes created")

def populate_default_payment_terms(cursor):
    """Populate table with default payment terms."""
    print("🔧 Populating default payment terms...")
    
    # Generate proper Estonian singular/plural forms
    def get_day_name(days):
        return f"{days} {'päev' if days == 1 else 'päeva'}"
    
    default_terms = [
        (get_day_name(0), 0, False),
        (get_day_name(1), 1, False),
        (get_day_name(7), 7, False),
        (get_day_name(14), 14, True),  # Default
        (get_day_name(21), 21, False),
        (get_day_name(30), 30, False),
        (get_day_name(60), 60, False),
        (get_day_name(90), 90, False),
    ]
    
    for name, days, is_default in default_terms:
        cursor.execute("""
            INSERT INTO payment_terms (name, days, is_default, is_active)
            VALUES (?, ?, ?, 1)
        """, (name, days, is_default))
        status = "✅ (default)" if is_default else "✅"
        print(f"   {status} {name} ({days} päeva)")

def migrate_database(db_path):
    """Apply the migration to create PaymentTerms table."""
    print(f"🔄 Starting migration on database: {db_path}")
    
    try:
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        
        # Check if table already exists
        if check_table_exists(cursor, 'payment_terms'):
            print("⏭️  payment_terms table already exists, skipping creation")
            return True
        
        # Create the table
        create_payment_terms_table(cursor)
        
        # Populate with default data
        populate_default_payment_terms(cursor)
        
        # Commit the changes
        conn.commit()
        
        # Verify the migration
        print("\n✅ Verifying migration...")
        cursor.execute("SELECT COUNT(*) FROM payment_terms")
        count = cursor.fetchone()[0]
        
        cursor.execute("SELECT COUNT(*) FROM payment_terms WHERE is_default = 1")
        default_count = cursor.fetchone()[0]
        
        print(f"   Payment terms created: {count}")
        print(f"   Default terms: {default_count}")
        
        if count > 0 and default_count == 1:
            print("✅ Migration successful!")
            return True
        else:
            print("❌ Migration verification failed")
            return False
        
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
    print("Creating PaymentTerms table:")
    print("  • payment_terms table with indexes")
    print("  • Default payment terms (0, 7, 14*, 21, 30, 60, 90 päeva)")
    print("  • * = default term")
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
        print("You can now manage payment terms in the settings page.")
        return 0
    else:
        print(f"\n💥 Migration failed!")
        print(f"Your original database is safe at: {backup_path}")
        print("Please check the error messages above and try again.")
        return 1

if __name__ == '__main__':
    sys.exit(main())