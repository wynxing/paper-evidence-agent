import test from 'node:test'
import assert from 'node:assert/strict'
import * as model from '../src/state/model.ts'
import { createDemoClient } from '../src/api/demo.ts'

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

test('semantic export rejects consent from a stale packet or task', async () => {
  const p = await packet()
  const refreshed = structuredClone(p)
  assert.throws(() => model.diagnosticExportRequest(refreshed, 'demo-1', 'Configured reviewer', true, p), /诊断包/)
  assert.throws(() => model.diagnosticExportRequest(p, 'demo-2', 'Configured reviewer', true, p), /诊断包/)
  assert.throws(() => model.diagnosticExportRequest(null, 'demo-1', 'Configured reviewer', true, p), /诊断包/)
})
