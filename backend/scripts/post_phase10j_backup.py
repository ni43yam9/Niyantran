import sqlite3
import os
import shutil
import datetime

db_path = 'backend/niyantra.db'
conn = sqlite3.connect(db_path)
c = conn.cursor()

c.execute('PRAGMA integrity_check;')
integrity = c.fetchall()
print('Integrity check:', integrity)

c.execute('PRAGMA foreign_key_check;')
fk_errors = c.fetchall()
print('FK check errors:', len(fk_errors))

c.execute("SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%';")
tables = [row[0] for row in c.fetchall()]
print(f'Total tables ({len(tables)}):', sorted(tables))

row_counts = {}
for t in sorted(tables):
    c.execute(f'SELECT COUNT(*) FROM "{t}"')
    row_counts[t] = c.fetchone()[0]
print('Row counts:', row_counts)
conn.close()

# Create verified post-phase10j backup
timestamp = datetime.datetime.now().strftime('%Y%m%d_%H%M%S')
backup_filename = f'backend/backups/niyantra_backup_{timestamp}_post_phase10j.db'
os.makedirs('backend/backups', exist_ok=True)
shutil.copy2(db_path, backup_filename)
print('Created post-phase10j backup:', backup_filename)

# Verify the backup
b_conn = sqlite3.connect(backup_filename)
b_c = b_conn.cursor()
b_c.execute('PRAGMA integrity_check;')
b_integrity = b_c.fetchall()
b_c.execute('PRAGMA foreign_key_check;')
b_fk = b_c.fetchall()
print('Backup verified integrity:', b_integrity, 'FK errors:', len(b_fk))
b_conn.close()
