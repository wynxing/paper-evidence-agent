"""Serve the real API over the stubbed sources.

前端 dev server 的代理把 ``/api`` 固定发到 ``127.0.0.1:8000``
（`frontend/vite.config.ts:6`），所以这个端口不是自由参数。
"""

import os
import sys
from pathlib import Path

import uvicorn

sys.path.insert(0, str(Path(__file__).resolve().parent))

from runtime import e2e_settings  # noqa: E402

from paper_evidence.api.app import app  # noqa: E402
from paper_evidence.api.deps import Services, set_services  # noqa: E402


def main() -> int:
    settings = e2e_settings()
    # 数据目录由配置层每次运行新建，这里不再删库；容器先装好，避免第一个请求
    # 各建一份：store、HTTP 客户端与模型网关都按替身地址构造。
    set_services(Services(settings))
    uvicorn.run(app, host="127.0.0.1", port=int(os.environ.get("PAPER_EVIDENCE_E2E_BACKEND_PORT", "8000")),
                log_level="warning")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
