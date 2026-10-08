"""Source connectors: DOI identity order, licence/language gating and status maps.

These use a mock transport, so they verify the connector logic and the documented
error mapping without any real upstream call. Real Crossref/PMC/OpenAlex
connectivity is not covered here.
"""

import asyncio
import hashlib

import httpx
import pytest

from paper_evidence.domain import ContractError, ErrorCode
from paper_evidence.sources.crossref import CrossrefClient, DoiResolver
from paper_evidence.sources.doi import is_valid_doi, normalize_doi, require_valid_doi
from paper_evidence.sources.http import Fetcher, classify_status
from paper_evidence.sources.openalex import OpenAlexClient
from paper_evidence.sources.pmc import PmcClient, classify_license
from paper_evidence.sources.service import SourceService

DOI = "10.1000/xyz"

JATS = b"""<?xml version="1.0" encoding="UTF-8"?>
<article xml:lang="en">
 <front><article-meta>
   <article-id pub-id-type="doi">10.1000/xyz</article-id>
   <title-group><article-title>Demo study</article-title></title-group>
   <permissions><license license-type="cc-by">CC BY 4.0</license></permissions>
 </article-meta></front>
 <body><sec><title>Results</title><p>The treatment reduced mortality.</p></sec></body>
</article>
"""


def build(handler) -> SourceService:
    client = httpx.AsyncClient(transport=httpx.MockTransport(handler))
    fetcher = Fetcher(client, 15, "test-agent")
    return SourceService(
        CrossrefClient(fetcher, "https://crossref.test"),
        DoiResolver(fetcher, "https://doi.test"),
        PmcClient(fetcher, "https://pmc.test/idconv", "https://pmc.test/oai"),
        OpenAlexClient(fetcher, "https://openalex.test"),
    )


def run(service, doi=DOI, deadline=None):
    import time

    return asyncio.run(service.resolve(doi) if deadline is None else service.fetch(doi, deadline))


# ------------------------------------------------------------------------ doi


def test_doi_normalization_and_validation():
    assert normalize_doi("https://doi.org/10.1000/XYZ") == "10.1000/xyz"
    assert is_valid_doi("10.1000/xyz") and not is_valid_doi("doi:not-a-doi")
    with pytest.raises(ContractError) as raised:
        require_valid_doi("nope")
    assert raised.value.error_code is ErrorCode.DOI_INVALID


def test_status_classification_matches_the_documented_upstream_codes():
    assert classify_status(401) is ErrorCode.UPSTREAM_AUTH_FAILED
    assert classify_status(429) is ErrorCode.UPSTREAM_RATE_LIMITED
    assert classify_status(503) is ErrorCode.UPSTREAM_UNAVAILABLE
    assert classify_status(400) is ErrorCode.UPSTREAM_INVALID_REQUEST


# -------------------------------------------------------------------- resolve


def crossref_metadata_handler(request: httpx.Request) -> httpx.Response:
    host = request.url.host
    if host == "crossref.test":
        return httpx.Response(200, json={"message": {
            "title": ["Demo study"], "author": [{"given": "Ada", "family": "Lovelace"}],
            "published-print": {"date-parts": [[2026]]},
        }})
    if host == "openalex.test":
        return httpx.Response(200, json={"open_access": {"is_oa": True}, "locations": []})
    return httpx.Response(404)


def test_resolve_returns_a_read_only_preview():
    preview = run(build(crossref_metadata_handler))
    assert preview.doi == DOI and preview.title == "Demo study"
    assert preview.authors == ["Ada Lovelace"] and preview.year == 2026


def test_crossref_404_with_agency_confirmed_is_metadata_not_found():
    def handler(request):
        if request.url.host == "crossref.test":
            if request.url.path.endswith("/agency"):
                return httpx.Response(200, json={"message": {"agency": {"id": "crossref"}}})
            return httpx.Response(404)
        return httpx.Response(404)

    with pytest.raises(ContractError) as raised:
        run(build(handler))
    assert raised.value.error_code is ErrorCode.METADATA_NOT_FOUND


def test_crossref_404_with_other_agency_is_unsupported():
    def handler(request):
        if request.url.host == "crossref.test" and request.url.path.endswith("/agency"):
            return httpx.Response(200, json={"message": {"agency": {"id": "datacite"}}})
        return httpx.Response(404)

    with pytest.raises(ContractError) as raised:
        run(build(handler))
    assert raised.value.error_code is ErrorCode.REGISTRATION_AGENCY_UNSUPPORTED


def test_agency_missing_and_resolver_miss_is_doi_unresolvable():
    def handler(request):
        if request.url.host == "crossref.test":
            return httpx.Response(404)
        if request.url.host == "doi.test":
            return httpx.Response(404)
        return httpx.Response(404)

    with pytest.raises(ContractError) as raised:
        run(build(handler))
    assert raised.value.error_code is ErrorCode.DOI_UNRESOLVABLE


def test_resolver_redirect_without_agency_record_is_metadata_not_found():
    def handler(request):
        if request.url.host == "doi.test":
            return httpx.Response(302, headers={"location": "https://publisher.example/x"})
        return httpx.Response(404)

    with pytest.raises(ContractError) as raised:
        run(build(handler))
    assert raised.value.error_code is ErrorCode.METADATA_NOT_FOUND


# ---------------------------------------------------------------------- fetch


def fetch_handler(jats=JATS, pmcid="PMC123", doi_in_article="10.1000/xyz"):
    def handler(request):
        host = request.url.host
        if host == "crossref.test":
            return httpx.Response(200, json={"message": {"title": ["Demo study"]}})
        if host == "pmc.test" and request.url.path == "/idconv":
            return httpx.Response(200, json={"records": [{"pmcid": pmcid}] if pmcid else []})
        if host == "pmc.test" and request.url.path == "/oai":
            body = jats.replace(b"10.1000/xyz", doi_in_article.encode())
            return httpx.Response(200, content=body)
        if host == "openalex.test":
            return httpx.Response(200, json={"open_access": {"is_oa": True},
                                             "locations": [{"landing_page_url": "https://open.example/x"}]})
        return httpx.Response(404)

    return handler


def test_fetch_returns_a_licensed_snapshot_with_a_version_hash():
    import time

    snapshot = run(build(fetch_handler()), deadline=time.monotonic() + 60)
    assert snapshot.metadata.license == "CC BY"
    assert snapshot.metadata.pmcid == "PMC123"
    assert snapshot.metadata.access_url == "https://open.example/x"
    assert snapshot.metadata.version_hash == hashlib.sha256(JATS).hexdigest()
    assert snapshot.source_id == f"PMC123:{snapshot.metadata.version_hash}"


def test_doi_mismatch_between_crossref_and_pmc_is_blocked():
    import time

    with pytest.raises(ContractError) as raised:
        run(build(fetch_handler(doi_in_article="10.1000/other")), deadline=time.monotonic() + 60)
    assert raised.value.error_code is ErrorCode.SOURCE_MISMATCH


def test_missing_pmc_source_is_source_unavailable():
    import time

    with pytest.raises(ContractError) as raised:
        run(build(fetch_handler(pmcid="")), deadline=time.monotonic() + 60)
    assert raised.value.error_code is ErrorCode.SOURCE_UNAVAILABLE


def test_non_english_body_is_language_unsupported():
    import time

    chinese = JATS.replace(b'xml:lang="en"', b'xml:lang="zh"')
    with pytest.raises(ContractError) as raised:
        run(build(fetch_handler(jats=chinese)), deadline=time.monotonic() + 60)
    assert raised.value.error_code is ErrorCode.SOURCE_LANGUAGE_UNSUPPORTED


@pytest.mark.parametrize("license_text,expected", [
    ("This article is distributed under CC BY 4.0", "CC BY"),
    ("Creative Commons Attribution 4.0", "CC BY"),
    ("CC0 1.0 Universal", "CC0"),
])
def test_supported_licenses_are_accepted(license_text, expected):
    assert classify_license(license_text) == expected


@pytest.mark.parametrize("license_text,code", [
    ("CC BY-NC 4.0", ErrorCode.LICENSE_UNSUPPORTED),
    ("All rights reserved", ErrorCode.LICENSE_UNKNOWN),
    ("", ErrorCode.LICENSE_UNKNOWN),
])
def test_unsupported_or_unknown_licenses_are_blocked(license_text, code):
    with pytest.raises(ContractError) as raised:
        classify_license(license_text)
    assert raised.value.error_code is code
