"""Service container and FastAPI dependencies.

The store and the HTTP client are created lazily so that importing the API or
answering a request that fails validation never opens a database or a socket.
"""

import os

import httpx

from paper_evidence.agents.prompts import PaperPromptBuilder
from paper_evidence.config import Settings
from paper_evidence.diagnosis.projector import SqliteDiagnosticProjector
from paper_evidence.models.gateway import OpenAIChatGateway
from paper_evidence.sources.crossref import CrossrefClient, DoiResolver
from paper_evidence.sources.http import USER_AGENT, Fetcher
from paper_evidence.sources.openalex import OpenAlexClient
from paper_evidence.sources.pmc import PmcClient
from paper_evidence.sources.service import SourceService
from paper_evidence.storage.sqlite import SqliteStore

__all__ = ["Services", "get_services", "set_services"]


class Services:
    """Lazily built adapters for one process."""

    def __init__(self, settings: Settings) -> None:
        self.settings = settings
        self.prompts = PaperPromptBuilder()
        self._store: SqliteStore | None = None
        self._client: httpx.AsyncClient | None = None

    @property
    def store(self) -> SqliteStore:
        if self._store is None:
            self.settings.data_dir.mkdir(parents=True, exist_ok=True)
            self._store = SqliteStore(self.settings.data_dir / "paper-evidence.sqlite3")
        return self._store

    @property
    def client(self) -> httpx.AsyncClient:
        if self._client is None:
            self._client = httpx.AsyncClient()
        return self._client

    @property
    def projector(self) -> SqliteDiagnosticProjector:
        return SqliteDiagnosticProjector(self.store, self.settings.criteria())

    def _fetcher(self) -> Fetcher:
        user_agent = USER_AGENT
        if self.settings.contact_email:
            user_agent = f"paper-evidence-agent/0.1 (local verification; mailto:{self.settings.contact_email})"
        return Fetcher(self.client, self.settings.timeouts.source_request_seconds, user_agent)

    def source_service(self) -> SourceService:
        fetcher = self._fetcher()
        email = self.settings.contact_email
        return SourceService(
            CrossrefClient(fetcher, self.settings.crossref_base_url, email),
            DoiResolver(fetcher, self.settings.doi_resolver_base_url),
            PmcClient(fetcher, self.settings.pmc_id_converter_url, self.settings.pmc_oai_url, email),
            OpenAlexClient(fetcher, self.settings.openalex_base_url, email),
        )

    def gateway(self) -> OpenAIChatGateway:
        return OpenAIChatGateway(
            self.client,
            base_url=self.settings.model_base_url,
            token=os.environ.get(self.settings.gateway_token_env),
            model_alias=self.settings.model_alias,
            configured_model=self.settings.configured_model,
            deployment_id=self.settings.deployment_id,
            recipient=self.settings.primary_recipient,
            attempt_seconds=self.settings.timeouts.model_attempt_seconds,
        )

    async def aclose(self) -> None:
        if self._client is not None:
            await self._client.aclose()
            self._client = None
        self.close()

    def close(self) -> None:
        if self._store is not None:
            self._store.close()
            self._store = None


_services: Services | None = None


def get_services() -> Services:
    global _services
    if _services is None:
        _services = Services(Settings.from_env())
    return _services


def set_services(services: Services | None) -> None:
    """Replace the process-local container; used by tests and by the worker."""

    global _services
    _services = services
