"""OpenAlex open-location hints.

OpenAlex only suggests open locations, versions and licence clues. Its
"freely readable" field is never treated as permission to fetch and reuse full
text; licence authority stays with the PMC version record.
"""

from paper_evidence.domain import ContractError, ErrorCode
from paper_evidence.sources.http import Fetcher

__all__ = ["OpenAlexClient"]


class OpenAlexClient:
    def __init__(self, fetcher: Fetcher, base_url: str, contact_email: str = "") -> None:
        self._fetcher = fetcher
        self._base = base_url.rstrip("/")
        self._mailto = contact_email

    async def work(self, doi: str, deadline: float | None) -> dict | None:
        """Best-effort work record; upstream failure is a hint gap, not a verdict."""

        params = {"mailto": self._mailto} if self._mailto else {}
        try:
            response = await self._fetcher.get(f"{self._base}/works/doi:{doi}", params=params, deadline=deadline)
        except ContractError as error:
            if error.error_code in (ErrorCode.UPSTREAM_AUTH_FAILED, ErrorCode.UPSTREAM_INVALID_REQUEST):
                raise
            return None
        if response.status_code != 200:
            return None
        try:
            return response.json()
        except ValueError:
            return None

    async def open_access_hint(self, doi: str, deadline: float | None) -> dict:
        work = await self.work(doi, deadline)
        if not work:
            return {"is_oa": None, "locations": []}
        locations = [
            {"landing_page_url": item.get("landing_page_url"), "pdf_url": item.get("pdf_url"),
             "version": item.get("version")}
            for item in (work.get("locations") or [])[:5]
        ]
        return {"is_oa": (work.get("open_access") or {}).get("is_oa"), "locations": locations}
