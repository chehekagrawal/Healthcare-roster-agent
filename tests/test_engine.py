from engine.metrics_engine import MetricsEngine

engine = MetricsEngine()

print("\nPipeline Health Scores")
print(engine.pipeline_health_score().head())

print("\nDelay Ratios")
print(engine.stage_delay_ratios().head())

print("\nRetry Overhead")
print(engine.retry_overhead().head())

print("\nState Failure Rates")
print(engine.state_failure_rate().head())

print("\nMarket Correlation")
print(engine.market_pipeline_correlation().head())

print("\nStuck ROs")
print(engine.stuck_ros())