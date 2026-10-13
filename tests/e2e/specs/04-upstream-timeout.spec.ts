import { expect, test } from '@playwright/test'

import { expectStatus, stubDelay, submitCheck } from './helpers'

/**
 * 上游超时：界面要显示超时这一**执行状态**，并且明确它不是学术判断
 * （测试方案「2. 维度」：显示超时）。
 *
 * 制造方式是把替身模型的回复延迟设到单次尝试上限（8 秒）之上，让真实的上游
 * 读超时发生，而不是伪造一个 5xx。用例结束后立刻把延迟复位，避免影响后面的
 * 用例。
 */

const CLAIM = '阿司匹林降低了老年患者的死亡率。'

test('上游超时落成执行失败，并把它与学术判断区分开', async ({ page }) => {
  await stubDelay(page, 12)
  try {
    await submitCheck(page, CLAIM)

    await expectStatus(page, '执行失败')
    // 停止原因与错误码都给出，而不是含糊的「核验失败」。
    await expect(page.getByRole('heading', { name: '单次上游请求超时' })).toBeVisible()
    await expect(page.getByText('UPSTREAM_TIMEOUT')).toBeVisible()
    await expect(page.getByText('这是执行状态，不能据此判断文献是否支持论断。')).toBeVisible()
    // 没有通过校验的证据，就不能显示任何摘录。
    await expect(page.getByText('尚无通过校验的最终证据。')).toBeVisible()

    // 终态任务三个时刻都落定。
    await page.locator('details.disclosure summary').first().click()
    const facts = page.locator('details.disclosure dl.facts')
    await expect(facts.getByText('尚未结束')).toHaveCount(0)
    await expect(facts.getByText('暂无数据')).toHaveCount(0)
  } finally {
    await stubDelay(page, 0)
  }
})
