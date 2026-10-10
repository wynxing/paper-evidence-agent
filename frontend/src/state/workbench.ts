import { computed, onMounted, onUnmounted, reactive, ref } from 'vue'
import type { ApiClient, CheckDetail, CheckSummary, DiagnosticPacket } from '../api/contracts.ts'
import { createHttpClient, ClientError, pollingShouldStop } from '../api/http.ts'
import { createDemoClient, type DemoScenario } from '../api/demo.ts'
import { canSubmit, createDraft, invalidateDraft, isTerminal, normalizeDoi, parseRoute, validDoi, type SubmissionContext } from './model.ts'
import { createPoller, POLL_INTERVAL_MS } from './poller.ts'

export function useWorkbench() {
  const demo = import.meta.env.MODE === 'demo'; const simulation = demo ? createDemoClient() : null
  const api: ApiClient = simulation ?? createHttpClient()
  const route = ref(parseRoute(location.hash)); const draft = reactive(createDraft())
  const history = ref<CheckSummary[]>([]); const detail = ref<CheckDetail | null>(null); const packet = ref<DiagnosticPacket | null>(null)
  const contexts = reactive(new Map<string, SubmissionContext>())
  const scenario = ref<DemoScenario>('部分支持')
  const loading = ref(false); const resolving = ref(false); const busy = ref(false)
  const message = ref(''); const historyError = ref(''); const connectionError = ref('')
  const context = computed(() => route.value.id ? contexts.get(route.value.id) ?? null : null)
  let reads: AbortController | null = null; let previewReads: AbortController | null = null; let historyReads: AbortController | null = null; let packetReads: AbortController | null = null
  let routeVersion = 0; let previewVersion = 0; let historyVersion = 0
  let poll: ReturnType<typeof createPoller<CheckDetail>> | null = null
  function client(signal: AbortSignal): ApiClient { return simulation ?? createHttpClient(fetch, signal) }
  function describe(error: unknown) { return error instanceof ClientError ? error.message : '操作未完成，请检查连接后重试。' }
  function abortPreview() { previewVersion++; previewReads?.abort(); resolving.value = false }
  function changeClaim(value: string) { draft.claim = value; invalidateDraft(draft, false); abortPreview() }
  function changeDoi(value: string) { draft.doi = value; invalidateDraft(draft, true); abortPreview() }
  async function refreshHistory() {
    const version = ++historyVersion; historyReads?.abort(); historyReads = new AbortController()
    try { const rows = await client(historyReads.signal).listChecks(); if (version === historyVersion) { history.value = rows; historyError.value = '' } }
    catch (error) { if (version === historyVersion && !historyReads?.signal.aborted) historyError.value = describe(error) }
  }
  async function resolve() {
    abortPreview(); message.value = ''; draft.cloudConsent = false; draft.sourceConfirmed = false; draft.source = null; draft.config = null; draft.fallbacks = []
    if (!validDoi(draft.doi)) { message.value = '请输入有效 DOI，例如 10.xxxx/文献标识。'; return }
    draft.doi = normalizeDoi(draft.doi); const version = previewVersion; previewReads = new AbortController(); resolving.value = true
    try {
      const c = client(previewReads.signal); const [source, config] = await Promise.all([c.resolveSource(draft.doi), c.getRunConfig()])
      if (version !== previewVersion) return
      draft.source = source; draft.config = config
    } catch (error) { if (version === previewVersion) message.value = describe(error) }
    finally { if (version === previewVersion) resolving.value = false }
  }
  async function loadRoute() {
    const version = ++routeVersion; reads?.abort(); packetReads?.abort(); abortPreview(); poll?.stop(); poll = null
    detail.value = null; packet.value = null; message.value = ''; connectionError.value = ''; loading.value = false
    if (route.value.invalid) { message.value = '链接中的任务标识无法识别，已打开新的核验。'; return }
    const { id, view } = route.value; if (!id) return
    reads = new AbortController(); const signal = reads.signal; loading.value = true
    try {
      const c = client(signal); const result = await c.getCheck(id)
      if (version !== routeVersion) return
      detail.value = result
      if (view === 'diagnostic') { const data = await c.getDiagnosticPacket(id); if (version === routeVersion) packet.value = data }
      if (!isTerminal(result.status)) {
        poll = createPoller(s => client(s).getCheck(id), value => {
          if (version !== routeVersion) return
          detail.value = value; connectionError.value = ''
          if (isTerminal(value.status)) {
            void refreshHistory()
            if (view === 'diagnostic') void refreshPacket(id, version)
          }
        }, error => {
          const reason = describe(error)
          if (pollingShouldStop(error)) { connectionError.value = `${reason} 已停止自动刷新。`; poll?.stop(); return }
          connectionError.value = reason
        }, POLL_INTERVAL_MS)
        if (!document.hidden) poll.start()
      }
    } catch (error) { if (version === routeVersion && !signal.aborted) message.value = describe(error) }
    finally { if (version === routeVersion) loading.value = false }
  }
  async function refreshPacket(id = route.value.id, version = routeVersion) {
    if (!id) return
    packetReads?.abort(); const controller = new AbortController(); packetReads = controller
    try { const value = await client(controller.signal).getDiagnosticPacket(id); if (version === routeVersion && !controller.signal.aborted) packet.value = value }
    catch (error) { if (version === routeVersion && !controller.signal.aborted) message.value = describe(error) }
  }
  function navigate(id?: string, diagnostic = false) { location.hash = id ? `/checks/${encodeURIComponent(id)}${diagnostic ? '/diagnostic' : ''}` : '/new' }
  function startNew() { abortPreview(); Object.assign(draft, createDraft()); selectScenario('部分支持'); navigate(); message.value = '' }
  function prepareEdit(split = false, retry = false) {
    const id = route.value.id; if (!id) return
    const row = history.value.find(x => x.id === id); const cached = contexts.get(id)
    if (!cached?.doi && !row?.doi) { message.value = '无法读取原任务 DOI，请刷新本地历史后再重新核验。'; return }
    if (!cached?.claim && !retry) { message.value = '当前接口未提供原始论断，无法修改或拆分。'; return }
    Object.assign(draft, createDraft(), { doi: cached?.doi ?? row?.doi ?? '', claim: cached?.claim ?? '', previousId: id, retryId: retry ? id : null })
    navigate(); message.value = split ? '请将原句改为一条可独立判断的子论断并提交。可从原任务再次创建其他子论断。' : ''
  }
  async function submit() {
    if (busy.value || !canSubmit(draft) || !draft.config) return
    busy.value = true; message.value = ''; const version = routeVersion
    const cached: SubmissionContext = { claim: draft.claim || null, doi: draft.doi, source: draft.source ? structuredClone({ ...draft.source, authors: [...draft.source.authors] }) : null }
    const authorization = { config_digest: draft.config.config_digest, authorized_recipients: [draft.config.primary_recipient, ...draft.fallbacks], cloud_consent: draft.cloudConsent, source_confirmed: draft.sourceConfirmed }
    try {
      const created = draft.retryId ? await api.retryCheck(draft.retryId, authorization) : await api.createCheck({ ...authorization, claim: draft.claim.trim(), doi: normalizeDoi(draft.doi), previous_id: draft.previousId })
      contexts.set(created.id, cached); await refreshHistory()
      if (version === routeVersion) { Object.assign(draft, createDraft()); navigate(created.id) }
    } catch (error) {
      if (version !== routeVersion) return
      message.value = describe(error)
      if (error instanceof ClientError && error.status === 409) {
        draft.cloudConsent = false; draft.config = null; draft.fallbacks = []
        const preview = previewVersion
        previewReads = new AbortController(); const signal = previewReads.signal
        try { const config = await client(signal).getRunConfig(); if (version === routeVersion && preview === previewVersion && !signal.aborted) draft.config = config }
        catch (refreshError) { if (version === routeVersion && preview === previewVersion && !signal.aborted) message.value += ` ${describe(refreshError)}` }
      }
    } finally { busy.value = false }
  }
  async function cancel() {
    const id = route.value.id; const version = routeVersion; if (!id || busy.value) return
    busy.value = true; poll?.stop()
    try { const value = await api.cancelCheck(id); if (version === routeVersion && detail.value) { Object.assign(detail.value, value); if (!isTerminal(value.status) && !document.hidden) poll?.start() }; await refreshHistory() }
    catch (error) { if (version === routeVersion) message.value = describe(error) }
    finally { busy.value = false; if (version === routeVersion && detail.value && !isTerminal(detail.value.status) && !document.hidden) poll?.start() }
  }
  async function remove() {
    const id = route.value.id; if (!id || busy.value) return
    const version = routeVersion; busy.value = true
    try { await api.deleteCheck(id); contexts.delete(id); await refreshHistory(); if (version === routeVersion) startNew() }
    catch (error) { if (version === routeVersion) message.value = describe(error) }
    finally { busy.value = false }
  }
  async function feedback(comment: string) {
    const id = route.value.id; const version = routeVersion; if (!id || busy.value || !comment.trim()) return
    busy.value = true
    try { await api.saveFeedback(id, { comment: comment.trim() }); if (version === routeVersion) message.value = '意见已单独保存，不改变核验结果。' }
    catch (error) { if (version === routeVersion) message.value = describe(error) }
    finally { busy.value = false }
  }
  async function semanticExport(recipient: string, consent: boolean): Promise<DiagnosticPacket | null> {
    if (consent !== true) { message.value = '导出语义诊断包前需要确认授权。'; return null }
    const id = route.value.id
    if (!id || busy.value) { message.value = '当前无法导出语义诊断包。'; return null }
    const version = routeVersion; busy.value = true
    try {
      const data = await api.exportDiagnosticPacket(id, { recipient: recipient.trim(), semantic_export_consent: consent })
      if (version !== routeVersion) { message.value = '页面已切换，这次导出结果未使用。'; return null }
      return data
    } catch (error) {
      message.value = version === routeVersion ? describe(error) : '页面已切换，这次导出结果未使用。'
      return null
    } finally { busy.value = false }
  }
  function selectScenario(value: DemoScenario) { scenario.value = value; simulation?.selectScenario(value) }
  function hashChanged() { route.value = parseRoute(location.hash); void loadRoute() }
  function visibilityChanged() { if (document.hidden) { poll?.stop(); reads?.abort(); packetReads?.abort() } else { void loadRoute(); void refreshHistory() } }
  onMounted(() => { window.addEventListener('hashchange', hashChanged); document.addEventListener('visibilitychange', visibilityChanged); void refreshHistory(); void loadRoute() })
  onUnmounted(() => { routeVersion++; historyVersion++; reads?.abort(); historyReads?.abort(); packetReads?.abort(); abortPreview(); poll?.stop(); window.removeEventListener('hashchange', hashChanged); document.removeEventListener('visibilitychange', visibilityChanged) })
  return { demo, scenario, route, draft, history, detail, packet, context, loading, resolving, busy, message, historyError, connectionError, changeClaim, changeDoi, resolve, submit, navigate, startNew, prepareEdit, cancel, remove, feedback, semanticExport, selectScenario, refreshHistory, refreshPacket, reload: loadRoute }
}
export type Workbench = ReturnType<typeof useWorkbench>
