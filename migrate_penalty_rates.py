#!/usr/bin/env python3
"""
Migration script to create penalty_rates table and add default penalty rates.
This script safely creates the penalty_rates table and populates it with default Estonian penalty rates.
"""

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from app import create_app
from app.models import db, PenaltyRate, CompanySettings

def migrate_penalty_rates():
    """Create penalty_rates table and add default rates."""
    app = create_app()
    
    with app.app_context():
        print("Creating penalty_rates table...")
        
        try:
            # Create the penalty_rates table
            db.create_all()
            print("✓ penalty_rates table created successfully")
            
            # Check if penalty rates already exist
            existing_count = PenaltyRate.query.count()
            if existing_count > 0:
                print(f"✓ Found {existing_count} existing penalty rates, skipping default creation")
            else:
                # Create default penalty rates
                print("Creating default penalty rates...")
                PenaltyRate.create_default_rates()
                
                # Verify creation
                new_count = PenaltyRate.query.count()
                print(f"✓ Created {new_count} default penalty rates")
                
                # List created rates
                rates = PenaltyRate.query.order_by(PenaltyRate.rate_per_day.asc()).all()
                for rate in rates:
                    status = " (VAIKIMISI)" if rate.is_default else ""
                    print(f"  - {rate.name}: {rate.rate_per_day}% päevas{status}")
            
            # Try to set default penalty rate in company settings if not set
            try:
                settings = CompanySettings.get_settings()
                if not settings.default_penalty_rate_id:
                    default_rate = PenaltyRate.get_default_rate()
                    if default_rate:
                        settings.default_penalty_rate_id = default_rate.id
                        db.session.commit()
                        print(f"✓ Set default penalty rate in company settings: {default_rate.name}")
            except Exception as e:
                print(f"⚠ Could not update company settings: {str(e)}")
            
        except Exception as e:
            print(f"✗ Error during penalty rates migration: {str(e)}")
            db.session.rollback()
            return False
        
        print("\n✅ Penalty rates migration completed successfully!")
        print("\nVoice viiviste seadeid saab hallata:")
        print("1. Seadete lehel → Vaikimisi viivis")
        print("2. 'Halda' nupu kaudu saab lisada, muuta ja kustutada viiviseid")
        return True

if __name__ == '__main__':
    success = migrate_penalty_rates()
    sys.exit(0 if success else 1)