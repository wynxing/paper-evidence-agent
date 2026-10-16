import test from 'node:test'
import assert from 'node:assert/strict'
import * as model from '../src/state/model.ts'
import { createDemoClient } from '../src/api/demo.ts'
import { downloadPacket, projectPacket } from '../src/api/export.ts'

async function packet(recipient = 'Configured reviewer') {
  const value = await createDemoClient().getDiagnosticPacket('demo-1')
  value.run_config.observability.recipient = recipient
  return value
}

test('semantic export is unavailable without a configured diagnostic recipient', async () => {
  for (const recipient of [null, '', ' ']) {
    const p = await packet(recipient)
    assert.throws(() => model.diagnosticExportRequest(p, 'demo-1', 'Arbitrary reviewer', true, p), /接收方/)
  }
})

test('semantic export payload binds separate consent to the exact configured recipient', async () => {
  const p = await packet()
  assert.deepEqual(model.diagnosticExportRequest(p, 'demo-1', 'Configured reviewer', true, p), { recipient: 'Configured reviewer', semantic_export_consent: true })
  assert.throws(() => model.diagnosticExportRequest(p, 'demo-1', 'Arbitrary reviewer', true, p), /接收方/)
  assert.throws(() => model.diagnosticExportRequest(p, 'demo-1', 'Configured reviewer', false, p), /授权/)
})

test('downloadPacket writes the projected packet to a file with a stable name', async () => {
  const source = await createDemoClient().getDiagnosticPacket('demo-1')
  source.case_id = 'case/1'
  source.raw_prompt = 'secret'
  const blobs = []
  const revoked = []
  const previousCreate = URL.createObjectURL
  const previousRevoke = URL.revokeObjectURL
  URL.createObjectURL = blob => { blobs.push(blob); return 'blob:packet' }
  URL.revokeObjectURL = url => { revoked.push(url) }
  const body = {
    children: [],
    appendChild(node) { node.parentNode = body; this.children.push(node); return node },
    removeChild(node) { this.children = this.children.filter(item => item !== node); node.parentNode = null; return node },
  }
  const created = []
  const previousDocument = globalThis.document
  globalThis.document = {
    body,
    createElement() {
      const node = {
        style: {}, parentNode: null, clicked: false, parentAtClick: null,
        click() { this.clicked = true; this.parentAtClick = this.parentNode },
        remove() { this.parentNode?.removeChild(this) },
      }
      created.push(node)
      return node
    },
  }
  try {
    downloadPacket(source)
    const anchor = created[0]
    assert.equal(anchor.clicked, true)
    assert.equal(anchor.parentAtClick, body)
    assert.equal(body.children.length, 0)
    assert.equal(anchor.download, 'case_1-redacted.json')
    assert.equal(anchor.rel, 'noopener')
    assert.equal(anchor.href, 'blob:packet')
    const saved = JSON.parse(await blobs[0].text())
    assert.deepEqual(saved, JSON.parse(JSON.stringify(projectPacket(source))))
    assert.equal(saved.schema_version, '2.2')
    assert.equal(saved.case_id, 'case/1')
    assert.equal(saved.input.privacy, 'redacted')
    assert.equal(saved.input.claim, '<redacted>')
    assert.equal(JSON.stringify(saved).includes('secret'), false)
    assert.equal(Object.hasOwn(saved.model_calls[0].attempts[0], 'provider_model'), true)
    assert.equal(revoked.length, 0)
    const consented = await createDemoClient().exportDiagnosticPacket('demo-1', { recipient: 'Configured reviewer', semantic_export_consent: true })
    downloadPacket(consented)
    assert.equal(created[1].download, 'demo-1-consented.json')
    assert.equal(JSON.parse(await blobs[1].text()).input.privacy, 'consented')
  } finally {
    URL.createObjectURL = previousCreate
    URL.revokeObjectURL = previousRevoke
    if (previousDocument === undefined) delete globalThis.document
    else globalThis.document = previousDocument
  }
})

test('semantic export rejects consent from a stale packet or task', async () => {
  const p = await packet()
  const refreshed = structuredClone(p)
  assert.throws(() => model.diagnosticExportRequest(refreshed, 'demo-1', 'Configured reviewer', true, p), /诊断包/)
  assert.throws(() => model.diagnosticExportRequest(p, 'demo-2', 'Configured reviewer', true, p), /诊断包/)
  assert.throws(() => model.diagnosticExportRequest(null, 'demo-1', 'Configured reviewer', true, p), /诊断包/)
})
