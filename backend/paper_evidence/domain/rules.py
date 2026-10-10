"""Terminal mappings, action/budget rules and the criteria snapshot.

Sources: 术语表「4. 错误码」「5. 证据门槛」「调用账与版本归属」 and 架构设计
「动作与预算」. This module is pure: it contains no I/O and no model calls.
"""

from dataclasses import dataclass, field

from .contracts import AcademicLabel, Limits, default_limits
from .digest import digest_of
from .enums import ErrorCode, ResultLabel, TaskStatus

__all__ = [
    "ACADEMIC_LABELS",
    "BLOCKED_CODES",
    "BLOCKED_PROCESSING_CODES",
    "BLOCKED_SOURCE_CODES",
    "BudgetState",
    "CRITERIA_VERSION",
    "DEFINITIVE_LABELS",
    "FAILED_CODES",
    "blocked_label",
    "criteria_reference",
    "criteria_snapshot",
    "terminal_status",
]

CRITERIA_VERSION = "0.6"

ACADEMIC_LABELS: tuple[AcademicLabel, ...] = ("支持", "部分支持", "相矛盾", "证据不足")

# 「支持」「部分支持」「相矛盾」是确定判断：展示前每条摘录都要能在冻结段落中
# 逐字定位，所以这些标签不允许零摘录（术语表「5. 证据门槛」）。
DEFINITIVE_LABELS: frozenset[str] = frozenset({"支持", "部分支持", "相矛盾"})

# DOI / metadata / identity / licence / full-text availability problems.
BLOCKED_SOURCE_CODES = frozenset({
    ErrorCode.DOI_INVALID,
    ErrorCode.DOI_UNRESOLVABLE,
    ErrorCode.METADATA_NOT_FOUND,
    ErrorCode.SOURCE_MISMATCH,
    ErrorCode.SOURCE_UNAVAILABLE,
    ErrorCode.LICENSE_UNKNOWN,
    ErrorCode.LICENSE_UNSUPPORTED,
})

# Processing-scope or content problems: registration agency, body language,
# incomplete or unparsable content.
BLOCKED_PROCESSING_CODES = frozenset({
    ErrorCode.REGISTRATION_AGENCY_UNSUPPORTED,
    ErrorCode.SOURCE_LANGUAGE_UNSUPPORTED,
    ErrorCode.CONTENT_INCOMPLETE,
})

BLOCKED_CODES = BLOCKED_SOURCE_CODES | BLOCKED_PROCESSING_CODES

FAILED_CODES = frozenset({
    ErrorCode.RETRIEVAL_FAILED,
    ErrorCode.UPSTREAM_TIMEOUT,
    ErrorCode.UPSTREAM_RATE_LIMITED,
    ErrorCode.UPSTREAM_AUTH_FAILED,
    ErrorCode.UPSTREAM_INVALID_REQUEST,
    ErrorCode.UPSTREAM_UNAVAILABLE,
    ErrorCode.TASK_TIMEOUT,
    ErrorCode.BUDGET_EXCEEDED,
    ErrorCode.MODEL_INVALID_OUTPUT,
    ErrorCode.QUOTE_MISMATCH,
})

# Terminal mapping reproduced from 术语表「4. 错误码」.
_TERMINAL_STATUS: dict[ErrorCode, TaskStatus] = {
    **{code: TaskStatus.BLOCKED for code in BLOCKED_CODES},
    **{code: TaskStatus.FAILED for code in FAILED_CODES},
    ErrorCode.RETRIEVAL_EMPTY: TaskStatus.COMPLETED,
}


def terminal_status(error_code: ErrorCode | None) -> TaskStatus:
    """Map a stopping error code to its documented terminal task status.

    ``None`` is an unclassified execution failure and stays FAILED, matching the
    glossary rule that an unknown error is not forced into a nearby code.
    """

    if error_code is None:
        return TaskStatus.FAILED
    return _TERMINAL_STATUS.get(error_code, TaskStatus.FAILED)


def blocked_label() -> ResultLabel:
    """The compatible label kept for every BLOCKED task."""

    return ResultLabel.SOURCE_UNVERIFIABLE


@dataclass
class BudgetState:
    """Local request/round counters checked before each dispatch.

    Attempt counting is owned by the gateway metadata; this state tracks the
    logical requests and supplemental rounds the workflow has dispatched.
    """

    limits: Limits = field(default_factory=default_limits)
    main_requests_used: int = 0
    repair_requests_used: int = 0
    supplemental_rounds_used: int = 0

    def can_dispatch_main(self) -> bool:
        return self.main_requests_used < self.limits.main_requests

    def can_dispatch_repair(self) -> bool:
        return self.repair_requests_used < self.limits.repair_requests

    def can_dispatch_supplemental(self) -> bool:
        return self.supplemental_rounds_used < self.limits.supplemental_rounds

    def take_main(self) -> None:
        self.main_requests_used += 1

    def take_repair(self) -> None:
        self.repair_requests_used += 1

    def take_supplemental(self) -> None:
        self.supplemental_rounds_used += 1


def criteria_snapshot() -> dict[str, object]:
    """The retrievable, immutable criteria JSON snapshot named by the glossary.

    It records the evidence threshold, the four academic labels with their
    source/execution display conditions, the error-code to terminal mapping, the
    action legality and budget order, and the text/quote comparison rules.
    """

    return {
        "version": CRITERIA_VERSION,
        "evidence_threshold": {
            "deterministic_checks": [
                "source_identity",
                "version",
                "licence",
                "quote_exact_substring_of_frozen_paragraph",
                "result_structure_and_evidence_references",
            ],
            "published_validation": "pass",
            "insufficient_evidence_may_have_no_quote": True,
            "definitive_labels_require_quote": True,
            "semantic_quality_checked_by": "evaluation",
        },
        "labels": {
            "支持": {"status": "COMPLETED", "requires": "原文在对应对象、条件和范围下支持论断"},
            "部分支持": {"status": "COMPLETED", "requires": "支持一部分，但数量、对象、因果性或范围有重要差异"},
            "相矛盾": {"status": "COMPLETED", "requires": "对应条件下有明确相反证据，不能由未检索到支持推导"},
            "证据不足": {"status": "COMPLETED", "requires": "来源可处理且有界检索已完成，仍缺少可核查片段"},
            "无法核验来源": {"status": "BLOCKED", "requires": "来源身份、可用范围、许可或内容完整性阻断"},
            "已取消": {"status": "CANCELLED", "requires": "作者取消；不是学术标签"},
            "运行中断": {"status": "INTERRUPTED", "requires": "进程重启时遗留的无取消标记 RUNNING；不是学术标签"},
        },
        "error_terminal_status": {code.value: status.value for code, status in _TERMINAL_STATUS.items()},
        "error_classification": {
            "source_block": sorted(code.value for code in BLOCKED_SOURCE_CODES),
            "processing_block": sorted(code.value for code in BLOCKED_PROCESSING_CODES),
            "execution_failure": sorted(code.value for code in FAILED_CODES),
        },
        "action_rules": {
            "request_1": "非空 queries 字符串数组",
            "request_2": "action=final + 最终判断，或 action=retrieve + queries 和 neighbor_paragraph_ids",
            "request_3": "仅 final",
            "supplemental_rounds": 1,
            "global_output_repair": 1,
            "main_requests": 3,
            "attempts_per_request": 2,
            "check_order": ["cancel_or_deadline", "response_structure_and_action", "remaining_budget", "dispatch"],
            "first_empty_retrieval_must_request_supplement": True,
        },
        "text_rules": {
            "whitespace": "段内 Unicode 空白连续串变成一个 U+0020 并去除段首尾空白",
            "frozen_reference": "保存冻结段落文本作为逐字校验基准",
            "quote": "精确子串，不 trim，不模糊归一化",
            "span": "Unicode 码点半开区间；重复匹配保存全部区间",
            "paragraph_id": "p:<source-key>:<version-hash>:<parser-version>:<ordinal>",
            "forbidden_normalization": ["case", "quotes", "hyphens", "unicode_normal_form"],
        },
    }


def criteria_reference(implementation_revision: str) -> dict[str, str]:
    """A CriteriaReference-shaped mapping that points at the criteria snapshot."""

    snapshot = criteria_snapshot()
    digest = digest_of(snapshot)
    return {
        "version": CRITERIA_VERSION,
        "digest": digest,
        "snapshot_ref": f"criteria:sha256:{digest}",
        "implementation_revision": implementation_revision,
    }
