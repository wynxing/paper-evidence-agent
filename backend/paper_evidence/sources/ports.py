"""Read-only source boundary. No HTTP connector is implemented."""

from typing import Protocol

from paper_evidence.domain.contracts import SourcePreview
from paper_evidence.domain.records import SourceSnapshot


class SourceResolver(Protocol):
    async def resolve(self, doi: str, deadline: float | None = None) -> SourcePreview:
        """Return a read-only bibliographic preview.

        deadline is an absolute time.monotonic() timestamp or None for a
        standalone preview; the task worker passes its remaining budget so source
        requests stay inside 架构设计「取消与截止时间」. Failures raise
        ContractError. Preview codes are DOI_UNRESOLVABLE, METADATA_NOT_FOUND,
        REGISTRATION_AGENCY_UNSUPPORTED, and the upstream codes for HTTP 502
        (UPSTREAM_AUTH_FAILED, UPSTREAM_INVALID_REQUEST), 503
        (UPSTREAM_RATE_LIMITED, UPSTREAM_UNAVAILABLE), and 504
        (UPSTREAM_TIMEOUT). DOI_INVALID is rejected by the API before resolve.
        """
        ...


class FullTextSource(Protocol):
    async def fetch(self, doi: str, deadline: float) -> SourceSnapshot:
        """Fetch one licensed full text.

        deadline is an absolute time.monotonic() timestamp. A single request
        that times out while task budget remains raises
        ContractError(UPSTREAM_TIMEOUT). Other codes are SOURCE_MISMATCH,
        SOURCE_UNAVAILABLE, LICENSE_UNKNOWN, LICENSE_UNSUPPORTED,
        SOURCE_LANGUAGE_UNSUPPORTED, CONTENT_INCOMPLETE, and the remaining
        UPSTREAM_* codes for source HTTP failures.
        """
        ...
