"""承重用例 for ``triage.py``.

The packet under test is a **real** one: ``packets/packet_completed.json`` was written
by ``SqliteDiagnosticProjector`` from a completed workflow run over a frozen three-
paragraph source (two candidates recalled, the third never retrieved). Every case
starts from that packet and changes one field, so the shapes are the product's, not
a hand-written guess at them.

What is deliberately *not* asserted: that a rule fires on every possible packet. The
point of these cases is the boundary the tool refuses to cross — no human answer, no
「检索遗漏」 — because that is the claim a defect report is built on.
"""

import json
from pathlib import Path

from paper_evidence.domain.contracts import DiagnosticPacket, ModelCall
from paper_evidence.domain.enums import ErrorCode, ResultLabel

import triage
from triage import triage as run

#: Deliberately **not** ``samples/``: that directory *is* the semantic-acceptance case
#: set, and every JSON in it becomes a case. The packet is a fixture, not a case.
PACKETS = Path(__file__).parent / "packets"
BASE = DiagnosticPacket.model_validate(json.loads((PACKETS / "packet_completed.json").read_text(encoding="utf-8")))


def variant(**overrides) -> DiagnosticPacket:
    """The real packet with named fields replaced, re-validated by the contract."""

    return DiagnosticPacket.model_validate({**BASE.model_dump(), **overrides})


def codes(findings) -> list[str]:
    return [finding.code for finding in findings]


def candidate_at(ordinal: int):
    return next(item for item in BASE.evidence_candidates
                if triage._ordinal_of(item.paragraph_id) == ordinal)


def call_with_attempt_error(code: ErrorCode) -> ModelCall:
    call = BASE.model_calls[0]
    attempt = call.attempts[0].model_copy(update={"status": "error", "error_code": code})
    return call.model_copy(update={"attempts": [attempt]})


def test_the_fixture_is_a_real_completed_packet():
    """Guard: if the fixture stops looking like a real run, the cases below are void."""

    assert str(BASE.status) == "COMPLETED"
    assert len(BASE.execution) >= 5
    assert len(BASE.model_calls) == 2
    assert [triage._ordinal_of(c.paragraph_id) for c in BASE.evidence_candidates] == [1, 2]
    assert all(c.entered_context for c in BASE.evidence_candidates)


def test_a_source_gate_never_reaches_the_model():
    """No model call means the model cannot be the cause."""

    findings = run(variant(status="BLOCKED", error_code=ErrorCode.LICENSE_UNKNOWN, model_calls=[]))

    assert findings[0].code == "SOURCE_GATE"
    assert findings[0].role == "primary"
    assert any("model_calls=0" in line for line in findings[0].evidence)
    assert "OUTPUT_CONTRACT" not in codes(findings)


def test_a_rate_limited_attempt_is_attributed_to_the_upstream():
    findings = run(variant(
        status="FAILED",
        error_code=ErrorCode.UPSTREAM_RATE_LIMITED,
        model_calls=[call_with_attempt_error(ErrorCode.UPSTREAM_RATE_LIMITED)],
    ))

    assert "UPSTREAM" in codes(findings)
    upstream = next(item for item in findings if item.code == "UPSTREAM")
    assert any("UPSTREAM_RATE_LIMITED" in line for line in upstream.evidence)
    assert any("request_id=" in line for line in upstream.evidence)


def test_a_quote_mismatch_is_named_with_its_request_and_repair():
    decision_call = BASE.model_calls[1]
    repair = decision_call.model_copy(update={
        "request_id": "pkt-1:output_repair:1",
        "purpose": "output_repair",
        "repairs_request_id": decision_call.request_id,
    })
    findings = run(variant(
        status="FAILED",
        error_code=ErrorCode.QUOTE_MISMATCH,
        model_calls=[BASE.model_calls[0], call_with_attempt_error(ErrorCode.QUOTE_MISMATCH), repair],
    ))

    assert findings[0].code == "OUTPUT_CONTRACT"
    assert any("QUOTE_MISMATCH" in line for line in findings[0].evidence)
    assert "REPAIR_EXHAUSTED" in codes(findings)
    repaired = next(item for item in findings if item.code == "REPAIR_EXHAUSTED")
    assert repaired.role == "secondary"
    assert any(decision_call.request_id in line for line in repaired.evidence)


def test_an_explicit_retrieval_error_is_reported_as_such():
    findings = run(variant(status="BLOCKED", error_code=ErrorCode.RETRIEVAL_EMPTY,
                           model_calls=[], evidence_candidates=[]))

    assert findings[0].code == "RETRIEVAL_EMPTY"
    assert any("candidates=0" in line for line in findings[0].evidence)


def test_an_empty_candidate_set_alone_is_not_called_a_retrieval_miss():
    """The defect a triage tool must not invent: "nothing recalled" ≠ "the right paragraph was missed"."""

    findings = run(variant(evidence_candidates=[], status="COMPLETED", label=ResultLabel.INSUFFICIENT_EVIDENCE))

    assert "RETRIEVAL_MISS" not in codes(findings)
    assert findings[0].code == "NO_FINDING"
    assert "不等于通过" in findings[0].summary


def test_without_an_expected_ordinal_the_tool_refuses_to_claim_a_retrieval_miss():
    """Asking the question is what makes the verdict possible — the tool never assumes it."""

    assert "RETRIEVAL_MISS" not in codes(run(BASE))
    findings = run(BASE, expect_ordinal=3)

    miss = next(item for item in findings if item.code == "RETRIEVAL_MISS")
    assert "expected_ordinal=3" in miss.evidence[0]
    assert "candidate_ordinals=[1, 2]" in miss.evidence[-1]


def test_a_recalled_paragraph_left_out_of_context_is_a_context_miss():
    second = candidate_at(2)
    weakened = second.model_copy(update={"entered_context": False})
    findings = run(variant(evidence_candidates=[candidate_at(1), weakened]), expect_ordinal=2)

    assert "CONTEXT_MISS" in codes(findings)
    assert "RETRIEVAL_MISS" not in codes(findings)


def test_a_recalled_and_cited_paragraph_has_no_retrieval_defect():
    findings = run(BASE, expect_ordinal=2)

    assert "RETRIEVAL_OK" in codes(findings)
    ok = next(item for item in findings if item.code == "RETRIEVAL_OK")
    assert any("cited_by_decision=True" in line for line in ok.evidence)


def test_a_recalled_paragraph_the_decision_did_not_cite_is_a_model_choice():
    """Retrieval did its job; the paragraph entered the context and the model ignored it."""

    first = candidate_at(1)
    # Cite paragraph 1 instead of the one the model actually used (paragraph 2).
    cited = BASE.decision.evidence[0].model_copy(update={"paragraph_id": first.paragraph_id})
    decision = BASE.decision.model_copy(update={"evidence": [cited]})
    assert decision.evidence[0].paragraph_id == first.paragraph_id
    findings = run(variant(decision=decision), expect_ordinal=2)

    assert "MODEL_IGNORED" in codes(findings)
    assert "RETRIEVAL_MISS" not in codes(findings)
    assert "CONTEXT_MISS" not in codes(findings)


def test_a_label_difference_with_a_clean_pipeline_is_a_criteria_gap():
    findings = run(BASE, expect_label="相矛盾")

    assert findings[0].code == "JUDGEMENT_DIVERGENCE"
    assert "判据边界" in findings[0].summary


def test_a_cancelled_run_is_not_attributed_to_a_technical_cause():
    findings = run(variant(status="CANCELLED", cancel_requested=True,
                           error_code=ErrorCode.MODEL_INVALID_OUTPUT))

    assert codes(findings) == ["CANCELLED"]
    assert "不是技术缺陷" in findings[0].summary


def test_the_verdict_does_not_depend_on_the_claim_text():
    """A redacted packet and one carrying a marker claim must triage identically."""

    marked = json.loads(json.dumps(BASE.model_dump()))
    marked["input"]["claim"] = "SENSITIVE-CLAIM-MARKER 治疗使死亡率下降"
    with_marker = DiagnosticPacket.model_validate(marked)

    # Every branch that can render text, not just the one the fixture happens to hit:
    # a leak added to any single branch must be caught by at least one of these.
    for kwargs in ({}, {"expect_ordinal": 3}, {"expect_ordinal": 2}, {"expect_label": "相矛盾"}):
        assert "SENSITIVE-CLAIM-MARKER" not in triage.render(run(with_marker, **kwargs)), kwargs

    plain = run(BASE, expect_ordinal=3)
    assert [(f.code, f.role) for f in plain] == [
        (f.code, f.role) for f in run(with_marker, expect_ordinal=3)
    ]


def test_a_clean_run_says_so_instead_of_returning_an_empty_list():
    findings = run(BASE)

    assert codes(findings) == ["NO_FINDING"]
    assert "不等于通过" in findings[0].summary


def test_the_cli_reads_a_packet_file_and_prints_the_primary_cause(capsys):
    assert triage.main([str(PACKETS / "packet_completed.json")]) == 0
    printed = capsys.readouterr().out
    assert "pkt-1" in printed
    assert "NO_FINDING" in printed


def test_the_cli_refuses_a_malformed_packet(tmp_path):
    broken = tmp_path / "broken.json"
    broken.write_text('{"status": "COMPLETED"}', encoding="utf-8")

    assert triage.main([str(broken)]) == 2
