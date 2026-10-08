import type { Accounting, RunConfigPreview, SourcePreview, TaskStatus } from '../api/contracts.ts'

export interface Draft {
  claim: string; doi: string; source: SourcePreview | null; config: RunConfigPreview | null
  sourceConfirmed: boolean; cloudConsent: boolean; fallbacks: string[]; previousId: string | null; retryId: string | null
}
export interface SubmissionContext { claim: string | null; doi: string; source: SourcePreview | null }
export const createDraft = (): Draft => ({ claim: '', doi: '', source: null, config: null, sourceConfirmed: false, cloudConsent: false, fallbacks: [], previousId: null, retryId: null })
export function invalidateDraft(d: Draft, sourceChanged: boolean) {
  d.cloudConsent = false
  if (sourceChanged) { d.source = null; d.sourceConfirmed = false }
}
export function normalizeDoi(value: string) { return value.trim().replace(/^https?:\/\/(?:dx\.)?doi\.org\//i, '').replace(/^doi:\s*/i, '') }
export function validDoi(value: string) { return /^10\.\d{4,9}\/\S+$/i.test(normalizeDoi(value)) }
export function canSubmit(d: Draft) { return !!((d.claim.trim() || d.retryId) && validDoi(d.doi) && d.source && d.config && d.sourceConfirmed && d.cloudConsent) }
export const isTerminal = (status: TaskStatus) => !['QUEUED', 'RUNNING'].includes(status)
export const statuses: Record<TaskStatus, string> = { QUEUED: '排队中', RUNNING: '执行中', COMPLETED: '已完成', BLOCKED: '核验受阻', FAILED: '执行失败', CANCELLED: '已取消', INTERRUPTED: '运行中断' }
export const stages: Record<string, string> = { wait: '等待', source_identity: '核对来源', license: '检查许可', fetch: '获取全文', query_generation: '生成检索词', retrieval: '检索证据', decision: '判断或申请补读', evidence_validation: '证据校验', output_repair: '修复输出' }
export const errors: Record<string, string> = {
  DOI_INVALID: 'DOI 格式无效', DOI_UNRESOLVABLE: 'DOI 当前无法解析', METADATA_NOT_FOUND: '文献元数据未找到', REGISTRATION_AGENCY_UNSUPPORTED: '注册机构暂不支持',
  SOURCE_MISMATCH: '来源身份不一致', SOURCE_UNAVAILABLE: '没有首版可处理的开放全文', LICENSE_UNKNOWN: '许可无法确认', LICENSE_UNSUPPORTED: '许可暂不支持自动处理',
  SOURCE_LANGUAGE_UNSUPPORTED: '正文语言暂不支持', CONTENT_INCOMPLETE: '内容不完整或无法解析；具体原因尚未知', RETRIEVAL_FAILED: '证据检索执行失败', RETRIEVAL_EMPTY: '本次未获得足够证据',
  UPSTREAM_TIMEOUT: '单次上游请求超时', UPSTREAM_RATE_LIMITED: '上游请求受到限流', UPSTREAM_AUTH_FAILED: '上游认证失败', UPSTREAM_INVALID_REQUEST: '上游请求不兼容', UPSTREAM_UNAVAILABLE: '上游服务暂不可用',
  TASK_TIMEOUT: '任务总执行时限已到', BUDGET_EXCEEDED: '授权调用预算已耗尽；调整配置后重新授权新任务', MODEL_INVALID_OUTPUT: '模型输出无效', QUOTE_MISMATCH: '摘录与原文校验不一致',
}
export function attemptText(a: Accounting) { return a.verification === 'verified' && a.upstream_attempts_used !== null ? `${a.upstream_attempts_used} 次` : `至少 ${a.observed_upstream_attempts} 次，实际次数未知` }
export function safeSourceUrl(value: string): string | null { try { const u = new URL(value); return ['http:', 'https:'].includes(u.protocol) ? u.href : null } catch { return null } }
export function parseRoute(hash: string): { view: 'new' | 'check' | 'diagnostic'; id: string | null; invalid: boolean } {
  const path = hash.startsWith('#') ? hash.slice(1) : hash
  if (path === '' || path === '/' || path === '/new') return { view: 'new', id: null, invalid: false }
  const m = /^\/checks\/([^/]+)(\/diagnostic)?$/.exec(path)
  if (!m) return { view: 'new', id: null, invalid: true }
  try {
    const id = decodeURIComponent(m[1]!)
    if (!id.trim()) return { view: 'new', id: null, invalid: true }
    return { view: m[2] ? 'diagnostic' : 'check', id, invalid: false }
  } catch { return { view: 'new', id: null, invalid: true } }
}
