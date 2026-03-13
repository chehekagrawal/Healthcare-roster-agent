import os
import json
import pandas as pd
from dotenv import load_dotenv
from langchain_community.tools.tavily_search import TavilySearchResults
from src.db.duckdb_engine import MetricsEngine

# Load environment variables
load_dotenv()

# -------------------------------------------------
# 🌐 WEB SEARCH TOOL (Requirement A5/Web Integration)
# -------------------------------------------------
def get_web_search_tool():
    """
    Returns the Tavily search tool for external context.
    """
    if not os.getenv("TAVILY_API_KEY"):
        print("WARNING: TAVILY_API_KEY not found!")
    return TavilySearchResults(max_results=3)


# -------------------------------------------------
# 📊 DATA QUERY TOOL (Requirement A2/A5 Upgrade)
# -------------------------------------------------
class DataQueryTool:
    """
    Task A2: Data Query & Metric Derivation.
    Uses DuckDB (MetricsEngine) to compute operational KPIs and detect anomalies.
    """
    def __init__(self, metrics_engine: MetricsEngine):
        self.engine = metrics_engine

    # Task A2.1: Execute validated SQL
    def query_duckdb(self, sql_query: str):
        """Executes SQL against the roster and market views."""
        try:
            return self.engine.query(sql_query)
        except Exception as e:
            return f"SQL Error: {str(e)}"

    # Task A2.2 & A5 Upgrade: derive_metrics
    def derive_metrics(self, metric_type: str, filters: str = ""):
        """
        Computes the 5 specific metrics requested in Task A2.
        Uses the analytical views created in Task A1.2 (schema.sql).
        """
        where_clause = f"WHERE {filters}" if filters else ""

        if metric_type == "health":
            # composite_health_score: Red flag count across 7 stages
            return self.engine.query(f"SELECT * FROM composite_health_view {where_clause}")

        elif metric_type == "deviation":
            # duration_deviation: actual / AVG_stage_DURATION
            return self.engine.query(f"SELECT * FROM duration_deviation_view {where_clause}")

        elif metric_type == "retry":
            # retry_indicator: RUN_NO > 1 with still-failing status
            return self.engine.query(f"""
                SELECT RO_ID, RUN_NO, LATEST_STAGE_NM, FAILURE_STATUS 
                FROM roster_ops 
                WHERE RUN_NO > 1 AND IS_FAILED = 1 
                {filters.replace('WHERE', 'AND') if filters else ''}
            """)

        elif metric_type == "completion":
            # pipeline_completion_rate: % of files at status 99
            return self.engine.query(f"""
                SELECT 
                    CNT_STATE, 
                    COUNT(*) FILTER (WHERE FILE_STATUS_CD = 99) * 1.0 / COUNT(*) AS completion_rate
                FROM roster_ops 
                {where_clause}
                GROUP BY CNT_STATE ORDER BY completion_rate DESC
            """)

        elif metric_type == "stuck_duration":
            # Task A2.2: DATEDIFF(NOW, LATEST_OBJECT_RUN_DT)
            # FIX: Cast current_timestamp to TIMESTAMP to match the column type
            return self.engine.query(f"""
                SELECT 
                    RO_ID, 
                    ORG_NM,
                    date_diff('minute', CAST(LATEST_OBJECT_RUN_DT AS TIMESTAMP), CAST(current_timestamp AS TIMESTAMP)) as minutes_stuck
                FROM roster_ops 
                WHERE IS_STUCK = 1 
                {filters.replace('WHERE', 'AND') if filters else ''}
            """)

        return None

    # Task A2.3: detect_anomalies
    def detect_anomalies(self, threshold_multiplier: float = 2.0):
        """
        Flags ROs where actual duration > N × AVG.
        N=2 is anomaly, N=3 is critical.
        """
        return self.engine.query(f"""
            SELECT * FROM duration_deviation_view 
            WHERE dart_deviation > {threshold_multiplier} 
               OR dart_ui_deviation > {threshold_multiplier} 
               OR sps_deviation > {threshold_multiplier}
        """)

    # Task A2.4 & A5 Upgrade: cross_table_join
    def cross_table_join(self, state: str):
        """
        Correlates CSV1 health signals with CSV2 SCS_PERCENT.
        """
        return self.engine.query(f"""
            SELECT * FROM cross_state_health_view 
            WHERE CNT_STATE = '{state.upper()}'
        """)

# -------------------------------------------------
# Task A5: Triage Stuck ROs (DuckDB Version)
# -------------------------------------------------
def triage_stuck_ros_v2(engine: MetricsEngine):
    """
    Upgraded version of triage: Uses composite health score 
    from DuckDB to rank stuck files.
    """
    sql = """
    SELECT r.RO_ID, r.ORG_NM, r.LATEST_STAGE_NM, h.composite_health_score
    FROM roster_ops r
    JOIN composite_health_view h ON r.RO_ID = h.RO_ID
    WHERE r.IS_STUCK = 1
    ORDER BY h.composite_health_score ASC
    LIMIT 10
    """
    return engine.query(sql)