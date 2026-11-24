import os
import sqlite3
import hashlib
import logging
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, Any, List, Optional

from backend.app.core.config import settings

logger = logging.getLogger("niyantra.backup")

def _compute_sha256(file_path: Path) -> str:
    """Computes SHA-256 checksum of a file in 64KB chunks."""
    sha256 = hashlib.sha256()
    with open(file_path, "rb") as f:
        while chunk := f.read(65536):
            sha256.update(chunk)
    return sha256.hexdigest()

def verify_database_integrity(db_path: Optional[Path] = None) -> Dict[str, Any]:
    """
    Performs comprehensive SQLite integrity and foreign key validation checks.
    """
    target_path = Path(db_path or settings.DB_PATH)
    if not target_path.exists():
        return {
            "status": "error",
            "message": f"Database file does not exist at {target_path}",
            "integrity_check": "missing",
            "foreign_key_violations": -1,
        }

    try:
        conn = sqlite3.connect(str(target_path), timeout=10.0)
        cursor = conn.cursor()

        # 1. Integrity check
        cursor.execute("PRAGMA integrity_check")
        integrity_res = cursor.fetchall()
        integrity_ok = len(integrity_res) == 1 and integrity_res[0][0] == "ok"
        integrity_msg = "ok" if integrity_ok else str(integrity_res)

        # 2. Foreign key check
        cursor.execute("PRAGMA foreign_key_check")
        fk_violations = cursor.fetchall()

        # 3. Journal mode check
        cursor.execute("PRAGMA journal_mode")
        journal_mode = cursor.fetchone()[0]

        # 4. Table counts summary
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%'")
        tables = [row[0] for row in cursor.fetchall()]
        table_counts = {}
        for tbl in tables:
            try:
                cursor.execute(f"SELECT COUNT(*) FROM \"{tbl}\"")
                table_counts[tbl] = cursor.fetchone()[0]
            except Exception:
                pass

        conn.close()

        status = "healthy" if (integrity_ok and len(fk_violations) == 0) else "unhealthy"

        return {
            "status": status,
            "path": str(target_path),
            "size_bytes": target_path.stat().st_size,
            "integrity_check": integrity_msg,
            "foreign_key_violations": len(fk_violations),
            "journal_mode": journal_mode,
            "table_counts": table_counts,
        }
    except Exception as exc:
        logger.error(f"Integrity check failed for {target_path}: {exc}")
        return {
            "status": "error",
            "message": str(exc),
            "integrity_check": "failed",
            "foreign_key_violations": -1,
        }

def create_database_backup(
    db_path: Optional[Path] = None,
    backup_dir: Optional[Path] = None,
    label: Optional[str] = None,
) -> Dict[str, Any]:
    """
    Creates an atomic, non-locking online backup of the SQLite database
    using sqlite3's native online backup API. Safe to run while writes are active.
    """
    source_path = Path(db_path or settings.DB_PATH)
    target_dir = Path(backup_dir or settings.BACKUP_DIR)
    target_dir.mkdir(parents=True, exist_ok=True)

    if not source_path.exists():
        raise FileNotFoundError(f"Source database not found at {source_path}")

    now_str = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
    clean_label = f"_{label.strip()}" if label and label.strip() else ""
    backup_filename = f"niyantra_backup_{now_str}{clean_label}.db"
    dest_path = target_dir / backup_filename

    logger.info(f"Initiating online database backup: {source_path} -> {dest_path}")

    # Use native SQLite online backup API
    src_conn = sqlite3.connect(str(source_path), timeout=15.0)
    dest_conn = sqlite3.connect(str(dest_path), timeout=15.0)

    try:
        with dest_conn:
            src_conn.backup(dest_conn, pages=100)
    finally:
        dest_conn.close()
        src_conn.close()

    # Verify backup integrity immediately
    verification = verify_database_integrity(dest_path)
    if verification.get("integrity_check") != "ok":
        if dest_path.exists():
            dest_path.unlink()
        raise RuntimeError(f"Backup verification failed: {verification}")

    sha256_hash = _compute_sha256(dest_path)
    size_bytes = dest_path.stat().st_size

    logger.info(f"Backup completed successfully: {dest_path.name} ({size_bytes} bytes, SHA256: {sha256_hash[:12]}...)")

    return {
        "status": "success",
        "filename": dest_path.name,
        "path": str(dest_path),
        "size_bytes": size_bytes,
        "sha256": sha256_hash,
        "created_at": datetime.now(timezone.utc).isoformat(),
        "integrity": verification.get("integrity_check"),
        "foreign_key_violations": verification.get("foreign_key_violations"),
    }

def list_backups(backup_dir: Optional[Path] = None) -> List[Dict[str, Any]]:
    """
    Lists all available database backup files sorted newest first.
    """
    target_dir = Path(backup_dir or settings.BACKUP_DIR)
    if not target_dir.exists():
        return []

    backups = []
    for f in target_dir.glob("*.db"):
        stat = f.stat()
        backups.append({
            "filename": f.name,
            "path": str(f),
            "size_bytes": stat.st_size,
            "created_at": datetime.fromtimestamp(stat.st_mtime, tz=timezone.utc).isoformat(),
        })

    backups.sort(key=lambda b: b["created_at"], reverse=True)
    return backups

def restore_database_from_backup(
    backup_filename: str,
    target_db_path: Optional[Path] = None,
    backup_dir: Optional[Path] = None,
) -> Dict[str, Any]:
    """
    Restores database from an existing validated backup file.
    Always takes an automatic safety snapshot of the existing database prior to restoration.
    Uses SQLite's online backup API for safe, atomic restoration.
    """
    target_dir = Path(backup_dir or settings.BACKUP_DIR)
    dest_path = Path(target_db_path or settings.DB_PATH)

    # Sanitize filename to prevent directory traversal
    safe_name = Path(backup_filename).name
    backup_path = target_dir / safe_name

    if not backup_path.exists():
        raise FileNotFoundError(f"Backup file not found: {safe_name}")

    # Step 1: Pre-validation of backup file
    verification = verify_database_integrity(backup_path)
    if verification.get("integrity_check") != "ok":
        raise ValueError(f"Selected backup failed integrity check: {verification}")

    # Step 2: Safety snapshot of current active DB (if exists)
    safety_snapshot_meta = None
    if dest_path.exists():
        safety_snapshot_meta = create_database_backup(
            db_path=dest_path,
            backup_dir=target_dir,
            label="pre_restore_safety_snapshot",
        )
        logger.info(f"Created pre-restore safety snapshot: {safety_snapshot_meta['filename']}")

    # Step 3: Perform atomic online restore into target
    src_conn = sqlite3.connect(str(backup_path), timeout=15.0)
    dest_conn = sqlite3.connect(str(dest_path), timeout=15.0)

    try:
        with dest_conn:
            src_conn.backup(dest_conn, pages=100)
    finally:
        dest_conn.close()
        src_conn.close()

    # Step 4: Verify restored database integrity
    post_verification = verify_database_integrity(dest_path)
    if post_verification.get("integrity_check") != "ok":
        raise RuntimeError(f"Restored database failed integrity check: {post_verification}")

    logger.info(f"Database successfully restored from {safe_name}")

    return {
        "status": "success",
        "restored_from": safe_name,
        "target_database": str(dest_path),
        "safety_snapshot": safety_snapshot_meta["filename"] if safety_snapshot_meta else None,
        "integrity": post_verification.get("integrity_check"),
        "foreign_key_violations": post_verification.get("foreign_key_violations"),
        "table_counts": post_verification.get("table_counts"),
    }
