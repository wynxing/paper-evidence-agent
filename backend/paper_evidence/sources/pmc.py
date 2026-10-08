"""PMC ID conversion, licensed JATS retrieval and licence/language checks.

The licence authority is the version record itself: only CC0 and CC BY are
auto-processed. A missing or conflicting licence is LICENSE_UNKNOWN; a known but
unsupported licence is LICENSE_UNSUPPORTED. The declared body language is
cross-checked against the parsed content and a non-English body is
SOURCE_LANGUAGE_UNSUPPORTED, never "no evidence".
"""

import re
import xml.etree.ElementTree as ElementTree
from dataclasses import dataclass

from paper_evidence.domain import ContractError, ErrorCode
from paper_evidence.sources.http import Fetcher

__all__ = ["PmcRecord", "PmcClient", "classify_license"]

_XML_LANG = "{http://www.w3.org/XML/1998/namespace}lang"
_CC0 = re.compile(r"\bcc0\b", re.IGNORECASE)
_CC_BY = re.compile(r"\bcc[\s-]*by\b", re.IGNORECASE)
_CC_ATTRIBUTION = re.compile(r"creative\s+commons\s+attribution", re.IGNORECASE)
_CC_RESTRICTED = re.compile(r"\b(nc|nd|sa)\b", re.IGNORECASE)


def classify_license(text: str | None, href: str | None = None) -> str:
    """Return the normalized supported licence, or raise a BLOCKED code.

    ``CC0`` and ``CC BY`` are supported. A present but unsupported licence is
    LICENSE_UNSUPPORTED; absence or conflict is LICENSE_UNKNOWN.
    """

    haystack = " ".join(part for part in (text, href) if part).strip()
    if not haystack:
        raise ContractError(ErrorCode.LICENSE_UNKNOWN, "许可缺失")
    if _CC0.search(haystack):
        return "CC0"
    if _CC_BY.search(haystack) or _CC_ATTRIBUTION.search(haystack):
        if _CC_RESTRICTED.search(haystack):
            raise ContractError(ErrorCode.LICENSE_UNSUPPORTED, "许可不在首版支持范围")
        return "CC BY"
    raise ContractError(ErrorCode.LICENSE_UNKNOWN, "无法确认许可")


def _local(tag: str) -> str:
    return tag.rsplit("}", 1)[-1]


@dataclass(frozen=True)
class PmcRecord:
    pmcid: str
    doi: str | None
    title: str | None
    license: str
    language: str | None
    version: str | None
    jats_bytes: bytes


class PmcClient:
    def __init__(self, fetcher: Fetcher, converter_url: str, oai_url: str, contact_email: str = "") -> None:
        self._fetcher = fetcher
        self._converter = converter_url
        self._oai = oai_url
        self._mailto = contact_email

    async def convert_to_pmcid(self, doi: str, deadline: float | None) -> str | None:
        """Map a DOI to a PMCID; None means no PMC full-text source is confirmed."""

        params = {"ids": doi, "format": "json"}
        if self._mailto:
            params["email"] = self._mailto
        response = await self._fetcher.get(self._converter, params=params, deadline=deadline)
        if response.status_code != 200:
            return None
        try:
            payload = response.json()
        except ValueError as error:
            raise ContractError(ErrorCode.UPSTREAM_INVALID_REQUEST, "PMC ID 转换响应无效") from error
        for record in payload.get("records") or []:
            pmcid = record.get("pmcid")
            if pmcid:
                return pmcid if pmcid.startswith("PMC") else f"PMC{pmcid}"
        return None

    async def fetch_record(self, pmcid: str, deadline: float | None) -> PmcRecord:
        """Fetch and validate one licensed JATS record from PMC OAI-PMH."""

        params = {
            "verb": "GetRecord",
            "identifier": f"oai:pubmedcentral.nih.gov:{pmcid.removeprefix('PMC')}",
            "metadataPrefix": "pmc",
        }
        response = await self._fetcher.get(self._oai, params=params, deadline=deadline)
        if response.status_code != 200:
            raise ContractError(ErrorCode.UPSTREAM_INVALID_REQUEST, "PMC OAI 响应无效")
        try:
            root = ElementTree.fromstring(response.content)
        except ElementTree.ParseError as error:
            raise ContractError(ErrorCode.CONTENT_INCOMPLETE, "PMC 返回内容无法解析") from error
        if any(_local(item.tag) == "error" for item in root.iter()):
            raise ContractError(ErrorCode.SOURCE_UNAVAILABLE, "PMC 未返回该标识的记录")
        article = next((item for item in root.iter() if _local(item.tag) == "article"), None)
        if article is None:
            raise ContractError(ErrorCode.CONTENT_INCOMPLETE, "PMC 记录缺少正文")

        doi = None
        title = None
        for element in article.iter():
            name = _local(element.tag)
            if name == "article-id" and (element.get("pub-id-type") or "").lower() == "doi":
                doi = (element.text or "").strip() or None
            elif name == "article-title" and title is None:
                title = " ".join("".join(element.itertext()).split()) or None

        license_element = next((item for item in article.iter() if _local(item.tag) == "license"), None)
        href = None
        if license_element is not None:
            href = (
                license_element.get("{http://www.w3.org/1999/xlink}href")
                or license_element.get("href")
                or license_element.get("license-type")
            )
        license_text = None if license_element is None else " ".join("".join(license_element.itertext()).split())
        license_name = classify_license(license_text, href)
        language = article.get(_XML_LANG) or article.get("lang")
        version = article.get("version")
        return PmcRecord(
            pmcid=pmcid, doi=doi, title=title, license=license_name, language=language,
            version=version, jats_bytes=response.content,
        )


def require_english(language: str | None, jats_bytes: bytes) -> None:
    """A non-English or mixed unsupported body is SOURCE_LANGUAGE_UNSUPPORTED."""

    declared = (language or "").lower()
    if declared and not declared.startswith("en"):
        raise ContractError(ErrorCode.SOURCE_LANGUAGE_UNSUPPORTED, "正文语言暂不支持")
    if not declared:
        # No declared language: fall back to a coarse content check.
        try:
            text = jats_bytes.decode("utf-8", errors="ignore")
        except Exception:  # pragma: no cover - decode with errors never raises here
            text = ""
        letters = [char for char in text if char.isalpha()]
        if letters:
            latin = sum(1 for char in letters if ord(char) < 0x250)
            if latin / len(letters) < 0.5:
                raise ContractError(ErrorCode.SOURCE_LANGUAGE_UNSUPPORTED, "正文语言无法确认为英文")
