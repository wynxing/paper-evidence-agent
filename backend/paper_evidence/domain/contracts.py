"""Typed public contracts from the design documents, without business validation.

Declaring these shapes does not implement source checks, consent enforcement,
redaction, accounting, or evidence validation. Business routes remain stubs.
"""

from typing import Literal

from pydantic import BaseModel, ConfigDict

from .enums import ErrorCode, ResultLabel, Stage, TaskStatus

AcademicLabel = Literal["支持", "部分支持", "相矛盾", "证据不足"]
Profile = Literal["daily", "evaluation"]


class Contract(BaseModel):
    model_config = ConfigDict(extra="forbid")


class ApiError(Contract):
    error_code: ErrorCode | None
    message: str


class ConflictResponse(Contract):
    """409 body from the architecture: the task exists, but this request is not allowed."""

    error_code: Literal[None]
    status: TaskStatus
    stage: Stage
    message: str


class HealthResponse(Contract):
    status: Literal["ok"]


class Limits(Contract):
    main_requests: int
    repair_requests: int
    attempts_per_request: int
    supplemental_rounds: int


class Timeouts(Contract):
    model_attempt_seconds: int
    source_request_seconds: int
    task_seconds: int


def default_limits() -> Limits:
    """Return a fresh default budget; explicit configuration stays supported."""
    return Limits(main_requests=3, repair_requests=1, attempts_per_request=2, supplemental_rounds=1)


def default_timeouts() -> Timeouts:
    """Return fresh default timeouts; actual values belong in config_digest."""
    return Timeouts(model_attempt_seconds=45, source_request_seconds=15, task_seconds=180)


class Observability(Contract):
    langfuse_enabled: bool
    recipient: str | None


class CriteriaReference(Contract):
    version: str
    digest: str
    snapshot_ref: str
    implementation_revision: str


class Accounting(Contract):
    verification: Literal["verified", "unverified"]
    main_requests_used: int
    repair_requests_used: int
    supplemental_rounds_used: int
    upstream_attempts_used: int | None
    observed_upstream_attempts: int
    reason: Literal["attempt_records_missing"] | None


class SourcePreview(Contract):
    doi: str
    title: str
    authors: list[str]
    year: int | None


class RunConfigPreview(Contract):
    profile: Profile
    config_digest: str
    primary_recipient: str
    fallback_recipients: list[str]
    model_alias: str
    data_scope: list[str]
    limits: Limits
    timeouts: Timeouts
    observability: Observability
    criteria: CriteriaReference


class CheckCreateRequest(Contract):
    claim: str
    doi: str
    source_confirmed: bool
    cloud_consent: bool
    config_digest: str
    authorized_recipients: list[str]
    previous_id: str | None = None


class RetryRequest(Contract):
    config_digest: str
    authorized_recipients: list[str]
    cloud_consent: bool
    source_confirmed: bool


class DiagnosticExportRequest(Contract):
    recipient: str
    semantic_export_consent: bool


class FeedbackRequest(Contract):
    comment: str


class CheckCreated(Contract):
    id: str
    status: Literal["QUEUED"]


class RetryCreated(CheckCreated):
    previous_id: str


class Evidence(Contract):
    """A published evidence item. validation is the constant pass, not a fallible check result."""

    paragraph_id: str
    quote: str
    section: str
    source_url: str
    paragraph_hash: str
    validation: Literal["pass"]


class Decision(Contract):
    """A published decision. validation is the constant pass, not a fallible check result."""

    agent: Literal["paper"]
    label: AcademicLabel
    rationale: str
    supported_parts: list[str]
    scope_differences: list[str]
    limitations: list[str]
    evidence: list[Evidence]
    validation: Literal["pass"]


class SourceRecord(Contract):
    """The frozen bibliographic identity of one licensed source version."""

    title: str | None
    authors: list[str]
    year: int | None
    doi: str | None
    pmcid: str | None
    license: str | None
    version: str | None
    access_url: str | None
    retrieved_at: str | None
    version_hash: str | None


class CheckSummary(Contract):
    """A history row. ``claim_excerpt`` is a bounded, single-line display copy."""

    id: str
    doi: str
    status: TaskStatus
    stage: Stage
    label: ResultLabel | None
    claim_excerpt: str
    created_at: str


class CheckDetail(Contract):
    id: str
    claim: str
    source: SourceRecord | None
    status: TaskStatus
    stage: Stage
    label: ResultLabel | None
    error_code: ErrorCode | None
    decision: Decision | None
    previous_id: str | None
    cancel_requested: bool
    criteria: CriteriaReference
    accounting: Accounting
    limits: Limits
    created_at: str
    started_at: str | None
    finished_at: str | None


class CheckInput(Contract):
    """The input a task was created with, returned as submitted.

    A per-task read that does not depend on the history list being loaded.
    ``CheckSummary`` also carries ``doi``, and the workbench already prefills
    「修改原句」「拆分论断」 from that row (``originalDoi`` falls back to it), so this
    route is **not** the only path to the submitted DOI. What is true is narrower:
    inside ``CheckDetail`` the DOI exists only under ``source``, which is null
    until source identity resolves, so the detail view alone has no DOI in that
    window.

    ``config_digest`` and ``authorized_recipients`` are the values frozen at
    creation and are **not** what a resubmission should send: ``POST /api/checks``
    validates the *current* effective digest, so a frozen digest is refused with
    409 once the effective configuration changes. Read-only and always local.
    The task detail UI calls this projection.
    """

    id: str
    claim: str
    doi: str
    previous_id: str | None
    config_digest: str
    authorized_recipients: list[str]


class CancelResponse(Contract):
    id: str
    status: TaskStatus
    cancel_requested: bool
    label: ResultLabel | None
    decision: Decision | None
    error_code: ErrorCode | None


class FeedbackSaved(Contract):
    id: str
    saved: Literal[True]


class CheckDeleted(Contract):
    id: str
    deleted: Literal[True]
    message: str


class DiagnosticInput(Contract):
    doi: str
    claim: str
    privacy: Literal["redacted", "consented"]
    recipient: str | None


class RunConfigSnapshot(Contract):
    """Reference view embedded in a diagnostic packet.

    config_digest summarizes the full frozen snapshot in the glossary section
    「调用账与版本归属」, not only the fields on this view.
    """

    profile: Profile
    config_digest: str
    snapshot_ref: str
    authorized_recipients: list[str]
    limits: Limits
    timeouts: Timeouts
    observability: Observability


class EvidenceCandidate(Contract):
    paragraph_id: str
    section: str
    quote: str
    paragraph_hash: str
    source_url: str
    round: Literal[0, 1]
    rank: int
    entered_context: bool


class ContextParagraph(Contract):
    """One paragraph of the frozen source around the checked evidence.

    ``text`` is the frozen paragraph text, not a published quote: a neighbour is
    read for context and is not itself claimed as evidence. ``paragraph_hash``
    and ``source_url`` are the same locators the published evidence uses, so a
    reader can find the paragraph in the licensed version.

    ``ordinal`` is the paragraph's own position in the frozen source, from 1 in
    body document order (glossary「文本与定位契约」). ``paragraphs`` is sorted by
    it, but 列表相邻不等于原文相邻：同一来源有两个锚点、其中一个的邻段没被展开
    时，紧挨在它后面的条目是另一个锚点。调用方只能用 ``ordinal`` 判断两段是否
    原文相邻——``after.ordinal == anchor.ordinal + 1``（Issue #47）。
    """

    paragraph_id: str
    section: str
    # 冻结来源内的正文序号，从 1 开始；与邻段展开用的 ``ordinal±1`` 同一个值。
    ordinal: int
    text: str
    paragraph_hash: str
    source_url: str
    # 该段曾作为候选进入模型上下文（术语表「调用账与版本归属」的 context_paragraph_ids）。
    entered_context: bool
    # 该段被最终判断引用为证据。
    cited: bool


class EvidenceContext(Contract):
    """Read-only view of one task's evidence context.

    It answers 「模型当时看到的是哪些段落」 and 「引文前后是什么」: the frozen
    paragraphs that entered the model context plus the final decision's cited
    paragraphs, expanded by their ``ordinal±1`` neighbours. Everything stays
    scoped to this task's frozen source, so no paragraph crosses sources; an
    empty list means nothing has been read yet, not that nothing exists.
    """

    id: str
    source_id: str | None
    paragraphs: list[ContextParagraph]


class ExecutionRecord(Contract):
    stage: Stage
    span_id: str
    tool: str
    status: Literal["success", "error", "blocked", "cancelled"]
    error_code: ErrorCode | None
    duration_ms: int | None
    round: Literal[0, 1] | None
    request_id: str | None


class TokenUsage(Contract):
    prompt_tokens: int | None
    completion_tokens: int | None
    total_tokens: int | None


class ModelAttempt(Contract):
    attempt_id: str
    attempt_index: int
    span_id: str
    gateway_request_id: str | None
    upstream_response_id: str | None
    configured_model: str | None
    provider_model: str | None
    deployment_id: str | None
    recipient: str | None
    response_model: str | None
    verified_model_version: str | None
    recovery_kind: Literal["none", "retry", "fallback"]
    recovery_reason: ErrorCode | None
    status: Literal["success", "error", "cancelled"]
    error_code: ErrorCode | None
    duration_ms: int | None
    usage: TokenUsage | None


class ModelCall(Contract):
    request_id: str
    purpose: Literal["query_generation", "decision", "output_repair"]
    round: Literal[0, 1] | None
    model_alias: str
    prompt_version: str
    params_digest: str
    context_paragraph_ids: list[str]
    repairs_request_id: str | None
    attempts: list[ModelAttempt]


class DiagnosticPacket(Contract):
    schema_version: Literal["2.2"]
    criteria: CriteriaReference
    accounting: Accounting
    case_id: str
    run_id: str
    trace_id: str
    previous_id: str | None
    cancel_requested: bool
    status: TaskStatus
    label: ResultLabel | None
    error_code: ErrorCode | None
    input: DiagnosticInput
    source: SourceRecord | None
    run_config: RunConfigSnapshot
    evidence_candidates: list[EvidenceCandidate]
    decision: Decision | None
    execution: list[ExecutionRecord]
    model_calls: list[ModelCall]
