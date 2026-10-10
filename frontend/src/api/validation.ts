import { errors, stages, statuses } from '../state/model.ts'
type Validator = (value: unknown) => boolean
export const record = (value: unknown): value is Record<string, unknown> => typeof value === 'object' && value !== null && !Array.isArray(value)
export const text: Validator = value => typeof value === 'string'
const number: Validator = value => typeof value === 'number' && Number.isFinite(value) && value >= 0
const bool: Validator = value => typeof value === 'boolean'
const oneOf = (...values: unknown[]): Validator => value => values.includes(value)
const nullable = (validate: Validator): Validator => value => value === null || validate(value)
const array = (validate: Validator): Validator => value => Array.isArray(value) && value.every(validate)
const strings = array(text)
const shape = (fields: Record<string, Validator>): Validator => value => record(value) && Object.entries(fields).every(([key, validate]) => Object.hasOwn(value, key) && validate(value[key]))
const status = oneOf(...Object.keys(statuses)); const stage = oneOf(...Object.keys(stages))
const errorCode = nullable(oneOf(...Object.keys(errors)))
const label = oneOf('支持', '部分支持', '相矛盾', '证据不足')
const criteria = shape({ version: text, digest: text, snapshot_ref: text, implementation_revision: text })
const limits = shape({ main_requests: number, repair_requests: number, attempts_per_request: number, supplemental_rounds: number })
const timeouts = shape({ model_attempt_seconds: number, source_request_seconds: number, task_seconds: number })
const observability = shape({ langfuse_enabled: bool, recipient: nullable(text) })
const accounting = shape({ verification: oneOf('verified', 'unverified'), main_requests_used: number, repair_requests_used: number, supplemental_rounds_used: number, upstream_attempts_used: nullable(number), observed_upstream_attempts: number, reason: oneOf(null, 'attempt_records_missing') })
const evidenceFields = { paragraph_id: text, quote: text, section: text, source_url: text, paragraph_hash: text }
const evidence = shape({ ...evidenceFields, validation: oneOf('pass') })
const decision = nullable(shape({ agent: oneOf('paper'), label, rationale: text, supported_parts: strings, scope_differences: strings, limitations: strings, evidence: array(evidence), validation: oneOf('pass') }))
const detailFields = { id: text, status, stage, label: nullable(oneOf('支持', '部分支持', '相矛盾', '证据不足', '无法核验来源')), error_code: errorCode, decision, previous_id: nullable(text), cancel_requested: bool, criteria, accounting, limits }
const academicLabels = new Set(['支持', '部分支持', '相矛盾', '证据不足'])
/** Status, label, decision, and error_code must agree. History rows omit decision and error_code, so those checks run only when the field is present. */
export function coherentOutcome(value: unknown): boolean {
  if (!record(value)) return false
  const { status, label } = value
  if (status === 'COMPLETED') {
    if (typeof label !== 'string' || !academicLabels.has(label)) return false
    if (!Object.hasOwn(value, 'decision')) return true
    const outcome = value.decision
    if (!record(outcome) || outcome.label !== label) return false
    return label === '证据不足' || (Array.isArray(outcome.evidence) && outcome.evidence.length > 0)
  }
  if (label !== (status === 'BLOCKED' ? '无法核验来源' : null)) return false
  if (Object.hasOwn(value, 'decision') && value.decision !== null) return false
  if (status === 'BLOCKED' && Object.hasOwn(value, 'error_code')) return typeof value.error_code === 'string' && value.error_code.trim() !== ''
  return true
}
export const validateDetail: Validator = value => shape(detailFields)(value) && coherentOutcome(value)
export const validateCreated = shape({ id: text, status: oneOf('QUEUED') })
export const validateSource = shape({ doi: text, title: text, authors: strings, year: nullable(number) })
export const validateConfig = shape({ profile: oneOf('daily', 'evaluation'), config_digest: text, primary_recipient: text, fallback_recipients: strings, model_alias: text, data_scope: strings, limits, timeouts, observability, criteria })
const summary = shape({ id: text, doi: text, status, stage, label: detailFields.label })
export const validateHistory = array(value => summary(value) && coherentOutcome(value))
export const validateCancel: Validator = value => shape({ id: text, status, cancel_requested: bool, label: detailFields.label, decision, error_code: errorCode })(value) && coherentOutcome(value)
export const validateSaved = shape({ id: text, saved: oneOf(true) })
export const validateDeleted = shape({ id: text, deleted: oneOf(true), message: text })
export const validateRetry = shape({ id: text, status: oneOf('QUEUED'), previous_id: text })
const source = nullable(shape({ title: nullable(text), doi: nullable(text), pmcid: nullable(text), license: nullable(text), version: nullable(text), access_url: nullable(text), retrieved_at: nullable(text), version_hash: nullable(text) }))
const execution = shape({ stage, span_id: text, tool: text, status: oneOf('success', 'error', 'blocked', 'cancelled'), error_code: errorCode, duration_ms: nullable(number), round: oneOf(null, 0, 1), request_id: nullable(text) })
const usage = nullable(shape({ prompt_tokens: nullable(number), completion_tokens: nullable(number), total_tokens: nullable(number) }))
const attempt = shape({ attempt_id: text, attempt_index: number, span_id: text, gateway_request_id: nullable(text), upstream_response_id: nullable(text), configured_model: nullable(text), deployment_id: nullable(text), recipient: nullable(text), response_model: nullable(text), verified_model_version: nullable(text), recovery_kind: oneOf('none', 'retry', 'fallback'), recovery_reason: errorCode, status: oneOf('success', 'error', 'cancelled'), error_code: errorCode, duration_ms: nullable(number), usage })
const call = shape({ request_id: text, purpose: oneOf('query_generation', 'decision', 'output_repair'), round: oneOf(null, 0, 1), model_alias: text, prompt_version: text, params_digest: text, context_paragraph_ids: strings, repairs_request_id: nullable(text), attempts: array(attempt) })
export const validatePacket: Validator = value => shape({ schema_version: oneOf('2.2'), criteria, accounting, case_id: text, run_id: text, trace_id: text, previous_id: nullable(text), cancel_requested: bool, status, label: detailFields.label, error_code: nullable(text), input: shape({ doi: text, claim: text, privacy: oneOf('redacted', 'consented'), recipient: nullable(text) }), source, run_config: shape({ profile: oneOf('daily', 'evaluation'), config_digest: text, snapshot_ref: text, authorized_recipients: strings, limits, timeouts, observability }), evidence_candidates: array(shape({ ...evidenceFields, round: oneOf(0, 1), rank: number, entered_context: bool })), decision, execution: array(execution), model_calls: array(call) })(value) && coherentOutcome(value)
