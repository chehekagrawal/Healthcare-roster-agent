"""
Test setup.

Every test run uses a fresh, temporary ROSTERIQ_HOME, so tests never touch the
real memory databases, and no API keys, so no network calls are made: the
supervisor uses its keyword fallback and specialists return their data
findings without an AI summary.

These variables must be set before any `src` module is imported, because the
memory modules open their databases at import time.
"""
import os
import sys
import tempfile

_HOME = tempfile.mkdtemp(prefix="rosteriq-test-")
os.environ["ROSTERIQ_HOME"] = _HOME
os.environ.pop("CHROMADB_PATH", None)
os.environ["GOOGLE_API_KEY"] = ""
os.environ["TAVILY_API_KEY"] = ""
os.environ["ANONYMIZED_TELEMETRY"] = "False"

PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

import pytest  # noqa: E402


@pytest.fixture(scope="session")
def engine():
    from src.db.duckdb_engine import MetricsEngine
    return MetricsEngine()


@pytest.fixture()
def fresh_engine():
    """An engine whose tables a test may modify."""
    from src.db.duckdb_engine import MetricsEngine
    return MetricsEngine()
