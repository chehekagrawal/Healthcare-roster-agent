"""
src/paths.py
============
Single source of truth for file locations.

Runtime files (SQLite databases, ChromaDB folder) used to be relative to the
current working directory, so running from `tests/` or another folder silently
created a second, empty memory. They now live under ROSTERIQ_HOME, which
defaults to the project root and can be overridden (the test suite points it
at a temporary folder).
"""

import os

PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
DATA_DIR = os.getenv("ROSTERIQ_DATA_DIR", os.path.join(PROJECT_ROOT, "data"))
RUNTIME_DIR = os.getenv("ROSTERIQ_HOME", PROJECT_ROOT)

MEMORY_DB = os.path.join(RUNTIME_DIR, "roster_iq_memory.db")
THREADS_DB = os.path.join(RUNTIME_DIR, "roster_iq_threads.db")
CHROMADB_PATH = os.getenv("CHROMADB_PATH", os.path.join(RUNTIME_DIR, "memory", "chromadb"))

ROSTER_CSV = os.path.join(DATA_DIR, "roster_processing_details.csv")
MARKET_CSV = os.path.join(DATA_DIR, "aggregated_operational_metrics.csv")

# The SLA target for SCS_PERCENT, used by the monitor, reports and procedures.
SLA_THRESHOLD = 95.0
