"""Bounded verification workflow.

This module implements the ``VerificationWorkflow`` port as an explicit bounded
state machine over the packages in 架构设计「代码布局」. The per-step check order
follows 架构设计「动作与预算」: cancel and remaining deadline first, then response
structure and per-step action legality, then remaining budget, and only then
dispatch.

Integration note: the design selects LangGraph for this orchestration (D5). This
implementation keeps the same bounded nodes and terminal exits as an explicit
state machine because LangGraph is not part of the locked dependency closure; the
node boundaries map one-to-one onto the methods below, so a later migration is
mechanical. This deviation is recorded in the PR.
"""

import asyncio
import contextlib
import time
from dataclasses import dataclass

from paper_evidence.agents.output import (
    DecisionDraft,
    FinalAction,
    OutputError,
    RetrieveAction,
    parse_decision_output,
    parse_query_output,
)
from paper_evidence.domain import ContractError, ErrorCode, ResultLabel, Stage, TaskStatus
from paper_evidence.domain.contracts import Decision, Evidence, EvidenceCandidate, SourceRecord
from paper_evidence.domain.records import Paragraph, TaskInput
from paper_evidence.domain.rules import (
    DEFINITIVE_LABELS,
    FRONT_MATTER_BLOCK_CODE,
    RETRIEVAL_FRONT_MATTER,
    BudgetState,
    blocked_label,
    terminal_status,
)
from paper_evidence.domain.text import quote_spans
from paper_evidence.graph.support import StageRecorder
from paper_evidence.models.gateway import ModelFailure
from paper_evidence.models.recording import AttemptCancelled
from paper_evidence.retrieval.jats import parse_jats

__all__ = ["BoundedWorkflow", "QuoteError"]

#: How often an in-flight upstream wait re-reads the persisted cancel flag.
#:
#: 取消只在阶段边界检查时，一次 45 秒的模型调用会把「受理后 2 秒内收尾释放
#: worker」拖成 45 秒（测试方案「性能」）。轮询而不是订阅，是因为取消标记落在
#: SQLite 里、由另一个进程的 API 写入；0.2 秒既远小于 2 秒的预算，也不至于让
#: 本地库每秒被打几百次。
CANCEL_POLL_SECONDS = 0.2


class QuoteError(ValueError):
    """A published quote could not be located in the frozen paragraph text."""


class _Cancelled(Exception):
    """An accepted cancel stops local work; it is not an academic result.

    ``call`` carries the attempt record of a model request that was already on the
    wire when the cancel landed, so the workflow can still put that dispatch in the
    ledger before settling the task as CANCELLED.
    """

    def __init__(self, call=None) -> None:
        super().__init__("cancel accepted")
        self.call = call


@dataclass
class _Outcome:
    decision: Decision
    error_code: ErrorCode | None
    stage: Stage


class BoundedWorkflow:
    def __init__(self, *, store, resolver, fulltext, retriever, prompts, gateway, settings, tracing=None) -> None:
        self._store = store
        self._resolver = resolver
        self._fulltext = fulltext
        self._retriever = retriever
        self._prompts = prompts
        self._gateway = gateway
        self._settings = settings
        # Optional span sink (``tracing/otel.py``). ``None`` means local-only.
        self._tracing = tracing

    # ------------------------------------------------------------------ utils

    async def _db(self, fn, *args, **kwargs):
        if kwargs:
            return await asyncio.to_thread(lambda: fn(*args, **kwargs))
        return await asyncio.to_thread(fn, *args)

    def _check_stop(self, deadline: float) -> None:
        if time.monotonic() > deadline:
            raise ContractError(ErrorCode.TASK_TIMEOUT, "任务超过总执行时限")

    async def _check_cancel(self, task_id: str) -> None:
        if await self._db(self._store.cancel_accepted, task_id):
            raise _Cancelled

    async def _await_upstream(self, task_id: str, awaitable):
        """Await one upstream step, aborting it if a cancel is accepted meanwhile.

        Stage boundaries alone do not bound the drain: a click during a 45-second
        model attempt or a 15-second source request would only be noticed when that
        await returned, and 测试方案「性能」 requires the worker to be released within
        2 seconds of accepting a cancel. So the persisted flag is polled while the
        step runs, and an accepted cancel cancels the in-flight dispatch. A
        transport that already sent the request reports it as an ``AttemptCancelled``
        carrying the attempt row, which the caller stores: the abort is fast, not
        amnesiac (测试方案「取消」: 保留已发生费用未知的说明).
        """

        inner = asyncio.ensure_future(awaitable)
        try:
            while True:
                done, _pending = await asyncio.wait({inner}, timeout=CANCEL_POLL_SECONDS)
                if done:
                    return inner.result()
                if await self._db(self._store.cancel_accepted, task_id):
                    raise _Cancelled(await self._abort_upstream(inner))
        except BaseException:
            # A dispatch must never outlive the task it belongs to: a late response
            # would try to write to a settled row and reopen the ledger.
            if not inner.done():
                inner.cancel()
                with contextlib.suppress(BaseException):
                    await inner
            raise

    async def _abort_upstream(self, inner):
        """Cancel the in-flight dispatch; return the attempt record it carried."""

        inner.cancel()
        try:
            await inner
        except AttemptCancelled as aborted:
            return aborted.call
        except BaseException:  # a transport without the abort path records nothing
            return None
        return None

    # -------------------------------------------------------------------- run

    async def run(self, task: TaskInput, deadline: float) -> "CheckDetail":  # noqa: F821
        recorder = StageRecorder(self._store, task.id, self._db, sink=self._tracing)
        budget = BudgetState(limits=self._settings.limits)
        if self._tracing is not None:
            self._tracing.begin(task)
        try:
            await self._check_cancel(task.id)
            source_id, preview = await self._prepare_source(task, deadline, recorder)
            outcome = await self._verify(task, deadline, recorder, budget, source_id, preview)
            return await self._complete(task, recorder, outcome)
        except _Cancelled:
            return await self._cancel(task, recorder, recorder.stage or Stage.WAIT)
        except ContractError as error:
            return await self._terminal(task, recorder, error.error_code, recorder.stage or Stage.WAIT)
        finally:
            # Close the trace on every exit path, including the ones that return a
            # blocked or cancelled result; otherwise the root span outlives the task.
            if self._tracing is not None:
                self._tracing.finish(task.id)

    # ------------------------------------------------------------- source prep

    async def _prepare_source(self, task, deadline, recorder):
        self._check_stop(deadline)
        # The task deadline reaches the source connectors too (架构「取消与截止时间」).
        preview = await self._stage(task.id, recorder, Stage.SOURCE_IDENTITY, "source_resolver",
                                    self._resolver.resolve(task.doi, deadline))
        snapshot = await self._stage(task.id, recorder, Stage.FETCH, "full_text_source",
                                     self._fulltext.fetch(task.doi, deadline))
        paragraphs = parse_jats(snapshot)
        await self._db(self._store.link_task_source, task.id, snapshot.source_id)
        await self._db(self._store.index_source, snapshot.source_id, snapshot.metadata, snapshot.jats_bytes,
                       snapshot.open_locations)
        await self._db(self._store.update_source, task.id, snapshot.metadata)
        await self._db(self._store.index_paragraphs, snapshot.source_id, paragraphs)
        # Freeze first, refuse to judge second: the frontend shows the retrieval form
        # of a blocked task, which requires the source row to exist (Issue #92).
        await self._refuse_front_matter(recorder, snapshot.metadata)
        return snapshot.source_id, preview

    async def _stage(self, task_id: str, recorder, stage: Stage, tool: str, coro):
        await recorder.enter(stage, tool)
        started = time.monotonic()
        try:
            result = await self._await_upstream(task_id, coro)
        except _Cancelled:
            await recorder.cancelled(stage, tool, started)
            raise
        except ContractError as error:
            await recorder.fail(stage, tool, error.error_code, started)
            raise
        await recorder.ok(stage, tool, started)
        return result

    async def _refuse_front_matter(self, recorder, source: SourceRecord) -> None:
        """A front-matter-only record blocks instead of being judged (Issue #28).

        PMC answers ``cannotDisseminateFormat`` for records outside its Open Access
        subset and the connector then falls back to ``pmc_fm``, which carries title,
        abstract and licence but **no ``<body>``**. Judging on that abstract is the
        negative example 产品需求 forbids ("用摘要代替全文来声称全文没有相关证据"),
        and an abstract's silence is not the article's silence. So the task stops
        here: ``BLOCKED`` with ``CONTENT_INCOMPLETE``, no model call, no label.

        The gate runs *after* the source is frozen on purpose: the frozen row keeps
        the ``retrieval_form`` that says why the task stopped, and the detail view
        renders「仅题录+摘要」from it instead of guessing from sections.
        """

        if source.retrieval_form != RETRIEVAL_FRONT_MATTER:
            return
        started = time.monotonic()
        await recorder.fail(Stage.FETCH, "retrieval_form_gate", FRONT_MATTER_BLOCK_CODE, started)
        raise ContractError(FRONT_MATTER_BLOCK_CODE, "来源只返回题录与摘要，没有正文，按规则不做判定")

    # ------------------------------------------------------------------ verify

    async def _verify(self, task, deadline, recorder, budget, source_id, preview) -> _Outcome:
        claim = task.claim
        queries = await self._generate_queries(task, deadline, recorder, budget, preview)
        round0 = await self._search(task, deadline, recorder, source_id, queries, 0)
        await self._record_candidates(task.id, 0, round0)

        decision = await self._decide(task, deadline, recorder, budget, claim, round0, round_index=0,
                                      final_only=False)
        if not round0 and not _requests_supplement(decision):
            # The first empty retrieval must request a supplemental *query*: a
            # neighbour read cannot answer an empty round (架构「动作与预算」).
            decision = await self._repair_action(
                task, deadline, recorder, budget, claim, [], round_index=0, final_only=False,
                note="首次检索为空时只能输出 action=retrieve 并提供至少一个非空 queries。",
            )
            if not _requests_supplement(decision):
                raise ContractError(ErrorCode.MODEL_INVALID_OUTPUT, "首次检索为空时未申请补充查询")

        context = list(round0)
        # The round the published decision came from. Quote validation repairs the
        # decision it just checked, so its record has to name that round: a first
        # round that goes straight to ``final`` is round 0, and only a decision
        # taken after a supplemental round is round 1 (Issue #70).
        decision_round = 0
        if isinstance(decision, RetrieveAction):
            if not budget.can_dispatch_supplemental():
                raise ContractError(ErrorCode.BUDGET_EXCEEDED, "补充检索额度已用尽")
            budget.take_supplemental()
            await self._db(self._store.take_request, task.id, "supplemental_rounds_used")
            round1 = await self._search(task, deadline, recorder, source_id, decision.queries, 1,
                                        neighbor_ids=decision.neighbor_paragraph_ids)
            await self._record_candidates(task.id, 1, round1)
            merged = _dedupe([*round0, *round1])
            if not merged:
                return self._insufficient()
            context = merged
            decision = await self._decide(task, deadline, recorder, budget, claim, merged, round_index=1,
                                          final_only=True)
            decision_round = 1
            if isinstance(decision, RetrieveAction):
                # Request 3 may only final; repair into a final using existing material.
                decision = await self._repair_action(
                    task, deadline, recorder, budget, claim, merged, round_index=1, final_only=True,
                    note="本轮只能输出 action=final，不得再申请补读。",
                )

        if not isinstance(decision, FinalAction):
            # Explicit instead of assert: this must survive ``python -O``.
            raise ContractError(ErrorCode.MODEL_INVALID_OUTPUT, "请求未提交最终判断")
        published = await self._validate(task, deadline, recorder, budget, source_id, decision.decision,
                                         context, round_index=decision_round)
        return _Outcome(decision=published, error_code=None, stage=Stage.EVIDENCE_VALIDATION)

    # ---------------------------------------------------------------- requests

    async def _generate_queries(self, task, deadline, recorder, budget, preview) -> list[str]:
        prompt = self._prompts.query_generation(task.claim, preview)
        text = await self._main_request(task, deadline, recorder, budget, stage=Stage.QUERY_GENERATION,
                                        purpose="query_generation", prompt=prompt, round_index=0, context=[])
        try:
            return parse_query_output(text)
        except OutputError as error:
            text = await self._repair_request(task, deadline, recorder, budget, stage=Stage.QUERY_GENERATION,
                                              prompt=prompt, round_index=0,
                                              context=[], note=str(error),
                                              repairs_request_id=f"{task.id}:query_generation:0")
            try:
                return parse_query_output(text)
            except OutputError:
                raise ContractError(ErrorCode.MODEL_INVALID_OUTPUT, "queries 结构不合法")

    async def _decide(self, task, deadline, recorder, budget, claim, candidates, *, round_index, final_only):
        prompt = self._prompts.decision(claim, candidates, final_only=final_only)
        context = [item.paragraph_id for item in candidates]
        text = await self._main_request(task, deadline, recorder, budget, stage=Stage.DECISION, purpose="decision",
                                        prompt=prompt, round_index=round_index, context=context)
        try:
            return parse_decision_output(text)
        except OutputError as error:
            text = await self._repair_request(task, deadline, recorder, budget, stage=Stage.DECISION,
                                              prompt=prompt, round_index=round_index,
                                              context=context, note=str(error),
                                              repairs_request_id=f"{task.id}:decision:{round_index}")
            try:
                return parse_decision_output(text)
            except OutputError:
                raise ContractError(ErrorCode.MODEL_INVALID_OUTPUT, "判断输出结构不合法")

    async def _repair_action(self, task, deadline, recorder, budget, claim, candidates, *, round_index,
                             final_only, note, stage=Stage.OUTPUT_REPAIR,
                             unparsable_code=ErrorCode.MODEL_INVALID_OUTPUT,
                             exhausted_code=ErrorCode.MODEL_INVALID_OUTPUT):
        """Repair a decision response once; never return an unparsed action.

        A structurally unusable repair output and an exhausted repair budget are
        both terminal here, so callers see a typed ContractError instead of a
        ``None`` or a bare assert. ``exhausted_code`` lets the quote-validation
        caller report QUOTE_MISMATCH while every other caller stays
        MODEL_INVALID_OUTPUT.
        """

        prompt = self._prompts.decision(claim, candidates, final_only=final_only)
        text = await self._repair_request(
            task, deadline, recorder, budget, stage=stage, prompt=prompt,
            round_index=round_index, context=[item.paragraph_id for item in candidates], note=note,
            repairs_request_id=f"{task.id}:decision:{round_index}", exhausted_code=exhausted_code,
        )
        try:
            return parse_decision_output(text)
        except OutputError as error:
            raise ContractError(unparsable_code, "修复后输出仍不合法") from error

    async def _main_request(self, task, deadline, recorder, budget, *, stage, purpose, prompt, round_index,
                            context) -> str:
        await self._check_cancel(task.id)
        self._check_stop(deadline)
        if not budget.can_dispatch_main():
            raise ContractError(ErrorCode.BUDGET_EXCEEDED, "主请求额度已用尽")
        budget.take_main()
        await self._db(self._store.take_request, task.id, "main_requests_used")
        request_id = f"{task.id}:{purpose}:{round_index}"
        return await self._invoke(task, deadline, recorder, stage=stage, purpose=purpose, prompt=prompt,
                                  round_index=round_index, context=context, request_id=request_id,
                                  repairs_request_id=None)

    async def _repair_request(self, task, deadline, recorder, budget, *, stage, prompt, round_index,
                              context, note, repairs_request_id,
                              exhausted_code=ErrorCode.MODEL_INVALID_OUTPUT) -> str:
        await self._check_cancel(task.id)
        self._check_stop(deadline)
        if not budget.can_dispatch_repair():
            # The caller owns which code describes the still-unfixed defect:
            # a quote failure that ran out of repairs is QUOTE_MISMATCH, not a
            # structural failure (术语表「4. 错误码」).
            raise ContractError(exhausted_code, "输出修复额度已用尽")
        budget.take_repair()
        await self._db(self._store.take_request, task.id, "repair_requests_used")
        # The discriminator is this repair's own ordinal in the task, not the round
        # of the request it repairs. One (purpose, round) slot can legitimately be
        # repaired twice — an unparsable decision, then the quote check of the
        # repaired one — so a round-based id would repeat, and ``request_id`` is the
        # ledger's primary key (Issue #70). The round of the repaired request stays
        # in ``round`` next to ``repairs_request_id``, so nothing is lost.
        #
        # A repair always records ``purpose="output_repair"``: the purpose names the
        # step this request performs, not the response it replaces (术语表「阶段标识」).
        request_id = f"{task.id}:output_repair:{budget.repair_requests_used}"
        return await self._invoke(
            task, deadline, recorder, stage=Stage.OUTPUT_REPAIR, purpose="output_repair",
            prompt=f"{prompt}\n\n上一轮输出不合法：{note}\n请只输出修正后的 JSON，不要解释。",
            round_index=round_index, context=context, request_id=request_id,
            repairs_request_id=repairs_request_id,
        )

    async def _invoke(self, task, deadline, recorder, *, stage, purpose, prompt, round_index, context,
                      request_id, repairs_request_id) -> str:
        await recorder.enter(stage, "model_gateway")
        started = time.monotonic()
        try:
            reply = await self._await_upstream(task.id, self._gateway.complete(
                request_id, prompt, deadline, purpose=purpose, round_index=round_index,
                prompt_version=self._prompts.version, context_paragraph_ids=list(context),
                repairs_request_id=repairs_request_id,
            ))
        except _Cancelled as stopped:
            # The request was already dispatched. Its attempt row says「cancelled,
            # usage unknown」, so the cancel is quick without hiding the spend.
            if stopped.call is not None:
                await self._db(self._store.record_model_call, task.id, stopped.call)
            await recorder.cancelled(stage, "model_gateway", started,
                                     round_index=round_index, request_id=request_id)
            raise
        except ModelFailure as failure:
            # The gateway builds the call record for both outcomes, so a failed
            # attempt keeps the same params_digest as a successful one.
            await self._db(self._store.record_model_call, task.id, failure.call)
            await recorder.fail(stage, "model_gateway", failure.error_code, started,
                                round_index=round_index, request_id=request_id)
            raise ContractError(failure.error_code, "模型上游失败") from failure
        if not reply.call.attempts:
            # 派发发生了，控制面却没有回报这一次的上游尝试：既不知道单价，也不知道
            # 它到底发出去几次。这不是「逐次元数据缺失」（那种记录在、usage 为空，
            # 结果可以保留并标 unverified），继续派发等于在无法计数的通道上花钱，
            # 所以停在这里（测试方案「边界与异常」, Issue #113）。
            await self._db(self._store.record_model_call, task.id, reply.call)
            await recorder.fail(stage, "model_gateway", ErrorCode.UPSTREAM_UNAVAILABLE, started,
                                round_index=round_index, request_id=request_id)
            raise ContractError(ErrorCode.UPSTREAM_UNAVAILABLE, "模型网关未回报本次派发，停止后续调用")
        await self._db(self._store.record_model_call, task.id, reply.call)
        await recorder.ok(stage, "model_gateway", started, round_index=round_index, request_id=request_id)
        return reply.text

    async def _search(self, task, deadline, recorder, source_id, queries, round_index, neighbor_ids=None):
        await self._check_cancel(task.id)
        self._check_stop(deadline)
        await recorder.enter(Stage.RETRIEVAL, "fts5")
        started = time.monotonic()
        terms = [item for item in queries if item.strip()]
        try:
            # A neighbour-only retrieve is legal: skip MATCH instead of asking
            # FTS5 to compile an empty expression.
            results = await self._db(self._retriever.search, source_id, terms) if terms else []
            if neighbor_ids:
                neighbors = await self._db(self._retriever.read_neighbors, source_id, list(neighbor_ids))
                results = _dedupe([*results, *neighbors])
        except ContractError as error:
            await recorder.fail(Stage.RETRIEVAL, "fts5", error.error_code, started, round_index=round_index)
            raise
        await recorder.ok(Stage.RETRIEVAL, "fts5", started, round_index=round_index)
        return results

    async def _record_candidates(self, task_id, round_index, paragraphs):
        candidates = [
            EvidenceCandidate(
                paragraph_id=item.paragraph_id, section=item.section, quote=item.text,
                paragraph_hash=item.paragraph_hash, source_url=item.source_url,
                round=round_index, rank=rank, entered_context=True,
            )
            for rank, item in enumerate(paragraphs, start=1)
        ]
        if candidates:
            await self._db(self._store.record_candidates, task_id, candidates)

    # -------------------------------------------------------------- validation

    async def _validate(self, task, deadline, recorder, budget, source_id, draft: DecisionDraft, context,
                        *, round_index):
        await recorder.enter(Stage.EVIDENCE_VALIDATION, "quote_check")
        started = time.monotonic()
        allowed = {item.paragraph_id for item in context}
        try:
            published = await self._build_decision(source_id, draft, allowed)
        except QuoteError as error:
            await recorder.fail(Stage.EVIDENCE_VALIDATION, "quote_check", ErrorCode.QUOTE_MISMATCH, started)
            # The repair takes the round of the decision it repairs, so its record
            # points back at a request that really exists: ``{task}:decision:{round}``.
            # A task whose first round went straight to ``final`` only ever dispatched
            # ``{task}:decision:0``, so recording this repair as round 1 named a
            # request that was never made (Issue #70).
            repaired = await self._repair_action(
                task, deadline, recorder, budget, task.claim, context, round_index=round_index,
                final_only=True, note=str(error), stage=Stage.EVIDENCE_VALIDATION,
                exhausted_code=ErrorCode.QUOTE_MISMATCH,
            )
            if not isinstance(repaired, FinalAction):
                raise ContractError(ErrorCode.MODEL_INVALID_OUTPUT, "修复后输出不是最终判断")
            try:
                published = await self._build_decision(source_id, repaired.decision, allowed)
            except QuoteError:
                raise ContractError(ErrorCode.QUOTE_MISMATCH, "摘录校验失败")
        await recorder.ok(Stage.EVIDENCE_VALIDATION, "quote_check", started)
        return published

    async def _build_decision(self, source_id: str, draft: DecisionDraft, allowed_ids: set[str]) -> Decision:
        if draft.label in DEFINITIVE_LABELS and not draft.evidence:
            # A definitive label without a locatable quote would be published as
            # COMPLETED + validation=pass, which 术语表「5. 证据门槛」 forbids.
            raise QuoteError(f"确定判断「{draft.label}」必须至少给出一条可逐字定位的摘录")
        evidence: list[Evidence] = []
        for item in draft.evidence:
            if item.paragraph_id not in allowed_ids:
                # Only paragraphs that entered this decision's context may back it,
                # and the id has to match one of them exactly.
                raise QuoteError(_candidate_id_note(item.paragraph_id, allowed_ids))
            paragraph = await self._db(self._store.read_paragraph, source_id, item.paragraph_id)
            if paragraph is None:
                raise QuoteError(f"未知段落 {item.paragraph_id}")
            if not quote_spans(paragraph.text, item.quote):
                raise QuoteError(
                    f"段落 {item.paragraph_id} 中没有这段逐字摘录；"
                    "quote 必须是该候选段落中的逐字精确子串"
                )
            evidence.append(
                Evidence(
                    paragraph_id=paragraph.paragraph_id, quote=item.quote, section=paragraph.section,
                    source_url=paragraph.source_url, paragraph_hash=paragraph.paragraph_hash, validation="pass",
                )
            )
        return Decision(
            agent="paper", label=draft.label, rationale=draft.rationale,
            supported_parts=list(draft.supported_parts), scope_differences=list(draft.scope_differences),
            limitations=list(draft.limitations), evidence=evidence, validation="pass",
        )

    # ---------------------------------------------------------------- terminals

    def _insufficient(self) -> _Outcome:
        return _Outcome(
            decision=Decision(
                agent="paper", label=ResultLabel.INSUFFICIENT_EVIDENCE,
                rationale="完成允许的补充检索后仍无候选片段。",
                supported_parts=[], scope_differences=[],
                limitations=["本次未获得足够证据；这是本次有界检索的结果，不代表该文献绝对没有证据。"],
                evidence=[], validation="pass",
            ),
            error_code=ErrorCode.RETRIEVAL_EMPTY,
            stage=Stage.EVIDENCE_VALIDATION,
        )

    async def _complete(self, task, recorder, outcome: _Outcome):
        # A cancel accepted while the final model call was in flight wins over
        # the result (测试方案「取消先于完成」, FR-4). This pre-check narrows the
        # window; the conditional write in finish() closes it atomically.
        if await self._db(self._store.cancel_accepted, task.id):
            return await self._cancel(task, recorder, recorder.stage or Stage.WAIT)
        written = await self._finish(task, TaskStatus.COMPLETED, outcome.stage, outcome.error_code,
                                     outcome.decision.label, outcome.decision)
        if not written:
            return await self._after_refused_write(task, recorder)
        return await self._db(self._store.get, task.id)

    async def _terminal(self, task, recorder, error_code, stage: Stage):
        status = terminal_status(error_code)
        label = blocked_label() if status is TaskStatus.BLOCKED else None
        # A non-CANCELLED terminal never overrides an accepted cancel; the
        # cancel is not an academic result, so it takes precedence over both a
        # completion and a failure that raced it.
        if await self._db(self._store.cancel_accepted, task.id):
            return await self._cancel(task, recorder, stage)
        written = await self._finish(task, status, stage, error_code, label, None)
        if not written:
            return await self._after_refused_write(task, recorder)
        return await self._db(self._store.get, task.id)

    async def _after_refused_write(self, task, recorder):
        """Reconcile a refused terminal write.

        ``finish`` refuses either because another writer already committed a
        terminal state, or because the cancel was accepted on this task. In the
        latter case the cancel must win, so the stored RUNNING + cancel_requested
        row is settled as CANCELLED instead of being reread as a live task.
        """

        if await self._db(self._store.cancel_accepted, task.id):
            return await self._cancel(task, recorder, recorder.stage or Stage.WAIT)
        return await self._db(self._store.get, task.id)

    async def _cancel(self, task, recorder, stage: Stage):
        stored = await self._db(self._store.get, task.id)
        if stored is not None and stored.status is TaskStatus.CANCELLED:
            return stored
        await self._finish(task, TaskStatus.CANCELLED, stage, None, None, None)
        return await self._db(self._store.get, task.id)

    async def _finish(self, task, status, stage, error_code, label, decision) -> bool:
        """Write a terminal state; ``False`` means the guard refused the write."""

        return await self._db(
            self._store.finish, task.id, status=status, stage=stage.value, error_code=error_code,
            label=label,
            decision=decision.model_dump(mode="json") if decision is not None else None,
        )


def _dedupe(paragraphs):
    seen: dict[str, Paragraph] = {}
    for paragraph in paragraphs:
        seen.setdefault(paragraph.paragraph_id, paragraph)
    return list(seen.values())


def _candidate_id_note(submitted: str, allowed_ids: set[str]) -> str:
    """Explain an evidence id that is not one of this decision's candidate ids.

    The check itself is unchanged: an id has to be exactly one of the ids that
    entered this decision's context (术语表「文本与定位契约」). Only the one repair
    request's input changes. The observed failure (Issue #74) is a faithful copy
    that lost the leading ``p:`` of the id the prompt renders inside square
    brackets; when the submitted id is recoverable from a candidate, the note
    names the candidate instead of only saying the paragraph never entered the
    context — that sentence left the model with no way to tell which id it meant.
    """

    for recovered, reason in (
        (f"p:{submitted}", "漏掉了开头的 p: 前缀"),
        (submitted.strip("[]"), "把候选片段里的方括号一起写了进去"),
    ):
        if recovered != submitted and recovered in allowed_ids:
            return (f"段落 ID「{submitted}」与候选片段里的 ID 不一致（{reason}）："
                    f"候选片段里是「{recovered}」，必须原样照抄")
    return (f"段落 ID「{submitted}」不在本次判断的候选片段里；"
            "evidence 的 paragraph_id 必须原样照抄候选片段行首方括号内的 ID，"
            "连开头的 p: 一起复制，不要带方括号")


def _requests_supplement(decision) -> bool:
    """True when the response is a retrieve that actually asks for new material.

    An empty first round additionally requires non-empty queries, because a
    neighbour read alone cannot answer it (架构设计「动作与预算」).
    """

    return isinstance(decision, RetrieveAction) and any(item.strip() for item in decision.queries)
