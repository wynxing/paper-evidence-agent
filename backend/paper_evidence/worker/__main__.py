"""Worker entry point.

Drains queued tasks with one claim at a time. Leftover RUNNING tasks are settled
when they cannot still be alive — their deadline has passed, or they carry no
deadline at all: a persisted cancel flag becomes CANCELLED, anything else becomes
INTERRUPTED and waits for an explicit retry. Only ``RUNNING`` rows that can still
belong to a live claim are left alone, so starting a second worker does not
interrupt the first one's task (Issue #34).

Two modes:

* default — drain the queue and exit. Suited to a one-shot run or a scheduler.
* ``--loop`` (or ``PAPER_EVIDENCE_WORKER_LOOP=1``) — stay up and keep claiming,
  so a client that polls a QUEUED task sees it run. The API process never
  executes tasks itself, so an end-to-end session needs this mode.

The poll interval for the loop comes from ``--interval <seconds>`` or
``PAPER_EVIDENCE_WORKER_POLL_SECONDS`` (default 1 second).
"""

import asyncio
import os
import sys

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


async def _run(services: Services, loop: bool, interval: float) -> int:
    try:
        # 启动先扫一次并报告结果。`run_once` 每轮也会结算（遗留行在启动这一刻通常还没到
        # deadline，只靠这一次扫尾留不住队列），但那里无法把「上个进程留下了几条」讲给
        # 启动这个进程的人听。
        settled = services.store.settle_orphaned_running()
        if settled:
            print(f"已结算 {settled} 个遗留 RUNNING 任务。", file=sys.stderr)
        worker = build_worker(services)
        return await (drain_forever(worker, interval) if loop else drain(worker))
    finally:
        await services.aclose()


def main() -> int:
    loop, interval = parse_options(sys.argv[1:], dict(os.environ))
    services = Services(Settings.from_env())
    try:
        count = asyncio.run(_run(services, loop, interval))
    except KeyboardInterrupt:
        # The resident loop only ends here, so its processed count is not reported.
        print("worker 收到中断，已停止。", file=sys.stderr)
        return 0
    print(f"worker 本次处理了 {count} 个任务，队列已空。", file=sys.stderr)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
