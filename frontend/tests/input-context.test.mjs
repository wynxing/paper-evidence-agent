import test from 'node:test'
import assert from 'node:assert/strict'
import { createHttpClient } from '../src/api/http.ts'
import { createDemoClient } from '../src/api/demo.ts'
import { validateCheckInput, validateEvidenceContext } from '../src/api/validation.ts'
import { anchorWindow, evidenceContextNotice, evidenceContextSummary, paragraphRole } from '../src/state/model.ts'

const paragraph = (id, text, flags = {}) => ({
  paragraph_id: id, section: 'Results', text, paragraph_hash: id, source_url: '',
  entered_context: false, cited: false, ...flags,
})

test('anchor windows follow the ordered context and stay empty when nothing sits beside the quote', () => {
  const only = [paragraph('p1', '冻结原文', { entered_context: true, cited: true })]
  assert.deepEqual(anchorWindow(only, 'p1'), { anchor: only[0], before: null, after: null })
  assert.equal(evidenceContextNotice({ id: 't', source_id: 'src', paragraphs: only }, 'p1'), '当前只返回了该摘录所在段落，没有相邻段落。')
  const around = [paragraph('p0', '前'), only[0], paragraph('p2', '后')]
  const window = anchorWindow(around, 'p1')
  assert.equal(window.before.text, '前')
  assert.equal(window.after.text, '后')
  assert.equal(evidenceContextNotice({ id: 't', source_id: 'src', paragraphs: around }, 'p1'), null)
  assert.equal(evidenceContextNotice({ id: 't', source_id: 'src', paragraphs: around }, 'missing'), '这段摘录不在当前返回的证据上下文中。')
  assert.deepEqual(anchorWindow([], 'p1'), { anchor: null, before: null, after: null })
})

test('empty evidence context says whether a source is frozen, and roles keep neighbours out of the evidence', () => {
  assert.equal(evidenceContextSummary({ id: 't', source_id: null, paragraphs: [] }), '来源尚未冻结，没有可读取的段落。')
  assert.equal(evidenceContextSummary({ id: 't', source_id: 'src', paragraphs: [] }), '来源已冻结，但还没有进入上下文或被引用的段落。')
  assert.equal(evidenceContextSummary({ id: 't', source_id: 'src', paragraphs: [paragraph('p1', '正文')] }), null)
  assert.equal(paragraphRole(paragraph('p0', '邻')), '邻段')
  assert.equal(paragraphRole(paragraph('p1', '引', { cited: true })), '被引用')
  assert.equal(paragraphRole(paragraph('p2', '两者', { cited: true, entered_context: true })), '被引用 · 进入模型上下文')
})

test('input and evidence-context reads check the path, the task id, and the contract', async () => {
  const requests = []
  const input = { id: 'a/b', claim: '  claim  ', doi: '10.1000/raw', previous_id: null, config_digest: 'frozen', authorized_recipients: ['接收方'] }
  const context = { id: 'a/b', source_id: 'src', paragraphs: [paragraph('p1', '冻结原文', { entered_context: true, cited: true })] }
  const client = createHttpClient(async url => {
    requests.push(String(url))
    const body = String(url).endsWith('/input') ? input : context
    return new Response(JSON.stringify(body))
  })
  assert.deepEqual(await client.getCheckInput('a/b'), input)
  assert.equal(requests[0], '/api/checks/a%2Fb/input')
  assert.deepEqual(await client.getEvidenceContext('a/b'), context)
  assert.equal(requests[1], '/api/checks/a%2Fb/evidence-context')
  assert.equal(validateCheckInput(input), true)
  assert.equal(validateEvidenceContext({ id: 'a/b', source_id: null, paragraphs: [] }), true)
  assert.equal(validateEvidenceContext({ ...context, paragraphs: [{ ...context.paragraphs[0], text: '' }] }), true)
  await assert.rejects(createHttpClient(async () => new Response(JSON.stringify(input))).getCheckInput('other'), error => error.kind === 'invalid')
  await assert.rejects(createHttpClient(async () => new Response(JSON.stringify({ id: 'a/b', source_id: 'src' }))).getEvidenceContext('a/b'), error => error.kind === 'invalid')
  const flagged = { ...context, paragraphs: [{ ...context.paragraphs[0], cited: 'yes' }] }
  assert.equal(validateEvidenceContext(flagged), false)
  await assert.rejects(
    createHttpClient(async () => new Response(JSON.stringify({ error_code: null, message: '任务不存在' }), { status: 404 })).getCheckInput('missing'),
    error => error.kind === 'business' && error.status === 404 && error.message === '任务不存在',
  )
})

test('demo input keeps the submitted text, and evidence context can be empty or anchor-adjacent', async () => {
  const c = createDemoClient()
  const config = await c.getRunConfig()
  const consent = { config_digest: config.config_digest, authorized_recipients: [config.primary_recipient], cloud_consent: true, source_confirmed: true }
  const created = await c.createCheck({ claim: '  spaced  ', doi: '10.0000/Raw', ...consent })
  const input = await c.getCheckInput(created.id)
  assert.equal(input.claim, '  spaced  ')
  assert.equal(input.doi, '10.0000/Raw')
  assert.equal(input.config_digest, config.config_digest)
  assert.deepEqual(input.authorized_recipients, [config.primary_recipient])
  assert.equal(validateCheckInput(input), true)
  const queued = await c.getEvidenceContext('demo-5')
  assert.equal(queued.source_id, null)
  assert.deepEqual(queued.paragraphs, [])
  const insufficient = await c.getEvidenceContext('demo-4')
  assert.equal(insufficient.source_id, 'demo-source')
  assert.deepEqual(insufficient.paragraphs, [])
  const supported = await c.getEvidenceContext('demo-1')
  assert.equal(validateEvidenceContext(supported), true)
  const window = anchorWindow(supported.paragraphs, 'demo:p:1')
  assert.equal(window.before.cited, false)
  assert.equal(window.before.entered_context, false)
  assert.equal(window.anchor.cited, true)
  assert.equal(window.after.paragraph_id, 'demo:p:2')
  assert.match(window.before.text, /构造/)
})
