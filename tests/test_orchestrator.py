"""
Phase 8.2 — Mission Orchestrator Tests

Tests for run_mission(), MissionLifecycleManager, MissionExecutionContext,
and run_queue(). Validates mission isolation, pipeline reuse, and
sequential multi-mission execution.
"""

import pytest

from core.hive import (
    QueuedMission,
    MissionPriority,
    MissionQueue,
    MissionStatus,
)
from core.mission_orchestrator import (
    ExecutionPhase,
    MissionExecutionContext,
    MissionLifecycleManager,
    run_mission,
    run_queue,
)


def _make_queued(mission_id, field_ha=50.0, crop="wheat", drones=4,
                 priority=MissionPriority.NORMAL, wind=10.0, temp=25.0):
    return QueuedMission(
        mission_id=mission_id,
        field_size_ha=field_ha,
        crop_type=crop,
        num_drones=drones,
        priority=priority,
        wind_speed_kmh=wind,
        temperature_c=temp,
    )


# ===========================================================================
# MissionExecutionContext Tests
# ===========================================================================

class TestMissionExecutionContext:

    def test_default_context(self):
        ctx = MissionExecutionContext(mission_id="test")
        assert ctx.mission_id == "test"
        assert ctx.phase == ExecutionPhase.PENDING
        assert ctx.profile is None
        assert ctx.assessment is None
        assert ctx.swarm is None
        assert ctx.routes is None
        assert ctx.resources is None
        assert ctx.risks is None
        assert ctx.recommendation is None
        assert ctx.timeline is None
        assert ctx.error is None

    def test_execution_phase_values(self):
        assert len(ExecutionPhase) == 11
        values = {p.value for p in ExecutionPhase}
        expected = {
            "pending", "profiling", "analyzing", "planning", "routing",
            "resourcing", "risk_eval", "recommending", "timeline",
            "completed", "failed",
        }
        assert values == expected


# ===========================================================================
# MissionLifecycleManager Tests
# ===========================================================================

class TestMissionLifecycleManager:

    def test_create_context(self):
        mgr = MissionLifecycleManager()
        ctx = mgr.create_context("m1")
        assert ctx.mission_id == "m1"
        assert mgr.total_count == 1

    def test_create_duplicate_raises(self):
        mgr = MissionLifecycleManager()
        mgr.create_context("m1")
        with pytest.raises(ValueError, match="already exists"):
            mgr.create_context("m1")

    def test_get_context(self):
        mgr = MissionLifecycleManager()
        mgr.create_context("m1")
        ctx = mgr.get_context("m1")
        assert ctx.mission_id == "m1"

    def test_get_nonexistent_raises(self):
        mgr = MissionLifecycleManager()
        with pytest.raises(ValueError, match="No execution context"):
            mgr.get_context("nope")

    def test_get_all_contexts(self):
        mgr = MissionLifecycleManager()
        mgr.create_context("m1")
        mgr.create_context("m2")
        all_ctx = mgr.get_all_contexts()
        assert len(all_ctx) == 2

    def test_get_by_phase(self):
        mgr = MissionLifecycleManager()
        ctx1 = mgr.create_context("m1")
        mgr.create_context("m2")
        ctx1.phase = ExecutionPhase.COMPLETED
        pending = mgr.get_by_phase(ExecutionPhase.PENDING)
        completed = mgr.get_by_phase(ExecutionPhase.COMPLETED)
        assert len(pending) == 1
        assert len(completed) == 1

    def test_completed_and_failed_counts(self):
        mgr = MissionLifecycleManager()
        ctx1 = mgr.create_context("m1")
        ctx2 = mgr.create_context("m2")
        ctx3 = mgr.create_context("m3")
        ctx1.phase = ExecutionPhase.COMPLETED
        ctx2.phase = ExecutionPhase.COMPLETED
        ctx3.phase = ExecutionPhase.FAILED
        assert mgr.completed_count == 2
        assert mgr.failed_count == 1


# ===========================================================================
# run_mission() Tests
# ===========================================================================

class TestRunMission:

    def test_successful_execution(self):
        queued = _make_queued("m1")
        lifecycle = MissionLifecycleManager()
        result = run_mission(queued, lifecycle)

        assert result.success is True
        assert result.mission_id == "m1"
        assert result.context.phase == ExecutionPhase.COMPLETED

    def test_all_pipeline_outputs_populated(self):
        queued = _make_queued("m1")
        lifecycle = MissionLifecycleManager()
        result = run_mission(queued, lifecycle)
        ctx = result.context

        assert ctx.profile is not None
        assert ctx.assessment is not None
        assert ctx.swarm is not None
        assert ctx.routes is not None
        assert ctx.resources is not None
        assert ctx.risks is not None
        assert ctx.recommendation is not None
        assert ctx.timeline is not None

    def test_recommendation_matches_v01(self):
        """Standard 50ha/4drone scenario must match v0.1 output."""
        queued = _make_queued("m1", field_ha=50.0, drones=4, wind=10.0, temp=25.0)
        lifecycle = MissionLifecycleManager()
        result = run_mission(queued, lifecycle)
        rec = result.context.recommendation

        assert rec.go_no_go == "GO WITH CAUTION"
        assert round(rec.confidence_pct, 1) == 67.7

    def test_different_field_sizes(self):
        lifecycle = MissionLifecycleManager()

        small = run_mission(_make_queued("small", field_ha=5.0, drones=2), lifecycle)
        large = run_mission(_make_queued("large", field_ha=200.0, drones=8), lifecycle)

        assert small.success is True
        assert large.success is True
        assert len(small.context.swarm.sectors) != len(large.context.swarm.sectors)

    def test_different_crop_types(self):
        lifecycle = MissionLifecycleManager()

        wheat = run_mission(_make_queued("wheat", crop="wheat"), lifecycle)
        corn = run_mission(_make_queued("corn", crop="corn"), lifecycle)

        assert wheat.success is True
        assert corn.success is True

    def test_high_wind_nogo(self):
        """40 km/h wind should produce NO-GO recommendation."""
        queued = _make_queued("windy", wind=40.0)
        lifecycle = MissionLifecycleManager()
        result = run_mission(queued, lifecycle)

        assert result.success is True
        assert result.context.recommendation.go_no_go == "NO-GO"

    def test_explanation_contains_decision(self):
        queued = _make_queued("m1")
        lifecycle = MissionLifecycleManager()
        result = run_mission(queued, lifecycle)

        assert "GO WITH CAUTION" in result.explanation
        assert "m1" in result.explanation

    def test_context_stored_in_lifecycle(self):
        queued = _make_queued("m1")
        lifecycle = MissionLifecycleManager()
        run_mission(queued, lifecycle)

        ctx = lifecycle.get_context("m1")
        assert ctx.phase == ExecutionPhase.COMPLETED


# ===========================================================================
# Mission Isolation Tests
# ===========================================================================

class TestMissionIsolation:

    def test_missions_have_independent_contexts(self):
        """Each mission must get its own isolated context."""
        lifecycle = MissionLifecycleManager()

        r1 = run_mission(_make_queued("m1", field_ha=50.0, drones=4), lifecycle)
        r2 = run_mission(_make_queued("m2", field_ha=100.0, drones=6), lifecycle)

        assert r1.context is not r2.context
        assert r1.context.profile is not r2.context.profile
        assert r1.context.swarm is not r2.context.swarm
        assert r1.context.routes is not r2.context.routes

    def test_mission_does_not_affect_other(self):
        """Running a second mission must not change the first's outputs."""
        lifecycle = MissionLifecycleManager()

        r1 = run_mission(_make_queued("m1", field_ha=50.0, drones=4), lifecycle)
        rec1_decision = r1.context.recommendation.go_no_go
        rec1_confidence = r1.context.recommendation.confidence_pct
        swarm1_sectors = len(r1.context.swarm.sectors)

        # Run a different mission
        run_mission(_make_queued("m2", field_ha=200.0, drones=8), lifecycle)

        # First mission's outputs must be unchanged
        ctx1 = lifecycle.get_context("m1")
        assert ctx1.recommendation.go_no_go == rec1_decision
        assert ctx1.recommendation.confidence_pct == rec1_confidence
        assert len(ctx1.swarm.sectors) == swarm1_sectors

    def test_deterministic_execution(self):
        """Same inputs produce identical results across runs."""
        results = []
        for _ in range(3):
            lifecycle = MissionLifecycleManager()
            r = run_mission(_make_queued("m1"), lifecycle)
            results.append(r)

        for r in results[1:]:
            assert r.context.recommendation.go_no_go == results[0].context.recommendation.go_no_go
            assert r.context.recommendation.confidence_pct == results[0].context.recommendation.confidence_pct
            assert len(r.context.swarm.sectors) == len(results[0].context.swarm.sectors)


# ===========================================================================
# run_queue() Tests
# ===========================================================================

class TestRunQueue:

    def test_process_empty_queue(self):
        queue = MissionQueue()
        lifecycle = MissionLifecycleManager()
        results = run_queue(queue, lifecycle)
        assert results == []

    def test_process_single_mission(self):
        queue = MissionQueue()
        queue.enqueue(_make_queued("m1"))
        lifecycle = MissionLifecycleManager()
        results = run_queue(queue, lifecycle)

        assert len(results) == 1
        assert results[0].success is True
        assert results[0].mission_id == "m1"

    def test_process_multiple_missions(self):
        queue = MissionQueue()
        queue.enqueue(_make_queued("m1", field_ha=50.0))
        queue.enqueue(_make_queued("m2", field_ha=30.0, drones=2))
        queue.enqueue(_make_queued("m3", field_ha=100.0, drones=6))
        lifecycle = MissionLifecycleManager()
        results = run_queue(queue, lifecycle)

        assert len(results) == 3
        assert all(r.success for r in results)

    def test_priority_order_respected(self):
        queue = MissionQueue()
        queue.enqueue(_make_queued("low", priority=MissionPriority.LOW))
        queue.enqueue(_make_queued("critical", priority=MissionPriority.CRITICAL))
        queue.enqueue(_make_queued("normal", priority=MissionPriority.NORMAL))
        lifecycle = MissionLifecycleManager()
        results = run_queue(queue, lifecycle)

        assert results[0].mission_id == "critical"
        assert results[1].mission_id == "normal"
        assert results[2].mission_id == "low"

    def test_queue_status_updated_after_execution(self):
        queue = MissionQueue()
        queue.enqueue(_make_queued("m1"))
        queue.enqueue(_make_queued("m2"))
        lifecycle = MissionLifecycleManager()
        run_queue(queue, lifecycle)

        m1 = queue.get_mission("m1")
        m2 = queue.get_mission("m2")
        assert m1.status == MissionStatus.COMPLETED
        assert m2.status == MissionStatus.COMPLETED

    def test_queue_empty_after_processing(self):
        queue = MissionQueue()
        queue.enqueue(_make_queued("m1"))
        lifecycle = MissionLifecycleManager()
        run_queue(queue, lifecycle)

        assert queue.pending_count == 0
        assert queue.dequeue() is None

    def test_multi_mission_all_independent(self):
        """All missions in a queue batch must have independent results."""
        queue = MissionQueue()
        queue.enqueue(_make_queued("small", field_ha=10.0, drones=2))
        queue.enqueue(_make_queued("large", field_ha=200.0, drones=8))
        lifecycle = MissionLifecycleManager()
        results = run_queue(queue, lifecycle)

        assert len(results) == 2
        small_ctx = results[0].context if results[0].mission_id == "small" else results[1].context
        large_ctx = results[0].context if results[0].mission_id == "large" else results[1].context
        assert len(small_ctx.swarm.sectors) != len(large_ctx.swarm.sectors)


# ===========================================================================
# Backward Compatibility
# ===========================================================================

class TestBackwardCompatibility:

    def test_pipeline_unchanged_without_orchestrator(self):
        """Existing pipeline produces identical output when Orchestrator is not invoked."""
        from core.mission_intake import create_mission_profile
        from core.environment_analyzer import analyze_environment
        from core.swarm_planner import plan_swarm
        from core.route_planner import plan_routes
        from core.resource_planner import plan_resources
        from core.risk_engine import evaluate_risks
        from core.decision_engine import generate_recommendation

        profile = create_mission_profile(
            field_size_ha=50.0, crop_type="wheat", num_drones=4,
            battery_capacity_mah=5000, liquid_capacity_l=10.0,
            temperature_c=25, wind_speed_kmh=10,
        )
        assessment = analyze_environment(profile)
        swarm = plan_swarm(profile, assessment)
        routes = plan_routes(swarm, assessment)
        resources = plan_resources(profile, routes)
        risks = evaluate_risks(profile, assessment, resources, routes)
        rec = generate_recommendation(profile, assessment, swarm, routes, resources, risks)

        assert rec.go_no_go == "GO WITH CAUTION"
        assert round(rec.confidence_pct, 1) == 67.7
        assert swarm.partition_method == "grid"
        assert len(swarm.sectors) == 4

    def test_orchestrated_matches_direct_pipeline(self):
        """Orchestrator output must match direct pipeline execution."""
        # Direct pipeline
        from core.mission_intake import create_mission_profile
        from core.environment_analyzer import analyze_environment
        from core.swarm_planner import plan_swarm
        from core.route_planner import plan_routes
        from core.resource_planner import plan_resources
        from core.risk_engine import evaluate_risks
        from core.decision_engine import generate_recommendation

        profile = create_mission_profile(
            field_size_ha=50.0, crop_type="wheat", num_drones=4,
            battery_capacity_mah=5000, liquid_capacity_l=10.0,
            temperature_c=25, wind_speed_kmh=10,
        )
        assessment = analyze_environment(profile)
        swarm = plan_swarm(profile, assessment)
        routes = plan_routes(swarm, assessment)
        resources = plan_resources(profile, routes)
        risks = evaluate_risks(profile, assessment, resources, routes)
        direct_rec = generate_recommendation(profile, assessment, swarm, routes, resources, risks)

        # Orchestrated pipeline
        lifecycle = MissionLifecycleManager()
        result = run_mission(_make_queued("m1"), lifecycle)
        orch_rec = result.context.recommendation

        assert orch_rec.go_no_go == direct_rec.go_no_go
        assert orch_rec.confidence_pct == direct_rec.confidence_pct
