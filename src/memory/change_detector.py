from src.db.duckdb_engine import MetricsEngine
from src.memory.episodic import get_last_snapshot


class ChangeDetector:
    """
    Change Detection Engine.
    Compares the live pipeline state with the snapshot saved by the PREVIOUS
    session and reports resolutions, new anomalies and KPI drift.
    """
    def __init__(self, metrics_engine: MetricsEngine, drift_threshold: float = 1.0):
        self.engine = metrics_engine
        self.drift_threshold = drift_threshold

    def detect_all_changes(self, session_id: str = None):
        """
        Returns {"baseline", "resolutions", "new_anomalies", "kpi_drift"}.

        `session_id` is the current session; the comparison is against the
        most recent snapshot from any OTHER session. `baseline` is True when no
        earlier session exists yet, in which case there is nothing to compare
        and all three lists are empty (instead of reporting every currently
        stuck file as "new").
        """
        prev_stuck = get_last_snapshot("stuck_ro_ids", exclude_session=session_id)
        prev_kpis = get_last_snapshot("market_kpi_snapshot", exclude_session=session_id)
        current_stuck = self.engine.get_stuck_ro_ids()

        if prev_stuck is None:
            return {"baseline": True, "resolutions": [], "new_anomalies": [], "kpi_drift": {}}

        prev_set, cur_set = set(prev_stuck), set(current_stuck)
        return {
            "baseline": False,
            # Resolved = stuck last session, not stuck now
            "resolutions": [ro for ro in prev_stuck if ro not in cur_set],
            # New = stuck now, not stuck last session
            "new_anomalies": [ro for ro in current_stuck if ro not in prev_set],
            "kpi_drift": self._detect_kpi_drift(prev_kpis),
        }

    def _detect_kpi_drift(self, prev_kpis):
        """Markets whose latest SCS_PERCENT moved by >= drift_threshold points."""
        if not prev_kpis:
            return {}
        current_kpis = self.engine.get_market_kpi_snapshot()
        drift = {}
        for market, new_val in current_kpis.items():
            old_val = prev_kpis.get(market)
            if old_val is not None and abs(new_val - old_val) >= self.drift_threshold:
                drift[market] = {"old": old_val, "new": new_val}
        return drift

    def format_report(self, session_id: str = None) -> str:
        """Plain-text change report for prompts and logs."""
        changes = self.detect_all_changes(session_id)
        if changes["baseline"]:
            return "--- PIPELINE STATE CHANGE REPORT ---\nFirst session: no earlier snapshot to compare with.\n"
        report = "--- PIPELINE STATE CHANGE REPORT ---\n"
        report += f"RESOLVED: {', '.join(map(str, changes['resolutions'])) or 'None'}\n"
        report += f"NEW ANOMALIES: {', '.join(map(str, changes['new_anomalies'])) or 'None'}\n"
        if changes["kpi_drift"]:
            report += "KPI DRIFT DETECTED:\n"
            for market, d in changes["kpi_drift"].items():
                report += f"   - {market}: {d['old']}% -> {d['new']}%\n"
        else:
            report += "KPI DRIFT: No significant drift.\n"
        return report
