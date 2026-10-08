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
from paper_evidence.domain.contracts import Decision, Evidence, EvidenceCandidate, ModelCall
from paper_evidence.domain.records import Paragraph, TaskInput
from paper_evidence.domain.rules import BudgetState, blocked_label, terminal_status
from paper_evidence.domain.text import quote_spans
from paper_evidence.graph.support import StageRecorder
from paper_evidence.models.gateway import ModelFailure
from paper_evidence.retrieval.jats import parse_jats

__all__ = ["BoundedWorkflow", "QuoteError"]


class QuoteError(ValueError):
    """A published quote could not be located in the frozen paragraph text."""


class _Cancelled(Exception):
    """An accepted cancel stops local work; it is not an academic result."""


@dataclass
class _Outcome:
    decision: Decision
    error_code: ErrorCode | None
    stage: Stage


class BoundedWorkflow:
    def __init__(self, *, store, resolver, fulltext, retriever, prompts, gateway, settings) -> None:
        self._store = store
        self._resolver = resolver
        self._fulltext = fulltext
        self._retriever = retriever
        self._prompts = prompts
        self._gateway = gateway
        self._settings = settings

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

    # -------------------------------------------------------------------- run

    async def run(self, task: TaskInput, deadline: float) -> "CheckDetail":  # noqa: F821
        recorder = StageRecorder(self._store, task.id, self._db)
        budget = BudgetState(limits=self._settings.limits)
        try:
            await self._check_cancel(task.id)
            source_id, preview = await self._prepare_source(task, deadline, recorder)
            outcome = await self._verify(task, deadline, recorder, budget, source_id, preview)
            return await self._complete(task, recorder, outcome)
        except _Cancelled:
            return await self._cancel(task, recorder, recorder.stage or Stage.WAIT)
        except ContractError as error:
            return await self._terminal(task, recorder, error.error_code, recorder.stage or Stage.WAIT)

    # ------------------------------------------------------------- source prep

    async def _prepare_source(self, task, deadline, recorder):
        self._check_stop(deadline)
        preview = await self._stage(recorder, Stage.SOURCE_IDENTITY, "source_resolver",
                                    self._resolver.resolve(task.doi))
        snapshot = await self._stage(recorder, Stage.FETCH, "full_text_source",
                                     self._fulltext.fetch(task.doi, deadline))
        paragraphs = parse_jats(snapshot)
        await self._db(self._store.link_task_source, task.id, snapshot.source_id)
        await self._db(self._store.index_source, snapshot.source_id, snapshot.metadata, snapshot.jats_bytes)
        await self._db(self._store.update_source, task.id, snapshot.metadata)
        await self._db(self._store.index_paragraphs, snapshot.source_id, paragraphs)
        return snapshot.source_id, preview

    async def _stage(self, recorder, stage: Stage, tool: str, coro):
        await recorder.enter(stage, tool)
        started = time.monotonic()
        try:
            result = await coro
        except ContractError as error:
            await recorder.fail(stage, tool, error.error_code, started)
            raise
        await recorder.ok(stage, tool, started)
        return result

    # ------------------------------------------------------------------ verify

    async def _verify(self, task, deadline, recorder, budget, source_id, preview) -> _Outcome:
        claim = task.claim
        queries = await self._generate_queries(task, deadline, recorder, budget, preview)
        round0 = await self._search(task, deadline, recorder, source_id, queries, 0)
        await self._record_candidates(task.id, 0, round0)

        decision = await self._decide(task, deadline, recorder, budget, claim, round0, round_index=0,
                                      final_only=False)
        if not round0 and isinstance(decision, FinalAction):
            # The first empty retrieval must request a supplemental query.
            decision = await self._repair_action(
                task, deadline, recorder, budget, claim, [], round_index=0, final_only=False,
                note="首次检索为空时必须输出 action=retrieve 申请补充查询。",
            )
            if isinstance(decision, FinalAction):
                raise ContractError(ErrorCode.MODEL_INVALID_OUTPUT, "首次检索为空仍输出 final")

        context = list(round0)
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
            if isinstance(decision, RetrieveAction):
                # Request 3 may only final; repair into a final using existing material.
                decision = await self._repair_action(
                    task, deadline, recorder, budget, claim, merged, round_index=1, final_only=True,
                    note="本轮只能输出 action=final，不得再申请补读。",
                )
                if isinstance(decision, RetrieveAction):
                    raise ContractError(ErrorCode.MODEL_INVALID_OUTPUT, "最终请求要求补读")

        assert isinstance(decision, FinalAction)
        published = await self._validate(task, deadline, recorder, budget, source_id, decision.decision, context)
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
                                              purpose="query_generation", prompt=prompt, round_index=0,
                                              context=[], note=str(error))
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
                                              purpose="decision", prompt=prompt, round_index=round_index,
                                              context=context, note=str(error))
            try:
                return parse_decision_output(text)
            except OutputError:
                raise ContractError(ErrorCode.MODEL_INVALID_OUTPUT, "判断输出结构不合法")

    async def _repair_action(self, task, deadline, recorder, budget, claim, candidates, *, round_index,
                             final_only, note, stage=Stage.OUTPUT_REPAIR):
        prompt = self._prompts.decision(claim, candidates, final_only=final_only)
        text = await self._repair_request(
            task, deadline, recorder, budget, stage=stage, purpose="decision", prompt=prompt,
            round_index=round_index, context=[item.paragraph_id for item in candidates], note=note,
            repairs_request_id=f"{task.id}:decision:{round_index}",
        )
        try:
            return parse_decision_output(text)
        except OutputError:
            return None

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

    async def _repair_request(self, task, deadline, recorder, budget, *, stage, purpose, prompt, round_index,
                              context, note, repairs_request_id) -> str:
        await self._check_cancel(task.id)
        self._check_stop(deadline)
        if not budget.can_dispatch_repair():
            raise ContractError(ErrorCode.MODEL_INVALID_OUTPUT, "输出修复额度已用尽")
        budget.take_repair()
        await self._db(self._store.take_request, task.id, "repair_requests_used")
        request_id = f"{task.id}:output_repair:{round_index}"
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
            reply = await self._gateway.complete(
                request_id, prompt, deadline, purpose=purpose, round_index=round_index,
                prompt_version=self._prompts.version, context_paragraph_ids=list(context),
                repairs_request_id=repairs_request_id,
            )
        except ModelFailure as failure:
            await self._db(self._store.record_model_call, task.id,
                           _call_from_failure(request_id, purpose, round_index, self._prompts.version,
                                              context, repairs_request_id, self._settings.model_alias,
                                              failure.attempt))
            await recorder.fail(stage, "model_gateway", failure.error_code, started,
                                round_index=round_index, request_id=request_id)
            raise ContractError(failure.error_code, "模型上游失败") from failure
        await self._db(self._store.record_model_call, task.id, reply.call)
        await recorder.ok(stage, "model_gateway", started, round_index=round_index, request_id=request_id)
        return reply.text

    async def _search(self, task, deadline, recorder, source_id, queries, round_index, neighbor_ids=None):
        await self._check_cancel(task.id)
        self._check_stop(deadline)
        await recorder.enter(Stage.RETRIEVAL, "fts5")
        started = time.monotonic()
        try:
            results = await self._db(self._retriever.search, source_id, [item for item in queries if item.strip()])
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

    async def _validate(self, task, deadline, recorder, budget, source_id, draft: DecisionDraft, context):
        await recorder.enter(Stage.EVIDENCE_VALIDATION, "quote_check")
        started = time.monotonic()
        try:
            published = await self._build_decision(source_id, draft)
        except QuoteError as error:
            await recorder.fail(Stage.EVIDENCE_VALIDATION, "quote_check", ErrorCode.QUOTE_MISMATCH, started)
            repaired = await self._repair_action(
                task, deadline, recorder, budget, task.claim, context, round_index=1, final_only=True,
                note=f"摘录无法在冻结段落中逐字定位：{error}", stage=Stage.EVIDENCE_VALIDATION,
            )
            if not isinstance(repaired, FinalAction):
                raise ContractError(ErrorCode.MODEL_INVALID_OUTPUT, "修复后输出不是最终判断")
            try:
                published = await self._build_decision(source_id, repaired.decision)
            except QuoteError:
                raise ContractError(ErrorCode.QUOTE_MISMATCH, "摘录校验失败")
        await recorder.ok(Stage.EVIDENCE_VALIDATION, "quote_check", started)
        return published

    async def _build_decision(self, source_id: str, draft: DecisionDraft) -> Decision:
        evidence: list[Evidence] = []
        for item in draft.evidence:
            rows = await self._db(self._store.read_neighbors, source_id, [item.paragraph_id])
            if not rows:
                raise QuoteError(f"未知段落 {item.paragraph_id}")
            paragraph: Paragraph = rows[0]
            if not quote_spans(paragraph.text, item.quote):
                raise QuoteError(f"摘录不在段落 {item.paragraph_id} 中")
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
        await self._finish(task, TaskStatus.COMPLETED, outcome.stage, outcome.error_code,
                           outcome.decision.label, outcome.decision)
        return await self._db(self._store.get, task.id)

    async def _terminal(self, task, recorder, error_code, stage: Stage):
        status = terminal_status(error_code)
        label = blocked_label() if status is TaskStatus.BLOCKED else None
        await self._finish(task, status, stage, error_code, label, None)
        return await self._db(self._store.get, task.id)

    async def _cancel(self, task, recorder, stage: Stage):
        stored = await self._db(self._store.get, task.id)
        if stored is not None and stored.status is TaskStatus.CANCELLED:
            return stored
        await self._finish(task, TaskStatus.CANCELLED, stage, None, None, None)
        return await self._db(self._store.get, task.id)

    async def _finish(self, task, status, stage, error_code, label, decision):
        await self._db(
            self._store.finish, task.id, status=status, stage=stage.value, error_code=error_code,
            label=label,
            decision=decision.model_dump(mode="json") if decision is not None else None,
        )


def _dedupe(paragraphs):
    seen: dict[str, Paragraph] = {}
    for paragraph in paragraphs:
        seen.setdefault(paragraph.paragraph_id, paragraph)
    return list(seen.values())


def _call_from_failure(request_id, purpose, round_index, prompt_version, context, repairs_request_id,
                       model_alias, attempt) -> ModelCall:
    return ModelCall(
        request_id=request_id, purpose=purpose, round=round_index, model_alias=model_alias,
        prompt_version=prompt_version, params_digest=request_id, context_paragraph_ids=list(context),
        repairs_request_id=repairs_request_id, attempts=[attempt],
    )
