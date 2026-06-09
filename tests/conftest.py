from __future__ import annotations

import pytest


@pytest.fixture(autouse=True)
def isolate_public_base_url_env(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("PRISM_PUBLIC_BASE_URL", raising=False)
