import { expect, type Page } from '@playwright/test'

/**
 * 用例共用动作。选择器取自模板里稳定的可见文案与元素 `id`；仓库没有
 * `data-testid`，所以这里不假设存在测试专用钩子。
 */

export const DOI = '10.1000/e2e-1'
export const TITLE = 'E2E Demo Study of Antiplatelet Treatment'
//: 与 support/upstreams.py 的替身正文逐字一致。
export const QUOTE = 'reduced mortality by twenty percent'
export const OBSERVER = 'e2e-observer@example.test'

const STUB_PORT = process.env.PAPER_EVIDENCE_E2E_STUB_PORT ?? '8765'
const STUB_BASE = `http://127.0.0.1:${STUB_PORT}`

/** 让替身模型在回复前等待若干秒，用来制造「任务在途」的窗口。 */
export async function stubDelay(page: Page, seconds: number): Promise<void> {
  const response = await page.request.post(`${STUB_BASE}/_stub/delay`, { data: { seconds } })
  expect(response.ok()).toBeTruthy()
}

/** 让替身模型按需失败或恢复。 */
export async function stubMode(page: Page, mode: 'ok' | 'unavailable'): Promise<void> {
  const response = await page.request.post(`${STUB_BASE}/_stub/mode`, { data: { mode } })
  expect(response.ok()).toBeTruthy()
}

/** 读取并确认来源身份。
 *
 * `读取文献` 会重置整次任务的授权（`workbench.ts` 的 `resolve` 把
 * `sourceConfirmed`/`cloudConsent` 一起清掉），所以它必须先于勾选执行。
 */
export async function readSource(page: Page): Promise<void> {
  await page.getByRole('button', { name: '读取文献' }).click()
  await expect(page.locator('.source-preview h2')).toHaveText(TITLE)
}

/** 勾选来源确认与整次任务授权。
 *
 * 顺序不能颠倒：来源确认的 `@change` 会把整次任务授权清回未勾选
 * （`NewCheck.vue` 第 26 行），反过来勾则不会被清。
 */
export async function authorize(page: Page): Promise<void> {
  const confirmed = page.getByRole('checkbox', { name: '我确认这是拟引用的文献' })
  if (!(await confirmed.isChecked())) await confirmed.check()
  const consent = page.getByRole('checkbox', { name: '我同意本次任务向以上接收方发送所列数据' })
  if (!(await consent.isChecked())) await consent.check()
}

/** 走完新建核验的界面主路径，停在创建出的任务详情页。 */
export async function submitCheck(page: Page, claim: string): Promise<string> {
  await page.goto('/#/new')
  await page.locator('#doi').fill(DOI)
  await page.locator('#claim').fill(claim)
  await readSource(page)
  await authorize(page)
  await page.locator('.submit-row button.primary').click()
  await expect(page).toHaveURL(/#\/checks\/[^/]+$/)
  return currentId(page)
}

/** 当前详情页的任务标识。 */
export function currentId(page: Page): string {
  const found = new URL(page.url()).hash.match(/#\/checks\/([^/]+)/)
  if (!found) throw new Error(`当前不在任务详情页：${page.url()}`)
  return decodeURIComponent(found[1])
}

/** 直接打开某个任务的详情页。 */
export async function openCheck(page: Page, id: string): Promise<void> {
  await page.goto(`/#/checks/${encodeURIComponent(id)}`)
  await expect(page.locator('.result-line .status-label')).toBeVisible()
}

/** 直接打开某个任务的运行诊断页。 */
export async function openDiagnostics(page: Page, id: string): Promise<void> {
  await page.goto(`/#/checks/${encodeURIComponent(id)}/diagnostic`)
  await expect(page.getByRole('heading', { name: '运行诊断' })).toBeVisible()
}

/** 等某个任务落到给定状态文案（前端每 1.5 秒轮询一次）。 */
export async function expectStatus(page: Page, text: string): Promise<void> {
  await expect(page.locator('.result-line .status-label')).toHaveText(text)
}

/** 历史列表里的记录总条数。列表展示全部本地记录，不按 DOI 过滤。 */
export async function historyCount(page: Page): Promise<number> {
  return page.locator('.history-list button').count()
}

/** 历史列表里论断摘要等于给定文本的条目数。
 *
 * 论断摘要是至多 80 字的单行副本（后端 `CLAIM_EXCERPT_LIMIT`）；用例内的论断都短于该
 * 上限，所以按可见文本即可定位到具体某一条记录，用来断言它删除后不再出现。
 */
export async function historyClaimCount(page: Page, claim: string): Promise<number> {
  return page.locator('.history-list .history-claim').filter({ hasText: claim }).count()
}
