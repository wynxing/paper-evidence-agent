import { expect, test } from '@playwright/test'

import { expectStatus, openCheck, stubDelay, submitCheck } from './helpers'

/**
 * 取消排队与运行中的任务（测试方案「2. 维度」：取消排队/运行任务）。
 *
 * 界面没有取消确认弹窗，所以点击即受理。两个分支都要覆盖：
 *
 * * 运行中（RUNNING）：受理后界面进入「正在取消」，等当前调用返回才落终态；
 * * 排队中（QUEUED）：受理即落 CANCELLED，不需要 worker 参与。
 *
 * 「在途」的窗口由替身模型的延迟制造；延迟只在模型回复前等待，不影响来源请求。
 */

const CLAIM = '阿司匹林降低了老年患者的死亡率。'

test('可以取消运行中的任务，也可以取消还在排队的任务', async ({ page }) => {
  await stubDelay(page, 6)
  try {
    // 运行中：A 被 worker 领取后在模型调用上停住
    const first = await submitCheck(page, CLAIM)
    await expectStatus(page, '执行中')

    await openCheck(page, first)
    await page.getByRole('button', { name: '取消任务' }).click()
    await expect(page.getByRole('heading', { name: '正在取消' })).toBeVisible()
    await expectStatus(page, '已取消')

    // 排队中：B 占住 worker，C 只能停在队列里
    const second = await submitCheck(page, CLAIM)
    await expectStatus(page, '执行中')
    const third = await submitCheck(page, CLAIM)
    await expectStatus(page, '排队中')
    await expect(page.getByText('排队中的任务需要后端 worker 常驻运行才会开始执行')).toBeVisible()

    await openCheck(page, third)
    await page.getByRole('button', { name: '取消任务' }).click()
    await expectStatus(page, '已取消')

    // 队列放行后，占住 worker 的那条任务照常跑完
    await openCheck(page, second)
    await expectStatus(page, '支持')
  } finally {
    await stubDelay(page, 0)
  }
})
