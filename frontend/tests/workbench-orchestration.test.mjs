import test, { describe } from 'node:test'
import assert from 'node:assert/strict'
import { ClientError } from '../src/api/http.ts'

// Vue's DOM runtime captures `document` at import time. Install the stub first, then import Vue,
// so the composable can mount under Node's built-in test runner without a browser or a new dependency.
installMountDom()
process.env.NODE_ENV ??= 'production'
const { createApp, h } = await import('vue')
const { useWorkbench } = await import('../src/state/workbench.ts')

const limits = { main_requests: 3, repair_requests: 1, attempts_per_request: 2, supplemental_rounds: 1 }
const criteria = { version: 'criteria', digest: 'digest', snapshot_ref: 'snap', implementation_revision: 'rev' }
const accounting = { verification: 'unverified', main_requests_used: 0, repair_requests_used: 0, supplemental_rounds_used: 0, upstream_attempts_used: null, observed_upstream_attempts: 0, reason: 'attempt_records_missing' }

function runConfig(digest = 'digest-1') {
  return {
    profile: 'daily', config_digest: digest, primary_recipient: '本地接收方', fallback_recipients: ['备用接收方'],
    model_alias: 'alias', data_scope: ['论断原句'], limits,
    timeouts: { model_attempt_seconds: 45, source_request_seconds: 15, task_seconds: 180 },
    observability: { langfuse_enabled: false, recipient: null }, criteria,
  }
}
function taskDetail(id, status, extra = {}) {
  return {
    id, status, stage: status === 'QUEUED' ? 'wait' : status === 'BLOCKED' ? 'license' : 'retrieval',
    label: status === 'COMPLETED' ? '部分支持' : status === 'BLOCKED' ? '无法核验来源' : null,
    error_code: status === 'BLOCKED' ? 'LICENSE_UNKNOWN' : status === 'FAILED' ? 'RETRIEVAL_FAILED' : null,
    decision: null, previous_id: null, cancel_requested: status === 'CANCELLED', criteria, accounting, limits, ...extra,
  }
}
function createScriptedClient() {
  const calls = []
  const tasks = new Map()
  const overrides = {}
  let seq = 0
  function storeTask(body, id = `task-${++seq}`) {
    tasks.set(id, { doi: body.doi, claim: body.claim ?? '', detail: taskDetail(id, 'QUEUED', { previous_id: body.previous_id ?? null }) })
    return { id, status: 'QUEUED' }
  }
  const api = {
    calls, tasks, overrides, storeTask,
    async resolveSource(doi) {
      calls.push(['resolveSource', doi])
      if (overrides.resolveSource) return overrides.resolveSource(doi)
      return { doi, title: '文献', authors: ['甲'], year: 2020 }
    },
    async getRunConfig() {
      calls.push(['getRunConfig'])
      if (overrides.getRunConfig) return overrides.getRunConfig()
      return runConfig()
    },
    async createCheck(body) {
      calls.push(['createCheck', body])
      if (overrides.createCheck) return overrides.createCheck(body)
      return storeTask(body)
    },
    async listChecks() {
      calls.push(['listChecks'])
      if (overrides.listChecks) return overrides.listChecks()
      return [...tasks.values()].map(task => ({ id: task.detail.id, doi: task.doi, status: task.detail.status, stage: task.detail.stage, label: task.detail.label }))
    },
    async getCheck(id) {
      calls.push(['getCheck', id])
      if (overrides.getCheck) return overrides.getCheck(id)
      const task = tasks.get(id)
      if (!task) throw new ClientError('business', '任务不存在。', 404)
      return structuredClone(task.detail)
    },
    async getDiagnosticPacket() { throw new ClientError('business', '未准备诊断包。', 404) },
    async exportDiagnosticPacket(id, body) {
      calls.push(['exportDiagnosticPacket', id, body])
      if (overrides.exportDiagnosticPacket) return overrides.exportDiagnosticPacket(id, body)
      return { case_id: id }
    },
    async saveFeedback(id, body) { calls.push(['saveFeedback', id, body]); return { id, saved: true } },
    async retryCheck(id, body) {
      calls.push(['retryCheck', id, body])
      if (overrides.retryCheck) return overrides.retryCheck(id, body)
      const old = tasks.get(id)
      const created = storeTask({ ...body, claim: old?.claim ?? '', doi: old?.doi ?? '', previous_id: id })
      return { ...created, previous_id: id }
    },
    async cancelCheck(id) {
      calls.push(['cancelCheck', id])
      if (overrides.cancelCheck) return overrides.cancelCheck(id)
      const task = tasks.get(id)
      task.detail = taskDetail(id, 'CANCELLED', { previous_id: task.detail.previous_id })
      return structuredClone(task.detail)
    },
    async deleteCheck(id) {
      calls.push(['deleteCheck', id])
      tasks.delete(id)
      return { id, deleted: true, message: '已删除' }
    },
  }
  api.clientFor = () => api
  return api
}
function createHost(hash = '') {
  const hashListeners = new Set()
  const visibilityListeners = new Set()
  let current = hash
  const location = {
    get hash() { return current },
    set hash(value) {
      const next = value.startsWith('#') ? value : `#${value}`
      if (next === current) return
      current = next
      for (const listener of [...hashListeners]) listener()
    },
  }
  const hostWindow = {
    addEventListener(type, listener) { if (type === 'hashchange') hashListeners.add(listener) },
    removeEventListener(type, listener) { hashListeners.delete(listener) },
  }
  const hostDocument = {
    hidden: false,
    addEventListener(type, listener) { if (type === 'visibilitychange') visibilityListeners.add(listener) },
    removeEventListener(type, listener) { visibilityListeners.delete(listener) },
    setHidden(hidden) {
      this.hidden = hidden
      for (const listener of [...visibilityListeners]) listener()
    },
  }
  return { location, window: hostWindow, document: hostDocument }
}
function mountWorkbench(options) {
  let work
  const app = createApp({
    setup() {
      work = useWorkbench(options)
      return () => h('div')
    },
  })
  app.mount(document.createElement('div'))
  return { work, unmount: () => app.unmount() }
}
async function until(predicate, label) {
  const start = Date.now()
  while (!predicate()) {
    if (Date.now() - start > 1000) throw new Error(`timed out waiting for ${label}`)
    await new Promise(resolve => setTimeout(resolve, 5))
  }
}
const named = (api, name) => api.calls.filter(call => call[0] === name)
function session(hash, extra = {}) {
  const host = createHost(hash)
  const api = createScriptedClient()
  let mounted = null
  return {
    host, api,
    mount(more = {}) {
      mounted = mountWorkbench({ location: host.location, document: host.document, window: host.window, pollIntervalMs: 5, client: signal => api.clientFor(signal), ...extra, ...more })
      return mounted
    },
    unmount() { mounted?.unmount() },
  }
}

describe('useWorkbench orchestration', { concurrency: 1 }, () => {
  test('submit sends the normalized claim and keeps it on the new history row', async () => {
    const s = session('')
    const { api } = s
    const { work } = s.mount()
    try {
      await until(() => named(api, 'listChecks').length >= 1, 'history')
      work.changeDoi('not-a-doi')
      await work.resolve()
      assert.match(work.message.value, /有效 DOI/)
      assert.equal(named(api, 'resolveSource').length, 0)
      work.changeClaim('论断在指定条件下成立')
      work.changeDoi('https://doi.org/10.1000/AbC')
      await work.resolve()
      assert.equal(work.draft.doi, '10.1000/AbC')
      assert.equal(work.draft.source.title, '文献')
      work.draft.sourceConfirmed = true
      work.draft.cloudConsent = true
      let reads = 0
      api.overrides.getCheck = id => {
        const task = api.tasks.get(id)
        reads += 1
        if (reads > 1) task.detail = taskDetail(id, 'COMPLETED', { previous_id: task.detail.previous_id })
        return structuredClone(task.detail)
      }
      await work.submit()
      const body = named(api, 'createCheck')[0][1]
      assert.equal(named(api, 'createCheck').length, 1)
      assert.equal(body.doi, '10.1000/AbC')
      assert.equal(body.claim, '论断在指定条件下成立')
      assert.equal(body.config_digest, 'digest-1')
      assert.deepEqual(body.authorized_recipients, ['本地接收方'])
      assert.equal(body.cloud_consent, true)
      assert.equal(body.source_confirmed, true)
      assert.equal(body.previous_id, null)
      assert.equal(work.draft.claim, '')
      assert.equal(work.route.value.id, 'task-1')
      assert.equal(work.history.value.find(row => row.id === 'task-1').doi, '10.1000/AbC')
      await until(() => work.detail.value?.status === 'COMPLETED', 'completed')
      assert.equal(work.context.value.doi, '10.1000/AbC')
      assert.equal(work.context.value.claim, '论断在指定条件下成立')
      const stoppedAt = named(api, 'getCheck').length
      await new Promise(resolve => setTimeout(resolve, 40))
      assert.equal(named(api, 'getCheck').length, stoppedAt)
    } finally { s.unmount() }
  })

  test('a submit that is already in flight does not send a second create', async () => {
    const s = session('')
    const { api } = s
    let release
    api.overrides.createCheck = body => new Promise(resolve => { release = () => resolve(api.storeTask(body)) })
    const { work } = s.mount()
    try {
      await until(() => named(api, 'listChecks').length >= 1, 'history')
      work.changeClaim('论断')
      work.changeDoi('10.1000/once')
      await work.resolve()
      work.draft.sourceConfirmed = true
      work.draft.cloudConsent = true
      const first = work.submit()
      const second = work.submit()
      assert.equal(named(api, 'createCheck').length, 1)
      release()
      await first
      await second
      assert.equal(named(api, 'createCheck').length, 1)
      assert.equal(work.route.value.id, 'task-1')
    } finally { s.unmount() }
  })

  test('polling publishes running updates and stops after the terminal read', async () => {
    const s = session('#/checks/run')
    const { api } = s
    const waiters = []
    api.tasks.set('run', { doi: '10.1000/run', claim: '论断', detail: taskDetail('run', 'RUNNING') })
    api.overrides.getCheck = id => new Promise(resolve => waiters.push({ id, resolve }))
    const { work } = s.mount()
    try {
      await until(() => waiters.length === 1, 'initial read')
      waiters[0].resolve(taskDetail('run', 'RUNNING'))
      await until(() => waiters.length === 2, 'first poll')
      waiters[1].resolve(taskDetail('run', 'RUNNING', { stage: 'decision' }))
      await until(() => work.detail.value?.stage === 'decision', 'running update')
      assert.equal(work.connectionError.value, '')
      waiters[2] || await until(() => waiters.length === 3, 'next poll')
      waiters[2].resolve(taskDetail('run', 'COMPLETED'))
      await until(() => work.detail.value?.status === 'COMPLETED', 'completed')
      await new Promise(resolve => setTimeout(resolve, 40))
      assert.equal(waiters.length, 3)
    } finally { s.unmount() }
  })

  test('polling continues after a recoverable error and stops on invalid, 404, and 409', async () => {
    async function drive(failure, { stops }) {
      const s = session('#/checks/run')
      const { api } = s
      const waiters = []
      api.tasks.set('run', { doi: '10.1000/run', claim: '论断', detail: taskDetail('run', 'RUNNING') })
      api.overrides.getCheck = id => new Promise((resolve, reject) => waiters.push({ id, resolve, reject }))
      const { work } = s.mount()
      try {
        await until(() => waiters.length === 1, 'initial read')
        waiters[0].resolve(taskDetail('run', 'RUNNING'))
        await until(() => waiters.length === 2, 'poll')
        waiters[1].reject(failure)
        if (stops) {
          await until(() => work.connectionError.value.includes('已停止自动刷新'), failure.message)
          await new Promise(resolve => setTimeout(resolve, 40))
          assert.equal(waiters.length, 2)
          assert.match(work.connectionError.value, /已停止自动刷新/)
        } else {
          await until(() => work.connectionError.value === failure.message, failure.message)
          await until(() => waiters.length === 3, 'continued poll')
          assert.equal(work.detail.value.status, 'RUNNING')
          waiters[2].resolve(taskDetail('run', 'COMPLETED'))
          await until(() => work.detail.value.status === 'COMPLETED', 'recovered')
          assert.equal(work.connectionError.value, '')
        }
      } finally { s.unmount() }
    }
    await drive(new ClientError('network', '连接失败，请检查服务后重新读取。', null), { stops: false })
    await drive(new ClientError('business', '上游暂不可用。', 503), { stops: false })
    await drive(new ClientError('invalid', '接口响应与已声明的数据契约不一致，已停止展示该结果。', 200), { stops: true })
    await drive(new ClientError('business', '任务不存在。', 404), { stops: true })
    await drive(new ClientError('business', '任务已结束。', 409), { stops: true })
  })

  test('a late read after navigation does not replace the task on screen', async () => {
    const host = createHost('#/checks/a')
    const api = createScriptedClient()
    const signals = new Map()
    const waiters = []
    api.overrides.getCheck = id => new Promise(resolve => waiters.push({ id, resolve }))
    api.clientFor = signal => {
      const bound = {
        ...api,
        getCheck: id => {
          signals.set(id, signal)
          return api.overrides.getCheck(id)
        },
      }
      return bound
    }
    const { work, unmount } = mountWorkbench({ location: host.location, document: host.document, window: host.window, pollIntervalMs: 5, client: signal => api.clientFor(signal) })
    try {
      await until(() => waiters.some(item => item.id === 'a'), 'read a')
      host.location.hash = '#/checks/b'
      await until(() => waiters.some(item => item.id === 'b'), 'read b')
      assert.equal(signals.get('a').aborted, true)
      waiters.find(item => item.id === 'b').resolve(taskDetail('b', 'COMPLETED'))
      await until(() => work.detail.value?.id === 'b', 'show b')
      waiters.find(item => item.id === 'a').resolve(taskDetail('a', 'RUNNING'))
      await new Promise(resolve => setTimeout(resolve, 30))
      assert.equal(work.detail.value.id, 'b')
      assert.equal(work.detail.value.status, 'COMPLETED')
      assert.equal(work.message.value, '')
    } finally { unmount() }
  })

  test('retry calls retryCheck and the new history row keeps the source DOI', async () => {
    const s = session('#/checks/done')
    const { api } = s
    api.tasks.set('done', { doi: '10.1000/done', claim: '原论断', detail: taskDetail('done', 'COMPLETED') })
    const { work } = s.mount()
    try {
      await until(() => work.detail.value?.id === 'done' && work.history.value.some(row => row.id === 'done'), 'loaded')
      work.prepareEdit(false, true)
      assert.equal(work.route.value.view, 'new')
      assert.equal(work.draft.retryId, 'done')
      assert.equal(work.draft.doi, '10.1000/done')
      assert.equal(work.draft.claim, '')
      await work.resolve()
      work.draft.sourceConfirmed = true
      work.draft.cloudConsent = true
      await work.submit()
      assert.equal(named(api, 'createCheck').length, 0)
      const [retryId, body] = named(api, 'retryCheck')[0].slice(1)
      assert.equal(retryId, 'done')
      assert.equal(body.claim, undefined)
      assert.equal(body.doi, undefined)
      assert.equal(body.config_digest, 'digest-1')
      assert.equal(body.cloud_consent, true)
      assert.equal(work.route.value.id, 'task-1')
      assert.equal(work.history.value.find(row => row.id === 'task-1').doi, '10.1000/done')
      assert.equal(work.context.value.doi, '10.1000/done')
      assert.equal(work.context.value.claim, null)
    } finally { s.unmount() }
  })

  test('cancel publishes the cancelled task and a cancel failure resumes polling', async () => {
    const s = session('#/checks/run')
    const { api } = s
    api.tasks.set('run', { doi: '10.1000/run', claim: '论断', detail: taskDetail('run', 'RUNNING') })
    const { work } = s.mount()
    try {
      await until(() => work.detail.value?.status === 'RUNNING', 'running')
      await work.cancel()
      assert.equal(work.detail.value.status, 'CANCELLED')
      assert.equal(work.history.value.find(row => row.id === 'run').status, 'CANCELLED')
      const stoppedAt = named(api, 'getCheck').length
      await new Promise(resolve => setTimeout(resolve, 40))
      assert.equal(named(api, 'getCheck').length, stoppedAt)
    } finally { s.unmount() }

    const failed = session('#/checks/run')
    failed.api.tasks.set('run', { doi: '10.1000/run', claim: '论断', detail: taskDetail('run', 'RUNNING') })
    failed.api.overrides.cancelCheck = () => { throw new ClientError('business', '任务已结束，无法取消。', 409) }
    const failedWork = failed.mount()
    try {
      await until(() => failedWork.work.detail.value?.status === 'RUNNING', 'running again')
      const before = named(failed.api, 'getCheck').length
      await failedWork.work.cancel()
      assert.equal(failedWork.work.message.value, '任务已结束，无法取消。')
      assert.equal(failedWork.work.detail.value.status, 'RUNNING')
      await until(() => named(failed.api, 'getCheck').length > before, 'polling resumed')
    } finally { failed.unmount() }
  })

  test('config conflict refreshes the draft and an unimplemented create does not enter demo mode', async () => {
    const conflict = session('')
    let configs = 0
    conflict.api.overrides.getRunConfig = () => runConfig(configs++ === 0 ? 'old' : 'new')
    conflict.api.overrides.createCheck = () => { throw new ClientError('business', '配置已变化，请重新确认。', 409) }
    const conflictWork = conflict.mount()
    try {
      await until(() => named(conflict.api, 'listChecks').length >= 1, 'history')
      conflictWork.work.changeClaim('论断')
      conflictWork.work.changeDoi('10.1000/conflict')
      await conflictWork.work.resolve()
      assert.equal(conflictWork.work.draft.config.config_digest, 'old')
      conflictWork.work.draft.sourceConfirmed = true
      conflictWork.work.draft.cloudConsent = true
      await conflictWork.work.submit()
      assert.equal(conflictWork.work.message.value, '配置已变化，请重新确认。')
      assert.equal(conflictWork.work.draft.cloudConsent, false)
      assert.equal(conflictWork.work.draft.config.config_digest, 'new')
      assert.equal(conflictWork.work.route.value.view, 'new')
      assert.equal(conflictWork.work.demo, false)
    } finally { conflict.unmount() }

    const pending = session('')
    pending.api.overrides.createCheck = () => { throw new ClientError('pending', '该功能后端尚未实现。草稿保留，未切换模拟数据。', 501) }
    const pendingWork = pending.mount()
    try {
      await until(() => named(pending.api, 'listChecks').length >= 1, 'history')
      pendingWork.work.changeClaim('论断保留')
      pendingWork.work.changeDoi('10.1000/pending')
      await pendingWork.work.resolve()
      pendingWork.work.draft.sourceConfirmed = true
      pendingWork.work.draft.cloudConsent = true
      await pendingWork.work.submit()
      assert.equal(pendingWork.work.message.value, '该功能后端尚未实现。草稿保留，未切换模拟数据。')
      assert.equal(pendingWork.work.draft.claim, '论断保留')
      assert.equal(pendingWork.work.draft.cloudConsent, true)
      assert.equal(pendingWork.work.route.value.view, 'new')
      assert.equal(pendingWork.work.demo, false)
      assert.equal(named(pending.api, 'createCheck').length, 1)
    } finally { pending.unmount() }
  })

  test('a hidden page does not start polling and a malformed hash is reported', async () => {
    const host = createHost('#/checks/run')
    host.document.hidden = true
    const api = createScriptedClient()
    api.clientFor = () => api
    api.tasks.set('run', { doi: '10.1000/run', claim: '论断', detail: taskDetail('run', 'RUNNING') })
    const pollers = []
    function createPoller(read, receive, fail, interval) {
      const record = { read, receive, fail, interval, starts: 0, stops: 0, start() { this.starts += 1 }, stop() { this.stops += 1 } }
      pollers.push(record)
      return record
    }
    const hidden = mountWorkbench({ location: host.location, document: host.document, window: host.window, pollIntervalMs: 5, client: () => api, createPoller })
    try {
      await until(() => hidden.work.detail.value?.status === 'RUNNING', 'loaded while hidden')
      assert.equal(pollers.length, 1)
      assert.equal(pollers[0].starts, 0)
      assert.equal(pollers[0].interval, 5)
      host.document.setHidden(false)
      await until(() => pollers.length === 2 && pollers[1].starts === 1, 'visible restart')
      assert.equal(pollers[0].stops, 1)
    } finally { hidden.unmount() }

    const bad = session('#/checks/%E4')
    const badWork = bad.mount()
    try {
      await until(() => badWork.work.message.value.includes('无法识别'), 'invalid hash')
      assert.equal(badWork.work.route.value.invalid, true)
      assert.equal(badWork.work.detail.value, null)
      assert.equal(named(bad.api, 'getCheck').length, 0)
    } finally { bad.unmount() }
  })

  test('an injected client replaces demo mode, and demo mode without one stays on the in-memory client', async () => {
    const injected = session('')
    const mounted = injected.mount({ mode: 'demo' })
    try {
      await until(() => named(injected.api, 'listChecks').length >= 1, 'injected history')
      assert.equal(mounted.work.demo, false)
      assert.deepEqual(mounted.work.history.value, [])
    } finally { injected.unmount() }

    const host = createHost('')
    const demo = mountWorkbench({ location: host.location, document: host.document, window: host.window, pollIntervalMs: 5, mode: 'demo' })
    try {
      await until(() => demo.work.history.value.length === 10, 'demo history')
      assert.equal(demo.work.demo, true)
      assert.equal(demo.work.history.value[0].doi, '10.0000/demo-1')
      demo.work.selectScenario('执行中')
      assert.equal(demo.work.scenario.value, '执行中')
    } finally { demo.unmount() }
  })

  test('semantic export requires the consent flag before it calls the client', async () => {
    const s = session('#/checks/done')
    const { api } = s
    api.tasks.set('done', { doi: '10.1000/done', claim: '原论断', detail: taskDetail('done', 'COMPLETED') })
    const { work } = s.mount()
    try {
      await until(() => work.detail.value?.id === 'done', 'loaded')
      const refused = await work.semanticExport('本地评审', false)
      assert.equal(refused, null)
      assert.match(work.message.value, /授权/)
      assert.equal(named(api, 'exportDiagnosticPacket').length, 0)
      api.overrides.exportDiagnosticPacket = () => { throw new ClientError('business', '接收方未授权。', 400) }
      const failed = await work.semanticExport('本地评审', true)
      assert.equal(failed, null)
      assert.equal(work.message.value, '接收方未授权。')
      assert.equal(named(api, 'exportDiagnosticPacket').length, 1)
      assert.equal(named(api, 'exportDiagnosticPacket')[0][2].semantic_export_consent, true)
    } finally { s.unmount() }
  })
})

function installMountDom() {
  function el(name) {
    const node = {
      nodeType: name === '#comment' ? 8 : name === '#text' ? 3 : 1,
      nodeName: String(name).toUpperCase(),
      tagName: String(name).toUpperCase(),
      textContent: '',
      data: '',
      nodeValue: '',
      childNodes: [],
      parentNode: null,
      style: {},
      classList: { add() {}, remove() {} },
      setAttribute() {},
      removeAttribute() {},
      getAttribute() { return null },
      addEventListener() {},
      removeEventListener() {},
      insertBefore(child, refNode) {
        if (child.parentNode) child.parentNode.removeChild(child)
        child.parentNode = node
        const index = refNode ? node.childNodes.indexOf(refNode) : -1
        if (index >= 0) node.childNodes.splice(index, 0, child)
        else node.childNodes.push(child)
        return child
      },
      appendChild(child) { return node.insertBefore(child, null) },
      removeChild(child) {
        node.childNodes = node.childNodes.filter(item => item !== child)
        child.parentNode = null
        return child
      },
    }
    Object.defineProperty(node, 'nextSibling', { get() { if (!node.parentNode) return null; const kids = node.parentNode.childNodes; return kids[kids.indexOf(node) + 1] ?? null } })
    return node
  }
  class Element {}
  class SVGElement {}
  globalThis.Element = Element
  globalThis.SVGElement = SVGElement
  globalThis.document = {
    createElement: name => el(name),
    createElementNS: (_namespace, name) => el(name),
    createTextNode: text => { const node = el('#text'); node.textContent = text; node.data = text; node.nodeValue = text; return node },
    createComment: text => { const node = el('#comment'); node.textContent = text; node.data = text; node.nodeValue = text; return node },
    querySelector: () => null,
    body: el('body'),
    hidden: false,
    addEventListener() {},
    removeEventListener() {},
  }
  globalThis.window = { document: globalThis.document }
}
