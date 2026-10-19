"""The checker behind #86 must catch malformed claims before a human review does.

Every case here is a claim someone could plausibly write: a paraphrase passed off as
a quote, a label outside the four, an ordinal that does not exist, a duplicate id. The
checker is only worth running if each of those turns red, so each test pins one.
"""

from pathlib import Path

import pytest

from claims import (
    JUDGEMENT_LABELS,
    OFFLINE_UNCHECKED,
    SOURCES,
    _status,
    build_parser,
    check_entry,
    check_quotes,
    check_shape,
    coverage,
    coverage_gaps,
    load_all,
    render_coverage,
)
from paper_evidence.domain.text import paragraph_hash

TEXT = "The treatment reduced mortality by 20 percent in the adult cohort."


def quotes(item, paragraphs=None) -> list[str]:
    """The errors only: most cases ask whether a quote was condemned, not why not."""

    problems, _ = check_quotes(item, paragraphs)
    return problems


def entry(claims, *, paragraphs=None, case_id="PMC_TEST") -> dict:
    """A minimal inventory entry; only the fields the checker reads."""

    if paragraphs is None:
        paragraphs = [
            {
                "ordinal": 1,
                "section": "body",
                "paragraph_hash": paragraph_hash(TEXT),
                "text_length": len(TEXT),
                "native_jats_id": "p1",
                "preview": TEXT,
            }
        ]
    return {"schema": 2, "case_id": case_id, "paragraphs": paragraphs, "claims": claims}


def claim(**overrides) -> dict:
    payload = {
        "claim_id": "c1",
        "claim": "该治疗把成人队列的死亡率降低了约 20%。",
        "claim_kind": "natural",
        "expected_label": "支持",
        "evidence": {"ordinal": 1, "quote": "reduced mortality by 20 percent"},
        "dimensions": ["quantity"],
    }
    payload.update(overrides)
    return payload


def test_the_committed_inventory_is_structurally_valid():
    """Whatever is committed today must at least be well-formed.

    ``claims`` is still empty for all three sources (#86); this test is the guard
    that the first hand-written entry cannot arrive malformed and unnoticed.
    """

    entries = load_all(SOURCES)
    assert entries, f"{SOURCES} 下没有冻结清单"
    for item in entries:
        errors, _ = check_entry(item)
        assert not errors, f"{item['case_id']} 的 claims 不合规：\n  - " + "\n  - ".join(errors)


def test_a_claim_without_a_kind_is_rejected():
    """#86 requires constructed variants to be marked, so the field is not optional."""

    errors, _ = check_shape(entry([claim(claim_kind=None)]))
    assert any("claim_kind" in line for line in errors)


def test_a_kind_outside_the_known_vocabulary_is_rejected():
    errors, _ = check_shape(entry([claim(claim_kind="synthetic")]))
    assert any("claim_kind" in line for line in errors)


def test_the_source_unverifiable_label_is_not_a_judgement_label():
    """A fetch failure is not a judgement about the paper, so it cannot be an answer."""

    errors, _ = check_shape(entry([claim(expected_label="无法核验来源")]))
    assert any("不是四类标签之一" in line for line in errors)
    assert any("任务终态" in line for line in errors)


def test_every_judgement_label_is_accepted():
    for label in JUDGEMENT_LABELS:
        evidence = None if label == "证据不足" else {"ordinal": 1, "quote": TEXT}
        errors, _ = check_shape(entry([claim(expected_label=label, evidence=evidence)]))
        assert not errors, f"{label} 被误判为不合规：{errors}"


def test_evidence_is_required_unless_the_label_is_insufficient():
    errors, _ = check_shape(entry([claim(evidence=None)]))
    assert any("evidence" in line for line in errors)

    errors, _ = check_shape(entry([claim(expected_label="证据不足", evidence=None)]))
    assert not any("evidence" in line for line in errors)


def test_an_insufficient_claim_may_cite_a_fragment_but_is_flagged_for_review():
    """The most common mislabelling: a fragment that fails to support is not absence."""

    errors, warnings = check_shape(entry([claim(expected_label="证据不足", evidence={
        "ordinal": 1, "quote": "adult cohort"})]))
    assert not errors
    assert any("证据不足" in line and "部分支持或相矛盾" in line for line in warnings)


def test_duplicate_claim_ids_are_rejected():
    errors, _ = check_shape(entry([claim(), claim(claim_id="c1")]))
    assert any("重复" in line for line in errors)


def test_an_unknown_field_is_reported_but_does_not_fail_the_record():
    errors, warnings = check_shape(entry([claim(dimension="quantity")]))
    assert not errors
    assert any("未识别字段" in line for line in warnings)


def test_a_paraphrased_quote_is_not_locatable():
    """This is the check the handwritten pass cannot do for itself."""

    paraphrased = claim(evidence={"ordinal": 1, "quote": "the treatment cut death rates by 20%"})
    problems = quotes(entry([paraphrased]), {1: TEXT})
    assert any("逐字定位" in line for line in problems)


def test_a_quote_that_differs_only_in_whitespace_is_locatable():
    wrapped = claim(evidence={"ordinal": 1, "quote": "reduced  mortality\nby 20 percent"})
    assert not quotes(entry([wrapped]), {1: TEXT})


def test_a_quote_for_a_missing_ordinal_is_rejected():
    problems = quotes(entry([claim(evidence={"ordinal": 9, "quote": TEXT})]), {1: TEXT})
    assert any("没有 ordinal 9" in line for line in problems)


def test_a_quote_longer_than_its_paragraph_is_rejected():
    problems = quotes(entry([claim(evidence={"ordinal": 1, "quote": TEXT * 2})]), {1: TEXT})
    assert any("还长" in line for line in problems)


def test_offline_a_complete_preview_is_a_complete_check():
    """When the paragraph fits in the stored preview, a miss is definitive."""

    problems = quotes(entry([claim(evidence={"ordinal": 1, "quote": "mortality by 30 percent"})]))
    assert any("清单存了整段预览" in line for line in problems)


def _truncated(quote: str = "B" * 10) -> dict:
    """An entry whose single paragraph is longer than the stored preview."""

    long_text = "A" * 200
    paragraphs = [{
        "ordinal": 1,
        "section": "body",
        "paragraph_hash": paragraph_hash(long_text),
        "text_length": len(long_text),
        "native_jats_id": "p1",
        "preview": long_text[:120],
    }]
    return entry([claim(evidence={"ordinal": 1, "quote": quote})], paragraphs=paragraphs)


def test_offline_a_truncated_preview_never_condemns_a_quote():
    """A quote past the 120-character cut may be correct; only ``--live`` can say."""

    problems, warnings = check_quotes(_truncated())
    assert not problems, "截断预览不能把一条可能正确的引文判错"
    assert any(OFFLINE_UNCHECKED in line and "--live" in line for line in warnings)


def test_offline_a_truncated_preview_never_passes_a_quote_silently():
    """The failure this guards: an empty result reads as "checked and fine".

    The quote is not condemned (it may straddle the cut), but it must be named as
    unchecked — both by the per-source line and by the checker's own return value.
    """

    errors, warnings = check_entry(_truncated())
    assert not errors
    assert _status(errors, warnings) == f"通过（含 1 条{OFFLINE_UNCHECKED}）"

    _, quiet = check_quotes(entry([claim()]))
    assert _status([], quiet) == "通过", "整段在预览内的引用应当就是「通过」"


def test_a_quote_found_inside_the_preview_counts_as_checked():
    """A hit is a hit even when the paragraph continues past the cut."""

    problems, warnings = check_quotes(_truncated("A" * 40))
    assert not problems
    assert not warnings


def test_a_live_fetch_that_lost_a_paragraph_is_reported():
    """Inventory drift has two directions; comparing only live ordinals sees one."""

    two = [
        {"ordinal": 1, "section": "body", "paragraph_hash": paragraph_hash(TEXT),
         "text_length": len(TEXT), "native_jats_id": "p1", "preview": TEXT},
        {"ordinal": 2, "section": "body", "paragraph_hash": paragraph_hash("Second."),
         "text_length": 7, "native_jats_id": "p2", "preview": "Second."},
    ]
    errors, _ = check_entry(entry([claim()], paragraphs=two), {1: TEXT})
    assert any("线上没有" in line and "ordinal 2" in line for line in errors)


def test_the_directory_option_keeps_its_old_name_as_an_alias():
    """``--out`` mirrors ``freeze_sources.py``; ``--sources`` says what it is."""

    parser = build_parser()
    assert parser.parse_args(["--sources", "x"]).sources == Path("x")
    assert parser.parse_args(["--out", "x"]).sources == Path("x")


def test_a_drifted_paragraph_hash_is_reported_as_drift():
    """Claims are written against frozen text; a changed hash invalidates them all."""

    live = {1: "A completely different sentence about something else entirely."}
    errors, _ = check_entry(entry([claim()]), live)
    assert any("哈希与清单不一致" in line for line in errors)


def test_coverage_counts_labels_and_dimensions_and_names_the_gaps():
    entries = [
        entry([claim(expected_label="支持", dimensions=["object"]),
               claim(claim_id="c2", expected_label="相矛盾", dimensions=["causality"],
                     evidence={"ordinal": 1, "quote": "reduced mortality"})],
              case_id="PMC_A"),
        entry([claim(expected_label="证据不足", evidence=None, dimensions=[])],
              case_id="PMC_B"),
    ]

    report = coverage(entries)
    assert report["total"] == 3
    assert report["labels"]["支持"] == 1
    assert report["labels"]["证据不足"] == 1
    assert report["dimensions"]["object"] == 1
    assert report["untagged"] == 1

    gaps = coverage_gaps(entries)
    assert "标签「部分支持」0 条" in gaps
    assert "维度「数量」0 条" in gaps

    table = render_coverage(entries)
    assert "PMC_A" in table and "PMC_B" in table
    assert "未覆盖的标签：部分支持" in table


def test_empty_claims_are_reported_as_incomplete_not_as_passing():
    table = render_coverage(load_all(SOURCES))
    assert "claims 全为空" in table
    assert coverage_gaps(load_all(SOURCES)), "空集不应被当作覆盖达标"


@pytest.mark.parametrize("missing", ["claim", "expected_label", "evidence"])
def test_a_half_written_claim_cannot_pass(missing):
    payload = claim()
    payload.pop(missing)
    errors, _ = check_shape(entry([payload]))
    assert errors


def test_the_checker_reads_the_files_it_ships_with():
    """Guard against a stale import path picking up another checkout's backend."""

    import paper_evidence

    assert Path(paper_evidence.__file__).resolve().parents[2] == Path(__file__).resolve().parents[2]
