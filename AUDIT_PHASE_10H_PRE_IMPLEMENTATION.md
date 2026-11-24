# NIYANTRA — Phase 10H: Advanced Conflict Detection & Resolution
## Mandatory Pre-Implementation Audit

**Date:** November 22, 2026  
**Status:** Audit Complete  
**Scope:** Multi-Device Offline-First Conflict Detection, Preservation, and Resolution Architecture  
**Database Backup:** `backend/backups/niyantra_backup_20261122_152546_pre_phase10h.db` (Integrity: `ok`, Foreign Key Violations: `0`)

---

## 1. Executive Summary

In Phase 10G, NIYANTRA successfully established end-to-end multi-device push and pull synchronization between the client-side IndexedDB database and the FastAPI/SQLAlchemy cloud backend. In that phase, an initial conflict guard was implemented in `src/sync/syncManager.js`: when remote updates arrive for an entity that has active `PENDING` operations in `sync_queue`, the remote change is deferred and logged to `sync_meta` under a key prefixed with `conflict_` to prevent silent overwriting of local offline work.

However, full multi-device collaboration requires an **advanced, interactive, and reliable conflict detection, data preservation, and resolution system**. The pre-implementation audit examines existing capabilities, identifies gaps, and defines the structural additions required for Phase 10H.

---

## 2. Comprehensive System Audit

### 2.1 Backend Synchronization Models & APIs (Phase 10F)
- **Models:**
  - `SyncOperation`: Append-only log with monotonic integer ID (`id`), `operation_uuid` (idempotency key), `user_id`, `device_uuid`, `entity_type`, `entity_id`, `operation_type` (`CREATE`, `UPDATE`, `DELETE`), `entity_version`, `payload`, and `status` (`APPLIED`, `REJECTED`, `CONFLICT`, `SUPERSEDED`).
  - `SyncCursor`: Per-device checkpoints storing `last_pulled_cursor` and `last_pushed_cursor`.
  - `SyncEntityVersion`: Canonical server-side version for every entity per user, tracking `current_version`, `last_modified_device`, and `is_deleted` tombstone.
- **Push Endpoint (`POST /api/sync/push`):**
  - Enforces device validation and active status (rejects revoked devices).
  - Enforces user isolation (`user_id`).
  - Currently computes `target_version = max(sync_ev.current_version + 1, op_item.entity_version)` and applies updates.
  - **Gap Identified:** When client submits a conflict resolution, the server must validate that the resolution is properly authorized, update the canonical `current_version` with a superseding version, and broadcast the resolved version to all other registered devices via the append-only `sync_operations` log.
  - **Gap Identified:** Add a dedicated server-side `SyncConflict` model and audit API (`/api/sync/conflicts`) so that conflicts detected or resolved across devices can be audited, tracked, and isolated per user account.

### 2.2 Push/Pull Synchronization Engine (Phase 10G)
- **`syncManager.pushChanges()`:**
  - Drains `sync_queue` items in batches of 50.
  - Retries failed operations with exponential backoff (`initialBackoffMs: 2000`, `maxRetries: 5`).
  - Preserves operation IDs across retry attempts for idempotency.
- **`syncManager.pullChanges()`:**
  - Queries `GET /api/sync/pull` using `exclude_self=true` to prevent downloading own operations.
  - Dispatches remote changes with `{ trackChange: false }` to avoid infinite ping-pong sync loops.
  - Advance cursor and sends acknowledgement `POST /api/sync/acknowledge` only after successful local IndexedDB writes.
- **Existing Conflict Behavior in Phase 10G:**
  - When pulling, if `syncQueue` has a `PENDING` record for `[userId, entityType, entityId]`, the change was deferred and a simple JSON stub was saved in `sync_meta`:
    ```json
    { "entityType": "task", "entityId": "123", "remoteVersion": 2, "localPendingCount": 1 }
    ```
  - **Gaps Identified:**
    1. The stub in `sync_meta` is ephemeral and overwritten per key. It lacks first-class lifecycle states (`DETECTED`, `PENDING_RESOLUTION`, `RESOLVED_LOCAL`, `RESOLVED_REMOTE`, `RESOLVED_MERGED`).
    2. Base version and local data snapshot are not systematically preserved alongside remote data.
    3. No mechanism exists to resolve conflicts, choose local/remote winners, or perform manual 3-way/field-level merges.
    4. Deferral without resolution leaves pending items blocking further remote synchronization indefinitely.

### 2.3 IndexedDB Database Schema & Repositories (Phase 10D / 10E)
- **Current Version:** `DB_VERSION = 2`.
- **Existing Tables:** `tasks`, `goals`, `habits`, `habit_logs`, `daily_timeblocks`, `daily_intents`, `activity_logs`, `recommendations`, `sync_meta`, `sync_queue`.
- **Versioning Invariant:** All entity repositories support `version`, `isDeleted`, `updatedAt`, `deletedAt`, and accept `options.trackChange !== false`.
- **Gap Identified:** IndexedDB requires `DB_VERSION = 3` to introduce a dedicated `conflicts` table:
  ```javascript
  conflicts: 'id, entityType, entityId, status, detectedAt, resolvedAt, [status+entityType], [userId+status], [userId+entityType+entityId]'
  ```
  This provides indexed querying by user, status, and entity type, enabling fast conflict listing, filtering, and history lookups.

### 2.4 Entity-Specific Conflict Nuances
1. **Tasks:** Fields include `title`, `description`, `taskType`, `priority`, `status`, `category`, `startDate`, `dueDate`, `goalId`, `completedAt`. Field-level merging allows combining non-conflicting fields (e.g., local priority change + remote due date change).
2. **Goals:** Fields include `title`, `description`, `targetDate`, `category`, `priority`, `status`, `progressPercentage`. Relationship safety is paramount: if a goal is remotely deleted, local child tasks referencing that goal must have `goalId` safely handled or retained.
3. **Habits & Habit Logs:** Habit logs are unique by `[habit_id, log_date]`. For simultaneous logs on the same date, safe deduplication must preserve completion (`completed = local.completed || remote.completed`) and combine notes.
4. **Daily Timeblocks:** Fields include `blockDate`, `title`, `time`, `durationMinutes`, `actualDurationMinutes`, `category`, `status`, `taskId`.
5. **Daily Intents:** Unique per day `[user_id, intent_date]`. Merge allows text reconciliation without duplicating calendar entries.
6. **Activity Logs:** Append-only event history. Conflicts must NEVER discard activity entries; deduplicate by UUID and preserve all historical events.
7. **Recommendations:** Fields include `status`, `actionPayload`.

### 2.5 Deletion Conflicts (Update vs. Delete & Delete vs. Update)
- If Device A updates an entity while Device B deletes it:
  - If user chooses **Keep Local (Update)**: The entity is restored/undeleted (`isDeleted = 0`, `deletedAt = null`) with an incremented version, and pushed to the cloud backend.
  - If user chooses **Keep Remote (Delete)**: The local deletion tombstone is confirmed (`isDeleted = 1`), local pending updates are marked superseded, and no resurrected entity remains.
- If Device A deletes an entity while Device B updates it:
  - If user chooses **Keep Local (Delete)**: The local deletion is confirmed with an incremented version.
  - If user chooses **Keep Remote (Restore & Update)**: The remote update payload is applied and the entity is undeleted locally.

### 2.6 Frontend Conflict Experience Gaps
- Currently, there is no UI indicator when conflicts occur.
- No visual comparison interface exists to inspect local vs. remote vs. base versions.
- No controls exist for "Keep Local", "Keep Remote", or "Manual Field Merge".
- Users have no visibility into conflict history or resolution outcomes.

---

## 3. Architecture Specification for Phase 10H

```
+-------------------------------------------------------------------------+
|                         NIYANTRA Phase 10H Architecture                  |
+-------------------------------------------------------------------------+
|                                                                         |
|  [ Remote Change Arrives via Pull ]                                    |
|                  |                                                      |
|                  v                                                      |
|        [ Has Pending Local Edit in sync_queue? ]                        |
|             /                         \                                 |
|          NO                            YES                              |
|           |                              |                              |
|           v                              v                              |
|  [ Apply Remote Change ]     [ Conflict Detector Triggers ]             |
|  (trackChange: false)                    |                              |
|                                          v                              |
|                           [ Snapshot 3-Way Versions ]                   |
|                           - Local Version + Pending Op                  |
|                           - Remote Version + Origin Device              |
|                           - Base Version (Pre-edit)                     |
|                                          |                              |
|                                          v                              |
|                           [ Store in IndexedDB 'conflicts' ]            |
|                           (status: PENDING_RESOLUTION)                  |
|                                          |                              |
|                                          v                              |
|                           [ UI Conflict Indicator Alert ]               |
|                                          |                              |
|                                          v                              |
|                           [ User Resolution Flow ]                      |
|                           +-----------------------+                     |
|                           | A. Keep Local         |                     |
|                           | B. Keep Remote        |                     |
|                           | C. Manual Field Merge |                     |
|                           +-----------------------+                     |
|                                          |                              |
|                                          v                              |
|                           [ Conflict Resolver Service ]                 |
|                           - Mark Conflict RESOLVED                      |
|                           - Update Local Repository                     |
|                           - Queue Bumped Version Op                     |
|                           - Trigger Outgoing Push                       |
|                                          |                              |
|                                          v                              |
|                           [ Cloud Backend Sync Server ]                 |
|                           - Validates User & Device                     |
|                           - Applies Winner Mutation                     |
|                           - Bumps Canonical Version                     |
|                           - Broadcasts to Other Devices                 |
+-------------------------------------------------------------------------+
```

---

## 4. Verification Checkpoints

1. SQLite Database integrity: `ok`, 0 foreign key violations.
2. Verified pre-Phase 10H backup safely created.
3. IndexedDB schema version upgrade (v2 -> v3) with zero data loss.
4. Non-breaking compatibility with all existing 150 backend tests and 50 frontend tests.
5. All 15 required conflict scenarios verified via comprehensive automated test suites.
