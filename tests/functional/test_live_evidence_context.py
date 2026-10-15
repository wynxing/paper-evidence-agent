"""Live check: evidence-context neighbours on a REAL frozen source (#20 checklist).

``#20`` 的清单有一条：*原始输入与证据上下文接口（#27）；证据邻段需在真实来源上复测
（#29 已合并，见 #28）*。本文件执行那次复测。

为什么这样搭：

* **来源是真的**——经真实 `SourceService` 走 Crossref/PMC 取回并冻结，`parse_jats`
  真的跑在这份正文上。此前该能力恒为空，正是因为非 OA 回落只拿到题录+摘要（`#28`）。
* **模型是脚本化的**——`ScriptedGateway` 回放一份固定判断。要复测的是**邻段展开**，
  不是模型判断；用真实模型只会把 `#62` 的失败混进来，让这次复测测不到本来的目标。
* **接口是真实入口**——断言同时走 `store.evidence_context` 与 HTTP 路由
  `GET /api/checks/{id}/evidence-context`，因为清单点的是这个接口。

跳过条件与 `tests/tools/test_live_source_contract.py` 一致：CI 无网络出口，只有显式设置
``PAPER_EVIDENCE_LIVE_SOURCES=1`` 才运行。**跳过的运行不算通过。**
"""

import asyncio
import json
import os
import re
import time
from dataclasses import replace

import pytest
from fastapi.testclient import TestClient

from acceptance import VERSION_HASH, ScriptedGateway

from paper_evidence.agents.prompts import PaperPromptBuilder
from paper_evidence.domain import ContractError
from paper_evidence.api.app import app
from paper_evidence.api.deps import Services, set_services
from paper_evidence.config import Settings
from paper_evidence.domain.contracts import RunConfigSnapshot
from paper_evidence.domain.records import TaskInput
from paper_evidence.domain.rules import criteria_reference
from paper_evidence.graph.workflow import BoundedWorkflow
from paper_evidence.retrieval.jats import parse_jats
from paper_evidence.retrieval.local import StoreRetriever

pytestmark = [
    pytest.mark.live,
    pytest.mark.skipif(
        os.environ.get("PAPER_EVIDENCE_LIVE_SOURCES") != "1",
        reason="live upstream checks are opt-in; CI has no network egress",
    ),
]

#: A CC BY record big enough to have a middle paragraph and real body text.
PMCID = "PMC1182327"
DOI = "10.1371/journal.pmed.0020124"

#: 1-based position of the paragraph the scripted decision cites. Deliberately a
#: middle paragraph: a boundary anchor cannot show that both sides expand.
ANCHOR_POSITION = 5

DEADLINE_SECONDS = 120.0


class _FetchedOnce:
    """Replay the one real resolve/fetch pair into the workflow.

    The workflow resolves and fetches on its own; fetching twice would double the
    network cost and could in principle straddle an upstream change. The calls
    this replays are the real ones, made once by :func:`_fetch_real_record`.
    """

    def __init__(self, preview, snapshot) -> None:
        self._preview = preview
        self._snapshot = snapshot

    async def resolve(self, doi: str, deadline=None):
        return self._preview

    async def fetch(self, doi: str, deadline=None):
        return self._snapshot


async def _with_backoff(call, *, attempts: int = 4, pause: float = 6.0):
    """Retry a live fetch a few times with a pause.

    ``Fetcher`` already retries once, but **immediately**: for a 429 without
    ``Retry-After`` that is no backoff at all, and Crossref/PMC do throttle. A
    transient throttle is not what this file is about, so absorb it here rather
    than let it look like a neighbour-expansion failure. Anything that survives
    the retries still fails, with the upstream error intact.
    """

    last = None
    for index in range(attempts):
        try:
            return await call()
        except ContractError as error:
            last = error
            if index + 1 < attempts:
                await asyncio.sleep(pause)
    raise last


def _fetch_real_record(work):
    """Real Crossref + PMC fetch, once, with bounded retries against throttling."""

    async def run():
        services = Services(replace(Settings.from_env(), data_dir=work, contact_email=""))
        # ``source_service`` is a method (it builds the connectors), not a property.
        service = services.source_service()

        async def resolve():
            return await service.resolve(DOI, time.monotonic() + DEADLINE_SECONDS)

        async def fetch():
            return await service.fetch(DOI, time.monotonic() + DEADLINE_SECONDS)

        preview = await _with_backoff(resolve)
        snapshot = await _with_backoff(fetch)
        return services, preview, snapshot

    return asyncio.run(run())


def _decision_citing(position: int, quote: str) -> str:
    return json.dumps({
        "action": "final",
        "decision": {
            "label": "支持",
            "rationale": "冻结片段直接支持该论断。",
            "supported_parts": ["该片段支持论断"],
            "scope_differences": [],
            "limitations": [],
            "evidence": [{"paragraph": position, "quote": quote}],
        },
    }, ensure_ascii=False)


@pytest.fixture(scope="module")
def frozen(tmp_path_factory):
    """One real record, fetched once and driven through the real workflow."""

    work = tmp_path_factory.mktemp("live-evidence-context")
    services, preview, snapshot = _fetch_real_record(work)
    paragraphs = parse_jats(snapshot)
    assert len(paragraphs) >= ANCHOR_POSITION + 1, "该记录段落太少，测不到两侧展开"

    anchor = paragraphs[ANCHOR_POSITION - 1]
    # The quote must be verbatim from the real paragraph; take a slice of it.
    quote = anchor.text[:80]
    # Query with words taken from the anchor itself: only paragraphs that entered
    # the decision context may back it, so a query that misses the anchor would be
    # rejected before the neighbour expansion is ever reached.
    terms = [word for word in re.findall(r"[A-Za-z]{6,}", anchor.text)][:2] or ["mortality"]
    transcript = [
        json.dumps({"queries": terms}, ensure_ascii=False),
        _decision_citing(ANCHOR_POSITION, quote),
    ]

    settings = replace(Settings.from_env(), data_dir=work, contact_email="")
    store = services.store
    workflow = BoundedWorkflow(
        store=store,
        resolver=_FetchedOnce(preview, snapshot),
        fulltext=_FetchedOnce(preview, snapshot),
        retriever=StoreRetriever(store, settings.retrieval_context_limit),
        prompts=PaperPromptBuilder(),
        gateway=ScriptedGateway(transcript, [item.paragraph_id for item in paragraphs]),
        settings=settings,
    )
    task = TaskInput(id="live-neighbours", claim=anchor.text[:80], doi=DOI,
                     config_digest="live", authorized_recipients=("Agnes",))
    store.create(
        task,
        RunConfigSnapshot(
            profile="evaluation", config_digest="live", snapshot_ref="live",
            authorized_recipients=["Agnes"], limits=settings.limits,
            timeouts=settings.timeouts, observability=settings.observability,
        ),
        criteria_reference("live"),
    )
    detail = asyncio.run(workflow.run(task, time.monotonic() + DEADLINE_SECONDS))

    yield {
        "services": services, "store": store, "task": task, "detail": detail,
        "snapshot": snapshot, "paragraphs": paragraphs, "anchor": anchor,
    }
    store.close()
    services.close()


def test_a_real_frozen_source_has_enough_paragraphs_to_expand(frozen):
    """Guard the premise: a real source must carry body text, not front matter.

    This is the check that would have caught `#28`: with the front-matter
    fallback the frozen "full text" had no body, so every expansion was empty.
    """

    paragraphs = frozen["paragraphs"]
    assert len(paragraphs) >= 5, f"{PMCID} 只解析出 {len(paragraphs)} 段，怀疑取到的不是正文"
    sections = {item.section for item in paragraphs}
    assert sections - {"abstract"}, f"全部段落都在 abstract 里：{sections}"


def test_the_scripted_task_completed_and_cited_a_real_paragraph(frozen):
    """Without a completed, cited task there is nothing for the endpoint to expand."""

    detail = frozen["detail"]
    assert detail.status.value == "COMPLETED", (detail.status.value, detail.error_code)
    assert detail.decision is not None and detail.decision.evidence


def _expected_ordinals(frozen) -> set[int]:
    """Every anchor's ordinal ±1 — the contract, not just the cited anchor's three.

    ``evidence_context`` expands **two** anchor sets together: the candidates that
    entered the model context, and the paragraphs the decision cites. A search round
    usually brings several candidates in, so the union is wider than one anchor's
    three paragraphs. Asserting only on the cited anchor's neighbourhood would pass
    while the endpoint also shipped unrelated paragraphs.
    """

    store = frozen["store"]
    ordinal_of = {item.paragraph_id: item.ordinal for item in frozen["paragraphs"]}
    entered = {
        item.paragraph_id for item in store.candidates(frozen["task"].id) if item.entered_context
    }
    cited = {item.paragraph_id for item in (frozen["detail"].decision.evidence or [])}
    highest = max(ordinal_of.values())
    expected: set[int] = set()
    for paragraph_id in entered | cited:
        ordinal = ordinal_of[paragraph_id]
        expected |= {ordinal - 1, ordinal, ordinal + 1}
    return {ordinal for ordinal in expected if 1 <= ordinal <= highest}


def test_evidence_context_expands_both_ordinal_neighbours(frozen):
    """The union is exactly the anchors' ordinal±1, and each entry is the real paragraph."""

    context = frozen["store"].evidence_context(frozen["task"].id)
    assert context is not None and context.source_id is not None

    anchor_ordinal = frozen["anchor"].ordinal
    returned = {item.ordinal for item in context.paragraphs}
    expected = _expected_ordinals(frozen)

    assert {anchor_ordinal - 1, anchor_ordinal, anchor_ordinal + 1} <= returned, (
        f"被引用的锚点 {anchor_ordinal} 没有拿到两侧邻段；实际 {sorted(returned)}"
    )
    assert returned == expected, (
        f"展开结果 {sorted(returned)} 不等于「各锚点 ordinal±1」{sorted(expected)}"
    )

    # Genuine adjacency: the neighbour's text must be the paragraph at that
    # ordinal in the real document, not merely the next item in some list.
    by_ordinal = {item.ordinal: item for item in frozen["paragraphs"]}
    for item in context.paragraphs:
        assert item.paragraph_id == by_ordinal[item.ordinal].paragraph_id
        assert item.text == by_ordinal[item.ordinal].text
        assert item.paragraph_hash == by_ordinal[item.ordinal].paragraph_hash


def test_evidence_context_marks_the_cited_anchor(frozen):
    """The cited anchor is flagged ``cited`` and also ``entered_context``."""

    context = frozen["store"].evidence_context(frozen["task"].id)
    by_ordinal = {item.ordinal: item for item in context.paragraphs}

    anchor = by_ordinal[frozen["anchor"].ordinal]
    assert anchor.cited is True
    assert anchor.entered_context is True, (
        "被引用的段落必须同时是进入上下文的候选，否则它本不该通过逐字校验"
    )
    assert anchor.text == frozen["anchor"].text

    cited_ordinals = [item.ordinal for item in context.paragraphs if item.cited]
    assert cited_ordinals == [frozen["anchor"].ordinal], "只有被引用的那一段该带 cited"


def test_the_http_endpoint_returns_the_same_neighbours(frozen):
    """The checklist item names this endpoint, so assert through it too."""

    services = frozen["services"]
    set_services(services)
    try:
        with TestClient(app) as http:
            response = http.get(f"/api/checks/{frozen['task'].id}/evidence-context")
    finally:
        set_services(None)

    assert response.status_code == 200, response.text
    payload = response.json()
    assert payload["source_id"] is not None

    anchor_ordinal = frozen["anchor"].ordinal
    returned = {item["ordinal"] for item in payload["paragraphs"]}
    assert returned == _expected_ordinals(frozen)
    assert {anchor_ordinal - 1, anchor_ordinal, anchor_ordinal + 1} <= returned
    assert [item["ordinal"] for item in payload["paragraphs"] if item["cited"]] == [anchor_ordinal]

    # The endpoint is a thin read of the same projection; the two must not drift.
    context = frozen["store"].evidence_context(frozen["task"].id)
    assert returned == {item.ordinal for item in context.paragraphs}


def test_a_boundary_anchor_expands_only_inward(frozen):
    """The last paragraph has no n+1; a phantom neighbour would mean made-up text."""

    paragraphs = frozen["paragraphs"]
    last = max(paragraphs, key=lambda item: item.ordinal)
    read = frozen["store"].read_neighbors(frozen["snapshot"].source_id, [last.paragraph_id])
    assert sorted(item.ordinal for item in read) == [last.ordinal - 1, last.ordinal]
    assert max(item.ordinal for item in read) <= last.ordinal


def test_an_unknown_paragraph_id_expands_to_nothing(frozen):
    """A foreign or unknown id must not leak paragraphs out of the frozen source."""

    bogus = f"p:PMC0000000:{VERSION_HASH}:jats-0.1.0:1"
    assert frozen["store"].read_neighbors(frozen["snapshot"].source_id, [bogus]) == []
