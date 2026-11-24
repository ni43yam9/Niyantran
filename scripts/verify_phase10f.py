import sqlite3

def main():
    conn = sqlite3.connect("backend/niyantra.db")
    c = conn.cursor()
    integrity = c.execute("PRAGMA integrity_check").fetchall()
    fks = c.execute("PRAGMA foreign_key_check").fetchall()
    print(f"PRAGMA integrity_check: {integrity}")
    print(f"PRAGMA foreign_key_check: {fks}")
    
    tables = [r[0] for r in c.execute("SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%'").fetchall()]
    print("Table row counts:")
    for t in sorted(tables):
        cnt = c.execute(f'SELECT COUNT(*) FROM "{t}"').fetchone()[0]
        print(f"  {t}: {cnt}")
    conn.close()

if __name__ == "__main__":
    main()
