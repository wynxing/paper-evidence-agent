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

为什么不叫 ``conftest.py``
--------------------------

``tests/adversarial``、``tests/functional`` 与 ``tests/conftest.py`` 里的用例都写
``from conftest import ...``，靠的是「同目录的 conftest 恰好是 sys.path 上第一个
``conftest``」。再添一个 ``conftest.py`` 会把这个顺序顶掉，让它们的裸导入拿到
别的目录的 conftest（实测会让 `tests/functional` 的 8 条用例 ImportError）。
所以这里用普通模块名，由各用例文件显式导入夹具；根因见 Issue #31。
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
