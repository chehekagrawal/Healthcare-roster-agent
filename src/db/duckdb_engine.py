import os
import duckdb
import pandas as pd
import threading

from src.paths import ROSTER_CSV, MARKET_CSV


class MetricsEngine:

    def __init__(self, roster_path: str = ROSTER_CSV, market_path: str = MARKET_CSV):
        """
        Initializes the DuckDB in-memory connection and loads the
        Healthcare Roster datasets.
        """
        # Create in-memory DuckDB connection. One connection is shared by the
        # Streamlit thread and the monitor thread, so every query takes a lock.
        self.con = duckdb.connect(database=':memory:')
        self.lock = threading.Lock()

        # roster_ops / market_ops stay as views over the raw CSVs (kept for
        # backwards compatibility); everything else reads the loaded tables.
        # (DDL can't take bound parameters, so the path is quoted safely instead.)
        q = lambda p: "'" + str(p).replace("'", "''") + "'"
        self.con.execute(f"CREATE VIEW roster_ops AS SELECT * FROM read_csv_auto({q(roster_path)})")
        self.con.execute(f"CREATE VIEW market_ops AS SELECT * FROM read_csv_auto({q(market_path)})")

        self.con.execute("CREATE TABLE roster AS SELECT * FROM roster_ops")

        # MONTH is text in "MM-YYYY" form, which sorts wrongly as a string
        # ("01-2026" < "02-2025"). MONTH_DATE is the real date to order by.
        self.con.execute("""
            CREATE TABLE market AS
            SELECT *, CAST(try_strptime(MONTH, '%m-%Y') AS DATE) AS MONTH_DATE
            FROM market_ops
        """)

        self._load_schema()

        # The data is a historical extract. "How long has this file been stuck?"
        # is measured against the extract's own latest activity time, not
        # today's date (which would add a year of fake waiting to every file).
        self.as_of = self.con.execute(
            "SELECT LEAST(MAX(LATEST_OBJECT_RUN_DT), CAST(current_timestamp AS TIMESTAMP)) FROM roster"
        ).fetchone()[0]

    def _load_schema(self):
        """
        Reads and executes schema.sql, which creates the analytical views.
        A broken schema is a hard error: every agent tool depends on these views.
        """
        schema_path = os.path.join(os.path.dirname(__file__), "schema.sql")
        with open(schema_path, 'r') as f:
            self.con.execute(f.read())

    # -------------------------------------------------
    # BASIC DATA ACCESS
    # -------------------------------------------------

    def query(self, sql, params=None):
        """
        Executes SQL and returns a DataFrame.
        Pass user-supplied values through `params` (with ? placeholders),
        never by formatting them into the SQL string.
        Thread-safe: a lock plus a fresh cursor per query.
        """
        with self.lock:
            try:
                cur = self.con.cursor()
                if params is None:
                    return cur.execute(sql).df()
                return cur.execute(sql, params).df()
            except Exception as e:
                print(f"[DuckDB Analysis Error]: {e}")
                raise

    def known_states(self):
        """All state codes present in either dataset (used for whole-word matching)."""
        df = self.query("""
            SELECT DISTINCT CNT_STATE AS s FROM roster WHERE CNT_STATE IS NOT NULL
            UNION
            SELECT DISTINCT MARKET FROM market WHERE MARKET IS NOT NULL
        """)
        return sorted(str(s).upper() for s in df["s"].tolist())

    # -------------------------------------------------
    # DERIVED METRIC 1 — PIPELINE HEALTH SCORE
    # -------------------------------------------------

    def pipeline_health_score(self):
        """Composite health score per RO (0.0 = all Red, 1.0 = all Green)."""
        return self.query("SELECT * FROM composite_health_view")

    # -------------------------------------------------
    # DERIVED METRIC 2 — STAGE DELAY RATIOS
    # -------------------------------------------------

    def stage_delay_ratios(self):
        return self.query("SELECT * FROM duration_deviation_view")

    # -------------------------------------------------
    # DERIVED METRIC 3 — RETRY OVERHEAD
    # -------------------------------------------------

    def retry_overhead(self):
        """How much extra work is spent on reprocessing (RUN_NO > 1)."""
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
        """Failure percentage per US state."""
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
        One row per state: failed / stuck ROs (CSV 1) next to the state's
        latest-month SCS_PERCENT and 12-month average (CSV 2).
        """
        return self.query("""
        SELECT * FROM cross_state_health_view
        ORDER BY SCS_PERCENT ASC
        """)

    # -------------------------------------------------
    # DERIVED METRIC 6 — STUCK ROs
    # -------------------------------------------------

    def stuck_ros(self):
        """Actionable data for all currently stuck operations."""
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
    # MEMORY HELPERS (change detection snapshots)
    # -------------------------------------------------

    def get_stuck_snapshot(self):
        """Currently stuck ROs (ID, stage, org) for change detection."""
        df = self.query("""
            SELECT RO_ID, LATEST_STAGE_NM, ORG_NM
            FROM roster
            WHERE IS_STUCK = 1
        """)
        return df.to_dict(orient='records')

    def get_market_kpi_snapshot(self):
        """
        {market: SCS_PERCENT} using each market's LATEST month.
        (Previously this took an arbitrary month per market, so drift
        detection compared unrelated months.)
        """
        df = self.query("SELECT MARKET, SCS_PERCENT FROM market_latest")
        return {str(k): float(v) for k, v in zip(df["MARKET"], df["SCS_PERCENT"])}

    def get_stuck_ro_ids(self):
        """Simple list of stuck RO IDs for set comparison in change_detector.py."""
        df = self.query("SELECT RO_ID FROM roster WHERE IS_STUCK = 1")
        return df['RO_ID'].tolist()

    # -------------------------------------------------
    # VISUALIZATION DATA EXPORT
    # -------------------------------------------------

    def get_market_trend_data(self, state):
        """Monthly history for one market, in true chronological order."""
        return self.query("""
            SELECT MONTH, MONTH_DATE, SCS_PERCENT
            FROM market
            WHERE MARKET = ?
            ORDER BY MONTH_DATE ASC
        """, [state.upper()])
