"""
visualizer.py
================================================================================
Visualization Engine for RosterIQ.
Contains the Visualizer class which generates Plotly figures for operational 
intelligence, including heatmaps, trend lines, and anomaly charts.

Strictly aligned with Task A3 of the Implementation Plan.
================================================================================
"""

import plotly.express as px
import plotly.graph_objects as go
import pandas as pd
from src.db.duckdb_engine import MetricsEngine

class Visualizer:
    """
    Standardized Visualization Engine.
    All methods return a Plotly Figure object for inline rendering in Streamlit.
    """

    def __init__(self, metrics_engine: MetricsEngine):
        """
        Initializes the visualizer with the DuckDB analytical engine.
        """
        self.engine = metrics_engine

    # ── 1. Market SCS_PERCENT Trend ───────────────────────────────────────────
    
    def plot_market_trend(self, market_code: str):
        """
        Line chart of SCS_PERCENT over time for a given market.
        Includes a 95% threshold reference line as per problem statement specs.
        """
        # Fetching monthly history for the specific market
        market_df = self.engine.get_market_trend_data(market_code)
        
        if market_df.empty:
            return None

        # Create the base line chart
        fig = px.line(
            market_df,
            x="MONTH",
            y="SCS_PERCENT",
            title=f"Market Transaction Success Trend — {market_code.upper()}",
            markers=True,
            labels={"SCS_PERCENT": "Success Rate (%)", "MONTH": "Month"},
            line_shape='spline', # Smoother professional look
            render_mode='svg'
        )

        # 95% threshold — strictly required per problem statement visualization spec
        fig.add_hline(
            y=95,
            line_dash="dash",
            line_color="#FF4B4B", # Standard professional red
            annotation_text="95% SLA Threshold",
            annotation_position="bottom right",
        )

        # Apply Dark Glassmorphism compatible styling
        fig.update_layout(
            template="plotly_dark",
            height=400,
            paper_bgcolor='rgba(0,0,0,0)',
            plot_bgcolor='rgba(0,0,0,0)',
            font=dict(family="Inter, sans-serif", size=12)
        )

        return fig

    # ── 2. Pipeline Stage Health Heatmap ──────────────────────────────────────
    
    def plot_pipeline_health_heatmap(self):
        """
        Org × Stage matrix coloured Green/Yellow/Red by health flag.
        Renders the top 20 riskiest ROs based on Red flag count.
        """
        # Query the full dataset via DuckDB
        df_pipeline = self.engine.query("SELECT * FROM roster_ops")
        
        health_cols = [
            "PRE_PROCESSING_HEALTH",
            "MAPPING_APROVAL_HEALTH",
            "ISF_GEN_HEALTH",
            "DART_GEN_HEALTH",
            "DART_REVIEW_HEALTH",
            "DART_UI_VALIDATION_HEALTH",
            "SPS_LOAD_HEALTH",
        ]

        # Ensure we only use columns that exist in the current dataframe
        existing_cols = [c for c in health_cols if c in df_pipeline.columns]
        
        df_pipeline = df_pipeline.copy()
        
        # Calculate red flags to rank the most critical files
        df_pipeline["RED_COUNT"] = (df_pipeline[existing_cols] == "Red").sum(axis=1)
        
        # Select top 20 problematic ROs
        df_sample = df_pipeline.nlargest(20, "RED_COUNT")[["RO_ID"] + existing_cols]

        # Melt the data for Heatmap compatibility
        df_melted = df_sample.melt(
            id_vars=["RO_ID"], 
            value_vars=existing_cols,
            var_name="Stage", 
            value_name="Health"
        )

        # Categorical to Numerical mapping for the colorscale
        # Green=1, Yellow=2, Red=3
        color_map = {"Green": 1, "Yellow": 2, "Red": 3}
        df_melted["Health_Num"] = df_melted["Health"].map(color_map).fillna(0)
        
        # Clean up stage names for the X-axis
        df_melted["Stage"] = df_melted["Stage"].str.replace("_HEALTH", "").str.replace("_", " ")

        fig = go.Figure(
            data=go.Heatmap(
                z=df_melted["Health_Num"],
                x=df_melted["Stage"],
                y=df_melted["RO_ID"].astype(str),
                # Custom discrete colorscale matching industry standards
                colorscale=[
                    [0, "#2d2d2d"],      # Background
                    [0.33, "#2ecc71"],   # Green
                    [0.66, "#f39c12"],   # Yellow
                    [1, "#e74c3c"]       # Red
                ],
                showscale=False,
                text=df_melted["Health"],
                hovertemplate="RO: %{y}<br>Stage: %{x}<br>Health: %{text}<extra></extra>",
            )
        )

        fig.update_layout(
            title="Pipeline Stage Health Heatmap — Top 20 Riskiest ROs",
            template="plotly_dark",
            height=500,
            xaxis_title="Pipeline Stage",
            yaxis_title="Roster Operation ID",
            paper_bgcolor='rgba(0,0,0,0)',
            plot_bgcolor='rgba(0,0,0,0)',
            font=dict(family="Inter, sans-serif")
        )

        return fig

    # ── 3. Duration Anomaly Chart ─────────────────────────────────────────────
    
    def plot_duration_anomaly(self, anomaly_threshold: float = 2.0):
        """
        Bar chart: actual vs AVG duration per stage.
        Highlighting stages that exceed historical averages.
        """
        # Fetching pre-calculated deviations from our DuckDB view
        df_deviation = self.engine.query("SELECT * FROM duration_deviation_view")
        
        # Calculate means for the summary bar chart
        summary_data = [
            {"Stage": "DART GEN", "Ratio": df_deviation["dart_deviation"].mean()},
            {"Stage": "DART UI", "Ratio": df_deviation["dart_ui_deviation"].mean()},
            {"Stage": "SPS LOAD", "Ratio": df_deviation["sps_deviation"].mean()}
        ]
        
        df_plot = pd.DataFrame(summary_data)
        
        # Determine status based on thresholds (2x = Anomaly, 3x = Critical)
        df_plot["Status"] = df_plot["Ratio"].apply(
            lambda x: "Critical" if x > 3.0 else ("Anomaly" if x > anomaly_threshold else "Normal")
        )

        # Mapping colors to status
        color_map = {"Normal": "#2ecc71", "Anomaly": "#f39c12", "Critical": "#e74c3c"}

        fig = px.bar(
            df_plot, 
            x="Stage", 
            y="Ratio",
            color="Status",
            color_discrete_map=color_map,
            title=f"Duration Anomaly Chart (>{anomaly_threshold}x = Anomaly)",
            labels={"Ratio": "Deviation Ratio (Actual/Avg)"}
        )
        
        # Horizontal lines to visually indicate the danger zones
        fig.add_hline(y=1.0, line_dash="dot", line_color="white", annotation_text="Historical Avg")
        fig.add_hline(y=anomaly_threshold, line_dash="dot", line_color="#f39c12")
        
        fig.update_layout(
            template="plotly_dark", 
            height=400,
            paper_bgcolor='rgba(0,0,0,0)',
            plot_bgcolor='rgba(0,0,0,0)',
            font=dict(family="Inter, sans-serif")
        )

        return fig

    # ── 4. Retry Lift Chart ───────────────────────────────────────────────────
    
    def plot_retry_lift(self, top_n: int = 10):
        """
        Grouped bar chart showing recovery of successful transactions.
        Compares First Pass Success vs. Final Success after Reprocessing.
        """
        df_market = self.engine.query("SELECT * FROM market_ops")
        
        # Aggregating by market to show total volume recovery
        df_agg = (
            df_market.groupby("MARKET")[["FIRST_ITER_SCS_CNT", "NEXT_ITER_SCS_CNT"]]
            .sum()
            .reset_index()
            .sort_values("FIRST_ITER_SCS_CNT", ascending=False)
            .head(top_n)
        )

        fig = go.Figure()

        # Trace 1: Successes on the very first try
        fig.add_trace(go.Bar(
            name="First Pass Success", 
            x=df_agg["MARKET"], 
            y=df_agg["FIRST_ITER_SCS_CNT"], 
            marker_color="#00C9FF" # Tech Cyan
        ))

        # Trace 2: Successes recovered after RUN_NO > 1
        fig.add_trace(go.Bar(
            name="Retry Recovery", 
            x=df_agg["MARKET"], 
            y=df_agg["NEXT_ITER_SCS_CNT"], 
            marker_color="#92FE9D" # Neon Green
        ))

        fig.update_layout(
            barmode="group",
            title=f"Retry Lift — First Pass vs Retry Success (Top {top_n} Markets)",
            template="plotly_dark",
            height=400,
            xaxis_title="Market State",
            yaxis_title="Transaction Count",
            paper_bgcolor='rgba(0,0,0,0)',
            plot_bgcolor='rgba(0,0,0,0)',
            font=dict(family="Inter, sans-serif")
        )

        return fig

    # ── 5. Stuck RO Tracker ───────────────────────────────────────────────────
    
    def plot_stuck_ro_tracker(self):
        """
        ULTRA-UPGRADED: Horizontal bar chart with sophisticated 'Sunset Heat' palette.
        Signals urgency without the eye-strain of bright yellow.
        """
        df_pipeline = self.engine.query("SELECT * FROM roster_ops")
        health_cols = [c for c in df_pipeline.columns if c.endswith("_HEALTH")]
        
        stuck = df_pipeline[df_pipeline["IS_STUCK"] == 1].copy()
        if stuck.empty:
            return None

        # Logic: Weighted scoring to differentiate severity
        stuck["RED_FLAGS"] = (stuck[health_cols] == "Red").sum(axis=1)
        stuck["YELLOW_FLAGS"] = (stuck[health_cols] == "Yellow").sum(axis=1)
        stuck["COMPOSITE_SCORE"] = (stuck["RED_FLAGS"] * 5) + (stuck["YELLOW_FLAGS"] * 2) + 1
        
        stuck = stuck.sort_values("COMPOSITE_SCORE", ascending=True).tail(15)

        # Pro-Typography: Using HTML spans for subtle state/org info
        label = stuck.apply(
            lambda r: f"<b>{r['RO_ID']}</b><br><span style='color:#808495'>{r['CNT_STATE']} | {r['ORG_NM'][:18]}</span>",
            axis=1,
        )
        
        # Professional Custom Colorscale (Deep Purple -> Deep Red -> Burnt Orange)
        custom_heat = [
            [0.0, '#4b1248'],   # Deep Purple (Lowest risk)
            [0.5, '#f01010'],   # Professional Red (Medium risk)
            [1.0, '#ff8c00']    # Burnt Orange/Amber (Highest priority)
        ]

        fig = go.Figure(go.Bar(
            x=stuck["COMPOSITE_SCORE"],
            y=label,
            orientation="h",
            marker=dict(
                color=stuck["COMPOSITE_SCORE"], 
                colorscale=custom_heat,
                line=dict(color='rgba(255, 255, 255, 0.1)', width=1)
            ),
            text=stuck["LATEST_STAGE_NM"],
            textposition='inside',
            insidetextanchor='start',
            textfont=dict(color='white', size=11, family="Inter"),
            hovertemplate="<b>Escalation Score:</b> %{x}<br><b>Current Stage:</b> %{text}<extra></extra>",
        ))
        
        fig.update_layout(
            title="🚨 <b>Roster Operations Escalation Matrix</b>",
            margin=dict(l=160, r=20, t=60, b=40),
            template="plotly_dark",
            height=500,
            xaxis_title="Priority Score (Higher = Urgent Intervention)",
            paper_bgcolor='rgba(0,0,0,0)',
            plot_bgcolor='rgba(0,0,0,0)',
            xaxis=dict(showgrid=False, zeroline=False),
            yaxis=dict(showgrid=False),
            font=dict(family="Inter, sans-serif")
        )

        return fig

# ──────────────────────────────────────────────────────────────────────────────
# End of Visualizer Class
# ──────────────────────────────────────────────────────────────────────────────