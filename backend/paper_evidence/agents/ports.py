"""Paper-agent prompt boundary. This package does not call models or sources."""

from typing import Protocol

from paper_evidence.domain.contracts import SourcePreview
from paper_evidence.domain.records import Paragraph


class PaperPromptBuilder(Protocol):
    def query_generation(self, claim: str, source: SourcePreview) -> str: ...

    def decision(self, claim: str, candidates: list[Paragraph], final_only: bool) -> str: ...
