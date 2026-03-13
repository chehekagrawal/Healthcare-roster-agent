import pandas as pd
import json
import os
from dotenv import load_dotenv
from langchain_community.tools.tavily_search import TavilySearchResults

# Load the environment variables from your .env file
load_dotenv()

# Check if the key is loaded
if not os.getenv("TAVILY_API_KEY"):
    print("WARNING: TAVILY_API_KEY not found in .env file!")

def get_web_search_tool():
    """
    Returns a search tool the LLM can use.
    The LLM will call this tool when it needs to look up 
    regulatory changes or provider organization details.
    """
    # This automatically picks up the TAVILY_API_KEY from your environment
    return TavilySearchResults(max_results=3)

# ==========================================
# 1. DATA LOADING & CLEANING
# ==========================================
def load_and_clean_data():
    """Loads CSVs and does basic cleaning for the tools."""
    # Assuming the files are in a folder named 'data'
    df_pipeline = pd.read_csv("data/roster_processing_details.csv")
    df_market = pd.read_csv("data/aggregated_operational_metrics.csv")
    
    # Cleaning CSV 1: Fill missing failure reasons with "None", ensure numeric types
    df_pipeline['FAILURE_STATUS'] = df_pipeline['FAILURE_STATUS'].fillna("None")
    df_pipeline['IS_STUCK'] = df_pipeline['IS_STUCK'].fillna(0).astype(int)
    
    # Cleaning CSV 2: Ensure market strings are uppercase for easy matching
    df_market['MARKET'] = df_market['MARKET'].astype(str).str.upper()
    
    return df_pipeline, df_market

# ==========================================
# 2. PROCEDURAL TOOL: Triage Stuck ROs
# ==========================================
def triage_stuck_ros() -> str:
    """
    Finds all stuck Roster Operations (IS_STUCK=1), ranks them by the number 
    of RED health flags, and returns the top priority cases as a JSON string.
    """
    df_pipeline, _ = load_and_clean_data()
    
    # Filter only stuck files
    stuck_df = df_pipeline[df_pipeline['IS_STUCK'] == 1].copy()
    
    if stuck_df.empty:
        return json.dumps({"status": "All clear", "message": "No stuck ROs found in the pipeline."})
    
    # Count 'Red' health flags across all health columns to determine severity
    health_cols =[col for col in stuck_df.columns if col.endswith('_HEALTH')]
    stuck_df['RED_FLAG_COUNT'] = (stuck_df[health_cols] == 'Red').sum(axis=1)
    
    # Sort by Most Red Flags (Severity)
    ranked_stuck = stuck_df.sort_values(by='RED_FLAG_COUNT', ascending=False)
    
    # Keep only the columns the LLM needs to see to make a decision
    result_df = ranked_stuck[['RO_ID', 'ORG_NM', 'CNT_STATE', 'LATEST_STAGE_NM', 'RED_FLAG_COUNT', 'FAILURE_STATUS']]
    
    # Return top 10 worst stuck files as a JSON string (LLMs read JSON perfectly)
    return result_df.head(10).to_json(orient="records")

# ==========================================
# 3. PROCEDURAL TOOL: Market Health Report (Cross-Table Join)
# ==========================================
def market_health_report(state_code: str) -> str:
    """
    Correlates a market's overall transaction success (CSV 2) 
    with its pipeline stage health (CSV 1).
    """
    df_pipeline, df_market = load_and_clean_data()
    state_code = state_code.upper()
    
    # 1. Get Macro Market Data (CSV 2)
    market_data = df_market[df_market['MARKET'] == state_code]
    if market_data.empty:
        return json.dumps({"error": f"No market data found for state: {state_code}"})
    
    # Use the columns that actually exist in your CSV 2
    avg_market_success = market_data['SCS_PERCENT'].mean()
    total_fails = market_data['OVERALL_FAIL_CNT'].sum()
    
    # 2. Get Pipeline Health Data (CSV 1)
    state_pipeline = df_pipeline[df_pipeline['CNT_STATE'] == state_code]
    stuck_files = state_pipeline[state_pipeline['IS_STUCK'] == 1].shape[0]
    
    # 3. Combine into an actionable report
    report = {
        "Market": state_code,
        "Overall_Transaction_Success_Rate": f"{avg_market_success:.2f}%",
        "Total_Failures_In_Market": int(total_fails),
        "Currently_Stuck_Files_In_Pipeline": stuck_files,
        "Insight": "By comparing market failures against stuck pipeline files, we can isolate if the issue is a systemic failure or a file-specific stall."
    }
    
    return json.dumps(report)

# --- TEST IT YOURSELF ---
if __name__ == "__main__":
    print("--- Testing Triage Tool ---")
    print(triage_stuck_ros())
    print("\n--- Testing Market Report Tool (for CA) ---")
    print(market_health_report("CA"))