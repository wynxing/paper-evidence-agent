"""FTS5-backed retrieval bound to the task's frozen source.

The source id is bound by the workflow; the model only submits query phrases and
known paragraph ids from the current source. Any database or index fault surfaces
as RETRIEVAL_FAILED and is never turned into an empty result.
"""

from paper_evidence.domain import ContractError, ErrorCode
from paper_evidence.domain.records import Paragraph
from paper_evidence.retrieval.query import NoIndexableTerms, compile_match

__all__ = ["StoreRetriever"]


class StoreRetriever:
    """Retrieve candidate paragraphs from one frozen source."""

    def __init__(self, store, context_limit: int) -> None:
        self._store = store
        self._context_limit = context_limit

    def search(self, source_id: str, queries: list[str]) -> list[Paragraph]:
        try:
            match = compile_match(queries)
        except NoIndexableTerms as error:
            # A query with no indexable term is an output problem the workflow
            # repairs once; it is not RETRIEVAL_FAILED.
            raise ContractError(ErrorCode.MODEL_INVALID_OUTPUT, "queries 无可索引词项") from error
        return self._store.search(source_id, match, self._context_limit)

    def read_neighbors(self, source_id: str, paragraph_ids: list[str]) -> list[Paragraph]:
        """Read the given paragraphs plus their ordinal±1 neighbours.

        The query is source-scoped, so ids from another source resolve to
        nothing instead of leaking paragraphs across frozen sources.
        """

        return self._store.read_neighbors(source_id, paragraph_ids)
