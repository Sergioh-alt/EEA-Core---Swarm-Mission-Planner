"""
ORION Phase 10D.2 — Mission Definition Pipeline.

The Mission Definition Pipeline is the central design-time contract that bridges
the user planning experience and Digital Twin execution:

    User Planning Experience
            -> Mission Definition   (created/edited by the UI, persisted here)
            -> Planning Core        (existing core/ pipeline — no new algorithms)
            -> Mission Package       (execution-ready artifact)
            -> Digital Twin / Mission Control

Boundary (see docs/architecture/ORION Phase 10D Boundary Specification):
    * This package NEVER implements planning/optimization/allocation algorithms.
      It only orchestrates the existing core/ functions and persists artifacts.
    * It NEVER mutates Digital Twin runtime state.
    * It contains NO UI rendering.

The persistence layer is intentionally replaceable (see persistence.py) so the
demonstration store (SQLite) can evolve into commercial infrastructure in
Phase 11 without rebuilding the contract.
"""

from backend.mission_pipeline.models import (
    EnvironmentParams,
    FieldDefinition,
    FieldImage,
    FieldSpec,
    FleetItem,
    MissionDefinition,
    MissionPackage,
    Obstacle,
    OperationParams,
    ProductSelection,
    Zone,
)

__all__ = [
    "EnvironmentParams",
    "FieldDefinition",
    "FieldImage",
    "FieldSpec",
    "FleetItem",
    "MissionDefinition",
    "MissionPackage",
    "Obstacle",
    "OperationParams",
    "ProductSelection",
    "Zone",
]
