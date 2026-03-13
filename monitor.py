"""
src/monitor.py
==============
Proactive Monitoring Agent (C5)

This module uses APScheduler to run background checks every 15 minutes.
It scans the data pipeline for critical anomalies and pushes alerts to the UI.
"""

import time
import logging
from apscheduler.schedulers.background import BackgroundScheduler
from typing import List, Dict

# Setup basic logging for the monitor
logging.basicConfig(level=logging.INFO, format='%(asctime)s - [Monitor] - %(message)s')
logger = logging.getLogger(__name__)

class PipelineMonitor:
    def __init__(self):
        self.scheduler = BackgroundScheduler()
        self.active_alerts: List[Dict] = []
        
        # We will add jobs here in stages
        self.scheduler.add_job(self.check_stuck_ros, 'interval', minutes=15, id='check_stuck_ros')
        self.scheduler.add_job(self.check_market_scs, 'interval', minutes=15, id='check_market_scs')
        self.scheduler.add_job(self.check_duration_anomaly, 'interval', minutes=15, id='check_duration_anomaly')

    def start(self):
        """Starts the background monitoring scheduler."""
        logger.info("Starting Proactive Monitoring Agent...")
        self.scheduler.start()

    def stop(self):
        """Stops the scheduler gracefully."""
        logger.info("Shutting down Proactive Monitoring Agent...")
        self.scheduler.shutdown()
        
    def _create_alert(self, title: str, severity: str, message: str):
        """Helper to format, store, and distribute an alert."""
        alert = {
            "timestamp": time.time(),
            "title": title,
            "severity": severity,
            "message": message
        }
        self.active_alerts.append(alert)
        logger.warning(f"ALERT [{severity}]: {title} - {message}")
        
        # 1. Push to Streamlit session state if running in a UI context
        try:
            import streamlit as st
            if "alerts" not in st.session_state:
                st.session_state.alerts = []
            st.session_state.alerts.append(alert)
        except ImportError:
            pass # Streamlit not installed or running, ignore
        except Exception:
            pass # Outside of Streamlit execution context, ignore
            
        # 2. Log to Episodic Memory
        episodic_event = {
            "session_id": "monitor_background_job",
            "intent": "System generated alert",
            "tools_used": ["proactive_monitor"],
            "final_output": f"Alert Generated: {title} | Severity: {severity}",
            "procedures_run": None
        }
        
        # Note: Calling Engineer 1's SQLite/Chroma Episodic DB writer here
        # from src.memory.episodic import log_episodic_event
        # log_episodic_event(episodic_event)

    # ==========================================
    # CHUNK 1: Monitor Stuck ROs
    # ==========================================
    def check_stuck_ros(self):
        """
        Scans for newly stuck ROs (IS_STUCK = 1).
        This connects to Engineer 1's Data Layer when fully integrated.
        """
        logger.info("Running check: Stuck ROs...")
        
        try:
            # Note: In a live system, this would call src.db.duckdb_engine
            # to run a query like: SELECT COUNT(*) FROM roster_ops WHERE IS_STUCK = 1
            
            # Mocking the detection of 2 new stuck ROs for now
            new_stuck_count = 2 
            
            if new_stuck_count > 0:
                self._create_alert(
                    title="New Stuck Roster Operations",
                    severity="High",
                    message=f"Detected {new_stuck_count} new ROs with IS_STUCK=1 flag."
                )
        except Exception as e:
            logger.error(f"Failed to check stuck ROs: {e}")

    # ==========================================
    # CHUNK 2: Monitor Market SCS_PERCENT
    # ==========================================
    def check_market_scs(self):
        """
        Scans CSV2 for any market where the success rate drops below 95%.
        Fulfills C5 requirement.
        """
        logger.info("Running check: Market SCS_PERCENT...")
        
        try:
            # Note: In a live system, this calls DuckDB for an aggregate
            # SELECT state, AVG(SCS_PERCENT) FROM market_ops GROUP BY state HAVING AVG < 95
            
            # Mocking the discovery of a degraded market
            degraded_markets = [{"state": "FL", "scs": 92.4}]
            
            for market in degraded_markets:
                self._create_alert(
                    title="Market SLA Warning",
                    severity="Medium",
                    message=f"Market {market['state']} has fallen to {market['scs']}% success rate (Below 95% threshold)."
                )
        except Exception as e:
            logger.error(f"Failed to check market SCS_PERCENT: {e}")

    # ==========================================
    # CHUNK 3: Monitor Stage Duration Anomalies
    # ==========================================
    def check_duration_anomaly(self):
        """
        Scans for stages where the actual processing duration is > 2x the historical average.
        Fulfills C5 requirement.
        """
        logger.info("Running check: Stage Duration Anomalies...")
        
        try:
            # Note: In a live system, this runs a SQL diff on DuckDB view:
            # SELECT stage, actual_duration, avg_duration FROM ... WHERE actual_duration > (avg_duration * 2)
            
            # Mocking the discovery of a bottleneck in DART_GEN
            anomalies = [{"stage": "DART_GEN", "actual": 45, "avg": 12}]
            
            for anomaly in anomalies:
                self._create_alert(
                    title="Critical Stage Bottleneck",
                    severity="High",
                    message=f"Stage '{anomaly['stage']}' taking {anomaly['actual']} mins (Normal: {anomaly['avg']} mins). >2x Anomaly detected."
                )
        except Exception as e:
            logger.error(f"Failed to check duration anomalies: {e}")

# Singleton initialization
monitor_agent = PipelineMonitor()

if __name__ == "__main__":
    monitor_agent.start()
    
    # Keep the main thread alive to let the scheduler run for testing
    try:
        print("Monitor running. Press Ctrl+C to exit.")
        # Trigger an immediate run just to prove it works
        monitor_agent.check_stuck_ros() 
        time.sleep(10)
    except KeyboardInterrupt:
        monitor_agent.stop()
