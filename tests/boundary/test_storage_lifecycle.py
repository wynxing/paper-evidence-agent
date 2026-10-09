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
    record = SourceRecord(title="Demo", doi="10.1000/xyz", pmcid="PMC123", license="CC BY", version="1",
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
