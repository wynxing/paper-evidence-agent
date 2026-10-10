"""Retrieval is bound to a frozen source; no index or query is executed."""

from typing import Protocol

from paper_evidence.domain.records import Paragraph


class EvidenceRetriever(Protocol):
    def search(self, source_id: str, queries: list[str]) -> list[Paragraph]:
        """Search the frozen source. A database or index error raises ContractError(RETRIEVAL_FAILED)."""
        ...

    def read_neighbors(self, source_id: str, paragraph_ids: list[str]) -> list[Paragraph]:
        """Read the given paragraphs and their immediate ordinal±1 neighbours.

        Only the frozen source is read; unknown or foreign ids resolve to
        nothing instead of leaking paragraphs across sources.
        """
        ...
