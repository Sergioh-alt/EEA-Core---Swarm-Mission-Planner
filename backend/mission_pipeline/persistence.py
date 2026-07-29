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


class InMemoryDefinitionStore(DefinitionStore):
    """Non-persistent store for tests and ephemeral usage."""

    def __init__(self) -> None:
        self._fields: dict[str, JSONObject] = {}
        self._definitions: dict[str, MissionDefinition] = {}
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
