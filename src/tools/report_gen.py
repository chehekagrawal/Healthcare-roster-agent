from src.db.duckdb_engine import MetricsEngine
from datetime import datetime

class ReportGenerator:
    """
    Task A3: Operational Report Generator.
    Produces structured Markdown reports summarizing pipeline health, 
    bottlenecks, and market-level impacts.
    """
    def __init__(self, metrics_engine: MetricsEngine):
        self.engine = metrics_engine

    def generate_pipeline_health_report(self):
        """
        Gathers derived metrics and assembles a Markdown report.
        Strictly aligned with Task A3 requirements.
        """
        # 1. Gather Data
        health_df = self.engine.pipeline_health_score()
        stuck_df = self.engine.stuck_ros()
        market_df = self.engine.market_pipeline_correlation()
        
        # 2. Calculate Aggregates
        avg_health = health_df['pipeline_health_score'].mean()
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

## ⚠️ Active Bottlenecks (Top 5 Critical)
The following Roster Operations (ROs) are currently flagged as `IS_STUCK` and require immediate attention:

| RO_ID | Organization | State | Current Stage | Failure Status |
|-------|--------------|-------|---------------|----------------|
"""
        # Add Stuck RO rows
        for _, row in stuck_df.head(5).iterrows():
            report += f"| {row['RO_ID']} | {row['ORG_NM']} | {row['CNT_STATE']} | {row['LATEST_STAGE_NM']} | {row['FAILURE_STATUS']} |\n"

        report += """
## 📉 Market Correlation Analysis
Correlation between pipeline failures and overall market transaction success rates:

| State | Failed ROs | Stuck ROs | Market Success % |
|-------|------------|-----------|------------------|
"""
        # Add Market Correlation rows
        for _, row in market_df.head(5).iterrows():
            status_icon = "🔴" if row['SCS_PERCENT'] < 95.0 else "🟢"
            report += f"| {row['CNT_STATE']} | {row['failed_ros']} | {row['stuck_ros']} | {row['SCS_PERCENT']}% {status_icon} |\n"

        report += f"""
## 💡 Recommended Actions
1. **Prioritize {total_stuck} Stuck ROs**: Focus on files in the `DART_REVIEW` stage as they represent manual bottlenecks.
2. **Investigate {', '.join(critical_markets[:2])}**: These markets are falling below the 95% threshold; check for source-system specific rejections.
3. **Audit Low Health Scores**: Review the {len(health_df[health_df['pipeline_health_score'] < 0.5])} files with a health score below 0.5.
"""
        return report