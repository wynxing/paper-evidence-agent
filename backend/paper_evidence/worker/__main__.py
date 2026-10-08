"""Worker entry point.

Drains queued tasks with one claim at a time, then exits. Leftover RUNNING tasks
are settled on startup: a persisted cancel flag becomes CANCELLED, anything else
becomes INTERRUPTED and waits for an explicit retry.
"""

import asyncio
import sys

from paper_evidence.api.deps import Services
from paper_evidence.config import Settings
from paper_evidence.graph.workflow import BoundedWorkflow
from paper_evidence.retrieval.local import StoreRetriever
from paper_evidence.worker.runner import SingleTaskWorker, drain


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


async def _run(services: Services) -> int:
    try:
        settled = services.store.settle_orphaned_running()
        if settled:
            print(f"已结算 {settled} 个遗留 RUNNING 任务。", file=sys.stderr)
        return await drain(build_worker(services))
    finally:
        await services.aclose()


def main() -> int:
    services = Services(Settings.from_env())
    count = asyncio.run(_run(services))
    print(f"worker 本次处理了 {count} 个任务，队列已空。", file=sys.stderr)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
