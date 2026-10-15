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

__all__ = ["Settings", "config_snapshot", "endpoint_class", "narrowed_snapshot"]

MODEL_ALIAS = "paper-default"
MODEL_TRANSPORT_SDK = "sdk"
MODEL_TRANSPORT_GATEWAY = "gateway"
DEFAULT_MODEL_TRANSPORT = MODEL_TRANSPORT_SDK
MODEL_TRANSPORTS = (MODEL_TRANSPORT_SDK, MODEL_TRANSPORT_GATEWAY)
DEFAULT_MODEL_BASE_URL = "http://127.0.0.1:4000"
# 提示词版本：冻结配置快照的 ``prompts.version`` 与每次模型调用记账的
# ``ModelCall.prompt_version`` 都取本常量（``agents`` 从这里导入）。改提示词文本
# 只需在这里发布新版本，不会出现记账版本与真实提示词不符（Issue #62）。
PROMPT_VERSION = "paper-prompt-0.2.0"
PARSER_VERSION = "jats-0.1.0"
RETRIEVAL_CONTEXT_LIMIT = 12
DATA_SCOPE = ["claim_text", "candidate_open_paragraphs"]

DEFAULT_CONFIGURED_MODEL = "agnes-2.5-flash"
DEFAULT_DEPLOYMENT_ID = "agnes-primary"
# The provider-qualified name the SDK dispatches to. LiteLLM keeps the provider
# adaptation; the application still only names the alias and this one mapping.
DEFAULT_PROVIDER_MODEL = "openai/agnes-2.5-flash"


def _implementation_revision() -> str:
    return os.environ.get("PAPER_EVIDENCE_REVISION", "unknown")


def _clean(value: str | None) -> str | None:
    """Trim a configured identifier; an all-whitespace value counts as unset.

    A recipient written as ``"A, B"`` must not become ``" B"``: the trailing space
    would not match the value the client echoes back, and the frozen digest would
    disagree with the preview. Configuration is the single place this is fixed.
    """

    if value is None:
        return None
    return value.strip() or None


@dataclass(frozen=True)
class Settings:
    """Everything the process reads from its environment."""

    profile: Profile = "daily"
    data_dir: Path = field(default_factory=lambda: Path.cwd() / ".paper-evidence")
    primary_recipient: str = "Agnes"
    fallback_recipients: tuple[str, ...] = ()
    model_transport: str = DEFAULT_MODEL_TRANSPORT
    model_alias: str = MODEL_ALIAS
    provider_model: str = DEFAULT_PROVIDER_MODEL
    model_api_base: str = ""
    model_api_key_env: str = "PAPER_EVIDENCE_MODEL_API_KEY"
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
    # The legacy host www.ncbi.nlm.nih.gov/pmc/oai/oai.cgi now answers with a 301
    # to this API path; point at the canonical address directly.
    pmc_oai_url: str = "https://pmc.ncbi.nlm.nih.gov/api/oai/v1/mh/"
    openalex_base_url: str = "https://api.openalex.org"
    contact_email: str = ""
    retrieval_context_limit: int = RETRIEVAL_CONTEXT_LIMIT
    implementation_revision: str = field(default_factory=_implementation_revision)

    @classmethod
    def from_env(cls) -> "Settings":
        data_dir = os.environ.get("PAPER_EVIDENCE_DATA_DIR")
        profile = os.environ.get("PAPER_EVIDENCE_PROFILE", "daily")
        fallback = tuple(
            item for item in (
                _clean(part) for part in os.environ.get("PAPER_EVIDENCE_FALLBACK_RECIPIENTS", "").split(",")
            ) if item
        )
        langfuse = os.environ.get("PAPER_EVIDENCE_LANGFUSE_ENABLED", "").lower() in {"1", "true", "yes"}
        # 已授权观测/诊断接收方，与模型接收方分开。它与 langfuse_enabled 解耦：
        # 否则不开启观测导出就无法授权任何诊断接收方。
        recipient = _clean(
            os.environ.get("PAPER_EVIDENCE_OBSERVABILITY_RECIPIENT")
            or os.environ.get("PAPER_EVIDENCE_LANGFUSE_RECIPIENT")
        )
        # 未知取值按既有的 profile 处理方式回落到默认值；生效的传输方式会写进
        # 冻结快照，因此预览显示的是实际使用的那一种，不会与实际调用不符。
        transport = (os.environ.get("PAPER_EVIDENCE_MODEL_TRANSPORT") or "").strip().lower()
        return cls(
            profile="evaluation" if profile == "evaluation" else "daily",
            data_dir=Path(data_dir) if data_dir else Path.cwd() / ".paper-evidence",
            primary_recipient=_clean(os.environ.get("PAPER_EVIDENCE_PRIMARY_RECIPIENT")) or "Agnes",
            fallback_recipients=fallback,
            model_transport=transport if transport in MODEL_TRANSPORTS else DEFAULT_MODEL_TRANSPORT,
            provider_model=_clean(os.environ.get("PAPER_EVIDENCE_PROVIDER_MODEL")) or DEFAULT_PROVIDER_MODEL,
            model_api_base=_clean(os.environ.get("PAPER_EVIDENCE_MODEL_API_BASE")) or "",
            model_base_url=_clean(os.environ.get("PAPER_EVIDENCE_MODEL_BASE_URL")) or DEFAULT_MODEL_BASE_URL,
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


def endpoint_class(settings: Settings) -> str:
    """Which kind of endpoint the effective transport will actually reach.

    The concrete address stays out of the snapshot: a host and port are local
    deployment detail, while the class of endpoint is what the frozen config has
    to pin so the preview cannot silently describe a different route than the one
    used. ``local_gateway`` is a separate process, ``configured_endpoint`` is an
    address given in configuration, and ``provider_default`` is the endpoint the
    provider adapter resolves on its own.
    """

    if settings.model_transport == MODEL_TRANSPORT_GATEWAY:
        return "local_gateway"
    return "configured_endpoint" if settings.model_api_base else "provider_default"


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
            "transport": settings.model_transport,
            "base_url_class": endpoint_class(settings),
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
