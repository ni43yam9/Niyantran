# NIYANTRA (नियन्त्र)
> **Tagline:** *"I for N@49_89#41_84@73"*  
> **Phase 1 & Phase 2:** Full-Stack Architecture — React Frontend + FastAPI & SQLite Backend

---

## 1. Executive Summary & Purpose

**NIYANTRA** is a modern, single-user personal productivity and goal architecture application. It is engineered to organize personal and academic life, manage daily activities, track short-term tactical milestones and long-term aspirational goals, monitor habit consistency, and analyse holistic productivity trends.

- **Phase 1 (Completed):** Established the complete frontend foundation, responsive design system, modular component hierarchy, client data persistence, and interactive UI views using pure React, Vite, and Tailwind CSS.
- **Phase 2 (Completed):** Built a high-performance, lightweight backend using Python, FastAPI, SQLAlchemy, Pydantic, and SQLite, with complete CRUD operations, dynamic metric aggregations, automatic localStorage migration, and graceful offline fallback.

---

## 2. Technology Stack

### Frontend
- **Runtime & Build Tooling:** [Vite](https://vitejs.dev/) (lightning-fast HMR and optimized bundler)
- **Framework:** [React.js 19](https://react.dev/) (pure JavaScript, functional components with hooks)
- **Styling & Design System:** [Tailwind CSS v3](https://tailwindcss.com/) with centralized design tokens & custom utilities
- **Routing & Code-Splitting:** [React Router DOM v7](https://reactrouter.com/) + `React.lazy()` with route-level chunking
- **Icons:** [Lucide React](https://lucide.dev/) (minimal, consistent iconography)
- **Data Visualizations:** [Recharts](https://recharts.org/) (isolated async chunk for lightweight initial loads)
- **API Services:** Native fetch wrapper with AbortController timeout & automatic fallback (`src/services/`)

### Backend
- **Framework:** [FastAPI](https://fastapi.tiangolo.com/) (high-performance asynchronous Python web framework)
- **Server:** [Uvicorn](https://www.uvicorn.org/) (ASGI server)
- **ORM & Database:** [SQLAlchemy 2.0](https://www.sqlalchemy.org/) + [SQLite 3](https://www.sqlite.org/) (`niyantra.db`)
- **Data Validation & Schemas:** [Pydantic v2](https://docs.pydantic.dev/) (field aliases, camelCase/snake_case interoperability)
- **Testing:** [pytest](https://docs.pytest.org/) + `fastapi.testclient` (14 automated unit and integration tests)

---

## 3. Architecture & Directory Structure

```
Niyantra/
├── backend/
│   ├── app/
│   │   ├── core/
│   │   │   ├── __init__.py
│   │   │   └── config.py          # Settings, CORS, and paths
│   │   ├── database.py            # SQLite engine, SessionLocal, get_db, init_db
│   │   ├── models/                # SQLAlchemy ORM models
│   │   │   ├── __init__.py
│   │   │   ├── goal.py            # Goal model (constraints, indexes)
│   │   │   └── task.py            # Task model (foreign key to goal, cascade set null)
│   │   ├── schemas/               # Pydantic validation & response models
│   │   │   ├── __init__.py
│   │   │   ├── dashboard.py       # Metrics, priorities, category distribution
│   │   │   ├── goal.py            # GoalCreate, GoalUpdate, GoalResponse
│   │   │   ├── migration.py       # MigrationImportRequest, MigrationStatusResponse
│   │   │   └── task.py            # TaskCreate, TaskUpdate, TaskResponse
│   │   ├── services/              # Business logic & database operations
│   │   │   ├── __init__.py
│   │   │   ├── dashboard_service.py # Dynamic metrics, priority ranking
│   │   │   ├── goal_service.py    # Goal CRUD, progress patch, task counts
│   │   │   ├── migration_service.py # Idempotent localStorage migration
│   │   │   └── task_service.py    # Task CRUD, filters, complete/pending toggles
│   │   ├── routers/               # FastAPI route definitions
│   │   │   ├── __init__.py
│   │   │   ├── dashboard.py       # /api/dashboard/summary, /api/health
│   │   │   ├── goals.py           # /api/goals CRUD & progress endpoints
│   │   │   ├── migration.py       # /api/migration/import, /api/migration/status
│   │   │   └── tasks.py           # /api/tasks CRUD & status flip endpoints
│   │   ├── __init__.py
│   │   └── main.py                # FastAPI app entrypoint & lifespan
│   ├── tests/                     # Automated pytest suite
│   │   ├── conftest.py            # In-memory SQLite fixtures & test client
│   │   ├── test_dashboard.py      # Health & summary tests
│   │   ├── test_goals.py          # Goal CRUD & unlinking tests
│   │   ├── test_migration.py      # Idempotent migration lifecycle tests
│   │   └── test_tasks.py          # Task CRUD, filters, & validation tests
│   ├── .env.example
│   ├── niyantra.db                # SQLite database (auto-generated)
│   └── requirements.txt           # Pinned backend dependencies
│
├── public/
│   └── favicon.svg                # Geometric monogram logo
├── src/
│   ├── components/                # Common, dashboard, tasks, goals, layout components
│   ├── constants/                 # Theme tokens & navigation constants
│   ├── context/
│   │   ├── AppContext.jsx         # Unified state, localStorage cache, background API sync
│   │   └── ThemeContext.jsx       # Theme toggle (light/dark mode)
│   ├── data/                      # Initial seed and mock data
│   ├── pages/                     # Lazy-loaded views (Dashboard, MyTasks, Goals, etc.)
│   ├── services/                  # Frontend API integration
│   │   ├── api.js                 # Resilient HTTP client with health check
│   │   ├── taskService.js         # Task CRUD & query operations
│   │   ├── goalService.js         # Goal CRUD & progress operations
│   │   └── migrationService.js    # Data migration client
│   ├── utils/                     # Date calculations & helpers
│   ├── App.jsx
│   ├── index.css
│   └── main.jsx
├── package.json                   # Scripts for dev, build, backend, test:backend
└── README.md
```

---

## 4. Database Schema & Relationships

### SQLite Tables (`niyantra.db`)

#### `goals` Table
| Column | Type | Constraints | Description |
|---|---|---|---|
| `id` | VARCHAR(36) | PRIMARY KEY | Goal identifier (`g-1`, `g-timestamp`) |
| `title` | VARCHAR(200) | NOT NULL | Title of the goal |
| `description` | TEXT | NULLABLE | Detailed goal description |
| `goal_type` | VARCHAR(50) | NOT NULL, CHECK in ('Short-Term', 'Long-Term') | Planning horizon |
| `category` | VARCHAR(50) | NOT NULL | Category (Coding, Academic, Career, etc.) |
| `priority` | VARCHAR(20) | NOT NULL, CHECK in ('High', 'Medium', 'Low') | Priority level |
| `status` | VARCHAR(20) | NOT NULL, CHECK in ('In Progress', 'On Track', 'Behind', 'Completed') | Current status |
| `start_date` | DATE | NOT NULL | Goal start date |
| `target_date` | DATE | NOT NULL | Target completion date |
| `progress` | INTEGER | NOT NULL, CHECK (progress >= 0 AND progress <= 100) | Completion percentage |
| `key_milestone`| VARCHAR(255) | NULLABLE | Current target milestone |
| `created_at` | DATETIME | NOT NULL | Creation timestamp (UTC) |
| `updated_at` | DATETIME | NOT NULL | Last update timestamp (UTC) |

#### `tasks` Table
| Column | Type | Constraints | Description |
|---|---|---|---|
| `id` | VARCHAR(36) | PRIMARY KEY | Task identifier (`t-1`, `t-timestamp`) |
| `title` | VARCHAR(200) | NOT NULL | Title of the task |
| `description` | TEXT | NULLABLE | Detailed task notes |
| `task_type` | VARCHAR(50) | NOT NULL, CHECK in ('Daily', 'Short-Term', 'Long-Term', 'One-Time', 'Occasional') | Task category |
| `category` | VARCHAR(50) | NOT NULL, CHECK in ('Academic', 'Coding', 'Career', 'Reading', 'Health', 'Personal') | Category |
| `priority` | VARCHAR(20) | NOT NULL, CHECK in ('High', 'Medium', 'Low') | Priority level |
| `status` | VARCHAR(20) | NOT NULL, CHECK in ('Pending', 'In Progress', 'Completed') | Completion status |
| `start_date` | DATE | NOT NULL | Task start date |
| `due_date` | DATE | NOT NULL | Task due date |
| `goal_id` | VARCHAR(36) | FOREIGN KEY -> `goals(id)` ON DELETE SET NULL | Associated goal |
| `completed_at` | DATETIME | NULLABLE | Timestamp when completed |
| `created_at` | DATETIME | NOT NULL | Creation timestamp (UTC) |
| `updated_at` | DATETIME | NOT NULL | Last update timestamp (UTC) |

---

## 5. REST API Endpoints

Interactive Swagger documentation is available at `http://localhost:8000/docs` and ReDoc at `http://localhost:8000/redoc`.

| Method | Endpoint | Description |
|---|---|---|
| `GET` | `/api/health` | Health check verifying API and SQLite database status |
| `GET` | `/api/dashboard/summary` | Aggregated metrics, tasks due today, top priorities, and category distribution |
| `GET` | `/api/tasks` | List tasks with filters (`status`, `priority`, `category`, `taskType`, `search`, `isToday`, `isOverdue`) |
| `GET` | `/api/tasks/{task_id}` | Retrieve single task details |
| `POST` | `/api/tasks` | Create a new task (201 Created) |
| `PUT` | `/api/tasks/{task_id}` | Update task details |
| `DELETE` | `/api/tasks/{task_id}` | Permanently delete a task |
| `PATCH` | `/api/tasks/{task_id}/complete` | Convenience endpoint: mark task as Completed |
| `PATCH` | `/api/tasks/{task_id}/pending` | Convenience endpoint: revert task to Pending |
| `GET` | `/api/goals` | List goals with linked task counts and days remaining |
| `GET` | `/api/goals/{goal_id}` | Retrieve single goal details |
| `POST` | `/api/goals` | Create a new goal (201 Created) |
| `PUT` | `/api/goals/{goal_id}` | Update goal details |
| `DELETE` | `/api/goals/{goal_id}` | Permanently delete a goal (safely unlinks child tasks) |
| `PATCH` | `/api/goals/{goal_id}/progress` | Update goal progress percentage (auto-completes at 100%) |
| `POST` | `/api/migration/import` | Idempotent import of localStorage tasks and goals into SQLite |
| `GET` | `/api/migration/status` | Current database record counts |

---

## 6. How to Run

### 1. Start the Backend API (FastAPI)
```powershell
# From project root:
npm run backend

# Or directly with Python:
uvicorn backend.app.main:app --reload --port 8000
```
Backend will start on `http://127.0.0.1:8000` with automatic table creation.

### 2. Start the Frontend (Vite)
```powershell
# In a second terminal:
npm run dev
```
Frontend will start on `http://localhost:5173`.

### 3. Run Backend Test Suite
```powershell
npm run test:backend
# Or:
pytest backend/tests -v
```
All 14 tests run in `< 0.4s` using isolated in-memory SQLite fixtures.

---

## 7. Data Synchronization & Offline Resilience

- **Instant Zero-Latency UI:** The application initializes immediately from `localStorage` cache with 0ms delay.
- **Automated Migration:** On first run with the backend online, all existing `localStorage` tasks and goals are automatically and idempotently migrated to SQLite without duplicate records or ID mutations.
- **Graceful Fallback:** If the backend is stopped or unavailable, the UI operates seamlessly in offline mode, caching all changes locally until reconnection.
- **Status Indicator:** A live connection badge in the Navbar and a dedicated **Backend Infrastructure** card in Settings provide real-time connection status and manual sync triggers.
