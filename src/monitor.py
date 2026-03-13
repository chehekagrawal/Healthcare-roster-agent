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

    def start(self):
        """Starts the background monitoring scheduler."""
        logger.info("Starting Proactive Monitoring Agent...")
        self.scheduler.start()

    def stop(self):
        """Stops the scheduler gracefully."""
        logger.info("Shutting down Proactive Monitoring Agent...")
        self.scheduler.shutdown()
        
    def _create_alert(self, title: str, severity: str, message: str):
        """Helper to format and store an alert."""
        alert = {
            "timestamp": time.time(),
            "title": title,
            "severity": severity,
            "message": message
        }
        self.active_alerts.append(alert)
        logger.warning(f"ALERT [{severity}]: {title} - {message}")

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
