import { expect, test } from '@playwright/test'

/**
 * 界面壳层：空历史状态与真实接口模式。
 *
 * 这是唯一依赖「任务库为空」的用例，所以文件名前缀保证它先跑；其余用例都把
 * 历史列表当作会累积的集合，用 DOI 与任务标识定位，不假设列表长度。
 */

test('空任务库时侧栏给出明确的空态，并表明当前是真实接口模式', async ({ page }) => {
  await page.goto('/#/new')

  await expect(page.getByRole('heading', { name: '新的核验' })).toBeVisible()
  // 真实接口模式：工具栏文案与演示模式不同，且不渲染模拟场景下拉。
  await expect(page.getByText('真实接口模式')).toBeVisible()
  await expect(page.locator('#scenario')).toHaveCount(0)

  await expect(page.getByText('暂无核验记录')).toBeVisible()
  await expect(page.locator('.history-list button')).toHaveCount(0)
})

test('无法识别的链接会被挡下并回到新建核验', async ({ page }) => {
  await page.goto('/#/nope')

  await expect(page.getByRole('heading', { name: '新的核验' })).toBeVisible()
  await expect(page.getByText('链接中的任务标识无法识别，已打开新的核验。')).toBeVisible()
})
