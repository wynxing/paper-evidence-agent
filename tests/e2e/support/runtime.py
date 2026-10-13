"""Shared settings for the end-to-end dimension's two Python processes.

来源端点没有环境变量可配（``Settings`` 里是字段默认值），所以两个进程都用
``dataclasses.replace`` 把五个来源地址指到本机替身。模型传输与观测接收方本身
有环境变量，直接由 `playwright.config.ts` 注入，不在这里重复。

两个进程必须拿到**完全一致**的 Settings：提交任务时 API 会把
``config_digest`` 与自己的快照比对（``api/app.py:403``），冻结快照里的
``timeouts`` 因此也属于被测配置的一部分，替身进程不能各配一套。

任务库的「空历史」起点由配置层保证——`playwright.config.ts` 每次运行都给一个
全新的数据目录。放在这里做「启动时删库」是不行的：Playwright 的四个
webServer 并发启动，worker 可能先一步打开 SQLite，后启动的进程再删就撞上
文件锁（实测 WinError 32）。
"""

import os
from dataclasses import replace
from pathlib import Path

from paper_evidence.config import Settings

__all__ = ["e2e_settings"]

#: 模型单次尝试的上限。默认值 45 秒是产品口径，这里调小只是为了让「上游超时」
#: 这类用例不用真的等 45 秒；两个进程用同一个值，快照仍自洽。
DEFAULT_ATTEMPT_SECONDS = "8"


def e2e_settings() -> Settings:
    base = Settings.from_env()
    stub = os.environ["PAPER_EVIDENCE_E2E_STUB_BASE"].rstrip("/")
    attempt_seconds = int(os.environ.get("PAPER_EVIDENCE_E2E_MODEL_ATTEMPT_SECONDS", DEFAULT_ATTEMPT_SECONDS))
    return replace(
        base,
        data_dir=Path(os.environ["PAPER_EVIDENCE_DATA_DIR"]),
        crossref_base_url=f"{stub}/crossref",
        doi_resolver_base_url=f"{stub}/doi",
        pmc_id_converter_url=f"{stub}/pmc/idconv",
        pmc_oai_url=f"{stub}/pmc/oai",
        openalex_base_url=f"{stub}/openalex",
        timeouts=base.timeouts.model_copy(update={"model_attempt_seconds": attempt_seconds}),
    )
