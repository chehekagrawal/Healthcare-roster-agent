import sys
import os
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from src.db.duckdb_engine import MetricsEngine
from src.tools.data_query import DataQueryTool

engine = MetricsEngine()
tool = DataQueryTool(engine)

print("--- Testing Stuck Duration ---")
print(tool.derive_metrics("stuck_duration").head())

print("\n--- Testing Anomalies ---")
print(tool.detect_anomalies(threshold_multiplier=2.0).head())

print("\n--- Testing Cross-Table Join ---")
print(tool.cross_table_join("GA"))