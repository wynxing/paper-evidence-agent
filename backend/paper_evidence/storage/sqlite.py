"""SQLite + FTS5 persistence for tasks, sources, paragraphs and diagnostics.

This module owns every local write. It implements the synchronous
``TaskRepository`` port and the additional read/projection queries used by the
API, worker and diagnosis packages. The worker calls these methods through
``asyncio.to_thread`` so SQLite never runs on the event loop.

Conditional terminal writes follow 架构设计「取消与截止时间」: a claimed task's
result never overwrites a terminal state that committed first.
"""

from __future__ import annotations

import json
import sqlite3
import threading
from datetime import datetime, timezone
from pathlib import Path

from paper_evidence.domain import ContractError, ErrorCode, TaskStatus
from paper_evidence.domain.contracts import (
    Accounting,
    CancelResponse,
    CheckDetail,
    CheckSummary,
    ConflictResponse,
    CriteriaReference,
    EvidenceCandidate,
    ExecutionRecord,
    Limits,
    ModelCall,
    RunConfigSnapshot,
    SourceRecord,
)
from paper_evidence.domain.records import Paragraph, TaskInput
from paper_evidence.domain.rules import terminal_status

TERMINAL_STATUSES = frozenset({
    TaskStatus.COMPLETED,
    TaskStatus.BLOCKED,
    TaskStatus.FAILED,
    TaskStatus.CANCELLED,
    TaskStatus.INTERRUPTED,
})

_SCHEMA = """
CREATE TABLE IF NOT EXISTS tasks (
    id TEXT PRIMARY KEY,
    claim TEXT NOT NULL,
    doi TEXT NOT NULL,
    status TEXT NOT NULL,
    stage TEXT NOT NULL,
    label TEXT,
    error_code TEXT,
    decision TEXT,
    previous_id TEXT,
    cancel_requested INTEGER NOT NULL DEFAULT 0,
    run_config TEXT NOT NULL,
    criteria TEXT NOT NULL,
    counters TEXT NOT NULL,
    source TEXT,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    claimed_at REAL,
    deadline_at REAL
);
CREATE TABLE IF NOT EXISTS check_sources (
    task_id TEXT NOT NULL,
    source_id TEXT NOT NULL,
    PRIMARY KEY (task_id, source_id)
);
CREATE TABLE IF NOT EXISTS sources (
    source_id TEXT PRIMARY KEY,
    doi TEXT,
    pmcid TEXT,
    title TEXT,
    license TEXT,
    version TEXT,
    access_url TEXT,
    retrieved_at TEXT,
    version_hash TEXT,
    jats_bytes BLOB
);
CREATE TABLE IF NOT EXISTS paragraphs (
    paragraph_id TEXT PRIMARY KEY,
    source_id TEXT NOT NULL,
    section TEXT NOT NULL,
    ordinal INTEGER NOT NULL,
    text TEXT NOT NULL,
    paragraph_hash TEXT NOT NULL,
    source_url TEXT NOT NULL,
    native_jats_id TEXT
);
CREATE VIRTUAL TABLE IF NOT EXISTS paragraphs_fts USING fts5(
    paragraph_id UNINDEXED,
    text,
    tokenize='unicode61'
);
CREATE TABLE IF NOT EXISTS candidates (
    task_id TEXT NOT NULL,
    paragraph_id TEXT NOT NULL,
    round INTEGER NOT NULL,
    rank INTEGER NOT NULL,
    entered_context INTEGER NOT NULL DEFAULT 0,
    PRIMARY KEY (task_id, paragraph_id)
);
CREATE TABLE IF NOT EXISTS execution (
    seq INTEGER PRIMARY KEY AUTOINCREMENT,
    task_id TEXT NOT NULL,
    payload TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS model_calls (
    task_id TEXT NOT NULL,
    request_id TEXT NOT NULL,
    payload TEXT NOT NULL,
    PRIMARY KEY (task_id, request_id)
);
CREATE TABLE IF NOT EXISTS feedback (
    seq INTEGER PRIMARY KEY AUTOINCREMENT,
    task_id TEXT NOT NULL,
    comment TEXT NOT NULL,
    created_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS diagnostic_exports (
    seq INTEGER PRIMARY KEY AUTOINCREMENT,
    task_id TEXT NOT NULL,
    recipient TEXT NOT NULL,
    created_at TEXT NOT NULL
);
"""

EMPTY_COUNTERS = {"main_requests_used": 0, "repair_requests_used": 0, "supplemental_rounds_used": 0}


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _json(value) -> str:
    if hasattr(value, "model_dump"):
        value = value.model_dump(mode="json")
    return json.dumps(value, ensure_ascii=False)


class SqliteStore:
    """A single-connection SQLite store guarded by a process-local lock."""

    def __init__(self, path: str | Path) -> None:
        self.path = Path(path)
        if self.path.parent and str(self.path) != ":memory:":
            self.path.parent.mkdir(parents=True, exist_ok=True)
        self._lock = threading.RLock()
        self._conn = sqlite3.connect(str(self.path), check_same_thread=False, isolation_level=None)
        self._conn.row_factory = sqlite3.Row
        self._conn.execute("PRAGMA journal_mode=WAL")
        self._conn.execute("PRAGMA foreign_keys=ON")
        self._conn.executescript(_SCHEMA)

    def close(self) -> None:
        with self._lock:
            self._conn.close()

    # ---------------------------------------------------------------- helpers

    def _write(self, sql: str, params: tuple = ()) -> sqlite3.Cursor:
        with self._lock:
            self._conn.execute("BEGIN IMMEDIATE")
            try:
                cursor = self._conn.execute(sql, params)
            except BaseException:
                self._conn.execute("ROLLBACK")
                raise
            self._conn.execute("COMMIT")
            return cursor

    def _query(self, sql: str, params: tuple = ()) -> list[sqlite3.Row]:
        with self._lock:
            return list(self._conn.execute(sql, params).fetchall())

    def _row(self, task_id: str) -> sqlite3.Row | None:
        rows = self._query("SELECT * FROM tasks WHERE id = ?", (task_id,))
        return rows[0] if rows else None

    def _counters(self, row: sqlite3.Row) -> dict[str, int]:
        stored = json.loads(row["counters"]) if row["counters"] else {}
        return {**EMPTY_COUNTERS, **{key: int(value) for key, value in stored.items()}}

    def _accounting(self, task_id: str, counters: dict[str, int]) -> Accounting:
        calls = self.model_calls(task_id)
        observed = sum(len(call.attempts) for call in calls)
        complete = all(len(call.attempts) >= 1 for call in calls)
        return Accounting(
            verification="verified" if complete else "unverified",
            main_requests_used=counters["main_requests_used"],
            repair_requests_used=counters["repair_requests_used"],
            supplemental_rounds_used=counters["supplemental_rounds_used"],
            upstream_attempts_used=observed if complete else None,
            observed_upstream_attempts=observed,
            reason=None if complete else "attempt_records_missing",
        )

    # ------------------------------------------------------------ task writes

    def create(
        self,
        task: TaskInput,
        run_config: RunConfigSnapshot,
        criteria: CriteriaReference,
    ) -> None:
        stamp = _now()
        self._write(
            """INSERT INTO tasks (id, claim, doi, status, stage, label, error_code, decision,
                   previous_id, cancel_requested, run_config, criteria, counters, source,
                   created_at, updated_at)
               VALUES (?, ?, ?, ?, ?, NULL, NULL, NULL, ?, 0, ?, ?, ?, NULL, ?, ?)""",
            (
                task.id, task.claim, task.doi, TaskStatus.QUEUED.value, "wait", task.previous_id,
                _json(run_config), _json(criteria), json.dumps(EMPTY_COUNTERS), stamp, stamp,
            ),
        )

    def get(self, task_id: str) -> CheckDetail | None:
        row = self._row(task_id)
        if row is None:
            return None
        run_config = RunConfigSnapshot.model_validate(json.loads(row["run_config"]))
        return CheckDetail(
            id=row["id"],
            status=TaskStatus(row["status"]),
            stage=row["stage"],
            label=row["label"],
            error_code=row["error_code"],
            decision=json.loads(row["decision"]) if row["decision"] else None,
            previous_id=row["previous_id"],
            cancel_requested=bool(row["cancel_requested"]),
            criteria=CriteriaReference.model_validate(json.loads(row["criteria"])),
            accounting=self._accounting(task_id, self._counters(row)),
            limits=run_config.limits,
        )

    def get_run_config(self, task_id: str) -> RunConfigSnapshot | None:
        row = self._row(task_id)
        return RunConfigSnapshot.model_validate(json.loads(row["run_config"])) if row else None

    def get_input(self, task_id: str) -> dict | None:
        """Raw task input for diagnosis: claim, doi, linkage and cancel flag."""

        row = self._row(task_id)
        if row is None:
            return None
        return {
            "id": row["id"], "claim": row["claim"], "doi": row["doi"],
            "previous_id": row["previous_id"], "cancel_requested": bool(row["cancel_requested"]),
        }

    def source_record(self, task_id: str) -> SourceRecord | None:
        row = self._row(task_id)
        if row is None or not row["source"]:
            return None
        return SourceRecord.model_validate(json.loads(row["source"]))

    def list(self, status: TaskStatus | None = None) -> list[CheckSummary]:
        if status is None:
            rows = self._query("SELECT * FROM tasks ORDER BY created_at, id")
        else:
            rows = self._query("SELECT * FROM tasks WHERE status = ? ORDER BY created_at, id", (status.value,))
        return [
            CheckSummary(id=row["id"], doi=row["doi"], status=TaskStatus(row["status"]),
                         stage=row["stage"], label=row["label"])
            for row in rows
        ]

    def claim_next(self, deadline_at: float | None = None) -> TaskInput | None:
        with self._lock:
            self._conn.execute("BEGIN IMMEDIATE")
            try:
                rows = self._conn.execute(
                    "SELECT * FROM tasks WHERE status = ? ORDER BY created_at, id LIMIT 1",
                    (TaskStatus.QUEUED.value,),
                ).fetchall()
                if not rows:
                    self._conn.execute("COMMIT")
                    return None
                row = rows[0]
                self._conn.execute(
                    """UPDATE tasks SET status = ?, stage = 'source_identity', claimed_at = ?,
                           deadline_at = ?, updated_at = ? WHERE id = ? AND status = ?""",
                    (TaskStatus.RUNNING.value, _monotonic(), deadline_at, _now(), row["id"], TaskStatus.QUEUED.value),
                )
                self._conn.execute("COMMIT")
            except BaseException:
                self._conn.execute("ROLLBACK")
                raise
        return TaskInput(
            id=row["id"], claim=row["claim"], doi=row["doi"],
            config_digest=RunConfigSnapshot.model_validate(json.loads(row["run_config"])).config_digest,
            authorized_recipients=tuple(RunConfigSnapshot.model_validate(json.loads(row["run_config"])).authorized_recipients),
            previous_id=row["previous_id"],
        )

    def set_stage(self, task_id: str, stage: str) -> None:
        self._write("UPDATE tasks SET stage = ?, updated_at = ? WHERE id = ? AND status = ?",
                    (stage, _now(), task_id, TaskStatus.RUNNING.value))

    def take_request(self, task_id: str, kind: str) -> None:
        """Persist a request/round counter *before* dispatch, conservatively."""

        row = self._row(task_id)
        if row is None:
            return
        counters = self._counters(row)
        counters[kind] = counters.get(kind, 0) + 1
        self._write("UPDATE tasks SET counters = ?, updated_at = ? WHERE id = ?",
                    (json.dumps(counters), _now(), task_id))

    def update_source(self, task_id: str, source: SourceRecord) -> None:
        self._write("UPDATE tasks SET source = ?, updated_at = ? WHERE id = ?", (_json(source), _now(), task_id))

    def request_cancel(self, task_id: str) -> CancelResponse | ConflictResponse | None:
        with self._lock:
            self._conn.execute("BEGIN IMMEDIATE")
            try:
                rows = self._conn.execute("SELECT * FROM tasks WHERE id = ?", (task_id,)).fetchall()
                if not rows:
                    self._conn.execute("COMMIT")
                    return None
                row = rows[0]
                status = TaskStatus(row["status"])
                if status in TERMINAL_STATUSES:
                    self._conn.execute("COMMIT")
                    if status is TaskStatus.CANCELLED:
                        return self._cancel_response(row, cancel_requested=True)
                    return self._conflict(row, "任务已结束，不能取消")
                deadline = row["deadline_at"]
                if deadline is not None and not row["cancel_requested"] and _monotonic() > deadline:
                    # An expired task settles as TASK_TIMEOUT before this conflict.
                    self._conn.execute(
                        "UPDATE tasks SET status = ?, error_code = ?, updated_at = ? WHERE id = ?",
                        (TaskStatus.FAILED.value, ErrorCode.TASK_TIMEOUT.value, _now(), task_id),
                    )
                    self._conn.execute("COMMIT")
                    return self._conflict(
                        {**dict(row), "status": TaskStatus.FAILED.value}, "任务已超过执行时限"
                    )
                if status is TaskStatus.QUEUED:
                    self._conn.execute(
                        "UPDATE tasks SET status = ?, cancel_requested = 1, updated_at = ? WHERE id = ?",
                        (TaskStatus.CANCELLED.value, _now(), task_id),
                    )
                else:  # RUNNING: accept and let the worker finish the local wait.
                    self._conn.execute(
                        "UPDATE tasks SET cancel_requested = 1, updated_at = ? WHERE id = ?", (_now(), task_id)
                    )
                self._conn.execute("COMMIT")
            except BaseException:
                self._conn.execute("ROLLBACK")
                raise
        refreshed = self._row(task_id)
        assert refreshed is not None
        return self._cancel_response(refreshed, cancel_requested=True)

    def _cancel_response(self, row: sqlite3.Row | dict, cancel_requested: bool) -> CancelResponse:
        data = dict(row)
        return CancelResponse(
            id=data["id"], status=TaskStatus(data["status"]), cancel_requested=cancel_requested,
            label=data["label"], decision=json.loads(data["decision"]) if data["decision"] else None,
            error_code=data["error_code"],
        )

    def _conflict(self, row: sqlite3.Row | dict, message: str) -> ConflictResponse:
        data = dict(row)
        return ConflictResponse(error_code=None, status=TaskStatus(data["status"]), stage=data["stage"], message=message)

    def cancel_accepted(self, task_id: str) -> bool:
        row = self._row(task_id)
        return bool(row and row["cancel_requested"])

    def settle_orphaned_running(self) -> int:
        rows = self._query("SELECT id, cancel_requested FROM tasks WHERE status = ?", (TaskStatus.RUNNING.value,))
        changed = 0
        for row in rows:
            target = TaskStatus.CANCELLED if row["cancel_requested"] else TaskStatus.INTERRUPTED
            self._write("UPDATE tasks SET status = ?, updated_at = ? WHERE id = ? AND status = ?",
                        (target.value, _now(), row["id"], TaskStatus.RUNNING.value))
            changed += 1
        return changed

    def finish(
        self,
        task_id: str,
        *,
        status: TaskStatus,
        stage: str,
        error_code: ErrorCode | None,
        label: str | None,
        decision: dict | None,
    ) -> bool:
        """Conditionally store a terminal result; never overwrite another terminal state."""

        cursor = self._write(
            """UPDATE tasks SET status = ?, stage = ?, error_code = ?, label = ?, decision = ?, updated_at = ?
               WHERE id = ? AND status IN (?, ?)""",
            (status.value, stage, error_code.value if error_code else None, label,
             json.dumps(decision, ensure_ascii=False) if decision is not None else None,
             _now(), task_id, TaskStatus.QUEUED.value, TaskStatus.RUNNING.value),
        )
        return cursor.rowcount > 0

    def save(self, result: CheckDetail) -> None:
        self.finish(
            result.id, status=result.status, stage=result.stage, error_code=result.error_code,
            label=result.label, decision=result.decision.model_dump(mode="json") if result.decision else None,
        )

    def delete(self, task_id: str) -> str:
        """Delete a terminal task; return 'deleted', 'missing' or 'conflict'."""

        row = self._row(task_id)
        if row is None:
            return "missing"
        if TaskStatus(row["status"]) not in TERMINAL_STATUSES:
            return "conflict"
        source_ids = [item["source_id"] for item in self._query(
            "SELECT source_id FROM check_sources WHERE task_id = ?", (task_id,))]
        for table in ("feedback", "execution", "model_calls", "candidates", "diagnostic_exports"):
            self._write(f"DELETE FROM {table} WHERE task_id = ?", (task_id,))
        self._write("DELETE FROM check_sources WHERE task_id = ?", (task_id,))
        self._write("DELETE FROM tasks WHERE id = ?", (task_id,))
        for source_id in source_ids:
            remaining = self._query("SELECT 1 FROM check_sources WHERE source_id = ? LIMIT 1", (source_id,))
            if not remaining:
                self._delete_source(source_id)
        return "deleted"

    def _delete_source(self, source_id: str) -> None:
        with self._lock:
            self._conn.execute("BEGIN IMMEDIATE")
            try:
                self._conn.execute(
                    "DELETE FROM paragraphs_fts WHERE paragraph_id IN "
                    "(SELECT paragraph_id FROM paragraphs WHERE source_id = ?)", (source_id,))
                self._conn.execute("DELETE FROM paragraphs WHERE source_id = ?", (source_id,))
                self._conn.execute("DELETE FROM sources WHERE source_id = ?", (source_id,))
                self._conn.execute("COMMIT")
            except BaseException:
                self._conn.execute("ROLLBACK")
                raise

    # ------------------------------------------------------- records & index

    def record_execution(self, task_id: str, event: ExecutionRecord) -> None:
        self._write("INSERT INTO execution (task_id, payload) VALUES (?, ?)", (task_id, _json(event)))

    def execution(self, task_id: str) -> list[ExecutionRecord]:
        return [ExecutionRecord.model_validate(json.loads(row["payload"]))
                for row in self._query("SELECT payload FROM execution WHERE task_id = ? ORDER BY seq", (task_id,))]

    def record_model_call(self, task_id: str, call: ModelCall) -> None:
        self._write(
            "INSERT OR REPLACE INTO model_calls (task_id, request_id, payload) VALUES (?, ?, ?)",
            (task_id, call.request_id, _json(call)),
        )

    def model_calls(self, task_id: str) -> list[ModelCall]:
        return [ModelCall.model_validate(json.loads(row["payload"]))
                for row in self._query("SELECT payload FROM model_calls WHERE task_id = ? ORDER BY rowid", (task_id,))]

    def record_candidates(self, task_id: str, candidates: list[EvidenceCandidate]) -> None:
        for candidate in candidates:
            self._write(
                """INSERT OR REPLACE INTO candidates (task_id, paragraph_id, round, rank, entered_context)
                   VALUES (?, ?, ?, ?, ?)""",
                (task_id, candidate.paragraph_id, candidate.round, candidate.rank, int(candidate.entered_context)),
            )

    def candidates(self, task_id: str) -> list[EvidenceCandidate]:
        return [
            EvidenceCandidate(
                paragraph_id=row["paragraph_id"], section=row["section"], quote=row["quote"],
                paragraph_hash=row["paragraph_hash"], source_url=row["source_url"],
                round=row["round"], rank=row["rank"], entered_context=bool(row["entered_context"]),
            )
            for row in self._query(
                """SELECT c.paragraph_id, c.round, c.rank, c.entered_context,
                          p.section, p.text AS quote, p.paragraph_hash, p.source_url
                   FROM candidates c JOIN paragraphs p ON p.paragraph_id = c.paragraph_id
                   WHERE c.task_id = ? ORDER BY c.round, c.rank""",
                (task_id,),
            )
        ]

    def add_feedback(self, task_id: str, comment: str) -> bool:
        if self._row(task_id) is None:
            return False
        self._write("INSERT INTO feedback (task_id, comment, created_at) VALUES (?, ?, ?)",
                    (task_id, comment, _now()))
        return True

    def record_diagnostic_export(self, task_id: str, recipient: str) -> None:
        self._write("INSERT INTO diagnostic_exports (task_id, recipient, created_at) VALUES (?, ?, ?)",
                    (task_id, recipient, _now()))

    def link_task_source(self, task_id: str, source_id: str) -> None:
        self._write("INSERT OR IGNORE INTO check_sources (task_id, source_id) VALUES (?, ?)", (task_id, source_id))

    def index_source(self, source_id: str, source: SourceRecord, jats_bytes: bytes) -> None:
        self._write(
            """INSERT OR REPLACE INTO sources (source_id, doi, pmcid, title, license, version,
                   access_url, retrieved_at, version_hash, jats_bytes)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (source_id, source.doi, source.pmcid, source.title, source.license, source.version,
             source.access_url, source.retrieved_at, source.version_hash, jats_bytes),
        )

    def index_paragraphs(self, source_id: str, paragraphs: list[Paragraph]) -> None:
        with self._lock:
            self._conn.execute("BEGIN IMMEDIATE")
            try:
                self._conn.execute(
                    "DELETE FROM paragraphs_fts WHERE paragraph_id IN "
                    "(SELECT paragraph_id FROM paragraphs WHERE source_id = ?)", (source_id,))
                self._conn.execute("DELETE FROM paragraphs WHERE source_id = ?", (source_id,))
                for paragraph in paragraphs:
                    self._conn.execute(
                        """INSERT INTO paragraphs (paragraph_id, source_id, section, ordinal, text,
                               paragraph_hash, source_url, native_jats_id)
                           VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
                        (paragraph.paragraph_id, source_id, paragraph.section,
                         _ordinal(paragraph.paragraph_id), paragraph.text, paragraph.paragraph_hash,
                         paragraph.source_url, paragraph.native_jats_id),
                    )
                    self._conn.execute(
                        "INSERT INTO paragraphs_fts (paragraph_id, text) VALUES (?, ?)",
                        (paragraph.paragraph_id, paragraph.text),
                    )
                self._conn.execute("COMMIT")
            except BaseException:
                self._conn.execute("ROLLBACK")
                raise

    def get_source(self, source_id: str) -> dict | None:
        rows = self._query("SELECT * FROM sources WHERE source_id = ?", (source_id,))
        if not rows:
            return None
        row = rows[0]
        return {key: row[key] for key in row.keys() if key != "jats_bytes"}

    def source_for_task(self, task_id: str) -> str | None:
        rows = self._query("SELECT source_id FROM check_sources WHERE task_id = ? LIMIT 1", (task_id,))
        return rows[0]["source_id"] if rows else None

    def search(self, source_id: str, match: str, limit: int) -> list[Paragraph]:
        try:
            rows = self._query(
                """SELECT p.* FROM paragraphs_fts
                   JOIN paragraphs p ON p.paragraph_id = paragraphs_fts.paragraph_id
                   WHERE paragraphs_fts MATCH ? AND p.source_id = ?
                   ORDER BY bm25(paragraphs_fts) LIMIT ?""",
                (match, source_id, limit),
            )
        except sqlite3.Error as error:  # index/database fault, never an empty result
            raise ContractError(ErrorCode.RETRIEVAL_FAILED, f"检索失败：{type(error).__name__}") from error
        return [_paragraph(row) for row in rows]

    def read_neighbors(self, source_id: str, paragraph_ids: list[str]) -> list[Paragraph]:
        if not paragraph_ids:
            return []
        placeholders = ",".join("?" for _ in paragraph_ids)
        rows = self._query(
            f"""SELECT * FROM paragraphs WHERE source_id = ? AND paragraph_id IN ({placeholders})
                ORDER BY ordinal""",
            (source_id, *paragraph_ids),
        )
        return [_paragraph(row) for row in rows]

    def paragraph_text(self, source_id: str, paragraph_id: str) -> str | None:
        rows = self._query("SELECT text FROM paragraphs WHERE source_id = ? AND paragraph_id = ?",
                           (source_id, paragraph_id))
        return rows[0]["text"] if rows else None

    def record_terminal_failure(self, task_id: str, error_code: ErrorCode | None, stage: str) -> bool:
        return self.finish(
            task_id, status=terminal_status(error_code), stage=stage,
            error_code=error_code, label=None, decision=None,
        )


def _paragraph(row: sqlite3.Row) -> Paragraph:
    return Paragraph(
        paragraph_id=row["paragraph_id"], source_id=row["source_id"], section=row["section"],
        text=row["text"], paragraph_hash=row["paragraph_hash"], source_url=row["source_url"],
        native_jats_id=row["native_jats_id"],
    )


def _ordinal(paragraph_id: str) -> int:
    try:
        return int(paragraph_id.rsplit(":", 1)[1])
    except (IndexError, ValueError):
        return 0


def _monotonic() -> float:
    import time

    return time.monotonic()
