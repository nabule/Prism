from __future__ import annotations

import hashlib
import json
import secrets
import sqlite3
from contextlib import contextmanager
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Iterator


def utc_now() -> str:
    return datetime.now(UTC).isoformat(timespec="seconds")


def _hash_token(token: str) -> str:
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


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


@dataclass(frozen=True)
class ReminderRecord:
    id: int
    workspace_id: str
    source_memo_uid: str
    title: str
    body: str
    due_at: str
    timezone: str
    status: str
    confidence: float
    raw_text: str
    sent_at: str | None
    error: str | None
    created_at: str
    updated_at: str


@dataclass(frozen=True)
class VectorUnitRecord:
    id: int
    workspace_id: str
    memo_uid: str
    chunk_text: str
    embedding: list[float]
    created_at: str


@dataclass(frozen=True)
class SystemLogRecord:
    id: int
    workspace_id: str
    timestamp: str
    level: str
    component: str
    message: str


# === Team knowledge base ===


TEAM_ROLES: tuple[str, ...] = ("owner", "editor", "viewer")
_TEAM_ROLE_RANK: dict[str, int] = {role: index for index, role in enumerate(TEAM_ROLES)}


def team_role_at_least(role: str, required: str) -> bool:
    """Return True when the actor's role is at least as privileged as the required one."""
    if role not in _TEAM_ROLE_RANK or required not in _TEAM_ROLE_RANK:
        return False
    return _TEAM_ROLE_RANK[role] <= _TEAM_ROLE_RANK[required]


@dataclass(frozen=True)
class TeamRecord:
    id: int
    workspace_id: str
    slug: str
    name: str
    description: str
    created_at: str
    updated_at: str


@dataclass(frozen=True)
class TeamMemberRecord:
    id: int
    team_id: int
    display_name: str
    role: str
    token_hash: str
    created_at: str
    updated_at: str
    last_active_at: str | None


@dataclass(frozen=True)
class TeamInviteRecord:
    id: int
    team_id: int
    code: str
    role: str
    max_uses: int
    uses: int
    expires_at: str | None
    created_at: str
    revoked_at: str | None


@dataclass(frozen=True)
class TeamEntryRecord:
    id: int
    team_id: int
    uid: str
    title: str
    body: str
    tags: list[str]
    author_member_id: int | None
    author_display_name: str | None
    created_at: str
    updated_at: str


@dataclass(frozen=True)
class TeamEntryVectorRecord:
    id: int
    team_id: int
    entry_uid: str
    chunk_text: str
    embedding: list[float]
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

                CREATE TABLE IF NOT EXISTS reminders (
                  id INTEGER PRIMARY KEY AUTOINCREMENT,
                  workspace_id TEXT NOT NULL,
                  source_memo_uid TEXT NOT NULL,
                  title TEXT NOT NULL,
                  body TEXT NOT NULL,
                  due_at TEXT NOT NULL,
                  timezone TEXT NOT NULL,
                  status TEXT NOT NULL,
                  confidence REAL NOT NULL,
                  raw_text TEXT NOT NULL,
                  sent_at TEXT,
                  error TEXT,
                  created_at TEXT NOT NULL,
                  updated_at TEXT NOT NULL,
                  UNIQUE (workspace_id, source_memo_uid, due_at, title),
                  FOREIGN KEY (workspace_id) REFERENCES workspaces(id)
                );

                CREATE INDEX IF NOT EXISTS idx_reminders_status_due
                  ON reminders(status, due_at);

                CREATE TABLE IF NOT EXISTS vector_units (
                  id INTEGER PRIMARY KEY AUTOINCREMENT,
                  workspace_id TEXT NOT NULL,
                  memo_uid TEXT NOT NULL,
                  chunk_text TEXT NOT NULL,
                  embedding_json TEXT NOT NULL,
                  created_at TEXT NOT NULL,
                  FOREIGN KEY (workspace_id) REFERENCES workspaces(id)
                );

                CREATE INDEX IF NOT EXISTS idx_vector_units_memo_uid
                  ON vector_units(workspace_id, memo_uid);

                CREATE TABLE IF NOT EXISTS system_logs (
                  id INTEGER PRIMARY KEY AUTOINCREMENT,
                  workspace_id TEXT NOT NULL,
                  timestamp TEXT NOT NULL,
                  level TEXT NOT NULL,
                  component TEXT NOT NULL,
                  message TEXT NOT NULL,
                  FOREIGN KEY (workspace_id) REFERENCES workspaces(id)
                );

                CREATE INDEX IF NOT EXISTS idx_system_logs_timestamp
                  ON system_logs(timestamp);

                CREATE TABLE IF NOT EXISTS teams (
                  id INTEGER PRIMARY KEY AUTOINCREMENT,
                  workspace_id TEXT NOT NULL,
                  slug TEXT NOT NULL,
                  name TEXT NOT NULL,
                  description TEXT NOT NULL DEFAULT '',
                  created_at TEXT NOT NULL,
                  updated_at TEXT NOT NULL,
                  UNIQUE (workspace_id, slug),
                  FOREIGN KEY (workspace_id) REFERENCES workspaces(id)
                );

                CREATE INDEX IF NOT EXISTS idx_teams_workspace
                  ON teams(workspace_id, slug);

                CREATE TABLE IF NOT EXISTS team_members (
                  id INTEGER PRIMARY KEY AUTOINCREMENT,
                  team_id INTEGER NOT NULL,
                  display_name TEXT NOT NULL,
                  role TEXT NOT NULL,
                  token_hash TEXT NOT NULL,
                  created_at TEXT NOT NULL,
                  updated_at TEXT NOT NULL,
                  last_active_at TEXT,
                  UNIQUE (team_id, display_name),
                  UNIQUE (token_hash),
                  FOREIGN KEY (team_id) REFERENCES teams(id) ON DELETE CASCADE
                );

                CREATE INDEX IF NOT EXISTS idx_team_members_team
                  ON team_members(team_id);

                CREATE TABLE IF NOT EXISTS team_invites (
                  id INTEGER PRIMARY KEY AUTOINCREMENT,
                  team_id INTEGER NOT NULL,
                  code TEXT NOT NULL,
                  role TEXT NOT NULL,
                  max_uses INTEGER NOT NULL DEFAULT 0,
                  uses INTEGER NOT NULL DEFAULT 0,
                  expires_at TEXT,
                  created_at TEXT NOT NULL,
                  revoked_at TEXT,
                  UNIQUE (code),
                  FOREIGN KEY (team_id) REFERENCES teams(id) ON DELETE CASCADE
                );

                CREATE INDEX IF NOT EXISTS idx_team_invites_team
                  ON team_invites(team_id);

                CREATE TABLE IF NOT EXISTS team_entries (
                  id INTEGER PRIMARY KEY AUTOINCREMENT,
                  team_id INTEGER NOT NULL,
                  uid TEXT NOT NULL,
                  title TEXT NOT NULL,
                  body TEXT NOT NULL,
                  tags_json TEXT NOT NULL DEFAULT '[]',
                  author_member_id INTEGER,
                  author_display_name TEXT,
                  created_at TEXT NOT NULL,
                  updated_at TEXT NOT NULL,
                  UNIQUE (team_id, uid),
                  FOREIGN KEY (team_id) REFERENCES teams(id) ON DELETE CASCADE,
                  FOREIGN KEY (author_member_id) REFERENCES team_members(id) ON DELETE SET NULL
                );

                CREATE INDEX IF NOT EXISTS idx_team_entries_team_updated
                  ON team_entries(team_id, updated_at);

                CREATE TABLE IF NOT EXISTS team_entry_vectors (
                  id INTEGER PRIMARY KEY AUTOINCREMENT,
                  team_id INTEGER NOT NULL,
                  entry_uid TEXT NOT NULL,
                  chunk_text TEXT NOT NULL,
                  embedding_json TEXT NOT NULL,
                  created_at TEXT NOT NULL,
                  FOREIGN KEY (team_id) REFERENCES teams(id) ON DELETE CASCADE
                );

                CREATE INDEX IF NOT EXISTS idx_team_entry_vectors_lookup
                  ON team_entry_vectors(team_id, entry_uid);
                """
            )

    def reset(self) -> None:
        with self.connect() as connection:
            connection.execute("PRAGMA foreign_keys = OFF")
            rows = connection.execute("SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%'").fetchall()
            for row in rows:
                connection.execute(f"DROP TABLE IF EXISTS {row['name']}")
            connection.execute("PRAGMA foreign_keys = ON")
        self.migrate()

    def insert_system_log(
        self,
        workspace_id: str,
        level: str,
        component: str,
        message: str,
    ) -> None:
        try:
            with self.connect() as connection:
                connection.execute(
                    """
                    INSERT INTO system_logs (workspace_id, timestamp, level, component, message)
                    VALUES (?, ?, ?, ?, ?)
                    """,
                    (workspace_id, utc_now(), level, component, message),
                )
                # Keep database bounded by pruning to last 5000 logs
                connection.execute(
                    """
                    DELETE FROM system_logs 
                    WHERE id NOT IN (
                        SELECT id FROM system_logs 
                        ORDER BY id DESC LIMIT 5000
                    )
                    """
                )
        except Exception:
            # Prevent logging database issues from crashing application components
            pass

    def get_system_logs(
        self,
        workspace_id: str,
        level: str | None = None,
        component: str | None = None,
        query: str | None = None,
        limit: int = 100,
        offset: int = 0,
    ) -> tuple[list[SystemLogRecord], int]:
        where_clauses = ["workspace_id = ?"]
        params: list[Any] = [workspace_id]

        if level:
            where_clauses.append("level = ?")
            params.append(level)

        if component:
            where_clauses.append("component = ?")
            params.append(component)

        if query:
            where_clauses.append("message LIKE ?")
            params.append(f"%{query}%")

        where_str = " AND ".join(where_clauses)

        with self.connect() as connection:
            count_cursor = connection.execute(
                f"SELECT COUNT(*) FROM system_logs WHERE {where_str}",
                tuple(params),
            )
            total_count = count_cursor.fetchone()[0]

            log_cursor = connection.execute(
                f"""
                SELECT id, workspace_id, timestamp, level, component, message
                FROM system_logs
                WHERE {where_str}
                ORDER BY id DESC
                LIMIT ? OFFSET ?
                """,
                tuple(params + [limit, offset]),
            )
            records = [
                SystemLogRecord(
                    id=row["id"],
                    workspace_id=row["workspace_id"],
                    timestamp=row["timestamp"],
                    level=row["level"],
                    component=row["component"],
                    message=row["message"],
                )
                for row in log_cursor
            ]
            return records, total_count

    def clear_system_logs(self, workspace_id: str) -> None:
        with self.connect() as connection:
            connection.execute("DELETE FROM system_logs WHERE workspace_id = ?", (workspace_id,))

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

    def has_job(self, *, workspace_id: str, idempotency_key: str) -> bool:
        with self.connect() as connection:
            row = connection.execute(
                """
                SELECT 1 FROM jobs
                WHERE workspace_id = ? AND idempotency_key = ?
                LIMIT 1
                """,
                (workspace_id, idempotency_key),
            ).fetchone()
        return row is not None

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
        return self.retry_job_with_payload(job_id)

    def retry_job_with_payload(self, job_id: int, payload_patch: dict[str, Any] | None = None) -> Job | None:
        now = utc_now()
        with self.connect() as connection:
            row = connection.execute("SELECT payload_json FROM jobs WHERE id = ?", (job_id,)).fetchone()
            payload_json: str | None = None
            if row is not None and payload_patch:
                payload = json.loads(row["payload_json"])
                payload.update(payload_patch)
                payload_json = json.dumps(payload, ensure_ascii=False, sort_keys=True)
            connection.execute(
                _retry_job_sql(payload_json is not None),
                (now, payload_json, job_id) if payload_json is not None else (now, job_id),
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

    def has_memo(
        self,
        *,
        workspace_id: str,
        memos_uid: str,
        memo_type: str | None = None,
    ) -> bool:
        conditions = ["workspace_id = ?", "memos_uid = ?"]
        params: list[Any] = [workspace_id, memos_uid]
        if memo_type is not None:
            conditions.append("type = ?")
            params.append(memo_type)
        with self.connect() as connection:
            row = connection.execute(
                f"""
                SELECT 1 FROM memos
                WHERE {" AND ".join(conditions)}
                LIMIT 1
                """,
                params,
            ).fetchone()
        return row is not None

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
            leaf = _tag_leaf(path)
            active_conflict = connection.execute(
                """
                SELECT * FROM business_tags
                WHERE workspace_id = ? AND status = 'active'
                ORDER BY path ASC
                """,
                (workspace_id,),
            ).fetchall()
            for row in active_conflict:
                if row["path"] != path and _tag_leaf(row["path"]) == leaf:
                    raise ValueError(f"Tag leaf conflicts with active tag: {row['path']}")

            candidate_conflict = connection.execute(
                """
                SELECT * FROM tag_candidates
                WHERE workspace_id = ? AND status = 'candidate'
                ORDER BY created_at ASC, id ASC
                """,
                (workspace_id,),
            ).fetchall()
            for row in candidate_conflict:
                if row["path"] != path and _tag_leaf(row["path"]) == leaf:
                    return _tag_candidate_from_row(row)

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
        path: str | None = None,
    ) -> TagCandidateRecord | None:
        if status not in {"approved", "rejected"}:
            raise ValueError(f"Unsupported tag candidate review status: {status}")
        now = utc_now()
        with self.connect() as connection:
            if path is not None:
                parent_path = path.rsplit("/", maxsplit=1)[0] if "/" in path else None
                connection.execute(
                    """
                    UPDATE tag_candidates
                    SET status = ?, reviewer_note = ?, path = ?, parent_path = ?, updated_at = ?
                    WHERE id = ? AND status = 'candidate'
                    """,
                    (status, reviewer_note, path, parent_path, now, candidate_id),
                )
            else:
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
                active_conflict = connection.execute(
                    """
                    SELECT path FROM business_tags
                    WHERE workspace_id = ? AND status = 'active'
                    ORDER BY path ASC
                    """,
                    (row["workspace_id"],),
                ).fetchall()
                for active_row in active_conflict:
                    if active_row["path"] != row["path"] and _tag_leaf(active_row["path"]) == _tag_leaf(row["path"]):
                        raise ValueError(f"Tag leaf conflicts with active tag: {active_row['path']}")
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

    def create_reminder(
        self,
        *,
        workspace_id: str,
        source_memo_uid: str,
        title: str,
        body: str,
        due_at: str,
        timezone: str,
        confidence: float,
        raw_text: str,
    ) -> tuple[ReminderRecord, bool]:
        now = utc_now()
        with self.connect() as connection:
            cursor = connection.execute(
                """
                INSERT OR IGNORE INTO reminders (
                  workspace_id, source_memo_uid, title, body, due_at, timezone,
                  status, confidence, raw_text, created_at, updated_at
                )
                VALUES (?, ?, ?, ?, ?, ?, 'pending', ?, ?, ?, ?)
                """,
                (
                    workspace_id,
                    source_memo_uid,
                    title,
                    body,
                    due_at,
                    timezone,
                    confidence,
                    raw_text,
                    now,
                    now,
                ),
            )
            created = cursor.rowcount == 1
            row = connection.execute(
                """
                SELECT * FROM reminders
                WHERE workspace_id = ? AND source_memo_uid = ? AND due_at = ? AND title = ?
                """,
                (workspace_id, source_memo_uid, due_at, title),
            ).fetchone()
        if row is None:
            raise RuntimeError("Reminder insert did not return a row")
        return _reminder_from_row(row), created

    def list_reminders(
        self,
        *,
        workspace_id: str,
        status: str | None = None,
        limit: int = 100,
    ) -> list[ReminderRecord]:
        with self.connect() as connection:
            if status:
                rows = connection.execute(
                    """
                    SELECT * FROM reminders
                    WHERE workspace_id = ? AND status = ?
                    ORDER BY due_at ASC, id ASC
                    LIMIT ?
                    """,
                    (workspace_id, status, limit),
                ).fetchall()
            else:
                rows = connection.execute(
                    """
                    SELECT * FROM reminders
                    WHERE workspace_id = ?
                    ORDER BY due_at ASC, id ASC
                    LIMIT ?
                    """,
                    (workspace_id, limit),
                ).fetchall()
        return [_reminder_from_row(row) for row in rows]

    def list_due_reminders(
        self,
        *,
        workspace_id: str,
        now: str,
        limit: int = 50,
    ) -> list[ReminderRecord]:
        with self.connect() as connection:
            rows = connection.execute(
                """
                SELECT * FROM reminders
                WHERE workspace_id = ? AND status IN ('pending', 'failed') AND due_at <= ?
                ORDER BY due_at ASC, id ASC
                LIMIT ?
                """,
                (workspace_id, now, limit),
            ).fetchall()
        return [_reminder_from_row(row) for row in rows]

    def get_reminder(self, reminder_id: int) -> ReminderRecord | None:
        with self.connect() as connection:
            row = connection.execute("SELECT * FROM reminders WHERE id = ?", (reminder_id,)).fetchone()
        return _reminder_from_row(row) if row else None

    def mark_reminder_sent(self, reminder_id: int) -> ReminderRecord | None:
        now = utc_now()
        with self.connect() as connection:
            connection.execute(
                """
                UPDATE reminders
                SET status = 'sent', sent_at = ?, error = NULL, updated_at = ?
                WHERE id = ? AND status IN ('pending', 'failed')
                """,
                (now, now, reminder_id),
            )
            row = connection.execute("SELECT * FROM reminders WHERE id = ?", (reminder_id,)).fetchone()
        return _reminder_from_row(row) if row else None

    def mark_reminder_failed(self, reminder_id: int, error: str) -> ReminderRecord | None:
        now = utc_now()
        with self.connect() as connection:
            connection.execute(
                """
                UPDATE reminders
                SET status = 'failed', error = ?, updated_at = ?
                WHERE id = ? AND status IN ('pending', 'failed')
                """,
                (error, now, reminder_id),
            )
            row = connection.execute("SELECT * FROM reminders WHERE id = ?", (reminder_id,)).fetchone()
        return _reminder_from_row(row) if row else None

    def retry_reminder(self, reminder_id: int) -> ReminderRecord | None:
        now = utc_now()
        with self.connect() as connection:
            connection.execute(
                """
                UPDATE reminders
                SET status = 'pending', error = NULL, updated_at = ?
                WHERE id = ? AND status IN ('failed', 'sent')
                """,
                (now, reminder_id),
            )
            row = connection.execute("SELECT * FROM reminders WHERE id = ?", (reminder_id,)).fetchone()
        return _reminder_from_row(row) if row else None

    def cancel_reminder(self, reminder_id: int) -> ReminderRecord | None:
        now = utc_now()
        with self.connect() as connection:
            connection.execute(
                """
                UPDATE reminders
                SET status = 'cancelled', error = NULL, updated_at = ?
                WHERE id = ? AND status IN ('pending', 'failed')
                """,
                (now, reminder_id),
            )
            row = connection.execute("SELECT * FROM reminders WHERE id = ?", (reminder_id,)).fetchone()
        return _reminder_from_row(row) if row else None

    def replace_vector_units(
        self,
        *,
        workspace_id: str,
        memo_uid: str,
        chunks: list[tuple[str, list[float]]],
    ) -> None:
        now = utc_now()
        with self.connect() as connection:
            connection.execute(
                "DELETE FROM vector_units WHERE workspace_id = ? AND memo_uid = ?",
                (workspace_id, memo_uid),
            )
            if not chunks:
                return
            connection.executemany(
                """
                INSERT INTO vector_units (
                  workspace_id, memo_uid, chunk_text, embedding_json, created_at
                ) VALUES (?, ?, ?, ?, ?)
                """,
                [
                    (workspace_id, memo_uid, text, json.dumps(embedding), now)
                    for text, embedding in chunks
                ],
            )

    def list_all_vector_units(self, workspace_id: str) -> list[VectorUnitRecord]:
        with self.connect() as connection:
            rows = connection.execute(
                "SELECT * FROM vector_units WHERE workspace_id = ?",
                (workspace_id,),
            ).fetchall()
        return [_vector_unit_from_row(row) for row in rows]

    def search_similar_chunks(
        self,
        *,
        workspace_id: str,
        query_embedding: list[float],
        limit: int = 15,
    ) -> list[tuple[VectorUnitRecord, float]]:
        import math
        
        all_units = self.list_all_vector_units(workspace_id)
        if not all_units:
            return []
            
        def cos_sim(v1: list[float], v2: list[float]) -> float:
            if len(v1) != len(v2):
                return 0.0
            dot = sum(a * b for a, b in zip(v1, v2))
            norm1 = math.sqrt(sum(a * a for a in v1))
            norm2 = math.sqrt(sum(b * b for b in v2))
            if norm1 == 0 or norm2 == 0:
                return 0.0
            return dot / (norm1 * norm2)
            
        scored_units = []
        for unit in all_units:
            score = cos_sim(query_embedding, unit.embedding)
            scored_units.append((unit, score))
            
        scored_units.sort(key=lambda x: x[1], reverse=True)
        return scored_units[:limit]

    # === Team knowledge base ===

    def create_team(
        self,
        *,
        workspace_id: str,
        slug: str,
        name: str,
        description: str = "",
    ) -> TeamRecord:
        slug_clean = slug.strip()
        if not slug_clean:
            raise ValueError("Team slug cannot be empty")
        now = utc_now()
        with self.connect() as connection:
            try:
                cursor = connection.execute(
                    """
                    INSERT INTO teams (workspace_id, slug, name, description, created_at, updated_at)
                    VALUES (?, ?, ?, ?, ?, ?)
                    """,
                    (workspace_id, slug_clean, name.strip() or slug_clean, description.strip(), now, now),
                )
            except sqlite3.IntegrityError as exc:
                raise ValueError(f"Team slug already exists in workspace: {slug_clean}") from exc
            team_id = int(cursor.lastrowid or 0)
            row = connection.execute("SELECT * FROM teams WHERE id = ?", (team_id,)).fetchone()
        if row is None:
            raise RuntimeError("Team insert did not return a row")
        return _team_from_row(row)

    def update_team(
        self,
        *,
        team_id: int,
        name: str | None = None,
        description: str | None = None,
    ) -> TeamRecord | None:
        if name is None and description is None:
            return self.get_team_by_id(team_id)
        now = utc_now()
        fields: list[str] = []
        params: list[Any] = []
        if name is not None:
            fields.append("name = ?")
            params.append(name.strip() or "")
        if description is not None:
            fields.append("description = ?")
            params.append(description.strip())
        fields.append("updated_at = ?")
        params.append(now)
        params.append(team_id)
        with self.connect() as connection:
            connection.execute(
                f"UPDATE teams SET {', '.join(fields)} WHERE id = ?",
                tuple(params),
            )
            row = connection.execute("SELECT * FROM teams WHERE id = ?", (team_id,)).fetchone()
        return _team_from_row(row) if row else None

    def delete_team(self, *, team_id: int) -> bool:
        with self.connect() as connection:
            connection.execute(
                "DELETE FROM team_entry_vectors WHERE team_id = ?", (team_id,),
            )
            connection.execute(
                "DELETE FROM team_entries WHERE team_id = ?", (team_id,),
            )
            connection.execute(
                "DELETE FROM team_invites WHERE team_id = ?", (team_id,),
            )
            connection.execute(
                "DELETE FROM team_members WHERE team_id = ?", (team_id,),
            )
            cursor = connection.execute("DELETE FROM teams WHERE id = ?", (team_id,))
            return cursor.rowcount > 0

    def list_teams(self, *, workspace_id: str, limit: int = 200) -> list[TeamRecord]:
        with self.connect() as connection:
            rows = connection.execute(
                """
                SELECT * FROM teams
                WHERE workspace_id = ?
                ORDER BY created_at ASC, id ASC
                LIMIT ?
                """,
                (workspace_id, limit),
            ).fetchall()
        return [_team_from_row(row) for row in rows]

    def get_team_by_slug(self, *, workspace_id: str, slug: str) -> TeamRecord | None:
        with self.connect() as connection:
            row = connection.execute(
                "SELECT * FROM teams WHERE workspace_id = ? AND slug = ?",
                (workspace_id, slug),
            ).fetchone()
        return _team_from_row(row) if row else None

    def get_team_by_id(self, team_id: int) -> TeamRecord | None:
        with self.connect() as connection:
            row = connection.execute("SELECT * FROM teams WHERE id = ?", (team_id,)).fetchone()
        return _team_from_row(row) if row else None

    def count_team_owners(self, *, team_id: int) -> int:
        with self.connect() as connection:
            row = connection.execute(
                "SELECT COUNT(*) AS n FROM team_members WHERE team_id = ? AND role = 'owner'",
                (team_id,),
            ).fetchone()
        return int(row["n"]) if row else 0

    def add_team_member(
        self,
        *,
        team_id: int,
        display_name: str,
        role: str,
        token: str | None = None,
    ) -> tuple[TeamMemberRecord, str]:
        if role not in _TEAM_ROLE_RANK:
            raise ValueError(f"Unsupported team role: {role}")
        display_name_clean = display_name.strip()
        if not display_name_clean:
            raise ValueError("Member display name cannot be empty")
        raw_token = token or f"team_{secrets.token_urlsafe(24)}"
        token_hash = _hash_token(raw_token)
        now = utc_now()
        with self.connect() as connection:
            try:
                cursor = connection.execute(
                    """
                    INSERT INTO team_members (
                      team_id, display_name, role, token_hash, created_at, updated_at
                    )
                    VALUES (?, ?, ?, ?, ?, ?)
                    """,
                    (team_id, display_name_clean, role, token_hash, now, now),
                )
            except sqlite3.IntegrityError as exc:
                raise ValueError(
                    f"Member already exists in team: {display_name_clean}"
                ) from exc
            member_id = int(cursor.lastrowid or 0)
            row = connection.execute(
                "SELECT * FROM team_members WHERE id = ?", (member_id,),
            ).fetchone()
        if row is None:
            raise RuntimeError("Team member insert did not return a row")
        return _team_member_from_row(row), raw_token

    def list_team_members(self, *, team_id: int) -> list[TeamMemberRecord]:
        with self.connect() as connection:
            rows = connection.execute(
                """
                SELECT * FROM team_members
                WHERE team_id = ?
                ORDER BY created_at ASC, id ASC
                """,
                (team_id,),
            ).fetchall()
        return [_team_member_from_row(row) for row in rows]

    def get_team_member(self, *, member_id: int) -> TeamMemberRecord | None:
        with self.connect() as connection:
            row = connection.execute(
                "SELECT * FROM team_members WHERE id = ?", (member_id,),
            ).fetchone()
        return _team_member_from_row(row) if row else None

    def update_team_member_role(
        self,
        *,
        member_id: int,
        role: str,
    ) -> TeamMemberRecord | None:
        if role not in _TEAM_ROLE_RANK:
            raise ValueError(f"Unsupported team role: {role}")
        now = utc_now()
        with self.connect() as connection:
            connection.execute(
                "UPDATE team_members SET role = ?, updated_at = ? WHERE id = ?",
                (role, now, member_id),
            )
            row = connection.execute(
                "SELECT * FROM team_members WHERE id = ?", (member_id,),
            ).fetchone()
        return _team_member_from_row(row) if row else None

    def delete_team_member(self, *, member_id: int) -> bool:
        with self.connect() as connection:
            cursor = connection.execute(
                "DELETE FROM team_members WHERE id = ?", (member_id,),
            )
            return cursor.rowcount > 0

    def find_team_member_by_token(
        self, token: str,
    ) -> tuple[TeamMemberRecord, TeamRecord] | None:
        if not token:
            return None
        token_hash = _hash_token(token)
        now = utc_now()
        with self.connect() as connection:
            row = connection.execute(
                """
                SELECT m.*, t.workspace_id AS team_workspace_id, t.slug AS team_slug,
                       t.name AS team_name, t.description AS team_description,
                       t.created_at AS team_created_at, t.updated_at AS team_updated_at
                FROM team_members AS m
                JOIN teams AS t ON t.id = m.team_id
                WHERE m.token_hash = ?
                """,
                (token_hash,),
            ).fetchone()
            if row is None:
                return None
            connection.execute(
                "UPDATE team_members SET last_active_at = ? WHERE id = ?",
                (now, int(row["id"])),
            )
        member = TeamMemberRecord(
            id=int(row["id"]),
            team_id=int(row["team_id"]),
            display_name=str(row["display_name"]),
            role=str(row["role"]),
            token_hash=str(row["token_hash"]),
            created_at=str(row["created_at"]),
            updated_at=str(row["updated_at"]),
            last_active_at=now,
        )
        team = TeamRecord(
            id=int(row["team_id"]),
            workspace_id=str(row["team_workspace_id"]),
            slug=str(row["team_slug"]),
            name=str(row["team_name"]),
            description=str(row["team_description"]),
            created_at=str(row["team_created_at"]),
            updated_at=str(row["team_updated_at"]),
        )
        return member, team

    def create_team_invite(
        self,
        *,
        team_id: int,
        role: str = "editor",
        max_uses: int = 0,
        expires_at: str | None = None,
        code: str | None = None,
    ) -> TeamInviteRecord:
        if role not in _TEAM_ROLE_RANK:
            raise ValueError(f"Unsupported team role: {role}")
        if max_uses < 0:
            raise ValueError("max_uses cannot be negative")
        code_value = code or secrets.token_urlsafe(8)
        now = utc_now()
        with self.connect() as connection:
            try:
                cursor = connection.execute(
                    """
                    INSERT INTO team_invites (
                      team_id, code, role, max_uses, uses, expires_at, created_at
                    )
                    VALUES (?, ?, ?, ?, 0, ?, ?)
                    """,
                    (team_id, code_value, role, max_uses, expires_at, now),
                )
            except sqlite3.IntegrityError as exc:
                raise ValueError("Invite code collision; please retry") from exc
            invite_id = int(cursor.lastrowid or 0)
            row = connection.execute(
                "SELECT * FROM team_invites WHERE id = ?", (invite_id,),
            ).fetchone()
        if row is None:
            raise RuntimeError("Team invite insert did not return a row")
        return _team_invite_from_row(row)

    def list_team_invites(self, *, team_id: int) -> list[TeamInviteRecord]:
        with self.connect() as connection:
            rows = connection.execute(
                """
                SELECT * FROM team_invites
                WHERE team_id = ?
                ORDER BY created_at DESC, id DESC
                """,
                (team_id,),
            ).fetchall()
        return [_team_invite_from_row(row) for row in rows]

    def revoke_team_invite(self, *, invite_id: int) -> TeamInviteRecord | None:
        now = utc_now()
        with self.connect() as connection:
            connection.execute(
                "UPDATE team_invites SET revoked_at = ? WHERE id = ? AND revoked_at IS NULL",
                (now, invite_id),
            )
            row = connection.execute(
                "SELECT * FROM team_invites WHERE id = ?", (invite_id,),
            ).fetchone()
        return _team_invite_from_row(row) if row else None

    def redeem_team_invite(
        self,
        *,
        code: str,
        display_name: str,
    ) -> tuple[TeamRecord, TeamMemberRecord, str]:
        if not code:
            raise ValueError("Invite code is required")
        display_name_clean = display_name.strip()
        if not display_name_clean:
            raise ValueError("Display name is required")
        now = utc_now()
        with self.connect() as connection:
            invite_row = connection.execute(
                "SELECT * FROM team_invites WHERE code = ?", (code,),
            ).fetchone()
            if invite_row is None:
                raise ValueError("Invite code not found")
            if invite_row["revoked_at"]:
                raise ValueError("Invite code has been revoked")
            expires_at = invite_row["expires_at"]
            if expires_at and str(expires_at) <= now:
                raise ValueError("Invite code has expired")
            max_uses = int(invite_row["max_uses"])
            uses = int(invite_row["uses"])
            if max_uses > 0 and uses >= max_uses:
                raise ValueError("Invite code has reached its maximum uses")
            team_row = connection.execute(
                "SELECT * FROM teams WHERE id = ?", (invite_row["team_id"],),
            ).fetchone()
            if team_row is None:
                raise ValueError("Team for invite no longer exists")
            existing = connection.execute(
                "SELECT id FROM team_members WHERE team_id = ? AND display_name = ?",
                (team_row["id"], display_name_clean),
            ).fetchone()
            if existing is not None:
                raise ValueError(
                    f"Member already exists in team: {display_name_clean}"
                )
            raw_token = f"team_{secrets.token_urlsafe(24)}"
            token_hash = _hash_token(raw_token)
            cursor = connection.execute(
                """
                INSERT INTO team_members (
                  team_id, display_name, role, token_hash, created_at, updated_at
                )
                VALUES (?, ?, ?, ?, ?, ?)
                """,
                (
                    team_row["id"],
                    display_name_clean,
                    str(invite_row["role"]),
                    token_hash,
                    now,
                    now,
                ),
            )
            member_id = int(cursor.lastrowid or 0)
            connection.execute(
                "UPDATE team_invites SET uses = uses + 1 WHERE id = ?",
                (invite_row["id"],),
            )
            member_row = connection.execute(
                "SELECT * FROM team_members WHERE id = ?", (member_id,),
            ).fetchone()
        if member_row is None:
            raise RuntimeError("Team member insert did not return a row")
        return _team_from_row(team_row), _team_member_from_row(member_row), raw_token

    def create_team_entry(
        self,
        *,
        team_id: int,
        title: str,
        body: str,
        tags: list[str] | None = None,
        author_member_id: int | None = None,
        author_display_name: str | None = None,
        uid: str | None = None,
    ) -> TeamEntryRecord:
        title_clean = title.strip()
        body_clean = body.rstrip()
        if not title_clean and not body_clean:
            raise ValueError("Entry must include title or body")
        if not title_clean:
            title_clean = body_clean.splitlines()[0][:80] if body_clean else "未命名条目"
        clean_tags = _clean_tag_list(tags or [])
        uid_value = uid or f"e_{secrets.token_urlsafe(8)}"
        now = utc_now()
        with self.connect() as connection:
            try:
                cursor = connection.execute(
                    """
                    INSERT INTO team_entries (
                      team_id, uid, title, body, tags_json,
                      author_member_id, author_display_name,
                      created_at, updated_at
                    )
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        team_id,
                        uid_value,
                        title_clean,
                        body_clean,
                        json.dumps(clean_tags, ensure_ascii=False),
                        author_member_id,
                        author_display_name,
                        now,
                        now,
                    ),
                )
            except sqlite3.IntegrityError as exc:
                raise ValueError("Entry UID collision; please retry") from exc
            row = connection.execute(
                "SELECT * FROM team_entries WHERE id = ?",
                (int(cursor.lastrowid or 0),),
            ).fetchone()
        if row is None:
            raise RuntimeError("Team entry insert did not return a row")
        return _team_entry_from_row(row)

    def update_team_entry(
        self,
        *,
        team_id: int,
        uid: str,
        title: str | None = None,
        body: str | None = None,
        tags: list[str] | None = None,
    ) -> TeamEntryRecord | None:
        if title is None and body is None and tags is None:
            return self.get_team_entry(team_id=team_id, uid=uid)
        fields: list[str] = []
        params: list[Any] = []
        if title is not None:
            fields.append("title = ?")
            params.append(title.strip() or "未命名条目")
        if body is not None:
            fields.append("body = ?")
            params.append(body.rstrip())
        if tags is not None:
            fields.append("tags_json = ?")
            params.append(json.dumps(_clean_tag_list(tags), ensure_ascii=False))
        fields.append("updated_at = ?")
        now = utc_now()
        params.append(now)
        params.extend([team_id, uid])
        with self.connect() as connection:
            connection.execute(
                f"UPDATE team_entries SET {', '.join(fields)} WHERE team_id = ? AND uid = ?",
                tuple(params),
            )
            row = connection.execute(
                "SELECT * FROM team_entries WHERE team_id = ? AND uid = ?",
                (team_id, uid),
            ).fetchone()
        return _team_entry_from_row(row) if row else None

    def delete_team_entry(self, *, team_id: int, uid: str) -> bool:
        with self.connect() as connection:
            connection.execute(
                "DELETE FROM team_entry_vectors WHERE team_id = ? AND entry_uid = ?",
                (team_id, uid),
            )
            cursor = connection.execute(
                "DELETE FROM team_entries WHERE team_id = ? AND uid = ?",
                (team_id, uid),
            )
            return cursor.rowcount > 0

    def get_team_entry(self, *, team_id: int, uid: str) -> TeamEntryRecord | None:
        with self.connect() as connection:
            row = connection.execute(
                "SELECT * FROM team_entries WHERE team_id = ? AND uid = ?",
                (team_id, uid),
            ).fetchone()
        return _team_entry_from_row(row) if row else None

    def list_team_entries(
        self,
        *,
        team_id: int,
        tag: str | None = None,
        query: str | None = None,
        limit: int = 100,
        offset: int = 0,
    ) -> list[TeamEntryRecord]:
        conditions = ["team_id = ?"]
        params: list[Any] = [team_id]
        if tag:
            conditions.append("tags_json LIKE ?")
            params.append(f"%{json.dumps(tag, ensure_ascii=False)}%")
        if query:
            conditions.append("(title LIKE ? OR body LIKE ?)")
            params.extend([f"%{query}%", f"%{query}%"])
        params.extend([limit, offset])
        with self.connect() as connection:
            rows = connection.execute(
                f"""
                SELECT * FROM team_entries
                WHERE {' AND '.join(conditions)}
                ORDER BY updated_at DESC, id DESC
                LIMIT ? OFFSET ?
                """,
                tuple(params),
            ).fetchall()
        return [_team_entry_from_row(row) for row in rows]

    def replace_team_entry_vectors(
        self,
        *,
        team_id: int,
        entry_uid: str,
        chunks: list[tuple[str, list[float]]],
    ) -> None:
        now = utc_now()
        with self.connect() as connection:
            connection.execute(
                "DELETE FROM team_entry_vectors WHERE team_id = ? AND entry_uid = ?",
                (team_id, entry_uid),
            )
            if not chunks:
                return
            connection.executemany(
                """
                INSERT INTO team_entry_vectors (
                  team_id, entry_uid, chunk_text, embedding_json, created_at
                ) VALUES (?, ?, ?, ?, ?)
                """,
                [
                    (team_id, entry_uid, text, json.dumps(embedding), now)
                    for text, embedding in chunks
                ],
            )

    def list_team_entry_vectors(self, *, team_id: int) -> list[TeamEntryVectorRecord]:
        with self.connect() as connection:
            rows = connection.execute(
                "SELECT * FROM team_entry_vectors WHERE team_id = ?",
                (team_id,),
            ).fetchall()
        return [_team_entry_vector_from_row(row) for row in rows]

    def search_team_entries_semantic(
        self,
        *,
        team_id: int,
        query_embedding: list[float],
        limit: int = 10,
    ) -> list[tuple[TeamEntryVectorRecord, float]]:
        import math

        all_units = self.list_team_entry_vectors(team_id=team_id)
        if not all_units:
            return []

        def cos_sim(v1: list[float], v2: list[float]) -> float:
            if len(v1) != len(v2):
                return 0.0
            dot = sum(a * b for a, b in zip(v1, v2))
            norm1 = math.sqrt(sum(a * a for a in v1))
            norm2 = math.sqrt(sum(b * b for b in v2))
            if norm1 == 0 or norm2 == 0:
                return 0.0
            return dot / (norm1 * norm2)

        scored = [(unit, cos_sim(query_embedding, unit.embedding)) for unit in all_units]
        scored.sort(key=lambda x: x[1], reverse=True)
        return scored[:limit]


def _clean_tag_list(values: list[str]) -> list[str]:
    cleaned: list[str] = []
    seen: set[str] = set()
    for value in values:
        if not isinstance(value, str):
            continue
        text = value.strip()
        if not text:
            continue
        # Allow tags with or without leading #; canonicalize without leading # to keep
        # storage uniform; the API layer can render with # when serializing.
        normalized = text.lstrip("#").strip()
        if not normalized or normalized in seen:
            continue
        seen.add(normalized)
        cleaned.append(normalized)
    return cleaned


def _team_from_row(row: sqlite3.Row) -> TeamRecord:
    return TeamRecord(
        id=int(row["id"]),
        workspace_id=str(row["workspace_id"]),
        slug=str(row["slug"]),
        name=str(row["name"]),
        description=str(row["description"] or ""),
        created_at=str(row["created_at"]),
        updated_at=str(row["updated_at"]),
    )


def _team_member_from_row(row: sqlite3.Row) -> TeamMemberRecord:
    return TeamMemberRecord(
        id=int(row["id"]),
        team_id=int(row["team_id"]),
        display_name=str(row["display_name"]),
        role=str(row["role"]),
        token_hash=str(row["token_hash"]),
        created_at=str(row["created_at"]),
        updated_at=str(row["updated_at"]),
        last_active_at=str(row["last_active_at"]) if row["last_active_at"] else None,
    )


def _team_invite_from_row(row: sqlite3.Row) -> TeamInviteRecord:
    return TeamInviteRecord(
        id=int(row["id"]),
        team_id=int(row["team_id"]),
        code=str(row["code"]),
        role=str(row["role"]),
        max_uses=int(row["max_uses"]),
        uses=int(row["uses"]),
        expires_at=str(row["expires_at"]) if row["expires_at"] else None,
        created_at=str(row["created_at"]),
        revoked_at=str(row["revoked_at"]) if row["revoked_at"] else None,
    )


def _team_entry_from_row(row: sqlite3.Row) -> TeamEntryRecord:
    tags_raw = row["tags_json"]
    try:
        tags = json.loads(tags_raw) if tags_raw else []
        if not isinstance(tags, list):
            tags = []
    except (TypeError, ValueError):
        tags = []
    return TeamEntryRecord(
        id=int(row["id"]),
        team_id=int(row["team_id"]),
        uid=str(row["uid"]),
        title=str(row["title"]),
        body=str(row["body"]),
        tags=[str(tag) for tag in tags],
        author_member_id=int(row["author_member_id"]) if row["author_member_id"] is not None else None,
        author_display_name=str(row["author_display_name"]) if row["author_display_name"] else None,
        created_at=str(row["created_at"]),
        updated_at=str(row["updated_at"]),
    )


def _team_entry_vector_from_row(row: sqlite3.Row) -> TeamEntryVectorRecord:
    return TeamEntryVectorRecord(
        id=int(row["id"]),
        team_id=int(row["team_id"]),
        entry_uid=str(row["entry_uid"]),
        chunk_text=str(row["chunk_text"]),
        embedding=json.loads(row["embedding_json"]),
        created_at=str(row["created_at"]),
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


def _retry_job_sql(update_payload: bool) -> str:
    if update_payload:
        return """
                UPDATE jobs
                SET status = 'pending', error = NULL, retry_count = 0,
                    updated_at = ?, payload_json = ?
                WHERE id = ? AND status IN ('failed', 'waiting_user')
                """
    return """
                UPDATE jobs
                SET status = 'pending', error = NULL, retry_count = 0, updated_at = ?
                WHERE id = ? AND status IN ('failed', 'waiting_user')
                """


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


def _reminder_from_row(row: sqlite3.Row) -> ReminderRecord:
    return ReminderRecord(
        id=int(row["id"]),
        workspace_id=str(row["workspace_id"]),
        source_memo_uid=str(row["source_memo_uid"]),
        title=str(row["title"]),
        body=str(row["body"]),
        due_at=str(row["due_at"]),
        timezone=str(row["timezone"]),
        status=str(row["status"]),
        confidence=float(row["confidence"]),
        raw_text=str(row["raw_text"]),
        sent_at=row["sent_at"],
        error=row["error"],
        created_at=str(row["created_at"]),
        updated_at=str(row["updated_at"]),
    )


def _vector_unit_from_row(row: sqlite3.Row) -> VectorUnitRecord:
    return VectorUnitRecord(
        id=int(row["id"]),
        workspace_id=str(row["workspace_id"]),
        memo_uid=str(row["memo_uid"]),
        chunk_text=str(row["chunk_text"]),
        embedding=json.loads(row["embedding_json"]),
        created_at=str(row["created_at"]),
    )


def _tag_leaf(path: str) -> str:
    return path.rsplit("/", maxsplit=1)[-1].removeprefix("#")
