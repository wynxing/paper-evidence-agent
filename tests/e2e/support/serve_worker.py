"""Run the resident worker against the same store and the stubbed sources.

API 进程不执行任务（`docs/development.md` 第 58 行），所以端到端必须另有常驻
worker，否则任务永远停在 ``QUEUED``。轮询间隔调小到 0.2 秒，避免用例为了等
「排队 → 执行」白等默认的 1 秒。

末尾那个只接受连接、不回内容的 TCP 监听只是一个**就绪信标**：Playwright 用
``port`` 判断进程是否起来，它本身不提供任何功能。
"""

import asyncio
import os
import socketserver
import sys
import threading
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from runtime import e2e_settings  # noqa: E402

from paper_evidence.api.deps import Services, set_services  # noqa: E402
from paper_evidence.worker.__main__ import build_worker  # noqa: E402
from paper_evidence.worker.runner import drain_forever  # noqa: E402


async def _serve(services: Services, interval: float) -> None:
    services.store.settle_orphaned_running()
    await drain_forever(build_worker(services), interval)


def _beacon(port: int) -> None:
    class Handler(socketserver.BaseRequestHandler):
        def handle(self) -> None:
            self.request.recv(1)

    with socketserver.TCPServer(("127.0.0.1", port), Handler) as server:
        server.serve_forever()


def main() -> int:
    services = Services(e2e_settings())
    set_services(services)
    beacon = os.environ.get("PAPER_EVIDENCE_E2E_WORKER_READY_PORT")
    if beacon:
        threading.Thread(target=_beacon, args=(int(beacon),), daemon=True).start()
    try:
        asyncio.run(_serve(services, float(os.environ.get("PAPER_EVIDENCE_E2E_WORKER_INTERVAL", "0.2"))))
    except KeyboardInterrupt:
        pass
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
