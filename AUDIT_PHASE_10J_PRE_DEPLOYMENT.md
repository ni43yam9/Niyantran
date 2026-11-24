# NIYANTRA — PHASE 10J: PRE-DEPLOYMENT ARCHITECTURE AUDIT

**Date:** November 22, 2026  
**Auditor:** Antigravity (Google DeepMind Agent)  
**System:** NIYANTRA Multi-Device Productivity System  
**Target:** Production Cloud Deployment & Real Laptop/Phone Synchronization  

---

## 1. Executive Summary

Phase 10J represents the transition from local-first development (Phases 10A–10I) to real-world cloud deployment. The objective is to verify bidirectional synchronization between independent physical devices (Laptop and Phone) across a publicly accessible HTTPS cloud backend and PostgreSQL database.

This audit evaluates the readiness of the existing codebase for production deployment across 10 critical dimensions, identifies all deployment blockers, and outlines the precise remediation steps required before cloud provisioning.

---

## 2. Backend Architecture Audit

### 2.1 FastAPI Application Configuration
- **Entry Point:** `backend/app/main.py`
- **Application Class:** Standard FastAPI application using `lifespan` context manager to trigger `init_db()` on startup.
- **Config Management:** `backend/app/core/config.py` defines `Settings` reading environment variables with development fallbacks.
- **Configuration Items:**
  - `APP_NAME`: Default `"NIYANTRA Backend API"`
  - `APP_VERSION`: `"2.0.0"`
  - `DEBUG`: Boolean derived from `DEBUG` env var (default: `True`).
  - `ENVIRONMENT`: Derived as `"development"` or `"production"`.
  - `DATABASE_URL`: Defaults to local SQLite (`sqlite:///.../niyantra.db`).
  - `JWT_SECRET_KEY`: Defaults to dev key.
  - `ACCESS_TOKEN_EXPIRE_MINUTES`: 10,080 minutes (7 days).
  - `CORS_ORIGINS`: Comma-separated list of allowed origins.
- **Audit Finding:** In production, `DEBUG` must be set to `False` to prevent leaking internal database paths and exception tracebacks in HTTP 500 responses.

### 2.2 Database Connection & Multi-Dialect Compatibility
- **Database Engine Module:** `backend/app/database.py`
- **Dialect Handling:**
  - Automatically translates legacy `postgres://` URLs to `postgresql://` (required by SQLAlchemy 2.0+).
  - Dialect-specific engine kwargs:
    - **SQLite:** Sets `check_same_thread=False` and `timeout=15`. Configures PRAGMA `foreign_keys=ON`, `journal_mode=WAL`, `synchronous=NORMAL`, `busy_timeout=5000` via event listener.
    - **PostgreSQL:** Configures connection pooling: `pool_pre_ping=True`, `pool_size=10`, `max_overflow=20`.
- **Audit Finding (Green):** The engine setup is already designed for seamless dual-database operation (SQLite for local development/testing, PostgreSQL for production cloud deployment).

### 2.3 Alembic Migration History & Schema Evolution
- **Migration Scripts:** Located at `backend/alembic/versions/`
  1. `fa32b08ebb44_phase10b_schema_evolution.py` (tasks, goals, habits, daily_intents schema evolution)
  2. `3d6bec57fb10_phase10c_auth_and_devices.py` (users, devices, default_user seed)
  3. `7a8b9c0d1e2f_phase10f_cloud_sync_api.py` (sync_operations, sync_cursors, sync_entity_versions)
  4. `8b9c0d1e2f3a_phase10h_conflict_management.py` (sync_conflicts)
- **Deployment Blocker 1 (Critical):**
  In migration `3d6bec57fb10_phase10c_auth_and_devices.py`, lines 45–60:
  ```sql
  INSERT OR IGNORE INTO users ...
  ```
  `INSERT OR IGNORE` is SQLite-specific syntax. On PostgreSQL, running `alembic upgrade head` fails with a SQL syntax error.
  *Remediation:* Make the seed statement dialect-aware: use `INSERT OR IGNORE` on SQLite and `INSERT ... ON CONFLICT (id) DO NOTHING` on PostgreSQL.
- **Deployment Blocker 2 (Minor):**
  In `backend/alembic/env.py`, `backend.app.models.user`, `device`, and `sync` are not imported into `target_metadata`. While manual migrations already exist, autogeneration requires these model imports.
  *Remediation:* Import `user`, `device`, and `sync` models in `backend/alembic/env.py`.

### 2.4 Authentication, Devices & Security
- **Security Module:** `backend/app/core/security.py`
- **Password Hashing:** `bcrypt.hashpw` with per-user salt and `bcrypt.checkpw` in constant time.
- **Token Generation:** `jwt.encode` using HS256 algorithm with expiration claims (`exp`, `sub`, `email`, `iat`).
- **Device Registration & Revocation:**
  - `Device` model in `backend/app/models/device.py` tracks `device_uuid`, `user_id`, `status` (`active` vs `revoked`).
  - `validate_device()` in `backend/app/services/sync_service.py` validates that the requesting `X-Device-UUID` belongs to the authenticated user and has status `'active'`.
  - Revoked devices are rejected with HTTP 403 `DEVICE_REVOKED`.
- **Audit Finding (Green):** Authentication and device revocation are robustly enforced at the service and router layers.

### 2.5 Synchronization & Conflict Endpoints
- **Endpoints:**
  - `POST /api/sync/push`: Batched idempotent mutation submission.
  - `GET /api/sync/pull`: Delta retrieval since sequence cursor.
  - `POST /api/sync/acknowledge`: Sequence checkpoint commit.
  - `GET /api/sync/status`: Active queue and cursor status.
  - `GET /api/sync/conflicts`: Unresolved conflict list.
  - `POST /api/sync/conflicts/resolve`: Conflict resolution endpoint.
- **Audit Finding (Green):** All synchronization endpoints enforce tenant isolation (`user_id = current_user.id`) and monotonic cursor guarantees.

### 2.6 CORS & Network Accessibility
- **Current Setup:** `CORSMiddleware` in `backend/app/main.py` allows origins listed in `settings.CORS_ORIGINS` and regex `r"^https?://(localhost|127\.0\.0\.1)(:\d+)?$"`.
- **Deployment Blocker 3:**
  When testing real mobile devices on the local network (e.g. `http://10.55.50.97:5173`) or accessing via public cloud domains, requests are blocked by CORS because the origin is neither localhost nor explicitly configured.
  *Remediation:* Allow `CORS_ORIGINS` to support comma-separated wildcards or cloud frontend domains, and extend the local regex to include local IPv4 subnets (`192.168.*`, `10.*`).

### 2.7 Health-Check & Monitoring Endpoints
- **Current Setup:**
  - `/api/health` in `backend/app/routers/dashboard.py` executes `SELECT 1` against the database.
  - Root `/` returns application metadata.
- **Audit Finding:** Many cloud hosting platforms (Render, Railway, Fly.io, AWS ALB) default to checking `/health`. We should mount a direct `@app.get("/health")` alias on `main.py` to ensure immediate health check compatibility without requiring custom path overrides.

### 2.8 Dependency Manifest (`requirements.txt`)
- **Current File:** `backend/requirements.txt` contains only 6 packages:
  `fastapi`, `uvicorn[standard]`, `sqlalchemy`, `pydantic`, `pytest`, `httpx`.
- **Deployment Blocker 4 (Critical):**
  Missing essential production packages:
  - `alembic` (required to run database migrations)
  - `psycopg2-binary` (required for PostgreSQL connection)
  - `bcrypt` (required for password hashing)
  - `pyjwt` (required for JWT tokens)
  - `python-multipart` (required for form handling)
  *Remediation:* Update `backend/requirements.txt` to include all runtime dependencies.

---

## 3. Frontend Architecture Audit

### 3.1 API Client & Base URL Configuration
- **API Client:** `src/services/api.js`
- **Base URL Resolution:**
  ```javascript
  const API_BASE_URL =
    (typeof import.meta !== 'undefined' && import.meta.env && import.meta.env.VITE_API_URL) ||
    'http://localhost:8000/api';
  ```
- **Audit Finding (Green):** The frontend dynamically respects `VITE_API_URL`. Pointing to a production cloud backend requires setting `VITE_API_URL=https://<production-host>/api` in `.env.production` or build environment variables.

### 3.2 Device UUID Persistence & Profiling
- **Module:** `src/utils/deviceUtils.js`
- **Storage:** Persisted under `niyantra_device_uuid` in `localStorage`.
- **Audit Finding (Green):** Each client browser generates and permanently retains a unique device UUID. When accessing from a laptop and a phone, each device maintains its own distinct identity.

### 3.3 IndexedDB & Offline Operation
- **Database:** `src/database/db.js` using Dexie.js (Schema Version 3).
- **Stores:** 11 stores (`tasks`, `goals`, `habits`, `habit_logs`, `daily_timeblocks`, `daily_intents`, `activity_logs`, `recommendations`, `sync_meta`, `sync_queue`, `conflicts`).
- **Audit Finding (Green):** IndexedDB operates completely client-side. Each device maintains an independent, durable offline database with full CRUD capabilities when disconnected.

### 3.4 Service Worker & PWA Readiness
- **Current Setup:** `public/sw.js` and `src/utils/serviceWorkerRegistration.js`.
- **Deployment Blocker 5 (Minor for mobile UX):**
  Missing `public/manifest.json` and meta link in `index.html`. On mobile phones (Android Chrome / iOS Safari), a Web App Manifest enables "Add to Home Screen" as a standalone, fullscreen PWA, and prevents aggressive iOS storage eviction.
  *Remediation:* Add `public/manifest.json` with app icons, standalone display mode, and link in `index.html`.

---

## 4. Summary of Deployment Blockers & Remediation Plan

| # | Component | Blocker Description | Severity | Remediation |
|---|---|---|---|---|
| **B1** | Backend Alembic | `3d6bec57fb10` uses SQLite `INSERT OR IGNORE` which fails on PostgreSQL | **Critical** | Make seed SQL dialect-aware (`ON CONFLICT DO NOTHING` for PostgreSQL) |
| **B2** | Backend Requirements | `backend/requirements.txt` lacks `psycopg2-binary`, `alembic`, `bcrypt`, `pyjwt` | **Critical** | Update `backend/requirements.txt` with full production dependencies |
| **B3** | Backend CORS | `main.py` rejects mobile device LAN IPs and non-localhost cloud origins | **High** | Support LAN IP regex and configurable production cloud origins |
| **B4** | Backend Health Check | Cloud platforms probe `/health`, but endpoint is currently at `/api/health` | **Medium** | Expose `@app.get("/health")` alias directly on `main.py` |
| **B5** | Alembic Metadata | `backend/alembic/env.py` missing imports for `user`, `device`, `sync` models | **Low** | Import all models in `env.py` for full metadata coverage |
| **B6** | Frontend PWA | Missing `manifest.json` for mobile phone standalone PWA installation | **Medium** | Create `public/manifest.json` and link in `index.html` |
| **B7** | Frontend Environment | Missing `.env.production` with `VITE_API_URL` configuration template | **Medium** | Add `.env.production` and `.env.example` |

---

## 5. Verification Checklist Prior to Provisioning

- [x] SQLite local development database verified intact (`backend/niyantra.db`, 0 FK violations).
- [x] Verified pre-Phase 10J SQLite backup created (`niyantra_backup_20261122_160748_post_phase10i.db`).
- [x] `psycopg2` driver verified available in python environment.
- [x] 84/84 frontend vitest tests passing.
- [x] 157/157 backend pytest tests passing.
- [x] Vite production build passing cleanly.
