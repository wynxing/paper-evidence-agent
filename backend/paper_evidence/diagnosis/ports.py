"""Diagnostic projection boundary; no packet generation or export is performed."""

from typing import Protocol

from paper_evidence.domain.contracts import DiagnosticPacket


class DiagnosticProjector(Protocol):
    def redacted(self, task_id: str) -> DiagnosticPacket: ...

    def consented(self, task_id: str, recipient: str) -> DiagnosticPacket: ...
