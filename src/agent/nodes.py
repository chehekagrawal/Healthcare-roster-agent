from src.db.duckdb_engine import MetricsEngine
from src.tools.data_query import DataQueryTool
from src.tools.root_cause import RootCauseTracer
from src.tools.report_gen import ReportGenerator

# Initialize your backend engines
engine = MetricsEngine()
query_tool = DataQueryTool(engine)
tracer = RootCauseTracer(engine)
report_gen = ReportGenerator(engine)

def pipeline_health_node(state):
    """
    Pipeline Health Agent Node.
    Analyzes stuck files, health scores, and duration anomalies.
    """
    query = state["messages"][-1].content.lower()
    
    # Logic to decide which of your A2 tools to call
    if "stuck" in query:
        data = query_tool.derive_metrics("stuck_duration")
        context = f"Current stuck files and their durations: {data.to_json()}"
    elif "anomaly" in query or "slow" in query:
        data = query_tool.detect_anomalies()
        context = f"Duration anomalies detected: {data.to_json()}"
    else:
        data = query_tool.derive_metrics("health")
        context = f"Overall pipeline health scores: {data.to_json()}"
    
    return {"messages": [("system", f"Data retrieved from Pipeline Engine: {context}")]}

def market_analytics_node(state):
    """
    Market Analytics Agent Node.
    Handles cross-table joins and root cause tracing.
    """
    query = state["messages"][-1].content.upper()
    
    # Extract state code (simple logic for the demo)
    # In a real run, the LLM provides the state code to this node.
    states = ["GA", "NY", "TX", "CA", "FL", "NH"]
    target_state = next((s for s in states if s in query), "NATIONAL")

    if "root cause" in query.lower() or "why" in query.lower():
        # Call your Extraordinary Root Cause Tool (Bonus Task)
        analysis = tracer.trace_market_failure(target_state)
        context = f"Root Cause Narrative: {analysis['narrative']}"
    else:
        # Call your Cross-Table Join tool
        data = query_tool.cross_table_join(target_state)
        context = f"Market Correlation Data for {target_state}: {data.to_json()}"

    return {"messages": [("system", f"Analysis from Market Engine: {context}")]}

def report_node(state):
    """
    Report Generation Node.
    Triggers the Markdown report generator.
    """
    report = report_gen.generate_pipeline_health_report()
    return {"messages": [("system", f"Generated Operational Report:\n{report}")]}
