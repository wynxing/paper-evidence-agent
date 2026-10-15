"""Live PMC contract checks — opt-in, real network.

``tests/tools/test_sources.py`` drives the connectors through
``httpx.MockTransport``. That pins the shape of the request this client *sends*;
it can never pin the shape PMC actually *serves*. That gap is how Issue #28
survived a green 248-case suite: every JATS fixture in this repository is a
hand-made minimal snapshot, so nothing in the suite could contradict a connector
comment that said ``pmc_fm`` returns a full ``<body>`` when live PMC returns none.

These checks close that gap by asking live PMC. They need network egress, which
CI does not have, so they are skipped unless ``PAPER_EVIDENCE_LIVE_SOURCES=1``:

    PAPER_EVIDENCE_LIVE_SOURCES=1 \\
      backend/.venv/bin/python -m pytest -c backend/pyproject.toml -q -m live

A skipped run is **not** a passing run: record it as unverified, never as passed.
Observed results belong in ``docs/verification.md`` with the date and environment.
"""

import asyncio
import hashlib
import os
import time
import xml.etree.ElementTree as ElementTree

import httpx
import pytest

from paper_evidence.domain.contracts import SourceRecord
from paper_evidence.domain.records import SourceSnapshot
from paper_evidence.retrieval.jats import parse_jats
from paper_evidence.sources.http import USER_AGENT, Fetcher
from paper_evidence.sources.pmc import PmcClient

pytestmark = [
    pytest.mark.live,
    pytest.mark.skipif(
        os.environ.get("PAPER_EVIDENCE_LIVE_SOURCES") != "1",
        reason="live upstream checks are opt-in; CI has no network egress",
    ),
]

PMC_OAI_URL = "https://pmc.ncbi.nlm.nih.gov/api/oai/v1/mh/"
PMC_ID_CONVERTER_URL = "https://pmc.ncbi.nlm.nih.gov/tools/idconv/api/v1/articles/"

DEADLINE_SECONDS = 60.0

#: CC BY records whose licence and full-text availability were confirmed by hand
#: in earlier rounds (#20, #28, #29). Public identifiers only — no article text is
#: stored in the repository, so the checks always read the current upstream.
KNOWN_CC_BY_RECORDS = [
    ("PMC1182327", "10.1371/journal.pmed.0020124"),
    ("PMC8806060", "10.1371/journal.pone.0262629"),
    ("PMC7461750", "10.1186/s12889-020-09394-x"),
]

_TAGS = ("body", "sec", "p", "abstract")


def _tag_counts(raw: bytes) -> dict[str, int]:
    """Count the structural tags a judgement depends on."""

    root = ElementTree.fromstring(raw)
    counts = dict.fromkeys(_TAGS, 0)
    for element in root.iter():
        local = element.tag.rsplit("}", 1)[-1]
        if local in counts:
            counts[local] += 1
    return counts


def _pmc_client(http: httpx.AsyncClient) -> PmcClient:
    return PmcClient(Fetcher(http, DEADLINE_SECONDS, USER_AGENT), PMC_ID_CONVERTER_URL, PMC_OAI_URL)


def _snapshot(pmcid: str, doi: str, raw: bytes) -> SourceSnapshot:
    """A frozen snapshot shaped like the one the storage layer writes."""

    return SourceSnapshot(
        source_id=pmcid,
        metadata=SourceRecord(
            title=None,
            authors=[],
            year=None,
            doi=doi,
            pmcid=pmcid,
            license="CC BY",
            version=None,
            access_url=None,
            retrieved_at=None,
            version_hash=hashlib.sha256(raw).hexdigest(),
        ),
        jats_bytes=raw,
    )


async def _both_prefixes(pmcid: str) -> tuple[dict[str, int], dict[str, int]]:
    """Fetch one record under both ``metadataPrefix`` values.

    ``_get_record`` is deliberately private: ``fetch_record`` hides the fallback
    behind the public result, and the whole point of these checks is to observe
    what each prefix actually serves. Reading both is the only way to catch PMC
    changing either shape.
    """

    async with httpx.AsyncClient(timeout=DEADLINE_SECONDS) as http:
        pmc = _pmc_client(http)
        deadline = time.monotonic() + DEADLINE_SECONDS
        _root, full = await pmc._get_record(pmcid, "pmc", deadline)
        _root, front = await pmc._get_record(pmcid, "pmc_fm", deadline)
    return _tag_counts(full), _tag_counts(front)


@pytest.mark.parametrize("pmcid,doi", KNOWN_CC_BY_RECORDS)
def test_pmc_id_conversion_resolves_a_real_doi_to_its_pmcid(pmcid, doi):
    """The DOI→PMCID hop is the first external call of every task; pin it live."""

    async def run():
        async with httpx.AsyncClient(timeout=DEADLINE_SECONDS) as http:
            return await _pmc_client(http).convert_to_pmcid(doi, time.monotonic() + DEADLINE_SECONDS)

    assert asyncio.run(run()) == pmcid


@pytest.mark.parametrize("pmcid,doi", KNOWN_CC_BY_RECORDS)
def test_the_full_text_prefix_serves_a_body(pmcid, doi):
    """``metadataPrefix=pmc`` must carry ``<body>``; a judgement may rest on it alone.

    If PMC ever stops serving ``<body>`` here, every claim check silently degrades
    to an abstract-only reading — the exact negative case 产品需求 forbids.
    """

    full, _front = asyncio.run(_both_prefixes(pmcid))
    assert full["body"] >= 1, f"{pmcid} 用 pmc 取回没有 <body>：{full}"


@pytest.mark.parametrize("pmcid,doi", KNOWN_CC_BY_RECORDS)
def test_the_front_matter_prefix_serves_no_body(pmcid, doi):
    """``metadataPrefix=pmc_fm`` is front matter only — ``<body>`` count 0.

    This is the measured fact behind #28. It is pinned here so that a change on
    PMC's side (serving bodies under the front-matter prefix after all) fails
    loudly instead of quietly invalidating the connector's fallback reasoning.
    """

    _full, front = asyncio.run(_both_prefixes(pmcid))
    assert front["body"] == 0, f"{pmcid} 的 pmc_fm 出现了 <body>：{front}"


@pytest.mark.parametrize("pmcid,doi", KNOWN_CC_BY_RECORDS)
def test_a_frozen_record_indexes_more_paragraphs_than_its_front_matter(pmcid, doi):
    """The assertion #28 asked for: a frozen record must beat its own front matter.

    The frozen side comes from the **public** ``fetch_record``, so this tracks the
    connector's own choice of prefix — switching it to the front-matter form fails
    here as well as in the ``fetch_record`` licence check. ``parse_jats`` is the
    real indexer, so the counts are what the retrieval layer would actually see,
    not a proxy. Equal counts would mean the frozen "full text" is the abstract,
    whatever the metadata prefix was.
    """

    async def run():
        async with httpx.AsyncClient(timeout=DEADLINE_SECONDS) as http:
            pmc = _pmc_client(http)
            deadline = time.monotonic() + DEADLINE_SECONDS
            record = await pmc.fetch_record(pmcid, deadline)
            _root, front = await pmc._get_record(pmcid, "pmc_fm", deadline)
            return record.jats_bytes, front

    frozen, front = asyncio.run(run())
    frozen_paragraphs = parse_jats(_snapshot(pmcid, doi, frozen))
    front_paragraphs = parse_jats(_snapshot(pmcid, doi, front))
    assert len(frozen_paragraphs) > len(front_paragraphs), (
        f"{pmcid} 冻结后的段落数 {len(frozen_paragraphs)} 未超过题录+摘要的 "
        f"{len(front_paragraphs)}，说明取到的不是正文"
    )


@pytest.mark.parametrize("pmcid,doi", KNOWN_CC_BY_RECORDS)
def test_a_fetched_record_is_english_cc_by_full_text(pmcid, doi):
    """``fetch_record`` must land on the full-text form, with the licence gate passing."""

    async def run():
        async with httpx.AsyncClient(timeout=DEADLINE_SECONDS) as http:
            return await _pmc_client(http).fetch_record(pmcid, time.monotonic() + DEADLINE_SECONDS)

    record = asyncio.run(run())
    assert record.pmcid == pmcid
    assert record.license == "CC BY"
    assert (record.language or "").lower().startswith("en")
    assert _tag_counts(record.jats_bytes)["body"] >= 1, (
        f"{pmcid} 的 fetch_record 落到了没有 <body> 的形式，即题录+摘要"
    )
