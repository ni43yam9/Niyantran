import sqlite3
import os
import json
from pathlib import Path
from backend.app.services.backup_service import (
    create_database_backup,
    restore_database_from_backup,
    verify_database_integrity,
)

def audit_restoration():
    print("Step 1: Creating fresh backup of active database...")
    backup_meta = create_database_backup(label="audit_phase10k_fresh")
    backup_filename = backup_meta["filename"]
    print(f"Created fresh backup: {backup_filename}")

    temp_target = Path("backend/temp_restore_audit.db")
    if temp_target.exists():
        temp_target.unlink()

    print("Step 2: Restoring backup into isolated test database...")
    res = restore_database_from_backup(
        backup_filename=backup_filename,
        target_db_path=temp_target
    )
    print("Restoration result:", res)

    print("Step 3: Verifying restored database integrity...")
    verification = verify_database_integrity(temp_target)
    print("Verification:", verification)
    assert verification["integrity_check"] == "ok"
    assert verification["foreign_key_violations"] == 0

    print("Step 4: Comparing all table row counts between production and restored sandbox...")
    prod_conn = sqlite3.connect("backend/niyantra.db")
    restored_conn = sqlite3.connect(str(temp_target))
    
    prod_c = prod_conn.cursor()
    rest_c = restored_conn.cursor()

    prod_c.execute("SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%';")
    tables = [r[0] for r in prod_c.fetchall()]

    comparison = {}
    mismatches = []
    for t in sorted(tables):
        prod_c.execute(f'SELECT COUNT(*) FROM "{t}"')
        prod_count = prod_c.fetchone()[0]

        rest_c.execute(f'SELECT COUNT(*) FROM "{t}"')
        rest_count = rest_c.fetchone()[0]

        comparison[t] = {"production": prod_count, "restored": rest_count}
        if prod_count != rest_count:
            mismatches.append(t)

    prod_conn.close()
    restored_conn.close()

    print("Table row counts comparison:")
    print(json.dumps(comparison, indent=2))
    print("Mismatches:", mismatches)

    # Clean up test database
    if temp_target.exists():
        temp_target.unlink()
    print("Cleaned up temp_restore_audit.db.")

    assert len(mismatches) == 0, f"Row count mismatches found in: {mismatches}"
    print("BACKUP RESTORATION AUDIT PASSED 100%!")

if __name__ == "__main__":
    audit_restoration()
