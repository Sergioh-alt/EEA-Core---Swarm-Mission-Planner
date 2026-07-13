"""
Phase 10C.4 — Digital Twin API Backend.

A thin, READ-ONLY service layer that exposes the existing Digital Twin
(Single Source of Truth) over REST + WebSocket for the ORIÓN UI.

Architecture role:
    Simulation Core → ROS2 transport → Sync Engine → Digital Twin
        → (this backend serializes/streams) → UI

Strict boundaries:
- This layer performs NO decision-making, planning, optimization,
  scheduling, routing, or resource allocation.
- It only SERIALIZES the read-only Digital Twin state and STREAMS it.
- The scripted demonstration mission uses fixed, pre-defined geometry
  (no route generation / no optimizer) and drives the existing
  Simulation Core exclusively through the CommandSchema single entry point.
- It never exposes write access to the Digital Twin to external layers.
"""
