import json
import sqlite3
from collections.abc import Iterable
from datetime import datetime
from pathlib import Path
from typing import Any, TypeVar

from pydantic import BaseModel


ModelT = TypeVar("ModelT", bound=BaseModel)


def _json_default(value: Any) -> str:
    if isinstance(value, datetime):
        return value.isoformat()
    return str(value)


class SQLiteStore:
    def __init__(self, path: Path):
        self.path = path
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.init_schema()

    def connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.path)
        conn.row_factory = sqlite3.Row
        return conn

    def init_schema(self) -> None:
        with self.connect() as conn:
            conn.executescript(
                """
                CREATE TABLE IF NOT EXISTS tickets (
                    id TEXT PRIMARY KEY,
                    payload TEXT NOT NULL,
                    created_at TEXT NOT NULL
                );
                CREATE TABLE IF NOT EXISTS runs (
                    id TEXT PRIMARY KEY,
                    ticket_id TEXT NOT NULL,
                    status TEXT NOT NULL,
                    current_state TEXT NOT NULL,
                    payload TEXT NOT NULL,
                    created_at TEXT NOT NULL
                );
                CREATE TABLE IF NOT EXISTS trace_events (
                    id TEXT PRIMARY KEY,
                    run_id TEXT NOT NULL,
                    node_name TEXT NOT NULL,
                    event_type TEXT NOT NULL,
                    payload TEXT NOT NULL,
                    created_at TEXT NOT NULL
                );
                CREATE TABLE IF NOT EXISTS approvals (
                    id TEXT PRIMARY KEY,
                    run_id TEXT NOT NULL,
                    status TEXT NOT NULL,
                    payload TEXT NOT NULL,
                    created_at TEXT NOT NULL
                );
                CREATE TABLE IF NOT EXISTS usage_metrics (
                    id TEXT PRIMARY KEY,
                    trace_id TEXT NOT NULL,
                    provider TEXT NOT NULL,
                    payload TEXT NOT NULL,
                    created_at TEXT NOT NULL
                );
                CREATE TABLE IF NOT EXISTS audit_events (
                    id TEXT PRIMARY KEY,
                    actor TEXT NOT NULL,
                    action TEXT NOT NULL,
                    payload TEXT NOT NULL,
                    created_at TEXT NOT NULL
                );
                """
            )

    def upsert_model(self, table: str, model: BaseModel, extra: dict[str, Any] | None = None) -> None:
        payload = model.model_dump(mode="json")
        created_at = payload.get("created_at") or datetime.utcnow().isoformat()
        columns = {"id": payload["id"], "payload": json.dumps(payload, default=_json_default), "created_at": created_at}
        if extra:
            columns.update(extra)
        placeholders = ", ".join(f":{key}" for key in columns)
        names = ", ".join(columns)
        updates = ", ".join(f"{key}=excluded.{key}" for key in columns if key != "id")
        with self.connect() as conn:
            conn.execute(
                f"INSERT INTO {table} ({names}) VALUES ({placeholders}) "
                f"ON CONFLICT(id) DO UPDATE SET {updates}",
                columns,
            )

    def list_models(self, table: str, model_type: type[ModelT], where: str = "", params: Iterable[Any] = ()) -> list[ModelT]:
        query = f"SELECT payload FROM {table} {where}"
        with self.connect() as conn:
            rows = conn.execute(query, tuple(params)).fetchall()
        return [model_type.model_validate_json(row["payload"]) for row in rows]

    def get_model(self, table: str, model_type: type[ModelT], model_id: str) -> ModelT | None:
        with self.connect() as conn:
            row = conn.execute(f"SELECT payload FROM {table} WHERE id = ?", (model_id,)).fetchone()
        if not row:
            return None
        return model_type.model_validate_json(row["payload"])
