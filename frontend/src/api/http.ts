import type { ApiClient } from './contracts.ts'
import { record, text, validateCancel, validateConfig, validateCreated, validateDeleted, validateDetail, validateHistory, validatePacket, validateRetry, validateSaved, validateSource } from './validation.ts'

export class ClientError extends Error {
  kind: 'pending' | 'network' | 'invalid' | 'business'; status: number | null; code: string | null
  constructor(kind: ClientError['kind'], message: string, status: number | null = null, code: string | null = null) { super(message); this.kind = kind; this.status = status; this.code = code }
}
export function createHttpClient(fetcher: typeof fetch = fetch, signal?: AbortSignal): ApiClient {
  async function request<T>(path: string, check: (x: unknown) => boolean, method = 'GET', body?: unknown): Promise<T> {
    let response: Response
    try {
      response = await fetcher(path, { method, signal, headers: body === undefined ? {} : { 'Content-Type': 'application/json' }, ...(body === undefined ? {} : { body: JSON.stringify(body) }) })
    } catch (error) {
      if (signal?.aborted) throw error
      throw new ClientError('network', method === 'GET' ? '连接失败，请检查服务后重新读取。' : '连接失败，操作结果尚未确认。请刷新任务列表后再决定是否重试。')
    }
    if (response.status === 501) throw new ClientError('pending', '该功能后端尚未实现。草稿保留，未切换模拟数据。', 501)
    let value: unknown
    try { value = await response.json() } catch (error) {
      if (signal?.aborted) throw error
      if (error instanceof TypeError) throw new ClientError('network', method === 'GET' ? '响应读取中断，请重新读取。' : '响应读取中断，操作结果尚未确认。请刷新任务列表后再决定是否重试。')
      throw new ClientError(response.ok ? 'invalid' : 'business', '接口返回了无法读取的响应。', response.status)
    }
    if (!response.ok) {
      throw new ClientError('business', record(value) && text(value.message) ? value.message as string : '接口请求未成功。', response.status, record(value) && text(value.error_code) ? value.error_code as string : null)
    }
    if (!check(value)) throw new ClientError('invalid', '接口响应与已声明的数据契约不一致，已停止展示该结果。', response.status)
    return value as T
  }
  const path = (id: string) => `/api/checks/${encodeURIComponent(id)}`
  const sameId = (id: string, validator: (x: unknown) => boolean) => (x: unknown) => validator(x) && record(x) && x.id === id
  const packetMode = (id: string, mode: string, recipient: string | null = null) => (x: unknown) => validatePacket(x) && record(x) && x.case_id === id && record(x.input) && x.input.privacy === mode && x.input.recipient === recipient
  return {
    resolveSource: doi => request(`/api/sources/resolve?doi=${encodeURIComponent(doi)}`, validateSource),
    getRunConfig: () => request('/api/run-config', validateConfig),
    createCheck: body => request('/api/checks', validateCreated, 'POST', body),
    listChecks: status => request(`/api/checks${status ? `?status=${encodeURIComponent(status)}` : ''}`, validateHistory),
    getCheck: id => request(path(id), sameId(id, validateDetail)),
    getDiagnosticPacket: id => request(`${path(id)}/diagnostic-packet`, packetMode(id, 'redacted')),
    exportDiagnosticPacket: (id, body) => request(`${path(id)}/diagnostic-export`, packetMode(id, 'consented', body.recipient), 'POST', body),
    saveFeedback: (id, body) => request(`${path(id)}/feedback`, sameId(id, validateSaved), 'POST', body),
    retryCheck: (id, body) => request(`${path(id)}/retry`, x => validateRetry(x) && record(x) && x.previous_id === id && x.id !== id, 'POST', body),
    cancelCheck: id => request(`${path(id)}/cancel`, sameId(id, validateCancel), 'POST'),
    deleteCheck: id => request(path(id), sameId(id, validateDeleted), 'DELETE'),
  }
}
