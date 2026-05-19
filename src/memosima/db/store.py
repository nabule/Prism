from __future__ import annotations

import json
import sqlite3
from contextlib import contextmanager
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Iterator


def utc_now() -> str:
    return datetime.now(UTC).isoformat(timespec="seconds")


@dataclass(frozen=True)
class Job:
    id: int
    workspace_id: str
    type: str
    status: str
    idempotency_key: str
    payload: dict[str, Any]
    result: dict[str, Any] | None
    error: str | None
    retry_count: int
    created_at: str
    updated_at: str


class Store:
    def __init__(self, database_path: str | Path):
        self.database_path = Path(database_path)
        self.database_path.parent.mkdir(parents=True, exist_ok=True)

    @contextmanager
    def connect(self) -> Iterator[sqlite3.Connection]:
        connection = sqlite3.connect(self.database_path)
        connection.row_factory = sqlite3.Row
        connection.execute("PRAGMA foreign_keys = ON")
        try:
            yield connection
            connection.commit()
        except Exception:
            connection.rollback()
            raise
        finally:
            connection.close()

    def migrate(self) -> None:
        with self.connect() as connection:
            connection.executescript(
                """
                CREATE TABLE IF NOT EXISTS workspaces (
                  id TEXT PRIMARY KEY,
                  name TEXT NOT NULL,
                  created_at TEXT NOT NULL,
                  updated_at TEXT NOT NULL
                );

                CREATE TABLE IF NOT EXISTS memos (
                  id INTEGER PRIMARY KEY AUTOINCREMENT,
                  workspace_id TEXT NOT NULL,
                  memos_uid TEXT NOT NULL,
                  type TEXT NOT NULL,
                  source_memo_uid TEXT,
                  content_hash TEXT,
                  status TEXT NOT NULL,
                  created_at TEXT NOT NULL,
                  updated_at TEXT NOT NULL,
                  UNIQUE (workspace_id, memos_uid, type),
                  FOREIGN KEY (workspace_id) REFERENCES workspaces(id)
                );

                CREATE TABLE IF NOT EXISTS jobs (
                  id INTEGER PRIMARY KEY AUTOINCREMENT,
                  workspace_id TEXT NOT NULL,
                  type TEXT NOT NULL,
                  status TEXT NOT NULL,
                  idempotency_key TEXT NOT NULL,
                  payload_json TEXT NOT NULL,
                  result_json TEXT,
                  error TEXT,
                  retry_count INTEGER NOT NULL DEFAULT 0,
                  created_at TEXT NOT NULL,
                  updated_at TEXT NOT NULL,
                  UNIQUE (workspace_id, idempotency_key),
                  FOREIGN KEY (workspace_id) REFERENCES workspaces(id)
                );

                CREATE INDEX IF NOT EXISTS idx_jobs_status_created
                  ON jobs(status, created_at);
                """
            )

    def ensure_workspace(self, workspace_id: str, name: str | None = None) -> None:
        now = utc_now()
        with self.connect() as connection:
            connection.execute(
                """
                INSERT INTO workspaces (id, name, created_at, updated_at)
                VALUES (?, ?, ?, ?)
                ON CONFLICT(id) DO UPDATE SET
                  name = excluded.name,
                  updated_at = excluded.updated_at
                """,
                (workspace_id, name or workspace_id, now, now),
            )

    def create_job(
        self,
        *,
        workspace_id: str,
        job_type: str,
        idempotency_key: str,
        payload: dict[str, Any],
    ) -> tuple[Job, bool]:
        now = utc_now()
        payload_json = json.dumps(payload, ensure_ascii=False, sort_keys=True)
        with self.connect() as connection:
            cursor = connection.execute(
                """
                INSERT OR IGNORE INTO jobs (
                  workspace_id, type, status, idempotency_key, payload_json,
                  created_at, updated_at
                )
                VALUES (?, ?, 'pending', ?, ?, ?, ?)
                """,
                (workspace_id, job_type, idempotency_key, payload_json, now, now),
            )
            created = cursor.rowcount == 1
            row = connection.execute(
                """
                SELECT * FROM jobs
                WHERE workspace_id = ? AND idempotency_key = ?
                """,
                (workspace_id, idempotency_key),
            ).fetchone()
        if row is None:
            raise RuntimeError("Job insert did not return a row")
        return _job_from_row(row), created

    def list_jobs(self, *, status: str | None = None, limit: int = 100) -> list[Job]:
        with self.connect() as connection:
            if status:
                rows = connection.execute(
                    """
                    SELECT * FROM jobs
                    WHERE status = ?
                    ORDER BY created_at DESC, id DESC
                    LIMIT ?
                    """,
                    (status, limit),
                ).fetchall()
            else:
                rows = connection.execute(
                    """
                    SELECT * FROM jobs
                    ORDER BY created_at DESC, id DESC
                    LIMIT ?
                    """,
                    (limit,),
                ).fetchall()
        return [_job_from_row(row) for row in rows]

    def get_job(self, job_id: int) -> Job | None:
        with self.connect() as connection:
            row = connection.execute("SELECT * FROM jobs WHERE id = ?", (job_id,)).fetchone()
        return _job_from_row(row) if row else None

    def claim_next_job(self) -> Job | None:
        now = utc_now()
        with self.connect() as connection:
            row = connection.execute(
                """
                SELECT * FROM jobs
                WHERE status = 'pending'
                ORDER BY created_at ASC, id ASC
                LIMIT 1
                """
            ).fetchone()
            if row is None:
                return None
            connection.execute(
                """
                UPDATE jobs
                SET status = 'running', updated_at = ?
                WHERE id = ? AND status = 'pending'
                """,
                (now, row["id"]),
            )
            updated = connection.execute("SELECT * FROM jobs WHERE id = ?", (row["id"],)).fetchone()
        return _job_from_row(updated) if updated else None

    def mark_job_succeeded(self, job_id: int, result: dict[str, Any] | None = None) -> None:
        now = utc_now()
        result_json = json.dumps(result or {}, ensure_ascii=False, sort_keys=True)
        with self.connect() as connection:
            connection.execute(
                """
                UPDATE jobs
                SET status = 'succeeded', result_json = ?, error = NULL, updated_at = ?
                WHERE id = ?
                """,
                (result_json, now, job_id),
            )

    def mark_job_failed(self, job_id: int, error: str, max_attempts: int) -> None:
        now = utc_now()
        with self.connect() as connection:
            row = connection.execute(
                "SELECT retry_count FROM jobs WHERE id = ?",
                (job_id,),
            ).fetchone()
            if row is None:
                return
            retry_count = int(row["retry_count"]) + 1
            status = "pending" if retry_count < max_attempts else "failed"
            connection.execute(
                """
                UPDATE jobs
                SET status = ?, error = ?, retry_count = ?, updated_at = ?
                WHERE id = ?
                """,
                (status, error, retry_count, now, job_id),
            )

    def retry_job(self, job_id: int) -> Job | None:
        now = utc_now()
        with self.connect() as connection:
            connection.execute(
                """
                UPDATE jobs
                SET status = 'pending', error = NULL, retry_count = 0, updated_at = ?
                WHERE id = ? AND status IN ('failed', 'waiting_user')
                """,
                (now, job_id),
            )
            row = connection.execute("SELECT * FROM jobs WHERE id = ?", (job_id,)).fetchone()
        return _job_from_row(row) if row else None

    def upsert_memo(
        self,
        *,
        workspace_id: str,
        memos_uid: str,
        memo_type: str,
        status: str,
        source_memo_uid: str | None = None,
        content_hash: str | None = None,
    ) -> None:
        now = utc_now()
        with self.connect() as connection:
            connection.execute(
                """
                INSERT INTO memos (
                  workspace_id, memos_uid, type, source_memo_uid, content_hash,
                  status, created_at, updated_at
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(workspace_id, memos_uid, type) DO UPDATE SET
                  source_memo_uid = excluded.source_memo_uid,
                  content_hash = excluded.content_hash,
                  status = excluded.status,
                  updated_at = excluded.updated_at
                """,
                (
                    workspace_id,
                    memos_uid,
                    memo_type,
                    source_memo_uid,
                    content_hash,
                    status,
                    now,
                    now,
                ),
            )


def _job_from_row(row: sqlite3.Row) -> Job:
    return Job(
        id=int(row["id"]),
        workspace_id=str(row["workspace_id"]),
        type=str(row["type"]),
        status=str(row["status"]),
        idempotency_key=str(row["idempotency_key"]),
        payload=json.loads(row["payload_json"]),
        result=json.loads(row["result_json"]) if row["result_json"] else None,
        error=row["error"],
        retry_count=int(row["retry_count"]),
        created_at=str(row["created_at"]),
        updated_at=str(row["updated_at"]),
    )
