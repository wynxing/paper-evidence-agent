"""Sensitive values must not leave the consented export (测试方案「对抗与安全」).

在正常与失败路径注入敏感标记，扫描 redacted 导出。理由与限制字段也要一并
检查，因为它们不能绕过脱敏。
"""

import json

from doubles import (
    CLAIM_MARKER,
    PARAGRAPH_MARKER,
    QUERY_MARKER,
    final_action,
    jats_with,
    pid,
    query_action,
)

from paper_evidence.diagnosis.projector import REDACTION_PLACEHOLDER

MARKERS = (CLAIM_MARKER, PARAGRAPH_MARKER, QUERY_MARKER)


def _blob(packet) -> str:
    return json.dumps(packet.model_dump(mode="json"), ensure_ascii=False)


def _decision_json(rationale: str, limits: list[str], ordinal: int, quote: str) -> str:
    return json.dumps({
        "action": "final",
        "decision": {
            "label": "支持", "rationale": rationale, "supported_parts": [],
            "scope_differences": [], "limitations": limits,
            "evidence": [{"paragraph_id": pid(ordinal), "quote": quote}],
        },
    }, ensure_ascii=False)


def _run_with_markers(run_workflow, *, rationale: str, limits: list[str]):
    claim = f"The treatment reduced mortality. {CLAIM_MARKER}"
    paragraph = f"The treatment reduced mortality. {PARAGRAPH_MARKER}"
    return run_workflow(
        claim=claim,
        jats_bytes=jats_with([paragraph]),
        # "mortality" 让首轮检索非空；标记同时作为查询词，用来证明查询文本不外泄。
        outputs=[query_action("mortality", QUERY_MARKER), _decision_json(rationale, limits, 1, paragraph)],
    )


def test_the_redacted_packet_carries_no_sensitive_marker(run_workflow):
    """redacted 导出不得带出原句、段落文本或查询。"""

    run = _run_with_markers(
        run_workflow,
        rationale=f"因为 {CLAIM_MARKER}",
        limits=[f"限制 {PARAGRAPH_MARKER}"],
    )
    blob = _blob(run.projector.redacted(run.task_id))

    for marker in MARKERS:
        assert marker not in blob, f"{marker} 泄漏到 redacted 包"


def test_reason_and_limitation_fields_are_redacted_too(run_workflow):
    """理由与限制字段不能绕过脱敏。"""

    run = _run_with_markers(
        run_workflow,
        rationale=f"因为 {CLAIM_MARKER}",
        limits=[f"限制 {PARAGRAPH_MARKER}"],
    )
    packet = run.projector.redacted(run.task_id)

    assert packet.decision is not None
    assert packet.decision.rationale == REDACTION_PLACEHOLDER
    assert packet.decision.limitations == [REDACTION_PLACEHOLDER]


def test_every_free_text_field_in_the_redacted_packet_is_a_placeholder(run_workflow):
    """论断、候选摘录与已发布摘录都必须被替换成占位符。"""

    run = _run_with_markers(run_workflow, rationale="r", limits=[])
    packet = run.projector.redacted(run.task_id)

    assert packet.input.claim == REDACTION_PLACEHOLDER
    assert packet.evidence_candidates, "本用例需要非空候选，否则测不到摘录遮罩"
    assert all(item.quote == REDACTION_PLACEHOLDER for item in packet.evidence_candidates)
    assert packet.decision is not None and packet.decision.evidence
    assert all(item.quote == REDACTION_PLACEHOLDER for item in packet.decision.evidence)


def test_the_consented_packet_keeps_the_claim_as_a_control(run_workflow):
    """对照组：已授权导出保留原句，确认遮罩不是无差别丢弃。"""

    run = _run_with_markers(run_workflow, rationale="r", limits=[])
    packet = run.projector.consented(run.task_id, "External Reviewer")

    assert CLAIM_MARKER in packet.input.claim, "consented 导出应保留原句"
    assert packet.input.privacy == "consented"


def test_a_failed_run_is_redacted_the_same_way(run_workflow):
    """失败路径的 redacted 包同样不得带出敏感标记。"""

    claim = f"The treatment reduced mortality. {CLAIM_MARKER}"
    paragraph = f"The treatment reduced mortality. {PARAGRAPH_MARKER}"
    run = run_workflow(
        claim=claim,
        jats_bytes=jats_with([paragraph]),
        # 引用不存在的段落 -> 拒判。
        outputs=[
            query_action("mortality", QUERY_MARKER),
            final_action(2, paragraph),
            final_action(2, paragraph),
        ],
    )
    assert run.detail.decision is None, "拒判时不应有已发布判断"

    blob = _blob(run.projector.redacted(run.task_id))
    for marker in MARKERS:
        assert marker not in blob, f"{marker} 从失败路径泄漏到 redacted 包"
