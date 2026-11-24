import sqlite3
import os
import shutil
import datetime

db_path = 'backend/niyantra.db'
timestamp = datetime.datetime.now().strftime('%Y%m%d_%H%M%S')
backup_path = f'backend/backups/niyantra_backup_{timestamp}_pre_phase10k.db'
os.makedirs('backend/backups', exist_ok=True)
shutil.copy2(db_path, backup_path)

conn = sqlite3.connect(backup_path)
c = conn.cursor()
c.execute('PRAGMA integrity_check;')
integrity = c.fetchall()
c.execute('PRAGMA foreign_key_check;')
fks = c.fetchall()
c.execute("SELECT count(*) FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%';")
tables_count = c.fetchone()[0]
conn.close()

print(f'Created backup: {backup_path}')
print(f'Integrity: {integrity}, FK errors: {len(fks)}, Tables: {tables_count}')
