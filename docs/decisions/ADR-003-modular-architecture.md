# ADR-003: Modular Pipeline Architecture

**Status**: Accepted
**Date**: 2026-06-21

## Context

The planning system must:
- Process mission parameters through multiple analysis stages
- Allow individual modules to be replaced or upgraded independently
- Support future integration with real sensors, ML models, and drone hardware
- Follow EEA Core's architectural philosophy of model independence and persistent knowledge

Design patterns considered:
- **Monolithic processor**: Single function that does everything
- **Event-driven**: Modules communicate via events/messages
- **Pipeline**: Sequential data transformation through typed stages
- **Agent-based**: Each module as an autonomous agent with its own decision loop

## Decision

Adopt a **typed pipeline architecture** where:
1. Each module is a pure function: `Input → Output`
2. Modules communicate through typed dataclasses (no shared state)
3. The pipeline follows the EEA Core decision cycle: Observe → Analyze → Plan → Decide → Recommend
4. The orchestrator (`app.py`) owns the pipeline execution order

```
MissionProfile → EnvironmentAssessment → SwarmPlan → RoutePlan → ResourcePlan → RiskAssessment → Recommendation
```

## Consequences

**Positive**:
- Each module can be tested in isolation with mock inputs
- Clear data contracts between modules (dataclass schemas)
- Easy to insert new modules (e.g., sensor fusion between Environment Analyzer and Swarm Planner)
- No hidden dependencies or side effects
- Natural mapping to EEA Core's agent model (each module = one agent's responsibility)
- Future: modules can run in parallel where dependencies allow

**Negative**:
- Linear pipeline doesn't support feedback loops (e.g., Risk Engine suggesting swarm reconfiguration)
- All intermediate data must be passed explicitly through the chain
- Adding a module requires updating the orchestrator

**Mitigations**:
- Version 0.2+ will introduce feedback loops via the Decision Engine requesting replanning
- The orchestrator is a single function — adding a module is a one-line change
- Dataclass contracts make interface changes explicit and traceable
