import streamlit as st
import pandas as pd
import plotly.graph_objects as go
from datetime import datetime

# Import your Tier 1/2/3 Backend
from src.db.duckdb_engine import MetricsEngine
from src.tools.data_query import DataQueryTool
from src.tools.visualizer import Visualizer
from src.tools.report_gen import ReportGenerator
from src.memory.episodic import log_interaction, get_history, save_data_snapshot
from src.memory.change_detector import ChangeDetector

# ==========================================
# 🎨 EXTRAORDINARY UI CONFIGURATION
# ==========================================
st.set_page_config(page_title="RosterIQ | Intelligence Agent", page_icon="🧬", layout="wide")

# Custom CSS for Glassmorphism and Neon Accents
# FIX: Changed unsafe_allow_value to unsafe_allow_html
st.markdown("""
<style>
.main { background-color: #0E1117; }

.stSidebar { 
    background-color: rgba(255, 255, 255, 0.05); 
    backdrop-filter: blur(10px); 
}

.stButton>button { 
    background: linear-gradient(90deg, #00C9FF 0%, #92FE9D 100%);
    color: black;
    font-weight: bold;
    border-radius: 5px;
    width: 100%;
}

/* Chat bubble styling */
[data-testid="stChatMessageContent"] > div {
    padding: 14px;
    border-radius: 12px;
    border: 1px solid rgba(255,255,255,0.1);
    font-size: 0.9rem;   /* smaller text */
    line-height: 1.5;
}

/* User message bubble */
div[data-testid="stChatMessageUser"] 
[data-testid="stChatMessageContent"] > div {
    background-color: rgba(0, 201, 255, 0.1);
    border-left: 4px solid #00C9FF;
}

/* Assistant message bubble */
div[data-testid="stChatMessageAssistant"] 
[data-testid="stChatMessageContent"] > div {
    background-color: rgba(146, 254, 157, 0.05);
    border-left: 4px solid #92FE9D;
}

/* Reduce markdown heading sizes inside chat */
[data-testid="stChatMessageContent"] h3 {
    font-size: 1.2rem;
}

[data-testid="stChatMessageContent"] h4 {
    font-size: 1rem;
}

[data-testid="stChatMessageContent"] p {
    font-size: 0.9rem;
}

.stMetric { 
    background: rgba(255,255,255,0.03);
    padding: 12px;
    border-radius: 12px;
    border: 1px solid rgba(255,255,255,0.1);
}

</style>
""", unsafe_allow_html=True)

# ==========================================
# 🧠 INITIALIZATION & STATE MANAGEMENT
# ==========================================
if 'engine' not in st.session_state:
    st.session_state.engine = MetricsEngine()
    st.session_state.viz = Visualizer(st.session_state.engine)
    st.session_state.reporter = ReportGenerator(st.session_state.engine)
    st.session_state.detector = ChangeDetector(st.session_state.engine)
    st.session_state.messages = []
    st.session_state.session_id = f"SES-{datetime.now().strftime('%H%M%S')}"

# ==========================================
# 📟 SIDEBAR: MEMORY & PROACTIVE MONITORING
# ==========================================
with st.sidebar:
    st.image("https://img.icons8.com/nolan/64/artificial-intelligence.png", width=60)
    st.title("RosterIQ")
    st.caption(f"Status: Operational | {st.session_state.session_id}")
    
    st.divider()
    
    # PROACTIVE MONITORING (Improved Professional UI)
    st.subheader("🚨 Proactive Alerts")
    
    change_data = st.session_state.detector.detect_all_changes()
    
    # 1. Handle New Anomalies
    if change_data["new_anomalies"]:
        for ro_id in change_data["new_anomalies"]:
            st.markdown(f"""
            <div class="alert-card">
                <span class="status-tag tag-new">⚠️ New Anomaly</span>
                <div style="font-weight: bold; font-size: 0.9rem;">{ro_id}</div>
                <div style="font-size: 0.8rem; color: #808495;">Stall detected since last session.</div>
            </div>
            """, unsafe_allow_html=True)
            
    # 2. Handle Resolutions
    if change_data["resolutions"]:
        for ro_id in change_data["resolutions"]:
            st.markdown(f"""
            <div class="alert-card">
                <span class="status-tag tag-resolved">✅ Resolved</span>
                <div style="font-weight: bold; font-size: 0.9rem;">{ro_id}</div>
                <div style="font-size: 0.8rem; color: #808495;">Pipeline stall successfully cleared.</div>
            </div>
            """, unsafe_allow_html=True)

    # 3. Handle KPI Drift
    if change_data["kpi_drift"]:
        for market, drift in change_data["kpi_drift"].items():
            st.markdown(f"""
            <div class="alert-card">
                <span class="status-tag tag-drift">📉 KPI Drift</span>
                <div style="font-weight: bold; font-size: 0.9rem;">{market} Market</div>
                <div style="font-size: 0.8rem; color: #808495;">{drift['old']}% → {drift['new']}% Success</div>
            </div>
            """, unsafe_allow_html=True)

    # 4. All Clear State
    if not any([change_data["new_anomalies"], change_data["resolutions"], change_data["kpi_drift"]]):
        st.success("System Healthy: No changes since last check.")

    st.divider()

    # REAL-TIME KPI SNAPSHOT (Using DuckDB Engine)
    st.subheader("📊 Pipeline Snapshot")
    stuck_ros_df = st.session_state.engine.stuck_ros()
    stuck_count = len(stuck_ros_df)
    
    health_df = st.session_state.engine.pipeline_health_score()
    # FIX: Using the correct column name from schema.sql
    avg_health = health_df['composite_health_score'].mean()
    
    col1, col2 = st.columns(2)
    col1.metric("Stuck ROs", stuck_count, delta_color="inverse")
    col2.metric("Health Score", f"{avg_health:.2f}")

    st.divider()
    
    if st.button("📄 Export Pipeline Health Report"):
        report = st.session_state.reporter.generate_pipeline_health_report()
        st.session_state.messages.append({"role": "assistant", "content": report})
        st.rerun()

# ==========================================
# 💬 MAIN INTERFACE: INTELLIGENT CHAT
# ==========================================
st.title("🧬 Provider Roster Intelligence")
st.markdown("Autonomous monitoring and diagnostic agent for provider operations.")

# Display Chat History (FIXED: Simplified for proper Markdown rendering)
for msg in st.session_state.messages:
    with st.chat_message(msg["role"]):
        st.markdown(msg["content"], unsafe_allow_html=True)
        if "fig" in msg and msg["fig"]:
            st.plotly_chart(msg["fig"], use_container_width=True)

# Chat Input Logic
if prompt := st.chat_input("Ask about stuck ROs, GA market trends, or anomalies..."):
    # 1. Add and display the User's message
    st.session_state.messages.append({"role": "user", "content": prompt})
    
    # 2. Process with the Logic Router (Correctly starting with 'if')
    fig = None # Initialize fig
    
    if "root cause" in prompt.lower() or "why" in prompt.lower():
        from src.tools.root_cause import RootCauseTracer
        tracer = RootCauseTracer(st.session_state.engine)
        analysis = tracer.trace_market_failure("GA")
        
        # "EXTRAORDINARY" UI Formatting for the narrative
        content = f"""
**🔍 Root Cause Analysis — GA Market**

{analysis['narrative']}

---

**Key Diagnostic Findings**

• **Primary Bottleneck:** `{analysis['primary_failure_stage']}`  
• **Culprit Source System:** `{analysis['primary_culprit_system']}`  
• **Top Failing Organization:** `{analysis['top_failing_orgs'][0]['ORG_NM'] if analysis['top_failing_orgs'] else 'N/A'}`
"""

    elif "trend" in prompt.lower() or "market" in prompt.lower():
        content = "Analyzing Market SCS_PERCENT trends..."
        fig = st.session_state.viz.plot_market_trend("GA") 

    elif "stuck" in prompt.lower() or "triage" in prompt.lower():
        content = "Triaging active bottlenecks..."
        fig = st.session_state.viz.plot_stuck_ro_tracker()

    elif "anomaly" in prompt.lower() or "slow" in prompt.lower():
        content = "Analyzing duration deviations..."
        fig = st.session_state.viz.plot_duration_anomaly()
        
    elif "report" in prompt.lower():
        content = st.session_state.reporter.generate_pipeline_health_report()

    else:
        content = "I've analyzed the pipeline. Please specify if you want a 'health report', or to investigate 'stuck ro', 'GA market trends', or 'why' a market is failing."

    # 3. Log the interaction to Episodic Memory
    log_interaction(st.session_state.session_id, prompt, content)

    # 4. Save the Agent's message to the session state
    agent_message = {"role": "assistant", "content": content}
    if fig:
        agent_message["fig"] = fig
    st.session_state.messages.append(agent_message)

    # 5. RERUN THE SCRIPT to display the new messages
    st.rerun()

# --- Everything below this is outside the 'if prompt' block ---

# ==========================================
# 💾 AUTOMATED SNAPSHOT (Requirement A4)
# ==========================================
save_data_snapshot("stuck_ro_ids", st.session_state.engine.get_stuck_ro_ids())
save_data_snapshot("market_kpi_snapshot", st.session_state.engine.get_market_kpi_snapshot())