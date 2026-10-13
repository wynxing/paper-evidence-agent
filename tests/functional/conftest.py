"""Fixtures for the functional-accuracy dimension (测试方案「功能准确性」).

The frozen-sample loader and the doubles that drive it live in :mod:`acceptance`;
this file keeps only the two fixtures. Why they are not in ``conftest.py`` is
explained there (Issue #31) — in short, a bare ``from conftest import ...`` binds
to whichever directory pytest imported first, so it breaks as soon as another
test directory adds its own ``conftest.py``.
"""

import pytest

from acceptance import AcceptanceOutcome, FrozenCase, load_case, run_case


@pytest.fixture
def frozen_case(request):
    return load_case(request.param)


@pytest.fixture
def acceptance(tmp_path):
    """Run one frozen case through the real workflow and return its outcome."""

    def _run(case: FrozenCase, *, transcript=None) -> AcceptanceOutcome:
        return run_case(case, tmp_path, transcript=transcript)

    return _run
