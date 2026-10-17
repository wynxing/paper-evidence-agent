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
from paper_evidence.retrieval.jats import parse_jats
from paper_evidence.sources.crossref import CrossrefClient, DoiResolver
from paper_evidence.sources.doi import is_valid_doi, normalize_doi, require_valid_doi
from paper_evidence.sources.http import Fetcher, classify_status
from paper_evidence.sources.openalex import OpenAlexClient
from paper_evidence.sources.pmc import PmcClient, classify_license
from paper_evidence.sources.service import SourceService

DOI = "10.1000/xyz"

#: The record the connector must freeze, described the way upstream serves it: an
#: ``<article>`` subtree **inside** an OAI-PMH envelope. The two fixtures below are
#: only the ``<article>`` part — ``oai_response`` adds the envelope, so a test can
#: tell the two byte ranges apart, and ``version_hash`` is defined over the
#: ``<article>`` bytes alone (Issue #67). The live record declares its namespaces on
#: ``<article>`` itself, so the envelope contributes no namespace either.
JATS = b"""<article xml:lang="en">
 <front><article-meta>
   <article-id pub-id-type="doi">10.1000/xyz</article-id>
   <title-group><article-title>Demo study</article-title></title-group>
   <permissions><license license-type="cc-by">CC BY 4.0</license></permissions>
 </article-meta></front>
 <body><sec><title>Results</title><p>The treatment reduced mortality.</p></sec></body>
</article>"""

#: The shape PMC actually returns for ``metadataPrefix=pmc_fm``: front matter
#: (title, permissions, abstract) and **no ``<body>``**. Measured against live
#: PMC on 2026-10-12 — three of three records had a ``<body>`` count of 0.
FRONT_MATTER_JATS = b"""<article xml:lang="en">
 <front><article-meta>
   <article-id pub-id-type="doi">10.1000/xyz</article-id>
   <title-group><article-title>Demo study</article-title></title-group>
   <abstract><p>The treatment reduced mortality.</p></abstract>
   <permissions><license license-type="cc-by">CC BY 4.0</license></permissions>
 </article-meta></front>
</article>"""

#: ``<responseDate>`` is the only part of the envelope that changes between two
#: fetches of an unchanged record — measured live 2026-10-16 on PMC1182327: the
#: full-response digest moved (``19ea7f7a…`` → ``cc37eb4d…``) while the
#: ``<article>`` digest stayed ``caf353df06c98af8…``.
RESPONSE_DATE = "2026-10-15T12:27:19Z"


def oai_response(article: bytes, response_date: str = RESPONSE_DATE) -> bytes:
    """Wrap an ``<article>`` subtree the way PMC's GetRecord does."""

    return (
        b'<?xml version="1.0" encoding="UTF-8"?>\n'
        b'<OAI-PMH xmlns="http://www.openarchives.org/OAI/2.0/">\n'
        b" <responseDate>" + response_date.encode() + b"</responseDate>\n"
        b' <request verb="GetRecord">https://pmc.test/oai</request>\n'
        b" <GetRecord><record>\n"
        b"  <header><identifier>oai:pubmedcentral.nih.gov:123</identifier></header>\n"
        b"  <metadata>" + article + b"</metadata>\n"
        b" </record></GetRecord>\n"
        b"</OAI-PMH>\n"
    )


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


def fetch_handler(jats=JATS, pmcid="PMC123", doi_in_article="10.1000/xyz", response=None):
    article = jats.replace(b"10.1000/xyz", doi_in_article.encode())

    def handler(request):
        host = request.url.host
        if host == "crossref.test":
            return httpx.Response(200, json={"message": {"title": ["Demo study"]}})
        if host == "pmc.test" and request.url.path == "/idconv":
            return httpx.Response(200, json={"records": [{"pmcid": pmcid}] if pmcid else []})
        if host == "pmc.test" and request.url.path == "/oai":
            body = oai_response(article) if response is None else response
            return httpx.Response(200, content=body)
        if host == "openalex.test":
            return httpx.Response(200, json={"open_access": {"is_oa": True},
                                             "locations": [{"landing_page_url": "https://open.example/x"}]})
        return httpx.Response(404)

    return handler


def test_fetch_returns_a_licensed_snapshot_with_a_version_hash():
    """``version_hash`` 覆盖 ``<article>`` 子树，**不**覆盖整个 OAI-PMH 响应。

    Issue #67：响应信封里的 ``<responseDate>`` 每次请求都不同，把它算进哈希会让
    ``version_hash``（进而 ``source_id``、``paragraph_id``）每次取回都变。这里同时断言
    相等与不等，好让退回「对整包取哈希」立刻失败，而不是只靠一个看起来仍旧成立的等号。
    """

    import time

    response = oai_response(JATS)
    snapshot = run(build(fetch_handler(response=response)), deadline=time.monotonic() + 60)
    assert snapshot.metadata.license == "CC BY"
    assert snapshot.metadata.pmcid == "PMC123"
    # access_url 必须指向实际冻结的 PMC 版本，而不是 OpenAlex 的 landing page。
    assert snapshot.metadata.access_url == "https://pmc.ncbi.nlm.nih.gov/articles/PMC123/"
    assert snapshot.open_locations == ("https://open.example/x",)
    assert snapshot.metadata.version_hash == hashlib.sha256(JATS).hexdigest()
    assert snapshot.metadata.version_hash != hashlib.sha256(response).hexdigest(), (
        "整包带每次请求都不同的 <responseDate>，不能作版本标识"
    )
    assert snapshot.source_id == f"PMC123:{snapshot.metadata.version_hash}"
    assert snapshot.jats_bytes == JATS


def test_stable_identifiers_survive_a_second_fetch_of_the_same_record():
    """同一记录取回两次、只有信封 ``<responseDate>`` 不同：三个标识必须逐字不变。

    Issue #67 的缺口正在这里：``version_hash`` 曾对整个 OAI-PMH 响应取哈希，于是
    ``source_id = <pmcid>:<version_hash>`` 与
    ``paragraph_id = p:<source-key>:<version-hash>:<parser>:<ordinal>``
    每次取回都变——诊断包里的段落引用、人工核对结论记下的段落位置、两次验收（回归）之间的
    对比，都会因此失效。同一记录重取必须得到同一份来源。

    原有用例没有检验过这条语义：它们都用固定常量 ``VERSION_HASH`` 构造来源，从未从
    ``fetch`` 的真实字节算过一次哈希。所以这里走完整的 ``fetch`` 链路，两次输入正文完全
    相同、只有请求时刻不同。
    """

    first_response = oai_response(JATS, "2026-10-15T12:27:19Z")
    second_response = oai_response(JATS, "2026-10-15T12:27:23Z")
    assert first_response != second_response, "两次取回的信封时间必须不同才能检验稳定性"
    served = [first_response, second_response]

    def handler(request):
        host = request.url.host
        if host == "crossref.test":
            return httpx.Response(200, json={"message": {"title": ["Demo study"]}})
        if host == "pmc.test" and request.url.path == "/idconv":
            return httpx.Response(200, json={"records": [{"pmcid": "PMC123"}]})
        if host == "pmc.test" and request.url.path == "/oai":
            return httpx.Response(200, content=served.pop(0))
        if host == "openalex.test":
            return httpx.Response(200, json={"locations": []})
        return httpx.Response(404)

    import time

    service = build(handler)
    first = run(service, deadline=time.monotonic() + 60)
    second = run(service, deadline=time.monotonic() + 60)

    assert first.metadata.version_hash == second.metadata.version_hash, (
        "同一版本重取得到了不同的 version_hash，它标识的是这一次请求而不是这个版本"
    )
    assert first.source_id == second.source_id
    assert [item.paragraph_id for item in parse_jats(first)] == [
        item.paragraph_id for item in parse_jats(second)
    ], "同一版本的段落 ID 必须可跨次指认，否则按 ID 保存的引用重取后全部失效"
    # 锚点：那个稳定值就是 <article> 子树的哈希，而不是任一次响应的整包哈希。
    assert first.metadata.version_hash == hashlib.sha256(JATS).hexdigest()


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


@pytest.mark.parametrize("status", [200, 400], ids=["body-with-200", "body-with-400"])
def test_pmc_oai_falls_back_to_front_matter_only_after_cannot_disseminate(status):
    """只有 PMC 明确回 ``cannotDisseminateFormat`` 时才退到只含题录+摘要的 ``pmc_fm``。

    两种到达形态都要覆盖：HTTP 200 与 HTTP 400。真实 PMC 走的是后者
    （2026-10-15 实测：非 OA 记录 10/10 为 ``400 cannotDisseminateFormat``），
    只测 200 的写法让「先按状态码拒绝」的实现看起来一直是对的（Issue #61）。
    """

    seen = []

    def handler(request):
        if request.url.host == "pmc.test" and request.url.path == "/oai":
            prefix = dict(request.url.params)["metadataPrefix"]
            seen.append(prefix)
            if prefix == "pmc":
                return httpx.Response(status, content=CANNOT_DISSEMINATE)
            return httpx.Response(200, content=FRONT_MATTER_JATS)
        if request.url.host == "pmc.test" and request.url.path == "/idconv":
            return httpx.Response(200, json={"records": [{"pmcid": "PMC123"}]})
        return httpx.Response(200, json={"message": {"title": ["Demo study"]}})

    client = httpx.AsyncClient(transport=httpx.MockTransport(handler))
    pmc = PmcClient(Fetcher(client, 15, "test-agent"), "https://pmc.test/idconv", "https://pmc.test/oai")
    record = asyncio.run(pmc.fetch_record("PMC123", None))

    assert seen == ["pmc", "pmc_fm"], "先取正文，被拒后才回落"
    assert record.pmcid == "PMC123"
    assert record.license == "CC BY"
    assert record.jats_bytes == FRONT_MATTER_JATS, "冻结的是 <article> 子树，不含 OAI 信封"
    assert b"<body" not in record.jats_bytes, "回落拿到的只有题录+摘要，不含正文"


@pytest.mark.parametrize("status", [200, 400], ids=["body-with-200", "body-with-400"])
@pytest.mark.parametrize("code", ["idDoesNotExist", "badArgument"])
def test_pmc_oai_errors_other_than_cannot_disseminate_are_not_retried(code, status):
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
            return httpx.Response(status, content=error)
        if request.url.host == "pmc.test" and request.url.path == "/idconv":
            return httpx.Response(200, json={"records": [{"pmcid": "PMC123"}]})
        return httpx.Response(200, json={"message": {"title": ["Demo study"]}})

    client = httpx.AsyncClient(transport=httpx.MockTransport(handler))
    pmc = PmcClient(Fetcher(client, 15, "test-agent"), "https://pmc.test/idconv", "https://pmc.test/oai")
    with pytest.raises(ContractError) as raised:
        asyncio.run(pmc.fetch_record("PMC123", None))

    assert raised.value.error_code is ErrorCode.SOURCE_UNAVAILABLE
    assert seen == ["pmc"], "非 cannotDisseminateFormat 的错误不重试"


@pytest.mark.parametrize("status,expected", [(400, ErrorCode.UPSTREAM_INVALID_REQUEST),
                                             (404, ErrorCode.UPSTREAM_INVALID_REQUEST)])
def test_a_non_oai_error_body_is_still_judged_by_status(status, expected):
    """状态码只在「响应体不是 OAI-PMH 错误」时才作准。

    把「凡非 200 一律当参数错误」改成「先看体」之后，这条反向边界必须还在：
    一个不带 OAI 错误码的错误响应不能被当成「记录不可获取」而回落。
    """

    seen = []

    def handler(request):
        if request.url.host == "pmc.test" and request.url.path == "/oai":
            seen.append(dict(request.url.params)["metadataPrefix"])
            return httpx.Response(status, content=b"<html><body>Bad Request</body></html>")
        if request.url.host == "pmc.test" and request.url.path == "/idconv":
            return httpx.Response(200, json={"records": [{"pmcid": "PMC123"}]})
        return httpx.Response(200, json={"message": {"title": ["Demo study"]}})

    client = httpx.AsyncClient(transport=httpx.MockTransport(handler))
    pmc = PmcClient(Fetcher(client, 15, "test-agent"), "https://pmc.test/idconv", "https://pmc.test/oai")
    with pytest.raises(ContractError) as raised:
        asyncio.run(pmc.fetch_record("PMC123", None))

    assert raised.value.error_code is expected
    assert seen == ["pmc"], "非 OAI 错误体不触发回落"


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
