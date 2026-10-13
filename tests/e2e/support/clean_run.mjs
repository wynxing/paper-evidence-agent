/**
 * 删掉上一轮运行留下的数据目录（`.run/data-*`），由 `npm test` 的 pretest 调用。
 *
 * 这件事不能放在 `playwright.config.ts` 里做。配置在一次运行中会被评测多次——
 * runner 一次，每个测试 worker 进程各一次——而 `data-<runId>` 是 runner 那次评测
 * 建出来、写进四个 webServer 的环境里的。放在配置里就等于在运行中途把本轮的库删掉：
 * POSIX 上 `rmSync` 会成功，API 与常驻 worker 于是各自拿着一个已经 unlink 的文件
 * 继续跑，worker 再也看不到 API 写进去的任务，界面上所有任务都停在「排队中」；
 * Windows 上因为有进程占着库而删除失败，反倒看不出这个错。放这里则一次运行只跑一次，
 * 删的只会是上一轮的目录。
 *
 * 删不掉（例如上一轮的进程还占着库）不算失败：本轮用的是新目录，不受影响。
 */

import fs from 'node:fs'
import path from 'node:path'
import { fileURLToPath } from 'node:url'

const runDir = path.join(path.dirname(fileURLToPath(import.meta.url)), '..', '.run')

let removed = 0
let kept = 0
if (fs.existsSync(runDir)) {
  for (const entry of fs.readdirSync(runDir)) {
    if (!entry.startsWith('data-')) continue
    try {
      fs.rmSync(path.join(runDir, entry), { recursive: true, force: true })
      removed += 1
    } catch {
      kept += 1
    }
  }
}

console.log(`clean-run: 上一轮数据目录 removed=${removed} kept=${kept}`)
