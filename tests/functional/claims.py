"""The machine-checkable half of the hand-written claims (Issue #86).

The frozen inventory in ``sources/`` carries identity, licence, paragraph hashes and
short previews; the ``claims`` array is written by hand and reviewed by a second
person (``docs/test-plan.md:46`` / ``:48``). This module is the part of that review a
script can do, and only that part:

* **shape** — the fields #86 asks for are present, and the values use vocabulary the
  repository already uses: ``expected_label`` from :class:`ResultLabel`, ``claim_kind``
  as spelled in ``tests/functional/samples/``;
* **location** — a quote must be a contiguous run of the *frozen* paragraph at the
  ordinal it names, compared after the same whitespace normalisation the parser
  applies (``normalize_paragraph_text``);
* **coverage** — labels and dimensions counted, uncovered cells printed. Coverage is
  a description of the set; ``--require-coverage`` turns it into a pass/fail rule for
  the acceptance gate.

It deliberately does **not** decide whether a label is right. That is the
annotator's judgement and the reviewer's; a script claiming to check it would be
impersonating the second person, which ``#86`` rules out.

Two modes
---------
``--live`` re-fetches each source and compares against the text the product would
actually read. Without it the checker works from the committed inventory, which
stores only a 120-character preview — so a quote that falls inside a *complete*
preview is verified, and one that would land beyond the preview is reported as
"cannot be checked offline" rather than silently passed.

Usage::

    python tests/functional/claims.py                     # shape + coverage, no network
    python tests/functional/claims.py --live              # also re-fetch and locate quotes
    python tests/functional/claims.py --require-coverage  # acceptance gate
    python tests/functional/claims.py --source PMC7461750
"""

import argparse
import asyncio
import json
import sys
import tempfile
import time
from dataclasses import replace
from pathlib import Path

# ``backend/.venv`` is editable-installed against one checkout; put this worktree's
# backend first so the checker describes the code it ships with (same reason as
# ``freeze_sources.py``).
REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO / "backend"))

from freeze_sources import PREVIEW_CHARS, SOURCES, load_all  # noqa: E402
from paper_evidence.domain import ResultLabel  # noqa: E402
from paper_evidence.domain.text import normalize_paragraph_text  # noqa: E402

#: The four labels a claim may carry, in the order reports print them.
#:
#: ``无法核验来源`` is a task outcome, not a judgement about the paper: a claim whose
#: expected label is "the source could not be verified" describes a fetch failure,
#: which belongs in an issue about the connector, not in the hand-checked answer key.
JUDGEMENT_LABELS = (
    ResultLabel.SUPPORTED.value,
    ResultLabel.PARTIALLY_SUPPORTED.value,
    ResultLabel.CONTRADICTED.value,
    ResultLabel.INSUFFICIENT_EVIDENCE.value,
)

#: ``docs/test-plan.md:46`` asks for one claim per dimension. The keys are the tags a
#: claim may carry; the values are only what the coverage table prints.
DIMENSIONS = {
    "object": "对象",
    "quantity": "数量",
    "condition": "条件",
    "causality": "因果关系",
    "negation": "否定方向",
}

#: The vocabulary ``tests/functional/samples/*.json`` already uses. Reused rather
#: than invented: a constructed variant must be marked as such (#86), and a natural
#: claim must not be mistaken for one.
CLAIM_KINDS = {"natural", "constructed"}

DEADLINE_SECONDS = 120.0


def entry_claims(entry: dict) -> list | None:
    """The ``claims`` array of one inventory entry, or ``None`` when it is malformed."""

    claims = entry.get("claims")
    return claims if isinstance(claims, list) else None


def _is_ordinal(value) -> bool:
    # ``bool`` is an ``int`` in Python; ``True`` must not pass as ordinal 1.
    return isinstance(value, int) and not isinstance(value, bool)


def check_shape(entry: dict) -> tuple[list[str], list[str]]:
    """Validate one entry's claims without touching the article text.

    Returns ``(errors, warnings)``. Errors mean the claim cannot be used as a
    reviewed truth value; warnings mean a human should look, but the record is
    still well-formed.
    """

    case_id = entry.get("case_id", "<未命名来源>")
    claims = entry_claims(entry)
    if claims is None:
        return [f"{case_id}: claims 必须是数组（当前是 {type(entry.get('claims')).__name__}）"], []

    errors: list[str] = []
    warnings: list[str] = []
    seen_ids: dict[str, int] = {}

    for index, claim in enumerate(claims, 1):
        where = f"{case_id} 第 {index} 条"
        if not isinstance(claim, dict):
            errors.append(f"{where}: 必须是对象，当前是 {type(claim).__name__}")
            continue

        text = claim.get("claim")
        if not isinstance(text, str) or not text.strip():
            errors.append(f"{where}: claim 必须是非空字符串")
        else:
            where = f"{case_id} 第 {index} 条（{_short(text)}）"

        claim_id = claim.get("claim_id")
        if claim_id is not None:
            if not isinstance(claim_id, str) or not claim_id.strip():
                errors.append(f"{where}: claim_id 给了就必须是非空字符串")
            elif claim_id in seen_ids:
                errors.append(
                    f"{where}: claim_id {claim_id!r} 与第 {seen_ids[claim_id]} 条重复；"
                    "引用一条 claim 时要能指到唯一一条"
                )
            else:
                seen_ids[claim_id] = index

        kind = claim.get("claim_kind")
        if kind is None:
            errors.append(
                f"{where}: 缺 claim_kind（natural / constructed）。#86 要求构造变体标明是构造输入，"
                "不标明就无法把它和自然引文分开"
            )
        elif kind not in CLAIM_KINDS:
            errors.append(f"{where}: claim_kind {kind!r} 不在 {sorted(CLAIM_KINDS)} 内")

        label = claim.get("expected_label")
        if label is None:
            errors.append(f"{where}: 缺 expected_label")
        elif label not in JUDGEMENT_LABELS:
            hint = ""
            if label == ResultLabel.SOURCE_UNVERIFIABLE.value:
                hint = "；「无法核验来源」是任务终态，不是对论文的判断"
            errors.append(
                f"{where}: expected_label {label!r} 不是四类标签之一 "
                f"{list(JUDGEMENT_LABELS)}{hint}"
            )

        errors.extend(_check_evidence(where, label, claim.get("evidence")))
        errors.extend(_check_dimensions(where, claim.get("dimensions")))
        for key in claim:
            if key not in _KNOWN_KEYS:
                warnings.append(f"{where}: 未识别字段 {key!r}，不参与校验")

        if label == ResultLabel.INSUFFICIENT_EVIDENCE.value and claim.get("evidence"):
            # Allowed, but it is the boundary that gets mislabelled most often: a
            # fragment that *cannot* support the claim is not the same as a source
            # where no checkable fragment exists.
            warnings.append(
                f"{where}: 「证据不足」条目附了引文。确认它表达的是「找到了片段但不支持」，"
                "那种情况按术语表属部分支持或相矛盾；证据不足指没有可核查片段"
            )

    return errors, warnings


_KNOWN_KEYS = {
    "claim_id",
    "claim",
    "claim_kind",
    "expected_label",
    "evidence",
    "dimensions",
    "note",
}


def _check_evidence(where: str, label, evidence) -> list[str]:
    """Shape rules for ``evidence``; whether the quote locates is checked separately."""

    problems: list[str] = []
    if evidence in (None, {}):
        if label != ResultLabel.INSUFFICIENT_EVIDENCE.value:
            problems.append(
                f"{where}: 除「证据不足」外，每条 claim 都要给 evidence"
                "（ordinal + quote），否则标签没有可复查的出处"
            )
        return problems
    if not isinstance(evidence, dict):
        return [f"{where}: evidence 必须是对象或 null，当前是 {type(evidence).__name__}"]

    ordinal = evidence.get("ordinal")
    if not _is_ordinal(ordinal) or ordinal < 1:
        problems.append(f"{where}: evidence.ordinal 必须是从 1 开始的整数")
    quote = evidence.get("quote")
    if not isinstance(quote, str) or not quote.strip():
        problems.append(f"{where}: evidence.quote 必须是非空字符串")
    for key in evidence:
        if key not in {"ordinal", "quote"}:
            problems.append(f"{where}: evidence 里的 {key!r} 不是本校验器认识的字段")
    return problems


def _check_dimensions(where: str, dimensions) -> list[str]:
    """``dimensions`` is optional, but a tag that is not in the vocabulary is a typo."""

    if dimensions is None:
        return []
    if not isinstance(dimensions, list):
        return [f"{where}: dimensions 必须是数组"]
    problems: list[str] = []
    seen: set[str] = set()
    for item in dimensions:
        if item not in DIMENSIONS:
            problems.append(f"{where}: dimensions 里的 {item!r} 不在 {list(DIMENSIONS)} 内")
        elif item in seen:
            problems.append(f"{where}: dimensions 重复了 {item!r}")
        else:
            seen.add(item)
    return problems


def check_quotes(entry: dict, paragraphs: dict[int, str] | None = None) -> list[str]:
    """Locate every quote, against the live text when given, else against the inventory.

    ``paragraphs`` maps ``ordinal`` to the *normalised* paragraph text the parser
    produced from a fresh fetch. With ``None`` the check falls back to the committed
    inventory, where only a 120-character preview survives — enough to verify a quote
    inside a complete preview, never enough to declare one wrong just because it
    lands past the cut.
    """

    case_id = entry.get("case_id", "<未命名来源>")
    claims = entry_claims(entry) or []
    by_ordinal = {item["ordinal"]: item for item in entry.get("paragraphs", [])}
    problems: list[str] = []

    for index, claim in enumerate(claims, 1):
        if not isinstance(claim, dict):
            continue
        evidence = claim.get("evidence")
        if not isinstance(evidence, dict):
            continue
        ordinal = evidence.get("ordinal")
        quote = evidence.get("quote")
        if not _is_ordinal(ordinal) or not isinstance(quote, str) or not quote.strip():
            continue  # already reported by check_shape
        where = f"{case_id} 第 {index} 条（{_short(claim.get('claim') or '')}）"
        frozen = normalize_paragraph_text(quote)

        stored = by_ordinal.get(ordinal)
        if stored is None:
            problems.append(
                f"{where}: 清单里没有 ordinal {ordinal}（该来源共 "
                f"{len(by_ordinal)} 段，序号从 1 开始）"
            )
            continue

        if paragraphs is None:
            problems.extend(_locate_offline(where, ordinal, frozen, stored))
            continue

        text = paragraphs.get(ordinal)
        if text is None:
            problems.append(f"{where}: 线上取回没有 ordinal {ordinal}，正文与清单不一致")
            continue
        if len(frozen) > len(text):
            problems.append(
                f"{where}: 引文（{len(frozen)} 字）比 ordinal {ordinal} 整段（{len(text)} 字）还长"
            )
            continue
        if frozen not in text:
            found = _locatable_prefix(text, frozen)
            problems.append(
                f"{where}: 引文不能在 ordinal {ordinal} 里逐字定位"
                f"（最长可定位前缀 {found}/{len(frozen)} 字；改写过的句子不算定位）"
            )

    return problems


def _locate_offline(where: str, ordinal: int, quote: str, stored: dict) -> list[str]:
    """What can be concluded from a preview, and nothing more."""

    preview = stored.get("preview") or ""
    length = stored.get("text_length")
    if isinstance(length, int) and len(quote) > length:
        return [
            f"{where}: 引文（{len(quote)} 字）比 ordinal {ordinal} 整段（{length} 字）还长"
        ]
    if isinstance(length, int) and length <= PREVIEW_CHARS:
        # The whole paragraph is inside the preview: this is a complete check.
        if quote not in preview:
            return [f"{where}: 引文不能在 ordinal {ordinal} 里逐字定位（清单存了整段预览）"]
        return []
    if quote in preview:
        return []
    # The quote may straddle the 120-character cut; only --live can tell.
    return []


def _locatable_prefix(text: str, quote: str) -> int:
    """Length of the longest prefix of ``quote`` that occurs in ``text``.

    A paraphrase usually shares a word or two with the original, and printing how far
    it matched is the difference between "your quote is wrong" and "where it went
    wrong". Paragraphs are short and this only runs on failure.
    """

    for size in range(len(quote), 0, -1):
        if quote[:size] in text:
            return size
    return 0


def _short(text: str, limit: int = 24) -> str:
    collapsed = normalize_paragraph_text(text)
    return collapsed if len(collapsed) <= limit else collapsed[:limit] + "…"


def coverage(entries: list[dict]) -> dict:
    """Count labels and dimensions over the set, per source and in total."""

    report = {
        "total": 0,
        "constructed": 0,
        "labels": {label: 0 for label in JUDGEMENT_LABELS},
        "dimensions": {dim: 0 for dim in DIMENSIONS},
        "untagged": 0,
        "per_source": {},
    }
    for entry in entries:
        case_id = entry.get("case_id", "<未命名来源>")
        claims = entry_claims(entry) or []
        row = {label: 0 for label in JUDGEMENT_LABELS}
        for claim in claims:
            if not isinstance(claim, dict):
                continue
            report["total"] += 1
            label = claim.get("expected_label")
            if label in row:
                row[label] += 1
                report["labels"][label] += 1
            if claim.get("claim_kind") == "constructed":
                report["constructed"] += 1
            tags = claim.get("dimensions") or []
            if not tags:
                report["untagged"] += 1
            for tag in tags:
                if tag in report["dimensions"]:
                    report["dimensions"][tag] += 1
        report["per_source"][case_id] = row
    return report


def render_coverage(entries: list[dict]) -> str:
    """A table a reviewer can read, including what is *not* covered."""

    report = coverage(entries)
    lines = [
        f"覆盖：{len(entries)} 个来源，{report['total']} 条 claims"
        f"（其中构造输入 {report['constructed']} 条，未标维度 {report['untagged']} 条）",
        "",
        "| 来源 | " + " | ".join(JUDGEMENT_LABELS) + " | 合计 |",
        "| --- | " + " | ".join("---" for _ in JUDGEMENT_LABELS) + " | --- |",
    ]
    for case_id, row in report["per_source"].items():
        lines.append(
            f"| {case_id} | " + " | ".join(str(row[label]) for label in JUDGEMENT_LABELS)
            + f" | {sum(row.values())} |"
        )
    lines.append(
        "| **合计** | "
        + " | ".join(str(report["labels"][label]) for label in JUDGEMENT_LABELS)
        + f" | {report['total']} |"
    )
    lines.append("")
    lines.append("| 维度 | " + " | ".join(DIMENSIONS.values()) + " |")
    lines.append("| --- | " + " | ".join("---" for _ in DIMENSIONS) + " |")
    lines.append(
        "| 条数 | "
        + " | ".join(str(report["dimensions"][tag]) for tag in DIMENSIONS)
        + " |"
    )

    missing_labels = [label for label in JUDGEMENT_LABELS if not report["labels"][label]]
    missing_dims = [DIMENSIONS[tag] for tag in DIMENSIONS if not report["dimensions"][tag]]
    lines.append("")
    if report["total"] == 0:
        lines.append(
            "**claims 全为空**：这是 #86 的现状，不是通过。真实的来源侧已冻结，人的那一半还没写。"
        )
    else:
        lines.append(
            "未覆盖的标签：" + ("无" if not missing_labels else "、".join(missing_labels))
        )
        lines.append(
            "未覆盖的维度：" + ("无" if not missing_dims else "、".join(missing_dims))
        )
        if missing_labels or missing_dims:
            lines.append("（#86 / `test-plan.md:46` 要求四类标签、五个维度各至少一例）")
    return "\n".join(lines)


def coverage_gaps(entries: list[dict]) -> list[str]:
    """The cells ``--require-coverage`` refuses to accept, in words."""

    report = coverage(entries)
    gaps = [f"标签「{label}」0 条" for label in JUDGEMENT_LABELS if not report["labels"][label]]
    gaps += [
        f"维度「{DIMENSIONS[tag]}」0 条"
        for tag in DIMENSIONS
        if not report["dimensions"][tag]
    ]
    return gaps


def _fetch_paragraphs(doi: str, work: Path) -> dict[int, str]:
    """The normalised text of every paragraph, from a fresh fetch.

    Uses the real connector and the real parser instead of re-deriving text from the
    raw JATS: the normalisation rule is what "locatable" means here, and a second
    implementation of it would drift from the first.
    """

    from paper_evidence.api.deps import Services
    from paper_evidence.config import Settings
    from paper_evidence.retrieval.jats import parse_jats

    async def run():
        services = Services(replace(Settings.from_env(), data_dir=work, contact_email=""))
        try:
            snapshot = await services.source_service().fetch(
                doi, time.monotonic() + DEADLINE_SECONDS
            )
        finally:
            services.close()
        return snapshot

    snapshot = asyncio.run(run())
    return {item.ordinal: item.text for item in parse_jats(snapshot)}


def check_entry(entry: dict, paragraphs: dict[int, str] | None = None):
    """Everything the checker can say about one source: (errors, warnings)."""

    errors, warnings = check_shape(entry)
    errors.extend(check_quotes(entry, paragraphs))

    if paragraphs is not None:
        by_ordinal = {item["ordinal"]: item for item in entry.get("paragraphs", [])}
        for ordinal, text in paragraphs.items():
            stored = by_ordinal.get(ordinal)
            if stored is None:
                errors.append(
                    f"{entry.get('case_id')}: 线上多出 ordinal {ordinal}，"
                    "先跑 freeze_sources.py --check 重新冻结"
                )
                continue
            from paper_evidence.domain.text import paragraph_hash

            if paragraph_hash(text) != stored["paragraph_hash"]:
                errors.append(
                    f"{entry.get('case_id')}: ordinal {ordinal} 的正文哈希与清单不一致"
                    "（正文漂移）；旧 claims 针对的是旧正文，先重新核对"
                )
    return errors, warnings


def main() -> int:
    parser = argparse.ArgumentParser(description="校验 #86 的人工 claims：形状、引文定位、覆盖")
    parser.add_argument("--out", type=Path, default=SOURCES)
    parser.add_argument("--source", action="append", default=[], help="只校验指定 case_id，可重复")
    parser.add_argument("--live", action="store_true", help="重新取回来源，逐段验证引文")
    parser.add_argument(
        "--require-coverage",
        action="store_true",
        help="四类标签与五个维度任一为 0 即失败（验收门禁用，撰写期不要开）",
    )
    args = parser.parse_args()

    entries = load_all(args.out)
    if not entries:
        print(f"{args.out} 下没有清单", file=sys.stderr)
        return 2
    if args.source:
        wanted = set(args.source)
        entries = [entry for entry in entries if entry.get("case_id") in wanted]
        missing = wanted - {entry.get("case_id") for entry in entries}
        if missing:
            print(f"清单里没有：{'、'.join(sorted(missing))}", file=sys.stderr)
            return 2

    work = Path(tempfile.mkdtemp(prefix="claims-check-"))
    failed = 0
    for entry in entries:
        paragraphs = None
        if args.live:
            try:
                paragraphs = _fetch_paragraphs(entry["provenance"]["doi"], work)
            except Exception as error:  # noqa: BLE001 - a fetch failure is a result too
                print(f"[取回失败] {entry.get('case_id')}: {type(error).__name__}: {error}",
                      file=sys.stderr)
                failed += 1
                continue
        errors, warnings = check_entry(entry, paragraphs)
        count = len(entry_claims(entry) or [])
        status = "通过" if not errors else f"{len(errors)} 处问题"
        print(f"[{status}] {entry.get('case_id')}（{count} 条 claims）")
        for line in errors:
            print(f"    ✗ {line}")
        for line in warnings:
            print(f"    ! {line}")
        if errors:
            failed += 1

    print()
    print(render_coverage(entries))

    gaps = coverage_gaps(entries) if args.require_coverage else []
    if gaps:
        print("\n覆盖不达门禁：" + "、".join(gaps), file=sys.stderr)

    if failed:
        print(f"\n{failed}/{len(entries)} 个来源有结构或定位问题", file=sys.stderr)
        return 1
    if gaps:
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
