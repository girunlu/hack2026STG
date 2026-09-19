"""Shared pytest fixtures for the T1 regression harness.

The dataset is loaded once per session; every test reuses the same ``Dataset`` and the same
``TestClient`` so the 18 MB of JSON is read exactly once.
"""

from __future__ import annotations

import os

import pytest
from fastapi.testclient import TestClient

from app.domain import index


@pytest.fixture(scope="session", autouse=True)
def _isolated_runtime_stores(tmp_path_factory):
    """Keep runtime state out of the repo for the whole session.

    Client uploads and imported ex-custody portfolios are *runtime* state that normally lives under
    ``data/``. Without this, a demo import or upload changes what the suite sees — the dataset grows
    and absolute-count assertions fail for reasons unrelated to the code under test.
    """
    root = tmp_path_factory.mktemp("runtime")
    os.environ["URO_UPLOAD_DIR"] = str(root / "uploads")
    os.environ["URO_EXCUSTODY_DIR"] = str(root / "excustody")
    # The harness must not touch the network: a briefing that reaches Bing inside a test is a flaky
    # test. Offline mode keeps every stage in place and declares market news unavailable.
    os.environ["URO_NEWS_OFFLINE"] = "1"
    # Nor may it call a paid model. `.env` holds a real key on a developer machine, and with it every
    # answer and briefing would hit the API: slow, nondeterministic and billed. Tests that need the
    # LLM stub `_chat` and set a key themselves (test_llm_renderer, test_assistant_grounding,
    # test_browse); everything else exercises the deterministic path, which is the contract.
    for name in ("DEEPSEEK_API_KEY", "URO_LLM_API_KEY"):
        os.environ.pop(name, None)
    yield
    os.environ.pop("URO_UPLOAD_DIR", None)
    os.environ.pop("URO_EXCUSTODY_DIR", None)
    os.environ.pop("URO_NEWS_OFFLINE", None)


@pytest.fixture(scope="session")
def dataset():
    """Process-wide dataset; loaded once for the whole test session."""
    return index.load(force=True)


def pytest_addoption(parser):
    """Add --run-harness flag to enable the full snapshot drill."""
    parser.addoption(
        "--run-harness",
        action="store_true",
        default=False,
        help="run the full harness over all 47 clients",
    )


@pytest.fixture(scope="session")
def api():
    """FastAPI ``TestClient`` bound to the already-loaded app (no network)."""
    from app.main import app

    with TestClient(app) as client:
        yield client
