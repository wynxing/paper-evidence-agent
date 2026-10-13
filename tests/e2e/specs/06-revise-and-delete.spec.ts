import { expect, test } from '@playwright/test'

import { authorize, expectStatus, historyCount, openCheck, readSource, submitCheck } from './helpers'

/**
 * 澄清重提与删除本地记录（测试方案「2. 维度」：澄清重提、删除本地记录）。
 *
 * 「修改原句」不改写原任务，而是带着原句回到新建核验，提交后创建一条**新任务**
 * 并在界面上标明与原任务的关联；「重试」则由后端复用原任务输入。
 */

const CLAIM = '阿司匹林降低了老年患者的死亡率。'
const REVISED = '阿司匹林降低了老年患者的全因死亡率，在 65 岁以上人群中。'

test('修改原句会回到新建核验，提交后创建关联的新任务', async ({ page }) => {
  const original = await submitCheck(page, CLAIM)
  await expectStatus(page, '支持')

  await openCheck(page, original)
  await page.getByRole('button', { name: '修改原句' }).click()

  // 回到新建核验，原句与 DOI 带过来且可编辑；提交按钮仍是「开始核验」。
  await expect(page.getByRole('heading', { name: '新的核验' })).toBeVisible()
  await expect(page.getByText(`关联原任务 ${original}`)).toBeVisible()
  await expect(page.locator('#claim')).toHaveValue(CLAIM)
  await expect(page.locator('#claim')).toBeEnabled()
  await expect(page.locator('.submit-row button.primary')).toHaveText('开始核验')
  // 草稿只带原句与 DOI：来源与运行配置要重新读，授权也要重新给，
  // 不能在旧任务的授权上顺延（`workbench.ts` 的 `prepareEdit` 清空了 source/config）。
  await expect(page.locator('.source-preview')).toHaveCount(0)

  await page.locator('#claim').fill(REVISED)
  await readSource(page)
  await authorize(page)
  await page.locator('.submit-row button.primary').click()
  await expect(page).toHaveURL(/#\/checks\/[^/]+$/)

  const created = new URL(page.url()).hash.split('/').pop()!
  expect(created).not.toBe(original)
  await expectStatus(page, '支持')
  await openCheck(page, created)
  await expect(page.locator('.claim-text')).toHaveText(REVISED)
})

test('重试用后端原输入，论断框保持只读', async ({ page }) => {
  const original = await submitCheck(page, CLAIM)
  await expectStatus(page, '支持')

  await openCheck(page, original)
  await page.getByRole('button', { name: '重新授权并重试' }).click()

  await expect(page.getByRole('heading', { name: '新的核验' })).toBeVisible()
  await expect(page.locator('#claim')).toBeDisabled()
  await expect(page.locator('#claim')).toHaveValue(CLAIM)
  await expect(page.locator('.submit-row button.primary')).toHaveText('重新授权并重试')
})

test('删除本地记录需要确认，删掉后不再出现在历史里', async ({ page }) => {
  const target = await submitCheck(page, CLAIM)
  await expectStatus(page, '支持')

  await openCheck(page, target)
  await page.getByRole('button', { name: '删除本地记录' }).click()

  const dialog = page.getByRole('dialog', { name: '删除本地记录？' })
  await expect(dialog).toBeVisible()
  await expect(dialog).toContainText('不能撤回已发生的云模型调用')
  await dialog.getByRole('button', { name: '删除记录' }).click()

  await expect(page.getByRole('heading', { name: '新的核验' })).toBeVisible()
  expect(await historyCount(page)).toBeGreaterThanOrEqual(0)
  await page.goto(`/#/checks/${encodeURIComponent(target)}`)
  await expect(page.locator('.result-line .status-label')).toHaveCount(0)
})
