import { expect, test } from '@playwright/test'

import { DOI, QUOTE, TITLE, currentId, expectStatus, openCheck, submitCheck } from './helpers'

/**
 * 界面主路径：确认来源 → 同意整次任务的接收方/数据范围/预算 → 提交 → 查看判断
 * 与原文位置（测试方案「2. 维度」末尾）。
 *
 * 上游是 `support/upstreams.py` 的替身，所以这里判定的是**界面与流程**，不是
 * 论文语义结论：替身给出的「支持」标签只用于验证渲染与状态流转。
 */

const CLAIM = '阿司匹林降低了老年患者的死亡率。'

test('提交前必须看到来源身份、以及这次任务的接收方、数据范围与预算', async ({ page }) => {
  await page.goto('/#/new')
  await page.locator('#doi').fill(DOI)
  await page.locator('#claim').fill(CLAIM)
  await page.getByRole('button', { name: '读取文献' }).click()

  // 来源身份来自真实 /api/sources/resolve，只是上游被换成本机替身。
  await expect(page.locator('#source-heading')).toBeVisible()
  await expect(page.locator('.source-preview h2')).toHaveText(TITLE)
  await expect(page.locator('.source-preview .mono')).toHaveText(DOI)

  // 授权区把数据范围、主接收方、调用上限与执行时限逐项列出。
  await expect(page.locator('#consent-heading')).toHaveText('本次调用授权')
  await expect(page.getByText('整次任务将发送以下数据')).toBeVisible()
  const facts = page.locator('dl.facts').first()
  for (const term of ['数据范围', '主接收方', '模型别名', '调用上限', '执行时限', '观测导出']) {
    await expect(facts.getByText(term, { exact: true })).toBeVisible()
  }

  // 未确认来源时，整次任务的授权勾选框不可用；未授权则提交按钮不可用。
  await expect(page.getByRole('checkbox', { name: '我同意本次任务向以上接收方发送所列数据' })).toBeDisabled()
  await expect(page.locator('.submit-row button.primary')).toBeDisabled()
  await page.getByRole('checkbox', { name: '我确认这是拟引用的文献' }).check()
  await expect(page.getByRole('checkbox', { name: '我同意本次任务向以上接收方发送所列数据' })).toBeEnabled()
  await expect(page.locator('.submit-row button.primary')).toBeDisabled()
})

test('提交后任务跑完，判断与可定位的原文位置都渲染出来', async ({ page }) => {
  const id = await submitCheck(page, CLAIM)
  expect(id.length).toBeGreaterThan(0)

  await expectStatus(page, '支持')
  await expect(page.getByRole('heading', { name: 'Paper agent 的核验意见' })).toBeVisible()
  await expect(page.locator('.decision-section p').first()).toContainText('构造的上游回复')
  await expect(page.getByRole('heading', { name: '限制' })).toBeVisible()

  // 原文位置：摘录逐字、段落号、章节名与校验标识。
  const evidence = page.locator('.evidence-panel .evidence-item')
  await expect(evidence).toHaveCount(1)
  await expect(evidence.locator('blockquote')).toHaveText(QUOTE)
  await expect(evidence.locator('p.mono.small.muted')).toContainText('p:')
  await expect(page.getByText('段落校验标识')).toBeVisible()

  // 计时字段：终态任务的三个时刻都落定，用时不是「暂无数据」。
  await page.locator('details.disclosure summary').first().click()
  const facts = page.locator('details.disclosure dl.facts')
  const value = (term: string) => facts.locator('dt', { hasText: term }).locator('xpath=following-sibling::dd[1]')
  for (const term of ['创建时间', '开始时间', '结束时间']) {
    await expect(value(term)).not.toHaveText(/未知|尚未/)
  }
  await expect(value('排队 / 执行用时')).not.toHaveText(/暂无数据/)

  // 费用按口径固定为「未知」：调用次数不是费用上限，且本机替身不提供计费。
  await expect(value('费用')).toHaveText('未知')

  // 任务出现在侧栏历史里，并标出当前项。
  await expect(page.locator('.history-list button[aria-current="page"]')).toHaveCount(1)
})

test('刷新页面后仍能从本地记录读回同一个任务', async ({ page }) => {
  const id = await submitCheck(page, CLAIM)
  await expectStatus(page, '支持')

  await page.reload()
  await expectStatus(page, '支持')
  await openCheck(page, id)
  await expect(page.locator('.result-line .status-label')).toHaveText('支持')
  await expect(page.locator('.evidence-panel .evidence-item blockquote')).toHaveText(QUOTE)
  await expect(page.getByRole('button', { name: '重新授权并重试' })).toBeEnabled()
})

test('运行诊断页展示调用账与逐次尝试', async ({ page }) => {
  await submitCheck(page, CLAIM)
  await expectStatus(page, '支持')

  await page.getByRole('button', { name: '运行诊断' }).click()
  await expect(page.getByRole('heading', { name: '运行诊断' })).toBeVisible()

  const facts = page.locator('.diagnostics-facts')
  await expect(facts.getByText('上游尝试', { exact: true })).toBeVisible()
  await expect(facts.getByText('主请求 / 修复', { exact: true })).toBeVisible()

  // 逐次尝试表：替身的响应带 usage，所以 Tokens 列是具体数字。
  await expect(page.getByRole('heading', { name: '模型请求与逐次尝试' })).toBeVisible()
  const row = page.locator('.disclosure table tbody tr').first()
  await expect(row).toContainText('成功')
  // 列序：尝试 / 状态 / 恢复 / 模型版本 / Tokens。
  await expect(row.locator('td').nth(4)).toHaveText('33')
  // 模型版本来自上游的**可验证**声明；替身不提供，按口径保持「未知」，
  // 不能用别名顶上（`docs/glossary.md:230`、`docs/verification.md:391`）。
  await expect(row.locator('td').nth(3)).toHaveText('未知')
})
