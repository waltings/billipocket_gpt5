#!/usr/bin/env python3
"""
Migration script to add pdf_template column to invoices table.
Run this script to update the database schema.
"""
import sqlite3
import sys
import os
from datetime import datetime

# Add the app directory to Python path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

def add_pdf_template_column():
    """Add pdf_template column to invoices table."""
    db_path = 'instance/billipocket.db'
    
    if not os.path.exists(db_path):
        print(f"Database not found at {db_path}")
        return False
    
    # Create backup
    backup_path = f'instance/billipocket_backup_pdf_template_{datetime.now().strftime("%Y%m%d_%H%M%S")}.db'
    
    try:
        # Copy database for backup
        import shutil
        shutil.copy2(db_path, backup_path)
        print(f"Created backup: {backup_path}")
        
        # Connect to database
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        
        # Check if column already exists
        cursor.execute("PRAGMA table_info(invoices);")
        columns = [column[1] for column in cursor.fetchall()]
        
        if 'pdf_template' in columns:
            print("pdf_template column already exists, skipping migration.")
            conn.close()
            return True
        
        # Add the new column
        cursor.execute("""
            ALTER TABLE invoices 
            ADD COLUMN pdf_template VARCHAR(20) DEFAULT 'standard';
        """)
        
        print("Added pdf_template column to invoices table")
        
        # Update existing records to have 'standard' as default
        cursor.execute("""
            UPDATE invoices 
            SET pdf_template = 'standard' 
            WHERE pdf_template IS NULL;
        """)
        
        updated_rows = cursor.rowcount
        print(f"Updated {updated_rows} existing records with default template 'standard'")
        
        # Commit changes
        conn.commit()
        conn.close()
        
        print("Migration completed successfully!")
        return True
        
    except Exception as e:
        print(f"Migration failed: {str(e)}")
        if os.path.exists(backup_path):
            print(f"Backup available at: {backup_path}")
        return False

if __name__ == "__main__":
    print("Running PDF template column migration...")
    if add_pdf_template_column():
        print("Migration successful!")
        sys.exit(0)
    else:
        print("Migration failed!")
        sys.exit(1)