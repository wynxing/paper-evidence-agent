"""Report the functional-accuracy metrics required by 测试方案「报告」 and 评测口径 §4.

Run from this directory::

    python report.py            # writes docs/semantic-report.md

The denominators follow ``docs/evaluation.md`` §4 (the mutual-exclusion identity
``N = D + I + B + F + C + X + U`` and the "分母为零记 N/A" rule) rather than any
convenience definition invented here. A ratio whose denominator is zero is
reported as ``None`` and rendered as ``N/A`` — never as 0 or 100%.

The sample set is a *constructed* first version, so the report states that the
labels are not claimed to be stable and the numbers are not a population
accuracy estimate (测试方案「采样与分母」).

Two properties make the report checkable rather than merely readable:

* every count appearing in the prose is derived from :func:`metrics`, so the
  text can never drift from the tables it summarises; and
* the report carries no commit-dependent field (an embedded ``git rev-parse
  HEAD`` would change on every commit and could never pass a "regenerate and
  diff" check). Provenance is the digest of the sample set, which is the input
  that actually determines the numbers. ``python report.py --check`` exits
  non-zero when the committed report differs from a fresh generation.
"""

import difflib
import hashlib
import sys
from dataclasses import dataclass
from pathlib import Path
from tempfile import TemporaryDirectory

from acceptance import SAMPLES, available_cases, load_case, run_case

from paper_evidence.domain.text import quote_spans

DEFINITIVE = ("支持", "部分支持", "相矛盾")
ALL_LABELS = (*DEFINITIVE, "证据不足")

#: evaluation.md §4: the buckets are mutually exclusive and must sum to N.
BUCKETS = {
    "D": "COMPLETED 且标签为确定判断（支持/部分支持/相矛盾）",
    "I": "COMPLETED 且标签为证据不足",
    "B": "BLOCKED",
    "F": "FAILED",
    "C": "CANCELLED",
    "X": "INTERRUPTED",
    "U": "QUEUED/RUNNING 及尚未创建的槽位",
}
_STATUS_BUCKET = {"BLOCKED": "B", "FAILED": "F", "CANCELLED": "C", "INTERRUPTED": "X",
                  "QUEUED": "U", "RUNNING": "U"}


@dataclass
class Outcome:
    """One frozen slot and what the system published for it."""

    case_id: str
    expected: str
    status: str
    label: str | None
    quotes_total: int
    quotes_located: int

    @property
    def is_completed(self) -> bool:
        return self.status == "COMPLETED"

    @property
    def is_definitive(self) -> bool:
        return self.label in DEFINITIVE


def collect(cases, work_dir) -> list[Outcome]:
    """Run every frozen case and record what it published."""

    outcomes: list[Outcome] = []
    for case in cases:
        run = run_case(case, work_dir)
        detail = run.detail
        evidence = detail.decision.evidence if detail.decision is not None else []
        located = sum(
            1 for item in evidence
            if (paragraph := run.paragraphs.get(item.paragraph_id)) is not None
            and quote_spans(paragraph.text, item.quote)
        )
        outcomes.append(Outcome(
            case_id=case.case_id,
            expected=case.label,
            status=detail.status.value,
            label=detail.label.value if detail.label is not None else None,
            quotes_total=len(evidence),
            quotes_located=located,
        ))
    return outcomes


def bucket(outcome: Outcome) -> str:
    if outcome.is_completed:
        return "D" if outcome.is_definitive else "I"
    return _STATUS_BUCKET.get(outcome.status, "U")


def ratio(numerator: int, denominator: int) -> float | None:
    """A ratio, or ``None`` when the denominator is zero (rendered as N/A)."""

    return None if denominator == 0 else numerator / denominator


def metrics(outcomes: list[Outcome]) -> dict:
    """Every reported number, with ``None`` wherever the denominator is zero."""

    counts = {key: 0 for key in BUCKETS}
    for outcome in outcomes:
        counts[bucket(outcome)] += 1
    total = len(outcomes)

    # --- per-label confusion counts (evidence-insufficient is a real label here) ---
    per_label = {}
    for label in ALL_LABELS:
        truth_n = sum(1 for o in outcomes if o.expected == label)
        pred_n = sum(1 for o in outcomes if o.label == label)
        tp = sum(1 for o in outcomes if o.expected == label and o.label == label)
        fp = sum(1 for o in outcomes if o.expected != label and o.label == label)
        # A truth-positive that the system refused or failed on is a false
        # negative; evaluation.md §4 forbids dropping those from the denominator.
        fn = truth_n - tp
        per_label[label] = {
            "truth_n": truth_n, "pred_n": pred_n, "tp": tp, "fp": fp, "fn": fn,
            "precision": ratio(tp, tp + fp), "recall": ratio(tp, tp + fn),
        }

    # --- macro-F1 over the decidability-truth subset only ---
    f1_by_label = {}
    for label in DEFINITIVE:
        row = per_label[label]
        f1_by_label[label] = ratio(2 * row["tp"], 2 * row["tp"] + row["fp"] + row["fn"])
    contributing = {k: v for k, v in f1_by_label.items() if v is not None}
    macro_f1 = sum(contributing.values()) / len(contributing) if contributing else None

    # --- decidability coverage ---
    decided = counts["D"]
    truth_decidable = sum(1 for o in outcomes if o.expected in DEFINITIVE)
    decided_on_truth_decidable = sum(
        1 for o in outcomes if o.expected in DEFINITIVE and o.is_definitive
    )

    # --- locatability, only meaningful when something was published ---
    published_quotes = sum(o.quotes_total for o in outcomes)
    located_quotes = sum(o.quotes_located for o in outcomes)

    # --- the should-refuse set R and the error rate on it ---
    r_set = [o for o in outcomes if o.expected == "证据不足"]
    r_completed = [o for o in r_set if o.is_completed]
    r_wrong = [o for o in r_completed if o.is_definitive]

    # --- misjudgements and over-refusals, listed separately ---
    misjudged = [o for o in outcomes if o.expected in DEFINITIVE and o.is_definitive
                 and o.label != o.expected]
    over_refused = [o for o in outcomes if o.expected in DEFINITIVE and o.is_completed
                    and o.label == "证据不足"]
    correct_labels = sum(1 for o in outcomes if o.label == o.expected)

    return {
        "total": total,
        "counts": counts,
        "labels_correct": correct_labels,
        "coverage_all": ratio(decided, total),
        "coverage_truth_decidable": ratio(decided_on_truth_decidable, truth_decidable),
        "truth_decidable_n": truth_decidable,
        "decided_on_truth_decidable": decided_on_truth_decidable,
        "locatability": ratio(located_quotes, published_quotes),
        "published_quotes": published_quotes,
        "located_quotes": located_quotes,
        "per_label": per_label,
        "f1_by_label": f1_by_label,
        "macro_f1": macro_f1,
        # DEFINITIVE order, so the prose below matches the F1 table above it;
        # a plain sort() would reorder the labels by Unicode code point.
        "macro_f1_labels": [label for label in DEFINITIVE if label in contributing],
        "r_total": len(r_set),
        "r_completed": len(r_completed),
        "r_wrong": len(r_wrong),
        "r_error_rate": ratio(len(r_wrong), len(r_completed)),
        "r_error_rate_all": ratio(len(r_wrong), len(r_set)),
        "misjudged": [o.case_id for o in misjudged],
        "over_refused": [o.case_id for o in over_refused],
        "pending": counts["U"],
        "distribution": {label: sum(1 for o in outcomes if o.expected == label) for label in ALL_LABELS},
    }


def _pct(value: float | None) -> str:
    return "N/A" if value is None else f"{value * 100:.1f}%"


def _num(value: float | None) -> str:
    return "N/A" if value is None else f"{value:.2f}"


def render(outcomes: list[Outcome], *, sample_fingerprint: str) -> str:
    """Render the report; every N/A is a zero denominator, never a silent zero."""

    m = metrics(outcomes)
    lines: list[str] = []
    add = lines.append

    add("# 语义验收报告：功能准确性维度")
    add("")
    add("本文件由 `tests/functional/report.py` 生成，不要手工编辑。")
    add("")
    add("## 0. 口径与限制")
    add("")
    add(f"- 数据来源：`tests/functional/samples/` 的冻结样本，样本集指纹 `{sample_fingerprint}`。"
        "报告内不含随 commit 变化的字段，同一样本集重新生成的结果逐字节一致"
        "（可用 `python report.py --check` 校验；生成时的 commit 记录在验证日志里，不写进正文）。")
    add(f"- 样本量：**N = {m['total']}**，全部为**人工构造**的最小可解析快照"
        "（每个样本标注 `claim_kind: \"constructed\"`），不是真实论文原文。")
    add(f"- **不声称标签稳定，也不构成总体准确率估计**：首版 N = {m['total']} 为单次抽样，"
        "指标只在本次有限验收集内成立（测试方案「采样与分母」）。")
    add("- 分母与对账规则取自 `docs/evaluation.md` §4；任何分母为零的比率记 **N/A**，"
        "不补成 0 或 100%。")
    add("- 真值由单人整理、**尚无第二人复核**，分歧解决前不计为确定真值。")
    if m["pending"]:
        add(f"- **U = {m['pending']}**：存在未结算槽位，以下所有指标均为**暂定**，"
            "不得作为最终质量结论发布。")
    add("")

    add("## 1. 执行结果分布（分母对账）")
    add("")
    add("互斥恒等式：`N = D + I + B + F + C + X + U`")
    add("")
    add("| 计数 | 值 | 含义 |")
    add("| --- | --- | --- |")
    add(f"| N | {m['total']} | 封存槽位总数 |")
    for key, meaning in BUCKETS.items():
        add(f"| {key} | {m['counts'][key]} | {meaning} |")
    add("")
    identity = m["counts"]["D"] + m["counts"]["I"] + m["counts"]["B"] + m["counts"]["F"] \
        + m["counts"]["C"] + m["counts"]["X"] + m["counts"]["U"]
    add(f"校验：D+I+B+F+C+X+U = {identity}，{'与 N 一致' if identity == m['total'] else '**与 N 不一致**'}。")
    add("")

    add("## 2. 样本类别分布")
    add("")
    add("| 真值标签 | 样本数 |")
    add("| --- | --- |")
    for label in ALL_LABELS:
        add(f"| {label} | {m['distribution'][label]} |")
    add("")

    add("## 3. 关键指标")
    add("")
    add("| 指标 | 值 | 分子/分母 |")
    add("| --- | --- | --- |")
    add(f"| 可判定覆盖率（全批次） | {_pct(m['coverage_all'])} | {m['counts']['D']}/{m['total']} |")
    add(f"| 可判定覆盖率（真值可判定子集） | {_pct(m['coverage_truth_decidable'])} "
        f"| {m['decided_on_truth_decidable']}/{m['truth_decidable_n']} |")
    if m["published_quotes"] == 0:
        add("| 摘录定位有效率 | 不适用 | 本次没有确定判断，未发布摘录 |")
    else:
        add(f"| 摘录定位有效率 | {_pct(m['locatability'])} "
            f"| {m['located_quotes']}/{m['published_quotes']} |")
    add(f"| 语义标签正确数/总数 | {m['labels_correct']}/{m['total']} | — |")
    add("")

    add("## 4. 逐标签 precision / recall")
    add("")
    add("`precision = TP/(TP+FP)`、`recall = TP/(TP+FN)`；真值为该类但系统**拒判或执行失败**"
        "的样本计入该类 FN，不从分母移除。")
    add("")
    add("| 标签 | 真实样本数 | 预测数 | TP | FP | FN | precision | recall |")
    add("| --- | --- | --- | --- | --- | --- | --- | --- |")
    for label in ALL_LABELS:
        row = m["per_label"][label]
        note = "（单列）" if label == "相矛盾" else ""
        add(f"| {label}{note} | {row['truth_n']} | {row['pred_n']} | {row['tp']} | {row['fp']} "
            f"| {row['fn']} | {_num(row['precision'])} | {_num(row['recall'])} |")
    add("")
    add("相矛盾类的 recall 即「证据冲突识别率」，单独列出。")
    add("")

    add("## 5. macro-F1（真值可判定三类，等权）")
    add("")
    add("`F1 = 2TP/(2TP+FP+FN)`；分母为零的类记 N/A 并从平均中排除，"
        "并报告实际参与平均的类别。")
    add("")
    add("| 类别 | F1 |")
    add("| --- | --- |")
    for label in DEFINITIVE:
        add(f"| {label} | {_num(m['f1_by_label'][label])} |")
    add(f"| **macro-F1** | **{_num(m['macro_f1'])}** |")
    add("")
    add(f"参与平均的类别：{'、'.join(m['macro_f1_labels']) or '无（整体 N/A）'}。")
    add("")

    add("## 6. 应拒判样本上的错误确定判断率")
    add("")
    add("R 为**独立标注**为证据不足的样本集合，不按系统输出倒推。")
    add("")
    add("| 项目 | 值 |")
    add("| --- | --- |")
    add(f"| R 总数 | {m['r_total']} |")
    add(f"| R 中 COMPLETED 数 | {m['r_completed']} |")
    add(f"| R 中输出确定判断数 | {m['r_wrong']} |")
    add(f"| 错误确定判断率（/R 中 COMPLETED） | {_pct(m['r_error_rate'])} |")
    add(f"| 全批次发生率（/R 总数） | {_pct(m['r_error_rate_all'])} |")
    add("")
    add("执行失败不当作正确拒判，也不能只用后一数字证明安全。")
    add("")

    add("## 7. 误判与过度拒判")
    add("")
    add(f"- 误判（真值确定、输出另一确定标签）：{len(m['misjudged'])} 例"
        + (f" — {', '.join(m['misjudged'])}" if m["misjudged"] else ""))
    add(f"- 过度拒判（真值确定、输出证据不足）：{len(m['over_refused'])} 例"
        + (f" — {', '.join(m['over_refused'])}" if m["over_refused"] else ""))
    add("")
    add("不只报告条件准确率；上表两项单独列出。")
    add("")

    add("## 8. 逐例明细")
    add("")
    add("| 样本 | 真值 | 状态 | 输出标签 | 摘录（可定位/已发布） |")
    add("| --- | --- | --- | --- | --- |")
    for o in outcomes:
        add(f"| `{o.case_id}` | {o.expected} | {o.status} | {o.label or '—'} "
            f"| {o.quotes_located}/{o.quotes_total} |")
    add("")

    add("## 9. 未覆盖与不适用")
    add("")
    add("- 来源匹配准确率、证据 Recall@k 需要独立基准与采样协议，本验收集不产出。")
    add(f"- 不确定区间需要采样协议，{m['total']} 个构造样本不估计。")
    add("- 正式研究评测（120 对）不是首版前置条件，本报告不涉及。")
    add("- 语义标签正确性受限于**单人标注、无第二人复核**。")
    add("")
    return "\n".join(lines)


def sample_fingerprint(samples: Path) -> str:
    """A digest of the frozen sample set — the provenance the numbers depend on.

    Sample file *names* are hashed alongside their bytes so that adding,
    removing or renaming a sample always changes the digest.
    """

    digest = hashlib.sha256()
    for path in sorted(samples.glob("*.json")):
        digest.update(path.name.encode("utf-8"))
        digest.update(b"\0")
        digest.update(path.read_bytes())
        digest.update(b"\0")
    return f"sha256:{digest.hexdigest()[:16]}"


def revision(repo: Path) -> str:
    """The commit the report was generated from, for the verification log only.

    Deliberately *not* rendered into the report: the value changes with every
    commit, so a report that embedded it could never pass ``--check``.
    """

    import subprocess

    try:
        done = subprocess.run(
            ["git", "rev-parse", "--short", "HEAD"],
            cwd=repo, capture_output=True, text=True, timeout=15, check=False,
        )
    except (OSError, subprocess.SubprocessError):
        return "unknown"
    return done.stdout.strip() or "unknown"


def generate(cases, work_dir: Path, samples: Path) -> str:
    """The exact bytes that ``docs/semantic-report.md`` must contain."""

    outcomes = collect(cases, work_dir)
    return render(outcomes, sample_fingerprint=sample_fingerprint(samples)) + "\n"


def main() -> int:
    args = sys.argv[1:]
    check_only = "--check" in args
    unknown = [a for a in args if a != "--check"]
    if unknown:
        print(f"未知参数：{' '.join(unknown)}（可用：--check）", file=sys.stderr)
        return 2

    repo = Path(__file__).resolve().parents[2]
    with TemporaryDirectory(prefix="semantic-report-") as work:
        cases = [load_case(case_id) for case_id in available_cases()]
        report = generate(cases, Path(work), SAMPLES)
    target = repo / "docs" / "semantic-report.md"

    if check_only:
        # The CI gate this enables: same samples in, same bytes out.
        current = target.read_text(encoding="utf-8") if target.exists() else ""
        if current == report:
            print(f"{target.relative_to(repo)} 与重新生成的结果逐字节一致（N={len(cases)}）")
            return 0
        print(
            f"{target.relative_to(repo)} 与重新生成的结果不一致；"
            "请运行 `python report.py` 并提交结果",
            file=sys.stderr,
        )
        # Show what actually drifted. A bare "不一致" costs one round trip per
        # occurrence — and the drift is often one line, not a rewrite.
        diff = list(difflib.unified_diff(
            current.splitlines(keepends=True),
            report.splitlines(keepends=True),
            fromfile="已提交的报告",
            tofile="重新生成的结果",
            n=1,
        ))
        for line in diff[:60]:
            sys.stderr.write(line if line.endswith("\n") else line + "\n")
        if len(diff) > 60:
            sys.stderr.write(f"...（另有 {len(diff) - 60} 行差异未显示）\n")
        return 1

    target.write_text(report, encoding="utf-8")
    print(f"已写入 {target.relative_to(repo)}（N={len(cases)}，基线 {revision(repo)}）")
    return 0


if __name__ == "__main__":
    sys.exit(main())
