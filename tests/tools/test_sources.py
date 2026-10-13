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

#: The shape PMC actually returns for ``metadataPrefix=pmc_fm``: front matter
#: (title, permissions, abstract) and **no ``<body>``**. Measured against live
#: PMC on 2026-10-12 — three of three records had a ``<body>`` count of 0.
FRONT_MATTER_JATS = b"""<?xml version="1.0" encoding="UTF-8"?>
<article xml:lang="en">
 <front><article-meta>
   <article-id pub-id-type="doi">10.1000/xyz</article-id>
   <title-group><article-title>Demo study</article-title></title-group>
   <abstract><p>The treatment reduced mortality.</p></abstract>
   <permissions><license license-type="cc-by">CC BY 4.0</license></permissions>
 </article-meta></front>
</article>
"""

#: The GetRecord error PMC answers for a record outside the Open Access subset.
CANNOT_DISSEMINATE = b"""<?xml version="1.0" encoding="UTF-8"?>
<OAI-PMH xmlns="http://www.openarchives.org/OAI/2.0/">
 <GetRecord>
  <error code="cannotDisseminateFormat">No full text available</error>
 </GetRecord>
</OAI-PMH>
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
    # access_url 必须指向实际冻结的 PMC 版本，而不是 OpenAlex 的 landing page。
    assert snapshot.metadata.access_url == "https://pmc.ncbi.nlm.nih.gov/articles/PMC123/"
    assert snapshot.open_locations == ("https://open.example/x",)
    assert snapshot.metadata.version_hash == hashlib.sha256(JATS).hexdigest()
    assert snapshot.source_id == f"PMC123:{snapshot.metadata.version_hash}"


@pytest.mark.parametrize("status,expected", [
    (401, ErrorCode.UPSTREAM_AUTH_FAILED),
    (403, ErrorCode.UPSTREAM_AUTH_FAILED),
    (400, ErrorCode.UPSTREAM_INVALID_REQUEST),
    (503, ErrorCode.UPSTREAM_UNAVAILABLE),
])
def test_pmc_id_conversion_upstream_errors_are_not_source_unavailable(status, expected):
    """只有 200 且无 pmcid 才是 SOURCE_UNAVAILABLE；认证/参数问题不能伪装成它。"""

    def handler(request):
        if request.url.host == "crossref.test":
            return httpx.Response(200, json={"message": {"title": ["Demo study"]}})
        if request.url.host == "pmc.test" and request.url.path == "/idconv":
            return httpx.Response(status, json={})
        return httpx.Response(404)

    import time

    with pytest.raises(ContractError) as raised:
        run(build(handler), deadline=time.monotonic() + 60)
    assert raised.value.error_code is expected


@pytest.mark.parametrize("status,expected", [
    (401, ErrorCode.UPSTREAM_AUTH_FAILED),
    (403, ErrorCode.UPSTREAM_AUTH_FAILED),
])
def test_crossref_auth_failure_is_not_an_invalid_request(status, expected):
    def handler(request):
        if request.url.host == "crossref.test":
            return httpx.Response(status, json={})
        return httpx.Response(404)

    with pytest.raises(ContractError) as raised:
        run(build(handler))
    assert raised.value.error_code is expected


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


# ------------------------------------------------- PMC OAI request contract
#
# The OAI call is the one upstream hop that a mock-only suite cannot validate by
# shape alone: its host, metadata prefix and redirect handling are all external
# facts that changed under us. These assertions pin the request the client makes
# so a silent regression surfaces here instead of as UPSTREAM_INVALID_REQUEST.


def test_default_pmc_oai_endpoint_is_the_canonical_api_path():
    """The legacy oai.cgi host now 301s; the default must target the API path."""

    from paper_evidence.config import Settings

    assert Settings.from_env().pmc_oai_url == "https://pmc.ncbi.nlm.nih.gov/api/oai/v1/mh/"


def test_pmc_oai_request_prefers_the_full_text_metadata_prefix():
    """正文必须用 ``pmc`` 取。

    此前这里断言的是 ``pmc_fm``，理由是「``pmc`` 会被 cannotDisseminateFormat
    拒绝」——与实测相反：``pmc_fm`` 只返回题录+摘要（``<body>`` 计数为 0），
    ``pmc`` 才带正文（3/3 样例）。
    """

    seen = []

    def handler(request):
        if request.url.host == "pmc.test" and request.url.path == "/oai":
            seen.append(dict(request.url.params))
            return httpx.Response(200, content=JATS)
        if request.url.host == "pmc.test" and request.url.path == "/idconv":
            return httpx.Response(200, json={"records": [{"pmcid": "PMC123"}]})
        return httpx.Response(200, json={"message": {"title": ["Demo study"]}})

    client = httpx.AsyncClient(transport=httpx.MockTransport(handler))
    pmc = PmcClient(Fetcher(client, 15, "test-agent"), "https://pmc.test/idconv", "https://pmc.test/oai")
    asyncio.run(pmc.fetch_record("PMC123", None))

    assert [call["metadataPrefix"] for call in seen] == ["pmc"], "不得用只含摘要的 pmc_fm 取正文"
    assert seen[0]["verb"] == "GetRecord"
    assert seen[0]["identifier"] == "oai:pubmedcentral.nih.gov:123"


def test_pmc_oai_falls_back_to_front_matter_only_after_cannot_disseminate():
    """只有 PMC 明确回 ``cannotDisseminateFormat`` 时才退到只含题录+摘要的 ``pmc_fm``。"""

    seen = []

    def handler(request):
        if request.url.host == "pmc.test" and request.url.path == "/oai":
            prefix = dict(request.url.params)["metadataPrefix"]
            seen.append(prefix)
            return httpx.Response(
                200, content=CANNOT_DISSEMINATE if prefix == "pmc" else FRONT_MATTER_JATS
            )
        if request.url.host == "pmc.test" and request.url.path == "/idconv":
            return httpx.Response(200, json={"records": [{"pmcid": "PMC123"}]})
        return httpx.Response(200, json={"message": {"title": ["Demo study"]}})

    client = httpx.AsyncClient(transport=httpx.MockTransport(handler))
    pmc = PmcClient(Fetcher(client, 15, "test-agent"), "https://pmc.test/idconv", "https://pmc.test/oai")
    record = asyncio.run(pmc.fetch_record("PMC123", None))

    assert seen == ["pmc", "pmc_fm"], "先取正文，被拒后才回落"
    assert record.pmcid == "PMC123"
    assert record.license == "CC BY"
    assert b"<body" not in record.jats_bytes, "回落拿到的只有题录+摘要，不含正文"


@pytest.mark.parametrize("code", ["idDoesNotExist", "badArgument"])
def test_pmc_oai_errors_other_than_cannot_disseminate_are_not_retried(code):
    """其它 OAI 错误照旧映射为 SOURCE_UNAVAILABLE，不做第二次请求。"""

    seen = []

    def handler(request):
        if request.url.host == "pmc.test" and request.url.path == "/oai":
            seen.append(dict(request.url.params)["metadataPrefix"])
            error = (
                b'<?xml version="1.0" encoding="UTF-8"?>'
                b'<OAI-PMH xmlns="http://www.openarchives.org/OAI/2.0/"><GetRecord>'
                b'<error code="' + code.encode() + b'">nope</error>'
                b"</GetRecord></OAI-PMH>"
            )
            return httpx.Response(200, content=error)
        if request.url.host == "pmc.test" and request.url.path == "/idconv":
            return httpx.Response(200, json={"records": [{"pmcid": "PMC123"}]})
        return httpx.Response(200, json={"message": {"title": ["Demo study"]}})

    client = httpx.AsyncClient(transport=httpx.MockTransport(handler))
    pmc = PmcClient(Fetcher(client, 15, "test-agent"), "https://pmc.test/idconv", "https://pmc.test/oai")
    with pytest.raises(ContractError) as raised:
        asyncio.run(pmc.fetch_record("PMC123", None))

    assert raised.value.error_code is ErrorCode.SOURCE_UNAVAILABLE
    assert seen == ["pmc"], "非 cannotDisseminateFormat 的错误不重试"


def test_pmc_oai_call_follows_redirects():
    """A 301 that is not followed is mapped to UPSTREAM_INVALID_REQUEST, not fetched."""

    def handler(request):
        if request.url.host == "pmc.test" and request.url.path == "/oai":
            return httpx.Response(301, headers={"Location": "https://pmc.test/oai-moved"})
        if request.url.host == "pmc.test" and request.url.path == "/oai-moved":
            return httpx.Response(200, content=JATS)
        return httpx.Response(404)

    client = httpx.AsyncClient(transport=httpx.MockTransport(handler))
    pmc = PmcClient(Fetcher(client, 15, "test-agent"), "https://pmc.test/idconv", "https://pmc.test/oai")
    record = asyncio.run(pmc.fetch_record("PMC123", None))
    assert record.pmcid == "PMC123"


def test_a_redirect_without_following_is_rejected_not_parsed():
    """Documents why the redirect flag is required, not merely present.

    With ``follow_redirects=False`` the same 301 reaches ``fetch_record`` as a
    non-200, which is exactly the UPSTREAM_INVALID_REQUEST this fix removed.
    """

    def handler(request):
        if request.url.path == "/oai":
            return httpx.Response(301, headers={"Location": "https://pmc.test/oai-moved"})
        return httpx.Response(200, content=JATS)

    # A fetcher that does not follow redirects stands in for the pre-fix call.
    client = httpx.AsyncClient(transport=httpx.MockTransport(handler))
    fetcher = Fetcher(client, 15, "test-agent")
    original = fetcher.get

    async def no_follow(url, **kwargs):
        kwargs["follow_redirects"] = False
        return await original(url, **kwargs)

    fetcher.get = no_follow  # type: ignore[method-assign]
    pmc = PmcClient(fetcher, "https://pmc.test/idconv", "https://pmc.test/oai")
    with pytest.raises(ContractError) as raised:
        asyncio.run(pmc.fetch_record("PMC123", None))
    assert raised.value.error_code is ErrorCode.UPSTREAM_INVALID_REQUEST
