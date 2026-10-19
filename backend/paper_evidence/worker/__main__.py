"""Worker entry point.

Drains queued tasks with one claim at a time. Leftover RUNNING tasks are settled
once their own time limit has passed — their deadline has passed, or they carry no
deadline at all: a persisted cancel flag becomes CANCELLED, anything else becomes
INTERRUPTED and waits for an explicit retry. Only ``RUNNING`` rows within their own
deadline are left alone, so starting a second worker does not interrupt the first
one's task (Issue #34).

Two modes:

* default — drain the queue and exit. Suited to a one-shot run or a scheduler.
* ``--loop`` (or ``PAPER_EVIDENCE_WORKER_LOOP=1``) — stay up and keep claiming,
  so a client that polls a QUEUED task sees it run. The API process never
  executes tasks itself, so an end-to-end session needs this mode.

Both stop claiming for two different reasons, and the closing line tells them
apart: the queue has no claimable task left, or a task is still RUNNING in another
process (in which case QUEUED tasks may still be waiting). Recovery that waits for
a deadline to pass needs ``--loop`` — a one-shot run does not wait, it exits and
has to be re-run.

The poll interval for the loop comes from ``--interval <seconds>`` or
``PAPER_EVIDENCE_WORKER_POLL_SECONDS`` (default 1 second).
"""

import asyncio
import os
import sys
from datetime import datetime, timezone

from paper_evidence.api.deps import Services
from paper_evidence.config import Settings
from paper_evidence.graph.workflow import BoundedWorkflow
from paper_evidence.retrieval.local import StoreRetriever
from paper_evidence.worker.runner import SingleTaskWorker, drain, drain_forever

LOOP_ENV = "PAPER_EVIDENCE_WORKER_LOOP"
INTERVAL_ENV = "PAPER_EVIDENCE_WORKER_POLL_SECONDS"
DEFAULT_INTERVAL = 1.0
MIN_INTERVAL = 0.05


def build_worker(services: Services) -> SingleTaskWorker:
    source = services.source_service()
    retriever = StoreRetriever(services.store, services.settings.retrieval_context_limit)
    gateway = services.gateway()

    def factory(task):
        return BoundedWorkflow(
            store=services.store, resolver=source, fulltext=source, retriever=retriever,
            prompts=services.prompts, gateway=gateway, settings=services.settings,
            tracing=services.tracing,
        )

    return SingleTaskWorker(services.store, factory, services.settings)


def parse_options(argv: list[str], env: dict[str, str]) -> tuple[bool, float]:
    """Resolve loop mode and the poll interval from arguments and environment."""

    loop = "--loop" in argv or env.get(LOOP_ENV, "").strip().lower() in {"1", "true", "yes"}
    interval = DEFAULT_INTERVAL
    raw = env.get(INTERVAL_ENV, "").strip()
    if "--interval" in argv:
        position = argv.index("--interval")
        raw = argv[position + 1] if position + 1 < len(argv) else ""
    if raw:
        try:
            interval = max(MIN_INTERVAL, float(raw))
        except ValueError:
            interval = DEFAULT_INTERVAL
    return loop, interval


async def _run(services: Services, loop: bool, interval: float) -> tuple[int, dict | None]:
    try:
        # 启动先扫一次并报告结果。`run_once` 每轮也会结算（遗留行在启动这一刻通常还没到
        # deadline，只靠这一次扫尾留不住队列），但那里无法把「上个进程留下了几条」讲给
        # 启动这个进程的人听。
        settled = services.store.settle_orphaned_running()
        if settled:
            print(f"已结算 {settled} 个遗留 RUNNING 任务。", file=sys.stderr)
        worker = build_worker(services)
        if loop:
            # 常驻循环只能被中断结束（见 `main`），所以这里的停止原因不会被用到。
            return await drain_forever(worker, interval), None
        return await drain(worker), worker.stall
    finally:
        await services.aclose()


def closing_message(count: int, stall: dict | None) -> str:
    """The line this run ends with: 队列已空, or the RUNNING task that stopped it.

    ``drain`` also stops when a task is still ``RUNNING`` in another process — the
    queue may then still hold ``QUEUED`` tasks this run could not take, so
    「队列已空」would tell the operator to stop re-running while work is waiting.
    This reports the blocking row instead, and claims nothing about the rest of the
    queue: it has not read it (Issue #44 第 3.2 条). ``--loop`` never reaches this
    line — it ends on an interrupt, which has its own message.
    """

    if stall is None:
        return f"worker 本次处理了 {count} 个任务，队列已空。"
    deadline = stall.get("deadline_at")
    due = "" if deadline is None else f"，时限 {_iso(deadline)}"
    return (f"worker 本次处理了 {count} 个任务；有 1 个任务仍在 RUNNING"
            f"（{stall['id']}，阶段 {stall['stage']}{due}），本次未处理。")


def _iso(deadline_at: float) -> str:
    """Render a stored wall-clock epoch second as an ISO-8601 UTC timestamp.

    ``deadline_at`` 是唯一能告诉操作者「还要等多久」的值：任务详情只返回
    ``created_at`` / ``started_at`` / ``finished_at``，不含 deadline。
    """

    return datetime.fromtimestamp(float(deadline_at), tz=timezone.utc).isoformat()


def main() -> int:
    loop, interval = parse_options(sys.argv[1:], dict(os.environ))
    services = Services(Settings.from_env())
    try:
        count, stall = asyncio.run(_run(services, loop, interval))
    except KeyboardInterrupt:
        # The resident loop only ends here, so its processed count is not reported.
        print("worker 收到中断，已停止。", file=sys.stderr)
        return 0
    print(closing_message(count, stall), file=sys.stderr)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
