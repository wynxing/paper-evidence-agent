import fs from 'node:fs'

import { expect, test } from '@playwright/test'

import { DOI, OBSERVER, currentId, expectStatus, openDiagnostics, submitCheck } from './helpers'

/**
 * 诊断包与导出预览（测试方案「2. 维度」：书目导出预览）。
 *
 * 两条边界都必须显式呈现，不能含糊：
 *
 * * 脱敏包**保留公开书目字段**，界面要写明「书目字段未遮盖」，不能当匿名包用；
 * * 语义导出要**单独授权**，接收方来自冻结的任务配置，界面上不可改。
 *
 * 这里不真实外发：用例只验证下载由本机浏览器发起。
 */

const CLAIM = '阿司匹林降低了老年患者的死亡率。'

test('脱敏包明示书目未遮盖，语义导出需要针对接收方单独授权', async ({ page }) => {
  await submitCheck(page, CLAIM)
  await expectStatus(page, '支持')

  await page.getByRole('button', { name: '运行诊断' }).click()
  await expect(page.getByRole('heading', { name: '运行诊断' })).toBeVisible()

  await expect(page.getByText('书目字段未遮盖，可识别文献及相关主题。')).toBeVisible()
  await expect(page.getByText('脱敏包隐藏论断与生成文本，不能用于声称复现全部语义缺陷。')).toBeVisible()

  // 展开脱敏 JSON：结构、公开书目仍在，模型生成的文本被替换。
  await page.locator('summary', { hasText: '查看脱敏 JSON' }).click()
  const preview = page.locator('.json-preview')
  await expect(preview).toBeVisible()
  await expect(preview).toContainText('"schema_version": "2.2"')
  await expect(preview).toContainText(DOI)
  await expect(preview).toContainText('<redacted>')

  await expect(page.getByRole('button', { name: '下载脱敏包' })).toBeEnabled()
  const id = currentId(page)
  const [download] = await Promise.all([
    page.waitForEvent('download'),
    page.getByRole('button', { name: '下载脱敏包' }).click(),
  ])
  expect(download.suggestedFilename()).toBe(`${id}-redacted.json`)
  const savedPath = await download.path()
  expect(savedPath).toBeTruthy()
  const saved = JSON.parse(fs.readFileSync(savedPath!, 'utf8'))
  const previewJson = JSON.parse(await preview.evaluate(node => node.textContent ?? ''))
  expect(saved).toEqual(previewJson)
  expect(saved.input.privacy).toBe('redacted')
  expect(saved.input.claim).toBe('<redacted>')
  expect(saved.model_calls.length).toBeGreaterThan(0)
  expect(saved.model_calls[0].attempts[0]).toHaveProperty('provider_model')
  expect(JSON.stringify(saved)).not.toContain('raw_prompt')

  // 语义导出：弹窗里接收方只读，未勾选授权时确认按钮不可用。
  await page.getByRole('button', { name: '预览语义导出范围' }).click()
  const dialog = page.getByRole('dialog', { name: '语义诊断包导出' })
  await expect(dialog).toBeVisible()
  await expect(page.locator('#recipient')).toHaveValue(OBSERVER)
  await expect(page.locator('#recipient')).toHaveAttribute('readonly', '')
  const confirm = dialog.getByRole('button', { name: '授权并下载到本地' })
  await expect(confirm).toBeDisabled()

  await dialog.getByRole('checkbox', { name: '我同意为所列接收方导出上述语义数据' }).check()
  await expect(confirm).toBeEnabled()
  await confirm.click()

  // 应用只负责下载到本机，不自动外发给接收方。
  await expect(page.getByText('诊断包下载已发起，未自动发送给接收方。')).toBeVisible()
})

test('诊断页能从任务标识直接深链打开，不依赖先在详情页点击', async ({ page }) => {
  const id = await submitCheck(page, CLAIM)
  await expectStatus(page, '支持')

  await openDiagnostics(page, id)
  await expect(page.locator('.diagnostics-facts').getByText('判据版本', { exact: true })).toBeVisible()
  await expect(page.getByRole('button', { name: '← 返回核验意见' })).toBeVisible()
})
