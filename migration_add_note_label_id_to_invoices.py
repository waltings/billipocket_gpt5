#!/usr/bin/env python3
"""
Migration script to add note_label_id column to invoices table.
Run this script to add the note_label_id foreign key to existing installations.
"""
import os
import sys

# Add the app directory to the path
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from app import create_app
from app.models import db, Invoice, NoteLabel
from app.logging_config import get_logger

logger = get_logger(__name__)

def add_note_label_id_column():
    """Add note_label_id column to invoices table if it doesn't exist."""
    try:
        # Check if column already exists
        inspector = db.inspect(db.engine)
        columns = [col['name'] for col in inspector.get_columns('invoices')]
        
        if 'note_label_id' in columns:
            logger.info("Column 'note_label_id' already exists")
            return True
        
        # Add the column using raw SQL
        with db.engine.connect() as conn:
            conn.execute(db.text('ALTER TABLE invoices ADD COLUMN note_label_id INTEGER REFERENCES note_labels(id)'))
            conn.commit()
        logger.info("Column 'note_label_id' added successfully")
        return True
    except Exception as e:
        logger.error(f"Error adding column: {e}")
        return False

def set_default_note_labels_for_existing_invoices():
    """Set default note label for existing invoices that don't have one."""
    try:
        # Get default note label
        default_label = NoteLabel.get_default_label()
        if not default_label:
            logger.warning("No default note label found, skipping invoice updates")
            return True
        
        # Find invoices without note_label_id
        invoices_to_update = Invoice.query.filter_by(note_label_id=None).all()
        
        if not invoices_to_update:
            logger.info("All invoices already have note labels assigned")
            return True
        
        logger.info(f"Setting default note label for {len(invoices_to_update)} invoices")
        
        # Update invoices
        for invoice in invoices_to_update:
            invoice.note_label_id = default_label.id
        
        db.session.commit()
        logger.info(f"Successfully updated {len(invoices_to_update)} invoices with default note label")
        
        return True
    except Exception as e:
        logger.error(f"Error setting default note labels: {e}")
        db.session.rollback()
        return False

def main():
    """Run the migration."""
    print("🔄 Starting Invoice note_label_id migration...")
    
    # Create Flask app
    app = create_app()
    
    with app.app_context():
        # Step 1: Add column
        print("📋 Adding note_label_id column to invoices table...")
        if not add_note_label_id_column():
            print("❌ Failed to add note_label_id column")
            return False
        print("✅ Note label ID column added successfully")
        
        # Step 2: Set default labels for existing invoices
        print("📝 Setting default note labels for existing invoices...")
        if not set_default_note_labels_for_existing_invoices():
            print("❌ Failed to set default note labels")
            return False
        print("✅ Default note labels set for existing invoices")
        
        # Show results
        total_invoices = Invoice.query.count()
        invoices_with_labels = Invoice.query.filter(Invoice.note_label_id.isnot(None)).count()
        
        print(f"\n📊 Migration results:")
        print(f"   - Total invoices: {total_invoices}")
        print(f"   - Invoices with note labels: {invoices_with_labels}")
        
        print(f"\n🎉 Migration completed successfully!")
        print(f"   - Column 'note_label_id' added to invoices table")
        print(f"   - Existing invoices updated with default note labels")
        
        return True

if __name__ == "__main__":
    success = main()
    if not success:
        sys.exit(1)