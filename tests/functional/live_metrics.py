"""Run the #86 human-answer set against the real model and write a dated metrics record.

Why this exists
---------------
`#110` 的第三件事：`#86` 的 24 条人工答案齐了之后，第 3 步要求用**真实模型**
跑完并按 `docs/evaluation.md` §4 的口径算指标。`report.py` 的数字来自
`ScriptedGateway` 回放，永远证明不了模型本身；这份跑测是另一半证据——
和 `live_acceptance.py` 一样**不可复现、不接 CI 门禁**，只能以
「某日某模型的一次实测」被引用。

与 `live_acceptance.py` 的分工：那份跑 `tests/functional/samples/` 的 7 例
构造样本（验收用例）；这份跑 `tests/functional/sources/` 的真实来源集
（`#86` 人工答案，每条都签核过）。分母与对账规则完全取自
`report.metrics`，不在本文件里另造口径。

Usage
-----
::

    PAPER_EVIDENCE_PROVIDER_MODEL=deepseek/deepseek-flash \
    PAPER_EVIDENCE_MODEL_API_KEY=... \
      python tests/functional/live_metrics.py

The key is read from the environment only and is never printed. There is **no
default provider**: the record has to name the model that actually ran, so the
runner refuses to guess one.
"""

import datetime
import os
import sys
import tempfile
import time
from dataclasses import replace
from pathlib import Path

from acceptance import FrozenCase, run_case
from freeze_sources import SOURCES, freeze, load_all
from live_acceptance import RecordingGateway, deepseek_balance, head_commit, parse_error
from report import BUCKETS, Outcome, _num, _pct, metrics

from paper_evidence.config import Settings
from paper_evidence.domain.text import quote_spans

REPO = Path(__file__).resolve().parents[2]
DEFAULT_OUT = REPO / "docs" / "metrics-live-86.md"


def load_claim_cases(work: Path) -> list[FrozenCase]:
    """Fetch every frozen source live and turn each signed claim into a case.

    The inventory deliberately stores **no article text** (drift must stay
    visible), so the JATS is re-fetched from the upstream here. A source whose
    live text no longer matches its frozen hashes will fail the quote checks
    downstream — that is the correct behaviour, not something to patch by
    trusting a cached copy.
    """

    cases: list[FrozenCase] = []
    for entry in sorted(load_all(SOURCES), key=lambda item: item["case_id"]):
        snapshot = freeze(entry["provenance"]["doi"], work, with_text=True)
        jats = snapshot["jats_text"].encode("utf-8")
        for claim in entry["claims"]:
            cases.append(FrozenCase(
                case_id=claim["claim_id"],
                claim=claim["claim"],
                doi=entry["provenance"]["doi"],
                label=claim["expected_label"],
                jats=jats,
                quotes={},
                transcript=(),
            ))
    return cases


def measure(case: FrozenCase, work: Path, gateway: RecordingGateway) -> dict:
    """Run one claim and record what the system published, quotes included."""

    gateway.reset()
    started = time.monotonic()
    try:
        outcome = run_case(case, work, gateway=gateway)
        detail = outcome.detail
        evidence = detail.decision.evidence if detail.decision is not None else []
        located = sum(
            1 for item in evidence
            if (paragraph := outcome.paragraphs.get(item.paragraph_id)) is not None
            and quote_spans(paragraph.text, item.quote)
        )
        row = {
            "case_id": case.case_id,
            "expected": case.label,
            "actual": detail.label.value if detail.label is not None else None,
            "status": detail.status.value,
            "error": detail.error_code.value if detail.error_code else None,
            "quotes_total": len(evidence),
            "quotes_located": located,
        }
    except Exception as error:  # noqa: BLE001 - a crashed case is a result too
        row = {"case_id": case.case_id, "expected": case.label, "actual": None,
               "status": "EXCEPTION", "error": f"{type(error).__name__}: {error}",
               "quotes_total": 0, "quotes_located": 0}
    row["seconds"] = round(time.monotonic() - started, 1)
    row["replies"] = [dict(reply) for reply in gateway.replies]
    for reply in row["replies"]:
        reply["parse_error"] = parse_error(reply["text"], reply["purpose"] or "")
    return row


def label_source(row: dict) -> str:
    """Whether the label came from a model ``final`` action or from the workflow."""

    if row.get("actual") is None:
        return "—"
    for reply in row.get("replies") or []:
        if '"action"' in (reply.get("text") or "") and '"final"' in (reply.get("text") or ""):
            return "模型判定"
    return "工作流降级"


def render(rows: list[dict], *, provider_model: str, fingerprint: str,
           balance_before: str | None, balance_after: str | None,
           started_at: str, commit: str | None) -> str:
    outcomes = [
        Outcome(case_id=row["case_id"], expected=row["expected"], status=row["status"],
                label=row["actual"], quotes_total=row["quotes_total"],
                quotes_located=row["quotes_located"])
        for row in rows
    ]
    m = metrics(outcomes)
    counts = m["counts"]

    lines: list[str] = []
    add = lines.append

    add("# 真实来源集语义指标记录（#86 人工答案 × 真实模型，非门禁产物）")
    add("")
    add("> 本文件由 `tests/functional/live_metrics.py` 生成，**不参与 CI**，也**不逐字节可复现**。")
    add("> 它跑的是 `tests/functional/sources/` 的真实来源集（`#86` 人工答案集），")
    add("> 分母与对账规则完全取自 `report.metrics`（`docs/evaluation.md` §4），本文件不另造口径。")
    add("> 它与 `docs/semantic-report.md`（回放、逐字节可比对、CI 门禁）分工不同，")
    add("> 引用时必须带上本文件顶部的生成时间与模型名。")
    add("")
    add("## 本次运行")
    add("")
    add("| 项 | 值 |")
    add("| --- | --- |")
    add(f"| 生成时间 | {started_at} |")
    add(f"| 运行所在提交 | {'`' + commit + '`' if commit else '未取到（不在 git 工作树内）'} |")
    add(f"| `PAPER_EVIDENCE_PROVIDER_MODEL` | `{provider_model}` |")
    add(f"| 答案集 | `tests/functional/sources/`，N = {m['total']}（4 篇来源，全部签核 agree） |")
    add(f"| 答案集指纹 | `{fingerprint}` |")
    add(f"| 余额（前 → 后） | {balance_before or '未取到'} → {balance_after or '未取到'} |")
    add("")
    add("复现命令（需网络与凭据，会真实计费）：")
    add("")
    add("```bash")
    add("PAPER_EVIDENCE_PROVIDER_MODEL=<provider/model> \\")
    add("PAPER_EVIDENCE_MODEL_API_KEY=<key> \\")
    add("  python tests/functional/live_metrics.py")
    add("```")
    add("")
    add("## 这份记录不能被读成什么")
    add("")
    add("- **不是可复现证据**。引用时必须带上生成时间与模型名；CI 不跑它，也不该跑。")
    add("- **不是总体准确率**。N = %d，单次抽样，指标只在本次有限验收集内成立。" % m["total"])
    add("- **真值是单人复核签核的**（`#86` 的 review 字段），不是双人独立标注后的仲裁结果，")
    add("  分歧解决前不构成正式真值（`docs/evaluation.md` §2 的标注规程是研究集的要求，")
    add("  首版小规模验收明确不以它为前提）。")
    add("- **「标签来源」列里的「工作流降级」不是模型的判断**（有界检索为空时工作流自己返回）。")
    add("")
    add("## 1. 执行结果分布（分母对账）")
    add("")
    add("互斥恒等式：`N = D + I + B + F + C + X + U`")
    add("")
    add("| 桶 | 数量 | 含义 |")
    add("| --- | --- | --- |")
    for key in ("D", "I", "B", "F", "C", "X", "U"):
        add(f"| {key} | {counts[key]} | {BUCKETS[key]} |")
    identity = sum(counts[key] for key in ("D", "I", "B", "F", "C", "X", "U"))
    add("")
    add(f"校验：D+I+B+F+C+X+U = {identity}，{'与 N 一致' if identity == m['total'] else '**与 N 不一致**'}。")
    add("")
    add("## 2. 关键指标")
    add("")
    add("| 指标 | 值 | 分子/分母 |")
    add("| --- | --- | --- |")
    add(f"| 可判定覆盖率（全批次） | {_pct(m['coverage_all'])} | {counts['D']}/{m['total']} |")
    add(f"| 可判定覆盖率（真值可判定子集） | {_pct(m['coverage_truth_decidable'])} "
        f"| {m['decided_on_truth_decidable']}/{m['truth_decidable_n']} |")
    if m["published_quotes"] == 0:
        add("| 摘录定位有效率 | 不适用 | 本次没有确定判断，未发布摘录 |")
    else:
        add(f"| 摘录定位有效率 | {_pct(m['locatability'])} "
            f"| {m['located_quotes']}/{m['published_quotes']} |")
    add(f"| 语义标签正确数/总数 | {m['labels_correct']}/{m['total']} | — |")
    add("")
    add("## 3. 逐标签 precision / recall")
    add("")
    add("`precision = TP/(TP+FP)`、`recall = TP/(TP+FN)`；真值为该类但系统**拒判或执行失败**"
        "的样本计入该类 FN，不从分母移除。")
    add("")
    add("| 标签 | 真实样本数 | 预测数 | TP | FP | FN | precision | recall |")
    add("| --- | --- | --- | --- | --- | --- | --- | --- |")
    for label in ("支持", "部分支持", "相矛盾", "证据不足"):
        row = m["per_label"][label]
        note = "（单列）" if label == "相矛盾" else ""
        add(f"| {label}{note} | {row['truth_n']} | {row['pred_n']} | {row['tp']} | {row['fp']} "
            f"| {row['fn']} | {_num(row['precision'])} | {_num(row['recall'])} |")
    add("")
    conflict = m["per_label"]["相矛盾"]["recall"]
    add(f"**证据冲突识别率**（相矛盾类 recall）= {_num(conflict)}；"
        + ("真值可判定子集里没有相矛盾样本，该指标记 **N/A**，不能写 0 或 100%。"
           if conflict is None else
           "分子分母都来自本次真实运行，不是回放。"))
    add("")
    add("## 4. macro-F1（真值可判定三类，等权）")
    add("")
    add("| 类别 | F1 |")
    add("| --- | --- |")
    for label in ("支持", "部分支持", "相矛盾"):
        add(f"| {label} | {_num(m['f1_by_label'][label])} |")
    add(f"| **macro-F1** | **{_num(m['macro_f1'])}** |")
    add("")
    add(f"参与平均的类别：{'、'.join(m['macro_f1_labels']) or '无（整体 N/A）'}。")
    add("")
    add("## 5. 应拒判样本上的错误确定判断率")
    add("")
    add("R 为独立标注（签核）为证据不足的样本集合，不按系统输出倒推。")
    add("")
    add("| 项目 | 值 |")
    add("| --- | --- |")
    add(f"| R 总数 | {m['r_total']} |")
    add(f"| R 中 COMPLETED | {m['r_completed']} |")
    add(f"| R 中输出确定判断（错误确定判断） | {m['r_wrong']} |")
    add(f"| 错误确定判断率（/ COMPLETED） | {_num(m['r_error_rate'])} |")
    add(f"| 全批次发生率（/ R 总数） | {_num(m['r_error_rate_all'])} |")
    add("")
    if m["misjudged"]:
        add(f"误判（真值可判定却判成别的确定标签）：{'、'.join(f'`{c}`' for c in m['misjudged'])}。")
    if m["over_refused"]:
        add(f"过度拒判（真值可判定却判成证据不足）：{'、'.join(f'`{c}`' for c in m['over_refused'])}。")
    if not m["misjudged"] and not m["over_refused"]:
        add("无误判、无过度拒判。")
    add("")
    add("## 6. 逐条结果")
    add("")
    add("| case | 期望标签 | 实际标签 | 标签来源 | 终态 | 错误码 | 发布引文（定位/总数） | 用时 |")
    add("| --- | --- | --- | --- | --- | --- | --- | --- |")
    for row in rows:
        add("| `%s` | %s | %s | %s | %s | %s | %s/%s | %ss |" % (
            row["case_id"], row["expected"], row["actual"] or "**无标签**",
            label_source(row), row["status"], row["error"] or "—",
            row["quotes_located"], row["quotes_total"], row["seconds"],
        ))
    matched = sum(1 for row in rows if row["actual"] == row["expected"])
    derived = sum(1 for row in rows if label_source(row) == "工作流降级")
    add("")
    add("| 汇总 | 值 |")
    add("| --- | --- |")
    add(f"| 标签与人工答案一致 | **{matched} / {len(rows)}** |")
    add(f"| 其中由**工作流降级**产出（不是模型判断） | {derived} |")
    add("")
    add("## 7. 原始输出（每次模型调用）")
    add("")
    add("保留原始输出是为了定位：只剩一句错误码时无法判断是模型判错还是输出形状不合契约。")
    add("")
    for row in rows:
        add(f"### `{row['case_id']}` 的 {len(row['replies'])} 次调用")
        add("")
        if not row["replies"]:
            add("（本次没有产生模型调用）")
            add("")
            continue
        for index, reply in enumerate(row["replies"], 1):
            add("<details><summary>第 %d 次：purpose=%s%s</summary>" % (
                index, reply["purpose"], "、解析失败" if reply.get("parse_error") else "、解析通过"))
            add("")
            add("```text")
            add(reply["text"] or "(空)")
            add("```")
            add("")
            if reply.get("parse_error"):
                add("解析器判定：`%s`" % reply["parse_error"])
                add("")
            add("</details>")
            add("")
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

    work = Path(tempfile.mkdtemp(prefix="live-metrics-"))
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

    cases = load_claim_cases(work)
    print(f"来源取回完成，共 {len(cases)} 条签核答案，开始真实模型跑测……")
    rows = []
    for case in cases:
        row = measure(case, work, gateway)
        rows.append(row)
        print("%-24s 期望=%-6s 实际=%-6s %-10s %s" % (
            row["case_id"], row["expected"], row["actual"] or "-", row["status"],
            row["error"] or ""))

    balance_after = deepseek_balance()
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(
        render(rows, provider_model=provider_model,
               fingerprint=source_fingerprint(), balance_before=balance_before,
               balance_after=balance_after, started_at=started_at,
               commit=head_commit()),
        encoding="utf-8",
    )
    matched = sum(1 for row in rows if row["actual"] == row["expected"])
    print()
    print("标签一致 %d / %d，未产出标签 %d" % (
        matched, len(rows), sum(1 for row in rows if row["actual"] is None)))
    print("已写入", out.relative_to(REPO))
    return 0


def source_fingerprint() -> str:
    """Hash the committed answer-set files, the input that determines the truth."""

    import hashlib
    digest = hashlib.sha256()
    for path in sorted(SOURCES.glob("PMC*.json")):
        digest.update(path.name.encode("utf-8"))
        digest.update(path.read_bytes())
    return digest.hexdigest()[:16]


if __name__ == "__main__":
    sys.exit(main())
