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


class CheckSummary(Contract):
    id: str
    doi: str
    status: TaskStatus
    stage: Stage
    label: ResultLabel | None


class CheckDetail(Contract):
    id: str
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


class SourceRecord(Contract):
    title: str | None
    doi: str | None
    pmcid: str | None
    license: str | None
    version: str | None
    access_url: str | None
    retrieved_at: str | None
    version_hash: str | None


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
