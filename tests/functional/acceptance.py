"""Doubles and sample loading for the functional-accuracy dimension (测试方案「功能准确性」).

This directory holds the frozen semantic acceptance set. Per 测试方案:44 the
frozen samples and their expected labels are read by the tests only and are
never imported by the running application; per 测试方案:46 every sample records a
real PMC source with a human-checked DOI, version, licence, original paragraph
position and expected label.

The upstream model is *not* faked into correctness: the runner feeds the canned
model outputs that the sample declares and asserts on what the application
publishes. A semantic label is therefore only credited when the deterministic
evidence gates accepted a quote that really is in the frozen paragraph.

Why this is not ``conftest.py``
-------------------------------

A bare ``from conftest import ...`` resolves to whichever ``conftest`` module
pytest placed on ``sys.path`` first, which follows collection order rather than
the importing directory. Adding a second ``conftest.py`` under ``tests/`` made
the imports in this dimension resolve to that file instead, so the sample loader
and the doubles now live under this dimension-unique module name — the same
convention ``tests/functional/report.py`` already uses. ``conftest.py`` keeps
only the fixtures and imports from here. Root cause: Issue #31.
"""

import asyncio
import json
import time
from dataclasses import dataclass, replace
from pathlib import Path

from paper_evidence.agents.prompts import PaperPromptBuilder
from paper_evidence.config import Settings
from paper_evidence.domain.contracts import RunConfigSnapshot, SourcePreview, SourceRecord
from paper_evidence.domain.records import SourceSnapshot, TaskInput
from paper_evidence.domain.rules import criteria_reference
from paper_evidence.graph.workflow import BoundedWorkflow
from paper_evidence.retrieval.local import StoreRetriever
from paper_evidence.retrieval.jats import parse_jats
from paper_evidence.storage.sqlite import SqliteStore

SAMPLES = Path(__file__).parent / "samples"

VERSION_HASH = "f" * 64


@dataclass(frozen=True)
class FrozenCase:
    """One human-checked sample plus the model transcript it expects."""

    case_id: str
    claim: str
    doi: str
    label: str
    jats: bytes
    quotes: dict[str, str]
    transcript: tuple[str, ...]
    #: Human-readable restatement of this case's acceptance checks (测试方案
    #: 「通过条件」). Read by a reviewer; the machine assertions live in the test
    #: module, so this stays a description rather than a second source of truth.
    expected_checks: tuple[str, ...] = ()

    def quote(self, name: str) -> str:
        return self.quotes[name]


def _load(case_id: str) -> FrozenCase:
    payload = json.loads((SAMPLES / f"{case_id}.json").read_text(encoding="utf-8"))
    return FrozenCase(
        case_id=case_id,
        claim=payload["claim"],
        # The DOI sits with the rest of the source block (pmcid/version/licence)
        # so a sample keeps all of its identifying facts in one place.
        doi=payload["source"]["doi"],
        label=payload["expected_label"],
        jats=payload["jats"].encode("utf-8"),
        quotes=payload["quotes"],
        transcript=tuple(payload["transcript"]),
        expected_checks=tuple(payload.get("expected_checks", [])),
    )


def available_cases() -> list[str]:
    return sorted(path.stem for path in SAMPLES.glob("*.json"))


def load_case(case_id: str) -> FrozenCase:
    """Load a sample directly; used by tests that also need a negative control."""

    return _load(case_id)


class FrozenResolver:
    """Serves the sample's own DOI so no connector is contacted."""

    def __init__(self, case: FrozenCase) -> None:
        self._case = case

    async def resolve(self, doi, deadline=None):
        return SourcePreview(doi=self._case.doi, title="frozen", authors=["A"], year=2026)


class FrozenFulltext:
    """Serves the sample's frozen JATS under the sample's own version hash."""

    def __init__(self, case: FrozenCase) -> None:
        self._case = case

    async def fetch(self, doi, deadline):
        record = SourceRecord(
            title="frozen", authors=["Ada Lovelace"], year=2026, doi=self._case.doi,
            pmcid="PMC0000001", license="CC BY", version="1", access_url="https://example.org/frozen",
            retrieved_at="2026-10-01T00:00:00+00:00", version_hash=VERSION_HASH,
        )
        return SourceSnapshot(
            source_id=f"PMC0000001:{VERSION_HASH}", metadata=record, jats_bytes=self._case.jats,
        )


class SampleReferenceError(ValueError):
    """A sample points at a paragraph that the frozen JATS does not contain."""


class ScriptedGateway:
    """Replays the sample's transcript and records the logical requests.

    A sample refers to a paragraph by its 1-based position in the frozen JATS
    (``"paragraph": 1``) rather than by the long generated id
    (``p:PMC...:<version>:jats-0.1.0:1``). The position is the human-checked
    fact; the id is derived, so the transcript stays readable and does not have
    to repeat the version hash. :meth:`_resolve` performs that substitution
    before the text reaches the parser, and refuses an out-of-range reference
    instead of silently dropping the evidence.
    """

    def __init__(self, transcript, paragraph_ids=None) -> None:
        self._transcript = list(transcript)
        self._paragraph_ids = list(paragraph_ids or [])
        self.calls: list[dict] = []

    def _resolve(self, text: str) -> str:
        """Replace each evidence ``paragraph`` position with the frozen id."""

        if not self._paragraph_ids:
            return text
        try:
            payload = json.loads(text)
        except ValueError:
            # Not JSON: the parser owns reporting a malformed response.
            return text
        decision = payload.get("decision") if isinstance(payload, dict) else None
        evidence = decision.get("evidence") if isinstance(decision, dict) else None
        if not isinstance(evidence, list):
            return text
        for item in evidence:
            if not isinstance(item, dict) or "paragraph" not in item:
                continue
            ordinal = item.pop("paragraph")
            if not isinstance(ordinal, int) or isinstance(ordinal, bool) or not 1 <= ordinal <= len(self._paragraph_ids):
                raise SampleReferenceError(
                    f"样本引用了不存在的段落 {ordinal!r}；冻结 JATS 只有 {len(self._paragraph_ids)} 段"
                )
            item["paragraph_id"] = self._paragraph_ids[ordinal - 1]
        return json.dumps(payload, ensure_ascii=False)

    async def complete(self, request_id, prompt, deadline, *, purpose, round_index, prompt_version="",
                       context_paragraph_ids=None, repairs_request_id=None):
        from paper_evidence.domain.contracts import ModelAttempt, ModelCall
        from paper_evidence.domain.records import ModelReply

        self.calls.append({"request_id": request_id, "purpose": purpose, "round": round_index})
        text = self._resolve(self._transcript.pop(0))
        attempt = ModelAttempt(
            attempt_id=f"{request_id}:1", attempt_index=1, span_id="s", gateway_request_id=None,
            upstream_response_id=None, configured_model="frozen", deployment_id="frozen", recipient="Agnes",
            response_model="agnes", verified_model_version=None, recovery_kind="none",
            recovery_reason=None, status="success", error_code=None, duration_ms=1, usage=None,
        )
        call = ModelCall(
            request_id=request_id, purpose=purpose, round=round_index, model_alias="paper-default",
            prompt_version=prompt_version, params_digest="frozen",
            context_paragraph_ids=list(context_paragraph_ids or []),
            repairs_request_id=repairs_request_id, attempts=[attempt],
        )
        return ModelReply(text=text, call=call)


@dataclass
class AcceptanceOutcome:
    case: FrozenCase
    detail: object
    gateway: ScriptedGateway
    paragraphs: dict


def run_case(case: FrozenCase, work_dir, *, transcript=None) -> AcceptanceOutcome:
    """Run one frozen case through the real workflow over an injected source.

    Module-level so the acceptance tests and the report generator drive the same
    implementation — a second copy would let the reported numbers drift from the
    numbers the tests assert on.
    """

    settings = replace(Settings.from_env(), data_dir=work_dir, contact_email="")
    store = SqliteStore(work_dir / f"{case.case_id}.sqlite3")
    snapshot = SourceSnapshot(
        source_id=f"PMC0000001:{VERSION_HASH}",
        metadata=SourceRecord(
            title="frozen", authors=["Ada Lovelace"], year=2026, doi=case.doi, pmcid="PMC0000001",
            license="CC BY", version="1", access_url="https://example.org/frozen",
            retrieved_at="2026-10-01T00:00:00+00:00", version_hash=VERSION_HASH,
        ),
        jats_bytes=case.jats,
    )
    parsed = parse_jats(snapshot)
    gateway = ScriptedGateway(
        case.transcript if transcript is None else transcript,
        [item.paragraph_id for item in parsed],
    )
    workflow = BoundedWorkflow(
        store=store, resolver=FrozenResolver(case), fulltext=FrozenFulltext(case),
        retriever=StoreRetriever(store, settings.retrieval_context_limit),
        prompts=PaperPromptBuilder(), gateway=gateway, settings=settings,
    )
    task = TaskInput(
        id=case.case_id, claim=case.claim, doi=case.doi, config_digest="frozen",
        authorized_recipients=("Agnes",),
    )
    store.create(
        task,
        RunConfigSnapshot(
            profile="evaluation", config_digest="frozen", snapshot_ref="frozen",
            authorized_recipients=["Agnes"], limits=settings.limits,
            timeouts=settings.timeouts, observability=settings.observability,
        ),
        criteria_reference("rev"),
    )
    detail = asyncio.run(workflow.run(task, time.monotonic() + 180))
    outcome = AcceptanceOutcome(
        case=case, detail=detail, gateway=gateway,
        paragraphs={item.paragraph_id: item for item in parsed},
    )
    store.close()
    return outcome
