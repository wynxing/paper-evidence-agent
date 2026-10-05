import type { DiagnosticPacket } from './contracts.ts'
/** Export known contract fields only; extra server fields never enter downloads. */
const pick = (value: unknown, keys: string[]) => Object.fromEntries(keys.map(k => [k, (value as Record<string, unknown>)[k]]))
export function projectPacket(p: DiagnosticPacket) {
  return {
    ...pick(p, ['schema_version', 'case_id', 'run_id', 'trace_id', 'previous_id', 'cancel_requested', 'status', 'label', 'error_code']),
    criteria: pick(p.criteria, ['version', 'digest', 'snapshot_ref', 'implementation_revision']),
    accounting: pick(p.accounting, ['verification', 'main_requests_used', 'repair_requests_used', 'supplemental_rounds_used', 'upstream_attempts_used', 'observed_upstream_attempts', 'reason']),
    input: pick(p.input, ['doi', 'claim', 'privacy', 'recipient']), source: p.source ? pick(p.source, ['title', 'doi', 'pmcid', 'license', 'version', 'access_url', 'retrieved_at', 'version_hash']) : null,
    run_config: { ...pick(p.run_config, ['profile', 'config_digest', 'snapshot_ref', 'authorized_recipients']), limits: pick(p.run_config.limits, ['main_requests', 'repair_requests', 'attempts_per_request', 'supplemental_rounds']), timeouts: pick(p.run_config.timeouts, ['model_attempt_seconds', 'source_request_seconds', 'task_seconds']), observability: pick(p.run_config.observability, ['langfuse_enabled', 'recipient']) },
    decision: p.decision ? { ...pick(p.decision, ['agent', 'label', 'rationale', 'supported_parts', 'scope_differences', 'limitations', 'validation']), evidence: p.decision.evidence.map(e => pick(e, ['paragraph_id', 'quote', 'section', 'source_url', 'paragraph_hash', 'validation'])) } : null,
    evidence_candidates: p.evidence_candidates.map(e => pick(e, ['paragraph_id', 'quote', 'section', 'source_url', 'paragraph_hash', 'round', 'rank', 'entered_context'])),
    execution: p.execution.map(e => pick(e, ['stage', 'span_id', 'tool', 'status', 'error_code', 'duration_ms', 'round', 'request_id'])),
    model_calls: p.model_calls.map(c => ({ ...pick(c, ['request_id', 'purpose', 'round', 'model_alias', 'prompt_version', 'params_digest', 'context_paragraph_ids', 'repairs_request_id']), attempts: c.attempts.map(a => ({ ...pick(a, ['attempt_id', 'attempt_index', 'span_id', 'gateway_request_id', 'upstream_response_id', 'configured_model', 'deployment_id', 'recipient', 'response_model', 'verified_model_version', 'recovery_kind', 'recovery_reason', 'status', 'error_code', 'duration_ms']), usage: a.usage ? pick(a.usage, ['prompt_tokens', 'completion_tokens', 'total_tokens']) : null })) })),
  }
}
export function downloadPacket(p: DiagnosticPacket) {
  const url = URL.createObjectURL(new Blob([JSON.stringify(projectPacket(p), null, 2)], { type: 'application/json' }))
  const a = document.createElement('a'); a.href = url; a.download = `${p.case_id.replace(/[^a-zA-Z0-9_-]/g, '_')}-${p.input.privacy}.json`; a.click(); setTimeout(() => URL.revokeObjectURL(url), 1000)
}
