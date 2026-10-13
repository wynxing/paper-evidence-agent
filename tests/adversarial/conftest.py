"""Fixtures for the adversarial-and-security dimension (测试方案「对抗与安全」).

The dimension's doubles, marker strings and JATS/action builders live in
:mod:`doubles`; this file keeps only the fixtures. Why the doubles are not in
``conftest.py`` is explained there (Issue #31) — in short, a bare ``from
conftest import ...`` binds to whichever directory pytest imported first, so it
breaks as soon as another test directory adds its own ``conftest.py``.
"""

import asyncio
import time
from dataclasses import replace

import httpx
import pytest

from doubles import AdversarialRun, CapturingGateway, FrozenFulltext, FrozenResolver
from paper_evidence.agents.prompts import PaperPromptBuilder
from paper_evidence.config import Settings
from paper_evidence.diagnosis.projector import SqliteDiagnosticProjector
from paper_evidence.domain.contracts import RunConfigSnapshot
from paper_evidence.domain.records import TaskInput
from paper_evidence.domain.rules import criteria_reference
from paper_evidence.graph.workflow import BoundedWorkflow
from paper_evidence.retrieval.local import StoreRetriever
from paper_evidence.storage.sqlite import SqliteStore


@pytest.fixture
def run_workflow(tmp_path):
    """Run the real bounded workflow over an injected frozen source."""

    def _run(*, claim: str, jats_bytes: bytes, outputs: list[str]) -> AdversarialRun:
        settings = replace(Settings.from_env(), data_dir=tmp_path, contact_email="")
        store = SqliteStore(tmp_path / "adversarial.sqlite3")
        gateway = CapturingGateway(outputs)
        workflow = BoundedWorkflow(
            store=store, resolver=FrozenResolver(), fulltext=FrozenFulltext(jats_bytes),
            retriever=StoreRetriever(store, settings.retrieval_context_limit),
            prompts=PaperPromptBuilder(), gateway=gateway, settings=settings,
        )
        task = TaskInput(id="adv-1", claim=claim, doi="10.1000/adversarial", config_digest="adv",
                         authorized_recipients=("Agnes",))
        store.create(
            task,
            RunConfigSnapshot(
                profile="evaluation", config_digest="adv", snapshot_ref="adv",
                authorized_recipients=["Agnes"], limits=settings.limits,
                timeouts=settings.timeouts, observability=settings.observability,
            ),
            criteria_reference("rev"),
        )
        detail = asyncio.run(workflow.run(task, time.monotonic() + 180))
        # The store stays open: tests inspect the diagnostic packet through it.
        return AdversarialRun(
            detail=detail, gateway=gateway, store=store,
            projector=SqliteDiagnosticProjector(store, settings.criteria()),
        )

    return _run


@pytest.fixture
def recorded_transport():
    """An httpx transport that records every URL the connectors request.

    The body mimics Crossref's envelope so the connector's own parsing succeeds
    and the test keeps measuring only where the request went.
    """

    seen: list[str] = []

    def handler(request: httpx.Request) -> httpx.Response:
        seen.append(str(request.url))
        return httpx.Response(200, json={"message": {"title": ["mock"], "author": []}})

    return seen, httpx.MockTransport(handler)
