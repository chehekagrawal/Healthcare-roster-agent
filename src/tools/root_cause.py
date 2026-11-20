from src.db.duckdb_engine import MetricsEngine

class RootCauseTracer:
    """
    BONUS CHALLENGE: Root Cause Chaining Engine.
    Traces Market-level failures back to specific Pipeline behaviors, 
    Source Systems, and Organizational patterns.
    """
    def __init__(self, metrics_engine: MetricsEngine):
        self.engine = metrics_engine

    def trace_market_failure(self, state_code: str):
        """
        Performs a 5-level diagnostic to isolate the 
        primary driver of low SCS_PERCENT in a specific market.
        """
        state = state_code.upper()
        
        # 1. Market Context Analysis
        market_stats = self.engine.query(
            "SELECT MONTH, MONTH_DATE, SCS_PERCENT FROM market WHERE MARKET = ? ORDER BY MONTH_DATE",
            [state])
        if market_stats.empty:
            return {"error": f"No market data for {state}",
                    "narrative": f"No market data is available for '{state}'."}
        
        avg_success = market_stats['SCS_PERCENT'].mean()
        latest = market_stats.iloc[-1]
        # Months below the 95% SLA, worst first: an average can hide that a
        # single bad month is responsible for most of the gap.
        breach_months = (market_stats[market_stats['SCS_PERCENT'] < 95.0]
                         .sort_values('SCS_PERCENT'))

        # 2. Source System Attribution (Culprit Scoring)
        # Identifies if one system (e.g. Availity) is providing worse data than others
        source_attribution = self.engine.query("""
            SELECT SRC_SYS, COUNT(*) as fail_count, 
            AVG(IS_FAILED) as fail_rate
            FROM roster 
            WHERE CNT_STATE = ?
            GROUP BY SRC_SYS
            HAVING COUNT(*) >= 20          -- ignore tiny feeds whose rate is noise
            ORDER BY fail_rate DESC
        """, [state])

        # 3. Stage Failure Fingerprinting
        # Finds which of the 7 stages is the most common "Dead End" in this state
        stage_bottleneck = self.engine.query("""
            SELECT LATEST_STAGE_NM, COUNT(*) as count
            FROM roster 
            WHERE CNT_STATE = ? AND (IS_FAILED = 1 OR IS_STUCK = 1)
            GROUP BY LATEST_STAGE_NM ORDER BY count DESC LIMIT 1
        """, [state])

        # 4. LOB Impact Analysis
        lob_impact = self.engine.query("""
            SELECT LOB, COUNT(*) as fail_count
            FROM roster 
            WHERE CNT_STATE = ? AND IS_FAILED = 1
            GROUP BY LOB ORDER BY fail_count DESC LIMIT 1
        """, [state])

        # 5. Organizational Concentration (Is it one hospital or many?)
        org_impact = self.engine.query("""
            SELECT ORG_NM, COUNT(*) as fail_count
            FROM roster 
            WHERE CNT_STATE = ? AND IS_FAILED = 1
            GROUP BY ORG_NM ORDER BY fail_count DESC LIMIT 3
        """, [state])

        # 6. Narrative Synthesis (The "Explainable AI" part)
        primary_source = source_attribution.iloc[0]['SRC_SYS'] if not source_attribution.empty else "Unknown"
        primary_stage = stage_bottleneck.iloc[0]['LATEST_STAGE_NM'] if not stage_bottleneck.empty else "Unknown"
        top_org = org_impact.iloc[0]['ORG_NM'] if not org_impact.empty else "All Orgs"
        top_lob = lob_impact.iloc[0]['LOB'] if not lob_impact.empty else "Unknown"

        if breach_months.empty:
            month_note = "No month fell below the 95% SLA."
        else:
            worst = ", ".join(f"{r.MONTH} ({r.SCS_PERCENT:.2f}%)" for r in breach_months.head(3).itertuples())
            month_note = (f"{len(breach_months)} of {len(market_stats)} months fell below the 95% SLA; "
                          f"the worst were {worst}.")

        narrative = (
            f"Market {state} averages {avg_success:.2f}% success over {len(market_stats)} months "
            f"(latest month {latest['MONTH']}: {latest['SCS_PERCENT']:.2f}%). {month_note} "
            f"Failed or stuck files in this state most often end at the {primary_stage} stage. "
            f"The highest failure rate comes from the {primary_source} source system. "
            f"The line of business with the most failures is {top_lob}. "
            f"The organisation with the most failures is {top_org}."
        )

        # 7. Data for Sankey Diagram (For the Visualizer Tool)
        # This prepares the Nodes and Links for a Flow Diagram: Source -> Stage -> State
        sankey_data = self._prepare_sankey_data(state, source_attribution, stage_bottleneck)

        return {
            "state": state,
            "success_rate": avg_success,
            "latest_month": latest['MONTH'],
            "latest_success_rate": float(latest['SCS_PERCENT']),
            "breach_months": breach_months[['MONTH', 'SCS_PERCENT']].to_dict(orient='records'),
            "primary_culprit_system": primary_source,
            "primary_failure_stage": primary_stage,
            "primary_lob": top_lob,
            "top_failing_orgs": org_impact.to_dict(orient='records'),
            "narrative": narrative,
            "sankey_flow": sankey_data
        }

    def _prepare_sankey_data(self, state, source_df, stage_df):
        """Formats data specifically for Plotly go.Sankey"""
        if source_df.empty or stage_df.empty:
            return None
        
        # This is the "Extraordinary" part: Creating a flow mapping
        # Nodes: [Source, Stage, State]
        source_name = str(source_df.iloc[0]['SRC_SYS'])
        stage_name = str(stage_df.iloc[0]['LATEST_STAGE_NM'])
        
        return {
            "labels": [source_name, stage_name, state],
            "sources": [0, 1], # Source -> Stage, Stage -> State
            "targets": [1, 2],
            "values": [int(source_df.iloc[0]['fail_count']), int(stage_df.iloc[0]['count'])]
        }