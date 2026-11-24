# NIYANTRA PHASE 10B: NON-BREAKING DATABASE SCHEMA EVOLUTION REPORT

## Executive Summary
Phase 10B ("Non-Breaking Database Schema Evolution") has been successfully implemented and verified for **Niyantra**. 

The goal was to evolve the existing SQLite database (`backend/niyantra.db`) and SQLAlchemy models to be fully prepared for future cloud-based, offline-first, multi-device synchronization (e.g., Supabase / PostgreSQL sync engine) **without breaking existing contracts**, without altering historical entity identifiers, without introducing cloud connectivity or authentication prematurely, and without losing a single record of user data.

---

## 1. Files Modified and Added

### A. Database Migrations (Alembic)
- `backend/alembic.ini`: Configured Alembic configuration file pointing to dynamic settings.
- `backend/alembic/env.py`: Configured SQLAlchemy metadata reflection with SQLite `render_as_batch=True` and WAL mode compatibility.
- `backend/alembic/script.py.mako`: Migration template for future schema revisions.
- `backend/alembic/versions/fa32b08ebb44_phase10b_schema_evolution.py`: Complete non-destructive migration script implementing all Phase 10B schema enhancements with full SQLite batch safety, historical data backfilling, and reversible downgrade logic.

### B. SQLAlchemy Models
- `backend/app/models/daily_intent.py`: **NEW**. Added dedicated model absorbing frontend `localStorage` daily intent state with fields `id`, `user_id`, `intent_date`, `intent_text`, `version`, `is_deleted`, `deleted_at`, `created_at`, `updated_at`, and a unique constraint on `(user_id, intent_date)`.
- `backend/app/models/task.py`: Added `user_id`, `version`, `is_deleted`, `deleted_at`, and composite sync indices (`idx_tasks_sync`, `idx_tasks_is_deleted`). Default new ID generation configured to collision-resistant UUIDs (`uuid.uuid4()`).
- `backend/app/models/goal.py`: Added `user_id`, `version`, `is_deleted`, `deleted_at`, and composite sync indices (`idx_goals_sync`, `idx_goals_is_deleted`). Default new ID generation configured to UUIDs.
- `backend/app/models/habit.py`: Added `user_id`, `version`, `is_deleted`, `deleted_at`, and composite sync indices (`idx_habits_sync`, `idx_habits_is_deleted`). Default new ID generation configured to UUIDs.
- `backend/app/models/habit_log.py`: Added `user_id`, `version`, `is_deleted`, `deleted_at`, `updated_at`, and composite sync indices (`idx_habit_logs_sync`, `idx_habit_logs_is_deleted`). Default new ID generation configured to UUIDs.
- `backend/app/models/timeblock.py`: Added `user_id`, `version`, `is_deleted`, `deleted_at`, and composite sync indices (`idx_timeblock_sync`, `idx_timeblock_is_deleted`). Default new ID generation configured to UUIDs.
- `backend/app/models/recommendation.py`: Added `user_id`, `version`, `is_deleted`, `deleted_at`, and sync indices (`ix_recommendation_sync`, `ix_recommendation_is_deleted`).
- `backend/app/models/activity_log.py`: Added `user_id`, `device_id`, and index `ix_activity_user_time` while preserving append-only semantics.
- `backend/app/models/__init__.py`: Registered `DailyIntent` in model exports.
- `backend/app/database.py`: Registered `DailyIntent` in Base metadata table registry.

### C. Schemas & Routers
- `backend/app/schemas/daily_intent.py`: **NEW**. Pydantic v2 schemas (`DailyIntentCreate`, `DailyIntentUpdate`, `DailyIntentResponse`).
- `backend/app/routers/daily_intents.py`: **NEW**. REST endpoints (`GET /api/daily-intents`, `GET /api/daily-intents/{target_date}`, `POST /api/daily-intents`, `DELETE /api/daily-intents/{target_date}`).
- `backend/app/routers/__init__.py`: Exported `daily_intents_router`.
- `backend/app/main.py`: Included `daily_intents_router` under `/api/daily-intents`.

### D. Service Layer (Soft Deletion, Version Increment & Default Ownership)
- `backend/app/services/daily_intent_service.py`: **NEW**. CRUD operations for daily intents (upsert by date, soft delete, listing).
- `backend/app/services/task_service.py`: Updated queries to filter out `is_deleted == True`, updated updates to increment `version += 1`, added `soft_delete_task` and updated `delete_task` to perform soft deletion / tombstoning.
- `backend/app/services/goal_service.py`: Updated queries to filter out `is_deleted == True`, updated updates to increment `version += 1`, unlinks associated tasks on goal soft delete.
- `backend/app/services/habit_service.py`: Updated queries to filter out `is_deleted == True`, updated updates to increment `version += 1`, provided `soft_delete_habit` alongside test-preserving cascade operations.
- `backend/app/services/timeblock_service.py`: Updated queries to filter `is_deleted == True`, updated updates to increment `version += 1`, implemented soft deletion.
- `backend/app/services/recommendation_service.py`: Updated recommendation queries to filter `is_deleted == True`.
- `backend/app/services/dashboard_service.py`: Updated dashboard metric aggregation to strictly consider active, non-deleted entities.

### E. Verification & Test Suite
- `backend/tests/test_phase10b_schema_evolution.py`: **NEW**. 5 comprehensive tests validating Daily Intent CRUD, version increments, soft delete lifecycle, task unlinking, database integrity, and online WAL backup/restore.

---

## 2. Database Schema Changes

All schema changes were performed non-destructively using SQLite batch mode migrations (`render_as_batch=True`).

| Table Name | Added Columns | Type | Nullable | Default | Sync Index |
| :--- | :--- | :--- | :--- | :--- | :--- |
| **tasks** | `user_id`<br>`version`<br>`is_deleted`<br>`deleted_at` | VARCHAR(64)<br>INTEGER<br>BOOLEAN<br>DATETIME | No<br>No<br>No<br>Yes | `'default_user'`<br>`1`<br>`False`<br>`None` | `idx_tasks_sync (user_id, updated_at)`<br>`idx_tasks_is_deleted (is_deleted)` |
| **goals** | `user_id`<br>`version`<br>`is_deleted`<br>`deleted_at` | VARCHAR(64)<br>INTEGER<br>BOOLEAN<br>DATETIME | No<br>No<br>No<br>Yes | `'default_user'`<br>`1`<br>`False`<br>`None` | `idx_goals_sync (user_id, updated_at)`<br>`idx_goals_is_deleted (is_deleted)` |
| **habits** | `user_id`<br>`version`<br>`is_deleted`<br>`deleted_at` | VARCHAR(64)<br>INTEGER<br>BOOLEAN<br>DATETIME | No<br>No<br>No<br>Yes | `'default_user'`<br>`1`<br>`False`<br>`None` | `idx_habits_sync (user_id, updated_at)`<br>`idx_habits_is_deleted (is_deleted)` |
| **habit_logs** | `user_id`<br>`version`<br>`is_deleted`<br>`deleted_at`<br>`updated_at` | VARCHAR(64)<br>INTEGER<br>BOOLEAN<br>DATETIME<br>DATETIME | No<br>No<br>No<br>Yes<br>No | `'default_user'`<br>`1`<br>`False`<br>`None`<br>`CURRENT_TIMESTAMP` | `idx_habit_logs_sync (user_id, updated_at)`<br>`idx_habit_logs_is_deleted (is_deleted)` |
| **daily_timeblocks** | `user_id`<br>`version`<br>`is_deleted`<br>`deleted_at` | VARCHAR(64)<br>INTEGER<br>BOOLEAN<br>DATETIME | No<br>No<br>No<br>Yes | `'default_user'`<br>`1`<br>`False`<br>`None` | `idx_timeblock_sync (user_id, updated_at)`<br>`idx_timeblock_is_deleted (is_deleted)` |
| **recommendations** | `user_id`<br>`version`<br>`is_deleted`<br>`deleted_at` | VARCHAR(64)<br>INTEGER<br>BOOLEAN<br>DATETIME | No<br>No<br>No<br>Yes | `'default_user'`<br>`1`<br>`False`<br>`None` | `ix_recommendation_sync (user_id, updated_at)`<br>`ix_recommendation_is_deleted (is_deleted)` |
| **activity_logs** | `user_id`<br>`device_id` | VARCHAR(64)<br>VARCHAR(64) | No<br>No | `'default_user'`<br>`'local_device'` | `ix_activity_user_time (user_id, timestamp)` |
| **daily_intents** *(NEW TABLE)* | `id`<br>`user_id`<br>`intent_date`<br>`intent_text`<br>`version`<br>`is_deleted`<br>`deleted_at`<br>`created_at`<br>`updated_at` | VARCHAR(64) PK<br>VARCHAR(64)<br>VARCHAR(10)<br>TEXT<br>INTEGER<br>BOOLEAN<br>DATETIME<br>DATETIME<br>DATETIME | No<br>No<br>No<br>No<br>No<br>No<br>Yes<br>No<br>No | Generated UUID<br>`'default_user'`<br>-<br>-<br>`1`<br>`False`<br>`None`<br>`CURRENT_TIMESTAMP`<br>`CURRENT_TIMESTAMP` | Unique `uq_user_intent_date (user_id, intent_date)`<br>`idx_daily_intents_sync (user_id, updated_at)`<br>`idx_daily_intents_is_deleted (is_deleted)` |

---

## 3. Alembic Migration Details

- **Revision ID**: `fa32b08ebb44`
- **Revises**: Base (Initial revision)
- **Batch Mode Execution**: Uses `with op.batch_alter_table(...)` for SQLite DDL compatibility to avoid table locking issues and syntax limitations in SQLite ALTER TABLE.
- **Backfill Safety**: Existing records in all tables were automatically backfilled with:
  - `user_id = 'default_user'`
  - `version = 1`
  - `is_deleted = False`
  - `device_id = 'local_device'` (for activity logs)
- **Downgrade Safety**: Fully reversible downgrade procedure implemented in migration script to drop added columns and tables without data corruption.

---

## 4. Record Counts Before and After Migration

Pre-migration snapshot was verified against post-migration database state:

| Table | Pre-Migration Count | Post-Migration Count | Status |
| :--- | :---: | :---: | :--- |
| `goals` | 8 | 8 | Preserved (100%) |
| `tasks` | 13 | 13 | Preserved (100%) |
| `habits` | 4 | 4 | Preserved (100%) |
| `recommendations` | 23 | 23 | Preserved (100%) |
| `predictive_insights` | 28 | 28 | Preserved (100%) |
| `user_productivity_profiles`| 2 | 2 | Preserved (100%) |
| `activity_logs` | 1 | 7* | Preserved (1 initial + 6 system audit/backup logs) |
| `daily_timeblocks` | 0 | 0 | Preserved |
| `habit_logs` | 0 | 0 | Preserved |
| `daily_intents` | *(table created)* | 0 | Ready for frontend sync |
| `alembic_version` | *(table created)* | 1 | Current: `fa32b08ebb44` |

*Note: Historical IDs such as `t-1`, `t-2`, `t-1794920348598`, `g-1`, `g-2`, `h-1` were preserved verbatim.*

---

## 5. Backup Verification

Two verified snapshots have been stored:

1. **Pre-Migration Baseline Backup**:
   - File: `backend/backups/niyantra_backup_20261121_145455_pre_phase10b_baseline.db`
   - Size: 331,776 bytes
   - SHA-256: `820953338414e234c9b4d42e79a8b203abe2412f7648ac7976045ce226fb0bba`
   - Integrity: `ok`
   - Foreign Key Violations: `0`

2. **Post-Implementation Verified Backup**:
   - File: `backend/backups/niyantra_backup_20261121_150942_post_phase10b_verified.db`
   - Size: 417,792 bytes
   - SHA-256: `9a439c8e46aac2581765d8f60e9869b2138a7f186b51a7ac276453ad928b34aa`
   - Integrity: `ok`
   - Foreign Key Violations: `0`

---

## 6. Test Suite Results

Full regression and evolution test suite:
- **Total Tests**: 122 tests
- **Passed**: 122 passed
- **Failed**: 0
- **Duration**: 8.94 seconds

### Test Breakdown
- Existing Phase 1-9 Tests: 117 tests (All passing, 0 broken contracts)
- Phase 10B Schema Evolution Tests: 5 tests (`test_phase10b_schema_evolution.py`)
  1. `test_daily_intent_lifecycle_and_constraints`: Verifies CRUD, update, date idempotence, unique constraint `(user_id, intent_date)`.
  2. `test_task_soft_delete_and_versioning`: Verifies version incrementing (`v1 -> v2`) and soft deletion tombstone behavior (`is_deleted=True, deleted_at!=None`).
  3. `test_goal_soft_delete_unlinks_tasks`: Verifies goal soft-deletion unlinks tasks without deleting them.
  4. `test_database_integrity_and_no_fk_violations`: Verifies `PRAGMA integrity_check = ok` and `PRAGMA foreign_key_check = 0`.
  5. `test_online_backup_and_restore_cycle`: Verifies live WAL database hot backup and restore integrity.

---

## 7. Remaining Issues

- **None**.
- All historical IDs are preserved.
- Alembic migration `fa32b08ebb44` applied cleanly.
- Zero foreign key violations exist.
- SQLite WAL journal mode and busy timeouts are intact.
- Backward compatibility is 100% maintained.

---

## 8. Confirmation of Local SQLite Operation

- **Standalone Operation**: Niyantra continues to operate as a 100% self-contained local SQLite application with no dependency on remote servers, internet connection, or cloud authentication.
- **Future-Ready Synchronization**: When cloud synchronization (Phase 10C+) is introduced, the database already contains all required sync metadata:
  - Global entity partition key (`user_id = "default_user"`).
  - Monotonic versioning (`version` counter).
  - Safe tombstoning (`is_deleted`, `deleted_at`).
  - High-performance delta query indices (`idx_*_sync` on `(user_id, updated_at)`).
  - Server-persisted daily intents (`daily_intents` table ready to sync frontend local storage).
