import type { ApiClient, AcademicLabel, CheckDetail, CheckCreateRequest, DiagnosticPacket, RetryRequest, RunConfigPreview, SourcePreview, TaskStatus } from './contracts.ts'
import { ClientError } from './http.ts'
import { isTerminal } from '../state/model.ts'

export const demoScenarios = ['支持', '部分支持', '相矛盾', '证据不足', '排队中', '执行中', '来源阻断', '执行失败', '已取消', '运行中断'] as const
export type DemoScenario = typeof demoScenarios[number]
const copy = <T>(x: T): T => structuredClone(x)
const limits = { main_requests: 3, repair_requests: 1, attempts_per_request: 2, supplemental_rounds: 1 }
const criteria = { version: 'demo-criteria', digest: 'demo-only', snapshot_ref: 'demo-memory', implementation_revision: 'constructed-fixture' }
const config: RunConfigPreview = { profile: 'daily', config_digest: 'demo-config-v1', primary_recipient: '本地模拟接收方（不发送）', fallback_recipients: ['模拟备用方（不发送）'], model_alias: 'demo-no-model', data_scope: ['论断原句', '获许可的候选片段'], limits, timeouts: { model_attempt_seconds: 45, source_request_seconds: 15, task_seconds: 180 }, observability: { langfuse_enabled: false, recipient: null }, criteria }
export function demoSource(doi: string): SourcePreview { return { doi, title: '构造文献 · 干预与观察指标的示例研究', authors: ['模拟作者 A', '模拟作者 B'], year: null } }
function detail(id: string, scenario: DemoScenario, previousId: string | null = null): CheckDetail {
  const mappings: Partial<Record<DemoScenario, TaskStatus>> = { 排队中: 'QUEUED', 执行中: 'RUNNING', 来源阻断: 'BLOCKED', 执行失败: 'FAILED', 已取消: 'CANCELLED', 运行中断: 'INTERRUPTED' }
  const status = mappings[scenario] ?? 'COMPLETED'
  const academic = status === 'COMPLETED' ? scenario as AcademicLabel : null
  return { id, status, stage: status === 'QUEUED' ? 'wait' : status === 'BLOCKED' ? 'license' : status === 'FAILED' ? 'retrieval' : status === 'RUNNING' ? 'retrieval' : 'evidence_validation', label: status === 'BLOCKED' ? '无法核验来源' : academic,
    error_code: status === 'BLOCKED' ? 'LICENSE_UNKNOWN' : status === 'FAILED' ? 'RETRIEVAL_FAILED' : academic === '证据不足' ? 'RETRIEVAL_EMPTY' : null,
    previous_id: previousId, cancel_requested: status === 'CANCELLED', criteria, limits,
    accounting: { verification: 'unverified', main_requests_used: status === 'COMPLETED' ? 2 : 0, repair_requests_used: 0, supplemental_rounds_used: academic === '证据不足' ? 1 : 0, upstream_attempts_used: null, observed_upstream_attempts: status === 'COMPLETED' ? 2 : 0, reason: 'attempt_records_missing' },
    decision: academic ? { agent: 'paper', label: academic, rationale: '构造说明：此处展示指定文献与论断的关系及判断依据。演示数据不代表真实学术判断。', supported_parts: academic === '支持' || academic === '部分支持' ? ['构造样本在指定观察条件下存在指标变化。'] : [], scope_differences: academic === '部分支持' ? ['构造原文只涉及短期观察，不能据此推及所有人群或长期效果。'] : [], limitations: ['全部内容为前端构造数据；未经真实文献核验。'], evidence: academic === '证据不足' ? [] : [
      { paragraph_id: 'demo:p:1', section: '构造章节 · Results', quote: '构造摘录：在指定样本和观察条件下，研究组记录到指标变化。', source_url: '', paragraph_hash: 'demo-paragraph-1', validation: 'pass' },
      { paragraph_id: 'demo:p:2', section: '构造章节 · Limitations', quote: '构造摘录：观察期有限，结论不能推广至未经研究的人群或条件。', source_url: '', paragraph_hash: 'demo-paragraph-2', validation: 'pass' },
    ], validation: 'pass' } : null }
}
export function createDemoClient(): ApiClient & { selectScenario: (value: DemoScenario) => void } {
  const entries = new Map<string, { doi: string; claim: string; result: CheckDetail; target: DemoScenario; tick: number; fresh: boolean; feedback: string[] }>()
  let selected: DemoScenario = '部分支持'; let counter = 0
  demoScenarios.forEach((scenario, i) => { const id = `demo-${i + 1}`; entries.set(id, { doi: `10.0000/demo-${i + 1}`, claim: '构造论断：该干预在所有人群中均具有持续效果。', result: detail(id, scenario), target: scenario, tick: 0, fresh: false, feedback: [] }) })
  function find(id: string) { const e = entries.get(id); if (!e) throw new ClientError('business', '任务不存在。', 404); return e }
  function consent(body: RetryRequest) {
    if (body.config_digest !== config.config_digest) throw new ClientError('business', '配置已变化，请重新确认。', 409)
    if (!body.source_confirmed || !body.cloud_consent || !body.authorized_recipients.includes(config.primary_recipient)) throw new ClientError('business', '尚未确认来源或调用授权。', 400)
  }
  function create(body: CheckCreateRequest) {
    consent(body); if (!body.claim.trim()) throw new ClientError('business', '请输入论断。', 400)
    const id = `demo-new-${++counter}`; entries.set(id, { doi: body.doi, claim: body.claim, result: detail(id, '排队中', body.previous_id ?? null), target: selected, tick: 0, fresh: true, feedback: [] }); return { id, status: 'QUEUED' as const }
  }
  function packet(id: string, privacy: 'redacted' | 'consented', recipient: string | null): DiagnosticPacket {
    const e = find(id); const d = copy(e.result); const decision = copy(d.decision)
    if (privacy === 'redacted' && decision) { decision.rationale = '<redacted>'; decision.supported_parts = decision.supported_parts.map(() => '<redacted>'); decision.scope_differences = decision.scope_differences.map(() => '<redacted>'); decision.limitations = decision.limitations.map(() => '<redacted>'); decision.evidence.forEach(x => x.quote = '<redacted>') }
    return { schema_version: '2.2', criteria, accounting: d.accounting, case_id: id, run_id: `run-${id}`, trace_id: `trace-${id}`, previous_id: d.previous_id, cancel_requested: d.cancel_requested, status: d.status, label: d.label, error_code: d.error_code,
      input: { doi: e.doi, claim: privacy === 'redacted' ? '<redacted>' : e.claim, privacy, recipient }, source: { title: demoSource(e.doi).title, doi: e.doi, pmcid: null, license: null, version: 'constructed', access_url: null, retrieved_at: null, version_hash: 'demo-source' },
      run_config: { profile: 'daily', config_digest: config.config_digest, snapshot_ref: 'demo-memory', authorized_recipients: [config.primary_recipient], limits, timeouts: config.timeouts, observability: config.observability },
      decision, evidence_candidates: (decision?.evidence ?? []).map(({ validation: _validation, ...x }, i) => ({ ...x, round: 0 as const, rank: i + 1, entered_context: true })),
      execution: [{ stage: 'source_identity', span_id: `${id}-source`, tool: 'demo-source', status: 'success', error_code: null, duration_ms: null, round: null, request_id: null }, { stage: d.stage, span_id: `${id}-last`, tool: 'demo-fixture', status: d.status === 'FAILED' ? 'error' : d.status === 'BLOCKED' ? 'blocked' : d.status === 'CANCELLED' ? 'cancelled' : 'success', error_code: d.error_code, duration_ms: null, round: 0, request_id: `${id}-request` }],
      model_calls: [{ request_id: `${id}-request`, purpose: 'decision', round: 0, model_alias: 'demo-no-model', prompt_version: 'demo', params_digest: 'demo', context_paragraph_ids: decision?.evidence.map(x => x.paragraph_id) ?? [], repairs_request_id: null, attempts: [{ attempt_id: `${id}-attempt`, attempt_index: 1, span_id: `${id}-last`, gateway_request_id: null, upstream_response_id: null, configured_model: 'demo-no-model', deployment_id: null, recipient: config.primary_recipient, response_model: null, verified_model_version: null, recovery_kind: 'none', recovery_reason: null, status: d.status === 'FAILED' ? 'error' : d.status === 'CANCELLED' ? 'cancelled' : 'success', error_code: d.error_code, duration_ms: null, usage: null }] }],
    }
  }
  return {
    selectScenario(value) { selected = value }, resolveSource: async doi => demoSource(doi), getRunConfig: async () => copy(config), createCheck: async body => create(body),
    listChecks: async status => [...entries.values()].filter(e => !status || e.result.status === status).map(e => ({ id: e.result.id, doi: e.doi, status: e.result.status, stage: e.result.stage, label: e.result.label })),
    getCheck: async id => { const e = find(id); if (e.result.cancel_requested && !isTerminal(e.result.status)) e.result.status = 'CANCELLED'
      else if (e.fresh && !isTerminal(e.result.status)) { e.tick++; if (e.tick > 1 && e.target !== '排队中') e.result = detail(id, e.tick > 2 ? e.target : '执行中', e.result.previous_id) }
      return copy(e.result) },
    getDiagnosticPacket: async id => copy(packet(id, 'redacted', null)), exportDiagnosticPacket: async (id, body) => { if (!body.semantic_export_consent || !body.recipient.trim()) throw new ClientError('business', '请确认接收方及导出授权。', 400); return copy(packet(id, 'consented', body.recipient)) },
    saveFeedback: async (id, body) => { find(id).feedback.push(body.comment); return { id, saved: true } },
    retryCheck: async (id, body) => { const e = find(id); if (!isTerminal(e.result.status)) throw new ClientError('business', '任务尚未结束。', 409); const next = create({ ...body, claim: e.claim, doi: e.doi, previous_id: id }); return { ...next, previous_id: id } },
    cancelCheck: async id => { const e = find(id); if (isTerminal(e.result.status) && e.result.status !== 'CANCELLED') throw new ClientError('business', '任务已结束，无法取消。', 409); e.result.cancel_requested = true; if (e.result.status === 'QUEUED') e.result.status = 'CANCELLED'; return copy(e.result) },
    deleteCheck: async id => { const e = find(id); if (!isTerminal(e.result.status)) throw new ClientError('business', '只能删除已结束任务。', 409); entries.delete(id); return { id, deleted: true, message: '模拟任务已移除；没有云调用。' } },
  }
}
