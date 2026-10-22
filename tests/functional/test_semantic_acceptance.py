"""Semantic acceptance for the functional-accuracy dimension (测试方案「功能准确性」).

Every case drives the real bounded workflow with the frozen source substituted
for the live connectors. A label is credited only when the deterministic gates
accepted a quote that really is in the frozen paragraph — the transcript does
not get to assert its own correctness.

The evaluator is itself under test: :func:`acceptance_failures` must pass the
human-checked result *and* reject a deliberately wrong label or a quote that is
not in the cited paragraph. A control that never rejects would let any output
through, so a failing control forbids publishing a semantic score (测试方案
「验收器负向控制」).
"""

import json
from dataclasses import replace

import pytest

from acceptance import available_cases, load_case
from paper_evidence.domain import ErrorCode, TaskStatus
from paper_evidence.domain.rules import DEFINITIVE_LABELS
from paper_evidence.domain.text import quote_spans

CASES = available_cases()


def _restate(case, quote: str) -> str:
    """The sample's own decision, but citing ``quote`` instead of the checked one."""

    payload = json.loads(case.transcript[1])
    payload["decision"]["evidence"] = [{"paragraph": 1, "quote": quote}]
    return json.dumps(payload, ensure_ascii=False)


def acceptance_failures(detail, case, paragraphs) -> list[str]:
    """Every reason ``detail`` fails the human check for ``case``; empty means pass.

    Deliberately returns reasons instead of asserting so the same evaluator can
    be pointed at a correct result and at a tampered one in the control test.
    """

    reasons: list[str] = []
    if detail.status is not TaskStatus.COMPLETED:
        return [f"任务终态是 {detail.status} / {detail.error_code}，不是 COMPLETED"]
    if detail.label is None:
        return ["任务完成但没有发布标签"]
    if detail.label != case.label:
        reasons.append(f"标签 {detail.label!r} 与人工核对的 {case.label!r} 不一致")
    decision = detail.decision
    if decision is None:
        return [*reasons, "任务完成但没有判断记录"]
    if case.label in DEFINITIVE_LABELS:
        # 术语表「5. 证据门槛」: a definitive label needs at least one locatable quote.
        if not decision.evidence:
            reasons.append("确定判断没有给出任何摘录")
        for item in decision.evidence:
            paragraph = paragraphs.get(item.paragraph_id)
            if paragraph is None:
                reasons.append(f"摘录引用了冻结版本之外的段落 {item.paragraph_id}")
                continue
            if item.validation != "pass":
                reasons.append(f"摘录 {item.paragraph_id} 的 validation 不是 pass")
            if not quote_spans(paragraph.text, item.quote):
                reasons.append(f"摘录无法在段落 {item.paragraph_id} 中逐字定位：{item.quote!r}")
    return reasons


@pytest.mark.parametrize("frozen_case", CASES, indirect=True)
def test_a_frozen_case_matches_its_human_checked_label(frozen_case, acceptance):
    """逐例满足人工核对的标签与关键语义约束。"""

    outcome = acceptance(frozen_case)
    reasons = acceptance_failures(outcome.detail, frozen_case, outcome.paragraphs)
    assert not reasons, f"{frozen_case.case_id}: " + "；".join(reasons)


@pytest.mark.parametrize("frozen_case", CASES, indirect=True)
def test_a_frozen_case_is_judged_against_the_frozen_version(frozen_case, acceptance):
    """判定必须定位到样本声明的冻结版本，不能悄悄用到别的内容。"""

    outcome = acceptance(frozen_case)
    assert outcome.detail.status is TaskStatus.COMPLETED
    assert outcome.detail.source is not None
    from acceptance import VERSION_HASH

    assert outcome.detail.source.version_hash == VERSION_HASH
    assert outcome.detail.source.pmcid == "PMC0000001"


def test_the_evaluator_rejects_a_wrong_label_and_a_mismatched_quote(acceptance):
    """Negative control: the evaluator must fail on a deliberately wrong result.

    A control that never rejects would credit any output, so both an obviously
    wrong label and a quote that is absent from the cited paragraph have to be
    caught while the correct result still passes.
    """

    case = load_case(CASES[0])
    outcome = acceptance(case)

    # 正确对照：真实结果必须通过，否则验收器只会永远拒判。
    assert not acceptance_failures(outcome.detail, case, outcome.paragraphs)

    # 负向一：换成语义明确错误的标签。
    wrong_label = "相矛盾" if case.label != "相矛盾" else "支持"
    mislabelled = outcome.detail.model_copy(update={"label": wrong_label})
    assert acceptance_failures(mislabelled, case, outcome.paragraphs), "错误标签没有被检出"

    # 负向二：摘录不在被引段落中。
    decision = outcome.detail.decision
    assert decision is not None and decision.evidence
    doctored = decision.evidence[0].model_copy(update={"quote": "This sentence is not in the paper at all."})
    tampered = outcome.detail.model_copy(
        update={"decision": decision.model_copy(update={"evidence": [doctored]})}
    )
    assert acceptance_failures(tampered, case, outcome.paragraphs), "不匹配摘录没有被检出"


def test_the_evaluator_rejects_a_definitive_label_without_evidence(acceptance):
    """负向控制：确定判断缺少可定位摘录时不得通过。"""

    case = load_case(CASES[0])
    outcome = acceptance(case)
    decision = outcome.detail.decision
    assert decision is not None
    stripped = outcome.detail.model_copy(
        update={"decision": decision.model_copy(update={"evidence": []})}
    )
    assert acceptance_failures(stripped, case, outcome.paragraphs), "无摘录的确定判断没有被检出"


def test_a_sample_that_points_at_a_missing_paragraph_is_refused(acceptance):
    """样本写错段落号时必须显式失败，不能静默丢掉摘录。"""

    from acceptance import SampleReferenceError

    case = load_case(CASES[0])
    # 把第一条 evidence 指向一个不存在的段号。
    broken = list(case.transcript)
    broken[1] = broken[1].replace('"paragraph": 1', '"paragraph": 99')
    with pytest.raises(SampleReferenceError):
        acceptance(case, transcript=broken)


def test_a_quote_outside_the_frozen_paragraph_cannot_become_a_definitive_label(acceptance):
    """确定性判定：摘录无法逐字定位时不得发布确定判断（测试方案「确定性判定」）。

    This exercises the application's own gate, not the evaluator's: the same
    definitive label is offered twice (the second is the repair request) and the
    workflow still has to refuse to publish it.
    """

    case = load_case("support_object_scope")
    bogus = _restate(case, "This sentence does not appear in the frozen paragraph.")
    outcome = acceptance(case, transcript=[case.transcript[0], bogus, bogus])

    assert outcome.detail.status is TaskStatus.FAILED, outcome.detail.status
    assert outcome.detail.error_code is ErrorCode.QUOTE_MISMATCH
    assert outcome.detail.label is None, "摘录校验失败时不得展示确定判断"
    assert acceptance_failures(outcome.detail, case, outcome.paragraphs), "拒判结果不应被判为通过"


def test_the_frozen_set_is_decidable_rather_than_all_refusals(acceptance):
    """可判定覆盖：验收集不能全部以「证据不足」通过（测试方案「通过条件」）。

    A set that passes only by refusing everything would satisfy "not wrong" while
    proving nothing, so the decidable labels must actually appear.
    """

    published = {}
    for case_id in CASES:
        case = load_case(case_id)
        outcome = acceptance(case)
        assert outcome.detail.label is not None, f"{case_id}: 样本应以人工核对的标签完成"
        published[case_id] = outcome.detail.label.value

    assert set(published.values()) >= {"支持", "部分支持", "相矛盾"}, published

#: 两段都支持同一论断的正文：结果段与摘要段在真实论文里常常重复同一结论。
#: 第 1 段是样本人工核对的引用位置，第 2 段是「邻段同样支持」的情形。
NEIGHBOUR_JATS = b"""<?xml version="1.0" encoding="UTF-8"?>
<article xml:lang="en"><front><article-meta/></front><body>
<sec id="s1"><title>Results</title>
<p id="n1">The treatment reduced mortality by 20 percent.</p>
<p id="n2">Mortality was 20 percent lower in the treated group.</p>
</sec></body></article>
"""
NEIGHBOUR_QUOTE = "Mortality was 20 percent lower in the treated group."


def test_a_neighbouring_paragraph_that_also_supports_is_not_a_hard_failure(acceptance):
    """邻段同样支持论断时，不得仅因更换邻段就硬判失败（测试方案 `test-plan.md:47`）。

    判据要防的是一种很自然的错法：验收器把「引了别的段落」直接等同于「引错了」。
    真实论文里同一个结论往往在摘要、结果段、讨论段各说一遍，模型引到哪一段都算
    找对了证据，差别只在定位，不在标签。

    这里把样本换成**两段都支持**的正文（断言论断与标签都不变），让模型引第 2 段：
    工作流必须照常完成并发布同一个标签，验收器也必须判它通过。对照放在同一个用例
    里——同一段引文换成另一段的原文必须被检出，否则「通过」可能只是因为验收器根本
    不看摘录。
    """

    base = load_case("support_object_scope")
    case = replace(base, jats=NEIGHBOUR_JATS)
    decision = json.dumps({"action": "final", "decision": {
        "label": case.label, "rationale": "两段都给出 20% 的降幅。",
        "supported_parts": ["死亡率下降 20%"], "scope_differences": [],
        "limitations": [], "evidence": [{"paragraph": 2, "quote": NEIGHBOUR_QUOTE}],
    }}, ensure_ascii=False)

    outcome = acceptance(case, transcript=['{"queries": ["mortality"]}', decision])

    assert outcome.detail.status is TaskStatus.COMPLETED, outcome.detail.error_code
    assert outcome.detail.label.value == case.label
    assert [item.paragraph_id for item in outcome.detail.decision.evidence] == [
        item.paragraph_id for item in outcome.paragraphs.values() if item.ordinal == 2
    ]
    reasons = acceptance_failures(outcome.detail, case, outcome.paragraphs)
    assert not reasons, "换了同样支持论断的邻段就被判失败：" + "；".join(reasons)

    # 对照：仍引第 2 段，但摘录换成第 1 段的原文 → 必须被检出。
    checked = outcome.detail.decision.evidence[0]
    swapped = checked.model_copy(update={"quote": base.quote("support")})
    tampered = outcome.detail.model_copy(update={
        "decision": outcome.detail.decision.model_copy(update={"evidence": [swapped]})})
    assert acceptance_failures(tampered, case, outcome.paragraphs), "引了别段的摘录没有被检出"

