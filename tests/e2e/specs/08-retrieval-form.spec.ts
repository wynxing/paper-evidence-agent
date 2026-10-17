import { expect, test } from '@playwright/test'

import { expectStatus, submitCheck } from './helpers'

/**
 * 来源取回形态（Issue #60 的 `retrieval_form`）要在详情和诊断里看得见。
 *
 * 替身返回的是带 `<body>` 的全文，所以这里断言的是「正文」。只取得题录和摘要
 * 时的阻断文案依赖后端 #28，尚未合入，不在这条真实接口路径上制造该终态。
 */

const CLAIM = '阿司匹林降低了老年患者的死亡率。'

test('详情和诊断都标出已冻结来源的取回形态', async ({ page }) => {
  await submitCheck(page, CLAIM)
  await expectStatus(page, '支持')

  await expect(page.getByText('取回形态：正文')).toBeVisible()

  await page.getByRole('button', { name: '运行诊断' }).click()
  await expect(page.getByRole('heading', { name: '运行诊断' })).toBeVisible()
  const facts = page.locator('.diagnostics-facts')
  const value = facts.locator('dt', { hasText: '取回形态' }).locator('xpath=following-sibling::dd[1]')
  await expect(value).toHaveText('正文')
})
