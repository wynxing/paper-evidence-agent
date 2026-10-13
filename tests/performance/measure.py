"""Read one task's performance record back out of the store.

测试方案「性能」要求「记录单任务延迟、逻辑请求数、上游尝试数及 token（缺失
标为未知）」。读数全部来自 ``store`` 已落库的行，不另建一份账：报告数字与用例
断言的数字因此不可能漂移。

不在真实上游下运行时，这里读到的只是**本机的一次运行**（构造/替身上游）。
它证明测量口径正确，不能当作性能结论——测试方案要求性能数字在真实上游下
测量才有意义。
"""

import time
from dataclasses import dataclass
from datetime import datetime

__all__ = ["TaskMeasurement", "TokenTotals", "measure", "measure_run"]


@dataclass(frozen=True)
class TokenTotals:
    """Per-task token sums; a field stays ``None`` when it is not fully observed.

    「缺失标为未知」按字段生效：只要有一条尝试没带 ``usage``，该字段就是未知，
    而不是一个偏小的数。``attempts_reporting``/``attempts_total`` 保留分母，
    让「未知」有据可查而不是只有一句 null。
    """

    prompt: int | None
    completion: int | None
    total: int | None
    attempts_reporting: int
    attempts_total: int

    @property
    def known(self) -> bool:
        return self.prompt is not None and self.completion is not None and self.total is not None


@dataclass(frozen=True)
class TaskMeasurement:
    task_id: str
    status: str
    #: 领取到结算的本机耗时，由调用方测量；没测就是 None，不写 0。
    latency_ms: float | None
    #: ``started_at`` 与 ``finished_at`` 之差；任一端缺失（例如仍在 QUEUED）即 None。
    persisted_ms: float | None
    logical_requests: int
    upstream_attempts: int
    observed_upstream_attempts: int
    tokens: TokenTotals


def measure(store, task_id: str, *, elapsed_seconds: float | None = None) -> TaskMeasurement:
    """Assemble the record for one task from its own rows."""

    detail = store.get(task_id)
    if detail is None:
        raise LookupError(f"没有任务 {task_id}")
    calls = store.model_calls(task_id)
    attempts = [attempt for call in calls for attempt in call.attempts]
    return TaskMeasurement(
        task_id=task_id,
        status=detail.status.value,
        latency_ms=None if elapsed_seconds is None else round(elapsed_seconds * 1000, 3),
        persisted_ms=_persisted_ms(detail),
        logical_requests=len(calls),
        upstream_attempts=len(attempts),
        observed_upstream_attempts=detail.accounting.observed_upstream_attempts,
        tokens=_tokens(attempts),
    )


def measure_run(store, task_id: str, run):
    """Time one claim-and-run call, then read the task's record back.

    ``run`` is a zero-argument callable (``functools.partial(worker.run_once)``
    or a ``drain`` call); its return value is passed through so a caller can
    still see whether a task was claimed.
    """

    started = time.monotonic()
    processed = run()
    return measure(store, task_id, elapsed_seconds=time.monotonic() - started), processed


def _persisted_ms(detail) -> float | None:
    if not detail.started_at or not detail.finished_at:
        return None
    started = datetime.fromisoformat(detail.started_at)
    finished = datetime.fromisoformat(detail.finished_at)
    return round((finished - started).total_seconds() * 1000, 3)


def _tokens(attempts) -> TokenTotals:
    reporting = [attempt for attempt in attempts if attempt.usage is not None]

    def summed(field: str) -> int | None:
        if not attempts or len(reporting) != len(attempts):
            return None
        values = [getattr(attempt.usage, field) for attempt in reporting]
        return None if any(value is None for value in values) else sum(values)

    return TokenTotals(
        prompt=summed("prompt_tokens"),
        completion=summed("completion_tokens"),
        total=summed("total_tokens"),
        attempts_reporting=len(reporting),
        attempts_total=len(attempts),
    )
