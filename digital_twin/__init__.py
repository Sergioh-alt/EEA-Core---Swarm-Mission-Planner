"""
Phase 10B — Digital Twin Layer.

Single source of truth for the entire swarm state.
Read-only state reconciliation, snapshots, and replay.

Architecture rules:
- NO decision-making
- NO planning logic
- NO mission execution
- NO command generation
- NO direct UI communication
- NO MAVLink access
- NO Hive/optimizer/fleet manager imports

May receive from: Simulation Layer, ROS2 state transport
May expose: Read-only state, Snapshots, Replay
"""
