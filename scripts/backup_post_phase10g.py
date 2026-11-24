import shutil
from datetime import datetime
from pathlib import Path

def main():
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    backup_path = Path("backend/backups") / f"niyantra_backup_{ts}_post_phase10g_verified.db"
    shutil.copy2("backend/niyantra.db", backup_path)
    print(f"Post-Phase 10G verified backup created: {backup_path}")

if __name__ == "__main__":
    main()
