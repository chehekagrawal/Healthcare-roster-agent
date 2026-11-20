from typing import Optional

import pandas as pd
from dotenv import load_dotenv
from src.db.duckdb_engine import MetricsEngine

# Load environment variables
load_dotenv()

HEALTH_COLS = [
    "PRE_PROCESSING_HEALTH",
    "MAPPING_APROVAL_HEALTH",
    "ISF_GEN_HEALTH",
    "DART_GEN_HEALTH",
    "DART_REVIEW_HEALTH",
    "DART_UI_VALIDATION_HEALTH",
    "SPS_LOAD_HEALTH",
]

_RED_COUNT = " + ".join(f"(CASE WHEN {c} = 'Red' THEN 1 ELSE 0 END)" for c in HEALTH_COLS)
_YELLOW_COUNT = " + ".join(f"(CASE WHEN {c} = 'Yellow' THEN 1 ELSE 0 END)" for c in HEALTH_COLS)


# -------------------------------------------------
# 📊 DATA QUERY TOOL
# -------------------------------------------------
class DataQueryTool:
    """
    Data Query & Metric Derivation.
    Uses DuckDB (MetricsEngine) to compute operational KPIs and detect anomalies.
    All user-influenced values (like a state code) are passed as bound
    parameters, never formatted into SQL text.
    """
    def __init__(self, metrics_engine: MetricsEngine):
        self.engine = metrics_engine

    def query_duckdb(self, sql_query: str):
        """Executes a read-only SQL query (SELECT / WITH only)."""
        first_word = sql_query.strip().split(None, 1)[0].upper() if sql_query.strip() else ""
        if first_word not in ("SELECT", "WITH"):
            return "SQL Error: only read-only SELECT queries are allowed."
        try:
            return self.engine.query(sql_query)
        except Exception as e:
            return f"SQL Error: {str(e)}"

    def derive_metrics(self, metric_type: str, state: Optional[str] = None):
        """
        Computes the derived metrics. `state` optionally limits the result
        to one state code.
        """
        state_sql = "AND CNT_STATE = ?" if state else ""
        params = [state.upper()] if state else None

        if metric_type == "health":
            # composite_health_score: 0.0 (all Red) .. 1.0 (all Green)
            return self.engine.query(
                f"SELECT * FROM composite_health_view WHERE TRUE {state_sql}", params)

        elif metric_type == "deviation":
            # duration deviation: actual / historical average per stage
            if state:
                return self.engine.query("""
                    SELECT d.* FROM duration_deviation_view d
                    JOIN (SELECT DISTINCT RO_ID FROM roster WHERE CNT_STATE = ?) r USING (RO_ID)
                """, params)
            return self.engine.query("SELECT * FROM duration_deviation_view")

        elif metric_type == "retry":
            # retry_indicator: RUN_NO > 1 with still-failing status
            return self.engine.query(f"""
                SELECT RO_ID, RUN_NO, LATEST_STAGE_NM, FAILURE_STATUS
                FROM roster
                WHERE RUN_NO > 1 AND IS_FAILED = 1 {state_sql}
            """, params)

        elif metric_type == "completion":
            # pipeline_completion_rate: % of files at status 99 (resolved)
            return self.engine.query(f"""
                SELECT
                    CNT_STATE,
                    COUNT(*) FILTER (WHERE FILE_STATUS_CD = 99) * 1.0 / COUNT(*) AS completion_rate
                FROM roster
                WHERE TRUE {state_sql}
                GROUP BY CNT_STATE ORDER BY completion_rate DESC
            """, params)

        elif metric_type == "stuck_duration":
            return self.engine.query(f"""
                SELECT
                    RO_ID,
                    ORG_NM,
                    CNT_STATE,
                    LATEST_STAGE_NM,
                    date_diff('minute',
                        CAST(LATEST_OBJECT_RUN_DT AS TIMESTAMP),
                        CAST(current_timestamp AS TIMESTAMP)
                    ) as minutes_stuck
                FROM roster
                WHERE IS_STUCK = 1 {state_sql}
            """, params)

        return None

    def detect_anomalies(self, threshold_multiplier: float = 2.0):
        """
        Flags ROs where actual duration > N × historical average.
        N=2 is anomaly, N=3 is critical.
        """
        t = float(threshold_multiplier)
        return self.engine.query("""
            SELECT * FROM duration_deviation_view
            WHERE dart_deviation > ?
               OR dart_ui_deviation > ?
               OR sps_deviation > ?
        """, [t, t, t])

    def cross_table_join(self, state: str):
        """
        Correlates CSV1 health signals with CSV2 SCS_PERCENT for one state
        (one row: latest-month rate plus 12-month average and minimum).
        """
        return self.engine.query(
            "SELECT * FROM cross_state_health_view WHERE CNT_STATE = ?", [state.upper()])

    def national_summary(self):
        """All states, worst latest-month success rate first."""
        return self.engine.market_pipeline_correlation()


# -------------------------------------------------
# Triage Stuck ROs — the single implementation of the escalation score
# -------------------------------------------------
def triage_stuck_ros(engine: MetricsEngine, red_weight: float = 5, yellow_weight: float = 1,
                     time_weight: float = 2, state: Optional[str] = None, limit: int = 10) -> pd.DataFrame:
    """
    Ranks stuck ROs by escalation score:
        red flags × red_weight + yellow flags × yellow_weight + days stuck × time_weight
    Days stuck are measured to the dataset's as-of time (see MetricsEngine.as_of).
    Used by the `triage_stuck_ros` procedure and the stuck-RO chart, so both
    always agree.
    """
    params = [float(red_weight), float(yellow_weight), float(time_weight), engine.as_of, int(limit)]
    if state:
        params.append(state.upper())
    return engine.query(f"""
        WITH s AS (
            SELECT
                RO_ID, ORG_NM, CNT_STATE, LOB, LATEST_STAGE_NM,
                ({_RED_COUNT}) AS red_flags,
                ({_YELLOW_COUNT}) AS yellow_flags,
                GREATEST(date_diff('day', CAST(LATEST_OBJECT_RUN_DT AS TIMESTAMP),
                                   CAST($4 AS TIMESTAMP)), 0) AS days_stuck
            FROM roster
            WHERE IS_STUCK = 1
        )
        SELECT *,
               red_flags * $1 + yellow_flags * $2 + days_stuck * $3 AS escalation_score
        FROM s
        WHERE TRUE {'AND CNT_STATE = $6' if state else ''}
        ORDER BY escalation_score DESC
        LIMIT $5
    """, params)


def triage_stuck_ros_v2(engine: MetricsEngine):
    """Backwards-compatible alias: triage with the default weights."""
    return triage_stuck_ros(engine)
