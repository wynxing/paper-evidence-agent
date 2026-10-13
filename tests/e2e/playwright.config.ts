import fs from 'node:fs'
import path from 'node:path'
import { defineConfig, devices } from '@playwright/test'

/**
 * 端到端维度的运行配置（测试方案「2. 维度」末尾的界面主路径）。
 *
 * 四个进程一起起：本机上游替身 → 真 API → 常驻 worker → 前端 dev server。
 * 用例只驱动浏览器，判定对象是界面行为；上游全是替身，所以这套用例**不能**
 * 用来产出论文语义结论或性能数字（Issue #26 已写明这条边界）。
 *
 * 端口是硬约束而不是自由参数：
 * - `frontend/vite.config.ts:6` 把 `/api`、`/health` 固定代理到 127.0.0.1:8000；
 * - 前端 dev server 固定 5173，用 `--strictPort` 让占用时直接失败，不要静默换端口。
 * 因此运行前请确保 8000 / 5173 / 8765 / 8001 都没有别的进程占用。
 * `reuseExistingServer` 刻意关掉：复用可能是用户自己的真实后端，那会让用例
 * 打到真实上游，而这正是本维度要避免的。
 */

const ROOT = path.resolve(__dirname, '..', '..')
const STUB_PORT = Number(process.env.PAPER_EVIDENCE_E2E_STUB_PORT ?? 8765)
const BACKEND_PORT = Number(process.env.PAPER_EVIDENCE_E2E_BACKEND_PORT ?? 8000)
const WORKER_READY_PORT = Number(process.env.PAPER_EVIDENCE_E2E_WORKER_READY_PORT ?? 8001)
const FRONTEND_PORT = Number(process.env.PAPER_EVIDENCE_E2E_FRONTEND_PORT ?? 5173)

const stubBase = `http://127.0.0.1:${STUB_PORT}`
const runDir = path.join(__dirname, '.run')

/**
 * 回环地址必须排除在代理之外，否则整套用例起不来。
 *
 * 开发机常见地设了 `HTTP_PROXY`（本机复现环境里是 `http://127.0.0.1:62800`），
 * 而两处都会读它：
 *  - Playwright 的 `config.webServer.url` 就绪检查走 `proxy-from-env`
 *    （`WebServerPlugin` → `isURLAvailable` → `httpRequest`），带代理实测把
 *    `127.0.0.1:8000/health` 的 200 变成 **404**，就绪检查因此 60 秒都过不去；
 *  - 后端用的 `httpx.AsyncClient()`（`api/deps.py:47`）默认 `trust_env=True`，
 *    会把查来源的请求也发给代理，而代理对本机替身端口的应答并不等于替身的应答。
 *
 * 所以这里把回环范围摘出代理：`NO_PROXY` 管 Playwright 自己的探活，四个代理变量
 * 置空后传给子进程管后端与替身。这套用例只跑 127.0.0.1，摘掉代理不影响任何判定。
 */
const LOOPBACK = '127.0.0.1,localhost,::1'
process.env.NO_PROXY = LOOPBACK
process.env.no_proxy = LOOPBACK

/**
 * 一次运行的所有产物都放进 `.run/` 下的**独立目录**，用例的起点就是「空任务库」。
 *
 * 不在启动脚本里删上一轮的库是有原因的：四个 webServer 并发启动，worker 可能
 * 先一步打开 SQLite，后启动的进程再去 `unlink` 就撞上文件锁（实测 WinError 32）。
 * 换成新目录既绕开锁，也保证本轮不受上一轮残留影响。
 *
 * 轨迹与报告同样按轮次分目录：Playwright 每次启动会先清空 `outputDir`，复用同一个
 * 名字等于让它去删上一轮的成百个轨迹文件。只清 `data-*`（文件很少）是安全的。
 */
function prepareRun(): { runId: string; dataDir: string } {
  if (fs.existsSync(runDir)) {
    for (const entry of fs.readdirSync(runDir)) {
      if (!entry.startsWith('data-')) continue
      try {
        fs.rmSync(path.join(runDir, entry), { recursive: true, force: true })
      } catch {
        // 上一轮残留（例如还占着句柄），忽略即可：本轮用的是新名字。
      }
    }
  }
  const runId = `${Date.now().toString(36)}-${process.pid}`
  const dir = path.join(runDir, `data-${runId}`)
  fs.mkdirSync(dir, { recursive: true })
  return { runId, dataDir: dir }
}

const { runId, dataDir } = prepareRun()

/** 后端解释器：默认用后端虚拟环境，可用环境变量覆盖。 */
const python =
  process.env.PAPER_EVIDENCE_E2E_PYTHON ??
  path.join(ROOT, 'backend', '.venv', process.platform === 'win32' ? 'Scripts/python.exe' : 'bin/python')

/** 两个 Python 进程共用的环境：同一份数据目录、同一份替身地址、同一份超时。 */
const pythonEnv = {
  PAPER_EVIDENCE_DATA_DIR: dataDir,
  PAPER_EVIDENCE_E2E_STUB_BASE: stubBase,
  PAPER_EVIDENCE_MODEL_TRANSPORT: 'gateway',
  PAPER_EVIDENCE_MODEL_BASE_URL: stubBase,
  PAPER_EVIDENCE_GATEWAY_TOKEN: 'e2e-token',
  // 语义诊断导出的接收方；未配置时界面会禁用该入口。
  PAPER_EVIDENCE_OBSERVABILITY_RECIPIENT: 'e2e-observer@example.test',
  PAPER_EVIDENCE_E2E_MODEL_ATTEMPT_SECONDS: '8',
  PAPER_EVIDENCE_E2E_BACKEND_PORT: String(BACKEND_PORT),
  PAPER_EVIDENCE_E2E_WORKER_READY_PORT: String(WORKER_READY_PORT),
  PAPER_EVIDENCE_E2E_WORKER_INTERVAL: '0.2',
  PYTHONPATH: path.join(ROOT, 'backend'),
  PYTHONUTF8: '1',
  PYTHONIOENCODING: 'utf-8',
  // 见文件头的说明：把回环摘出代理，子进程也不许走代理。
  NO_PROXY: LOOPBACK,
  no_proxy: LOOPBACK,
  HTTP_PROXY: '',
  http_proxy: '',
  HTTPS_PROXY: '',
  https_proxy: '',
}

export default defineConfig({
  testDir: './specs',
  outputDir: path.join(runDir, `results-${runId}`),
  // 用例共享同一份任务库，所以串行执行：界面状态是按顺序累积的。
  fullyParallel: false,
  workers: 1,
  forbidOnly: !!process.env.CI,
  retries: 0,
  timeout: 90_000,
  expect: { timeout: 15_000 },
  reporter: process.env.CI ? [['list'], ['html', { open: 'never', outputFolder: path.join(runDir, `report-${runId}`) }]] : [['list']],
  use: {
    baseURL: `http://127.0.0.1:${FRONTEND_PORT}`,
    trace: 'retain-on-failure',
    headless: true,
  },
  projects: [{ name: 'chromium', use: { ...devices['Desktop Chrome'] } }],
  webServer: [
    {
      command: `"${python}" ${path.join(__dirname, 'support', 'upstreams.py')}`,
      url: `${stubBase}/_stub/state`,
      reuseExistingServer: false,
      timeout: 60_000,
      env: pythonEnv,
    },
    {
      command: `"${python}" ${path.join(__dirname, 'support', 'serve_backend.py')}`,
      url: `http://127.0.0.1:${BACKEND_PORT}/health`,
      reuseExistingServer: false,
      timeout: 60_000,
      env: pythonEnv,
    },
    {
      command: `"${python}" ${path.join(__dirname, 'support', 'serve_worker.py')}`,
      port: WORKER_READY_PORT,
      reuseExistingServer: false,
      timeout: 60_000,
      env: pythonEnv,
    },
    {
      command: `npm --prefix "${path.join(ROOT, 'frontend')}" run dev -- --port ${FRONTEND_PORT} --strictPort`,
      url: `http://127.0.0.1:${FRONTEND_PORT}/`,
      reuseExistingServer: false,
      timeout: 120_000,
      env: pythonEnv,
    },
  ],
})
