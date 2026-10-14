"""In-process values used by module interfaces; no I/O or state transitions."""

from dataclasses import dataclass

from .contracts import ModelCall, SourceRecord


@dataclass(frozen=True)
class TaskInput:
    id: str
    claim: str
    doi: str
    config_digest: str
    authorized_recipients: tuple[str, ...]
    previous_id: str | None = None


@dataclass(frozen=True)
class SourceSnapshot:
    source_id: str
    metadata: SourceRecord
    jats_bytes: bytes
    # OpenAlex open-location hints kept locally only; they are not the frozen
    # access URL and never enter the diagnostic packet.
    open_locations: tuple[str, ...] = ()


@dataclass(frozen=True)
class Paragraph:
    paragraph_id: str
    source_id: str
    section: str
    # 该段在冻结解析里的正文序号，从 1 开始（术语表「文本与定位契约」）。它与
    # ``paragraph_id`` 尾段的数字是同一个值：id 由本字段拼出，存储列也按它写入。
    # 邻段展开按它做 ±1，读取方（如 evidence-context 的调用者）靠它判断两段是否
    # 原文相邻，不能用列表先后代替。
    ordinal: int
    text: str
    paragraph_hash: str
    source_url: str
    native_jats_id: str | None = None


@dataclass(frozen=True)
class ModelReply:
    text: str
    call: ModelCall
