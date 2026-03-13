import sys
import os

# Add the parent directory (root) to the python path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from src.db.duckdb_engine import MetricsEngine
from src.tools.root_cause import RootCauseTracer

engine = MetricsEngine()
tracer = RootCauseTracer(engine)

# Tracing Georgia (GA) which had a very low success rate
result = tracer.trace_market_failure("GA")

print("--- ROOT CAUSE DIAGNOSTIC ---")
print(f"Narrative: {result['narrative']}")
print("\n--- SANKEY FLOW DATA ---")
print(result['sankey_flow'])