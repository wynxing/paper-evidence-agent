"""The machine-checkable half of the hand-written claims (Issue #86).

The frozen inventory in ``sources/`` carries identity, licence, paragraph hashes and
short previews; the ``claims`` array is written by hand and reviewed by a second
person (``docs/test-plan.md:46`` / ``:48``). This module is the part of that review a
script can do, and only that part:

* **shape** — the fields #86 asks for are present, and the values use vocabulary the
  repository already uses: ``expected_label`` from :class:`ResultLabel`, ``claim_kind``
  as spelled in ``tests/functional/samples/``. The field names themselves are written
  down once, in ``docs/glossary.md``「claims 字段」, because two independent guesses at
  them had already diverged (#86); this module is the executable copy of that table;
* **location** — a quote must be a contiguous run of the *frozen* paragraph at the
  ordinal it names, compared after the same whitespace normalisation the parser
  applies (``normalize_paragraph_text``);
* **coverage** — labels and variations counted, uncovered cells printed. Coverage is
  a description of the set; ``--require-coverage`` turns it into a pass/fail rule for
  the acceptance gate.
* **review** — the second person's sign-off is shape-checked, not content-checked:
  a missing ``review`` is a warning while the set is being written and an error under
  ``--require-review`` (the acceptance gate). ``review.outcome == "disputed"`` keeps
  the entry in the file but out of the coverage denominator, which is how
  「分歧解决前不计为确定真值」is implemented.

It deliberately does **not** decide whether a label is right. That is the
annotator's judgement and the reviewer's; a script claiming to check it would be
impersonating the second person, which ``#86`` rules out.

Two modes
---------
``--live`` re-fetches each source and compares against the text the product would
actually read. Without it the checker works from the committed inventory, which
stores only a 120-character preview — so a quote that falls inside a *complete*
preview is verified, and one that may land beyond the preview is reported as a
warning ("cannot be checked offline"), never as a pass and never as an error.
An exit status of 0 therefore means "no structural or locational problem", not
"every quote was verified"; only ``--live`` can say the latter.

Usage::

    python tests/functional/claims.py                     # shape + coverage, no network
    python tests/functional/claims.py --live              # also re-fetch and locate quotes
    python tests/functional/claims.py --require-coverage  # coverage gate
    python tests/functional/claims.py --require-review    # second-person sign-off gate
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
from paper_evidence.domain.text import normalize_paragraph_text, paragraph_hash  # noqa: E402

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

#: ``docs/test-plan.md:46`` asks for one claim per variation of the claim. The keys
#: are the tags a claim may carry; the values are only what the coverage table prints.
#:
#: Not called ``dimensions``: ``tests/functional/samples/*.json`` already has a
#: ``dimension`` key meaning the *test* dimension (``功能准确性``), not the aspect of
#: the claim that was varied. Two plurals of the same word with different meanings is
#: exactly the confusion this name exists to avoid (#86).
VARIATIONS = {
    "object": "对象",
    "quantity": "数量",
    "condition": "条件",
    "causality": "因果关系",
    "negation": "否定方向",
}

#: The vocabulary ``tests/functional/samples/*.json`` already uses. Reused rather
#: than invented: a constructed variant must be marked as such (#86), and a natural
#: claim must not be mistaken for one. ``paraphrase`` is not a third kind: a rewritten
#: sentence is still a constructed input, and ``claim_note`` says what was rewritten.
CLAIM_KINDS = {"natural", "constructed"}

#: ``review.outcome``: agreed, disagreed, or left open. ``disputed`` entries stay in
#: the file and out of the coverage denominator (test-plan:48「分歧解决前不计为确定真值」).
REVIEW_OUTCOMES = {"agree", "disagree", "disputed"}

DEADLINE_SECONDS = 120.0

#: Marks a warning that means "offline, this quote was neither confirmed nor
#: condemned". Warnings are plain strings like everything else here, so the count
#: that the summary line prints is derived from this phrase; it is a constant so
#: the producing and the counting side cannot drift apart.
OFFLINE_UNCHECKED = "离线无法判定"


def entry_claims(entry: dict) -> list | None:
    """The ``claims`` array of one inventory entry, or ``None`` when it is malformed."""

    claims = entry.get("claims")
    return claims if isinstance(claims, list) else None


def _is_ordinal(value) -> bool:
    # ``bool`` is an ``int`` in Python; ``True`` must not pass as ordinal 1.
    return isinstance(value, int) and not isinstance(value, bool)


def check_shape(entry: dict, *, require_review: bool = False) -> tuple[list[str], list[str]]:
    """Validate one entry's claims without touching the article text.

    Returns ``(errors, warnings)``. Errors mean the claim cannot be used as a
    reviewed truth value; warnings mean a human should look, but the record is
    still well-formed.

    ``require_review`` upgrades a missing ``review`` from warning to error. It is
    off while the answer key is being written (nobody can review an unwritten
    claim) and on at the acceptance gate, where an unsigned entry must not count.
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
        errors.extend(_check_variations(where, claim.get("variations")))
        for key in ("claim_note", "rationale", "limits"):
            value = claim.get(key)
            if value is not None and not isinstance(value, str):
                errors.append(f"{where}: {key} 必须是字符串")
        if claim.get("claim_kind") != "natural" and not str(claim.get("claim_note") or "").strip():
            # Not an error: the claim can still be judged. But a constructed input
            # that does not say what it changed invites the reviewer to read it as a
            # natural quotation, which is the one thing `claim_kind` exists to prevent.
            warnings.append(
                f"{where}: 非 natural 的 claim 没有 claim_note，复核时看不出改了什么"
            )
        review_errors, review_warnings = _check_review(
            where, claim.get("review"), required=require_review
        )
        errors.extend(review_errors)
        warnings.extend(review_warnings)
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
    "claim_note",
    "expected_label",
    "evidence",
    "variations",
    "rationale",
    "limits",
    "review",
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


def _check_variations(where: str, variations) -> list[str]:
    """``variations`` is optional, but a tag that is not in the vocabulary is a typo."""

    if variations is None:
        return []
    if not isinstance(variations, list):
        return [f"{where}: variations 必须是数组"]
    problems: list[str] = []
    seen: set[str] = set()
    for item in variations:
        if item not in VARIATIONS:
            problems.append(f"{where}: variations 里的 {item!r} 不在 {list(VARIATIONS)} 内")
        elif item in seen:
            problems.append(f"{where}: variations 重复了 {item!r}")
        else:
            seen.add(item)
    return problems


def _check_review(where: str, review, *, required: bool) -> tuple[list[str], list[str]]:
    """Shape of the second person's sign-off, never its substance.

    A missing ``review`` is only a warning unless ``required``: while the answer key
    is being written, every entry is by definition unreviewed, and failing the whole
    file for that would make the checker useless during authoring. A ``review`` that
    exists but is malformed is always an error — "someone signed" and "someone
    signed with an outcome nobody can act on" are different states.
    """

    if review is None:
        if required:
            return [f"{where}: 缺 review——验收门禁要求第二人已签核"], []
        return [], [f"{where}: 尚未复核（缺 review），不计入真值分母"]
    if not isinstance(review, dict):
        return [f"{where}: review 必须是对象，当前是 {type(review).__name__}"], []

    problems: list[str] = []
    for key in ("by", "at"):
        value = review.get(key)
        if not isinstance(value, str) or not value.strip():
            problems.append(f"{where}: review.{key} 必须是非空字符串")
    outcome = review.get("outcome")
    if outcome not in REVIEW_OUTCOMES:
        problems.append(
            f"{where}: review.outcome 必须是 {sorted(REVIEW_OUTCOMES)} 之一，当前 {outcome!r}"
        )
    note = review.get("note")
    if note is not None and (not isinstance(note, str) or not note.strip()):
        problems.append(f"{where}: review.note 给了就必须是非空字符串")
    for key in review:
        if key not in {"by", "at", "outcome", "note"}:
            problems.append(f"{where}: review 里的 {key!r} 不是本校验器认识的字段")
    return problems, []


def check_quotes(
    entry: dict, paragraphs: dict[int, str] | None = None
) -> tuple[list[str], list[str]]:
    """Locate every quote, against the live text when given, else against the inventory.

    ``paragraphs`` maps ``ordinal`` to the *normalised* paragraph text the parser
    produced from a fresh fetch. With ``None`` the check falls back to the committed
    inventory, where only a 120-character preview survives — enough to verify a quote
    inside a complete preview, never enough to declare one wrong just because it
    lands past the cut. Those come back as warnings, not as an empty list: a run
    that skipped a quote must not read as a run that checked it.

    Returns ``(problems, warnings)``, like :func:`check_shape`.
    """

    case_id = entry.get("case_id", "<未命名来源>")
    claims = entry_claims(entry) or []
    by_ordinal = {item["ordinal"]: item for item in entry.get("paragraphs", [])}
    problems: list[str] = []
    warnings: list[str] = []

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
            found, unsure = _locate_offline(where, ordinal, frozen, stored)
            problems.extend(found)
            warnings.extend(unsure)
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

    return problems, warnings


def _locate_offline(
    where: str, ordinal: int, quote: str, stored: dict
) -> tuple[list[str], list[str]]:
    """What can be concluded from a preview, and nothing more.

    Three outcomes, kept apart on purpose: a miss inside a complete preview is a
    definite error; a hit is a definite pass; anything the cut could have hidden is
    an explicit "unchecked", because the one result this must never produce is a
    silent pass.
    """

    preview = stored.get("preview") or ""
    length = stored.get("text_length")
    if isinstance(length, int) and len(quote) > length:
        return [
            f"{where}: 引文（{len(quote)} 字）比 ordinal {ordinal} 整段（{length} 字）还长"
        ], []
    if isinstance(length, int) and length <= PREVIEW_CHARS:
        # The whole paragraph is inside the preview: this is a complete check.
        if quote not in preview:
            return [f"{where}: 引文不能在 ordinal {ordinal} 里逐字定位（清单存了整段预览）"], []
        return [], []
    if quote in preview:
        return [], []
    # The quote may straddle the character cut (or the inventory does not record a
    # length at all); only --live can tell, so say so instead of passing.
    size = f"整段 {length} 字" if isinstance(length, int) else "整段长度未记录"
    return [], [
        f"{where}: 引文不在清单的 {PREVIEW_CHARS} 字预览内（{size}），"
        f"{OFFLINE_UNCHECKED}，用 --live 才能核对"
    ]


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
    """Count labels and variations over the set, per source and in total.

    ``disputed`` entries are counted in ``total`` but not in the label or variation
    tallies: they stay in the file, and they do not enter the truth denominator
    until the two annotators agree.
    """

    report = {
        "total": 0,
        "constructed": 0,
        "reviewed": 0,
        "disputed": 0,
        "labels": {label: 0 for label in JUDGEMENT_LABELS},
        "variations": {tag: 0 for tag in VARIATIONS},
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
            review = claim.get("review")
            if isinstance(review, dict) and isinstance(review.get("by"), str) and review["by"].strip():
                report["reviewed"] += 1
            if isinstance(review, dict) and review.get("outcome") == "disputed":
                report["disputed"] += 1
                continue
            label = claim.get("expected_label")
            if label in row:
                row[label] += 1
                report["labels"][label] += 1
            if claim.get("claim_kind") == "constructed":
                report["constructed"] += 1
            tags = claim.get("variations") or []
            if not tags:
                report["untagged"] += 1
            for tag in tags:
                if tag in report["variations"]:
                    report["variations"][tag] += 1
        report["per_source"][case_id] = row
    return report


def render_coverage(entries: list[dict]) -> str:
    """A table a reviewer can read, including what is *not* covered."""

    report = coverage(entries)
    counted = report["total"] - report["disputed"]
    lines = [
        f"覆盖：{len(entries)} 个来源，{report['total']} 条 claims"
        f"（其中构造输入 {report['constructed']} 条，未标变体 {report['untagged']} 条，"
        f"已复核 {report['reviewed']} 条，disputed {report['disputed']} 条）",
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
        + f" | {counted} |"
    )
    lines.append("")
    lines.append("| 变体 | " + " | ".join(VARIATIONS.values()) + " |")
    lines.append("| --- | " + " | ".join("---" for _ in VARIATIONS) + " |")
    lines.append(
        "| 条数 | "
        + " | ".join(str(report["variations"][tag]) for tag in VARIATIONS)
        + " |"
    )

    missing_labels = [label for label in JUDGEMENT_LABELS if not report["labels"][label]]
    missing_vars = [VARIATIONS[tag] for tag in VARIATIONS if not report["variations"][tag]]
    lines.append("")
    if report["total"] == 0:
        lines.append(
            "**claims 全为空**：这是 #86 的现状，不是通过。真实的来源侧已冻结，人的那一半还没写。"
        )
    else:
        if report["disputed"]:
            lines.append(
                f"disputed {report['disputed']} 条留在清单里，但**不计入覆盖与真值分母**"
                "（分歧解决前不计为确定真值）。"
            )
        lines.append(
            "未覆盖的标签：" + ("无" if not missing_labels else "、".join(missing_labels))
        )
        lines.append(
            "未覆盖的变体：" + ("无" if not missing_vars else "、".join(missing_vars))
        )
        if missing_labels or missing_vars:
            lines.append("（#86 / `test-plan.md:46` 要求四类标签、五个变体各至少一例）")
    return "\n".join(lines)


def coverage_gaps(entries: list[dict]) -> list[str]:
    """The cells ``--require-coverage`` refuses to accept, in words."""

    report = coverage(entries)
    gaps = [f"标签「{label}」0 条" for label in JUDGEMENT_LABELS if not report["labels"][label]]
    gaps += [
        f"变体「{VARIATIONS[tag]}」0 条"
        for tag in VARIATIONS
        if not report["variations"][tag]
    ]
    return gaps


def review_gaps(entries: list[dict]) -> list[str]:
    """Entries the acceptance gate must not count: unsigned or left disputed."""

    gaps: list[str] = []
    for entry in entries:
        case_id = entry.get("case_id", "<未命名来源>")
        for index, claim in enumerate(entry_claims(entry) or [], 1):
            if not isinstance(claim, dict):
                continue
            review = claim.get("review")
            if not isinstance(review, dict) or not str(review.get("by") or "").strip():
                gaps.append(f"{case_id} 第 {index} 条未复核")
            elif review.get("outcome") == "disputed":
                gaps.append(f"{case_id} 第 {index} 条仍 disputed")
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


def check_entry(
    entry: dict, paragraphs: dict[int, str] | None = None, *, require_review: bool = False
):
    """Everything the checker can say about one source: (errors, warnings)."""

    errors, warnings = check_shape(entry, require_review=require_review)
    quote_errors, quote_warnings = check_quotes(entry, paragraphs)
    errors.extend(quote_errors)
    warnings.extend(quote_warnings)

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
            if paragraph_hash(text) != stored["paragraph_hash"]:
                errors.append(
                    f"{entry.get('case_id')}: ordinal {ordinal} 的正文哈希与清单不一致"
                    "（正文漂移）；旧 claims 针对的是旧正文，先重新核对"
                )
        # The live text may also have *lost* a paragraph. Comparing only the live
        # ordinals would stay quiet about it unless some claim happened to cite it.
        for ordinal in by_ordinal:
            if ordinal not in paragraphs:
                errors.append(
                    f"{entry.get('case_id')}: 清单里有 ordinal {ordinal}，线上没有"
                    "（正文少了这一段）；引用它的 claim 指向了已不存在的段落，先重新核对"
                )
    return errors, warnings


def _status(errors: list[str], warnings: list[str]) -> str:
    """The word in the brackets of the per-source line.

    "通过" alone must mean every quote was actually checked. Offline that is often
    not true, so the count of unchecked quotes is printed in the same line rather
    than left to a footnote the reader may skip.
    """

    if errors:
        return f"{len(errors)} 处问题"
    unchecked = _offline_unchecked(warnings)
    return f"通过（含 {unchecked} 条{OFFLINE_UNCHECKED}）" if unchecked else "通过"


def _offline_unchecked(warnings: list[str]) -> int:
    return sum(OFFLINE_UNCHECKED in line for line in warnings)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="校验 #86 的人工 claims：形状、引文定位、覆盖")
    parser.add_argument(
        "--sources",
        "--out",
        dest="sources",
        type=Path,
        default=SOURCES,
        help="清单目录（--out 是旧名，与 freeze_sources.py 的写法保持一致）",
    )
    parser.add_argument("--source", action="append", default=[], help="只校验指定 case_id，可重复")
    parser.add_argument("--live", action="store_true", help="重新取回来源，逐段验证引文")
    parser.add_argument(
        "--require-coverage",
        action="store_true",
        help="四类标签与五个变体任一为 0 即失败（验收门禁用，撰写期不要开）",
    )
    parser.add_argument(
        "--require-review",
        action="store_true",
        help="缺 review 或仍为 disputed 即失败（验收门禁用，撰写期不要开）",
    )
    return parser


def main() -> int:
    args = build_parser().parse_args()

    entries = load_all(args.sources)
    if not entries:
        print(f"{args.sources} 下没有清单", file=sys.stderr)
        return 2
    if args.source:
        wanted = set(args.source)
        entries = [entry for entry in entries if entry.get("case_id") in wanted]
        missing = wanted - {entry.get("case_id") for entry in entries}
        if missing:
            print(f"清单里没有：{'、'.join(sorted(missing))}", file=sys.stderr)
            return 2

    failed = 0
    unchecked_total = 0
    # A TemporaryDirectory, not mkdtemp: the fetch leaves a database behind per
    # source, and nothing outside this function reads it.
    with tempfile.TemporaryDirectory(prefix="claims-check-") as work:
        for entry in entries:
            paragraphs = None
            if args.live:
                try:
                    paragraphs = _fetch_paragraphs(
                        entry["provenance"]["doi"], Path(work)
                    )
                except Exception as error:  # noqa: BLE001 - a fetch failure is a result too
                    print(f"[取回失败] {entry.get('case_id')}: {type(error).__name__}: {error}",
                          file=sys.stderr)
                    failed += 1
                    continue
            errors, warnings = check_entry(
                entry, paragraphs, require_review=args.require_review
            )
            count = len(entry_claims(entry) or [])
            unchecked_total += _offline_unchecked(warnings)
            print(f"[{_status(errors, warnings)}] {entry.get('case_id')}（{count} 条 claims）")
            for line in errors:
                print(f"    ✗ {line}")
            for line in warnings:
                print(f"    ! {line}")
            if errors:
                failed += 1

    print()
    print(render_coverage(entries))

    if unchecked_total:
        print(
            f"\n注意：{unchecked_total} 条引文落在清单预览之外，离线模式下{OFFLINE_UNCHECKED}；"
            "这些条目要跑 --live 才算核对过，不能用离线绿灯当验收依据。"
        )

    gaps = coverage_gaps(entries) if args.require_coverage else []
    if args.require_review:
        gaps += review_gaps(entries)
    if gaps:
        print("\n覆盖或复核不达门禁：" + "、".join(gaps), file=sys.stderr)

    if failed:
        print(f"\n{failed}/{len(entries)} 个来源有结构或定位问题", file=sys.stderr)
        return 1
    if gaps:
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
