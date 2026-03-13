from src.db.duckdb_engine import MetricsEngine
from src.tools.report_gen import ReportGenerator

engine = MetricsEngine()
gen = ReportGenerator(engine)

markdown_report = gen.generate_pipeline_health_report()
print(markdown_report)