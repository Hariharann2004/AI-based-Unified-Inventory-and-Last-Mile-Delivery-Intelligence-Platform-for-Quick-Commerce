from __future__ import annotations

from collections.abc import Iterator

import pytest

from unified_intelligence.api.app import app
from unified_intelligence.infrastructure.persistence.workbench_store import WorkbenchStore


@pytest.fixture()
def client() -> Iterator:
    app.config.update(TESTING=True)
    with app.test_client() as test_client:
        yield test_client


@pytest.fixture()
def work_store(tmp_path):
    return WorkbenchStore(tmp_path / "workbench.db")
