# NIYANTRA — Phase 10G: Pre-Implementation Compatibility Audit

**Date:** November 22, 2026  
**Auditor:** Antigravity Engineering  
**Scope:** Client-to-Cloud Push/Pull Synchronization Infrastructure  

---

## 1. Backend Synchronization Inspection (Phase 10F)

| Component | Inspection Finding | Compatibility Assessment |
|---|---|---|
| **`POST /api/sync/push`** | Expects `SyncPushRequest(device_uuid, operations: [SyncOperationItem])`. Enforces strict JWT auth (`get_current_user`) and non-revoked device ownership via `X-Device-UUID` or `device_uuid` body. | **100% Compatible.** Payload structure matches `syncService.js`. |
| **`GET /api/sync/pull`** | Accepts `cursor` (int, ge=0), `limit` (int, 1-100), `exclude_self` (bool), `device_uuid` query/header. Returns `{ changes: [...], next_cursor, has_more, server_timestamp }` ordered by monotonic `SyncOperation.id ASC`. | **100% Compatible.** Sequence ID guarantees total order across multi-device transactions. |
| **`POST /api/sync/acknowledge`** | Accepts `{ cursor: int, device_uuid: str }`. Updates `SyncCursor.last_pulled_cursor = max(current, cursor)` atomically. | **100% Compatible.** |
| **`GET /api/sync/status`** | Returns pending pull counts, latest server cursor, registered device count, and active device state. | **100% Compatible.** |
| **Idempotency Gate** | Checks `(operation_uuid, user_id)` in `sync_operations`. If duplicate, returns previous `APPLIED` result without re-executing entity mutation. | **100% Compatible.** Retrying network timeouts or browser restarts will never cause duplicate entity creation. |
| **Supported Entity Types** | `task`, `goal`, `habit`, `habit_log`, `daily_timeblock`, `timeblock`, `daily_intent`, `recommendation`, `activity_log`. | **100% Match.** Mirrors frontend `ENTITY_TYPES` in `syncConstants.js`. |

---

## 2. Frontend Client Storage Inspection (Phases 10D & 10E)

| Component | Inspection Finding | Compatibility Assessment |
|---|---|---|
| **Dexie Schema (`DB_VERSION = 2`)** | Tables: `tasks`, `goals`, `habits`, `habit_logs`, `daily_timeblocks`, `daily_intents`, `activity_logs`, `recommendations`, `sync_meta`, `sync_queue`. | **100% Compatible.** No schema migration needed; `sync_meta` and `sync_queue` exist with compound indices. |
| **Durable Queue (`sync_queue`)** | Records have `id`, `operationId`, `userId`, `deviceUuid`, `entityType`, `entityId`, `operation`, `status`, `entityVersion`, `payload`, `createdAt`, `nextRetryAt`. | **100% Compatible.** Field names cleanly map to `SyncOperationItem` (`operation_uuid: op.operationId`). |
| **Change Tracker & Repositories** | All repositories (`taskRepository`, `goalRepository`, etc.) accept `options = { trackChange: true }`. If `options.trackChange === false`, mutations write to Dexie without enqueuing into `sync_queue`. | **CRITICAL ENABLER.** When pulling remote changes, calling repositories with `{ trackChange: false }` guarantees zero outgoing queue echo loops. |
| **Device Identification** | `getOrCreateDeviceUUID()` in `src/utils/deviceUtils.js` stores hardware UUID in localStorage. | **100% Compatible.** Passed as `X-Device-UUID` to backend. |
| **Authentication State** | Token stored in `localStorage.getItem('niyantra_access_token')`. | **100% Compatible.** When token is absent (guest mode), sync gracefully pauses without network errors. |
| **Network Reachability** | `src/utils/networkUtils.js` provides `currentIsOnline`, `probeBackendReachability()`, and event listeners. | **100% Compatible.** Directly usable for automatic sync triggers. |

---

## 3. Potential Compatibility Risks & Mitigations

1. **Risk — Echo Loops:** A remote change pulled from the server could trigger `changeTracker.recordChange()`, creating an infinite outgoing ping-pong loop between devices.  
   *Mitigation:* Apply all incoming pull mutations with `{ trackChange: false }`.
2. **Risk — Concurrent Push Collision:** Multiple triggers (e.g., timer + tab focus + local mutation) firing simultaneously could send duplicate queue items.  
   *Mitigation:* Implement a mutex / execution lock in `syncManager` (`isSyncing`, `isPushing`, `isPulling`).
3. **Risk — Overwriting Local Unsynced Changes (Conflict Safety):** If Device A edits Task 1 while offline, and Device B pushed an update to Task 1, Device A pulling before pushing could overwrite Device A's local unsynced edits.  
   *Mitigation:* Check `syncQueue` for pending mutations on `(entityType, entityId)` before applying remote changes. If pending, defer remote application and record conflict entry in `sync_meta`.
4. **Risk — Unauthenticated Guest Mode:** If user runs Niyantra without logging in, API calls to `/api/sync/*` return 401.  
   *Mitigation:* If `token` is null, set sync status to `LOCAL_ONLY` and skip cloud push/pull until user logs in.
