# NIYANTRA — Phase 10I: Background Synchronization, Reliability & Recovery
## Mandatory Pre-Implementation Audit Report

**Date:** November 22, 2026  
**Status:** Audit Complete  
**Scope:** Background Synchronization, Fault Tolerance, Multi-Tab Coordination, Storage Health, and Failure Recovery  
**Database Backup:** `backend/backups/niyantra_backup_20261122_155025_pre_phase10i.db` (Integrity: `ok`, Foreign Key Violations: `0`)

---

## 1. Executive Summary

Phases 10A through 10H successfully established Niyantra's offline-first foundation:
- Non-breaking database schemas with UUIDs and monotonic versioning (Phase 10B).
- Authentication and multi-device identity management (Phase 10C).
- Client persistence in IndexedDB with local repositories (Phase 10D).
- Local change tracking and durable sync queues (Phase 10E).
- Cloud synchronization backend with monotonic cursors and idempotency (Phase 10F).
- End-to-end multi-device push/pull synchronization (Phase 10G).
- Advanced 3-way conflict detection, preservation, and resolution (Phase 10H).

The purpose of Phase 10I is to harden this architecture against real-world runtime anomalies: application closures during in-flight batches, browser refreshes, device sleep/wake transitions, expired tokens, server downtime, storage quota eviction, and multi-tab race conditions.

---

## 2. Pre-Implementation Audit Findings

### 2.1 Frontend Inspection

#### A. In-Flight Operations & Crash Recovery (`src/sync/syncQueue.js` & `src/sync/syncManager.js`)
- **Current Behavior:** In `syncManager.pushChanges()`, operations selected for push are transitioned from `PENDING` to `PROCESSING` via `syncQueue.markProcessing(batchIds)`.
- **Reliability Gap:** If a browser tab crashes, user closes the window, or device shuts down while operations are marked `PROCESSING`:
  - `syncQueue.peek()` only queries for `status === 'PENDING'` or retry-eligible `FAILED` items.
  - Operations marked `PROCESSING` become **orphaned**: they remain indefinitely in the queue and are never retried unless manually modified.
- **Required Fix:** Introduce an automated **In-Flight Recovery mechanism** (`syncQueue.recoverInFlightOperations()`) on application startup and before sync cycles. Any operation in `PROCESSING` whose lease has expired (>60s) or that was abandoned by a terminated session is cleanly reverted to `PENDING` with its original `operationId` preserved.

#### B. Multi-Tab Coordination (`src/sync/syncManager.js`)
- **Current Behavior:** Concurrency locks in `syncManager.js` use in-memory module-level variables (`let isPushing = false; let isPulling = false;`).
- **Reliability Gap:** When a user opens Niyantra in multiple browser tabs simultaneously:
  - Each tab runs an independent JavaScript heap with its own `isPushing` flag.
  - If both tabs attempt to push or pull at the same time (e.g. via interval timers or focus events), both tabs could concurrently read the same pending queue, submit duplicate HTTP requests, or race to advance the pull cursor.
- **Required Fix:** Implement cross-tab coordination using the **Web Locks API (`navigator.locks.request`)** with fallback to a leased `localStorage` lock (`niyantra_sync_lock`). Only one tab may execute the push/pull synchronization pipeline at any given moment.

#### C. Cross-Tab Communication (`BroadcastChannel`)
- **Current Behavior:** Changes made in Tab 1 update IndexedDB, but Tab 2 only discovers them upon manual refresh or its next poll cycle.
- **Required Fix:** Introduce `BroadcastChannel('niyantra_sync_bus')` to instantly broadcast sync events, conflict detections, and account transitions across all open tabs.

#### D. Background Synchronization & Service Worker
- **Current Behavior:** Synchronization is driven entirely by foreground triggers: network `online` event, document `visibilitychange`, periodic interval (`setInterval`), and mutation debounce (`triggerDebouncedSync`).
- **Reliability Gap:** If the user creates or updates a task and closes the tab 200ms later, the change remains queued in IndexedDB until Niyantra is reopened.
- **Required Fix:** Register a Service Worker supporting the **Background Sync API (`registration.sync.register('niyantra-sync')`)** where supported (Chromium browsers). When a mutation occurs, the service worker background sync tag is registered. Provide a seamless fallback for non-supporting browsers (Firefox/Safari) using foreground triggers and visibility listeners.

#### E. Local Storage Health & Eviction Protection
- **Current Behavior:** IndexedDB database is created via Dexie, but no storage persistence request (`navigator.storage.persist()`) is made.
- **Reliability Gap:** Mobile and desktop browsers under storage pressure may evict non-persisted IndexedDB origins.
- **Required Fix:**
  - Call `navigator.storage.persist()` on application initialization to request durable storage.
  - Implement periodic quota monitoring using `navigator.storage.estimate()`.
  - Alert the user if storage quota usage exceeds 90% or if available space is critically low (<50MB).

#### F. Network Error & Token Expiry Handling
- **Current Behavior:** Network errors catch and mark operations as failed with exponential backoff.
- **Reliability Gap:**
  - HTTP 401 Unauthorized (expired token) was treated as a generic failure and retried up to 5 times before giving up, causing unnecessary HTTP traffic.
  - HTTP 403 Forbidden (revoked device) was not explicitly flagged with a dedicated status.
- **Required Fix:** Detect HTTP 401 / 403 / 429 status codes in `syncService` and `syncManager`:
  - `401`: Immediately halt sync loops, transition engine status to `AUTH_EXPIRED`, emit event prompting user login without discarding pending changes.
  - `403`: Set status to `DEVICE_REVOKED`, halt sync.
  - `429`: Parse `Retry-After` header and back off accordingly.

---

### 2.2 Backend Inspection

#### A. Idempotency & Re-transmission Safeguards (`backend/app/services/sync_service.py`)
- **Audit:** Push endpoint (`POST /api/sync/push`) searches `SyncOperation.operation_uuid == op_item.operation_uuid`. If already present, it returns status `APPLIED` with the existing server version without duplicating records or re-executing mutations.
- **Outcome:** Sound. Safe for recovery re-submissions.

#### B. Cursor & Acknowledgement Invariants (`backend/app/services/sync_service.py`)
- **Audit:** Pull endpoint queries `SyncOperation.id > cursor` ordered monotonically. Pull cursor updates via `POST /api/sync/acknowledge` take `max(cursor_rec.last_pulled_cursor, cursor)`.
- **Outcome:** Sound. The client advances and acknowledges the cursor only after Dexie writes complete.

#### C. Database Connection Resilience (`backend/app/database.py`)
- **Audit:** SQLite connection supports WAL mode and timeout configuration. PostgreSQL supports pooling with `pool_pre_ping=True`.
- **Outcome:** Sound.

---

## 3. Phase 10I Architecture Plan

```
+─────────────────────────────────────────────────────────────────────────+
│                 NIYANTRA Phase 10I Architecture Blueprint               │
+─────────────────────────────────────────────────────────────────────────+
│                                                                         │
│  [ Application Startup / Tab Wake / Network Restored ]                  │
│                 │                                                       │
│                 ▼                                                       │
│   ┌────────────────────────────────────────────────────────┐            │
│   │ 1. Storage Health & Quota Check                       │            │
│   │    - navigator.storage.persist()                       │            │
│   │    - navigator.storage.estimate()                      │            │
│   └────────────────────────────────────────────────────────┘            │
│                 │                                                       │
│                 ▼                                                       │
│   ┌────────────────────────────────────────────────────────┐            │
│   │ 2. In-Flight Recovery Engine                           │            │
│   │    - Reset abandoned PROCESSING items to PENDING       │            │
│   │    - Preserve original operationId & version           │            │
│   └────────────────────────────────────────────────────────┘            │
│                 │                                                       │
│                 ▼                                                       │
│   ┌────────────────────────────────────────────────────────┐            │
│   │ 3. Multi-Tab Lock Coordinator                          │            │
│   │    - Web Locks: navigator.locks.request()              │            │
│   │    - Fallback: localStorage leased lock with expiry    │            │
│   │    - Cross-tab bus: BroadcastChannel('niyantra_sync')  │            │
│   └────────────────────────────────────────────────────────┘            │
│                 │                                                       │
│                 ▼                                                       │
│   ┌────────────────────────────────────────────────────────┐            │
│   │ 4. Smart Synchronization Engine                        │            │
│   │    - Check Token Validity & Device Registration        │            │
│   │    - Drain Outgoing Queue with Retry Backoff           │            │
│   │    - Pull Delta Changes from Monotonic Cursor          │            │
│   │    - 3-Way Conflict Detection                          │            │
│   └────────────────────────────────────────────────────────┘            │
│                 │                                                       │
│                 ▼                                                       │
│   ┌────────────────────────────────────────────────────────┐            │
│   │ 5. Background Sync & Observability                     │            │
│   │    - Service Worker Background Sync API (if supported) │            │
│   │    - Adaptive polling & visibility listeners (fallback)│            │
│   │    - Sync Status & Diagnostics Drawer in UI            │            │
│   └────────────────────────────────────────────────────────┘            │
+─────────────────────────────────────────────────────────────────────────+
```
