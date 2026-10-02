/** Interface declarations only; no HTTP client or business logic is implemented. */
export type TaskStatus = 'QUEUED' | 'RUNNING' | 'COMPLETED' | 'BLOCKED' | 'FAILED' | 'CANCELLED' | 'INTERRUPTED'
export type AcademicLabel = '支持' | '部分支持' | '相矛盾' | '证据不足'
export type ResultLabel = AcademicLabel | '无法核验来源'
export type Stage = 'wait' | 'source_identity' | 'license' | 'fetch' | 'query_generation' | 'retrieval' | 'decision' | 'evidence_validation' | 'output_repair'
export type ErrorCode =
  | 'DOI_INVALID' | 'DOI_UNRESOLVABLE' | 'METADATA_NOT_FOUND' | 'REGISTRATION_AGENCY_UNSUPPORTED'
  | 'SOURCE_MISMATCH' | 'SOURCE_UNAVAILABLE' | 'LICENSE_UNKNOWN' | 'LICENSE_UNSUPPORTED'
  | 'SOURCE_LANGUAGE_UNSUPPORTED' | 'CONTENT_INCOMPLETE' | 'RETRIEVAL_FAILED' | 'RETRIEVAL_EMPTY'
  | 'UPSTREAM_TIMEOUT' | 'UPSTREAM_RATE_LIMITED' | 'UPSTREAM_AUTH_FAILED' | 'UPSTREAM_INVALID_REQUEST'
  | 'UPSTREAM_UNAVAILABLE' | 'TASK_TIMEOUT' | 'BUDGET_EXCEEDED' | 'MODEL_INVALID_OUTPUT' | 'QUOTE_MISMATCH'
export interface ApiError { error_code: ErrorCode | null; message: string }
export interface ConflictResponse { error_code: null; status: TaskStatus; stage: Stage; message: string }
export interface HealthResponse { status: 'ok' }
export interface DiagnosticExportRequest { recipient: string; semantic_export_consent: boolean }
export interface FeedbackRequest { comment: string }
export interface FeedbackSaved { id: string; saved: true }
export interface CheckDeleted { id: string; deleted: true; message: string }
export interface DiagnosticInput { doi: string; claim: string; privacy: 'redacted' | 'consented'; recipient: string | null }
export interface TokenUsage { prompt_tokens: number | null; completion_tokens: number | null; total_tokens: number | null }
/** Reference view; config_digest covers the full glossary snapshot. */
export interface RunConfigSnapshot {
  profile: 'daily' | 'evaluation'
  config_digest: string
  snapshot_ref: string
  authorized_recipients: string[]
  limits: Limits
  timeouts: Timeouts
  observability: Observability
}
export interface Limits { main_requests: number; repair_requests: number; attempts_per_request: number; supplemental_rounds: number }
export interface Timeouts { model_attempt_seconds: number; source_request_seconds: number; task_seconds: number }
export interface Observability { langfuse_enabled: boolean; recipient: string | null }
export interface CriteriaReference { version: string; digest: string; snapshot_ref: string; implementation_revision: string }
export interface Accounting {
  verification: 'verified' | 'unverified'
  main_requests_used: number
  repair_requests_used: number
  supplemental_rounds_used: number
  upstream_attempts_used: number | null
  observed_upstream_attempts: number
  reason: 'attempt_records_missing' | null
}
export interface SourcePreview { doi: string; title: string; authors: string[]; year: number | null }
export interface RunConfigPreview {
  profile: 'daily' | 'evaluation'
  config_digest: string
  primary_recipient: string
  fallback_recipients: string[]
  model_alias: string
  data_scope: string[]
  limits: Limits
  timeouts: Timeouts
  observability: Observability
  criteria: CriteriaReference
}
export interface RetryRequest {
  config_digest: string
  authorized_recipients: string[]
  cloud_consent: boolean
  source_confirmed: boolean
}
export interface CheckCreateRequest extends RetryRequest { claim: string; doi: string; previous_id?: string | null }
export interface CheckCreated { id: string; status: 'QUEUED' }
export interface RetryCreated extends CheckCreated { previous_id: string }
export interface Evidence {
  paragraph_id: string
  quote: string
  section: string
  source_url: string
  paragraph_hash: string
  /** Published invariant. This is not a fallible validation result. */
  validation: 'pass'
}
export interface Decision {
  agent: 'paper'
  label: AcademicLabel
  rationale: string
  supported_parts: string[]
  scope_differences: string[]
  limitations: string[]
  evidence: Evidence[]
  /** Published invariant. This is not a fallible validation result. */
  validation: 'pass'
}
export interface CheckSummary { id: string; doi: string; status: TaskStatus; stage: Stage; label: ResultLabel | null }
export interface CheckDetail {
  id: string
  status: TaskStatus
  stage: Stage
  label: ResultLabel | null
  error_code: ErrorCode | null
  decision: Decision | null
  previous_id: string | null
  cancel_requested: boolean
  criteria: CriteriaReference
  accounting: Accounting
  limits: Limits
}
export interface CancelResponse {
  id: string
  status: TaskStatus
  cancel_requested: boolean
  label: ResultLabel | null
  decision: Decision | null
  error_code: ErrorCode | null
}
export interface SourceRecord {
  title: string | null
  doi: string | null
  pmcid: string | null
  license: string | null
  version: string | null
  access_url: string | null
  retrieved_at: string | null
  version_hash: string | null
}
export interface EvidenceCandidate extends Omit<Evidence, 'validation'> { round: 0 | 1; rank: number; entered_context: boolean }
export interface ExecutionRecord {
  stage: Stage
  span_id: string
  tool: string
  status: 'success' | 'error' | 'blocked' | 'cancelled'
  error_code: ErrorCode | null
  duration_ms: number | null
  round: 0 | 1 | null
  request_id: string | null
}
export interface ModelAttempt {
  attempt_id: string
  attempt_index: number
  span_id: string
  gateway_request_id: string | null
  upstream_response_id: string | null
  configured_model: string | null
  deployment_id: string | null
  recipient: string | null
  response_model: string | null
  verified_model_version: string | null
  recovery_kind: 'none' | 'retry' | 'fallback'
  recovery_reason: ErrorCode | null
  status: 'success' | 'error' | 'cancelled'
  error_code: ErrorCode | null
  duration_ms: number | null
  usage: TokenUsage | null
}
export interface ModelCall {
  request_id: string
  purpose: 'query_generation' | 'decision' | 'output_repair'
  round: 0 | 1 | null
  model_alias: string
  prompt_version: string
  params_digest: string
  context_paragraph_ids: string[]
  repairs_request_id: string | null
  attempts: ModelAttempt[]
}
export interface DiagnosticPacket {
  schema_version: '2.2'
  criteria: CriteriaReference
  accounting: Accounting
  case_id: string
  run_id: string
  trace_id: string
  previous_id: string | null
  cancel_requested: boolean
  status: TaskStatus
  label: ResultLabel | null
  error_code: ErrorCode | null
  input: DiagnosticInput
  source: SourceRecord | null
  /** Reference view. config_digest covers the full glossary snapshot, not only these fields. */
  run_config: RunConfigSnapshot
  evidence_candidates: EvidenceCandidate[]
  decision: Decision | null
  execution: ExecutionRecord[]
  model_calls: ModelCall[]
}
export interface ApiClient {
  resolveSource(doi: string): Promise<SourcePreview>
  getRunConfig(): Promise<RunConfigPreview>
  createCheck(body: CheckCreateRequest): Promise<CheckCreated>
  listChecks(status?: TaskStatus): Promise<CheckSummary[]>
  getCheck(id: string): Promise<CheckDetail>
  getDiagnosticPacket(id: string): Promise<DiagnosticPacket>
  exportDiagnosticPacket(id: string, body: DiagnosticExportRequest): Promise<DiagnosticPacket>
  saveFeedback(id: string, body: FeedbackRequest): Promise<FeedbackSaved>
  retryCheck(id: string, body: RetryRequest): Promise<RetryCreated>
  cancelCheck(id: string): Promise<CancelResponse>
  deleteCheck(id: string): Promise<CheckDeleted>
}
