# 验证记录

## 前端工作台（2026-10-05）

在更新后的 main `240e9ae` 创建独立工作树及 `feat/frontend-workbench` 分支。仅修改前端和相关文档；后端代码、公共 TS 契约、依赖版本及锁定文件均保持不变。没有来源或模型调用，也未部署。未配置仓库 CI，本节是本地验证，不替代未参与实现的团队成员独立评审。

环境：Windows / PowerShell、Python 3.12.10、Node 24.18.1、npm 11.16.0；另从 Node.js 官方发行源取得 Node 22.12.0，放在 Git 忽略的 `.cache/node22`，核对最低版本的测试及构建。

| 实际检查 | 结果 |
| --- | --- |
| `npm --prefix frontend ci` | 安装现有 45 个锁定包，未新增依赖，安装报告 0 vulnerabilities |
| `npm --prefix frontend test` | 16 passed；Node 内置测试覆盖接口异常、响应中断不重发、授权失效、两种取消分支、串行轮询、迟到响应、重试保留、空历史、任务及接收方一致性、数据契约和导出字段投影 |
| `.cache/node22/node.exe --experimental-strip-types --test frontend/tests/*.test.mjs` | 最低版本 Node 22.12.0：16 passed，保留类型擦除实验性警告 |
| `npm --prefix frontend run build` | vue-tsc 类型检查和 Vite 构建通过 |
| 在 frontend 目录以 Node 22.12.0 分别运行 `node_modules/vue-tsc/bin/vue-tsc.js --noEmit`、`node_modules/vite/bin/vite.js build` | 类型检查及构建通过 |
| `backend/.venv/Scripts/python -m pytest -c backend/pyproject.toml -q` | 54 passed，1 条现有 Starlette TestClient/httpx 弃用警告；未隐藏或调整依赖 |
| `backend/.venv/Scripts/python -m pip check` | No broken requirements found |
| Node fetch 经开发代理读取 `/health`、空 body 创建任务、读取 `/api/run-config` | 分别为 200、422、501；422 返回已声明缺失字段，业务接口仍未实现 |
| `git diff --check` | 无空白错误；Windows Git 有 LF/CRLF 工作副本提示 |

内置浏览器使用本机演示端口检查了文献预览、未确认时禁用提交、编辑后云授权失效、重新确认并创建模拟任务、运行至部分支持、多证据展示、独立反馈、取消模拟运行任务、删除确认及执行、旧任务重新授权入口、诊断预览和导出确认。补充检查了长论断、手动拆分后提交关联任务、重新授权并重试，三条新记录及原记录均保留。真实模式 501 时输入保持、没有回退构造结果。桌面 1440px、平板 1024px 与窄屏 390px 检查布局、证据页签、导航与 Escape 焦点恢复，观察的页面宽度无横向溢出；平板证据页签可用 Enter 切换，hash 路由前进和后退正常。截图是构造输入及模拟结果，保留在 Git 忽略的本地缓存中。

下载完成事件在内置浏览器和 Chrome 中均超时，未确认实际文件落盘；进一步查看下载管理页被浏览器 URL 安全策略阻断，没有绕过。导出投影与权限交互已验证，实际下载完成仍需独立验收；界面仅提示已发起下载。纯模块测试覆盖网络异常、空历史和轮询停止，但不能替代全部浏览器端场景；浏览器后台切换、短暂加载态、断网态和空历史，以及真实重试等实测范围须按后续记录补齐。

初轮前端检查发现 TypeScript 对嵌套 unknown 的收窄错误及取消测试未区分排队/运行状态，修复为逐层响应校验，并分别覆盖排队直接 CANCELLED 与运行受理后收尾；没有削弱既有后端断言。窄屏检查发现遮罩点击区域与侧栏重叠，改为只覆盖抽屉右侧，并增加焦点约束。

本节不验证真实论文语义、来源许可处理、后端任务持久化、模型调用、真实取消/超时时限或诊断包服务端脱敏。接口缺口和固定降级见 [前端工作台指南](frontend-workbench.md)。

---

## 本轮范围

| 项目 | 记录 |
| --- | --- |
| 状态 | 文档修订；用户要求从 PR 中移除文档检查脚本、脚本回归和 GitHub Actions 工作流 |
| 验证对象 | 设计文档提交 9792413 的后续修订；远端分支在本记录更新后核对 |
| 环境 | Windows / PowerShell、Python 3.12.10 |
| 对象 | README 及六份设计/测试 Markdown、决策记录和本验证记录；不含应用实现 |

## 实际检查

| 检查 | 结果 |
| --- | --- |
| `git diff --check` | 本次修订完成后执行；结果见当前 PR 提交记录 |
| 文档链接、示例及契约 | 本轮没有保留可复用的自动检查器。前一临时版本曾运行一次性静态检查及检查器回归，但对应脚本和工作流按用户要求移除；其通过结果不等于最终提交具备 CI 守护。 |
| GitHub Actions | 当前 PR 版本不包含文档工作流；9792413 上曾触发的成功记录不代表本次提交有 CI 检查。 |

## 未覆盖项

没有应用或应用测试套件，也没有冻结语义集。未运行 Proxy/Agnes/Langfuse 集成、真实模型或 DOI API、取消/截止时间/性能、论文语义验收或正式研究。文本定位、判据摘要、审计缺口及统计规则均是待实现的契约，尚无应用测试证明。未全量检查外链；不声称检查了所有敏感信息。

后续验证记录须关联实际提交，逐项列出环境、命令、真实结果和未覆盖项。不可用临时检查结果或旧提交 CI 冒充当前提交验证。

## 骨架评审修正

| 项目 | 记录 |
| --- | --- |
| 状态 | 在 `codex/project-scaffold` 上处理 PR #4 评审；父提交 `c588193`。本记录随修正提交 `47d15191226d0c394598dec7548433fbc0400bc2` 落地 |
| 环境 | Linux、Python 3.12.14、Node.js v26.10.0、npm 12.2.0。仓库未配置 CI，结果来自本地检查 |
| 对象 | 接口占位、领域契约、端口说明、锁定文件、README、开发指南和前端类型。没有来源解析、持久化、模型调用或任务执行实现 |

## 实际检查

| 检查 | 结果 |
| --- | --- |
| `backend/.venv/bin/python -m pytest -c backend/pyproject.toml -q` | 21 passed，1 条 Starlette TestClient 对 httpx 的弃用警告 |
| `backend/.venv/bin/python -m pip check` | No broken requirements found |
| `npm --prefix frontend ci && npm --prefix frontend run build` | 安装锁定依赖后，vue-tsc 与 Vite 构建通过 |
| README 与开发指南的本地链接、`git diff --check` | 本地链接均存在；`git diff --check` 无输出 |

## 未覆盖项

来源解析、持久化、真实模型调用、任务执行和论文语义验收仍未实现。实现方没有在 Windows 上重跑测试；原 Windows 失败来自评审记录的 `socket.connect` 拦截，本次改为拦截 `create_connection` 与 `getaddrinfo`，并在 Windows 上改用选择器事件循环。[评审方复审](https://github.com/wynxing/paper-evidence-agent/pull/4#issuecomment-5950892819)报告在 Windows / Python 3.13 上复现此提交为 21 passed、1 warning；这是第三方记录，不是实现方本机验证，也不代表 editable 安装支持 Python 3.13。临时目录为空不能证明没有绝对路径写入。没有性能、取消时限或真实论文验收数据。

## 最新复审修正（2026-10-02）

| 项目 | 记录 |
| --- | --- |
| 对象提交 | `51b2a25929daadf9219fe2bd215dc6bee9e0ba0b`；先提交代码及契约文档，再在独立记录提交中写入本节，避免提交哈希自指 |
| 关联 | PR #4 最新复审 N1–N6；在独立工作树、临时分支 `codex/pr4-review-followup` 修复，普通推送回原分支 `codex/project-scaffold` |
| 环境 | Linux、Python 3.12.14、Node.js v26.10.0、npm 12.2.0；新建 venv 并安装既有锁定依赖。没有新增依赖或 CI |
| 改动 | 保留 HTTP 错误响应头、来源预览 ContractError 映射、创建任务 409 模型、422 脱敏字段信息、TS 对象形状及响应状态双向检查、默认预算/超时工厂和平台说明 |

### 实际检查

以下命令均从独立工作树的仓库根目录执行，完整测试和构建在对象提交已落地且工作区干净时运行。

| 检查 | 结果 |
| --- | --- |
| `backend/.venv/bin/python -m pip install -r backend/requirements.lock` | 新 venv 安装锁定的运行、测试和构建依赖成功 |
| `backend/.venv/bin/python -m pip install --no-deps --no-build-isolation -e backend` | editable 安装成功 |
| `npm --prefix frontend ci` | 安装 45 个锁定包成功，安装输出报告 0 vulnerabilities；未升级依赖 |
| `backend/.venv/bin/python -m pytest -c backend/pyproject.toml -q` | **54 passed，1 warning**。警告仍为 Starlette TestClient 对 httpx 的弃用提示，未隐藏或新增 httpx2 |
| `backend/.venv/bin/python -m pip check` | No broken requirements found |
| `npm --prefix frontend run build` | vue-tsc 类型检查及 Vite 生产构建通过 |
| 本地 Markdown 文件链接检查（Python 内联脚本，见下方命令） | README、architecture、development、verification 四文件共 41 个本地文件链接存在；不检查锚点及外部 URL |
| `git diff --check`、`git diff --cached --check`、暂存文件范围与凭据模式检查 | 无空白错误；代码提交仅 11 个任务文件，未包含环境、node_modules、dist 或缓存；未匹配私钥、OpenAI/AWS/GitHub 凭据模式。不是全仓敏感信息审计 |

链接检查命令：

```bash
backend/.venv/bin/python - <<'PY'
import re
from pathlib import Path
files = [Path('README.md'), Path('docs/architecture.md'), Path('docs/development.md'), Path('docs/verification.md')]
count = 0
for source in files:
    for target in re.findall(r'\[[^\]]+\]\(([^)]+)\)', source.read_text(encoding='utf-8')):
        path = target.split('#', 1)[0]
        if not path or re.match(r'[a-z]+://', path):
            continue
        assert (source.parent / path).is_file(), (source, target)
        count += 1
print(f'{count} local file links passed')
PY
```

### 失败与修复过程

初轮完整测试为 **4 failed / 49 passed**：422 脱敏字段路径使用了当前 FastAPI 已移除的 ModelField.type_，导致已声明的字段也被遮成 `<unknown>`。对照安装版本确认应读取 field_info.annotation 后修复；新增公共响应规则检查后，对象提交的完整套件为上述 54 passed。没有削弱字段路径断言。首次提交因环境未配置 Git 作者身份失败，随后仅在提交命令中沿用原 PR 提交的作者身份，没有修改全局或仓库配置。

### 覆盖与限制

新增检查使用合成请求及测试应用：九种来源预览业务错误保留真实错误码和 HTTP 映射；未定义的错误或其他端点不会被预览映射重分类；405 保留 Allow、自定义头透传、结构化 HTTPException 日志不含原始键值；422 覆盖缺字段、类型错误、非法 JSON、查询字段、数组位置及额外字段脱敏。前后端对象检查覆盖继承、Omit、字段集合、必填性和可空性，包含刻意改变接口的失败用例；响应状态检查覆盖两侧状态增删、错误模型及公共规则移除。七个默认配置值从术语表核对，并验证每次生成独立实例。

业务路由仍为 501，健康检查仍为 200。未实现或验证真实来源请求、任务持久化、模型接入、业务取消/超时执行、性能、论文语义或诊断脱敏能力。对象形状检查不等于完整 TypeScript/OpenAPI 类型等价证明。此新提交未在 Windows 上重跑；上一轮评审方的 21 passed 不能代替本轮 Windows 验证。仓库没有 CI，仍需未参与实现的团队成员独立复审后再考虑合并。
