"""Runtime configuration, frozen config snapshot and its digest.

``config_digest`` summarizes the frozen effective snapshot described in
术语表「调用账与版本归属」. The snapshot must expand defaults, so every value
this process actually uses is written in explicitly. Authorization narrowing is
handled by the caller, which writes the narrowed snapshot per task rather than
widening the preview.
"""

import os
from dataclasses import dataclass, field
from pathlib import Path

from .domain.contracts import (
    CriteriaReference,
    Limits,
    Observability,
    Profile,
    RunConfigSnapshot,
    Timeouts,
    default_limits,
    default_timeouts,
)
from .domain.digest import digest_of
from .domain.rules import criteria_reference

__all__ = ["Settings", "config_snapshot", "narrowed_snapshot"]

MODEL_ALIAS = "paper-default"
DEFAULT_MODEL_BASE_URL = "http://127.0.0.1:4000"
PROMPT_VERSION = "paper-prompt-0.1.0"
PARSER_VERSION = "jats-0.1.0"
RETRIEVAL_CONTEXT_LIMIT = 12
DATA_SCOPE = ["claim_text", "candidate_open_paragraphs"]

DEFAULT_CONFIGURED_MODEL = "agnes-2.5-flash"
DEFAULT_DEPLOYMENT_ID = "agnes-primary"


def _implementation_revision() -> str:
    return os.environ.get("PAPER_EVIDENCE_REVISION", "unknown")


@dataclass(frozen=True)
class Settings:
    """Everything the process reads from its environment."""

    profile: Profile = "daily"
    data_dir: Path = field(default_factory=lambda: Path.cwd() / ".paper-evidence")
    primary_recipient: str = "Agnes"
    fallback_recipients: tuple[str, ...] = ()
    model_alias: str = MODEL_ALIAS
    model_base_url: str = DEFAULT_MODEL_BASE_URL
    gateway_token_env: str = "PAPER_EVIDENCE_GATEWAY_TOKEN"
    configured_model: str = DEFAULT_CONFIGURED_MODEL
    deployment_id: str = DEFAULT_DEPLOYMENT_ID
    data_scope: tuple[str, ...] = tuple(DATA_SCOPE)
    limits: Limits = field(default_factory=default_limits)
    timeouts: Timeouts = field(default_factory=default_timeouts)
    observability: Observability = field(default_factory=lambda: Observability(langfuse_enabled=False, recipient=None))
    crossref_base_url: str = "https://api.crossref.org"
    doi_resolver_base_url: str = "https://doi.org"
    pmc_id_converter_url: str = "https://pmc.ncbi.nlm.nih.gov/tools/idconv/api/v1/articles/"
    pmc_oai_url: str = "https://www.ncbi.nlm.nih.gov/pmc/oai/oai.cgi"
    openalex_base_url: str = "https://api.openalex.org"
    contact_email: str = ""
    retrieval_context_limit: int = RETRIEVAL_CONTEXT_LIMIT
    implementation_revision: str = field(default_factory=_implementation_revision)

    @classmethod
    def from_env(cls) -> "Settings":
        data_dir = os.environ.get("PAPER_EVIDENCE_DATA_DIR")
        profile = os.environ.get("PAPER_EVIDENCE_PROFILE", "daily")
        fallback = tuple(item for item in os.environ.get("PAPER_EVIDENCE_FALLBACK_RECIPIENTS", "").split(",") if item)
        langfuse = os.environ.get("PAPER_EVIDENCE_LANGFUSE_ENABLED", "").lower() in {"1", "true", "yes"}
        # 已授权观测/诊断接收方，与模型接收方分开。它与 langfuse_enabled 解耦：
        # 否则不开启观测导出就无法授权任何诊断接收方。
        recipient = (
            os.environ.get("PAPER_EVIDENCE_OBSERVABILITY_RECIPIENT")
            or os.environ.get("PAPER_EVIDENCE_LANGFUSE_RECIPIENT")
            or None
        )
        return cls(
            profile="evaluation" if profile == "evaluation" else "daily",
            data_dir=Path(data_dir) if data_dir else Path.cwd() / ".paper-evidence",
            primary_recipient=os.environ.get("PAPER_EVIDENCE_PRIMARY_RECIPIENT", "Agnes"),
            fallback_recipients=fallback,
            model_base_url=os.environ.get("PAPER_EVIDENCE_MODEL_BASE_URL", DEFAULT_MODEL_BASE_URL),
            contact_email=os.environ.get("PAPER_EVIDENCE_CONTACT_EMAIL", ""),
            observability=Observability(langfuse_enabled=langfuse, recipient=recipient),
        )

    def criteria(self) -> CriteriaReference:
        return CriteriaReference(**criteria_reference(self.implementation_revision))

    def snapshot(self, authorized_recipients: tuple[str, ...] | None = None) -> RunConfigSnapshot:
        recipients = tuple(authorized_recipients) if authorized_recipients is not None else (
            self.primary_recipient, *self.fallback_recipients
        )
        return RunConfigSnapshot(
            profile=self.profile,
            config_digest="",
            snapshot_ref="",
            authorized_recipients=list(recipients),
            limits=self.limits,
            timeouts=self.timeouts,
            observability=self.observability,
        )

    def run_config(self, authorized_recipients: tuple[str, ...] | None = None) -> dict[str, object]:
        """The full frozen snapshot expanded for configuration-digest purposes."""

        return config_snapshot(self, authorized_recipients)

    def config_digest(self, authorized_recipients: tuple[str, ...] | None = None) -> str:
        return digest_of(config_snapshot(self, authorized_recipients))


def config_snapshot(settings: Settings, authorized_recipients: tuple[str, ...] | None = None) -> dict[str, object]:
    """The expanded config snapshot written into ``config_digest``.

    Run id, claim/DOI, source text, evidence, timestamps, counters, tokens,
    results and the digest/reference itself never enter this snapshot.
    """

    recipients = list(authorized_recipients) if authorized_recipients is not None else [
        settings.primary_recipient, *settings.fallback_recipients
    ]
    return {
        "profile": settings.profile,
        "model": {
            "alias": settings.model_alias,
            "base_url_class": "local_gateway",
            "configured_model": settings.configured_model,
            "deployment_id": settings.deployment_id,
            "params": {"temperature": 0, "cache": False},
        },
        "routing": {
            "primary_recipient": settings.primary_recipient,
            "fallback_recipients": list(settings.fallback_recipients),
            "authorized_recipients": recipients,
            "allow_fallback": settings.profile == "daily" and bool(settings.fallback_recipients),
        },
        "prompts": {"version": PROMPT_VERSION},
        "retrieval": {
            "tokenizer": "unicode61",
            "rank": "bm25",
            "query_operator": "OR",
            "context_limit": settings.retrieval_context_limit,
        },
        "source_parser_version": PARSER_VERSION,
        "recovery": {
            "client_retries": False,
            "attempts_per_request": settings.limits.attempts_per_request,
            "cache": False,
        },
        "limits": settings.limits.model_dump(),
        "timeouts": settings.timeouts.model_dump(),
        "observability": settings.observability.model_dump(),
        "criteria": criteria_reference(settings.implementation_revision),
    }


def narrowed_snapshot(settings: Settings, authorized_recipients: tuple[str, ...]) -> RunConfigSnapshot:
    """Store the narrowed effective snapshot; never widen the preview range."""

    digest = digest_of(config_snapshot(settings, authorized_recipients))
    return settings.snapshot(authorized_recipients).model_copy(
        update={"config_digest": digest, "snapshot_ref": f"config:sha256:{digest}"}
    )
