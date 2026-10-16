import { expect, test, type Page } from '@playwright/test'

import { expectStatus, openCheck, submitCheck } from './helpers'

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

/**
 * 桌面「收起证据」留下 desktop-hidden 之后，≤1199px 仍要看得见证据面板，或仍有办法打开它。
 *
 * 窄屏的 desktop-panel-toggle 是 display:none。现在能看见，是因为
 * `@media (max-width:1199px)` 里更靠后的 `.evidence-panel { display: block }`
 * 压过了 `.desktop-hidden`，以及这条规则只在 ≥1200px 生效。两边都拿掉
 * （把 .desktop-hidden 改回全局，并删掉那条 display:block）时，本用例会失败。
 * 判定用的是 getComputedStyle，不是类名是否还在。
 */
test('1024 与 390 下带 desktop-hidden 的证据面板仍可见或仍能打开', async ({ page }) => {
  const id = await submitCheck(page, CLAIM)
  await expectStatus(page, '支持')
  await page.setViewportSize({ width: 1440, height: 900 })
  await openCheck(page, id)
  await page.getByRole('button', { name: '收起证据' }).click()

  const collapsed = await readEvidencePanel(page)
  expect(collapsed.desktopHidden, '桌面收起后证据面板应带 desktop-hidden').toBe(true)
  expect(collapsed.display, '1440 下收起的证据面板应被藏住').toBe('none')

  for (const width of [1024, 390]) {
    await page.setViewportSize({ width, height: 900 })
    await page.getByRole('tab', { name: '原文证据' }).click()
    let probe = await readEvidencePanel(page)
    expect(probe.desktopHidden, `${width}px 下证据面板应仍带 desktop-hidden`).toBe(true)
    if (!panelVisible(probe) && controlVisible(probe.toggle)) {
      await page.getByRole('button', { name: '查看证据' }).click()
      probe = await readEvidencePanel(page)
    }
    expect(
      panelVisible(probe),
      `窄屏 ${width}px：带 desktop-hidden 的证据面板不可见，且没有打开方式（panel display=${probe.display}，toggle display=${probe.toggle.display}）`,
    ).toBe(true)
  }
})

type BoxProbe = { display: string; visibility: string; width: number; height: number }

async function readEvidencePanel(page: Page) {
  return page.evaluate(() => {
    const panel = document.querySelector('.evidence-panel')
    const toggle = document.querySelector('.desktop-panel-toggle')
    if (!(panel instanceof HTMLElement)) throw new Error('缺少 .evidence-panel')
    const style = getComputedStyle(panel)
    const box = panel.getBoundingClientRect()
    const toggleStyle = toggle instanceof HTMLElement ? getComputedStyle(toggle) : null
    const toggleBox = toggle instanceof HTMLElement ? toggle.getBoundingClientRect() : { width: 0, height: 0 }
    return {
      desktopHidden: panel.classList.contains('desktop-hidden'),
      display: style.display,
      visibility: style.visibility,
      width: box.width,
      height: box.height,
      toggle: {
        display: toggleStyle?.display ?? 'missing',
        visibility: toggleStyle?.visibility ?? 'missing',
        width: toggleBox.width,
        height: toggleBox.height,
      },
    }
  })
}

function panelVisible(probe: { display: string; visibility: string; width: number; height: number }) {
  return probe.display !== 'none' && probe.visibility !== 'hidden' && probe.width > 0 && probe.height > 0
}

function controlVisible(probe: BoxProbe) {
  return probe.display !== 'none' && probe.display !== 'missing' && probe.visibility !== 'hidden' && probe.width > 0 && probe.height > 0
}
