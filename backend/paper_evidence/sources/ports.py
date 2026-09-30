"""Read-only source boundary. No HTTP connector is implemented."""

from typing import Protocol

from paper_evidence.domain.contracts import SourcePreview
from paper_evidence.domain.records import SourceSnapshot


class SourceResolver(Protocol):
    async def resolve(self, doi: str) -> SourcePreview: ...


class FullTextSource(Protocol):
    async def fetch(self, doi: str, deadline: float) -> SourceSnapshot: ...
