"""Task lifecycle in storage: claim, cancellation races, deadline clock, deletion.

These cover 测试方案「边界与异常」的要求：取消/总超时竞争、重启结算、删除的原子性。
The deadline clock is asserted explicitly, because ``claimed_at``/``deadline_at``
are persisted and read by the API process, so a process-local monotonic
timestamp would be wrong across a restart.
"""

import time
from dataclasses import replace

import pytest

from paper_evidence.config import Settings
from paper_evidence.domain import ErrorCode, TaskStatus
from paper_evidence.domain.contracts import RunConfigSnapshot, SourceRecord
from paper_evidence.domain.records import TaskInput
from paper_evidence.domain.rules import criteria_reference
from paper_evidence.retrieval.jats import parse_jats
from paper_evidence.domain.records import SourceSnapshot
from paper_evidence.storage.sqlite import SqliteStore

VERSION_HASH = "d" * 64
JATS = b"""<?xml version="1.0" encoding="UTF-8"?>
<article xml:lang="en"><front><article-meta/></front><body>
<sec><title>Results</title><p id="n1">The treatment reduced mortality.</p></sec>
</body></article>
"""


def _moment(value: str | None):
    """Parse a stored ISO-8601 timestamp so durations compare as instants."""

    from datetime import datetime

    assert value is not None
    return datetime.fromisoformat(value)


@pytest.fixture
def store(tmp_path):
    db = SqliteStore(tmp_path / "lifecycle.sqlite3")
    yield db
    db.close()


def make_task(store, task_id="t1", doi="10.1000/xyz"):
    settings = replace(Settings.from_env(), contact_email="")
    task = TaskInput(id=task_id, claim="The treatment reduced mortality.", doi=doi,
                     config_digest="d", authorized_recipients=("Agnes",))
    run_config = RunConfigSnapshot(profile="daily", config_digest="d", snapshot_ref="r",
                                   authorized_recipients=["Agnes"], limits=settings.limits,
                                   timeouts=settings.timeouts, observability=settings.observability)
    store.create(task, run_config, criteria_reference("rev"))
    return task


def index_source(store, task_id, source_id=f"PMC123:{VERSION_HASH}"):
    record = SourceRecord(title="Demo", authors=["Ada Lovelace"], year=2026, doi="10.1000/xyz",
                          pmcid="PMC123", license="CC BY", version="1",
                          access_url="https://pmc.ncbi.nlm.nih.gov/articles/PMC123/",
                          retrieved_at="2026-10-01T00:00:00+00:00", version_hash=VERSION_HASH)
    snapshot = SourceSnapshot(source_id=source_id, metadata=record, jats_bytes=JATS,
                              open_locations=("https://open.example/x",))
    store.link_task_source(task_id, source_id)
    store.index_source(source_id, record, JATS, snapshot.open_locations)
    store.index_paragraphs(source_id, parse_jats(snapshot))
    return source_id


def test_claimed_deadline_records_a_wall_clock_epoch(store):
    make_task(store)
    store.claim_next(time.time() + 180)
    row = store._query("SELECT claimed_at, deadline_at FROM tasks WHERE id = ?", ("t1",))[0]
    now = time.time()
    # Same clock the API process reads; a monotonic value would be far off.
    assert abs(row["claimed_at"] - now) < 60
    assert abs(row["deadline_at"] - (now + 180)) < 60


def test_expired_wall_clock_deadline_settles_as_task_timeout(store):
    make_task(store)
    store.claim_next(time.time() - 1)  # already past the wall-clock deadline

    outcome = store.request_cancel("t1")
    assert outcome.status is TaskStatus.FAILED
    assert store.get("t1").error_code is ErrorCode.TASK_TIMEOUT


def test_live_deadline_accepts_cancel_without_false_expiry(store):
    make_task(store)
    store.claim_next(time.time() + 180)

    outcome = store.request_cancel("t1")
    assert outcome.status is TaskStatus.RUNNING
    assert outcome.cancel_requested is True
    assert store.cancel_accepted("t1") is True


def test_queued_cancel_short_circuits_and_repeats_are_idempotent(store):
    make_task(store)
    first = store.request_cancel("t1")
    assert first.status is TaskStatus.CANCELLED
    assert store.request_cancel("t1").status is TaskStatus.CANCELLED
    assert store.claim_next(time.time() + 180) is None  # never re-claimed
    assert store.request_cancel("missing") is None


def test_terminal_result_never_overwrites_a_terminal_state(store):
    make_task(store)
    store.request_cancel("t1")  # QUEUED -> CANCELLED
    assert store.finish("t1", status=TaskStatus.COMPLETED, stage="evidence_validation",
                        error_code=None, label="支持", decision=None) is False
    assert store.get("t1").status is TaskStatus.CANCELLED


def test_worker_finishes_a_claimed_cancelled_task_as_cancelled(store):
    make_task(store)
    store.claim_next(time.time() + 180)
    store.request_cancel("t1")

    assert store.finish("t1", status=TaskStatus.CANCELLED, stage="wait",
                        error_code=None, label=None, decision=None) is True
    stored = store.get("t1")
    assert stored.status is TaskStatus.CANCELLED
    assert stored.label is None and stored.decision is None


def test_completion_without_a_cancel_still_lands(store):
    """没有受理取消时，普通终态照常写入（守卫只挡已受理的取消）。"""

    make_task(store)
    store.claim_next(time.time() + 180)

    assert store.finish("t1", status=TaskStatus.COMPLETED, stage="evidence_validation",
                        error_code=None, label="支持", decision=None) is True
    stored = store.get("t1")
    assert stored.status is TaskStatus.COMPLETED
    assert stored.label == "支持"


def test_accepted_cancel_blocks_a_later_completion_and_wins(store):
    """RUNNING 期间受理的取消必须先落：完成结果不得覆盖（测试方案「取消先于完成」）。

    必须经 ``claim_next`` 进入 RUNNING —— 若仍是 QUEUED，``request_cancel`` 会直接把
    任务落成 CANCELLED，测不出这个窗口。
    """

    make_task(store)
    store.claim_next(time.time() + 180)  # QUEUED -> RUNNING via the real claim path
    store.request_cancel("t1")
    assert store.cancel_accepted("t1") is True

    # A completed result must not overwrite the accepted cancel.
    assert store.finish("t1", status=TaskStatus.COMPLETED, stage="evidence_validation",
                        error_code=None, label="支持", decision=None) is False
    running = store.get("t1")
    assert running.status is TaskStatus.RUNNING
    assert running.label is None and running.decision is None

    # A failure must not overwrite it either.
    assert store.finish("t1", status=TaskStatus.FAILED, stage="wait",
                        error_code=None, label=None, decision=None) is False
    assert store.get("t1").status is TaskStatus.RUNNING

    # The cancel path then commits CANCELLED.
    assert store.finish("t1", status=TaskStatus.CANCELLED, stage="wait",
                        error_code=None, label=None, decision=None) is True
    assert store.get("t1").status is TaskStatus.CANCELLED


def test_settle_orphaned_running_splits_cancelled_from_interrupted(store):
    make_task(store, "t1")
    make_task(store, "t2")
    store.claim_next(time.time() + 180)
    store.claim_next(time.time() + 180)
    store.request_cancel("t2")

    assert store.settle_orphaned_running() == 2
    assert store.get("t1").status is TaskStatus.INTERRUPTED
    assert store.get("t2").status is TaskStatus.CANCELLED


def test_delete_refuses_a_running_task(store):
    make_task(store)
    store.claim_next(time.time() + 180)
    assert store.delete("t1") == "conflict"
    assert store.get("t1") is not None
    assert store.delete("missing") == "missing"


def test_delete_keeps_a_source_cache_until_its_last_reference_is_gone(store):
    make_task(store, "t1")
    make_task(store, "t2")
    source_id = index_source(store, "t1")
    store.link_task_source("t2", source_id)
    store.record_candidates("t1", [])
    store.add_feedback("t1", "first")
    store.request_cancel("t1")
    store.request_cancel("t2")

    assert store.delete("t1") == "deleted"
    assert store.get("t1") is None
    assert store._query("SELECT 1 FROM feedback WHERE task_id = ?", ("t1",)) == []
    # The shared source cache and its index survive while t2 still references it.
    assert store.get_source(source_id) is not None
    assert store.read_paragraph(source_id, f"p:PMC123:{VERSION_HASH}:jats-0.1.0:1") is not None
    # The local OpenAlex hint is stored alongside the frozen PMC version.
    assert store.get_source(source_id)["open_locations"] == ["https://open.example/x"]

    assert store.delete("t2") == "deleted"
    assert store.get_source(source_id) is None
    assert store.read_paragraph(source_id, f"p:PMC123:{VERSION_HASH}:jats-0.1.0:1") is None
    assert store._query("SELECT 1 FROM paragraphs_fts LIMIT 1") == []


def test_history_rows_carry_an_excerpt_and_a_timestamp(store):
    make_task(store, "t1", doi="10.1000/older")
    rows = store.list()
    assert [row.id for row in rows] == ["t1"]
    assert rows[0].doi == "10.1000/older"
    assert rows[0].claim_excerpt == "The treatment reduced mortality."
    assert rows[0].created_at and "T" in rows[0].created_at
    assert [row.id for row in store.list(TaskStatus.QUEUED)] == ["t1"]
    assert store.list(TaskStatus.COMPLETED) == []


def test_list_orders_by_creation_time_descending(store):
    """界面按服务端顺序直接渲染，最新的在最前；不再由客户端倒序。"""

    for task_id in ("t1", "t2", "t3"):
        make_task(store, task_id)
    for task_id, stamp in (("t1", "2026-01-01T00:00:00+00:00"),
                           ("t2", "2026-02-01T00:00:00+00:00"),
                           ("t3", "2026-03-01T00:00:00+00:00")):
        store._write("UPDATE tasks SET created_at = ? WHERE id = ?", (stamp, task_id))

    assert [row.id for row in store.list()] == ["t3", "t2", "t1"]
    assert [row.created_at for row in store.list()] == [
        "2026-03-01T00:00:00+00:00", "2026-02-01T00:00:00+00:00", "2026-01-01T00:00:00+00:00",
    ]


def test_detail_exposes_the_claim_source_and_run_timing(store):
    make_task(store, "t1")
    fresh = store.get("t1")
    assert fresh.claim == "The treatment reduced mortality."
    assert fresh.source is None
    assert fresh.created_at and fresh.started_at is None and fresh.finished_at is None

    store.claim_next(time.time() + 180)
    running = store.get("t1")
    assert running.status is TaskStatus.RUNNING
    assert running.started_at is not None and running.finished_at is None
    assert _moment(running.started_at) >= _moment(running.created_at)

    assert store.finish("t1", status=TaskStatus.CANCELLED, stage="wait", error_code=None,
                        label=None, decision=None) is True
    done = store.get("t1")
    assert done.finished_at is not None
    assert _moment(done.finished_at) >= _moment(done.started_at)


def test_finished_at_is_set_when_a_queued_cancel_commits(store):
    make_task(store, "t1")
    store.request_cancel("t1")
    assert store.get("t1").finished_at is not None


def test_source_index_keeps_the_bibliographic_identity(store):
    make_task(store, "t1")
    source_id = index_source(store, "t1")
    stored = store.get_source(source_id)
    assert stored["authors"] == ["Ada Lovelace"] and stored["year"] == 2026

    store.update_source("t1", SourceRecord(
        title="Demo", authors=["Ada Lovelace"], year=2026, doi="10.1000/xyz", pmcid="PMC123",
        license="CC BY", version="1", access_url="https://example.org/a",
        retrieved_at="2026-10-01T00:00:00+00:00", version_hash=VERSION_HASH,
    ))
    record = store.source_record("t1")
    assert record.authors == ["Ada Lovelace"] and record.year == 2026


def test_a_source_row_written_before_authors_existed_still_reads(store):
    """新增字段是契约扩展，不是解析失败：旧行缺少 authors/year 时按空值读出。"""

    make_task(store, "t1")
    legacy = ('{"title": "Legacy", "doi": "10.1000/xyz", "pmcid": "PMC123", "license": "CC BY", '
              '"version": "1", "access_url": "https://example.org/a", '
              '"retrieved_at": "2026-10-01T00:00:00+00:00", "version_hash": "e"}')
    store._write("UPDATE tasks SET source = ? WHERE id = ?", (legacy, "t1"))
    record = store.source_record("t1")
    assert record.title == "Legacy" and record.authors == [] and record.year is None
    assert store.get("t1").source.doi == "10.1000/xyz"


def test_opening_an_older_database_adds_the_new_columns_and_keeps_rows(tmp_path):
    """CREATE TABLE IF NOT EXISTS 不会改动已有表，故新增列显式补齐且不丢数据。"""

    import sqlite3

    path = tmp_path / "legacy.sqlite3"
    connection = sqlite3.connect(str(path))
    connection.executescript(
        """
        CREATE TABLE tasks (id TEXT PRIMARY KEY, claim TEXT NOT NULL, doi TEXT NOT NULL,
            status TEXT NOT NULL, stage TEXT NOT NULL, label TEXT, error_code TEXT, decision TEXT,
            previous_id TEXT, cancel_requested INTEGER NOT NULL DEFAULT 0, run_config TEXT NOT NULL,
            criteria TEXT NOT NULL, counters TEXT NOT NULL, source TEXT,
            created_at TEXT NOT NULL, updated_at TEXT NOT NULL, claimed_at REAL, deadline_at REAL);
        CREATE TABLE sources (source_id TEXT PRIMARY KEY, doi TEXT, pmcid TEXT, title TEXT,
            license TEXT, version TEXT, access_url TEXT, retrieved_at TEXT, version_hash TEXT,
            open_locations TEXT, jats_bytes BLOB);
        """
    )
    connection.execute(
        "INSERT INTO tasks (id, claim, doi, status, stage, run_config, criteria, counters, created_at, updated_at)"
        " VALUES ('old', '遗留论断', '10.1000/old', 'QUEUED', 'wait', '{}', '{}', '{}', '2026-01-01T00:00:00+00:00',"
        " '2026-01-01T00:00:00+00:00')"
    )
    connection.commit()
    connection.close()

    store = SqliteStore(path)
    try:
        assert {"finished_at"} <= {row["name"] for row in store._query("PRAGMA table_info(tasks)")}
        assert {"authors", "year"} <= {row["name"] for row in store._query("PRAGMA table_info(sources)")}
        rows = store.list()
        assert [row.id for row in rows] == ["old"]
        assert rows[0].claim_excerpt == "遗留论断"
    finally:
        store.close()
