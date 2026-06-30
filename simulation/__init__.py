"""
Phase 10A — Simulation Core.

Multi-drone simulation environment with MAVLink bridge,
ROS2-compatible state bus, and failure injection.

Architecture rules:
- Simulation is execution + transport ONLY
- NO decision-making logic
- NO Hive state modification
- NO UI logic
- All commands flow through CommandSchema
"""
