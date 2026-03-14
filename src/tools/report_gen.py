from datetime import datetime
from src.db.duckdb_engine import MetricsEngine
from src.tools.data_query import DataQueryTool

class ReportGenerator:
    """
    Operational Report Generator.
    Produces structured Markdown reports summarizing pipeline health, 
    bottlenecks, and market-level impacts.
    """
    def __init__(self, metrics_engine: MetricsEngine):
        self.engine = metrics_engine
        # Initialize the query tool to access 
        self.query_tool = DataQueryTool(metrics_engine)

    def generate_pipeline_health_report(self):
        """
        Gathers derived metrics and assembles an advanced Markdown report.
        Strictly aligned with Task A3 requirements.
        """
        # 1. Gather Data using the A2 Metric Engine
        health_df = self.query_tool.derive_metrics("health")
        stuck_df = self.query_tool.derive_metrics("stuck_duration")
        market_df = self.engine.market_pipeline_correlation()
        anomalies_df = self.query_tool.detect_anomalies(threshold_multiplier=2.0)
        
        # 2. Calculate Aggregates
        avg_health = health_df['composite_health_score'].mean()
        total_stuck = len(stuck_df)
        
        # Get unique state codes and sort them alphabetically
        critical_markets = sorted(market_df[market_df['SCS_PERCENT'] < 95.0]['CNT_STATE'].unique().tolist())

        # 3. Build Markdown String
        report = f"""
# 📋 Provider Roster: Pipeline Health Report
**Generated on:** {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}

## 🚀 Executive Summary
- **Overall Pipeline Health Score:** `{avg_health:.2f} / 1.0`
- **Total Stuck Operations:** `{total_stuck}`
- **Critical Markets (<95% Success):** {', '.join(critical_markets) if critical_markets else 'None'}

## ⚠️ Active Bottlenecks (Prioritized by Duration)
The following ROs are currently stalled. 'Minutes Stuck' represents the time since the last successful stage update.

| RO_ID | Organization | State | Current Stage | Minutes Stuck |
|-------|--------------|-------|---------------|---------------|
"""
        # Add Stuck RO rows with the new 'minutes_stuck' metric
        for _, row in stuck_df.sort_values('minutes_stuck', ascending=False).head(5).iterrows():
            report += f"| {row['RO_ID']} | {row['ORG_NM']} | {row['CNT_STATE']} | {row['LATEST_STAGE_NM']} | {int(row['minutes_stuck'])} |\n"

        report += """
## 📉 Market Correlation Analysis
Correlation between pipeline failures and overall market transaction success rates:

| State | Failed ROs | Stuck ROs | Market Success % |
|-------|------------|-----------|------------------|
"""
        # Add Market Correlation rows
        for _, row in market_df.sort_values('SCS_PERCENT', ascending=True).head(5).iterrows():
            status_icon = "🔴" if row['SCS_PERCENT'] < 95.0 else "🟢"
            report += f"| {row['CNT_STATE']} | {row['failed_ros']} | {row['stuck_ros']} | {row['SCS_PERCENT']}% {status_icon} |\n"

        report += """
## 🔍 Duration Anomalies (Actual > 2x Average)
ROs exhibiting significant deviation from historical processing times:

| RO_ID | Stage | Deviation Ratio |
|-------|-------|-----------------|
"""
        # Add Anomalies 
        for _, row in anomalies_df.head(5).iterrows():
            # Find which stage had the anomaly
            ratio = max(
    row.get('dart_deviation', 0) or 0,
    row.get('dart_ui_deviation', 0) or 0,
    row.get('sps_deviation', 0) or 0
)
            report += f"| {row['RO_ID']} | Pipeline Stage | {ratio:.2f}x |\n"

        report += f"""
## 💡 Recommended Actions
1. **Prioritize {total_stuck} Stuck ROs**: Immediate intervention required for files stuck longer than 24 hours.
2. **Investigate {', '.join(critical_markets[:3])}**: These markets show critical KPI drift.
3. **Optimize Anomalies**: Review the {len(anomalies_df)} files exceeding historical duration averages.
"""
        return report