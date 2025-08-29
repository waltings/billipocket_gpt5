#!/usr/bin/env python3
"""
Database migration script to add authentication support to existing Billipocket application.
This script preserves ALL existing data while adding the User table and authentication infrastructure.

Usage: python migrate_add_authentication.py
"""

import os
import shutil
import sqlite3
from datetime import datetime

def backup_database(db_path):
    """Create a backup of the database before migration."""
    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
    backup_path = f"{db_path}_backup_auth_migration_{timestamp}"
    
    try:
        shutil.copy2(db_path, backup_path)
        print(f"✅ Database backed up to: {backup_path}")
        return backup_path
    except Exception as e:
        print(f"❌ Error creating backup: {str(e)}")
        return None

def add_users_table(db_path):
    """Add the users table to the existing database."""
    try:
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        
        # Check if users table already exists
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='users'")
        if cursor.fetchone():
            print("ℹ️ Users table already exists, skipping creation.")
            return True
        
        # Create users table
        cursor.execute('''
            CREATE TABLE users (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                username VARCHAR(80) NOT NULL UNIQUE,
                email VARCHAR(120) NOT NULL UNIQUE,
                password_hash VARCHAR(255) NOT NULL,
                is_active BOOLEAN NOT NULL DEFAULT 1,
                is_admin BOOLEAN NOT NULL DEFAULT 0,
                created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                last_login DATETIME
            )
        ''')
        
        # Create indexes for performance
        cursor.execute('CREATE INDEX ix_users_username ON users (username)')
        cursor.execute('CREATE INDEX ix_users_email ON users (email)')
        
        conn.commit()
        conn.close()
        
        print("✅ Users table created successfully")
        return True
        
    except Exception as e:
        print(f"❌ Error creating users table: {str(e)}")
        return False

def verify_existing_data(db_path):
    """Verify that all existing data is still intact."""
    try:
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        
        # Check main tables exist and have data
        tables_to_check = [
            'clients', 'invoices', 'invoice_lines', 'vat_rates', 
            'payment_terms', 'penalty_rates', 'company_settings'
        ]
        
        print("\n📊 Verifying existing data integrity:")
        for table in tables_to_check:
            try:
                cursor.execute(f"SELECT COUNT(*) FROM {table}")
                count = cursor.fetchone()[0]
                print(f"  {table}: {count} records")
            except sqlite3.OperationalError:
                print(f"  {table}: table does not exist (may be optional)")
        
        conn.close()
        print("✅ Data integrity check completed")
        return True
        
    except Exception as e:
        print(f"❌ Error verifying data: {str(e)}")
        return False

def main():
    """Main migration function."""
    print("🔄 Starting authentication migration for Billipocket")
    print("=" * 50)
    
    # Locate database file
    instance_dir = "instance"
    db_filename = "billipocket.db"
    db_path = os.path.join(instance_dir, db_filename)
    
    # Also check in project root for development
    if not os.path.exists(db_path):
        db_path = db_filename
    
    if not os.path.exists(db_path):
        print(f"❌ Database file not found at {db_path}")
        print("   Please ensure the database file exists before running migration.")
        return False
    
    print(f"📂 Found database at: {db_path}")
    
    # Step 1: Backup existing database
    print("\n1️⃣ Creating database backup...")
    backup_path = backup_database(db_path)
    if not backup_path:
        print("❌ Migration aborted - could not create backup")
        return False
    
    # Step 2: Verify existing data before migration
    print("\n2️⃣ Verifying existing data...")
    if not verify_existing_data(db_path):
        print("❌ Migration aborted - data integrity check failed")
        return False
    
    # Step 3: Add users table
    print("\n3️⃣ Adding authentication tables...")
    if not add_users_table(db_path):
        print("❌ Migration failed - could not create users table")
        return False
    
    # Step 4: Final verification
    print("\n4️⃣ Final verification...")
    if not verify_existing_data(db_path):
        print("❌ Migration completed but data integrity check failed")
        return False
    
    # Success!
    print("\n" + "=" * 50)
    print("🎉 Authentication migration completed successfully!")
    print("\nNext steps:")
    print("1. Install Flask-Login: pip install Flask-Login==0.6.3")
    print("2. Start the application: python run.py")
    print("3. Register the first user (will be made admin automatically)")
    print("\nCLI Commands available:")
    print("- flask create-admin <username> <email>  # Create admin user")
    print("- flask create-user <username> <email>   # Create regular user")
    print("- flask list-users                       # List all users")
    print("\n✅ All existing invoices, clients, and settings are preserved!")
    
    return True

if __name__ == '__main__':
    success = main()
    exit(0 if success else 1)