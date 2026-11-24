import uuid
from datetime import date, datetime, timedelta, timezone
import pytest

from backend.app.models.task import Task
from backend.app.models.goal import Goal
from backend.app.models.habit import Habit
from backend.app.models.habit_log import HabitLog
from backend.app.models.timeblock import DailyTimeblock
from backend.app.models.activity_log import ActivityLog
from backend.app.models.recommendation import Recommendation
from backend.app.services import recommendation_service

# ---------------------------------------------------------------------------
# Existing Baseline Tests (Preserved)
# ---------------------------------------------------------------------------

def test_prioritization_engine_urgent_task(client, db_session):
    today = date.today()
    task = Task(
        id=str(uuid.uuid4()),
        title="High Priority Production Hotfix",
        task_type="Daily",
        category="Coding",
        priority="High",
        status="Pending",
        start_date=today,
        due_date=today + timedelta(days=1),
    )
    db_session.add(task)
    db_session.commit()

    resp = client.get("/api/recommendations")
    assert resp.status_code == 200
    data = resp.json()
    assert data["total_active"] >= 1
    
    prio_items = [i for i in data["items"] if i["type"] == "PRIORITIZATION"]
    assert len(prio_items) >= 1
    assert "Hotfix" in prio_items[0]["title"]
    assert prio_items[0]["priority"] in ("HIGH", "MEDIUM")
    assert prio_items[0]["action_type"] == "FOCUS_TASK"

def test_workload_balancing_and_accept_action(client, db_session):
    today = date.today()
    task1 = Task(
        id=str(uuid.uuid4()),
        title="Core Architecture Redesign",
        task_type="Short-Term",
        category="Coding",
        priority="Low",
        status="Pending",
        start_date=today,
        due_date=today + timedelta(days=5),
    )
    db_session.add(task1)
    db_session.commit()

    # Add a 400 min timeblock for today to exceed 360 min limit
    tb = DailyTimeblock(
        id=str(uuid.uuid4()),
        task_id=task1.id,
        block_date=today,
        title="Deep Work Marathon",
        time="09:00 AM",
        duration_minutes=400,
        category="Coding",
        status="Pending",
    )
    db_session.add(tb)
    db_session.commit()

    resp = client.get("/api/recommendations")
    assert resp.status_code == 200
    data = resp.json()
    
    wb_items = [i for i in data["items"] if i["type"] == "WORKLOAD_BALANCE"]
    assert len(wb_items) >= 1
    wb_rec = wb_items[0]
    assert wb_rec["action_type"] == "RESCHEDULE_TASK"
    suggested_date = wb_rec["action_payload"]["suggested_date"]
    assert suggested_date is not None

    # Test accepting recommendation
    rec_id = wb_rec["id"]
    accept_resp = client.post(f"/api/recommendations/{rec_id}/accept")
    assert accept_resp.status_code == 200
    assert accept_resp.json()["status"] == "ACCEPTED"

    # Verify task start_date was updated
    db_session.refresh(task1)
    assert str(task1.start_date) == suggested_date

    # Verify activity was logged
    act = db_session.query(ActivityLog).filter(ActivityLog.event_type == "TASK_RESCHEDULED").first()
    assert act is not None
    assert act.entity_id == task1.id

def test_deadline_risk_engine(client, db_session):
    today = date.today()
    task = Task(
        id=str(uuid.uuid4()),
        title="Critical Security Audit",
        task_type="Short-Term",
        category="Coding",
        priority="High",
        status="Pending",
        start_date=today,
        due_date=today + timedelta(days=2),
    )
    db_session.add(task)
    db_session.commit()

    # Log 2 postponements
    log1 = ActivityLog(event_type="TASK_POSTPONED", entity_type="TASK", entity_id=task.id)
    log2 = ActivityLog(event_type="TASK_POSTPONED", entity_type="TASK", entity_id=task.id)
    db_session.add_all([log1, log2])
    db_session.commit()

    resp = client.get("/api/recommendations")
    assert resp.status_code == 200
    data = resp.json()
    risk_items = [i for i in data["items"] if i["type"] == "DEADLINE_RISK"]
    assert len(risk_items) >= 1
    assert "Security Audit" in risk_items[0]["title"]
    assert "postponed" in risk_items[0]["reason"].lower()

def test_goal_progress_intelligence(client, db_session):
    today = date.today()
    goal = Goal(
        id=str(uuid.uuid4()),
        title="Launch Version 2.0",
        description="Public rollout",
        goal_type="Short-Term",
        category="Coding",
        priority="High",
        start_date=today,
        target_date=today + timedelta(days=30),
        status="In Progress",
        progress=0,
    )
    db_session.add(goal)
    db_session.commit()

    resp = client.get("/api/recommendations")
    assert resp.status_code == 200
    data = resp.json()
    goal_items = [i for i in data["items"] if i["type"] == "GOAL_PROGRESS"]
    assert len(goal_items) >= 1
    assert goal_items[0]["action_type"] == "ADD_GOAL_TASK"

def test_habit_improvement_streak_protection(client, db_session):
    today = date.today()
    habit = Habit(
        id=str(uuid.uuid4()),
        name="Daily Morning Reading",
        category="Reading",
        frequency="Daily",
        base_streak=5,
    )
    db_session.add(habit)
    db_session.commit()

    resp = client.get("/api/recommendations")
    assert resp.status_code == 200
    data = resp.json()
    habit_items = [i for i in data["items"] if i["type"] == "HABIT_IMPROVEMENT"]
    assert len(habit_items) >= 1
    assert "Protect Streak" in habit_items[0]["title"]
    assert habit_items[0]["priority"] == "HIGH"

def test_recommendation_dismiss_and_complete(client, db_session):
    today = date.today()
    task = Task(
        id=str(uuid.uuid4()),
        title="Refactor CSS Modules",
        task_type="Daily",
        category="Coding",
        priority="High",
        status="Pending",
        start_date=today,
        due_date=today,
    )
    db_session.add(task)
    db_session.commit()

    resp = client.get("/api/recommendations")
    assert resp.status_code == 200
    rec_id = resp.json()["items"][0]["id"]

    # Dismiss
    dismiss_resp = client.post(f"/api/recommendations/{rec_id}/dismiss")
    assert dismiss_resp.status_code == 200
    assert dismiss_resp.json()["status"] == "DISMISSED"

    # Verify no longer in PENDING list
    pending_resp = client.get("/api/recommendations?status=PENDING")
    pending_ids = [r["id"] for r in pending_resp.json()["items"]]
    assert rec_id not in pending_ids

def test_recommendations_deduplication(client, db_session):
    today = date.today()
    task = Task(
        id=str(uuid.uuid4()),
        title="Review PR #42",
        task_type="Daily",
        category="Coding",
        priority="High",
        status="Pending",
        start_date=today,
        due_date=today,
    )
    db_session.add(task)
    db_session.commit()

    # Generate twice
    client.post("/api/recommendations/generate")
    client.post("/api/recommendations/generate")

    all_recs = db_session.query(Recommendation).filter(
        Recommendation.entity_id == task.id,
        Recommendation.status == "PENDING"
    ).all()
    assert len(all_recs) == 1

# ---------------------------------------------------------------------------
# Phase 4.1 New Reliability & Deduplication Tests
# ---------------------------------------------------------------------------

def test_dismissal_cooldown_prevents_immediate_respawn(client, db_session):
    """
    Verifies that a dismissed recommendation does not respawn on subsequent
    recommendation generation calls within the 48-hour cooldown window.
    """
    today = date.today()
    task = Task(
        id=str(uuid.uuid4()),
        title="Fix Memory Leak in Cache",
        task_type="Daily",
        category="Coding",
        priority="High",
        status="Pending",
        start_date=today,
        due_date=today,
    )
    db_session.add(task)
    db_session.commit()

    # 1. Initial generation creates 1 pending recommendation
    resp = client.get("/api/recommendations?status=PENDING")
    assert resp.status_code == 200
    items = resp.json()["items"]
    assert len(items) == 1
    rec_id = items[0]["id"]

    # 2. Dismiss the recommendation
    dismiss_resp = client.post(f"/api/recommendations/{rec_id}/dismiss")
    assert dismiss_resp.status_code == 200
    assert dismiss_resp.json()["status"] == "DISMISSED"

    # 3. Trigger generation again immediately via API
    gen_resp = client.post("/api/recommendations/generate")
    assert gen_resp.status_code == 200

    # 4. Fetch pending recommendations: must NOT respawn
    pending_resp = client.get("/api/recommendations?status=PENDING")
    assert pending_resp.status_code == 200
    assert pending_resp.json()["total_active"] == 0

    # 5. Check database records: dismissed record preserved, no new pending records
    all_recs = db_session.query(Recommendation).filter(Recommendation.entity_id == task.id).all()
    assert len(all_recs) == 1
    assert all_recs[0].id == rec_id
    assert all_recs[0].status == "DISMISSED"

def test_recommendation_regeneration_after_cooldown_expiry(client, db_session):
    """
    Verifies that after the 48-hour cooldown expires, if the underlying condition
    still persists (task still pending and overdue), a recommendation can regenerate.
    """
    now = datetime.now(timezone.utc)
    today = now.date()

    task = Task(
        id=str(uuid.uuid4()),
        title="Submit Annual Compliance Filing",
        task_type="Daily",
        category="Career",
        priority="High",
        status="Pending",
        start_date=today,
        due_date=today,
    )
    db_session.add(task)
    db_session.commit()

    # Generate at T=0
    recs = recommendation_service.generate_recommendations(
        db=db_session,
        cooldown_hours=48,
        current_time=now,
    )
    assert len(recs) == 1
    rec_id = recs[0].id

    # Dismiss at T=0
    recommendation_service.dismiss_recommendation(
        db=db_session,
        rec_id=rec_id,
        current_time=now,
    )

    # At T=24 hours (within cooldown): does NOT regenerate
    recs_t24 = recommendation_service.generate_recommendations(
        db=db_session,
        cooldown_hours=48,
        current_time=now + timedelta(hours=24),
    )
    assert len(recs_t24) == 0

    # At T=49 hours (past 48h cooldown): condition still holds -> REGENERATES
    recs_t49 = recommendation_service.generate_recommendations(
        db=db_session,
        cooldown_hours=48,
        current_time=now + timedelta(hours=49),
    )
    assert len(recs_t49) == 1
    new_rec = recs_t49[0]
    assert new_rec.id != rec_id
    assert new_rec.status == "PENDING"
    assert new_rec.entity_id == task.id

    # Database records preserved: 1 DISMISSED, 1 PENDING
    all_recs = db_session.query(Recommendation).filter(Recommendation.entity_id == task.id).all()
    assert len(all_recs) == 2
    statuses = {r.status for r in all_recs}
    assert statuses == {"DISMISSED", "PENDING"}

def test_different_entities_same_type_not_suppressed(client, db_session):
    """
    Verifies that dismissing a recommendation for Task A does not suppress
    generating the same recommendation type for Task B.
    """
    today = date.today()
    task_a = Task(
        id=str(uuid.uuid4()),
        title="Task Alpha Critical",
        task_type="Daily",
        category="Personal",
        priority="High",
        status="Pending",
        start_date=today,
        due_date=today,
    )
    task_b = Task(
        id=str(uuid.uuid4()),
        title="Task Beta Critical",
        task_type="Daily",
        category="Personal",
        priority="High",
        status="Pending",
        start_date=today,
        due_date=today,
    )
    db_session.add_all([task_a, task_b])
    db_session.commit()

    # Generate: both get PRIORITIZATION
    resp = client.get("/api/recommendations?status=PENDING")
    items = resp.json()["items"]
    assert len(items) == 2

    # Dismiss Task A
    rec_a = next(i for i in items if i["entity_id"] == task_a.id)
    dismiss_resp = client.post(f"/api/recommendations/{rec_a['id']}/dismiss")
    assert dismiss_resp.status_code == 200

    # Regenerate
    client.post("/api/recommendations/generate")
    active_resp = client.get("/api/recommendations?status=PENDING")
    active_items = active_resp.json()["items"]

    # Task A is suppressed; Task B remains active
    active_entities = [i["entity_id"] for i in active_items]
    assert task_a.id not in active_entities
    assert task_b.id in active_entities

def test_accepted_recommendation_prevents_duplicate_generation(client, db_session):
    """
    Verifies that an accepted recommendation suppresses duplicate pending recommendations.
    """
    today = date.today()
    task = Task(
        id=str(uuid.uuid4()),
        title="Database Optimization Sprint",
        task_type="Daily",
        category="Coding",
        priority="High",
        status="Pending",
        start_date=today,
        due_date=today,
    )
    db_session.add(task)
    db_session.commit()

    resp = client.get("/api/recommendations?status=PENDING")
    rec_id = resp.json()["items"][0]["id"]

    # Accept recommendation
    accept_resp = client.post(f"/api/recommendations/{rec_id}/accept")
    assert accept_resp.status_code == 200
    assert accept_resp.json()["status"] == "ACCEPTED"

    # Regenerate
    client.post("/api/recommendations/generate")
    client.post("/api/recommendations/generate")

    # No pending recommendations created for this task
    pending = client.get("/api/recommendations?status=PENDING").json()["items"]
    task_pending = [r for r in pending if r["entity_id"] == task.id]
    assert len(task_pending) == 0

    # Only 1 record in database, in ACCEPTED status
    recs = db_session.query(Recommendation).filter(Recommendation.entity_id == task.id).all()
    assert len(recs) == 1
    assert recs[0].status == "ACCEPTED"

def test_invalid_status_transitions_return_400(client, db_session):
    """
    Verifies that illegal status transitions are rejected with HTTP 400 Bad Request.
    """
    today = date.today()
    task = Task(
        id=str(uuid.uuid4()),
        title="Kernel Patch Verification",
        task_type="Daily",
        category="Coding",
        priority="High",
        status="Pending",
        start_date=today,
        due_date=today,
    )
    db_session.add(task)
    db_session.commit()

    resp = client.get("/api/recommendations?status=PENDING")
    rec_id = resp.json()["items"][0]["id"]

    # 1. Dismiss the recommendation (PENDING -> DISMISSED)
    client.post(f"/api/recommendations/{rec_id}/dismiss")

    # 2. Attempt illegal transition: DISMISSED -> ACCEPTED (returns 400)
    illegal_accept = client.post(f"/api/recommendations/{rec_id}/accept")
    assert illegal_accept.status_code == 400
    assert "Invalid recommendation status transition" in illegal_accept.json()["detail"]

    # 3. Transition from DISMISSED -> COMPLETED is valid (archives/completes recommendation)
    legal_complete = client.post(f"/api/recommendations/{rec_id}/complete")
    assert legal_complete.status_code == 200
    assert legal_complete.json()["status"] == "COMPLETED"

    # 4. Attempt illegal transitions from terminal COMPLETED state (returns 400)
    illegal_reaccept = client.post(f"/api/recommendations/{rec_id}/accept")
    assert illegal_reaccept.status_code == 400
    assert "Invalid recommendation status transition" in illegal_reaccept.json()["detail"]

    illegal_redismiss = client.post(f"/api/recommendations/{rec_id}/dismiss")
    assert illegal_redismiss.status_code == 400
    assert "Invalid recommendation status transition" in illegal_redismiss.json()["detail"]

def test_accepted_recommendation_lifecycle(client, db_session):
    """
    Verifies lifecycle for accepted recommendations:
    PENDING -> ACCEPTED -> COMPLETED, and terminal COMPLETED cannot be modified.
    """
    today = date.today()
    task = Task(
        id=str(uuid.uuid4()),
        title="CI Pipeline Fix",
        task_type="Daily",
        category="Coding",
        priority="High",
        status="Pending",
        start_date=today,
        due_date=today,
    )
    db_session.add(task)
    db_session.commit()

    resp = client.get("/api/recommendations?status=PENDING")
    rec_id = resp.json()["items"][0]["id"]

    # Accept: PENDING -> ACCEPTED
    accept_resp = client.post(f"/api/recommendations/{rec_id}/accept")
    assert accept_resp.status_code == 200
    assert accept_resp.json()["status"] == "ACCEPTED"

    # Legal transition: ACCEPTED -> COMPLETED
    legal_complete = client.post(f"/api/recommendations/{rec_id}/complete")
    assert legal_complete.status_code == 200
    assert legal_complete.json()["status"] == "COMPLETED"

    # Attempt illegal transition: COMPLETED -> ACCEPTED
    illegal_reaccept = client.post(f"/api/recommendations/{rec_id}/accept")
    assert illegal_reaccept.status_code == 400
    assert "Invalid recommendation status transition" in illegal_reaccept.json()["detail"]

def test_auto_sync_completes_pending_and_accepted_recommendations(client, db_session):
    """
    Verifies that completing an entity automatically transitions both PENDING
    and ACCEPTED recommendations to COMPLETED.
    """
    today = date.today()
    task1 = Task(
        id=str(uuid.uuid4()),
        title="Deliverable One",
        task_type="Daily",
        category="Coding",
        priority="High",
        status="Pending",
        start_date=today,
        due_date=today,
    )
    task2 = Task(
        id=str(uuid.uuid4()),
        title="Deliverable Two",
        task_type="Daily",
        category="Coding",
        priority="High",
        status="Pending",
        start_date=today,
        due_date=today,
    )
    db_session.add_all([task1, task2])
    db_session.commit()

    # Generate recommendations
    resp = client.get("/api/recommendations?status=PENDING")
    items = resp.json()["items"]
    rec1 = next(i for i in items if i["entity_id"] == task1.id)
    rec2 = next(i for i in items if i["entity_id"] == task2.id)

    # Accept recommendation 2
    client.post(f"/api/recommendations/{rec2['id']}/accept")

    # Complete both tasks in database
    task1.status = "Completed"
    task2.status = "Completed"
    db_session.commit()

    # Run auto_sync via generation call
    recommendation_service.auto_sync_completed_entities(db_session)

    # Verify both recommendations transitioned to COMPLETED
    r1 = db_session.query(Recommendation).filter(Recommendation.id == rec1["id"]).first()
    r2 = db_session.query(Recommendation).filter(Recommendation.id == rec2["id"]).first()
    assert r1.status == "COMPLETED"
    assert r2.status == "COMPLETED"

def test_different_subtypes_for_same_entity_not_suppressed(client, db_session):
    """
    Verifies that dismissing one subtype for a goal (e.g. Structure Goal)
    does not suppress a different subtype (e.g. Goal Lagging) for that same goal.
    """
    today = date.today()
    goal = Goal(
        id=str(uuid.uuid4()),
        title="Enterprise Certification",
        description="ISO audit",
        goal_type="Short-Term",
        category="Career",
        priority="High",
        start_date=today,
        target_date=today + timedelta(days=7),
        status="In Progress",
        progress=10,
    )
    db_session.add(goal)
    db_session.commit()

    # Step 1: Goal has 0 tasks -> triggers Check 4A: Structure Goal
    recs_1 = recommendation_service.generate_recommendations(db_session)
    struct_rec = next(r for r in recs_1 if r.entity_id == goal.id)
    assert "Structure" in struct_rec.title
    assert struct_rec.action_payload.get("sub_key") == "STRUCTURE"

    # Dismiss the Structure recommendation
    recommendation_service.dismiss_recommendation(db_session, struct_rec.id)

    # Step 2: User adds 1 task to the goal (so Check 4A with 0 tasks no longer triggers)
    task1 = Task(
        id=str(uuid.uuid4()),
        title="Audit Prep Document",
        goal_id=goal.id,
        category="Career",
        priority="High",
        status="Pending",
        start_date=today,
        due_date=today + timedelta(days=5),
    )
    db_session.add(task1)
    db_session.commit()

    # Step 3: Now Check 4B (Goal Lagging: <= 14 days and progress < 50%) is triggered!
    recs_2 = recommendation_service.generate_recommendations(db_session)
    lagging_recs = [r for r in recs_2 if r.entity_id == goal.id and "Lagging" in r.title]
    assert len(lagging_recs) == 1
    assert lagging_recs[0].action_payload.get("sub_key") == "LAGGING"

def test_interaction_tracking_activity_logs(client, db_session):
    """
    Verifies that user interactions (accept, dismiss, complete) are
    tracked in ActivityLog.
    """
    today = date.today()
    task = Task(
        id=str(uuid.uuid4()),
        title="Interaction Verification Task",
        category="Academic",
        priority="High",
        status="Pending",
        start_date=today,
        due_date=today,
    )
    db_session.add(task)
    db_session.commit()

    resp = client.get("/api/recommendations?status=PENDING")
    items = resp.json()["items"]
    rec = next(i for i in items if i["entity_id"] == task.id)
    rec_id = rec["id"]

    # 1. Dismiss recommendation
    client.post(f"/api/recommendations/{rec_id}/dismiss")
    act_dismiss = (
        db_session.query(ActivityLog)
        .filter(
            ActivityLog.event_type == "RECOMMENDATION_DISMISSED",
            ActivityLog.entity_id == rec_id
        )
        .first()
    )
    assert act_dismiss is not None
    assert act_dismiss.details["type"] == rec["type"]

    # 2. Test accept on another recommendation
    task2 = Task(
        id=str(uuid.uuid4()),
        title="Interaction Accept Task",
        category="Reading",
        priority="High",
        status="Pending",
        start_date=today,
        due_date=today,
    )
    db_session.add(task2)
    db_session.commit()

    resp2 = client.get("/api/recommendations?status=PENDING")
    rec2 = next(i for i in resp2.json()["items"] if i["entity_id"] == task2.id)
    rec2_id = rec2["id"]

    client.post(f"/api/recommendations/{rec2_id}/accept")
    act_accept = (
        db_session.query(ActivityLog)
        .filter(
            ActivityLog.event_type == "RECOMMENDATION_ACCEPTED",
            ActivityLog.entity_id == rec2_id
        )
        .first()
    )
    assert act_accept is not None

    # 3. Test complete on the accepted recommendation
    client.post(f"/api/recommendations/{rec2_id}/complete")
    act_comp = (
        db_session.query(ActivityLog)
        .filter(
            ActivityLog.event_type == "RECOMMENDATION_COMPLETED",
            ActivityLog.entity_id == rec2_id
        )
        .first()
    )
    assert act_comp is not None

def test_dismissal_persistence_across_simulated_restart(client, db_session):
    """
    Verifies that a dismissed recommendation stays dismissed and is not
    respawned even after simulating a fresh restart and running generation multiple times.
    """
    today = date.today()
    task = Task(
        id=str(uuid.uuid4()),
        title="Persistent Dismiss Task",
        category="Personal",
        priority="High",
        status="Pending",
        start_date=today,
        due_date=today,
    )
    db_session.add(task)
    db_session.commit()

    # Generate initial recommendation
    r1 = client.get("/api/recommendations?status=PENDING")
    item = next(i for i in r1.json()["items"] if i["entity_id"] == task.id)
    rec_id = item["id"]

    # Dismiss it
    dis_res = client.post(f"/api/recommendations/{rec_id}/dismiss")
    assert dis_res.status_code == 200
    assert dis_res.json()["status"] == "DISMISSED"

    # Simulate backend restart by committing session, clearing caches, and querying cleanly
    db_session.commit()
    db_session.expire_all()

    # Verify state in database is DISMISSED
    persisted = db_session.query(Recommendation).filter(Recommendation.id == rec_id).first()
    assert persisted.status == "DISMISSED"

    # Trigger generation 5 consecutive times (simulating recurring cycles / refreshes)
    for _ in range(5):
        gen_res = client.post("/api/recommendations/generate")
        assert gen_res.status_code == 200
        # The dismissed task recommendation must NOT appear in pending items
        pending_items = gen_res.json()["items"]
        assert not any(p["entity_id"] == task.id for p in pending_items)

    # Verify that still only 1 record exists for this task (no duplicate rows created)
    all_recs = db_session.query(Recommendation).filter(Recommendation.entity_id == task.id).all()
    assert len(all_recs) == 1
    assert all_recs[0].status == "DISMISSED"

def test_dynamic_goal_progress_change_completes_recommendation(client, db_session):
    """
    Verifies that updating goal progress or linking tasks updates recommendations dynamically.
    """
    today = date.today()
    goal = Goal(
        id=str(uuid.uuid4()),
        title="Dynamic Progress Goal",
        category="Health",
        goal_type="Short-Term",
        priority="High",
        status="In Progress",
        progress=20,
        start_date=today,
        target_date=today + timedelta(days=5),
    )
    db_session.add(goal)
    db_session.commit()

    # Step 1: Goal has 0 tasks -> Structure recommendation generated
    r1 = client.get("/api/recommendations?status=PENDING")
    struct_rec = next(i for i in r1.json()["items"] if i["entity_id"] == goal.id)
    assert "Structure" in struct_rec["title"]

    # Step 2: Add a task to goal -> structure recommendation auto-completes!
    t = Task(
        id=str(uuid.uuid4()),
        title="Goal Milestone Deliverable",
        goal_id=goal.id,
        category="Health",
        priority="High",
        status="Pending",
        start_date=today,
        due_date=today + timedelta(days=3),
    )
    db_session.add(t)
    db_session.commit()

    # Sync
    recommendation_service.auto_sync_completed_entities(db_session)
    struct_rec_db = db_session.query(Recommendation).filter(Recommendation.id == struct_rec["id"]).first()
    assert struct_rec_db.status == "COMPLETED"

    # Step 3: Now goal triggers Lagging recommendation (progress is 20 < 50)
    r2 = client.get("/api/recommendations?status=PENDING")
    lagging_rec = next(i for i in r2.json()["items"] if i["entity_id"] == goal.id)
    assert "Lagging" in lagging_rec["title"]

    # Step 4: User updates goal progress to 75% -> lagging recommendation auto-completes!
    goal.progress = 75
    db_session.commit()

    recommendation_service.auto_sync_completed_entities(db_session)
    lagging_rec_db = db_session.query(Recommendation).filter(Recommendation.id == lagging_rec["id"]).first()
    assert lagging_rec_db.status == "COMPLETED"

def test_recommendation_prioritization_hierarchy(client, db_session):
    """
    Verifies sensible prioritization: High priority with immediate/overdue
    deadlines sort ahead of lower priorities.
    """
    today = date.today()

    # Task A: High priority, overdue
    task_a = Task(
        id=str(uuid.uuid4()),
        title="Overdue Critical Fix",
        category="Coding",
        priority="High",
        status="Pending",
        start_date=today - timedelta(days=5),
        due_date=today - timedelta(days=2),
    )
    # Task B: Low priority, future
    task_b = Task(
        id=str(uuid.uuid4()),
        title="Future Documentation",
        category="Reading",
        priority="Low",
        status="Pending",
        start_date=today,
        due_date=today + timedelta(days=10),
    )
    db_session.add_all([task_a, task_b])
    db_session.commit()

    resp = client.get("/api/recommendations?status=PENDING")
    items = resp.json()["items"]

    # Find position of task_a rec vs task_b rec (if generated)
    rec_a_idx = next((idx for idx, i in enumerate(items) if i["entity_id"] == task_a.id), None)
    rec_b_idx = next((idx for idx, i in enumerate(items) if i["entity_id"] == task_b.id), None)

    assert rec_a_idx is not None
    if rec_b_idx is not None:
        assert rec_a_idx < rec_b_idx
    # Task A should be HIGH priority
    assert items[rec_a_idx]["priority"] == "HIGH"

