import type { Accounting, CheckDetail, ContextParagraph, DiagnosticExportRequest, DiagnosticPacket, EvidenceContext, RunConfigPreview, SourcePreview, TaskStatus } from '../api/contracts.ts'

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
export function diagnosticExportRequest(packet: DiagnosticPacket | null, id: string | null, recipient: string, consent: boolean, authorizedPacket: DiagnosticPacket | null): DiagnosticExportRequest {
  if (!packet || packet !== authorizedPacket || packet.case_id !== id) throw new Error('诊断包或任务已变化，请重新预览并授权。')
  const configured = packet.run_config.observability.recipient
  if (!configured?.trim()) throw new Error('当前任务未配置语义诊断接收方，可下载脱敏包。')
  if (recipient !== configured) throw new Error('接收方必须与当前诊断包配置一致，请重新预览。')
  if (consent !== true) throw new Error('导出语义诊断包前需要确认授权。')
  return { recipient: configured, semantic_export_consent: true }
}
export const isTerminal = (status: TaskStatus) => !['QUEUED', 'RUNNING'].includes(status)
/**
 * The claim to show and to edit. The submit-time cache wins because it is the exact text the user typed;
 * the task record is the fallback, so a reopened or refreshed task is no longer unreadable.
 */
export function originalClaim(cached: SubmissionContext | null, loaded: CheckDetail | null): string { return cached?.claim ?? loaded?.claim ?? '' }
/** Same precedence as originalClaim, for the DOI that retry, revise, and split must re-authorize. */
export function originalDoi(cached: SubmissionContext | null, rowDoi: string | undefined, loaded: CheckDetail | null): string { return cached?.doi ?? rowDoi ?? loaded?.source?.doi ?? '' }
/** A span is only reported when both ends exist; a missing or reversed end stays an explicit placeholder. */
export function elapsedText(from: string | null, to: string | null): string {
  if (!from || !to) return '暂无数据'
  const start = Date.parse(from); const end = Date.parse(to)
  if (!Number.isFinite(start) || !Number.isFinite(end) || end < start) return '暂无数据'
  const seconds = (end - start) / 1000
  return seconds < 60 ? `${seconds.toFixed(1)} 秒` : `${Math.floor(seconds / 60)} 分 ${Math.round(seconds % 60)} 秒`
}
/** Local-time display copy. An unparsable timestamp renders as nothing rather than as a wrong instant. */
export function stampText(value: string | null): string {
  if (!value) return ''
  const parsed = Date.parse(value)
  if (!Number.isFinite(parsed)) return ''
  const at = new Date(parsed); const pad = (n: number) => String(n).padStart(2, '0')
  return `${at.getFullYear()}-${pad(at.getMonth() + 1)}-${pad(at.getDate())} ${pad(at.getHours())}:${pad(at.getMinutes())}`
}
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
export interface AnchorWindow { anchor: ContextParagraph | null; before: ContextParagraph | null; after: ContextParagraph | null }
/**
 * The evidence-context list is ordered by paragraph ordinal and already includes each anchor's neighbours.
 * The entries immediately beside an anchor are those neighbours. A list that contains only the anchor has none.
 */
export function anchorWindow(paragraphs: readonly ContextParagraph[], paragraphId: string): AnchorWindow {
  const index = paragraphs.findIndex(item => item.paragraph_id === paragraphId)
  if (index < 0) return { anchor: null, before: null, after: null }
  return { anchor: paragraphs[index] ?? null, before: paragraphs[index - 1] ?? null, after: paragraphs[index + 1] ?? null }
}
/** Why a frozen context has no paragraphs yet. A non-empty list is not an empty state. */
export function evidenceContextSummary(context: EvidenceContext): string | null {
  if (context.paragraphs.length) return null
  return context.source_id ? '来源已冻结，但还没有进入上下文或被引用的段落。' : '来源尚未冻结，没有可读取的段落。'
}
/** What to say about one quote's surroundings. The anchor text stays visible when the notice is only about missing neighbours. */
export function evidenceContextNotice(context: EvidenceContext, paragraphId: string): string | null {
  const summary = evidenceContextSummary(context)
  if (summary) return summary
  const window = anchorWindow(context.paragraphs, paragraphId)
  if (!window.anchor) return '这段摘录不在当前返回的证据上下文中。'
  if (!window.before && !window.after) return '当前只返回了该摘录所在段落，没有相邻段落。'
  return null
}
/** Cited and entered-context paragraphs are anchors. A paragraph with neither flag is a neighbour, not evidence. */
export function paragraphRole(paragraph: ContextParagraph): string {
  const parts: string[] = []
  if (paragraph.cited) parts.push('被引用')
  if (paragraph.entered_context) parts.push('进入模型上下文')
  if (!parts.length) parts.push('邻段')
  return parts.join(' · ')
}
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
