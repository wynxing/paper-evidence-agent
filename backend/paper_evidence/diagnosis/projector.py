"""Diagnostic packet projection for schema 2.2.

The projector reads task records and produces the input diagnostic packet from
术语表「6. 诊断包」. It never changes a task and never runs a second agent. The
``redacted`` packet keeps structure, identifiers, status, usage and the public
bibliographic identity, and replaces claim/query/quote/rationale free text with a
placeholder. The ``consented`` packet is generated locally only and is never
uploaded by the projector.
"""

from paper_evidence.domain.contracts import (
    Decision,
    DiagnosticInput,
    DiagnosticPacket,
    Evidence,
    EvidenceCandidate,
    RunConfigSnapshot,
    SourceRecord,
)

__all__ = ["REDACTION_PLACEHOLDER", "SqliteDiagnosticProjector"]

REDACTION_PLACEHOLDER = "<redacted>"


class SqliteDiagnosticProjector:
    def __init__(self, store, criteria) -> None:
        self._store = store
        self._criteria = criteria

    def redacted(self, task_id: str) -> DiagnosticPacket:
        return self._build(task_id, privacy="redacted", recipient=None)

    def consented(self, task_id: str, recipient: str) -> DiagnosticPacket:
        packet = self._build(task_id, privacy="consented", recipient=recipient)
        self._store.record_diagnostic_export(task_id, recipient)
        return packet

    # ------------------------------------------------------------------ build

    def _build(self, task_id: str, *, privacy: str, recipient: str | None) -> DiagnosticPacket:
        detail = self._store.get(task_id)
        if detail is None:
            raise KeyError(task_id)
        raw = self._store.get_input(task_id) or {}
        run_config = self._store.get_run_config(task_id)
        source = self._store.source_record(task_id)
        candidates = self._store.candidates(task_id)
        decision = detail.decision
        consented = privacy == "consented"

        return DiagnosticPacket(
            schema_version="2.2",
            criteria=detail.criteria,
            accounting=detail.accounting,
            case_id=task_id,
            run_id=f"run:{task_id}",
            trace_id=f"trace:{task_id}",
            previous_id=raw.get("previous_id"),
            cancel_requested=bool(raw.get("cancel_requested")),
            status=detail.status,
            label=detail.label,
            error_code=detail.error_code,
            input=DiagnosticInput(
                doi=raw.get("doi", ""),
                claim=raw.get("claim", "") if consented else REDACTION_PLACEHOLDER,
                privacy="consented" if consented else "redacted",
                recipient=recipient,
            ),
            source=_source(source) if source is not None else None,
            run_config=run_config if run_config is not None else _empty_run_config(detail),
            evidence_candidates=[_candidate(item, consented) for item in candidates],
            decision=_decision(decision, consented),
            execution=self._store.execution(task_id),
            model_calls=self._store.model_calls(task_id),
        )


def _source(source: SourceRecord) -> SourceRecord:
    # Bibliographic fields are public and kept; the preview states this boundary.
    return source


def _empty_run_config(detail) -> RunConfigSnapshot:
    return RunConfigSnapshot(
        profile="daily", config_digest="", snapshot_ref="", authorized_recipients=[],
        limits=detail.limits, timeouts=_default_timeouts(), observability=_default_observability(),
    )


def _default_timeouts():
    from paper_evidence.domain.contracts import default_timeouts

    return default_timeouts()


def _default_observability():
    from paper_evidence.domain.contracts import Observability

    return Observability(langfuse_enabled=False, recipient=None)


def _candidate(candidate: EvidenceCandidate, consented: bool) -> EvidenceCandidate:
    if consented:
        return candidate
    return candidate.model_copy(update={"quote": REDACTION_PLACEHOLDER})


def _decision(decision: Decision | None, consented: bool) -> Decision | None:
    if decision is None:
        return None
    if consented:
        return decision
    return Decision(
        agent=decision.agent,
        label=decision.label,
        rationale=REDACTION_PLACEHOLDER,
        supported_parts=[REDACTION_PLACEHOLDER for _ in decision.supported_parts],
        scope_differences=[REDACTION_PLACEHOLDER for _ in decision.scope_differences],
        limitations=[REDACTION_PLACEHOLDER for _ in decision.limitations],
        evidence=[_evidence(item) for item in decision.evidence],
        validation="pass",
    )


def _evidence(item: Evidence) -> Evidence:
    return Evidence(
        paragraph_id=item.paragraph_id,
        quote=REDACTION_PLACEHOLDER,
        section=item.section,
        source_url=item.source_url,
        paragraph_hash=item.paragraph_hash,
        validation="pass",
    )
