import { expect, test, type Page } from '@playwright/test'

import { expectStatus, submitCheck } from './helpers'

/**
 * 桌面 1440、平板 1024、窄屏 390 下，主路径（新建、详情、诊断 JSON、窄屏导航）
 * 不应把页面撑出横向滚动。
 */

const CLAIM = '阿司匹林降低了老年患者的死亡率。'

async function assertFits(page: Page, width: number) {
  const box = await page.evaluate(() => ({
    scroll: document.documentElement.scrollWidth,
    client: document.documentElement.clientWidth,
  }))
  expect(box.scroll, `横向溢出 @ ${width}px：${box.scroll} > ${box.client}`).toBeLessThanOrEqual(box.client + 1)
}

test('1440、1024 与 390 宽度下主路径不横向溢出', async ({ page }) => {
  const id = await submitCheck(page, CLAIM)
  await expectStatus(page, '支持')

  for (const width of [1440, 1024, 390]) {
    await page.setViewportSize({ width, height: 900 })

    await page.goto('/#/new')
    await expect(page.getByRole('heading', { name: '新的核验' })).toBeVisible()
    await assertFits(page, width)

    await page.goto(`/#/checks/${encodeURIComponent(id)}`)
    await expect(page.locator('.result-line .status-label')).toBeVisible()
    if (width < 1200) await page.getByRole('tab', { name: '原文证据' }).click()
    await assertFits(page, width)

    await page.goto(`/#/checks/${encodeURIComponent(id)}/diagnostic`)
    await expect(page.getByRole('heading', { name: '运行诊断' })).toBeVisible()
    await page.locator('summary', { hasText: '查看脱敏 JSON' }).click()
    await expect(page.locator('.json-preview')).toBeVisible()
    await assertFits(page, width)

    if (width < 768) {
      await page.getByRole('button', { name: '切换导航' }).click()
      await expect(page.getByRole('button', { name: '收起导航' })).toBeVisible()
      await assertFits(page, width)
    }
  }
})
