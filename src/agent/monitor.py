import sqlite3
import json
import os
from datetime import datetime
from apscheduler.schedulers.background import BackgroundScheduler
from src.db.duckdb_engine import MetricsEngine
from src.memory.episodic import DB_NAME

class ProactiveMonitor:
    """
    Autonomously scans roster and market data for anomalies.
    Surfaces findings as persistent alerts in SQLite.
    Fulfills the 'Proactive monitoring' bonus challenge.
    """
    def __init__(self, engine: MetricsEngine):
        self.engine = engine
        self.scheduler = BackgroundScheduler()
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
                resolved INTEGER DEFAULT 0
            )
        ''')
        conn.commit()
        conn.close()

    def add_alert(self, alert_type: str, severity: str, message: str, meta_dict: dict):
        """Persists a new alert to the database."""
        conn = sqlite3.connect(DB_NAME)
        cursor = conn.cursor()
        # Check if identical active alert already exists to prevent spam
        cursor.execute("SELECT id FROM active_alerts WHERE type=? AND message=? AND resolved=0", (alert_type, message))
        if cursor.fetchone():
            conn.close()
            return

        cursor.execute('''
            INSERT INTO active_alerts (type, severity, message, metadata, timestamp)
            VALUES (?, ?, ?, ?, ?)
        ''', (alert_type, severity, message, json.dumps(meta_dict), datetime.now().isoformat()))
        conn.commit()
        conn.close()
        print(f"[ProactiveMonitor] Alert Raised: {message}")

    def scan_stalled_ros(self):
        """Scans for new stuck ROs."""
        try:
            # Use the correct method from MetricsEngine
            stuck_df = self.engine.stuck_ros()
            if not stuck_df.empty:
                count = len(stuck_df)
                msg = f"Critical Alert: {count} Roster Operations are currently STUCK in the pipeline."
                self.add_alert("PIPELINE_STALL", "High", msg, {"count": count, "ids": stuck_df['RO_ID'].tolist()})
        except Exception as e:
            print(f"Monitor Error (RO): {e}")

    def scan_market_slippage(self):
        """Scans for markets where success rate < 95%."""
        try:
            # Use query() directly for flexibility
            slippage_df = self.engine.query("SELECT MARKET, SCS_PERCENT FROM market WHERE SCS_PERCENT < 95")
            if not slippage_df.empty:
                for _, row in slippage_df.iterrows():
                    market = row['MARKET']
                    scs = row['SCS_PERCENT']
                    msg = f"SLA Warning: Market {market} has dropped to {scs}% success rate (Threshold: 95%)."
                    self.add_alert("MARKET_SLIPPAGE", "Medium", msg, {"market": market, "scs_percent": scs})
        except Exception as e:
            print(f"Monitor Error (Market): {e}")

    def run_immediate_scan(self):
        """Runs all jobs once synchronously."""
        print("[ProactiveMonitor] Running manual system scan...")
        self.scan_stalled_ros()
        self.scan_market_slippage()
        print("[ProactiveMonitor] Manual scan complete.")

    def start(self):
        """Starts the background scheduler."""
        self.scheduler.add_job(self.scan_stalled_ros, 'interval', minutes=5, id='check_stalled')
        self.scheduler.add_job(self.scan_market_slippage, 'interval', minutes=5, id='check_slippage')
        self.scheduler.start()
        print("[ProactiveMonitor] Background scheduler started (5m interval).")

def get_active_alerts(limit=5):
    """Utility to fetch active alerts for UI or Agent consumption."""
    try:
        conn = sqlite3.connect(DB_NAME)
        cursor = conn.cursor()
        cursor.execute("SELECT type, severity, message, timestamp FROM active_alerts WHERE resolved=0 ORDER BY timestamp DESC LIMIT ?", (limit,))
        rows = cursor.fetchall()
        conn.close()
        return [{"type": r[0], "severity": r[1], "message": r[2], "time": r[3]} for r in rows]
    except Exception:
        return []

if __name__ == "__main__":
    # Test script
    engine = MetricsEngine()
    monitor = ProactiveMonitor(engine)
    monitor.run_immediate_scan()
    print("Active Alerts:", get_active_alerts())
