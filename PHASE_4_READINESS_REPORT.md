# NIYANTRA — PHASE 4 READINESS ASSESSMENT REPORT
**Document Reference**: `PHASE_4_READINESS_REPORT.md`  
**Assessment Date**: 2026-11-19  
**Assessment Scope**: Inspection of Existing Recommendation, Intelligence, Analytics, and Behaviour Monitoring Capabilities  
**Status**: COMPLETED (Non-Destructive Inspection & Diagnostic Verification)

---

## 1. EXECUTIVE SUMMARY

An exhaustive code-level audit was conducted across the backend services, database schema, API routers, and React frontend components of the Niyantra application. The objective was to ascertain the exact state of the recommendation engine, identify existing intelligence algorithms, assess behavioural data integration, uncover architectural deficiencies, and map development priorities before beginning Phase 4 feature development.

### Baseline Status
- **Automated Test Suite**: 50/50 backend tests passing (`pytest backend/tests -v` in 1.16s).
- **API Endpoints**: 51/51 documented REST endpoints registered and functional.
- **End-to-End Workflows**: 8/8 core user workflows verified across tasks, habits, timeblocks, goals, and analytics.
- **Database Records (Preserved)**: 8 goals, 11 tasks, 4 habits, 7 recommendations currently stored in `backend/niyantra.db`.
- **Active Servers**:
  - FastAPI Backend: `http://localhost:8000` (PID 38284, Uvicorn 0.34.0)
  - Vite Frontend: `http://localhost:5173` (PID 14772, Vite 8.3.8)

---

## 2. DETAILED RECOMMENDATION SUBSYSTEM INSPECTION

### 2.1 Database Model (`backend/app/models/recommendation.py`)
- **Table Name**: `recommendations`
- **Columns**:
  - `id`: `String(36)`, Primary Key (UUID format `rec_...`)
  - `type`: `String(50)` (`FOCUS_TASK`, `RESCHEDULE_TASK`, `EXPEDITE_TASK`, `ADD_GOAL_TASK`, `TRACK_HABIT`)
  - `category`: `String(50)` (`PRIORITIZATION`, `WORKLOAD_BALANCE`, `DEADLINE_RISK`, `GOAL_PROGRESS`, `HABIT_IMPROVEMENT`)
  - `title`: `String(255)`, Not Null
  - `description`: `Text`, Nullable
  - `reason`: `Text`, Nullable (stores behavioral rationale)
  - `priority`: `String(20)` (`CRITICAL`, `HIGH`, `MEDIUM`, `LOW`)
  - `status`: `String(20)` (`PENDING`, `ACCEPTED`, `DISMISSED`, `COMPLETED`)
  - `action_type`: `String(50)`, Nullable
  - `action_payload`: `JSON`, Nullable (stores structured action parameters)
  - `entity_id`: `String(36)`, Nullable (ID of target task, habit, or goal)
  - `target_date`: `Date`, Nullable
  - `created_at`: `DateTime(timezone=True)`, server default `utcnow`
  - `updated_at`: `DateTime(timezone=True)`, onupdate `utcnow`
- **Indices**: Composite index on `(category, status)` and single index on `entity_id`.

### 2.2 Schemas (`backend/app/schemas/recommendation.py`)
- Standardized Pydantic models: `RecommendationBase`, `RecommendationCreate`, `RecommendationUpdate`, `RecommendationResponse`, `RecommendationSummary`.
- Properly configured with `from_attributes = True` for SQLAlchemy ORM conversion.

### 2.3 Service Layer (`backend/app/services/recommendation_service.py`)
- Lines 1–535 implement 5 rule-based generation routines:
  1. `_rule_smart_prioritization`: Identifies pending tasks due within 48h or overdue. Hardcodes morning focus block.
  2. `_rule_workload_balance`: Sums planned focus minutes per day; if $> 360$ minutes (6 hours), finds a lighter day $< 240$ minutes and recommends shifting one task.
  3. `_rule_deadline_risk`: Evaluates pending tasks with deadlines, queries `ActivityLog` for postponement count and `DailyTimeblock` for estimation bias.
  4. `_rule_goal_progress`: Checks goals with zero tasks, active goals with $< 50\%$ progress within 14 days of deadline, and stagnant goals with no completed tasks in 10 days.
  5. `_rule_habit_improvement`: Evaluates habit logs over the last 4 days; suggests streak protection ($\ge 3$ consecutive completions) or recovery ($\ge 2$ missed days).
- **Execution Handlers**:
  - `accept_recommendation`: Updates recommendation status to `ACCEPTED`. If `action_type == "RESCHEDULE_TASK"`, it updates task `start_date` and shifts any linked `DailyTimeblock.block_date`. Other action types do not execute mutations.
  - `dismiss_recommendation`: Updates status to `DISMISSED`.
  - `complete_recommendation`: Updates status to `COMPLETED`.
  - `auto_sync_completed_entities`: Marks pending recommendations as `COMPLETED` when the underlying task, habit, or goal is finished.

### 2.4 API Router (`backend/app/routers/recommendations.py`)
- `GET /api/recommendations`: Lists recommendations (supports filters: `status`, `category`, `priority`, `limit`). Triggers `generate_recommendations(db)` on fetch.
- `POST /api/recommendations/generate`: Forces re-evaluation of all 5 rule sets.
- `POST /api/recommendations/{rec_id}/accept`: Calls service accept handler.
- `POST /api/recommendations/{rec_id}/dismiss`: Sets status to `DISMISSED`.
- `POST /api/recommendations/{rec_id}/complete`: Sets status to `COMPLETED`.

### 2.5 Frontend Integration
- Dedicated page: `src/pages/Recommendations.jsx` (mounted as a tab in `/analytics` and route `/recommendations`).
- Service client: `src/services/recommendationService.js` calling all 5 REST endpoints.
- UI features: Category badges, priority badges, rationale box, filter tabs (All, Pending, Accepted, Dismissed, Completed), Accept/Dismiss buttons.

---

## 3. THE DISMISSAL RESPAWN FLAW (CRITICAL DEFECT)

During inspection of `backend/app/services/recommendation_service.py` (lines 37–46), a significant architectural flaw was detected in deduplication logic:

```python
def has_pending_rec(db: Session, entity_id: str, rec_type: str) -> bool:
    if not entity_id:
        return False
    return db.query(Recommendation).filter(
        Recommendation.entity_id == entity_id,
        Recommendation.type == rec_type,
        Recommendation.status == "PENDING"
    ).first() is not None
```

### Manifestation:
1. User receives a recommendation (e.g. `FOCUS_TASK` for Task A) in `PENDING` status.
2. User clicks **Dismiss**. The backend updates its status to `"DISMISSED"`.
3. When the user navigates back or refreshes, `GET /api/recommendations` invokes `generate_recommendations(db)`.
4. `has_pending_rec()` checks for `status == "PENDING"`. Because the previous record is `"DISMISSED"`, it returns `False`.
5. The engine **immediately regenerates the exact same recommendation** with a new UUID in `PENDING` status.
6. **Result**: A user cannot permanently dismiss or snooze an unwanted suggestion.

---

## 4. BEHAVIOURAL DATA INTEGRATION AUDIT

### 4.1 Connected Services
- `ActivityLog`: Querying task postponement counts (`event_type == "POSTPONED"`).
- `DailyTimeblock`: Calculating estimation variance ratio ($ratio > 1.25$ indicates underestimation).
- `HabitLog`: Calculating recent 4-day completion sequences.
- `Goal`: Tracking linked task count and progress percentages.

### 4.2 Disconnected & Bypassed Services
- **`behaviour_service.get_productivity_hours()`**: Computes a user's peak execution window (e.g. Morning, Afternoon, Evening). `recommendation_service.py` **bypasses this service entirely** and hardcodes `"Morning (09:00 - 12:00)"` for all focus recommendations.
- **`behaviour_service.get_time_estimation_bias()`**: Re-implemented with inline ORM queries in `recommendation_service.py` rather than consuming the dedicated behaviour service.
- **`analytics_service.get_analytics_overview()`**: High-level productivity score (0–100) is never referenced to modulate recommendation frequency or tone.
- **User Preference Learning**: The engine maintains zero memory of which categories the user frequently accepts or rejects.

---

## 5. RECENT DIAGNOSTIC VERIFICATION (USER SCREENSHOTS)

### 5.1 Screenshot 1: `localhost refused to connect` (`ERR_CONNECTION_REFUSED`)
- **Cause**: Chrome displays `ERR_CONNECTION_REFUSED` when navigating to a port where no server is listening (such as port 80 if typing `localhost` without a port, or port 3000 which is the Create-React-App default).
- **Verification**:
  - Vite dev server is running on **`http://localhost:5173`** (PID 14772, verified 200 OK).
  - FastAPI backend is running on **`http://localhost:8000`** (PID 38284, verified 200 OK).
  - Both ports are actively listening on `0.0.0.0` and accessible.

### 5.2 Screenshot 2: Empty "Weekly Deliverable Velocity" Chart on Analytics Page
- **Cause**: The backend `/api/analytics/weekly` was returning valid 7-day data (13 planned, 4 completed, 30.8% rate, peak day Tue). However, in `src/pages/Analytics.jsx`, the chart container was inside a CSS Grid item (`lg:col-span-2`) with default `min-width: auto` and wrapped in `min-h-[280px]` (without an explicit fixed height). In Chromium, Recharts `<ResponsiveContainer>` encountered a CSS Grid dimension-measuring loop, collapsing chart dimensions to `0x0px` and rendering invisible.
- **Resolution Applied**:
  - Added `min-w-0` to the grid cell (`lg:col-span-2 min-w-0`).
  - Added explicit fixed height `h-72 w-full min-w-0` to the chart wrapper.
  - Set `<ResponsiveContainer width="100%" height="100%" minWidth={0}>`.
  - Added visual legend indicators for Planned vs Completed deliverables.
  - Vite HMR compiled and pushed the update cleanly.

---

## 6. CAPABILITY ASSESSMENT TABLE

| Capability Area | Status | Implementation Details & Gaps |
| :--- | :--- | :--- |
| **1. Smart Prioritization** | `PARTIALLY IMPLEMENTED` | Implemented via Rule Set 1 (`FOCUS_TASK`). Identifies urgent tasks ($\le 48\text{h}$ or overdue). **Gap**: Hardcodes morning focus window instead of reading user's personal peak hours from `behaviour_service`. |
| **2. Deadline Risk Detection** | `PARTIALLY IMPLEMENTED` | Implemented via Rule Set 3 (`EXPEDITE_TASK`). Analyzes postponement count and timeblock estimation ratios. **Gap**: Action has no automated execution handler when accepted. |
| **3. Workload Balancing** | `PARTIALLY IMPLEMENTED` | Implemented via Rule Set 2 (`RESCHEDULE_TASK`). Detects days $> 360\text{m}$ and shifts tasks to days $< 240\text{m}$. Shifts timeblocks upon acceptance. **Gap**: Hardcoded 6h/4h thresholds; moves only 1 task at a time. |
| **4. Goal Risk Detection** | `PARTIALLY IMPLEMENTED` | Implemented via Rule Set 4 (`ADD_GOAL_TASK`). Detects orphaned, deadline-approaching, and stagnant goals. **Gap**: Action does not open the task creation modal pre-linked to the goal. |
| **5. Habit Recommendations** | `PARTIALLY IMPLEMENTED` | Implemented via Rule Set 5 (`TRACK_HABIT`). Checks 4-day logs for streaks ($\ge 3\text{d}$) and lapses ($\ge 2\text{d}$). **Gap**: Acceptance does not automatically log or open habit completion modal. |
| **6. Behaviour-Based Insights** | `FULLY IMPLEMENTED` | Implemented in `analytics_service.py` (`get_productivity_insights`). Generates 5 distinct observation cards rendered in Analytics "Behaviour Insights" tab. |
| **7. Adaptive Recommendations** | `NOT IMPLEMENTED` | Zero feedback loops. Past acceptance and dismissal history does not adjust priority weights, thresholds, or generation rules. |
| **8. Recommendation History** | `FULLY IMPLEMENTED` | Database model stores `PENDING`, `ACCEPTED`, `DISMISSED`, `COMPLETED`. Frontend tabs filter by status. **Gap**: Passive storage only; not used to train or refine suggestions. |

---

## 7. PHASE 4 DEVELOPMENT PRIORITIES

### Priority 1: Essential (Must Fix First)
1. **Fix Dismissal Respawn Flaw**:
   - Update `has_pending_rec` in `recommendation_service.py` to enforce a cooldown or snooze period (e.g. 7 days) on `DISMISSED` recommendations so dismissed items do not immediately respawn on next refresh.
2. **Connect Behaviour Service Peak Hours**:
   - Replace the hardcoded `"Morning (09:00 - 12:00)"` in `_rule_smart_prioritization` with a dynamic query to `behaviour_service.get_productivity_hours()`.
3. **Frontend Action Handlers**:
   - For `TRACK_HABIT`: Allow clicking Accept to toggle today's habit completion.
   - For `ADD_GOAL_TASK`: Allow clicking Accept to open `TaskModal` pre-populated with the target `goal_id`.
   - For `EXPEDITE_TASK`: Allow clicking Accept to raise task priority to `CRITICAL` or open the scheduler.

### Priority 2: Important (Core Enhancements)
1. **Dynamic Workload Capacity**:
   - Replace hardcoded $360\text{m}$ and $240\text{m}$ thresholds in `_rule_workload_balance` with user's daily capacity setting from the Daily Planner settings.
2. **Dashboard Recommendation Card**:
   - Surface the top 1–2 most critical recommendations directly on `src/pages/Dashboard.jsx` so users see high-priority warnings immediately without having to navigate to Analytics.
3. **Sidebar Indicator**:
   - Add a dynamic count badge for pending recommendations to the sidebar navigation.

### Priority 3: Optional (Advanced Polish)
1. **Adaptive Acceptance Weighting**:
   - Track acceptance rates per category. If a user dismisses 3 consecutive habit recommendations, reduce habit recommendation frequency for 14 days.
2. **Multi-Task Load Balancing**:
   - Allow rescheduling multiple tasks across the week when a day has more than 8 hours of planned focus.

---
*Report generated for Niyantra productivity architecture.*
