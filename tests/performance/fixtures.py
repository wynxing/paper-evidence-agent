"""性能维度夹具（测试方案「性能」）。

被测模块是 `worker/`：**单进程、一次一个任务**。总时限自任务被领取并转为
RUNNING 起算，含解析与重试等待、不含队列时间。

判定要走 45 秒模型尝试、15 秒来源请求、180 秒总执行时限三档边界，真实等待
不可行，所以时间交给 :class:`harness.VirtualClock`。它只替换
``harness.CLOCK_MODULES`` 里各模块命名空间中的 ``time`` 引用，不改动
`backend/paper_evidence/` 的任何行为（Issue #26 第 3 条：如需为可测性调整实现，
要先在 PR 里说明方案与影响面）。

本目录不引入 Redis / Locust / JMeter，也不做分布式压测；数据目录固定在
``tmp_path``，不碰 ``backend/.paper-evidence``。

为什么夹具不放在 ``conftest.py``
--------------------------------

本目录沿用与 ``tests/functional``、``tests/adversarial`` 相同的约定：夹具放在
普通模块（本文件）里，由用例文件显式导入，不用 ``from conftest import ...``
这种按 ``sys.path`` 顺序解析的裸导入。根因见 Issue #31——各维度已改为「维度
独有的模块名 + 显式导入」，因此现在再往 ``tests/`` 下加 ``conftest.py`` 不会
再串目录；本目录保留 ``fixtures.py`` 只是与既有约定保持一致。
"""

import importlib

import pytest

from harness import CLOCK_MODULES, VirtualClock, settings_for
from paper_evidence.storage.sqlite import SqliteStore


@pytest.fixture
def clock(monkeypatch):
    """Install one virtual clock into every module that reads the time."""

    virtual = VirtualClock()
    for name in CLOCK_MODULES:
        module = importlib.import_module(name)
        monkeypatch.setattr(module, "time", virtual)
    return virtual


@pytest.fixture
def settings(tmp_path):
    return settings_for(tmp_path)


@pytest.fixture
def store(tmp_path):
    handle = SqliteStore(tmp_path / "performance.sqlite3")
    yield handle
    handle.close()
