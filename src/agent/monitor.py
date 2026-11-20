import sqlite3
import json
import threading
from datetime import datetime
from apscheduler.schedulers.background import BackgroundScheduler
from src.db.duckdb_engine import MetricsEngine
from src.memory.episodic import DB_NAME
from src.paths import SLA_THRESHOLD

SCAN_INTERVAL_MINUTES = 5


class ProactiveMonitor:
    """
    Autonomously scans roster and market data for anomalies and keeps a set of
    persistent alerts in SQLite in step with the data (the 'Proactive
    monitoring' bonus challenge).

    Each scan RECONCILES alerts rather than only adding them:
      - a condition that is new gets a new alert;
      - a condition that is unchanged keeps its existing alert (no duplicates);
      - a condition that changed (e.g. 2 stuck files -> 3) resolves the old
        alert and raises an updated one;
      - a condition that has cleared resolves its alert.
    Alerts are identified by `alert_key` (one per stall set / per market).
    """
    def __init__(self, engine: MetricsEngine):
        self.engine = engine
        self.scheduler = BackgroundScheduler()
        self._started = False
        self._scan_lock = threading.Lock()
        self.init_alert_table()

    def init_alert_table(self):
        """Ensures the alerts table exists in the episodic memory DB."""
        conn = sqlite3.connect(DB_NAME)
        cursor = conn.cursor()
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS active_alerts (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                type TEXT,
                severity TEXT,
                message TEXT,
                metadata TEXT,
                timestamp DATETIME,
                resolved INTEGER DEFAULT 0,
                alert_key TEXT,
                resolved_at DATETIME
            )
        ''')
        # Migrate tables created before alerts had keys / resolution times.
        cols = [r[1] for r in cursor.execute("PRAGMA table_info(active_alerts)")]
        if "alert_key" not in cols:
            cursor.execute("ALTER TABLE active_alerts ADD COLUMN alert_key TEXT")
        if "resolved_at" not in cols:
            cursor.execute("ALTER TABLE active_alerts ADD COLUMN resolved_at DATETIME")
        conn.commit()
        conn.close()

    # ── Alert storage ─────────────────────────────────────────────────────────

    def add_alert(self, alert_type: str, severity: str, message: str, meta_dict: dict, alert_key: str = None):
        """Persists a new alert unless an identical one is already open (de-duplication)."""
        alert_key = alert_key or alert_type
        conn = sqlite3.connect(DB_NAME)
        cursor = conn.cursor()
        cursor.execute(
            "SELECT id FROM active_alerts WHERE alert_key=? AND message=? AND resolved=0",
            (alert_key, message))
        if cursor.fetchone():
            conn.close()
            return False
        cursor.execute('''
            INSERT INTO active_alerts (type, severity, message, metadata, timestamp, alert_key)
            VALUES (?, ?, ?, ?, ?, ?)
        ''', (alert_type, severity, message, json.dumps(meta_dict, default=str),
              datetime.now().isoformat(), alert_key))
        conn.commit()
        conn.close()
        print(f"[ProactiveMonitor] Alert Raised: {message}")
        return True

    def _reconcile(self, alert_type: str, desired: dict):
        """
        desired = {alert_key: (severity, message, metadata)} for every condition
        that holds right now. Resolves open alerts of this type that are no
        longer wanted (cleared or changed), then raises the missing ones.
        """
        conn = sqlite3.connect(DB_NAME)
        cursor = conn.cursor()
        open_rows = cursor.execute(
            "SELECT id, alert_key, message FROM active_alerts WHERE type=? AND resolved=0",
            (alert_type,)).fetchall()
        now = datetime.now().isoformat()
        for alert_id, key, message in open_rows:
            wanted = desired.get(key)
            if wanted is None or wanted[1] != message:
                cursor.execute("UPDATE active_alerts SET resolved=1, resolved_at=? WHERE id=?",
                               (now, alert_id))
        conn.commit()
        conn.close()
        for key, (severity, message, meta) in desired.items():
            self.add_alert(alert_type, severity, message, meta, alert_key=key)

    # ── Scans ─────────────────────────────────────────────────────────────────

    def scan_stalled_ros(self):
        """One High alert describing the current set of stuck ROs (if any)."""
        try:
            stuck_df = self.engine.stuck_ros()
            desired = {}
            if not stuck_df.empty:
                ids = sorted(stuck_df['RO_ID'].astype(str).tolist())
                count = len(ids)
                shown = ", ".join(ids[:5]) + (" ..." if count > 5 else "")
                msg = f"Critical Alert: {count} Roster Operation(s) currently STUCK in the pipeline: {shown}."
                desired["PIPELINE_STALL"] = ("High", msg, {"count": count, "ids": ids})
            self._reconcile("PIPELINE_STALL", desired)
        except Exception as e:
            print(f"Monitor Error (RO): {e}")

    def scan_market_slippage(self):
        """
        One Medium alert per market whose LATEST month is below the SLA.
        (The old scan checked every month row, raising ~129 alerts, many about
        months long past, and phrased them all as "has dropped to".)
        """
        try:
            df = self.engine.query(
                # best first, so the worst market is inserted last = newest = shown first
                "SELECT MARKET, MONTH, SCS_PERCENT FROM market_latest WHERE SCS_PERCENT < ? ORDER BY SCS_PERCENT DESC",
                [SLA_THRESHOLD])
            desired = {}
            for _, row in df.iterrows():
                market, month, scs = row['MARKET'], row['MONTH'], float(row['SCS_PERCENT'])
                msg = (f"SLA Warning: Market {market} was at {scs:.2f}% success in its latest month "
                       f"({month}), below the {SLA_THRESHOLD:g}% target.")
                desired[f"MARKET_SLIPPAGE:{market}"] = (
                    "Medium", msg, {"market": market, "month": month, "scs_percent": scs})
            self._reconcile("MARKET_SLIPPAGE", desired)
        except Exception as e:
            print(f"Monitor Error (Market): {e}")

    def run_immediate_scan(self):
        """Runs all checks once, synchronously (also used by the scheduler)."""
        with self._scan_lock:
            self.scan_stalled_ros()
            self.scan_market_slippage()

    def start(self):
        """Starts the background scheduler (safe to call more than once)."""
        if self._started:
            return
        self.scheduler.add_job(self.run_immediate_scan, 'interval', minutes=SCAN_INTERVAL_MINUTES,
                               id='proactive_scan', replace_existing=True,
                               max_instances=1, coalesce=True)
        self.scheduler.start()
        self._started = True
        print(f"[ProactiveMonitor] Background scheduler started ({SCAN_INTERVAL_MINUTES}m interval).")

    def shutdown(self):
        if self._started:
            self.scheduler.shutdown(wait=False)
            self._started = False


def get_active_alerts(limit=5):
    """Open alerts for the UI or the agent: High severity first, then newest."""
    try:
        conn = sqlite3.connect(DB_NAME)
        cursor = conn.cursor()
        cursor.execute('''
            SELECT type, severity, message, timestamp FROM active_alerts
            WHERE resolved=0
            ORDER BY CASE severity WHEN 'High' THEN 0 WHEN 'Medium' THEN 1 ELSE 2 END,
                     timestamp DESC
            LIMIT ?
        ''', (limit,))
        rows = cursor.fetchall()
        conn.close()
        return [{"type": r[0], "severity": r[1], "message": r[2], "time": r[3]} for r in rows]
    except Exception:
        return []


if __name__ == "__main__":
    engine = MetricsEngine()
    monitor = ProactiveMonitor(engine)
    monitor.run_immediate_scan()
    print("Active Alerts:", get_active_alerts())
