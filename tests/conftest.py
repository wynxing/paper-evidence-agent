"""Shared test defaults and fixtures."""

import asyncio
import sys
from dataclasses import replace

import pytest

if sys.platform == "win32":
    asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())


@pytest.fixture
def services(tmp_path):
    """A process-local container writing to a temporary data directory."""

    from paper_evidence.api.deps import Services, set_services
    from paper_evidence.config import Settings

    container = Services(replace(Settings.from_env(), data_dir=tmp_path, contact_email=""))
    set_services(container)
    yield container
    container.close()
    set_services(None)


@pytest.fixture
def client(services):
    from fastapi.testclient import TestClient

    from paper_evidence.api.app import app

    with TestClient(app) as http:
        yield http
