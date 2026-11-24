import shutil
import sqlite3
from datetime import datetime
from pathlib import Path

def main():
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    backup_path = Path("backend/backups") / f"niyantra_backup_{ts}_pre_phase10f_baseline.db"
    backup_path.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2("backend/niyantra.db", backup_path)
    print(f"Created backup: {backup_path}")

    conn = sqlite3.connect("backend/niyantra.db")
    c = conn.cursor()
    tables = [r[0] for r in c.execute("SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%'").fetchall()]
    print("Baseline table counts:")
    for t in sorted(tables):
        cnt = c.execute(f'SELECT COUNT(*) FROM "{t}"').fetchone()[0]
        print(f"  {t}: {cnt}")
    conn.close()

if __name__ == "__main__":
    main()
