import json
import sqlite3
from src.db.duckdb_engine import MetricsEngine
from src.memory.episodic import get_last_snapshot

class ChangeDetector:
    """
    Task A4: Change Detection Engine.
    Compares current operational state against the previous episodic snapshot.
    Detects: KPI Drift, Resolution of issues, and New Anomalies.
    """
    def __init__(self, metrics_engine: MetricsEngine):
        self.engine = metrics_engine

    def detect_all_changes(self):
        """
        Runs a full comparison of the pipeline and market states.
        Strictly aligned with Task A4 requirements.
        """
        changes = {
            "resolutions": self._detect_resolutions(),
            "new_anomalies": self._detect_new_anomalies(),
            "kpi_drift": self._detect_kpi_drift()
        }
        
        # Format for the Agent to read
        report = "--- PIPELINE STATE CHANGE REPORT ---\n"
        
        if changes["resolutions"]:
            report += f"✅ RESOLVED: {', '.join(changes['resolutions'])}\n"
        else:
            report += "✅ RESOLVED: None\n"
            
        if changes["new_anomalies"]:
            report += f"⚠️ NEW ANOMALIES: {', '.join(changes['new_anomalies'])}\n"
        else:
            report += "⚠️ NEW ANOMALIES: None\n"
            
        if changes["kpi_drift"]:
            report += "📉 KPI DRIFT DETECTED:\n"
            for market, drift in changes["kpi_drift"].items():
                report += f"   - {market}: {drift['old']}% -> {drift['new']}%\n"
        else:
            report += "📉 KPI DRIFT: No significant drift.\n"
            
        return report

    def _detect_resolutions(self):
        """Finds ROs that were stuck in the last session but are now cleared."""
        prev_stuck = get_last_snapshot("stuck_ro_ids")
        if not prev_stuck: return []
        
        current_stuck = self.engine.get_stuck_ro_ids()
        # Resolved = Was in previous, but NOT in current
        return [ro_id for ro_id in prev_stuck if ro_id not in current_stuck]

    def _detect_new_anomalies(self):
        """Finds ROs that are newly stuck since the last session."""
        prev_stuck = get_last_snapshot("stuck_ro_ids")
        current_stuck = self.engine.get_stuck_ro_ids()
        
        if not prev_stuck: return current_stuck
        # New = In current, but WAS NOT in previous
        return [ro_id for ro_id in current_stuck if ro_id not in prev_stuck]

    def _detect_kpi_drift(self, threshold=1.0):
        """Detects if Market Success Rates (SCS_PERCENT) have changed significantly."""
        prev_kpis = get_last_snapshot("market_kpi_snapshot")
        if not prev_kpis: return {}
        
        current_kpis = self.engine.get_market_kpi_snapshot()
        drift = {}
        
        for market, new_val in current_kpis.items():
            old_val = prev_kpis.get(market)
            if old_val is not None and abs(new_val - old_val) >= threshold:
                drift[market] = {"old": old_val, "new": new_val}
                
        return drift