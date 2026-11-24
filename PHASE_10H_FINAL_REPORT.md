# NIYANTRA — PHASE 10H FINAL IMPLEMENTATION REPORT
## Advanced Conflict Detection & Resolution

**Date:** November 22, 2026  
**Status:** Completed & Fully Verified  
**Architecture:** Offline-First, Multi-Device Productivity System with 3-Way Conflict Resolution  
**Verification Results:**  
- **Frontend Test Suite:** 66 / 66 Passed (100%) in 949ms  
  - `tests/conflictResolution.test.js`: 16 / 16 Passed (All 16 scenarios verified)  
  - `tests/syncManager.test.js`: 14 / 14 Passed  
  - `tests/syncQueue.test.js`: 17 / 17 Passed  
  - `tests/indexeddb.test.js`: 19 / 19 Passed  
- **Backend Test Suite:** 157 / 157 Passed (100%) in 18.42s  
  - `backend/tests/test_phase10h_conflicts.py`: 7 / 7 Passed  
  - `backend/tests/test_phase10f_sync.py`: 16 / 16 Passed  
  - Full Regression Matrix: 134 / 134 Passed  
- **Production Build:** Vite v8.3.8 compiled cleanly in 1.25s (0 errors)  
- **Database Integrity:** SQLite `integrity_check` = `ok`  
- **Foreign Key Constraints:** 0 violations  
- **Database Backups:**  
  - Pre-Phase 10H: `backend/backups/niyantra_backup_20261122_152546_pre_phase10h.db`  
  - Post-Phase 10H Verified: `backend/backups/niyantra_backup_20261122_154556_post_phase10h_verified.db`  

---

## 1. Pre-Implementation Audit Summary

A mandatory audit was conducted across existing sync engines, database repositories, and backend APIs before making code modifications (documented in [AUDIT_PHASE_10H_PRE_IMPLEMENTATION.md](file:///c:/Users/nitya/OneDrive/Attachments/Desktop/NIYAM/Niyantra/AUDIT_PHASE_10H_PRE_IMPLEMENTATION.md)):

1. **Phase 10G Baseline:**
   - In Phase 10G, a baseline conflict stub was introduced in `syncManager.pullChanges()` that checked whether `sync_queue` contained `PENDING` edits for `[userId, entityType, entityId]`. When true, incoming remote changes were deferred, logging a lightweight key into `sync_meta`.
2. **Identified Deficiencies & Gaps:**
   - **Ephemeral Metadata:** Storing conflict notices under `conflict_${entityType}_${entityId}` in `sync_meta` did not support lifecycle states, multi-device device identifiers, base version snapshots, or resolution audit trails.
   - **No Resolution Mechanism:** Without an interactive resolution engine, deferred changes accumulated, blocking ongoing delta synchronization for affected entities.
   - **Lack of Structured Preservation:** Silent overwrites were prevented by deferral, but 3-way data (base, local, remote) was not preserved systematically.
   - **Server-Side Tracking:** The cloud backend had no dedicated table or endpoints for tracking or auditing unresolved conflicts per user account.
3. **Audit Outcomes:**
   - Designed a dedicated IndexedDB table `conflicts` (Schema Version 3).
   - Designed server-side SQLAlchemy model `SyncConflict` and migration `8b9c0d1e2f3a_phase10h_conflict_management.py`.
   - Designed 3 core resolution strategies: Keep Local, Keep Remote, and Manual Merge.

---

## 2. Conflict Detection Architecture

The conflict detection engine is implemented in `src/sync/conflictDetector.js` and tightly integrated into `src/sync/syncManager.js`:

```
Incoming Remote Change (Pull)
            │
            ▼
┌────────────────────────────────────────────────────────┐
│             conflictDetector.detectConflict()          │
└────────────────────────────────────────────────────────┘
            │
  Does local sync_queue contain PENDING edits?
  OR does local entity version supersede remote version?
  OR does operation collide (Update vs Delete)?
            │
     ┌──────┴──────┐
     │             │
    YES            NO
     │             │
     │             ▼
     │      Apply remote mutation directly
     │      with { trackChange: false }
     ▼
┌────────────────────────────────────────────────────────┐
│             conflictDetector.recordConflict()          │
│ - Snapshots Local Data, Remote Data, Base Version      │
│ - Records Originating Device UUIDs & Timestamps        │
│ - Sets status = PENDING_RESOLUTION                     │
│ - Emits real-time notification to UI listeners         │
└────────────────────────────────────────────────────────┘
```

### Detection Triggers
1. **Concurrent Offline Modifications:** Remote delta arrives for an entity while unpushed `PENDING` mutations exist in `sync_queue`.
2. **Update vs. Remote Deletion:** Remote operation is `DELETE` while local device has pending updates, or vice versa (`localOperation === 'DELETE'` while remote is `UPDATE`).
3. **Stale Remote Version:** Remote delta arrives with version lower than locally upgraded entity.
4. **Idempotency Guarantee:** If a duplicate operation arrives, `recordConflict` reuses the active conflict ID rather than creating duplicate unresolved conflicts.

---

## 3. Conflict Storage Schema

### Client-Side IndexedDB (`conflicts` table - DB_SCHEMA_V3)
Defined in `src/database/schema.js` and initialized in `src/database/db.js`:
```javascript
export const DB_SCHEMA_V3 = {
  ...DB_SCHEMA_V2,
  conflicts:
    'id, entityType, entityId, status, detectedAt, resolvedAt, [status+entityType], [userId+status], [userId+entityType+entityId]',
};
```

**Conflict Record Structure:**
```typescript
interface ConflictRecord {
  id: string;                      // Unique UUIDv4
  userId: string;                  // User account ID (tenant isolation)
  entityType: string;              // 'task' | 'goal' | 'habit' | 'habit_log' | 'daily_timeblock' | 'daily_intent' | 'recommendation' | 'activity_log'
  entityId: string;                // Primary identifier of target entity
  status: string;                  // 'PENDING_RESOLUTION' | 'RESOLVED_LOCAL' | 'RESOLVED_REMOTE' | 'RESOLVED_MERGED'
  reason: string;                  // 'CONCURRENT_OFFLINE_EDITS' | 'UPDATE_VS_DELETE' | 'STALE_REMOTE_VERSION'
  baseVersion: number;             // Pre-divergence common ancestor version
  localVersion: number;            // Local entity version
  remoteVersion: number;           // Incoming remote version
  localOperation: string;          // 'UPDATE' | 'DELETE' | 'CREATE'
  remoteOperation: string;         // 'UPDATE' | 'DELETE'
  localOperationId: string | null; // Idempotency token of local edit
  remoteOperationId: string | null;// Idempotency token of remote change
  localDeviceUuid: string;         // Device UUID where local edit occurred
  remoteDeviceUuid: string;        // Originating remote device UUID
  localData: Record<string, any>;  // Full snapshot of local entity attributes
  remoteData: Record<string, any>; // Full snapshot of incoming remote attributes
  baseData: Record<string, any> | null;
  detectedAt: string;              // ISO 8601 timestamp
  updatedAt: string;               // ISO 8601 timestamp
  resolvedAt: string | null;       // ISO 8601 timestamp
  resolutionStrategy: string | null;// 'KEEP_LOCAL' | 'KEEP_REMOTE' | 'MANUAL_MERGE'
  resolvedData: Record<string, any> | null; // Winning or merged attribute payload
}
```

### Server-Side SQLAlchemy Model (`sync_conflicts` table)
Defined in `backend/app/models/sync.py`:
- `id` (String(64), Primary Key)
- `user_id` (String(64), Foreign Key to `users.id` with `ondelete="CASCADE"`)
- `entity_type` (String(32), Indexed)
- `entity_id` (String(64), Indexed)
- `base_version` (Integer)
- `local_version` (Integer)
- `remote_version` (Integer)
- `detecting_device_uuid` (String(64))
- `conflicting_device_uuid` (String(64), Nullable)
- `status` (String(32), Indexed)
- `resolution_strategy` (String(32), Nullable)
- `local_data` (JSON)
- `remote_data` (JSON)
- `resolved_data` (JSON)
- `detected_at` (DateTime(timezone=True))
- `resolved_at` (DateTime(timezone=True), Nullable)

---

## 4. Conflict Resolution Strategies

The resolution engine in `src/sync/conflictResolver.js` implements three deterministic strategies:

### A. Keep Local
- **Concept:** Local offline changes are chosen as the definitive winner.
- **Version Assignment:** Computes `winningVersion = Math.max(localVersion, remoteVersion) + 1`.
- **Queue Transition:** Updates any existing pending queue operation for this entity to the winning version, or enqueues a new operation if none exists.
- **Lifecycle Transition:** Transitions conflict state to `RESOLVED_LOCAL`, records `resolvedData = localData` and `resolvedAt = now`.
- **Propagation:** When pushed, the server applies the winning version and broadcasts it to all other devices.

### B. Keep Remote
- **Concept:** Remote incoming change is accepted, abandoning local edits.
- **Queue Transition:** Marks any pending local operations for this entity as `SUPERSEDED` so they will **never** be pushed to overwrite the server.
- **Local Application:** Applies the remote payload to the local repository using `{ trackChange: false }`.
- **Deletion Safety:** If the remote operation was `DELETE`, applies soft-deletion locally (`isDeleted = 1`, `deletedAt = now`).
- **Lifecycle Transition:** Transitions conflict state to `RESOLVED_REMOTE`, records `resolvedData = remoteData`.

### C. Manual Merge
- **Concept:** Granular field-level combination tailored to each entity schema.
- **Version Assignment:** Assigns `winningVersion = Math.max(localVersion, remoteVersion) + 1`.
- **Validation & Domain Merging:**
  - Tasks: combines `title`, `description`, `priority`, `status`, `category`, `dueDate`, `startDate`, `goalId`.
  - Goals: combines `title`, `description`, `targetDate`, `priority`, `status`, `progress`.
  - Habits: combines `name`, `frequency`, `category`, `baseStreak`, `archived`.
  - Habit Logs: deduplicates by `[habitId, logDate]`, unions completion booleans (`local.completed || remote.completed`), merges notes.
  - Daily Timeblocks: reconciles `title`, `time`, `durationMinutes`, `category`, `status`, `taskId`.
- **Local Application:** Saves merged record with `winningVersion`.
- **Queue Transition:** Marks older pending operations as `SUPERSEDED` and enqueues a single clean `UPDATE` operation with the merged payload and `winningVersion`.
- **Lifecycle Transition:** Transitions conflict state to `RESOLVED_MERGED`, records `resolvedData = mergedData`.

---

## 5. Server-Side Consistency & API Endpoints

The backend was extended cleanly without altering existing APIs:

| HTTP Method | Path | Summary | Authentication & Authorization |
|---|---|---|---|
| `GET` | `/api/sync/conflicts` | List unresolved and resolved conflicts | JWT required; strictly scoped to `current_user.id` |
| `POST` | `/api/sync/conflicts/record` | Register detected conflict from client | JWT + Active Device required |
| `POST` | `/api/sync/conflicts/{id}/resolve` | Record conflict resolution on server | JWT + Active Device; checks ownership; rejects cross-tenant |

### Security Invariants Enforced:
1. **Tenant Isolation:** If Device B attempts to resolve a conflict belonging to User A, the server rejects the request with `HTTP 403 Forbidden` (`"Conflict belongs to a different account. Cross-tenant conflict resolution is forbidden."`).
2. **Device Active Check:** Revoked devices attempting to access conflict endpoints are immediately rejected with `HTTP 403 Forbidden`.
3. **Database Transactions:** Server-side resolutions use explicit SQLAlchemy transaction commit and rollback guards.
4. **Broadcast Integration:** Resolving with `KEEP_LOCAL` or `MANUAL_MERGE` appends an entry to `SyncOperation` and increments `SyncEntityVersion.current_version`, broadcasting the resolved state to all registered devices on their subsequent pull.

---

## 6. Frontend Conflict Experience

Conflict handling was integrated into the existing UI layout without invasive redesign:

### 1. Conflict Indicator in `Navbar.jsx` & `MobileHeader.jsx`
- When `conflictCount > 0`, an animated amber badge appears:
  - Desktop: `<AlertTriangle /> <span>{count} Conflict(s)</span>`
  - Mobile: Icon button with warning badge in the mobile header.
- Real-time updates via `registerConflictListener` and `useSyncStatus`.

### 2. Side-by-Side Diff & Resolution Modal (`ConflictResolutionModal.jsx`)
- **Unresolved Conflicts Tab:**
  - Item selector list showing entity type, title/ID, and detection timestamp.
  - Side-by-side comparison table:
    - Left Column: Field name.
    - Middle Column: Local Device state (v{localVersion}) with laptop badge.
    - Right Column: Remote Device state (v{remoteVersion}) with phone badge.
    - Divergent fields highlighted in gentle amber.
  - Action Controls:
    - **Keep Local:** Green outline button to retain local state.
    - **Keep Remote:** Emerald button to adopt remote state.
    - **Custom Merge:** Opens inline field-level inputs and "Use Remote" quick-pick chips.
    - **Save & Synchronize Merge:** Confirms resolution and triggers background push.
- **Resolution History Tab:**
  - Auditable log of previously resolved conflicts with resolution strategy, timestamp, and status badge.

---

## 7. Synchronization Behavior After Resolution

1. **Resolution Execution:**
   - User clicks resolution action ("Keep Local", "Keep Remote", or "Save Merge").
   - `conflictResolver.resolveConflict()` executes atomically on client IndexedDB.
   - Pending operations are updated or superseded; winning version is set to `max(vLocal, vRemote) + 1`.
2. **Immediate Push Trigger:**
   - Background push (`syncManager.pushChanges()`) transmits winning mutation to cloud server.
3. **Zero Echo Loops:**
   - Local records written via `Keep Remote` use `{ trackChange: false }`, ensuring no spurious outgoing sync operations are generated.
   - Local pending operations are marked `SUPERSEDED`, preventing stale overwrites.
4. **Propagation to Other Devices:**
   - The cloud server records the resolved operation in `sync_operations` with incremented `entity_version`.
   - All other devices pulling with `exclude_self=true` download the clean winner without triggering further conflicts.

---

## 8. Files Created and Modified

### Created Files
- [src/sync/conflictDetector.js](file:///c:/Users/nitya/OneDrive/Attachments/Desktop/NIYAM/Niyantra/src/sync/conflictDetector.js): 3-way conflict detection, persistence, listeners, and counts.
- [src/sync/conflictResolver.js](file:///c:/Users/nitya/OneDrive/Attachments/Desktop/NIYAM/Niyantra/src/sync/conflictResolver.js): Keep Local, Keep Remote, Manual Merge, and entity merge helpers.
- [src/components/common/ConflictResolutionModal.jsx](file:///c:/Users/nitya/OneDrive/Attachments/Desktop/NIYAM/Niyantra/src/components/common/ConflictResolutionModal.jsx): Side-by-side diff comparison, field merge UI, and resolution history.
- [backend/alembic/versions/8b9c0d1e2f3a_phase10h_conflict_management.py](file:///c:/Users/nitya/OneDrive/Attachments/Desktop/NIYAM/Niyantra/backend/alembic/versions/8b9c0d1e2f3a_phase10h_conflict_management.py): Alembic migration creating `sync_conflicts` table.
- [backend/tests/test_phase10h_conflicts.py](file:///c:/Users/nitya/OneDrive/Attachments/Desktop/NIYAM/Niyantra/backend/tests/test_phase10h_conflicts.py): Backend conflict tests.
- [tests/conflictResolution.test.js](file:///c:/Users/nitya/OneDrive/Attachments/Desktop/NIYAM/Niyantra/tests/conflictResolution.test.js): 16 comprehensive automated multi-device conflict scenarios.
- [AUDIT_PHASE_10H_PRE_IMPLEMENTATION.md](file:///c:/Users/nitya/OneDrive/Attachments/Desktop/NIYAM/Niyantra/AUDIT_PHASE_10H_PRE_IMPLEMENTATION.md): Pre-implementation audit report.

### Modified Files
- [src/database/schema.js](file:///c:/Users/nitya/OneDrive/Attachments/Desktop/NIYAM/Niyantra/src/database/schema.js): Bumped schema to `DB_VERSION = 3` with `conflicts` table.
- [src/database/db.js](file:///c:/Users/nitya/OneDrive/Attachments/Desktop/NIYAM/Niyantra/src/database/db.js): Bound `this.conflicts` table.
- [src/sync/syncConstants.js](file:///c:/Users/nitya/OneDrive/Attachments/Desktop/NIYAM/Niyantra/src/sync/syncConstants.js): Added `CONFLICT_STATUS`, `RESOLUTION_STRATEGY`, and `CONFLICT_COUNT`.
- [src/sync/syncManager.js](file:///c:/Users/nitya/OneDrive/Attachments/Desktop/NIYAM/Niyantra/src/sync/syncManager.js): Integrated `conflictDetector.detectConflict` and `conflictCount` in summary.
- [src/sync/syncStatus.js](file:///c:/Users/nitya/OneDrive/Attachments/Desktop/NIYAM/Niyantra/src/sync/syncStatus.js): Added conflict listener and real-time state tracking.
- [src/sync/index.js](file:///c:/Users/nitya/OneDrive/Attachments/Desktop/NIYAM/Niyantra/src/sync/index.js): Exported conflict detector, resolver, and helpers.
- [src/database/repositories/taskRepository.js](file:///c:/Users/nitya/OneDrive/Attachments/Desktop/NIYAM/Niyantra/src/database/repositories/taskRepository.js): Preserved explicit versions on remote apply.
- [src/database/repositories/goalRepository.js](file:///c:/Users/nitya/OneDrive/Attachments/Desktop/NIYAM/Niyantra/src/database/repositories/goalRepository.js): Preserved explicit versions and unified progress fields.
- [src/database/repositories/habitRepository.js](file:///c:/Users/nitya/OneDrive/Attachments/Desktop/NIYAM/Niyantra/src/database/repositories/habitRepository.js): Preserved explicit versions on remote apply.
- [src/components/layout/Navbar.jsx](file:///c:/Users/nitya/OneDrive/Attachments/Desktop/NIYAM/Niyantra/src/components/layout/Navbar.jsx): Added conflict pill and resolution modal.
- [src/components/layout/MobileHeader.jsx](file:///c:/Users/nitya/OneDrive/Attachments/Desktop/NIYAM/Niyantra/src/components/layout/MobileHeader.jsx): Added mobile conflict indicator and modal.
- [backend/app/models/sync.py](file:///c:/Users/nitya/OneDrive/Attachments/Desktop/NIYAM/Niyantra/backend/app/models/sync.py): Added `SyncConflict` model.
- [backend/app/models/user.py](file:///c:/Users/nitya/OneDrive/Attachments/Desktop/NIYAM/Niyantra/backend/app/models/user.py): Added `sync_conflicts` relationship.
- [backend/app/models/__init__.py](file:///c:/Users/nitya/OneDrive/Attachments/Desktop/NIYAM/Niyantra/backend/app/models/__init__.py): Exported `SyncConflict`.
- [backend/app/schemas/sync.py](file:///c:/Users/nitya/OneDrive/Attachments/Desktop/NIYAM/Niyantra/backend/app/schemas/sync.py): Added conflict request/response schemas.
- [backend/app/schemas/__init__.py](file:///c:/Users/nitya/OneDrive/Attachments/Desktop/NIYAM/Niyantra/backend/app/schemas/__init__.py): Exported conflict schemas.
- [backend/app/services/sync_service.py](file:///c:/Users/nitya/OneDrive/Attachments/Desktop/NIYAM/Niyantra/backend/app/services/sync_service.py): Added conflict service handlers.
- [backend/app/routers/sync.py](file:///c:/Users/nitya/OneDrive/Attachments/Desktop/NIYAM/Niyantra/backend/app/routers/sync.py): Added conflict REST endpoints.

---

## 9. Backend Test Results

Ran `pytest backend/tests/ -q`:
```
........................................................................ [ 45%]
........................................................................ [ 91%]
.............                                                            [100%]
157 passed, 1 warning in 18.42s
```
- Total test files: 21
- Total tests passed: **157 / 157 (100%)**
- Zero failures, zero regressions across tasks, goals, habits, analytics, predictive models, adaptive profiles, and sync APIs.

---

## 10. Frontend Test Results

Ran `npm run test:frontend`:
```
 ✓ tests/syncManager.test.js (14 tests) 112ms
 ✓ tests/syncQueue.test.js (17 tests) 99ms
 ✓ tests/indexeddb.test.js (19 tests) 115ms
 ✓ tests/conflictResolution.test.js (16 tests) 141ms

 Test Files  4 passed (4)
      Tests  66 passed (66)
   Duration  949ms
```
- Total test files: 4
- Total tests passed: **66 / 66 (100%)**
- All 16 conflict scenarios verified.

---

## 11. Multi-Device Conflict Scenarios Verification Matrix

| # | Scenario | Mechanism | Result |
|---|---|---|---|
| 1 | Two devices updating same task | Concurrent offline edit detection; both versions preserved | Passed |
| 2 | Local update vs remote deletion | Update vs Delete detection; local data preserved | Passed |
| 3 | Local deletion vs remote update | Update vs Delete detection; tombstone preserved | Passed |
| 4 | Simultaneous goal modifications | Goal progress & date collision detected without loss | Passed |
| 5 | Conflicting habit changes | Name & streak divergence detected without loss | Passed |
| 6 | Duplicate operation delivery | Reuses active conflict ID; idempotent duplicate ignored | Passed |
| 7 | Stale entity versions | Stale incoming remote version detected | Passed |
| 8 | Manual merge | Combines local priority + remote due date; bumps version | Passed |
| 9 | Keep Local | Retains local version; queues bumped version for push | Passed |
| 10 | Keep Remote | Adopts remote version; local pending ops superseded | Passed |
| 11 | Account isolation | User B blocked from resolving User A's conflicts (HTTP 403) | Passed |
| 12 | Device revocation | Revoked device blocked from sync and conflict resolution | Passed |
| 13 | Interrupted conflict resolution | Status remains PENDING_RESOLUTION across interruption | Passed |
| 14 | Conflict propagation to 3rd device | Resolved winner propagates cleanly to Device C | Passed |
| 15 | Restart recovery | Conflict state and queue persist across DB restart | Passed |
| 16 | Historical conflict preservation | Full resolution history queryable with strategy & data | Passed |

---

## 12. Database Integrity Results

- SQLite PRAGMA `integrity_check`: **`ok`**
- SQLite PRAGMA `foreign_key_check`: **`0 errors`**
- All existing production user records, tasks, goals, habits, and activity logs remain fully intact.
- Migration `8b9c0d1e2f3a_phase10h_conflict_management` verified at head.

---

## 13. Remaining Limitations

1. **Automated Merging Heuristics:** Complex rich-text or markdown task descriptions are currently resolved via field replacement or user manual edit rather than operational transformation / CRDT character-level diffing.
2. **Bulk Conflict Actions:** Conflicts are currently resolved on an individual item basis; batch "Accept All Remote" or "Keep All Local" operations can be considered for future phases.
3. **Network Transport:** Tests simulate multi-device synchronization using separate IndexedDB instances connected to the shared API server. Production deployment across physical devices will depend on standard internet connectivity and reverse-proxy setups.
