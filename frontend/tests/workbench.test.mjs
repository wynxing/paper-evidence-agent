import test from 'node:test'
import assert from 'node:assert/strict'
import { createHttpClient, ClientError } from '../src/api/http.ts'
import { createDemoClient } from '../src/api/demo.ts'
import { createDraft, invalidateDraft, canSubmit, isTerminal, attemptText, safeSourceUrl } from '../src/state/model.ts'
import { createPoller } from '../src/state/poller.ts'
import { validateDetail, validatePacket, validateConfig, validateSource } from '../src/api/validation.ts'
import { projectPacket } from '../src/api/export.ts'

test('501 is explicit and never falls back to demo', async () => {
  let calls = 0
  const client = createHttpClient(async () => { calls++; return new Response(JSON.stringify({ error_code: null, message: 'pending' }), { status: 501 }) })
  await assert.rejects(client.createCheck({}), e => e instanceof ClientError && e.kind === 'pending')
  assert.equal(calls, 1)
})
test('invalid successful responses and transport failures remain distinct', async () => {
  await assert.rejects(createHttpClient(async () => new Response('{}')).getCheck('a'), e => e.kind === 'invalid')
  await assert.rejects(createHttpClient(async () => { throw new TypeError('private content') }).listChecks(), e => e.kind === 'network' && !e.message.includes('private'))
})
test('HTTP methods encode identifiers, consent, and empty bodies safely', async () => {
  const requests = []
  const c = createHttpClient(async (url, init) => { requests.push([url, init]); return new Response(JSON.stringify({ id: 'a/b', saved: true })) })
  await c.saveFeedback('a/b', { comment: '意见' })
  assert.equal(requests[0][0], '/api/checks/a%2Fb/feedback')
  assert.equal(requests[0][1].method, 'POST')
  assert.deepEqual(JSON.parse(requests[0][1].body), { comment: '意见' })
})
test('source and cloud confirmation invalidate when input changes; refused consent cannot submit', () => {
  const d = createDraft(); d.claim = '论断'; d.doi = '10.0000/demo'; d.sourceConfirmed = true; d.cloudConsent = true
  d.source = { doi: d.doi, title: '构造文献', authors: [], year: null }; d.config = { config_digest: 'x' }
  assert.equal(canSubmit(d), true)
  invalidateDraft(d, false); assert.equal(canSubmit(d), false); assert.equal(d.sourceConfirmed, true)
  invalidateDraft(d, true); assert.equal(d.source, null); assert.equal(d.sourceConfirmed, false)
})
test('unknown attempt accounting and unsafe links do not become known values', () => {
  assert.match(attemptText({ verification: 'unverified', observed_upstream_attempts: 2, upstream_attempts_used: null }), /至少 2.*未知/)
  assert.equal(safeSourceUrl('javascript:alert(1)'), null)
  assert.equal(safeSourceUrl('https://example.org/paper'), 'https://example.org/paper')
  assert.equal(isTerminal('RUNNING'), false); assert.equal(isTerminal('CANCELLED'), true)
})
test('demo preserves old tasks on retry, cancellation closes, export only returns data', async () => {
  const c = createDemoClient(); const old = (await c.listChecks())[0]
  const config = await c.getRunConfig()
  const consent = { config_digest: config.config_digest, authorized_recipients: [config.primary_recipient], cloud_consent: true, source_confirmed: true }
  const newer = await c.retryCheck(old.id, consent)
  assert.notEqual(newer.id, old.id); assert.equal((await c.getCheck(old.id)).id, old.id)
  await c.getCheck(newer.id); await c.getCheck(newer.id)
  assert.equal((await c.cancelCheck(newer.id)).status, 'RUNNING')
  const cancelled = await c.getCheck(newer.id)
  assert.equal(cancelled.status, 'CANCELLED'); assert.equal(cancelled.stage, 'retrieval')
  const queued = await c.retryCheck(old.id, consent)
  assert.equal((await c.cancelCheck(queued.id)).status, 'CANCELLED')
  const redacted = await c.getDiagnosticPacket(old.id)
  assert.equal(redacted.input.claim, '<redacted>')
  assert.equal((await c.exportDiagnosticPacket(old.id, { recipient: '本地评审', semantic_export_consent: true })).input.privacy, 'consented')
  await assert.rejects(c.createCheck({ claim: 'x', doi: '10.0000/demo', ...consent, cloud_consent: false }))
  await assert.rejects(c.createCheck({ claim: 'x', doi: '10.0000/demo', ...consent, config_digest: 'stale' }), e => e.status === 409)
})
test('poller discards late results after stopping and stops at terminal state', async () => {
  let release; let received = 0
  const p = createPoller(() => new Promise(r => { release = r }), () => received++, () => {}, 5)
  p.start(); p.stop(); release({ status: 'COMPLETED' }); await new Promise(r => setTimeout(r, 15)); assert.equal(received, 0)
  let calls = 0
  const terminal = createPoller(async () => { calls++; return { status: 'COMPLETED' } }, () => {}, () => {}, 5)
  terminal.start(); await new Promise(r => setTimeout(r, 15)); terminal.stop(); assert.equal(calls, 1)
})
test('all constructed scenarios satisfy published types without claiming real evidence', async () => {
  const c = createDemoClient()
  assert.equal(validateConfig(await c.getRunConfig()), true)
  assert.equal(validateSource(await c.resolveSource('10.0000/demo')), true)
  for (const row of await c.listChecks()) {
    const d = await c.getCheck(row.id); const p = await c.getDiagnosticPacket(row.id)
    assert.equal(validateDetail(d), true, row.id); assert.equal(validatePacket(p), true, row.id)
    if (d.status !== 'COMPLETED') assert.equal(d.decision, null)
    if (d.decision) assert.match(d.decision.rationale, /构造/)
  }
})
test('reject malformed nested data and determinate results without evidence', async () => {
  const c = createDemoClient(); const d = await c.getCheck('demo-1')
  d.decision.evidence = []; assert.equal(validateDetail(d), false)
  const p = await c.getDiagnosticPacket('demo-1')
  p.model_calls[0].attempts[0].usage = { total_tokens: 'unknown' }; assert.equal(validatePacket(p), false)
})
test('read endpoint refuses consented packet and undeclared fields never enter export', async () => {
  const c = createDemoClient(); const p = await c.exportDiagnosticPacket('demo-1', { recipient: 'test', semantic_export_consent: true })
  await assert.rejects(createHttpClient(async () => new Response(JSON.stringify(p))).getDiagnosticPacket('demo-1'), e => e.kind === 'invalid')
  p.raw_prompt = 'secret'; p.input.private_field = 'secret'; p.model_calls[0].attempts[0].api_key = 'secret'
  assert.equal(JSON.stringify(projectPacket(p)).includes('secret'), false)
})
test('poller performs serial reads, aborts on stop, and recovers after network error', async () => {
  let calls = 0; let overlap = 0; let active = 0; let release; let signal
  const p = createPoller(s => { calls++; signal = s; active++; overlap = Math.max(overlap, active); return new Promise(r => { release = v => { active--; r(v) } }) }, () => {}, () => {}, 5)
  p.start(); await new Promise(r => setTimeout(r, 20)); assert.equal(calls, 1); assert.equal(overlap, 1)
  p.stop(); assert.equal(signal.aborted, true); release({ status: 'RUNNING' })
  let attempts = 0; let errors = 0; let received = 0
  const recovered = createPoller(async () => { if (++attempts === 1) throw new TypeError('offline'); return { status: 'COMPLETED' } }, () => received++, () => errors++, 5)
  recovered.start(); await new Promise(r => setTimeout(r, 25)); recovered.stop(); assert.equal(errors, 1); assert.equal(received, 1)
})
test('no-content mutations retain exact API semantics', async () => {
  const c = createDemoClient(); const requests = []
  const fake = createHttpClient(async (url, init) => { requests.push({ url, init }); return new Response(JSON.stringify(await c.cancelCheck('demo-5'))) })
  await fake.cancelCheck('demo-5')
  assert.equal(requests[0].init.body, undefined); assert.equal(requests[0].init.method, 'POST')
})
test('mismatched task identity cannot publish another task result', async () => {
  const d = await createDemoClient().getCheck('demo-1')
  await assert.rejects(createHttpClient(async () => new Response(JSON.stringify(d))).getCheck('wrong-id'), e => e.kind === 'invalid')
  const c = createDemoClient(); const packet = await c.getDiagnosticPacket('demo-1')
  await assert.rejects(createHttpClient(async () => new Response(JSON.stringify(packet))).getDiagnosticPacket('wrong-id'), e => e.kind === 'invalid')
  const semantic = await c.exportDiagnosticPacket('demo-1', { recipient: 'different-recipient', semantic_export_consent: true })
  await assert.rejects(createHttpClient(async () => new Response(JSON.stringify(semantic))).exportDiagnosticPacket('demo-1', { recipient: 'intended-recipient', semantic_export_consent: true }), e => e.kind === 'invalid')
  await assert.rejects(createHttpClient(async () => new Response(JSON.stringify({ id: 'new-id', status: 'QUEUED', previous_id: 'other-id' }))).retryCheck('demo-1', {}), e => e.kind === 'invalid')
})
test('response body transport loss leaves mutation outcome unconfirmed without retry', async () => {
  let calls = 0
  const client = createHttpClient(async () => { calls++; return { status: 200, ok: true, json: async () => { throw new TypeError('connection lost') } } })
  await assert.rejects(client.createCheck({}), e => e.kind === 'network' && e.message.includes('尚未确认'))
  assert.equal(calls, 1)
})
test('completed evidence cannot appear on a failed task', async () => {
  const d = await createDemoClient().getCheck('demo-1'); d.status = 'FAILED'
  assert.equal(validateDetail(d), false)
})
test('empty history can be reached without deleting active tasks', async () => {
  const c = createDemoClient()
  for (const row of await c.listChecks()) {
    if (!isTerminal(row.status)) { await assert.rejects(c.deleteCheck(row.id)); await c.cancelCheck(row.id); await c.getCheck(row.id) }
    await c.deleteCheck(row.id)
  }
  assert.deepEqual(await c.listChecks(), [])
})
