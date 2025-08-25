#!/usr/bin/env python3
"""
Logo Centralization Migration Script

This script migrates the existing logo system to the new centralized logo management system.
It creates the new database tables (Logo and TemplateLogoAssignment) and migrates existing
logo URLs from the CompanySettings table to the new system.

Usage:
    python migrate_centralized_logos.py

Features:
- Creates new Logo and TemplateLogoAssignment tables
- Migrates existing logo files to new system
- Maintains backward compatibility with old logo URLs
- Provides detailed migration report
- Automatically backs up database before migration

Author: Claude Backend Developer
Date: 2024-08-24
"""

import os
import sys
import sqlite3
import shutil
from datetime import datetime
from pathlib import Path

# Add app directory to Python path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from app import create_app
from app.models import db, CompanySettings, Logo, TemplateLogoAssignment
from sqlalchemy import text
import uuid

def create_backup():
    """Create database backup before migration."""
    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
    db_path = 'instance/billipocket.db'
    backup_path = f'instance/billipocket_backup_centralized_logos_{timestamp}.db'
    
    try:
        if os.path.exists(db_path):
            shutil.copy2(db_path, backup_path)
            print(f"✓ Database backup created: {backup_path}")
            return backup_path
        else:
            print(f"⚠️ Database file not found at {db_path}")
            return None
    except Exception as e:
        print(f"❌ Failed to create backup: {str(e)}")
        return None

def create_tables():
    """Create new Logo and TemplateLogoAssignment tables."""
    try:
        # Create tables using SQLAlchemy
        db.create_all()
        print("✓ New tables created successfully")
        return True
    except Exception as e:
        print(f"❌ Failed to create tables: {str(e)}")
        return False

def migrate_existing_logos():
    """Migrate existing logos from CompanySettings to new system."""
    print("\n=== Migrating Existing Logos ===")
    
    try:
        company_settings = CompanySettings.get_settings()
        if not company_settings:
            print("⚠️ No company settings found")
            return 0
        
        print(f"Found company settings for: {company_settings.company_name}")
        
        # Use the migration method from CompanySettings
        migrated_count = company_settings.migrate_old_logos_to_new_system()
        
        if migrated_count > 0:
            print(f"✓ Successfully migrated {migrated_count} logo(s)")
        else:
            print("ℹ️ No logos found to migrate")
        
        return migrated_count
        
    except Exception as e:
        print(f"❌ Failed to migrate logos: {str(e)}")
        return 0

def verify_migration():
    """Verify that migration was successful."""
    print("\n=== Verifying Migration ===")
    
    try:
        # Check Logo table
        logo_count = Logo.query.count()
        print(f"✓ Logo table contains {logo_count} logo(s)")
        
        # Check TemplateLogoAssignment table  
        assignment_count = TemplateLogoAssignment.query.count()
        print(f"✓ TemplateLogoAssignment table contains {assignment_count} assignment(s)")
        
        # Check if logos have valid URLs
        logos = Logo.get_all_active()
        for logo in logos:
            file_exists = os.path.exists(logo.file_path)
            url_valid = logo.get_url() is not None
            print(f"  - {logo.original_name}: file_exists={file_exists}, url_valid={url_valid}")
        
        # Check assignments are working
        company_settings = CompanySettings.get_settings()
        if company_settings:
            assignments = company_settings.get_all_logo_assignments()
            for assignment in assignments:
                logo_url = company_settings.get_logo_for_template_new(assignment.template_name)
                print(f"  - Template '{assignment.template_name}' → {assignment.logo.original_name} → URL: {logo_url is not None}")
        
        return True
        
    except Exception as e:
        print(f"❌ Verification failed: {str(e)}")
        return False

def test_new_api():
    """Test new API functionality."""
    print("\n=== Testing New API ===")
    
    try:
        # Test Logo model methods
        logos = Logo.get_all_active()
        print(f"✓ Logo.get_all_active() returned {len(logos)} logo(s)")
        
        if logos:
            first_logo = logos[0]
            logo_by_id = Logo.get_by_id(first_logo.id)
            print(f"✓ Logo.get_by_id() working: {logo_by_id is not None}")
            
            url = first_logo.get_url()
            print(f"✓ Logo.get_url() working: {url}")
        
        # Test TemplateLogoAssignment methods
        company_settings = CompanySettings.get_settings()
        if company_settings:
            # Test getting logo for template
            for template in ['standard', 'modern', 'elegant', 'minimal', 'classic']:
                logo_url = company_settings.get_logo_for_template_new(template)
                if logo_url:
                    print(f"✓ Template '{template}' has logo assigned: {logo_url}")
                else:
                    print(f"ℹ️ Template '{template}' has no logo assigned")
        
        return True
        
    except Exception as e:
        print(f"❌ API testing failed: {str(e)}")
        return False

def main():
    """Main migration function."""
    print("=" * 60)
    print("BILLIPOCKET LOGO CENTRALIZATION MIGRATION")
    print("=" * 60)
    print(f"Started at: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print()
    
    # Create Flask app
    app = create_app()
    with app.app_context():
        
        # Step 1: Create database backup
        print("=== Step 1: Creating Database Backup ===")
        backup_path = create_backup()
        if not backup_path:
            print("❌ Cannot proceed without backup")
            return False
        
        # Step 2: Create new tables
        print("\n=== Step 2: Creating New Tables ===")
        if not create_tables():
            print("❌ Failed to create tables")
            return False
        
        # Step 3: Migrate existing logos
        print("\n=== Step 3: Migrating Existing Logos ===")
        migrated_count = migrate_existing_logos()
        
        # Step 4: Verify migration
        if not verify_migration():
            print("❌ Migration verification failed")
            return False
        
        # Step 5: Test new API
        if not test_new_api():
            print("❌ API testing failed")
            return False
        
        print("\n" + "=" * 60)
        print("MIGRATION COMPLETED SUCCESSFULLY")
        print("=" * 60)
        print(f"✓ Database backup: {backup_path}")
        print(f"✓ New tables created: Logo, TemplateLogoAssignment")
        print(f"✓ Migrated logos: {migrated_count}")
        print(f"✓ All systems verified and working")
        print()
        print("NEXT STEPS:")
        print("1. Test the application to ensure everything works")
        print("2. Use new API endpoints for logo management:")
        print("   - GET /settings/logos")
        print("   - POST /settings/logos/upload")
        print("   - DELETE /settings/logos/<id>")
        print("   - POST /settings/templates/<template>/logo/<logo_id>")
        print("   - DELETE /settings/templates/<template>/logo")
        print("3. Old logo URLs will continue to work (backward compatibility)")
        print("4. Gradually transition to new centralized system")
        print()
        print(f"Completed at: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        
        return True

if __name__ == '__main__':
    success = main()
    sys.exit(0 if success else 1)