"""PMC ID conversion, licensed JATS retrieval and licence/language checks.

The licence authority is the version record itself: only CC0 and CC BY are
auto-processed. A missing or conflicting licence is LICENSE_UNKNOWN; a known but
unsupported licence is LICENSE_UNSUPPORTED. The declared body language is
cross-checked against the parsed content and a non-English body is
SOURCE_LANGUAGE_UNSUPPORTED, never "no evidence".

What ``fetch_record`` freezes is the ``<article>`` subtree of the OAI-PMH answer,
not the answer as a whole: the envelope carries a per-request ``<responseDate>``,
so a digest over it would name the request instead of the version (Issue #67).
"""

import re
import xml.etree.ElementTree as ElementTree
from dataclasses import dataclass

from paper_evidence.domain import ContractError, ErrorCode
from paper_evidence.sources.http import Fetcher, classify_status

__all__ = ["PmcRecord", "PmcClient", "classify_license"]

_XML_LANG = "{http://www.w3.org/XML/1998/namespace}lang"
_CC0 = re.compile(r"\bcc0\b", re.IGNORECASE)
_CC_BY = re.compile(r"\bcc[\s-]*by\b", re.IGNORECASE)
_CC_ATTRIBUTION = re.compile(r"creative\s+commons\s+attribution", re.IGNORECASE)
_CC_RESTRICTED = re.compile(r"\b(nc|nd|sa)\b", re.IGNORECASE)

#: ``pmc`` serves the full JATS record, ``<body>`` included. A judgement may only
#: rest on it. Verified against live PMC (2026-10-12): three CC BY records all
#: returned a populated ``<body>`` under this prefix.
_FULL_TEXT_PREFIX = "pmc"
#: ``pmc_fm`` is PMC **F**ront **M**atter: title, abstract and permissions, and
#: **no ``<body>`` at all** (three of three live records had ``<body>`` count 0).
#: It is a fallback for records PMC will not serve as full text, never the first
#: choice — judging a claim on an abstract alone is forbidden by 产品需求「不测」:
#: 「用摘要代替全文来声称全文没有相关证据」.
_FRONT_MATTER_PREFIX = "pmc_fm"
#: The OAI-PMH error PMC returns when a record is outside the Open Access subset.
_CANNOT_DISSEMINATE = "cannotDisseminateFormat"

#: What the frozen record actually contains, recorded rather than inferred.
#:
#: ``pmc_fm`` is a degradation, and until Issue #60 the only trace of it was the
#: ``<request metadataPrefix>`` echoed inside the stored bytes — a BLOB nothing reads.
#: Nothing downstream could tell a body from an abstract, so the "judge on the
#: article, never on the abstract" rule had no reliable predicate to enforce. The
#: values are part of the public ``SourceRecord`` contract, so they are written out
#: literally and may not drift.
RETRIEVAL_FULL_TEXT = "full_text"
RETRIEVAL_FRONT_MATTER = "front_matter"

#: The ``<article>`` start tag. The lookahead keeps ``<article-meta>``,
#: ``<article-id>`` and ``<article-title>`` out of the match — they are children
#: of the element being located, never a second record.
_ARTICLE_START = re.compile(rb"<article(?=[\s/>])")
_ARTICLE_END = b"</article>"


def _article_bytes(response: bytes) -> bytes:
    """The ``<article>`` subtree of an OAI-PMH response, byte-exact.

    Sliced out of the response bytes instead of re-serialised. Two reasons:
    ``version_hash`` is defined over the JATS bytes the upstream served
    (术语表「文本与定位契约」), and re-serialisation rewrites them (namespace
    prefixes, attribute quoting, entity forms); and a public digest that already
    describes a stored source must keep describing the same bytes.

    The slice excludes the XML declaration and the whole OAI envelope — crucially
    the per-request ``<responseDate>``, which is why hashing the envelope gave a
    different ``version_hash``, ``source_id`` and ``paragraph_id`` on every fetch
    (Issue #67). The ``<article>`` element declares the namespaces it uses, so the
    slice parses on its own.
    """

    start = _ARTICLE_START.search(response)
    end = response.rfind(_ARTICLE_END)
    if start is None or end < start.start():
        raise ContractError(ErrorCode.CONTENT_INCOMPLETE, "PMC 记录缺少正文")
    return response[start.start():end + len(_ARTICLE_END)]


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


def _oai_error_code(root: ElementTree.Element) -> str | None:
    """The OAI-PMH ``error`` code of a GetRecord response, or ``None``.

    The code matters, not just its presence: ``cannotDisseminateFormat`` means
    "this record has no full text to serve" and is the one case worth retrying
    under a different ``metadataPrefix``; everything else is a real failure.
    """

    for item in root.iter():
        if _local(item.tag) == "error":
            return (item.get("code") or "").strip() or "error"
    return None


@dataclass(frozen=True)
class PmcRecord:
    pmcid: str
    doi: str | None
    title: str | None
    license: str
    language: str | None
    version: str | None
    #: The ``<article>`` subtree of the OAI-PMH response — the JATS record itself,
    #: without the XML declaration or the envelope (``_article_bytes``). Callers may
    #: hash it as the version-identifying bytes; hashing the envelope would make the
    #: digest change on every fetch (Issue #67).
    jats_bytes: bytes
    #: ``full_text`` or ``front_matter`` — what ``jats_bytes`` actually contains.
    #: ``front_matter`` means title + abstract + permissions and no ``<body>``, so a
    #: judgement must not rest on it as if it were the article (Issue #60).
    retrieval_form: str


class PmcClient:
    def __init__(self, fetcher: Fetcher, converter_url: str, oai_url: str, contact_email: str = "") -> None:
        self._fetcher = fetcher
        self._converter = converter_url
        self._oai = oai_url
        self._mailto = contact_email

    async def convert_to_pmcid(self, doi: str, deadline: float | None) -> str | None:
        """Map a DOI to a PMCID; None means the official lookup confirmed no record.

        Only a 200 whose payload has no pmcid means "no PMC full text"; any other
        status is an upstream failure, because SOURCE_UNAVAILABLE must not absorb
        authentication, parameter or protocol errors (术语表「4. 错误码」).
        """

        params = {"ids": doi, "format": "json"}
        if self._mailto:
            params["email"] = self._mailto
        response = await self._fetcher.get(self._converter, params=params, deadline=deadline)
        if response.status_code != 200:
            raise ContractError(classify_status(response.status_code), "PMC ID 转换响应异常")
        try:
            payload = response.json()
        except ValueError as error:
            raise ContractError(ErrorCode.UPSTREAM_INVALID_REQUEST, "PMC ID 转换响应无效") from error
        records = payload.get("records")
        if not isinstance(records, list):
            raise ContractError(ErrorCode.UPSTREAM_INVALID_REQUEST, "PMC ID 转换响应缺少 records")
        for record in records:
            pmcid = record.get("pmcid")
            if pmcid:
                return pmcid if pmcid.startswith("PMC") else f"PMC{pmcid}"
        return None

    async def _get_record(self, pmcid: str, prefix: str, deadline: float | None):
        """One GetRecord call, returned as ``(root, raw_bytes)``."""

        params = {
            "verb": "GetRecord",
            "identifier": f"oai:pubmedcentral.nih.gov:{pmcid.removeprefix('PMC')}",
            "metadataPrefix": prefix,
        }
        # The configured OAI host answers with a 301 to its API path; without
        # following it the redirect surfaces as an upstream parameter error.
        response = await self._fetcher.get(
            self._oai, params=params, deadline=deadline, follow_redirects=True
        )
        if response.status_code != 200:
            raise ContractError(ErrorCode.UPSTREAM_INVALID_REQUEST, "PMC OAI 响应无效")
        try:
            root = ElementTree.fromstring(response.content)
        except ElementTree.ParseError as error:
            raise ContractError(ErrorCode.CONTENT_INCOMPLETE, "PMC 返回内容无法解析") from error
        return root, response.content

    async def fetch_record(self, pmcid: str, deadline: float | None) -> PmcRecord:
        """Fetch and validate one licensed JATS record from PMC OAI-PMH.

        Full text (``pmc``) is requested first, because that is the only form a
        judgement may rest on. PMC serves it for records in the Open Access
        subset; for the rest it answers ``cannotDisseminateFormat``, and only
        then does the client fall back to ``pmc_fm`` front matter. The fallback
        is a degradation, not an equivalent: it carries title, abstract and
        permissions but **no ``<body>``**, so the caller cannot read it as the
        article. Whether such a record should block instead of being judged on
        an abstract is a product decision, not one this connector can make.

        The returned ``jats_bytes`` is the ``<article>`` subtree, byte-exact
        (``_article_bytes``); the OAI envelope is deliberately not part of it.
        """

        retrieval_form = RETRIEVAL_FULL_TEXT
        root, content = await self._get_record(pmcid, _FULL_TEXT_PREFIX, deadline)
        if _oai_error_code(root) == _CANNOT_DISSEMINATE:
            retrieval_form = RETRIEVAL_FRONT_MATTER
            root, content = await self._get_record(pmcid, _FRONT_MATTER_PREFIX, deadline)
        if _oai_error_code(root) is not None:
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
        jats = _article_bytes(content)
        return PmcRecord(
            pmcid=pmcid, doi=doi, title=title, license=license_name, language=language,
            version=version, jats_bytes=jats,
            # Recorded from which request actually produced the bytes, not inferred
            # from the parsed sections: a short real article and a front-matter-only
            # record look alike once parsed, so `section` is not a predicate (Issue #60).
            retrieval_form=retrieval_form,
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
