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


@dataclass(frozen=True)
class TagCandidateRecord:
    id: int
    workspace_id: str
    path: str
    parent_path: str | None
    status: str
    reason: str
    source_memo_uid: str | None
    similar_tags: list[str]
    confidence: float
    reviewer_note: str | None
    created_at: str
    updated_at: str


@dataclass(frozen=True)
class MemoRecord:
    id: int
    workspace_id: str
    memos_uid: str
    type: str
    source_memo_uid: str | None
    content_hash: str | None
    status: str
    created_at: str
    updated_at: str


@dataclass(frozen=True)
class BusinessTagRecord:
    id: int
    workspace_id: str
    path: str
    status: str
    source: str
    created_at: str
    updated_at: str


@dataclass(frozen=True)
class ArtifactRecord:
    id: int
    workspace_id: str
    memo_uid: str
    resource_uid: str | None
    kind: str
    content_markdown: str
    metadata: dict[str, Any]
    created_at: str


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

                CREATE TABLE IF NOT EXISTS tag_candidates (
                  id INTEGER PRIMARY KEY AUTOINCREMENT,
                  workspace_id TEXT NOT NULL,
                  path TEXT NOT NULL,
                  parent_path TEXT,
                  status TEXT NOT NULL,
                  reason TEXT NOT NULL,
                  source_memo_uid TEXT,
                  similar_tags_json TEXT NOT NULL,
                  confidence REAL NOT NULL,
                  reviewer_note TEXT,
                  created_at TEXT NOT NULL,
                  updated_at TEXT NOT NULL,
                  UNIQUE (workspace_id, path),
                  FOREIGN KEY (workspace_id) REFERENCES workspaces(id)
                );

                CREATE INDEX IF NOT EXISTS idx_tag_candidates_status_created
                  ON tag_candidates(status, created_at);

                CREATE TABLE IF NOT EXISTS business_tags (
                  id INTEGER PRIMARY KEY AUTOINCREMENT,
                  workspace_id TEXT NOT NULL,
                  path TEXT NOT NULL,
                  status TEXT NOT NULL,
                  source TEXT NOT NULL,
                  created_at TEXT NOT NULL,
                  updated_at TEXT NOT NULL,
                  UNIQUE (workspace_id, path),
                  FOREIGN KEY (workspace_id) REFERENCES workspaces(id)
                );

                CREATE INDEX IF NOT EXISTS idx_business_tags_status_path
                  ON business_tags(status, path);

                CREATE TABLE IF NOT EXISTS artifacts (
                  id INTEGER PRIMARY KEY AUTOINCREMENT,
                  workspace_id TEXT NOT NULL,
                  memo_uid TEXT NOT NULL,
                  resource_uid TEXT,
                  kind TEXT NOT NULL,
                  content_markdown TEXT NOT NULL,
                  metadata_json TEXT NOT NULL,
                  created_at TEXT NOT NULL,
                  UNIQUE (workspace_id, memo_uid, resource_uid, kind),
                  FOREIGN KEY (workspace_id) REFERENCES workspaces(id)
                );

                CREATE INDEX IF NOT EXISTS idx_artifacts_memo_kind
                  ON artifacts(workspace_id, memo_uid, kind);
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

    def mark_job_waiting_user(self, job_id: int, result: dict[str, Any] | None = None) -> None:
        now = utc_now()
        result_json = json.dumps(result or {}, ensure_ascii=False, sort_keys=True)
        with self.connect() as connection:
            connection.execute(
                """
                UPDATE jobs
                SET status = 'waiting_user', result_json = ?, error = NULL, updated_at = ?
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

    def list_memos(
        self,
        *,
        workspace_id: str,
        memo_type: str | None = None,
        source_memo_uid: str | None = None,
        limit: int = 100,
    ) -> list[MemoRecord]:
        conditions = ["workspace_id = ?"]
        params: list[Any] = [workspace_id]
        if memo_type is not None:
            conditions.append("type = ?")
            params.append(memo_type)
        if source_memo_uid is not None:
            conditions.append("source_memo_uid = ?")
            params.append(source_memo_uid)
        params.append(limit)
        with self.connect() as connection:
            rows = connection.execute(
                f"""
                SELECT * FROM memos
                WHERE {" AND ".join(conditions)}
                ORDER BY created_at DESC, id DESC
                LIMIT ?
                """,
                params,
            ).fetchall()
        return [_memo_from_row(row) for row in rows]

    def upsert_tag_candidate(
        self,
        *,
        workspace_id: str,
        path: str,
        reason: str,
        parent_path: str | None = None,
        source_memo_uid: str | None = None,
        similar_tags: list[str] | None = None,
        confidence: float = 0.5,
    ) -> TagCandidateRecord:
        now = utc_now()
        similar_tags_json = json.dumps(similar_tags or [], ensure_ascii=False, sort_keys=True)
        with self.connect() as connection:
            connection.execute(
                """
                INSERT INTO tag_candidates (
                  workspace_id, path, parent_path, status, reason, source_memo_uid,
                  similar_tags_json, confidence, created_at, updated_at
                )
                VALUES (?, ?, ?, 'candidate', ?, ?, ?, ?, ?, ?)
                ON CONFLICT(workspace_id, path) DO UPDATE SET
                  parent_path = excluded.parent_path,
                  reason = excluded.reason,
                  source_memo_uid = excluded.source_memo_uid,
                  similar_tags_json = excluded.similar_tags_json,
                  confidence = excluded.confidence,
                  updated_at = excluded.updated_at
                WHERE tag_candidates.status = 'candidate'
                """,
                (
                    workspace_id,
                    path,
                    parent_path,
                    reason,
                    source_memo_uid,
                    similar_tags_json,
                    confidence,
                    now,
                    now,
                ),
            )
            row = connection.execute(
                """
                SELECT * FROM tag_candidates
                WHERE workspace_id = ? AND path = ?
                """,
                (workspace_id, path),
            ).fetchone()
        if row is None:
            raise RuntimeError("Tag candidate upsert did not return a row")
        return _tag_candidate_from_row(row)

    def list_tag_candidates(
        self,
        *,
        workspace_id: str,
        status: str | None = None,
        limit: int = 100,
    ) -> list[TagCandidateRecord]:
        with self.connect() as connection:
            if status:
                rows = connection.execute(
                    """
                    SELECT * FROM tag_candidates
                    WHERE workspace_id = ? AND status = ?
                    ORDER BY created_at DESC, id DESC
                    LIMIT ?
                    """,
                    (workspace_id, status, limit),
                ).fetchall()
            else:
                rows = connection.execute(
                    """
                    SELECT * FROM tag_candidates
                    WHERE workspace_id = ?
                    ORDER BY created_at DESC, id DESC
                    LIMIT ?
                    """,
                    (workspace_id, limit),
                ).fetchall()
        return [_tag_candidate_from_row(row) for row in rows]

    def review_tag_candidate(
        self,
        *,
        candidate_id: int,
        status: str,
        reviewer_note: str | None = None,
    ) -> TagCandidateRecord | None:
        if status not in {"approved", "rejected"}:
            raise ValueError(f"Unsupported tag candidate review status: {status}")
        now = utc_now()
        with self.connect() as connection:
            connection.execute(
                """
                UPDATE tag_candidates
                SET status = ?, reviewer_note = ?, updated_at = ?
                WHERE id = ? AND status = 'candidate'
                """,
                (status, reviewer_note, now, candidate_id),
            )
            row = connection.execute(
                "SELECT * FROM tag_candidates WHERE id = ?",
                (candidate_id,),
            ).fetchone()
            if row is not None and status == "approved" and row["status"] == "approved":
                connection.execute(
                    """
                    INSERT INTO business_tags (
                      workspace_id, path, status, source, created_at, updated_at
                    )
                    VALUES (?, ?, 'active', 'candidate_review', ?, ?)
                    ON CONFLICT(workspace_id, path) DO UPDATE SET
                      status = 'active',
                      source = excluded.source,
                      updated_at = excluded.updated_at
                    """,
                    (row["workspace_id"], row["path"], now, now),
                )
        return _tag_candidate_from_row(row) if row else None

    def list_business_tags(
        self,
        *,
        workspace_id: str,
        status: str | None = "active",
        limit: int = 1000,
    ) -> list[BusinessTagRecord]:
        with self.connect() as connection:
            if status:
                rows = connection.execute(
                    """
                    SELECT * FROM business_tags
                    WHERE workspace_id = ? AND status = ?
                    ORDER BY path ASC
                    LIMIT ?
                    """,
                    (workspace_id, status, limit),
                ).fetchall()
            else:
                rows = connection.execute(
                    """
                    SELECT * FROM business_tags
                    WHERE workspace_id = ?
                    ORDER BY path ASC
                    LIMIT ?
                    """,
                    (workspace_id, limit),
                ).fetchall()
        return [_business_tag_from_row(row) for row in rows]

    def upsert_artifact(
        self,
        *,
        workspace_id: str,
        memo_uid: str,
        kind: str,
        content_markdown: str,
        resource_uid: str | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> ArtifactRecord:
        now = utc_now()
        metadata_json = json.dumps(metadata or {}, ensure_ascii=False, sort_keys=True)
        with self.connect() as connection:
            connection.execute(
                """
                INSERT INTO artifacts (
                  workspace_id, memo_uid, resource_uid, kind, content_markdown,
                  metadata_json, created_at
                )
                VALUES (?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(workspace_id, memo_uid, resource_uid, kind) DO UPDATE SET
                  content_markdown = excluded.content_markdown,
                  metadata_json = excluded.metadata_json
                """,
                (
                    workspace_id,
                    memo_uid,
                    resource_uid,
                    kind,
                    content_markdown,
                    metadata_json,
                    now,
                ),
            )
            row = connection.execute(
                """
                SELECT * FROM artifacts
                WHERE workspace_id = ? AND memo_uid = ? AND resource_uid IS ?
                  AND kind = ?
                """,
                (workspace_id, memo_uid, resource_uid, kind),
            ).fetchone()
        if row is None:
            raise RuntimeError("Artifact upsert did not return a row")
        return _artifact_from_row(row)

    def list_artifacts(
        self,
        *,
        workspace_id: str,
        memo_uid: str | None = None,
        kind: str | None = None,
        limit: int = 100,
    ) -> list[ArtifactRecord]:
        conditions = ["workspace_id = ?"]
        params: list[Any] = [workspace_id]
        if memo_uid is not None:
            conditions.append("memo_uid = ?")
            params.append(memo_uid)
        if kind is not None:
            conditions.append("kind = ?")
            params.append(kind)
        params.append(limit)
        with self.connect() as connection:
            rows = connection.execute(
                f"""
                SELECT * FROM artifacts
                WHERE {" AND ".join(conditions)}
                ORDER BY created_at DESC, id DESC
                LIMIT ?
                """,
                params,
            ).fetchall()
        return [_artifact_from_row(row) for row in rows]


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


def _memo_from_row(row: sqlite3.Row) -> MemoRecord:
    return MemoRecord(
        id=int(row["id"]),
        workspace_id=str(row["workspace_id"]),
        memos_uid=str(row["memos_uid"]),
        type=str(row["type"]),
        source_memo_uid=row["source_memo_uid"],
        content_hash=row["content_hash"],
        status=str(row["status"]),
        created_at=str(row["created_at"]),
        updated_at=str(row["updated_at"]),
    )


def _tag_candidate_from_row(row: sqlite3.Row) -> TagCandidateRecord:
    return TagCandidateRecord(
        id=int(row["id"]),
        workspace_id=str(row["workspace_id"]),
        path=str(row["path"]),
        parent_path=row["parent_path"],
        status=str(row["status"]),
        reason=str(row["reason"]),
        source_memo_uid=row["source_memo_uid"],
        similar_tags=json.loads(row["similar_tags_json"]),
        confidence=float(row["confidence"]),
        reviewer_note=row["reviewer_note"],
        created_at=str(row["created_at"]),
        updated_at=str(row["updated_at"]),
    )


def _business_tag_from_row(row: sqlite3.Row) -> BusinessTagRecord:
    return BusinessTagRecord(
        id=int(row["id"]),
        workspace_id=str(row["workspace_id"]),
        path=str(row["path"]),
        status=str(row["status"]),
        source=str(row["source"]),
        created_at=str(row["created_at"]),
        updated_at=str(row["updated_at"]),
    )


def _artifact_from_row(row: sqlite3.Row) -> ArtifactRecord:
    return ArtifactRecord(
        id=int(row["id"]),
        workspace_id=str(row["workspace_id"]),
        memo_uid=str(row["memo_uid"]),
        resource_uid=row["resource_uid"],
        kind=str(row["kind"]),
        content_markdown=str(row["content_markdown"]),
        metadata=json.loads(row["metadata_json"]),
        created_at=str(row["created_at"]),
    )
