"""Run the resident worker against the same store and the stubbed sources.

API 进程不执行任务（`docs/development.md` 第 58 行），所以端到端必须另有常驻
worker，否则任务永远停在 ``QUEUED``。轮询间隔调小到 0.2 秒，避免用例为了等
「排队 → 执行」白等默认的 1 秒。

末尾那个只接受连接、不回内容的 TCP 监听只是一个**就绪信标**：Playwright 用
``port`` 判断进程是否起来，它本身不提供任何功能。

就绪信标只能证明「进程起过」，证明不了「它还在消费队列」：这个进程若在就绪之后
退出，界面上只会看到任务永远停在「排队中」。所以这里把 stdout / stderr 另存一份到
数据目录（``worker.log``），随作业产物上传——Playwright 自己接管 webServer 的
stdout（默认 ``ignore``），光靠它的转述不足以定位。
"""

import asyncio
import os
import socketserver
import sys
import threading
import traceback
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


class _Tee:
    """Write through to the real stream *and* to the run's log file.

    写一份到文件是刻意的：进程被谁杀掉、卡在哪一行，只有它自己的输出能说清，
    而 CI 上那份输出不归我们管。
    """

    def __init__(self, stream, handle) -> None:
        self._stream = stream
        self._handle = handle

    def write(self, text: str) -> int:
        self._handle.write(text)
        self._handle.flush()
        return self._stream.write(text)

    def flush(self) -> None:
        self._handle.flush()
        self._stream.flush()

    def isatty(self) -> bool:
        return False


def _mirror_output() -> None:
    """Mirror stdout/stderr into ``<数据目录>/worker.log``; no-op without the env.

    这是诊断用的旁路，不是功能的一部分：拿不到目录、写不进去都只当没这回事，
    绝不能因为记录失败把 worker 自己弄停——那正是它要防的那种失败。
    """

    data_dir = os.environ.get("PAPER_EVIDENCE_DATA_DIR")
    if not data_dir:
        return
    path = Path(data_dir) / "worker.log"
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        handle = path.open("a", encoding="utf-8", errors="backslashreplace")
    except OSError as exc:
        print(f"worker: 无法写运行日志 {path}（{exc}）；继续以原有输出运行", file=sys.stderr)
        return
    sys.stdout = _Tee(sys.stdout, handle)
    sys.stderr = _Tee(sys.stderr, handle)


def main() -> int:
    # 第一件事：后面的任何失败都要留下痕迹。
    _mirror_output()
    try:
        return _run()
    except BaseException:
        # 解释器自带的回溯会走 sys.stderr（已被镜像），这里再显式落一次，
        # 免得 BaseException 的子类绕过默认钩子。
        traceback.print_exc()
        raise


def _run() -> int:
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
