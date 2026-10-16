"""Run the frozen cases against the real model and write a dated acceptance record.

Why this exists
---------------
``report.py`` writes ``docs/semantic-report.md`` driven by ``ScriptedGateway``: it
replays a transcript, so its numbers measure the pipeline and the script, never the
model. A real-model run is **not deterministic**, so it can never satisfy that
report's "regenerate and compare byte for byte" contract, and it must not be
smuggled into it.

This runner is the other half: it drives the *same* ``run_case`` with a real gateway
and writes a record that is explicitly **not reproducible** and **not a CI gate**.
Two artefacts, two jobs:

* ``docs/semantic-report.md`` — byte-checked, gate-able, proves the pipeline and the
  denominators are stable.
* ``docs/semantic-acceptance-live.md`` — generated on demand, dated, names the model,
  keeps every raw reply. This is the acceptance evidence.

Usage
-----
::

    PAPER_EVIDENCE_PROVIDER_MODEL=deepseek/deepseek-flash \
    PAPER_EVIDENCE_MODEL_API_KEY=... \
      python tests/functional/live_acceptance.py

The key is read from the environment only and is never printed. There is **no
default provider**: the record has to name the model that actually ran, so the
runner refuses to guess one.
"""

import asyncio
import datetime
import json
import os
import re
import subprocess
import sys
import tempfile
import time
from dataclasses import replace
from pathlib import Path
from urllib import request as urlrequest

from acceptance import SAMPLES, available_cases, load_case, run_case
from report import sample_fingerprint

from paper_evidence.config import Settings
from paper_evidence.models.sdk import LiteLLMSdkGateway

REPO = Path(__file__).resolve().parents[2]
DEFAULT_OUT = REPO / "docs" / "semantic-acceptance-live.md"

NO_LABEL = {"FAILED", "BLOCKED", "CANCELLED", "INTERRUPTED"}


class RecordingGateway(LiteLLMSdkGateway):
    """The real gateway, keeping every raw reply so a failure can be diagnosed.

    Without this the record says only "MODEL_INVALID_OUTPUT", which is exactly the
    kind of unactionable line this project keeps paying for.
    """

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.replies = []

    async def complete(self, request_id, prompt, deadline, **kwargs):
        reply = await super().complete(request_id, prompt, deadline, **kwargs)
        # ``response_model`` lives on the attempt, not on the call: the call may
        # hold a retry, and only the attempt records what the provider answered
        # with. The frozen ``configured_model`` is a different field entirely and
        # must not be used as a stand-in for the model that actually ran.
        attempts = getattr(getattr(reply, "call", None), "attempts", None) or []
        response_model = next(
            (item.response_model for item in reversed(attempts)
             if getattr(item, "response_model", None)), None)
        self.replies.append({
            "request_id": request_id,
            "purpose": kwargs.get("purpose"),
            "repairs": kwargs.get("repairs_request_id"),
            "text": getattr(reply, "text", ""),
            "response_model": response_model,
        })
        return reply

    def reset(self):
        self.replies = []


def head_commit() -> str | None:
    """The commit this record was produced from, so a run can be attributed.

    Best-effort by design: a record without it is still usable; a record that
    *states the wrong* commit would be worse than one that states none. So a missing
    git, a missing worktree, or a non-zero exit all yield ``None`` rather than a guess.
    """

    try:
        done = subprocess.run(
            ["git", "-C", str(REPO), "rev-parse", "HEAD"],
            capture_output=True, text=True, timeout=15, check=False,
        )
    except Exception:  # noqa: BLE001 - attribution is never worth failing a run
        return None
    value = done.stdout.strip()
    return value if done.returncode == 0 and len(value) == 40 else None


def deepseek_balance() -> str | None:
    """Best-effort balance read, so the record can carry a cost figure.

    Provider-specific and deliberately non-fatal: a missing balance must never stop
    an acceptance run.
    """

    token = os.environ.get("PAPER_EVIDENCE_MODEL_API_KEY", "")
    if not token:
        return None
    opener = urlrequest.build_opener(urlrequest.ProxyHandler({}))
    call = urlrequest.Request("https://api.deepseek.com/user/balance")
    call.add_header("Authorization", "Bearer " + token)
    try:
        with opener.open(call, timeout=30) as response:
            payload = json.loads(response.read())
        return payload["balance_infos"][0]["total_balance"]
    except Exception:  # noqa: BLE001 - a cost figure is never worth failing a run
        return None


def parse_error(text: str, purpose: str) -> str | None:
    """What the real parser says about this reply, or ``None`` when it is usable."""

    from paper_evidence.agents.output import OutputError, parse_decision_output, parse_query_output

    try:
        if purpose == "query_generation":
            parse_query_output(text)
        else:
            parse_decision_output(text)
        return None
    except OutputError as error:
        return f"{type(error).__name__}: {error}"
    except Exception as error:  # noqa: BLE001 - record anything the parser raises
        return f"{type(error).__name__}: {error}"


def label_source(row: dict) -> str:
    """Whether the label came from a model ``final`` action or from the workflow.

    A label the workflow derives itself (the bounded retrieval came back empty,
    `graph/workflow.py` returns ``INSUFFICIENT_EVIDENCE`` on its own) is **not** a
    model judgement. Counting the two together is how a record turns a degradation
    into a capability, so the record has to say which one each row is.
    """

    if row.get("actual") is None:
        return "—"
    for reply in row.get("replies") or []:
        if re.search(r'"action"\s*:\s*"final"', reply.get("text") or ""):
            return "模型判定"
    return "工作流降级"


def measure(case, work: Path, gateway: RecordingGateway) -> dict:
    gateway.reset()
    started = time.monotonic()
    try:
        outcome = run_case(case, work, gateway=gateway)
        detail = outcome.detail
        row = {
            "case_id": case.case_id,
            "expected": case.label,
            "actual": detail.label.value if detail.label is not None else None,
            "status": detail.status.value,
            "stage": detail.stage.value,
            "error": detail.error_code.value if detail.error_code else None,
            "evidence": len(detail.decision.evidence) if detail.decision is not None else None,
        }
    except Exception as error:  # noqa: BLE001 - a crashed case is a result too
        row = {"case_id": case.case_id, "expected": case.label, "actual": None,
               "status": "EXCEPTION", "stage": "-", "error": f"{type(error).__name__}: {error}",
               "evidence": None}
    row["seconds"] = round(time.monotonic() - started, 1)
    row["replies"] = [dict(reply) for reply in gateway.replies]
    for reply in row["replies"]:
        reply["parse_error"] = parse_error(reply["text"], reply["purpose"] or "")
    row["label_source"] = label_source(row)
    return row


def render(rows: list[dict], *, provider_model: str, settings, fingerprint: str,
           balance_before: str | None, balance_after: str | None, started_at: str,
           commit: str | None = None) -> str:
    matched = sum(1 for row in rows if row["actual"] == row["expected"])
    unlabelled = sum(1 for row in rows if row["actual"] is None)
    derived = sum(1 for row in rows if row.get("label_source") == "工作流降级")
    models = sorted({reply["response_model"] for row in rows for reply in row["replies"]
                     if reply.get("response_model")})

    commit_cell = f"`{commit}`" if commit else "未取到（不在 git 工作树内）"
    lines = [
        "# 真实模型语义验收记录（非门禁产物）",
        "",
        "> 本文件由 `tests/functional/live_acceptance.py` 生成，**不参与 CI**，也**不逐字节可复现**。",
        "> 它与 `docs/semantic-report.md` 分工不同：那一份由 `ScriptedGateway` 回放、逐字节可比对、由 CI 门禁；",
        "> 这一份跑真实模型，因此每次输出的字节都可能不同，只能以「某日某模型的一次实测」被引用。",
        "",
        "## 本次运行",
        "",
        "| 项 | 值 |",
        "| --- | --- |",
        f"| 生成时间 | {started_at} |",
        f"| 运行所在提交 | {commit_cell} |",
        f"| `PAPER_EVIDENCE_PROVIDER_MODEL` | `{provider_model}` |",
        f"| 上游回报的模型 | {'、'.join(f'`{m}`' for m in models) if models else '未取得（上游未回传 `model`）'} |",
        f"| 冻结快照里的 `provider_model` | `{settings.provider_model}`（本进程请求的名字；`#68` / `PR #75` 起进快照与 `config_digest`） |",
        f"| 冻结配置里的 `configured_model` | `{settings.configured_model}`（**不是实际调用的模型**，见下） |",
        f"| 样本集 | `tests/functional/samples/`，N = {len(rows)} |",
        f"| 样本集指纹 | `{fingerprint}` |",
        f"| 余额（前 → 后） | {balance_before or '未取到'} → {balance_after or '未取到'} |",
        "",
        "复现命令（需网络与凭据，会真实计费）：",
        "",
        "```bash",
        "PAPER_EVIDENCE_PROVIDER_MODEL=<provider/model> \\",
        "PAPER_EVIDENCE_MODEL_API_KEY=<key> \\",
        "  python tests/functional/live_acceptance.py",
        "```",
        "",
        "## 这份记录不能被读成什么",
        "",
        "- **不是可复现证据**。模型的输出不保证逐字节一致；引用时必须带上本文件顶部的生成时间与模型名。",
        "- **不是 CI 门禁**。它不进 `.github/workflows/`，也不该进：CI 既无网络出口也无凭据。",
        "- **不是「系统准确率」**。下游要分开看三件事：**没产出标签**、**标签由工作流降级产出**、"
        "**模型判错**。前两者都不是模型判断，不能计入任何一侧。",
        "- **「标签来源」列里的「工作流降级」不是模型的判断**。有界检索为空时由 `graph/workflow.py` "
        "自己返回 `INSUFFICIENT_EVIDENCE`（该行通常伴有 `RETRIEVAL_EMPTY`）。它可能正好与人工核对一致，"
        "但那是规则对了，不是模型对了。",
        "- **不是默认上游的表现**。产品默认上游与本次不同时，结论的可迁移性是有限的，须显式声明。",
        "",
        "## 逐例结果",
        "",
        "| case | 期望标签 | 实际标签 | 标签来源 | 终态 | 错误码 | 证据条数 | 用时 |",
        "| --- | --- | --- | --- | --- | --- | --- | --- |",
    ]
    for row in rows:
        lines.append("| `%s` | %s | %s | %s | %s | %s | %s | %ss |" % (
            row["case_id"], row["expected"], row["actual"] or "**无标签**",
            row.get("label_source") or "—",
            row["status"], row["error"] or "—",
            "—" if row["evidence"] is None else row["evidence"], row["seconds"],
        ))

    lines += [
        "",
        "| 汇总 | 值 |",
        "| --- | --- |",
        f"| 标签与人工核对一致 | **{matched} / {len(rows)}** |",
        f"| **未产出标签**（`FAILED`/`BLOCKED` 等） | **{unlabelled} / {len(rows)}** |",
        f"| 其中标签由**工作流降级**（不是模型判断）产出 | **{derived} / {len(rows)}** |",
        "",
    ]
    if balance_before and balance_before == balance_after:
        lines += [
            "> 余额前后读数相同，**不代表本次没有计费**：结算有延迟，按余额差估算花费并不可靠。",
            "",
        ]
    if unlabelled:
        lines += [
            f"> **{unlabelled} 例没有产出标签**，因此上面的「一致数」**不是准确率**：它没有把这些例计入任何一侧。",
            "> 在产出标签之前，本记录不对语义准确率作任何结论。",
            "",
        ]

    lines += ["## 原始输出（每次模型调用）", "",
              "保留原始输出是为了定位：只剩一句错误码时无法判断是模型判错还是输出形状不合契约。", ""]
    for row in rows:
        lines.append(f"### `{row['case_id']}` 的 {len(row['replies'])} 次调用")
        lines.append("")
        if not row["replies"]:
            lines.append("（本次没有产生模型调用）")
            lines.append("")
            continue
        for index, reply in enumerate(row["replies"], 1):
            lines.append("<details><summary>第 %d 次：purpose=%s、repairs=%s%s</summary>" % (
                index, reply["purpose"], reply["repairs"],
                "、解析失败" if reply.get("parse_error") else "、解析通过"))
            lines.append("")
            lines.append("```text")
            lines.append(reply["text"] or "(空)")
            lines.append("```")
            lines.append("")
            if reply.get("parse_error"):
                lines.append("解析器判定：`%s`" % reply["parse_error"])
                lines.append("")
            lines.append("</details>")
            lines.append("")
    return "\n".join(lines) + "\n"


def main() -> int:
    provider_model = os.environ.get("PAPER_EVIDENCE_PROVIDER_MODEL", "").strip()
    if not provider_model:
        print("必须先显式设置 PAPER_EVIDENCE_PROVIDER_MODEL：本记录要写明实际调用的模型，不接受猜测。",
              file=sys.stderr)
        return 2
    if not os.environ.get("PAPER_EVIDENCE_MODEL_API_KEY"):
        print("缺少 PAPER_EVIDENCE_MODEL_API_KEY（只从环境读取，不会回显）。", file=sys.stderr)
        return 2

    out = Path(sys.argv[1]) if len(sys.argv) > 1 else DEFAULT_OUT
    started_at = datetime.datetime.now(datetime.timezone.utc).astimezone().isoformat(timespec="seconds")
    balance_before = deepseek_balance()

    work = Path(tempfile.mkdtemp(prefix="live-acceptance-"))
    settings = replace(Settings.from_env(), data_dir=work, contact_email="",
                       provider_model=provider_model)
    gateway = RecordingGateway(
        provider_model=settings.provider_model,
        api_base=settings.model_api_base,
        api_key=os.environ["PAPER_EVIDENCE_MODEL_API_KEY"],
        model_alias=settings.model_alias,
        configured_model=settings.configured_model,
        deployment_id=settings.deployment_id,
        recipient=settings.primary_recipient,
        attempt_seconds=settings.timeouts.model_attempt_seconds,
        attempts_per_request=settings.limits.attempts_per_request,
    )

    rows = []
    for case_id in available_cases():
        row = measure(load_case(case_id), work, gateway)
        rows.append(row)
        print("%-28s 期望=%-6s 实际=%-6s %-10s %s" % (
            row["case_id"], row["expected"], row["actual"] or "-", row["status"],
            row["error"] or ""))

    balance_after = deepseek_balance()
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(
        render(rows, provider_model=provider_model, settings=settings,
               fingerprint=sample_fingerprint(SAMPLES), balance_before=balance_before,
               balance_after=balance_after, started_at=started_at, commit=head_commit()),
        encoding="utf-8",
    )
    matched = sum(1 for row in rows if row["actual"] == row["expected"])
    print()
    print("标签一致 %d / %d，未产出标签 %d" % (
        matched, len(rows), sum(1 for row in rows if row["actual"] is None)))
    print("已写入", out.relative_to(REPO))
    return 0


if __name__ == "__main__":
    sys.exit(main())
