"""Shared stand-ins for the performance dimension (测试方案「性能」).

A stand-in is needed because the two things under test here are *timing* and
*concurrency*, not the workflow's academic logic: the real workflow is exercised
in `tests/functional/`, and re-running it would only add upstream-shaped noise to
a latency measurement. The worker, the store, the claim path and the request
recorders are all the real ones.
"""

import asyncio
from dataclasses import replace

from paper_evidence.config import Settings
from paper_evidence.domain import TaskStatus
from paper_evidence.domain.contracts import RunConfigSnapshot
from paper_evidence.domain.records import TaskInput
from paper_evidence.domain.rules import criteria_reference

#: 读取时钟的模块。少写一个会让对应分支用真实时间，边界断言就失去意义，
#: 所以这里用 ``raising=True`` 的默认行为：模块挪走了就该立刻报错。
#:
#: 故意不含 ``models/sdk.py`` 与 ``models/gateway.py``：导入 sdk 会连带加载
#: LiteLLM，给每个用到时钟的用例加十几秒。这两条传输的时钟用法已由
#: `tests/tools/` 在真实时钟下覆盖；要用它们做边界断言时再把模块加进来。
CLOCK_MODULES = (
    "paper_evidence.worker.runner",
    "paper_evidence.graph.workflow",
    "paper_evidence.models.recording",
    "paper_evidence.sources.http",
)

WALL_EPOCH = 1_700_000_000.0
DEFAULT_START = 1_000.0


class VirtualClock:
    """A clock the test advances by hand; no test waits 45 real seconds."""

    def __init__(self, start: float = DEFAULT_START) -> None:
        self._monotonic = float(start)

    def monotonic(self) -> float:
        return self._monotonic

    def time(self) -> float:
        """Wall clock that moves with the monotonic one, so both agree."""

        return WALL_EPOCH + self._monotonic

    def advance(self, seconds: float) -> None:
        self._monotonic += float(seconds)


def settings_for(data_dir) -> Settings:
    """Settings that never reach the network and never touch the real data dir."""

    return replace(Settings.from_env(), data_dir=data_dir, contact_email="")


def enqueue(store, settings: Settings, task_id: str, *, claim: str = "论断",
            doi: str = "10.1000/perf") -> TaskInput:
    """Queue one task the way the API does, so the real claim path is exercised."""

    task = TaskInput(id=task_id, claim=claim, doi=doi, config_digest="perf",
                     authorized_recipients=("Agnes",))
    store.create(
        task,
        RunConfigSnapshot(
            profile="evaluation", config_digest="perf", snapshot_ref="perf",
            authorized_recipients=["Agnes"], limits=settings.limits,
            timeouts=settings.timeouts, observability=settings.observability,
        ),
        criteria_reference("rev"),
    )
    return task


class HarnessWorkflow:
    """A workflow stand-in: records its deadline and settles its own task.

    The real workflow owns its terminal write, so the stand-in does too; the
    worker may only bail a task out through its own failure path.
    """

    def __init__(self, harness: "WorkflowHarness", task: TaskInput) -> None:
        self._harness = harness
        self._task = task
        self.deadline: float | None = None
        self.entered = asyncio.Event()

    async def run(self, task, deadline):
        self.deadline = deadline
        self._harness.deadlines.append(deadline)
        self._harness.in_flight += 1
        self._harness.max_in_flight = max(self._harness.max_in_flight, self._harness.in_flight)
        self._harness.claims.append(task.id)
        if len(self._harness.claims) == 1:
            self._harness.first_claim.set()
        elif len(self._harness.claims) == 2:
            self._harness.second_claim.set()
        self.entered.set()
        try:
            if self._harness.gate is not None:
                await self._harness.gate.wait()
            if self._harness.body is not None:
                await self._harness.body(task, self._harness)
            self._harness.store.finish(
                task.id, status=TaskStatus.COMPLETED, stage="evidence_validation",
                error_code=None, label="支持", decision=None,
            )
        finally:
            self._harness.in_flight -= 1
        return self._harness.store.get(task.id)


class WorkflowHarness:
    """The worker's ``workflow_factory``: one stand-in per claim, with counters."""

    def __init__(self, store, *, gate=None, body=None) -> None:
        self.store = store
        self.gate = gate
        self.body = body
        self.workflows: list[HarnessWorkflow] = []
        self.claims: list[str] = []
        self.deadlines: list[float] = []
        self.in_flight = 0
        self.max_in_flight = 0
        self.first_claim = asyncio.Event()
        self.second_claim = asyncio.Event()

    def __call__(self, task) -> HarnessWorkflow:
        workflow = HarnessWorkflow(self, task)
        self.workflows.append(workflow)
        return workflow
