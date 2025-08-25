#!/usr/bin/env python3
"""
Kasutaja Andmete Automaatne Backup

See skript loob automaatse backup kasutaja originaalsetest andmetest.
Käivita see regulaarselt või enne teste, et kaitsta andmeid.
"""

import os
import shutil
from datetime import datetime

def create_user_data_backup():
    """Loo backup kasutaja andmetest."""
    
    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
    
    # Backup andmebaasi
    source_db = 'instance/billipocket.db'
    if os.path.exists(source_db):
        backup_db = f'instance/USER_DATA_BACKUP_{timestamp}.db'
        shutil.copy2(source_db, backup_db)
        print(f"✅ Andmebaas varundatud: {backup_db}")
        
        # Kontrolli, et kasutaja andmed on olemas
        import sqlite3
        conn = sqlite3.connect(backup_db)
        cursor = conn.cursor()
        
        # Kontrolli kasutaja kliente
        cursor.execute("SELECT COUNT(*) FROM clients WHERE name IN ('Hoi Hoi OÜ', 'Geopol OÜ', 'HOKA Sports OÜ')")
        user_clients = cursor.fetchone()[0]
        
        cursor.execute("SELECT COUNT(*) FROM invoices")
        total_invoices = cursor.fetchone()[0]
        
        conn.close()
        
        print(f"📊 Backup sisaldab:")
        print(f"   - Kasutaja kliendid: {user_clients}/3")
        print(f"   - Kokku arveid: {total_invoices}")
        
        if user_clients >= 2:  # Vähemalt Hoi Hoi ja Geopol
            print("✅ Kasutaja andmed on turvaliselt varundatud!")
            return backup_db
        else:
            print("⚠️  Hoiatus: Mõned kasutaja andmed puuduvad!")
            return backup_db
    else:
        print(f"❌ Andmebaasi fail '{source_db}' ei leitud!")
        return None

def restore_from_backup(backup_file=None):
    """Taasta andmed backup'ist."""
    
    if backup_file is None:
        # Leia uusim kasutaja backup
        backup_files = [f for f in os.listdir('instance/') if f.startswith('USER_DATA_BACKUP_')]
        if not backup_files:
            print("❌ Ühtki kasutaja backup'i ei leitud!")
            return False
        
        backup_file = f"instance/{sorted(backup_files)[-1]}"
        print(f"📁 Kasutan uusimat backup'i: {backup_file}")
    
    if os.path.exists(backup_file):
        shutil.copy2(backup_file, 'instance/billipocket.db')
        print(f"✅ Andmed taastatud backup'ist: {backup_file}")
        return True
    else:
        print(f"❌ Backup fail '{backup_file}' ei leitud!")
        return False

if __name__ == '__main__':
    import sys
    
    if len(sys.argv) > 1 and sys.argv[1] == 'restore':
        # Taastamine
        backup_file = sys.argv[2] if len(sys.argv) > 2 else None
        restore_from_backup(backup_file)
    else:
        # Backup loomine
        create_user_data_backup()