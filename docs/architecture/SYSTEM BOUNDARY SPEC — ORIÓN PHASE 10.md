SYSTEM BOUNDARY SPEC — ORIÓN PHASE 10
0. DEFINICIÓN GENERAL

Este sistema define los límites estrictos de comunicación entre:

Simulation Layer (PX4 SITL)
Hive Core (decisión y orquestación)
ROS2 Swarm Bus (estado distribuido)
MAVLink Execution Layer (drones)
Digital Twin (truth model)
UI GCS (visualización + control intent)
1. ROS2 MESSAGE SCHEMA (SWARM BUS)
1.1 DroneState.msg
{
  "drone_id": "string",
  "timestamp": "int64",
  "position": {
    "lat": "float",
    "lon": "float",
    "alt": "float"
  },
  "velocity": {
    "vx": "float",
    "vy": "float",
    "vz": "float"
  },
  "battery": {
    "percentage": "float",
    "voltage": "float"
  },
  "state": "IDLE | ACTIVE | RETURNING | CHARGING | FAIL",
  "health": "OK | WARNING | CRITICAL"
}
1.2 SwarmState.msg
{
  "mission_id": "string",
  "active_drones": ["drone_id"],
  "completed_tasks": ["task_id"],
  "pending_tasks": ["task_id"],
  "global_coverage": "float",
  "timestamp": "int64"
}
1.3 Event.msg
{
  "event_type": "FAILURE | PLAGUE_DETECTED | BATTERY_LOW | GEO_ALERT",
  "source": "drone_id",
  "severity": "LOW | MEDIUM | HIGH",
  "payload": {},
  "timestamp": "int64"
}
2. MAVLINK COMMAND ENVELOPE
2.1 CommandSchema (STRICT EXECUTION UNIT)
{
  "command_id": "string",
  "drone_id": "string",
  "command_type": "TAKEOFF | LAND | GOTO | SPRAY | HOVER | RTH",
  "params": {
    "lat": "float",
    "lon": "float",
    "alt": "float",
    "duration": "float",
    "intensity": "float"
  },
  "priority": "LOW | NORMAL | HIGH | EMERGENCY",
  "ack_required": true,
  "timeout_ms": 3000
}
2.2 ExecutionResult
{
  "command_id": "string",
  "status": "ACK | NACK | TIMEOUT",
  "drone_state": "string",
  "error": "string | null",
  "timestamp": "int64"
}
REGLA CRÍTICA

Ningún comando puede ejecutarse sin ACK del nivel inferior

3. DIGITAL TWIN STATE MODEL
3.1 Truth Model (SINGLE SOURCE OF TRUTH)
{
  "mission_state": {
    "mission_id": "string",
    "status": "RUNNING | PAUSED | FAILED | COMPLETED"
  },
  "fleet_state": {
    "total": "int",
    "active": "int",
    "failed": "int"
  },
  "drone_states": {
    "drone_id": "DroneState"
  },
  "resource_state": {
    "battery_pool": "float",
    "liquid_pool": "float"
  },
  "simulation_sync": {
    "drift_score": "float",
    "last_sync": "int64"
  }
}
3.2 Sync Rules
Simulation NEVER overrides Twin directamente
Twin CAN correct Simulation
Drift > threshold → reconciliation event
3.3 Drift Event
{
  "type": "DRIFT_DETECTED",
  "severity": "LOW | HIGH",
  "source": "simulation | hive",
  "delta": {},
  "timestamp": "int64"
}
4. UI DATA CONTRACT (GCS FRONTEND)
4.1 UI State Model
{
  "fleet": [
    {
      "id": "string",
      "position": {},
      "status": "string",
      "battery": "float"
    }
  ],
  "missions": [],
  "telemetry_stream": [],
  "alerts": [],
  "map_layers": [],
  "simulation_time": "int64",
  "selected_drone": "string"
}
4.2 UI RULES (ABSOLUTE)
UI NO tiene lógica de decisión
UI NO calcula rutas
UI NO asigna drones
UI SOLO:
visualiza
envía intentos (intent layer)
4.3 UI INTENT LAYER
{
  "intent_type": "START_MISSION | PAUSE | STOP | REPLAY",
  "payload": {},
  "user_id": "string",
  "timestamp": "int64"
}
5. WEBHOOK / EVENT BUS SCHEMA
5.1 External Event Format
{
  "source": "orion-core",
  "event_type": "MISSION_UPDATE | DRONE_EVENT | SYSTEM_ALERT",
  "severity": "INFO | WARNING | CRITICAL",
  "data": {},
  "timestamp": "int64"
}
5.2 Event Routing Rules
Hive emite eventos
UI solo subscribe
External systems SOLO reciben eventos filtrados
Nunca write-back externo directo al core
6. CROSS-LAYER BOUNDARY RULES
HARD RULES (NO EXCEPTIONS)
6.1 Simulation
NO puede modificar Hive state
6.2 Hive
NO puede renderizar UI
NO puede ejecutar MAVLink directamente
6.3 UI
NO puede emitir comandos directos
6.4 ROS2
Solo transporte de estado
NO lógica
6.5 MAVLink
Solo ejecución
NO interpretación de misión
7. SYSTEM INTEGRITY MODEL
Flujo correcto:
UI → Intent → Hive → Command Schema → MAVLink → Drone
                                      ↓
                            ROS2 State Stream
                                      ↓
                                Digital Twin
                                      ↓
                                     UI
8. SUCCESS CRITERIA (BOUNDARY VALIDATION)

El sistema es válido si:

0 cross-layer leaks
ROS2 solo transporta estado
UI no ejecuta lógica
MAVLink no recibe comandos sin ACK
Digital Twin mantiene coherencia >99%
Simulation reproducible bit-by-bit
Hive es único orquestador
9. CONCLUSIÓN

Este boundary define:

separación total de responsabilidades
contratos estrictos entre capas
base para Phase 10A–10C sin ambigüedad
escalabilidad a hardware real
