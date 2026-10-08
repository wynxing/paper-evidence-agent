"""Composite read-only source service.

Wires the Crossref, DOI-resolver, PMC and OpenAlex connectors into the
``SourceResolver`` and ``FullTextSource`` ports. Identity is checked in the
documented order: DOI normalization and Crossref metadata, then the PMC
DOI/PMCID mapping, then the PMC version record, then the per-version licence.
OpenAlex only supplies open-location hints.
"""

from datetime import datetime, timezone
from hashlib import sha256

from paper_evidence.domain import ContractError, ErrorCode
from paper_evidence.domain.contracts import SourcePreview, SourceRecord
from paper_evidence.domain.records import SourceSnapshot
from paper_evidence.sources.crossref import CrossrefClient, DoiResolver
from paper_evidence.sources.doi import require_valid_doi
from paper_evidence.sources.openalex import OpenAlexClient
from paper_evidence.sources.pmc import PmcClient, require_english

__all__ = ["SourceService"]


def _authors(message: dict) -> list[str]:
    names: list[str] = []
    for author in message.get("author") or []:
        given = author.get("given")
        family = author.get("family")
        if given and family:
            names.append(f"{given} {family}")
        elif family or author.get("name"):
            names.append(family or author["name"])
    return names


def _year(message: dict) -> int | None:
    for key in ("published-print", "published-online", "published", "issued"):
        parts = (message.get(key) or {}).get("date-parts")
        if parts and parts[0] and isinstance(parts[0][0], int):
            return parts[0][0]
    return None


def _title(message: dict) -> str:
    titles = message.get("title") or []
    return " ".join(titles[0].split()) if titles else ""


class SourceService:
    """Implements SourceResolver.resolve and FullTextSource.fetch."""

    def __init__(
        self,
        crossref: CrossrefClient,
        doi_resolver: DoiResolver,
        pmc: PmcClient,
        openalex: OpenAlexClient,
    ) -> None:
        self._crossref = crossref
        self._doi_resolver = doi_resolver
        self._pmc = pmc
        self._openalex = openalex

    async def resolve(self, doi: str) -> SourcePreview:
        normalized = require_valid_doi(doi)
        message = await self._crossref.metadata(normalized, None)
        if message is None:
            agency = await self._crossref.agency(normalized, None)
            if agency and agency.lower() != "crossref":
                raise ContractError(ErrorCode.REGISTRATION_AGENCY_UNSUPPORTED, "注册机构不在首版支持范围")
            if agency is None and not await self._doi_resolver.resolvable(normalized, None):
                raise ContractError(ErrorCode.DOI_UNRESOLVABLE, "DOI 官方解析服务未找到")
            raise ContractError(ErrorCode.METADATA_NOT_FOUND, "Crossref 未收录该文献")
        return SourcePreview(doi=normalized, title=_title(message), authors=_authors(message), year=_year(message))

    async def fetch(self, doi: str, deadline: float) -> SourceSnapshot:
        normalized = require_valid_doi(doi)
        message = await self._crossref.metadata(normalized, deadline)
        if message is None:
            raise ContractError(ErrorCode.METADATA_NOT_FOUND, "Crossref 未收录该文献")
        pmcid = await self._pmc.convert_to_pmcid(normalized, deadline)
        if not pmcid:
            raise ContractError(ErrorCode.SOURCE_UNAVAILABLE, "未确认可用的 PMC 全文来源")
        record = await self._pmc.fetch_record(pmcid, deadline)
        if record.doi and record.doi.lower() != normalized.lower():
            raise ContractError(ErrorCode.SOURCE_MISMATCH, "DOI 与 PMC 版本身份冲突")
        require_english(record.language, record.jats_bytes)

        hint = await self._openalex.open_access_hint(normalized, deadline)
        access_url = next(
            (item["landing_page_url"] for item in hint.get("locations", []) if item.get("landing_page_url")),
            f"https://pmc.ncbi.nlm.nih.gov/articles/{pmcid}/",
        )
        version_hash = sha256(record.jats_bytes).hexdigest()
        source = SourceRecord(
            title=_title(message) or record.title,
            doi=normalized,
            pmcid=pmcid,
            license=record.license,
            version=record.version or "1",
            access_url=access_url,
            retrieved_at=datetime.now(timezone.utc).isoformat(),
            version_hash=version_hash,
        )
        return SourceSnapshot(source_id=f"{pmcid}:{version_hash}", metadata=source, jats_bytes=record.jats_bytes)
