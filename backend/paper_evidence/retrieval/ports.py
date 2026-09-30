"""Retrieval is bound to a frozen source; no index or query is executed."""

from typing import Protocol

from paper_evidence.domain.records import Paragraph


class EvidenceRetriever(Protocol):
    def search(self, source_id: str, queries: list[str]) -> list[Paragraph]: ...

    def read_neighbors(self, source_id: str, paragraph_ids: list[str]) -> list[Paragraph]: ...
