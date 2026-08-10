"""
Mission Definition Pipeline — persistence layer.

Stores editable design-time artifacts (fields, mission definitions). This is
NOT a runtime source of truth — the Digital Twin remains that. Persistence is
deliberately abstracted behind `DefinitionStore` so the demonstration backend
(SQLite / in-memory) can be replaced by commercial infrastructure in Phase 11
without touching the pipeline or API.

No planning, optimization, or decision logic lives here — pure storage.
"""

from __future__ import annotations

import abc
import json
import sqlite3
import threading
import time
from typing import Optional

from backend.mission_pipeline.deployment import DeploymentRecord
from backend.mission_pipeline.library import (
    ExecutionRecord,
    LibraryEntry,
    ScheduleEntry,
)
from backend.mission_pipeline.models import MissionDefinition
from backend.serializers import JSONObject


class NotFoundError(KeyError):
    """Raised when a requested record does not exist."""


class DefinitionStore(abc.ABC):
    """
    Replaceable persistence contract for the Mission Definition Pipeline.

    A future commercial implementation (Postgres, cloud, ...) only needs to
    satisfy this interface; the pipeline and API depend on nothing else.
    """

    # -- fields (raw JSON records; enriched by 10D.3) ------------------------

    @abc.abstractmethod
    def save_field(self, field_id: str, data: JSONObject) -> JSONObject:
        ...

    @abc.abstractmethod
    def get_field(self, field_id: str) -> JSONObject:
        ...

    @abc.abstractmethod
    def list_fields(self) -> list[JSONObject]:
        ...

    @abc.abstractmethod
    def delete_field(self, field_id: str) -> None:
        ...

    # -- mission definitions -------------------------------------------------

    @abc.abstractmethod
    def save_definition(self, definition: MissionDefinition) -> MissionDefinition:
        ...

    @abc.abstractmethod
    def get_definition(self, definition_id: str) -> MissionDefinition:
        ...

    @abc.abstractmethod
    def list_definitions(self) -> list[MissionDefinition]:
        ...

    @abc.abstractmethod
    def delete_definition(self, definition_id: str) -> None:
        ...

    # -- deployment records (Mission Review — 10D.6) -------------------------

    @abc.abstractmethod
    def save_deployment(self, record: DeploymentRecord) -> DeploymentRecord:
        ...

    @abc.abstractmethod
    def get_deployment(self, mission_id: str) -> DeploymentRecord:
        ...

    @abc.abstractmethod
    def delete_deployment(self, mission_id: str) -> None:
        """Remove a deployment record; a missing record is not an error."""

    # -- mission library (10D.7) ---------------------------------------------

    @abc.abstractmethod
    def save_library_entry(self, entry: LibraryEntry) -> LibraryEntry:
        ...

    @abc.abstractmethod
    def get_library_entry(self, entry_id: str) -> LibraryEntry:
        ...

    @abc.abstractmethod
    def list_library_entries(self) -> list[LibraryEntry]:
        ...

    @abc.abstractmethod
    def delete_library_entry(self, entry_id: str) -> None:
        ...

    # -- schedules (10D.7) ---------------------------------------------------

    @abc.abstractmethod
    def save_schedule(self, schedule: ScheduleEntry) -> ScheduleEntry:
        ...

    @abc.abstractmethod
    def get_schedule(self, schedule_id: str) -> ScheduleEntry:
        ...

    @abc.abstractmethod
    def list_schedules(self) -> list[ScheduleEntry]:
        ...

    @abc.abstractmethod
    def delete_schedule(self, schedule_id: str) -> None:
        ...

    # -- execution history (10D.7) -------------------------------------------

    @abc.abstractmethod
    def save_execution(self, record: ExecutionRecord) -> ExecutionRecord:
        ...

    @abc.abstractmethod
    def get_execution(self, execution_id: str) -> ExecutionRecord:
        ...

    @abc.abstractmethod
    def list_executions(self) -> list[ExecutionRecord]:
        ...


class SQLiteDefinitionStore(DefinitionStore):
    """
    SQLite-backed store for the demonstration stage.

    Records are stored as JSON blobs keyed by id, keeping the schema trivial and
    the contract (not the table shape) authoritative. Thread-safe via a lock;
    connections are opened per operation so it works under the async server.
    """

    def __init__(self, db_path: str) -> None:
        self._db_path = db_path
        self._lock = threading.Lock()
        self._init_schema()

    def _connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self._db_path)
        conn.row_factory = sqlite3.Row
        return conn

    def _init_schema(self) -> None:
        with self._lock, self._connect() as conn:
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS fields (
                    id TEXT PRIMARY KEY,
                    data TEXT NOT NULL,
                    updated_ms INTEGER NOT NULL
                )
                """
            )
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS mission_definitions (
                    id TEXT PRIMARY KEY,
                    data TEXT NOT NULL,
                    updated_ms INTEGER NOT NULL
                )
                """
            )
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS mission_deployments (
                    mission_id TEXT PRIMARY KEY,
                    data TEXT NOT NULL,
                    updated_ms INTEGER NOT NULL
                )
                """
            )
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS library_entries (
                    entry_id TEXT PRIMARY KEY,
                    data TEXT NOT NULL,
                    updated_ms INTEGER NOT NULL
                )
                """
            )
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS mission_schedules (
                    schedule_id TEXT PRIMARY KEY,
                    data TEXT NOT NULL,
                    updated_ms INTEGER NOT NULL
                )
                """
            )
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS mission_executions (
                    execution_id TEXT PRIMARY KEY,
                    data TEXT NOT NULL,
                    started_ms INTEGER NOT NULL
                )
                """
            )

    # -- fields --------------------------------------------------------------

    def save_field(self, field_id: str, data: JSONObject) -> JSONObject:
        record = dict(data)
        record["id"] = field_id
        record["updated_ms"] = int(time.time() * 1000)
        with self._lock, self._connect() as conn:
            conn.execute(
                "INSERT INTO fields (id, data, updated_ms) VALUES (?, ?, ?) "
                "ON CONFLICT(id) DO UPDATE SET data=excluded.data, "
                "updated_ms=excluded.updated_ms",
                (field_id, json.dumps(record), record["updated_ms"]),
            )
        return record

    def get_field(self, field_id: str) -> JSONObject:
        with self._lock, self._connect() as conn:
            row = conn.execute(
                "SELECT data FROM fields WHERE id = ?", (field_id,)
            ).fetchone()
        if row is None:
            raise NotFoundError(field_id)
        return _load_object(row["data"])

    def list_fields(self) -> list[JSONObject]:
        with self._lock, self._connect() as conn:
            rows = conn.execute(
                "SELECT data FROM fields ORDER BY updated_ms DESC"
            ).fetchall()
        return [_load_object(r["data"]) for r in rows]

    def delete_field(self, field_id: str) -> None:
        with self._lock, self._connect() as conn:
            cur = conn.execute("DELETE FROM fields WHERE id = ?", (field_id,))
            if cur.rowcount == 0:
                raise NotFoundError(field_id)

    # -- mission definitions -------------------------------------------------

    def save_definition(self, definition: MissionDefinition) -> MissionDefinition:
        definition.updated_ms = int(time.time() * 1000)
        with self._lock, self._connect() as conn:
            conn.execute(
                "INSERT INTO mission_definitions (id, data, updated_ms) "
                "VALUES (?, ?, ?) ON CONFLICT(id) DO UPDATE SET "
                "data=excluded.data, updated_ms=excluded.updated_ms",
                (
                    definition.id,
                    json.dumps(definition.to_json()),
                    definition.updated_ms,
                ),
            )
        return definition

    def get_definition(self, definition_id: str) -> MissionDefinition:
        with self._lock, self._connect() as conn:
            row = conn.execute(
                "SELECT data FROM mission_definitions WHERE id = ?",
                (definition_id,),
            ).fetchone()
        if row is None:
            raise NotFoundError(definition_id)
        return MissionDefinition.from_json(_load_object(row["data"]))

    def list_definitions(self) -> list[MissionDefinition]:
        with self._lock, self._connect() as conn:
            rows = conn.execute(
                "SELECT data FROM mission_definitions ORDER BY updated_ms DESC"
            ).fetchall()
        return [MissionDefinition.from_json(_load_object(r["data"])) for r in rows]

    def delete_definition(self, definition_id: str) -> None:
        with self._lock, self._connect() as conn:
            cur = conn.execute(
                "DELETE FROM mission_definitions WHERE id = ?", (definition_id,)
            )
            if cur.rowcount == 0:
                raise NotFoundError(definition_id)

    # -- deployment records --------------------------------------------------

    def save_deployment(self, record: DeploymentRecord) -> DeploymentRecord:
        with self._lock, self._connect() as conn:
            conn.execute(
                "INSERT INTO mission_deployments (mission_id, data, updated_ms) "
                "VALUES (?, ?, ?) ON CONFLICT(mission_id) DO UPDATE SET "
                "data=excluded.data, updated_ms=excluded.updated_ms",
                (
                    record.mission_id,
                    json.dumps(record.to_json()),
                    record.updated_ms,
                ),
            )
        return record

    def get_deployment(self, mission_id: str) -> DeploymentRecord:
        with self._lock, self._connect() as conn:
            row = conn.execute(
                "SELECT data FROM mission_deployments WHERE mission_id = ?",
                (mission_id,),
            ).fetchone()
        if row is None:
            raise NotFoundError(mission_id)
        return DeploymentRecord.from_json(_load_object(row["data"]))

    def delete_deployment(self, mission_id: str) -> None:
        with self._lock, self._connect() as conn:
            conn.execute(
                "DELETE FROM mission_deployments WHERE mission_id = ?",
                (mission_id,),
            )

    # -- mission library -----------------------------------------------------

    def save_library_entry(self, entry: LibraryEntry) -> LibraryEntry:
        entry.updated_ms = int(time.time() * 1000)
        with self._lock, self._connect() as conn:
            conn.execute(
                "INSERT INTO library_entries (entry_id, data, updated_ms) "
                "VALUES (?, ?, ?) ON CONFLICT(entry_id) DO UPDATE SET "
                "data=excluded.data, updated_ms=excluded.updated_ms",
                (entry.entry_id, json.dumps(entry.to_json()), entry.updated_ms),
            )
        return entry

    def get_library_entry(self, entry_id: str) -> LibraryEntry:
        with self._lock, self._connect() as conn:
            row = conn.execute(
                "SELECT data FROM library_entries WHERE entry_id = ?", (entry_id,)
            ).fetchone()
        if row is None:
            raise NotFoundError(entry_id)
        return LibraryEntry.from_json(_load_object(row["data"]))

    def list_library_entries(self) -> list[LibraryEntry]:
        with self._lock, self._connect() as conn:
            rows = conn.execute(
                "SELECT data FROM library_entries ORDER BY updated_ms DESC"
            ).fetchall()
        return [LibraryEntry.from_json(_load_object(r["data"])) for r in rows]

    def delete_library_entry(self, entry_id: str) -> None:
        with self._lock, self._connect() as conn:
            cur = conn.execute(
                "DELETE FROM library_entries WHERE entry_id = ?", (entry_id,)
            )
            if cur.rowcount == 0:
                raise NotFoundError(entry_id)

    # -- schedules -----------------------------------------------------------

    def save_schedule(self, schedule: ScheduleEntry) -> ScheduleEntry:
        schedule.updated_ms = int(time.time() * 1000)
        with self._lock, self._connect() as conn:
            conn.execute(
                "INSERT INTO mission_schedules (schedule_id, data, updated_ms) "
                "VALUES (?, ?, ?) ON CONFLICT(schedule_id) DO UPDATE SET "
                "data=excluded.data, updated_ms=excluded.updated_ms",
                (
                    schedule.schedule_id,
                    json.dumps(schedule.to_json()),
                    schedule.updated_ms,
                ),
            )
        return schedule

    def get_schedule(self, schedule_id: str) -> ScheduleEntry:
        with self._lock, self._connect() as conn:
            row = conn.execute(
                "SELECT data FROM mission_schedules WHERE schedule_id = ?",
                (schedule_id,),
            ).fetchone()
        if row is None:
            raise NotFoundError(schedule_id)
        return ScheduleEntry.from_json(_load_object(row["data"]))

    def list_schedules(self) -> list[ScheduleEntry]:
        with self._lock, self._connect() as conn:
            rows = conn.execute(
                "SELECT data FROM mission_schedules ORDER BY updated_ms DESC"
            ).fetchall()
        return [ScheduleEntry.from_json(_load_object(r["data"])) for r in rows]

    def delete_schedule(self, schedule_id: str) -> None:
        with self._lock, self._connect() as conn:
            cur = conn.execute(
                "DELETE FROM mission_schedules WHERE schedule_id = ?",
                (schedule_id,),
            )
            if cur.rowcount == 0:
                raise NotFoundError(schedule_id)

    # -- execution history ---------------------------------------------------

    def save_execution(self, record: ExecutionRecord) -> ExecutionRecord:
        with self._lock, self._connect() as conn:
            conn.execute(
                "INSERT INTO mission_executions (execution_id, data, started_ms) "
                "VALUES (?, ?, ?) ON CONFLICT(execution_id) DO UPDATE SET "
                "data=excluded.data",
                (
                    record.execution_id,
                    json.dumps(record.to_json()),
                    record.started_ms,
                ),
            )
        return record

    def get_execution(self, execution_id: str) -> ExecutionRecord:
        with self._lock, self._connect() as conn:
            row = conn.execute(
                "SELECT data FROM mission_executions WHERE execution_id = ?",
                (execution_id,),
            ).fetchone()
        if row is None:
            raise NotFoundError(execution_id)
        return ExecutionRecord.from_json(_load_object(row["data"]))

    def list_executions(self) -> list[ExecutionRecord]:
        with self._lock, self._connect() as conn:
            rows = conn.execute(
                "SELECT data FROM mission_executions ORDER BY started_ms DESC"
            ).fetchall()
        return [ExecutionRecord.from_json(_load_object(r["data"])) for r in rows]


class InMemoryDefinitionStore(DefinitionStore):
    """Non-persistent store for tests and ephemeral usage."""

    def __init__(self) -> None:
        self._fields: dict[str, JSONObject] = {}
        self._definitions: dict[str, MissionDefinition] = {}
        self._deployments: dict[str, DeploymentRecord] = {}
        self._library: dict[str, LibraryEntry] = {}
        self._schedules: dict[str, ScheduleEntry] = {}
        self._executions: dict[str, ExecutionRecord] = {}
        self._lock = threading.Lock()

    def save_field(self, field_id: str, data: JSONObject) -> JSONObject:
        record = dict(data)
        record["id"] = field_id
        record["updated_ms"] = int(time.time() * 1000)
        with self._lock:
            self._fields[field_id] = record
        return record

    def get_field(self, field_id: str) -> JSONObject:
        with self._lock:
            if field_id not in self._fields:
                raise NotFoundError(field_id)
            return dict(self._fields[field_id])

    def list_fields(self) -> list[JSONObject]:
        with self._lock:
            return [dict(v) for v in self._fields.values()]

    def delete_field(self, field_id: str) -> None:
        with self._lock:
            if field_id not in self._fields:
                raise NotFoundError(field_id)
            del self._fields[field_id]

    def save_definition(self, definition: MissionDefinition) -> MissionDefinition:
        definition.updated_ms = int(time.time() * 1000)
        with self._lock:
            self._definitions[definition.id] = definition
        return definition

    def get_definition(self, definition_id: str) -> MissionDefinition:
        with self._lock:
            if definition_id not in self._definitions:
                raise NotFoundError(definition_id)
            return self._definitions[definition_id]

    def list_definitions(self) -> list[MissionDefinition]:
        with self._lock:
            return list(self._definitions.values())

    def delete_definition(self, definition_id: str) -> None:
        with self._lock:
            if definition_id not in self._definitions:
                raise NotFoundError(definition_id)
            del self._definitions[definition_id]

    def save_deployment(self, record: DeploymentRecord) -> DeploymentRecord:
        with self._lock:
            self._deployments[record.mission_id] = record
        return record

    def get_deployment(self, mission_id: str) -> DeploymentRecord:
        with self._lock:
            if mission_id not in self._deployments:
                raise NotFoundError(mission_id)
            return self._deployments[mission_id]

    def delete_deployment(self, mission_id: str) -> None:
        with self._lock:
            self._deployments.pop(mission_id, None)

    def save_library_entry(self, entry: LibraryEntry) -> LibraryEntry:
        entry.updated_ms = int(time.time() * 1000)
        with self._lock:
            self._library[entry.entry_id] = entry
        return entry

    def get_library_entry(self, entry_id: str) -> LibraryEntry:
        with self._lock:
            if entry_id not in self._library:
                raise NotFoundError(entry_id)
            return self._library[entry_id]

    def list_library_entries(self) -> list[LibraryEntry]:
        with self._lock:
            return sorted(
                self._library.values(), key=lambda e: e.updated_ms, reverse=True
            )

    def delete_library_entry(self, entry_id: str) -> None:
        with self._lock:
            if entry_id not in self._library:
                raise NotFoundError(entry_id)
            del self._library[entry_id]

    def save_schedule(self, schedule: ScheduleEntry) -> ScheduleEntry:
        schedule.updated_ms = int(time.time() * 1000)
        with self._lock:
            self._schedules[schedule.schedule_id] = schedule
        return schedule

    def get_schedule(self, schedule_id: str) -> ScheduleEntry:
        with self._lock:
            if schedule_id not in self._schedules:
                raise NotFoundError(schedule_id)
            return self._schedules[schedule_id]

    def list_schedules(self) -> list[ScheduleEntry]:
        with self._lock:
            return sorted(
                self._schedules.values(), key=lambda s: s.updated_ms, reverse=True
            )

    def delete_schedule(self, schedule_id: str) -> None:
        with self._lock:
            if schedule_id not in self._schedules:
                raise NotFoundError(schedule_id)
            del self._schedules[schedule_id]

    def save_execution(self, record: ExecutionRecord) -> ExecutionRecord:
        with self._lock:
            self._executions[record.execution_id] = record
        return record

    def get_execution(self, execution_id: str) -> ExecutionRecord:
        with self._lock:
            if execution_id not in self._executions:
                raise NotFoundError(execution_id)
            return self._executions[execution_id]

    def list_executions(self) -> list[ExecutionRecord]:
        with self._lock:
            return sorted(
                self._executions.values(), key=lambda r: r.started_ms, reverse=True
            )


def _load_object(raw: str) -> JSONObject:
    parsed = json.loads(raw)
    if not isinstance(parsed, dict):
        raise ValueError("Stored record is not a JSON object")
    return parsed


def create_default_store(db_path: Optional[str]) -> DefinitionStore:
    """Factory: SQLite when a path is provided, else in-memory."""
    if db_path:
        return SQLiteDefinitionStore(db_path)
    return InMemoryDefinitionStore()
