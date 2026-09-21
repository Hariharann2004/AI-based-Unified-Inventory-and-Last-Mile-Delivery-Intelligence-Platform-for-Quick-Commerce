from __future__ import annotations

from collections.abc import Iterator

import pytest

from src.api.app import app


@pytest.fixture()
def client() -> Iterator:
    app.config.update(TESTING=True)
    with app.test_client() as test_client:
        yield test_client

