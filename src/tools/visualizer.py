import plotly.express as px
import pandas as pd

def plot_market_trend(df_market, market_code):
    """Generates a line chart for SCS_PERCENT over time for a given market."""
    market_df = df_market[df_market['MARKET'] == market_code.upper()].sort_values('MONTH')
    
    fig = px.line(market_df, x='MONTH', y='SCS_PERCENT', 
                  title=f"Market Success Trend: {market_code.upper()}",
                  markers=True)
    
    # Add a reference line for a healthy threshold (e.g., 90%)
    fig.add_hline(y=90, line_dash="dash", line_color="red", annotation_text="90% Threshold")
    
    return fig

def plot_pipeline_health_heatmap(df_pipeline):
    """Heatmap of pipeline stage durations for top 15 files."""
    # Using the columns from your previous column list
    health_cols = ['PRE_PROCESSING_HEALTH', 'MAPPING_APROVAL_HEALTH', 'ISF_GEN_HEALTH', 'DART_GEN_HEALTH', 'SPS_LOAD_HEALTH']
    
    # Filter only relevant columns
    df_sample = df_pipeline.head(15)
    df_melted = df_sample.melt(id_vars=['RO_ID'], value_vars=health_cols, var_name='Stage', value_name='Health')
    
    fig = px.density_heatmap(df_melted, x="Stage", y="RO_ID", z="Health", 
                             title="Pipeline Health Heatmap (Red=Issue, Green=Healthy)")
    return fig