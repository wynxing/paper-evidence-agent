"""Local persistence boundary. SQLite/FTS5 is not implemented yet."""

from typing import Protocol

from paper_evidence.domain import TaskStatus
from paper_evidence.domain.contracts import CancelResponse, CheckDetail, CheckSummary, ConflictResponse
from paper_evidence.domain.records import TaskInput


class TaskRepository(Protocol):
    def create(self, task: TaskInput) -> None: ...

    def get(self, task_id: str) -> CheckDetail | None: ...

    def list(self, status: TaskStatus | None = None) -> list[CheckSummary]: ...

    def claim_next(self) -> TaskInput | None:
        """Atomically claim one queued task; None when none may be claimed.

        Returns None for three reasons: the queue is empty; a task is still
        RUNNING, so 「同一时刻只执行一个任务」 keeps this caller out (存储层不变量，
        见 Issue #34); or the conditional ``UPDATE`` moved no row, so this call did
        not actually claim anything. 前两种是运行中会遇到的，第三种在
        ``BEGIN IMMEDIATE`` 之下不可达，保留它使「返回的任务确实被本次调用领取了」
        成为存储层自己的保证（Issue #44 第 3.3 条）。实现只能返回它在本次调用中
        真正领取的任务。
        """
        ...

    def running_task(self) -> dict | None:
        """The RUNNING row that makes ``claim_next`` return None, if any.

        ``claim_next`` 的 None 分不出「队列为空」与「已有任务在 RUNNING」，调用方要
        如实报出停止原因（一次性 ``drain`` 不能把被挡住说成队列已空）就得读这一行。
        Returns ``{"id": …, "stage": …, "deadline_at": …}``，没有 RUNNING 行时返回
        ``None``（Issue #44 第 3.2 条）。
        """
        ...

    def request_cancel(self, task_id: str) -> CancelResponse | ConflictResponse | None:
        """Atomically record cancellation without replacing the whole detail.

        None when the task is missing. CancelResponse when cancellation is
        accepted or the task is already CANCELLED. ConflictResponse when
        another terminal state wins; the stored task stays unchanged.
        """
        ...

    def settle_orphaned_running(self) -> int:
        """Settle the leftover RUNNING tasks whose own time limit has passed.

        Only a row whose wall-clock deadline has already passed is settled: the
        task's own time limit says it has to stop. 「超过时限」不等于「持有进程已死」——
        停止检查是协作式的（只在阶段边界比较单调时钟），所以 deadline 过后持有者仍可能
        合法地处于 RUNNING 一小段时间；只有第二个 worker 才会在这段窗口里抢先把它记成
        INTERRUPTED（状态不会被写坏，但结束原因从超时变成中断，Issue #44 第 3.1 条）。
        A row without a deadline also counts, because the claim path always records
        one. A task another worker is still running within its deadline keeps its
        RUNNING row.

        A persisted cancel_requested becomes CANCELLED. Any other orphan becomes
        INTERRUPTED. Return how many tasks changed.
        """
        ...

    def save(self, result: CheckDetail) -> None:
        """Conditionally store a terminal result.

        Do not overwrite CANCELLED or another terminal state, including when
        cancellation was accepted after this result was prepared.
        """
        ...

    def delete(self, task_id: str) -> None: ...
