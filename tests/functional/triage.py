"""Trace-driven defect triage: attribute a finished run to a cause, from its packet.

Run from the repository root (``PYTHONPATH`` must point at ``backend`` so the
contract being validated is *this* checkout's, not a globally installed one)::

    PYTHONPATH=backend python tests/functional/triage.py packet.json
    PYTHONPATH=backend python tests/functional/triage.py packet.json --expect-ordinal 39 --expect-label 支持
    PYTHONPATH=backend python tests/functional/triage.py packet.json --json    # for the report

The input is a diagnostic packet (``DiagnosticPacket``, schema 2.2), not a log. Every
judgement is made from structured fields — ``status``, ``error_code``, the
``execution`` records, the ``model_calls`` attempts, ``evidence_candidates`` and their
``entered_context`` flag, and the paragraphs the ``decision`` actually cited. The
claim text and the quoted passages are never read, so a **redacted** packet triages
exactly like a consented one.

What this can and cannot say:

* It **can** separate a run that never reached the model (source gate, upstream) from
  one where the model answered and the output did not satisfy the contract
  (``QUOTE_MISMATCH``, ``MODEL_INVALID_OUTPUT``), from one where the model answered
  correctly but the label disagrees with the human answer.
* It **cannot** claim 「检索遗漏」 without a human answer. An empty candidate set only
  says retrieval returned nothing — it does not say the paragraph that should have
  been found exists. Pass ``--expect-ordinal`` (from the reviewed ``claims`` evidence)
  to ask the narrower question: *that* paragraph, was it retrieved, did it enter the
  context, did the decision cite it? Those are three different defects and the tool
  reports them separately.

That distinction is the whole point: a triage tool that guesses 「检索遗漏」 from
"no candidates" would produce a defect report that cannot be reproduced.
"""

from __future__ import annotations

import argparse
import json
import sys
from dataclasses import dataclass
from pathlib import Path

from paper_evidence.domain.contracts import DiagnosticPacket
from paper_evidence.domain.enums import ErrorCode, TaskStatus
# 「一次模型都没调就终态的」就是来源门禁拒掉的那组错误码。这组词汇的唯一来源在
# ``domain/rules.py``（``BLOCKED_CODES``）：在那里加码，这里自动跟着变——手抄一份
# 的下场是 rules 新增一个来源类码后，那次失败掉进 BLOCKED_BEFORE_MODEL，归因错层。
from paper_evidence.domain.rules import BLOCKED_CODES as SOURCE_GATE_CODES

#: The model answered and the answer was unusable. Distinguished from an upstream
#: failure because the fix lives in the prompt/repair path, not in the transport.
MODEL_OUTPUT_CODES = frozenset({ErrorCode.QUOTE_MISMATCH, ErrorCode.MODEL_INVALID_OUTPUT})


@dataclass(frozen=True)
class Finding:
    """One attributed cause, with the fields it was read from.

    ``evidence`` lines are ``field=value`` so a reviewer can re-read the packet and
    check the conclusion without trusting the tool. ``role`` is ``primary`` for the
    single cause that explains the terminal state and ``secondary`` for concurrent
    ones; ``ruled_out`` records what was explicitly *not* the cause, which is what
    makes this a localisation rather than a description.
    """

    code: str
    summary: str
    evidence: tuple[str, ...]
    role: str = "primary"


def _code(value) -> ErrorCode | None:
    return value if isinstance(value, ErrorCode) else (ErrorCode(value) if value else None)


def _ordinal_of(paragraph_id: str) -> int | None:
    """Read the ordinal out of ``p:<source>:<hash>:<parser>:<ordinal>``.

    The shape is fixed by :func:`paper_evidence.domain.text.paragraph_id`; the last
    colon-separated field is the ordinal. Anything else returns ``None`` instead of
    guessing, because a wrong ordinal would make the retrieval verdict wrong.
    """

    tail = paragraph_id.rsplit(":", 1)[-1]
    try:
        return int(tail)
    except (TypeError, ValueError):
        return None


def triage(
    packet: DiagnosticPacket,
    *,
    expect_ordinal: int | None = None,
    expect_label: str | None = None,
) -> list[Finding]:
    """Attribute a packet to one primary cause plus the causes it rules out."""

    status = str(packet.status)
    code = _code(packet.error_code)
    calls = list(packet.model_calls)
    executions = list(packet.execution)
    candidates = list(packet.evidence_candidates)
    decision = packet.decision

    if packet.status is TaskStatus.CANCELLED:
        return [Finding(
            "CANCELLED",
            "任务被取消：取消是用户的终态决定，不是技术缺陷，其余错误不再归因",
            (f"status={status}", f"cancel_requested={packet.cancel_requested}"),
        )]

    findings: list[Finding] = []

    # 1. Did the run ever reach the model? If not, nothing downstream can be blamed.
    if not calls:
        if code in SOURCE_GATE_CODES:
            findings.append(Finding(
                "SOURCE_GATE",
                "来源在取回 / 许可 / 形态门禁处被拒，检索与模型一次都没运行",
                (
                    f"error_code={code.value if code else None}",
                    f"model_calls=0",
                    *_last_execution(executions),
                ),
            ))
        elif code is not None and code.value.startswith("UPSTREAM_"):
            findings.append(Finding(
                "UPSTREAM",
                "上游在第一次模型请求前就失败，与提示词、检索和判据无关",
                (f"error_code={code.value}", "model_calls=0", *_last_execution(executions)),
            ))
        elif code is ErrorCode.RETRIEVAL_EMPTY:
            findings.append(Finding(
                "RETRIEVAL_EMPTY",
                "索引里没有可用段落：检索阶段明确空手，模型未被调用",
                (f"error_code={code.value}", "model_calls=0", f"candidates={len(candidates)}"),
            ))
        else:
            findings.append(Finding(
                "BLOCKED_BEFORE_MODEL",
                "任务在首次模型调用之前结束，具体原因未落在已知的来源类错误码上",
                (f"status={status}", f"error_code={code.value if code else None}", "model_calls=0"),
            ))

    # 2. The model answered; did the answer satisfy the output contract?
    contract_hits = []
    for call in calls:
        for attempt in call.attempts:
            attempt_code = _code(attempt.error_code)
            if attempt.status == "error" and attempt_code in MODEL_OUTPUT_CODES:
                contract_hits.append((call, attempt, attempt_code))
    if contract_hits:
        call, attempt, attempt_code = contract_hits[-1]
        findings.append(Finding(
            "OUTPUT_CONTRACT",
            "模型的输出没有满足契约（引用定位 / 顶层形状），与其他阶段无关",
            (
                f"request_id={call.request_id}",
                f"purpose={call.purpose}",
                f"attempt={attempt.attempt_index}",
                f"error_code={attempt_code.value}",
                f"prompt_version={call.prompt_version}",
                f"context_paragraphs={len(call.context_paragraph_ids)}",
            ),
        ))

    # 3. Was the repair path used, and did it run out?
    repairs = [call for call in calls if call.purpose == "output_repair"]
    if repairs and packet.status is not TaskStatus.COMPLETED:
        findings.append(Finding(
            "REPAIR_EXHAUSTED",
            "输出修复已发生且用尽，终态仍未产出可发布的结果",
            tuple(
                f"repair request_id={call.request_id} repairs_request_id={call.repairs_request_id}"
                for call in repairs
            ) + (f"status={status}",),
            role="secondary",
        ))

    # 4. Upstream failures that happened mid-run (after some calls succeeded).
    upstream_hits = [
        (call, attempt) for call in calls for attempt in call.attempts
        if attempt.status == "error"
        and _code(attempt.error_code) is not None
        and _code(attempt.error_code).value.startswith("UPSTREAM_")
    ]
    if upstream_hits:
        call, attempt = upstream_hits[-1]
        findings.append(Finding(
            "UPSTREAM",
            "上游请求失败（限流 / 超时 / 鉴权 / 不可用），与判据和检索无关",
            (
                f"request_id={call.request_id}",
                f"attempt={attempt.attempt_index}",
                f"error_code={_code(attempt.error_code).value}",
                f"recovery_kind={attempt.recovery_kind}",
            ),
            role="secondary" if findings else "primary",
        ))

    # 5. Tool-level errors that are not the model's output contract (already named above)
    #    nor a source-gate refusal (that story is SOURCE_GATE's; a fetch-stage
    #    LICENSE_UNKNOWN reported twice is one defect wearing two codes).
    gate_exclusion = MODEL_OUTPUT_CODES | SOURCE_GATE_CODES
    tool_errors = [
        (index, record) for index, record in enumerate(executions)
        if record.status == "error" and _code(record.error_code) not in gate_exclusion
    ]
    for index, record in tool_errors:
        findings.append(Finding(
            "TOOL_ERROR",
            f"{record.stage} 阶段的 {record.tool} 调用失败，失败点在工具而不是判断",
            (
                f"execution[{index}] stage={record.stage} tool={record.tool} "
                f"status={record.status} error_code={record.error_code}",
            ),
            role="secondary" if findings else "primary",
        ))

    # Everything found so far is a *technical* error. The two questions below — was the
    # expected paragraph retrieved, does the label match the human answer — must not
    # count an informational retrieval verdict (RETRIEVAL_OK) as one: a clean pipeline
    # plus a label difference is a criteria gap, not "another error to fix first".
    has_technical_error = bool(findings)

    # 6. Retrieval, but only against a human answer.
    if expect_ordinal is not None:
        findings.extend(
            _retrieval_findings(candidates, decision, expect_ordinal, has_error=has_technical_error)
        )

    # 7. The pipeline was clean and the label still differs: that is a criteria gap,
    #    not a defect in the run. Only claimable when no technical error fired.
    expected = _normalise_label(expect_label)
    if expected and decision is not None and _normalise_label(decision.label) != expected:
        findings.append(Finding(
            "JUDGEMENT_DIVERGENCE",
            f"发布标签与人工答案不同（{decision.label} vs {expected}）"
            + ("；管道无技术错误，属判据边界" if not has_technical_error else "；但管道另有技术错误，先修错误再看标签"),
            (
                f"decision.label={decision.label}",
                f"expected_label={expected}",
                f"decision.evidence={len(decision.evidence)}",
            ),
            role="primary" if not has_technical_error else "secondary",
        ))

    # 8. Nothing fired: say so explicitly rather than returning an empty list that
    #    could be read as "checked and clean" or "not checked".
    if not findings:
        findings.append(Finding(
            "NO_FINDING",
            "按现有字段没有可归因的缺陷；这不等于通过，只表示没有已知形态的问题",
            (
                f"status={status}",
                f"label={packet.label}",
                f"model_calls={len(calls)}",
                f"candidates={len(candidates)}",
            ),
        ))
    return findings


def _retrieval_findings(candidates, decision, expect_ordinal: int, *, has_error: bool) -> list[Finding]:
    """Three questions about one paragraph, three different defects."""

    matching = [item for item in candidates if _ordinal_of(item.paragraph_id) == expect_ordinal]
    if not matching:
        return [Finding(
            "RETRIEVAL_MISS",
            f"人工答案指到 ordinal {expect_ordinal}，但它不在候选集里：检索没有召回该段",
            (
                f"expected_ordinal={expect_ordinal}",
                f"candidates={len(candidates)}",
                f"candidate_ordinals={sorted(o for o in (_ordinal_of(c.paragraph_id) for c in candidates) if o is not None)}",
            ),
            role="secondary" if has_error else "primary",
        )]

    entered = [item for item in matching if item.entered_context]
    if not entered:
        return [Finding(
            "CONTEXT_MISS",
            f"ordinal {expect_ordinal} 被召回了，但没有进入模型上下文：问题在上下文选择，不在检索",
            (
                f"expected_ordinal={expect_ordinal}",
                f"candidate_rounds={[item.round for item in matching]}",
                "entered_context=False",
            ),
            role="secondary" if has_error else "primary",
        )]

    cited = {item.paragraph_id for item in (decision.evidence if decision is not None else [])}
    if decision is None:
        # The run never produced a verdict to check against (FAILED/CANCELLED paths
        # leave ``decision=None``). Saying 「被结论引用」 here would be a claim the
        # packet itself disproves — exactly what this tool must not output.
        return [Finding(
            "NO_DECISION",
            f"ordinal {expect_ordinal} 被召回并进入上下文，但本次运行没有可核对的结论，引用无从谈起",
            (
                f"expected_ordinal={expect_ordinal}",
                "entered_context=True",
                "decision=None",
            ),
            role="secondary" if has_error else "primary",
        )]
    if not (cited & {item.paragraph_id for item in entered}):
        return [Finding(
            "MODEL_IGNORED",
            f"ordinal {expect_ordinal} 已进入上下文，但发布结论没有引用它：这是模型选择问题，不是检索遗漏",
            (
                f"expected_ordinal={expect_ordinal}",
                f"entered_context=True（{len(entered)} 条）",
                f"decision.evidence={len(cited)} 条，均不含该段",
            ),
            role="secondary" if has_error else "primary",
        )]

    # An observation, not a defect: it never outranks a real cause, so it is always
    # secondary even on an otherwise clean packet.
    return [Finding(
        "RETRIEVAL_OK",
        f"ordinal {expect_ordinal} 被召回、进入上下文且被结论引用：检索链路这一段没有缺陷",
        (
            f"expected_ordinal={expect_ordinal}",
            "entered_context=True",
            "cited_by_decision=True",
        ),
        role="secondary",
    )]


def _last_execution(executions) -> tuple[str, ...]:
    if not executions:
        return ("execution=0（没有任何阶段记录）",)
    last = executions[-1]
    return (
        f"last_stage={last.stage} tool={last.tool} status={last.status} "
        f"error_code={last.error_code}",
    )


def _normalise_label(label) -> str | None:
    if label is None:
        return None
    value = getattr(label, "value", label)
    return str(value)


def render(findings: list[Finding]) -> str:
    lines = []
    for finding in findings:
        tag = "主因" if finding.role == "primary" else "并发"
        lines.append(f"[{tag}] {finding.code}  {finding.summary}")
        for item in finding.evidence:
            lines.append(f"       · {item}")
    return "\n".join(lines)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="从诊断包归因：把终态失败定位到来源 / 上游 / 输出契约 / 检索 / 判据",
    )
    parser.add_argument("packet", type=Path, help="DiagnosticPacket 的 JSON 文件（- 表示 stdin）")
    parser.add_argument(
        "--expect-ordinal", type=int, default=None,
        help="人工答案里该论断的 ordinal；给了才判「检索遗漏 / 上下文遗漏 / 模型未引用」",
    )
    parser.add_argument("--expect-label", default=None, help="人工答案里的标签，用于判判断分歧")
    parser.add_argument("--json", action="store_true", help="输出 JSON，供报告生成使用")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    raw = sys.stdin.read() if str(args.packet) == "-" else args.packet.read_text(encoding="utf-8")
    try:
        packet = DiagnosticPacket.model_validate(json.loads(raw))
    except Exception as error:  # noqa: BLE001 - a bad packet is a result too
        print(f"诊断包不合法：{type(error).__name__}: {error}", file=sys.stderr)
        return 2

    findings = triage(packet, expect_ordinal=args.expect_ordinal, expect_label=args.expect_label)
    if args.json:
        print(json.dumps(
            {
                "case_id": packet.case_id,
                "status": str(packet.status),
                "findings": [
                    {"code": f.code, "role": f.role, "summary": f.summary, "evidence": list(f.evidence)}
                    for f in findings
                ],
            },
            ensure_ascii=False,
            indent=2,
        ))
    else:
        print(f"{packet.case_id}  status={packet.status}  label={packet.label}")
        print(render(findings))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
