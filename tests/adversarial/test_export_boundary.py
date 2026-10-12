"""Export authorization is separate from model consent (测试方案「对抗与安全」).

判定：semantic export 的本地预览和接收方授权与模型调用分开；redacted 导出保留
公开 DOI、PMCID、题名及章节；来源字段来自公开原文，不接受模型生成文本冒充
公开书目。
"""

import json

from conftest import PMCID, VERSION_HASH, final_action, jats_with, pid, query_action

from paper_evidence.diagnosis.projector import REDACTION_PLACEHOLDER
from paper_evidence.domain import ErrorCode, TaskStatus


def _run(run_workflow, text: str = "The treatment reduced mortality."):
    return run_workflow(
        claim=text,
        jats_bytes=jats_with([text]),
        outputs=[query_action("mortality"), final_action(1, text)],
    )


def test_the_redacted_packet_keeps_the_public_bibliography(run_workflow):
    """redacted 保留公开书目与章节，不能错误地要求它隐藏这些字段。"""

    run = _run(run_workflow)
    packet = run.projector.redacted(run.task_id)

    assert packet.source is not None
    assert packet.source.pmcid == PMCID
    assert packet.source.title == "frozen"
    assert packet.source.doi == "10.1000/adversarial"
    assert packet.source.version_hash == VERSION_HASH
    # 章节来自公开原文，同样保留。
    assert packet.evidence_candidates
    assert all(item.section for item in packet.evidence_candidates)


def test_the_redacted_packet_still_masks_the_claim_while_keeping_the_bibliography(run_workflow):
    """保留书目不等于保留论断：两者必须分开处理。"""

    run = _run(run_workflow)
    packet = run.projector.redacted(run.task_id)

    assert packet.source.title == "frozen"
    assert packet.input.claim == REDACTION_PLACEHOLDER


def test_the_model_cannot_inject_a_bibliographic_field(run_workflow):
    """模型输出带书目字段时被拒，来源字段只能来自公开原文。"""

    text = "The treatment reduced mortality."
    fabricated = "MODEL-FABRICATED-TITLE"
    bogus = json.dumps({
        "action": "final",
        "decision": {
            "label": "支持", "rationale": "r", "supported_parts": [], "scope_differences": [],
            "limitations": [], "title": fabricated,
            "evidence": [{"paragraph_id": pid(1), "quote": text}],
        },
    }, ensure_ascii=False)
    run = run_workflow(
        claim=text,
        jats_bytes=jats_with([text]),
        outputs=[query_action("mortality"), bogus, bogus],
    )

    assert run.detail.status is TaskStatus.FAILED
    assert run.detail.error_code is ErrorCode.MODEL_INVALID_OUTPUT
    assert run.detail.source is not None and run.detail.source.title == "frozen"
    blob = json.dumps(run.detail.model_dump(mode="json"), ensure_ascii=False)
    assert fabricated not in blob, "模型生成的书目字段不得进入结果"


def test_the_redacted_and_consented_views_differ_only_by_the_gated_text(run_workflow):
    """两种视图的结构与标识一致，只有受授权约束的文本不同。"""

    run = _run(run_workflow)
    redacted = run.projector.redacted(run.task_id)
    consented = run.projector.consented(run.task_id, "External Reviewer")

    assert redacted.schema_version == consented.schema_version
    assert redacted.case_id == consented.case_id
    assert redacted.source == consented.source
    assert redacted.status == consented.status
    assert redacted.input.privacy == "redacted"
    assert consented.input.privacy == "consented"
    assert redacted.input.claim != consented.input.claim


def test_the_consented_view_records_the_recipient_locally(run_workflow):
    """导出在本地留下接收方记录，不产生自动外传。"""

    run = _run(run_workflow)
    packet = run.projector.consented(run.task_id, "External Reviewer")

    assert packet.input.recipient == "External Reviewer"
    # 返回值就是交给作者下载的内容；应用自身没有发送步骤。
    assert packet.input.privacy == "consented"
