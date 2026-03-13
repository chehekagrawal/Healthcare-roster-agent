import duckdb
import pandas as pd

class MetricsEngine:

    def __init__(self):
        """
        Initializes the DuckDB in-memory connection and loads the
        Healthcare Roster datasets.
        """
        # Create in-memory DuckDB connection
        self.con = duckdb.connect(database=':memory:')

        # Load CSV 1: Pipeline Details
        # read_csv_auto is used to handle the 53-column structure dynamically
        self.con.execute("""
        CREATE TABLE roster AS
        SELECT * FROM read_csv_auto('data/roster_processing_details.csv')
        """)

        # Load CSV 2: Market Aggregates
        self.con.execute("""
        CREATE TABLE market AS
        SELECT * FROM read_csv_auto('data/aggregated_operational_metrics.csv')
        """)

    # -------------------------------------------------
    # BASIC DATA ACCESS
    # -------------------------------------------------

    def query(self, sql):
        """
        Generic query tool to execute raw SQL and return a dataframe.
        """
        return self.con.execute(sql).df()

    # -------------------------------------------------
    # DERIVED METRIC 1 — PIPELINE HEALTH SCORE
    # -------------------------------------------------

    def pipeline_health_score(self):
        """
        Calculates a numerical 0-1 score based on Green/Yellow/Red flags.
        This provides the success signal missing from raw counts.
        """
        return self.query("""
        SELECT
            RO_ID,
            ORG_NM,
            (
            CASE PRE_PROCESSING_HEALTH
                WHEN 'Green' THEN 1
                WHEN 'Yellow' THEN 0.5
                ELSE 0
            END +

            CASE MAPPING_APROVAL_HEALTH
                WHEN 'Green' THEN 1
                WHEN 'Yellow' THEN 0.5
                ELSE 0
            END +

            CASE ISF_GEN_HEALTH
                WHEN 'Green' THEN 1
                WHEN 'Yellow' THEN 0.5
                ELSE 0
            END +

            CASE DART_GEN_HEALTH
                WHEN 'Green' THEN 1
                WHEN 'Yellow' THEN 0.5
                ELSE 0
            END +

            CASE DART_REVIEW_HEALTH
                WHEN 'Green' THEN 1
                WHEN 'Yellow' THEN 0.5
                ELSE 0
            END +

            CASE DART_UI_VALIDATION_HEALTH
                WHEN 'Green' THEN 1
                WHEN 'Yellow' THEN 0.5
                ELSE 0
            END +

            CASE SPS_LOAD_HEALTH
                WHEN 'Green' THEN 1
                WHEN 'Yellow' THEN 0.5
                ELSE 0
            END
            ) / 7.0 AS pipeline_health_score

        FROM roster
        """)

    # -------------------------------------------------
    # DERIVED METRIC 2 — STAGE DELAY RATIOS
    # -------------------------------------------------

    def stage_delay_ratios(self):
        """
        Detects time-based anomalies by comparing against AVG duration.
        Uses NULLIF to prevent division by zero errors.
        """
        return self.query("""
        SELECT
            RO_ID,

            DART_GEN_DURATION /
            NULLIF(AVG_DART_GENERATION_DURATION, 0)
            AS dart_delay_ratio,

            DART_UI_VALIDATION_DURATION /
            NULLIF(AVG_DART_UI_VLDTN_DURATION, 0)
            AS dart_ui_delay_ratio,

            SPS_LOAD_DURATION /
            NULLIF(AVG_SPS_LOAD_DURATION, 0)
            AS sps_delay_ratio

        FROM roster
        """)

    # -------------------------------------------------
    # DERIVED METRIC 3 — RETRY OVERHEAD
    # -------------------------------------------------

    def retry_overhead(self):
        """
        Calculates how much extra work is spent on reprocessing (RUN_NO > 1).
        """
        return self.query("""
        SELECT
            RO_ID,
            RUN_NO,
            RUN_NO - 1 AS retry_overhead
        FROM roster
        WHERE RUN_NO > 1
        """)

    # -------------------------------------------------
    # DERIVED METRIC 4 — STATE FAILURE RATE
    # -------------------------------------------------

    def state_failure_rate(self):
        """
        Calculates failure percentage per US state.
        """
        return self.query("""
        SELECT
            CNT_STATE,
            COUNT(*) FILTER (WHERE IS_FAILED = 1) * 1.0 /
            COUNT(*) AS failure_rate
        FROM roster
        GROUP BY CNT_STATE
        ORDER BY failure_rate DESC
        """)

    # -------------------------------------------------
    # DERIVED METRIC 5 — MARKET PIPELINE CORRELATION
    # -------------------------------------------------

    def market_pipeline_correlation(self):
        """
        Joins Market Success % (CSV 2) with Pipeline Stalls (CSV 1).
        """
        return self.query("""
        SELECT
            r.CNT_STATE,
            COUNT(*) FILTER (WHERE r.IS_FAILED = 1) AS failed_ros,
            COUNT(*) FILTER (WHERE r.IS_STUCK = 1) AS stuck_ros,
            m.SCS_PERCENT

        FROM roster r
        JOIN market m
        ON r.CNT_STATE = m.MARKET

        GROUP BY r.CNT_STATE, m.SCS_PERCENT
        ORDER BY m.SCS_PERCENT ASC
        """)

    # -------------------------------------------------
    # DERIVED METRIC 6 — STUCK ROs
    # -------------------------------------------------

    def stuck_ros(self):
        """
        Returns actionable data for all currently stuck operations.
        """
        return self.query("""
        SELECT
            RO_ID,
            ORG_NM,
            CNT_STATE,
            LATEST_STAGE_NM,
            IS_STUCK,
            FAILURE_STATUS
        FROM roster
        WHERE IS_STUCK = 1
        """)

    # -------------------------------------------------
    # MEMORY HELPERS (NEW: Essential for Memory Architecture)
    # -------------------------------------------------

    def get_stuck_ro_ids(self):
        """
        Provides a list of IDs for the episodic snapshot system.
        """
        df = self.query("SELECT RO_ID FROM roster WHERE IS_STUCK = 1")
        return df['RO_ID'].tolist()

    def get_market_metrics_snapshot(self):
        """
        Provides dictionary of current SCS_PERCENT for drift detection.
        """
        df = self.query("SELECT MARKET, SCS_PERCENT FROM market")
        return df.set_index('MARKET')['SCS_PERCENT'].to_dict()

    # -------------------------------------------------
    # VISUALIZATION DATA EXPORT
    # -------------------------------------------------

    def get_market_trend_data(self, state):
        """
        Returns monthly history for a specific market state.
        """
        return self.query(f"""
            SELECT MONTH, SCS_PERCENT 
            FROM market 
            WHERE MARKET = '{state.upper()}' 
            ORDER BY MONTH ASC
        """)