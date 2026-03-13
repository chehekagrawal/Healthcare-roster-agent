"""
visualizations.py
==================
Partner A — Plotly chart generators.
All functions return a Plotly figure object (rendered inline in Streamlit).

IMPORTANT: SCS_PERCENT threshold is 95% (per problem statement).
"""

import plotly.express as px
import plotly.graph_objects as go
import pandas as pd


# ── 1. Market SCS_PERCENT Trend ──────────────────────────────
def plot_market_trend(df_market: pd.DataFrame, market_code: str):
    """
    Line chart of SCS_PERCENT over time for a given market.
    Includes 95% threshold reference line (per problem statement).
    """
    market_df = (
        df_market[df_market["MARKET"] == market_code.upper()]
        .sort_values("MONTH")
    )
    if market_df.empty:
        return None

    fig = px.line(
        market_df,
        x="MONTH",
        y="SCS_PERCENT",
        title=f"Market Transaction Success Trend — {market_code.upper()}",
        markers=True,
        labels={"SCS_PERCENT": "Success Rate (%)", "MONTH": "Month"},
    )
    # 95% threshold — per problem statement visualization spec
    fig.add_hline(
        y=95,
        line_dash="dash",
        line_color="red",
        annotation_text="95% Threshold",
        annotation_position="bottom right",
    )
    fig.update_layout(template="plotly_dark", height=400)
    return fig


# ── 2. Pipeline Stage Health Heatmap ─────────────────────────
def plot_pipeline_health_heatmap(df_pipeline: pd.DataFrame):
    """
    Org × Stage matrix coloured Green/Yellow/Red by health flag.
    Includes all 7 stage-health columns.
    """
    health_cols = [
        "PRE_PROCESSING_HEALTH",
        "MAPPING_APROVAL_HEALTH",
        "ISF_GEN_HEALTH",
        "DART_GEN_HEALTH",
        "DART_REVIEW_HEALTH",
        "DART_UI_VALIDATION_HEALTH",
        "SPS_LOAD_HEALTH",
    ]
    # Use top 20 ROs with most Red flags
    existing_cols = [c for c in health_cols if c in df_pipeline.columns]
    df_pipeline = df_pipeline.copy()
    df_pipeline["RED_COUNT"] = (df_pipeline[existing_cols] == "Red").sum(axis=1)
    df_sample = df_pipeline.nlargest(20, "RED_COUNT")[["RO_ID"] + existing_cols]

    df_melted = df_sample.melt(
        id_vars=["RO_ID"], value_vars=existing_cols,
        var_name="Stage", value_name="Health"
    )
    color_map = {"Green": 1, "Yellow": 2, "Red": 3}
    df_melted["Health_Num"] = df_melted["Health"].map(color_map).fillna(0)
    df_melted["Stage"] = df_melted["Stage"].str.replace("_HEALTH", "").str.replace("_", " ")

    fig = go.Figure(
        data=go.Heatmap(
            z=df_melted["Health_Num"],
            x=df_melted["Stage"],
            y=df_melted["RO_ID"].astype(str),
            colorscale=[[0, "#2d2d2d"], [0.33, "#2ecc71"], [0.66, "#f39c12"], [1, "#e74c3c"]],
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
    )
    return fig


# ── 3. Duration Anomaly Chart ─────────────────────────────────
def plot_duration_anomaly(df_pipeline: pd.DataFrame, anomaly_threshold: float = 2.0):
    """
    Bar chart: actual vs AVG duration per stage.
    Bars exceeding anomaly_threshold × AVG are highlighted red.
    """
    stage_pairs = [
        ("PRE_PROCESSING_DURATION", "AVG_PRE_PROCESSING_DURATION"),
        ("MAPPING_APROVAL_DURATION", "AVG_MAPPING_APROVAL_DURATION"),
        ("ISF_GEN_DURATION", "AVG_ISF_GENERATION_DURATION"),
        ("DART_GEN_DURATION", "AVG_DART_GENERATION_DURATION"),
        ("DART_REVIEW_DURATION", "AVG_DART_UI_VLDTN_DURATION"),
        ("SPS_LOAD_DURATION", "AVG_SPS_LOAD_DURATION"),
    ]
    rows = []
    for actual_col, avg_col in stage_pairs:
        if actual_col in df_pipeline.columns and avg_col in df_pipeline.columns:
            avg_actual = df_pipeline[actual_col].mean()
            avg_hist = df_pipeline[avg_col].mean()
            ratio = avg_actual / avg_hist if avg_hist > 0 else 0
            stage_name = actual_col.replace("_DURATION", "").replace("_", " ")
            rows.append({
                "Stage": stage_name,
                "Avg Actual (min)": round(avg_actual, 1),
                "Avg Historical (min)": round(avg_hist, 1),
                "Ratio": round(ratio, 2),
                "Status": "Critical" if ratio > 3.0 else ("Anomaly" if ratio > anomaly_threshold else "Normal"),
            })

    df_plot = pd.DataFrame(rows)
    color_map = {"Normal": "#2ecc71", "Anomaly": "#f39c12", "Critical": "#e74c3c"}

    fig = go.Figure()
    fig.add_trace(go.Bar(
        name="Avg Historical",
        x=df_plot["Stage"], y=df_plot["Avg Historical (min)"],
        marker_color="#5dade2", opacity=0.6,
    ))
    fig.add_trace(go.Bar(
        name="Avg Actual",
        x=df_plot["Stage"], y=df_plot["Avg Actual (min)"],
        marker_color=[color_map[s] for s in df_plot["Status"]],
    ))
    fig.update_layout(
        barmode="overlay",
        title=f"Duration Anomaly Chart (>{anomaly_threshold}× = Anomaly, >3× = Critical)",
        template="plotly_dark",
        height=400,
        xaxis_title="Pipeline Stage",
        yaxis_title="Duration (minutes)",
    )
    return fig


# ── 4. Retry Lift Chart ───────────────────────────────────────
def plot_retry_lift(df_market: pd.DataFrame, top_n: int = 10):
    """
    Grouped bar: FIRST_ITER_SCS_CNT vs NEXT_ITER_SCS_CNT per market.
    Shows how much retries recover failed transactions.
    """
    df_agg = (
        df_market.groupby("MARKET")[["FIRST_ITER_SCS_CNT", "NEXT_ITER_SCS_CNT"]]
        .sum()
        .reset_index()
        .sort_values("FIRST_ITER_SCS_CNT", ascending=False)
        .head(top_n)
    )
    fig = go.Figure()
    fig.add_trace(go.Bar(name="First Pass Success", x=df_agg["MARKET"], y=df_agg["FIRST_ITER_SCS_CNT"], marker_color="#2ecc71"))
    fig.add_trace(go.Bar(name="Retry Recovery", x=df_agg["MARKET"], y=df_agg["NEXT_ITER_SCS_CNT"], marker_color="#f39c12"))
    fig.update_layout(
        barmode="group",
        title=f"Retry Lift — First Pass vs Retry Success (Top {top_n} Markets)",
        template="plotly_dark",
        height=400,
        xaxis_title="Market",
        yaxis_title="Transaction Count",
    )
    return fig


# ── 5. Stuck RO Tracker ───────────────────────────────────────
def plot_stuck_ro_tracker(df_pipeline: pd.DataFrame):
    """
    Horizontal bar: IS_STUCK=1 ROs ranked by Red flag count + failure indication.
    """
    health_cols = [c for c in df_pipeline.columns if c.endswith("_HEALTH")]
    stuck = df_pipeline[df_pipeline["IS_STUCK"] == 1].copy()
    if stuck.empty:
        return None

    stuck["RED_FLAGS"] = (stuck[health_cols] == "Red").sum(axis=1)
    stuck["YELLOW_FLAGS"] = (stuck[health_cols] == "Yellow").sum(axis=1)
    stuck["COMPOSITE_SCORE"] = stuck["RED_FLAGS"] * 3 + stuck["YELLOW_FLAGS"]
    stuck = stuck.sort_values("COMPOSITE_SCORE", ascending=True).tail(15)

    label = stuck.apply(
        lambda r: f"{r['RO_ID']} | {r['ORG_NM'][:20]} | {r['CNT_STATE']} | {r['LATEST_STAGE_NM']}",
        axis=1,
    )
    fig = go.Figure(go.Bar(
        x=stuck["COMPOSITE_SCORE"],
        y=label,
        orientation="h",
        marker_color=stuck["COMPOSITE_SCORE"].apply(
            lambda s: "#e74c3c" if s >= 9 else ("#f39c12" if s >= 4 else "#f1c40f")
        ),
        text=stuck["FAILURE_STATUS"].fillna(""),
        hovertemplate="Composite Score: %{x}<br>Stage: %{y}<br>Failure: %{text}<extra></extra>",
    ))
    fig.update_layout(
        title="Stuck RO Tracker — Ranked by Composite Escalation Score",
        template="plotly_dark",
        height=500,
        xaxis_title="Composite Escalation Score",
    )
    return fig