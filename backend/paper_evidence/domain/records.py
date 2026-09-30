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


@dataclass(frozen=True)
class SourceSnapshot:
    source_id: str
    metadata: SourceRecord
    jats_bytes: bytes


@dataclass(frozen=True)
class Paragraph:
    paragraph_id: str
    source_id: str
    section: str
    text: str
    paragraph_hash: str
    source_url: str


@dataclass(frozen=True)
class ModelReply:
    text: str
    call: ModelCall
