"""
Mission Orchestrator (Phase 8.2)

Enables execution of multiple missions using the existing Phase 0–7
pipeline. Each mission runs in an isolated context with no shared
mutable state.

This module is an orchestration layer only — it does NOT introduce
scheduling, optimization, resource allocation, or planning logic.
It coordinates execution flow by delegating to existing pipeline
functions.

Components:
- MissionExecutionContext: isolated container for a single mission run
- MissionLifecycleManager: tracks mission execution state transitions
- run_mission(): executes a single mission through the Phase 0–7 pipeline

See docs/architecture/phase8_design.md (Phase 8.2) for design spec.
"""

from dataclasses import dataclass
from enum import Enum
from typing import Optional

from core.hive import QueuedMission, MissionQueue
from core.mission_intake import MissionProfile, create_mission_profile
from core.environment_analyzer import EnvironmentAssessment, analyze_environment
from core.swarm_planner import SwarmPlan, plan_swarm
from core.route_planner import RoutePlan, plan_routes
from core.resource_planner import ResourcePlan, plan_resources
from core.risk_engine import RiskAssessment, evaluate_risks
from core.decision_engine import MissionRecommendation, generate_recommendation
from core.mission_timeline import MissionTimeline, generate_timeline
from utils.logger import get_logger

logger = get_logger("mission_orchestrator")


# =========================================================================
# Execution Lifecycle
# =========================================================================

class ExecutionPhase(Enum):
    """Phases of mission execution through the pipeline."""
    PENDING = "pending"
    PROFILING = "profiling"
    ANALYZING = "analyzing"
    PLANNING = "planning"
    ROUTING = "routing"
    RESOURCING = "resourcing"
    RISK_EVAL = "risk_eval"
    RECOMMENDING = "recommending"
    TIMELINE = "timeline"
    COMPLETED = "completed"
    FAILED = "failed"


@dataclass
class MissionExecutionContext:
    """
    Isolated container for a single mission execution.

    Each mission gets its own context with independent pipeline
    outputs. No mutable state is shared between contexts.
    """
    mission_id: str
    phase: ExecutionPhase = ExecutionPhase.PENDING
    profile: Optional[MissionProfile] = None
    assessment: Optional[EnvironmentAssessment] = None
    swarm: Optional[SwarmPlan] = None
    routes: Optional[RoutePlan] = None
    resources: Optional[ResourcePlan] = None
    risks: Optional[RiskAssessment] = None
    recommendation: Optional[MissionRecommendation] = None
    timeline: Optional[MissionTimeline] = None
    error: Optional[str] = None


class MissionLifecycleManager:
    """
    Tracks mission execution state transitions.

    Maintains a registry of MissionExecutionContexts and provides
    queries on execution status. Does not make scheduling or
    allocation decisions.
    """

    def __init__(self) -> None:
        self._contexts: dict[str, MissionExecutionContext] = {}

    def create_context(self, mission_id: str) -> MissionExecutionContext:
        """Create a new isolated execution context for a mission."""
        if mission_id in self._contexts:
            raise ValueError(
                f"Execution context for mission '{mission_id}' already exists"
            )
        ctx = MissionExecutionContext(mission_id=mission_id)
        self._contexts[mission_id] = ctx
        logger.info("Lifecycle: context created for mission '%s'", mission_id)
        return ctx

    def get_context(self, mission_id: str) -> MissionExecutionContext:
        """Get the execution context for a mission."""
        if mission_id not in self._contexts:
            raise ValueError(
                f"No execution context for mission '{mission_id}'"
            )
        return self._contexts[mission_id]

    def get_all_contexts(self) -> list[MissionExecutionContext]:
        """Return all execution contexts."""
        return list(self._contexts.values())

    def get_by_phase(self, phase: ExecutionPhase) -> list[MissionExecutionContext]:
        """Return all contexts in the given execution phase."""
        return [c for c in self._contexts.values() if c.phase == phase]

    @property
    def total_count(self) -> int:
        """Total number of execution contexts."""
        return len(self._contexts)

    @property
    def completed_count(self) -> int:
        """Number of completed executions."""
        return len(self.get_by_phase(ExecutionPhase.COMPLETED))

    @property
    def failed_count(self) -> int:
        """Number of failed executions."""
        return len(self.get_by_phase(ExecutionPhase.FAILED))


# =========================================================================
# Mission Execution
# =========================================================================

@dataclass
class MissionResult:
    """Complete result of a mission execution."""
    mission_id: str
    success: bool
    context: MissionExecutionContext
    explanation: str


def run_mission(
    queued: QueuedMission,
    lifecycle: MissionLifecycleManager,
) -> MissionResult:
    """
    Execute a single mission through the Phase 0–7 pipeline.

    Creates an isolated MissionExecutionContext, runs each pipeline
    stage sequentially, and returns the complete result. No mutable
    state is shared between missions.

    Pipeline stages (all reuse existing functions):
    1. create_mission_profile()
    2. analyze_environment()
    3. plan_swarm()
    4. plan_routes()
    5. plan_resources()
    6. evaluate_risks()
    7. generate_recommendation()
    8. generate_timeline()

    If any stage fails, the context is marked FAILED with the error
    message and a MissionResult with success=False is returned.
    """
    logger.info(
        "Orchestrator: executing mission '%s' (%.1f ha, %s, %d drones)",
        queued.mission_id, queued.field_size_ha, queued.crop_type,
        queued.num_drones,
    )

    ctx = lifecycle.create_context(queued.mission_id)

    try:
        # Stage 1: Mission Profile
        ctx.phase = ExecutionPhase.PROFILING
        ctx.profile = create_mission_profile(
            field_size_ha=queued.field_size_ha,
            crop_type=queued.crop_type,
            num_drones=queued.num_drones,
            battery_capacity_mah=5000,
            liquid_capacity_l=10.0,
            temperature_c=queued.temperature_c,
            wind_speed_kmh=queued.wind_speed_kmh,
        )

        # Stage 2: Environment Analysis
        ctx.phase = ExecutionPhase.ANALYZING
        ctx.assessment = analyze_environment(ctx.profile)

        # Stage 3: Swarm Planning
        ctx.phase = ExecutionPhase.PLANNING
        ctx.swarm = plan_swarm(ctx.profile, ctx.assessment)

        # Stage 4: Route Planning
        ctx.phase = ExecutionPhase.ROUTING
        ctx.routes = plan_routes(ctx.swarm, ctx.assessment)

        # Stage 5: Resource Planning
        ctx.phase = ExecutionPhase.RESOURCING
        ctx.resources = plan_resources(ctx.profile, ctx.routes)

        # Stage 6: Risk Evaluation
        ctx.phase = ExecutionPhase.RISK_EVAL
        ctx.risks = evaluate_risks(
            ctx.profile, ctx.assessment, ctx.resources, ctx.routes,
        )

        # Stage 7: Recommendation
        ctx.phase = ExecutionPhase.RECOMMENDING
        ctx.recommendation = generate_recommendation(
            ctx.profile, ctx.assessment, ctx.swarm,
            ctx.routes, ctx.resources, ctx.risks,
        )

        # Stage 8: Timeline
        ctx.phase = ExecutionPhase.TIMELINE
        ctx.timeline = generate_timeline(
            ctx.profile, ctx.routes, ctx.resources,
        )

        ctx.phase = ExecutionPhase.COMPLETED

        logger.info(
            "Orchestrator: mission '%s' completed — %s, confidence=%.1f%%",
            queued.mission_id,
            ctx.recommendation.go_no_go,
            ctx.recommendation.confidence_pct,
        )

        return MissionResult(
            mission_id=queued.mission_id,
            success=True,
            context=ctx,
            explanation=(
                f"Mission '{queued.mission_id}' executed successfully. "
                f"Decision: {ctx.recommendation.go_no_go}, "
                f"confidence: {ctx.recommendation.confidence_pct}%, "
                f"duration: {ctx.resources.mission_duration_formatted}."
            ),
        )

    except Exception as e:
        ctx.phase = ExecutionPhase.FAILED
        ctx.error = str(e)
        logger.error(
            "Orchestrator: mission '%s' failed at phase %s — %s",
            queued.mission_id, ctx.phase.value, e,
        )
        return MissionResult(
            mission_id=queued.mission_id,
            success=False,
            context=ctx,
            explanation=(
                f"Mission '{queued.mission_id}' failed: {e}"
            ),
        )


def run_queue(
    queue: MissionQueue,
    lifecycle: MissionLifecycleManager,
) -> list[MissionResult]:
    """
    Execute all queued missions sequentially.

    Dequeues missions one at a time and runs each through the
    Phase 0–7 pipeline in isolation. Each mission gets its own
    MissionExecutionContext. Failed missions do not prevent
    subsequent missions from executing.

    No concurrency, no parallelism — simple sequential execution.
    """
    results: list[MissionResult] = []

    while True:
        queued = queue.dequeue()
        if queued is None:
            break

        result = run_mission(queued, lifecycle)

        if result.success:
            queue.complete(queued.mission_id)
        else:
            queue.fail(queued.mission_id)

        results.append(result)

    logger.info(
        "Orchestrator: queue processed — %d missions, %d succeeded, %d failed",
        len(results),
        sum(1 for r in results if r.success),
        sum(1 for r in results if not r.success),
    )

    return results
