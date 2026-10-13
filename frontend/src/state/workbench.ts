import { computed, onMounted, onUnmounted, reactive, ref } from 'vue'
import type { ApiClient, CheckDetail, CheckInput, CheckSummary, DiagnosticPacket, EvidenceContext } from '../api/contracts.ts'
import { createHttpClient, ClientError, pollingShouldStop } from '../api/http.ts'
import { createDemoClient, type DemoScenario } from '../api/demo.ts'
import { canSubmit, createDraft, diagnosticExportRequest, invalidateDraft, isTerminal, normalizeDoi, originalClaim, originalDoi, parseRoute, validDoi, type SubmissionContext } from './model.ts'
import { createPoller, POLL_INTERVAL_MS } from './poller.ts'

/** Browser pieces the page already provides. Tests pass fakes; omitted values stay the page globals. */
export interface WorkbenchHost {
  location?: { hash: string }
  document?: { hidden: boolean; addEventListener(type: string, listener: () => void): void; removeEventListener(type: string, listener: () => void): void }
  window?: { addEventListener(type: string, listener: () => void): void; removeEventListener(type: string, listener: () => void): void }
}
/**
 * Optional dependencies for orchestration tests.
 * The app calls useWorkbench() with no arguments, so demo mode, the HTTP client, and the poller stay on the page path.
 * A supplied client is used as given and does not switch the page into demo mode.
 */
export interface WorkbenchOptions extends WorkbenchHost {
  /** Vite mode. Omitted reads import.meta.env.MODE. Only `demo` selects the in-memory client. */
  mode?: string
  /**
   * Client instance, or a factory called once for mutations and again per read with that read's AbortSignal.
   * Omitted uses the demo client when mode is `demo`, otherwise createHttpClient.
   */
  client?: ApiClient | ((signal?: AbortSignal) => ApiClient)
  /** Poller factory. Omitted uses createPoller. */
  createPoller?: typeof createPoller
  /** Poll spacing in milliseconds. Omitted uses POLL_INTERVAL_MS. */
  pollIntervalMs?: number
  fetch?: typeof fetch
}
export function useWorkbench(options: WorkbenchOptions = {}) {
  const mode = options.mode ?? import.meta.env?.MODE
  // An injected client stays in charge. Demo mode applies only when the caller leaves the client unset.
  const demo = options.client == null && mode === 'demo'
  const simulation = demo ? createDemoClient() : null
  const fetchImpl = options.fetch ?? fetch
  const supplied = options.client
  const api: ApiClient = simulation ?? (typeof supplied === 'function' ? supplied() : supplied ?? createHttpClient(fetchImpl))
  const location = options.location ?? globalThis.location
  const document = options.document ?? globalThis.document
  const window = options.window ?? globalThis.window
  const startPoller = options.createPoller ?? createPoller
  const pollInterval = options.pollIntervalMs ?? POLL_INTERVAL_MS
  const route = ref(parseRoute(location.hash)); const draft = reactive(createDraft())
  const history = ref<CheckSummary[]>([]); const detail = ref<CheckDetail | null>(null); const packet = ref<DiagnosticPacket | null>(null)
  const submittedInput = ref<CheckInput | null>(null); const evidenceContext = ref<EvidenceContext | null>(null)
  const contexts = reactive(new Map<string, SubmissionContext>())
  const scenario = ref<DemoScenario>('部分支持')
  const loading = ref(false); const resolving = ref(false); const busy = ref(false)
  const submittedInputLoading = ref(false); const evidenceContextLoading = ref(false)
  const message = ref(''); const historyError = ref(''); const connectionError = ref('')
  const submittedInputError = ref(''); const evidenceContextError = ref('')
  const context = computed(() => route.value.id ? contexts.get(route.value.id) ?? null : null)
  let reads: AbortController | null = null; let previewReads: AbortController | null = null; let historyReads: AbortController | null = null; let packetReads: AbortController | null = null
  let submittedReads: AbortController | null = null; let contextReads: AbortController | null = null
  let routeVersion = 0; let previewVersion = 0; let historyVersion = 0
  let activeId: string | null = null; let contextWatched = false
  let poll: ReturnType<typeof createPoller<CheckDetail>> | null = null
  function client(signal: AbortSignal): ApiClient {
    if (simulation) return simulation
    if (typeof supplied === 'function') return supplied(signal)
    if (supplied) return supplied
    return createHttpClient(fetchImpl, signal)
  }
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
  function releaseProjectionReads() {
    submittedReads?.abort(); contextReads?.abort(); submittedInputLoading.value = false; evidenceContextLoading.value = false
  }
  /**
   * Input and context belong to one task. A visibility reload keeps a projection that already landed.
   * loadRoute bumps the route version first, so an in-flight read cannot land; if it had no data yet, start it again.
   */
  function adoptRoute() {
    const nextId = route.value.invalid ? null : route.value.id
    const retryInput = submittedInputLoading.value && submittedInput.value === null
    const retryContext = evidenceContextLoading.value && evidenceContext.value === null
    releaseProjectionReads()
    if (nextId === activeId) {
      if (retryInput) void loadSubmittedInput(true)
      if (retryContext) void loadEvidenceContext(true)
      return
    }
    activeId = nextId; contextWatched = false
    submittedInput.value = null; submittedInputError.value = ''
    evidenceContext.value = null; evidenceContextError.value = ''
  }
  async function loadRoute() {
    const version = ++routeVersion; reads?.abort(); packetReads?.abort(); abortPreview(); poll?.stop(); poll = null
    detail.value = null; packet.value = null; message.value = ''; connectionError.value = ''; loading.value = false
    adoptRoute()
    if (route.value.invalid) { message.value = '链接中的任务标识无法识别，已打开新的核验。'; return }
    const { id, view } = route.value; if (!id) return
    reads = new AbortController(); const signal = reads.signal; loading.value = true
    try {
      const c = client(signal); const result = await c.getCheck(id)
      if (version !== routeVersion) return
      detail.value = result
      if (view === 'diagnostic') { const data = await c.getDiagnosticPacket(id); if (version === routeVersion) packet.value = data }
      if (!isTerminal(result.status)) {
        poll = startPoller(s => client(s).getCheck(id), value => {
          if (version !== routeVersion) return
          const previous = detail.value
          detail.value = value; connectionError.value = ''
          if (contextWatched && previous && (previous.status !== value.status || previous.stage !== value.stage)) void loadEvidenceContext(true)
          if (isTerminal(value.status)) {
            void refreshHistory()
            if (view === 'diagnostic') void refreshPacket(id, version)
          }
        }, error => {
          const reason = describe(error)
          if (pollingShouldStop(error)) { connectionError.value = `${reason} 已停止自动刷新。`; poll?.stop(); return }
          connectionError.value = reason
        }, pollInterval)
        if (!document.hidden) poll.start()
      }
    } catch (error) { if (version === routeVersion && !signal.aborted) message.value = describe(error) }
    finally { if (version === routeVersion) loading.value = false }
  }
  /** The frozen digest is only for display. Retry and revise keep using the current preview. */
  async function loadSubmittedInput(force = false) {
    const id = route.value.id
    if (!id) return
    if (!force && (submittedInputLoading.value || (submittedInput.value?.id === id && !submittedInputError.value))) return
    const version = routeVersion; submittedReads?.abort(); const controller = new AbortController(); submittedReads = controller
    submittedInputLoading.value = true; submittedInputError.value = ''
    if (submittedInput.value?.id !== id) submittedInput.value = null
    try {
      const value = await client(controller.signal).getCheckInput(id)
      if (version !== routeVersion || controller.signal.aborted) return
      submittedInput.value = value
    } catch (error) {
      if (version !== routeVersion || controller.signal.aborted) return
      submittedInput.value = null; submittedInputError.value = describe(error)
    } finally { if (version === routeVersion && submittedReads === controller) submittedInputLoading.value = false }
  }
  async function loadEvidenceContext(force = false) {
    const id = route.value.id
    if (!id) return
    contextWatched = true
    if (!force && (evidenceContextLoading.value || (evidenceContext.value?.id === id && !evidenceContextError.value))) return
    const version = routeVersion; contextReads?.abort(); const controller = new AbortController(); contextReads = controller
    evidenceContextLoading.value = true; evidenceContextError.value = ''
    if (evidenceContext.value?.id !== id) evidenceContext.value = null
    try {
      const value = await client(controller.signal).getEvidenceContext(id)
      if (version !== routeVersion || controller.signal.aborted) return
      evidenceContext.value = value
    } catch (error) {
      if (version !== routeVersion || controller.signal.aborted) return
      evidenceContext.value = null; evidenceContextError.value = describe(error)
    } finally { if (version === routeVersion && contextReads === controller) evidenceContextLoading.value = false }
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
    const row = history.value.find(x => x.id === id); const cached = contexts.get(id) ?? null
    const loaded = detail.value?.id === id ? detail.value : null
    const doi = originalDoi(cached, row?.doi, loaded)
    if (!doi) { message.value = '无法读取原任务 DOI，请刷新本地历史后再重新核验。'; return }
    // Retry replays the stored input on the backend, so its draft intentionally carries no claim.
    const claim = retry ? cached?.claim ?? '' : originalClaim(cached, loaded)
    if (!claim && !retry) { message.value = '无法读取原任务论断，请刷新任务详情后再修改或拆分。'; return }
    Object.assign(draft, createDraft(), { doi, claim, previousId: id, retryId: retry ? id : null })
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
  async function semanticExport(recipient: string, consent: boolean, authorizedPacket: DiagnosticPacket | null): Promise<DiagnosticPacket | null> {
    const id = route.value.id
    if (!id || busy.value) { message.value = '当前无法导出语义诊断包。'; return null }
    let request
    try { request = diagnosticExportRequest(packet.value, id, recipient, consent, authorizedPacket) }
    catch (error) { message.value = error instanceof Error ? error.message : '当前无法导出语义诊断包。'; return null }
    const version = routeVersion; busy.value = true
    try {
      const data = await api.exportDiagnosticPacket(id, request)
      if (version !== routeVersion) { message.value = '页面已切换，这次导出结果未使用。'; return null }
      try { diagnosticExportRequest(packet.value, route.value.id, recipient, consent, authorizedPacket) }
      catch (error) { message.value = error instanceof Error ? error.message : '诊断包已变化，请重新预览并授权。'; return null }
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
  onUnmounted(() => { routeVersion++; historyVersion++; reads?.abort(); historyReads?.abort(); packetReads?.abort(); submittedReads?.abort(); contextReads?.abort(); abortPreview(); poll?.stop(); window.removeEventListener('hashchange', hashChanged); document.removeEventListener('visibilitychange', visibilityChanged) })
  return { demo, scenario, route, draft, history, detail, packet, submittedInput, evidenceContext, context, loading, resolving, busy, submittedInputLoading, evidenceContextLoading, message, historyError, connectionError, submittedInputError, evidenceContextError, changeClaim, changeDoi, resolve, submit, navigate, startNew, prepareEdit, cancel, remove, feedback, semanticExport, selectScenario, refreshHistory, refreshPacket, loadSubmittedInput, loadEvidenceContext, reload: loadRoute }
}
export type Workbench = ReturnType<typeof useWorkbench>
