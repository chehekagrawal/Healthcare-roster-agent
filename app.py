import streamlit as st
import pandas as pd
import plotly.graph_objects as go
from datetime import datetime
from fpdf import FPDF
import time

# Import your Tier 1/2/3 Backend
from src.db.duckdb_engine import MetricsEngine
from src.tools.data_query import DataQueryTool
from src.tools.visualizer import Visualizer
from src.tools.report_gen import ReportGenerator
from src.memory.episodic import log_interaction, get_history, save_data_snapshot, DB_NAME
from src.memory.change_detector import ChangeDetector
from src.agent.monitor import ProactiveMonitor, get_active_alerts
from src.agent.graph import build_roster_graph
import sqlite3

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
            
[data-testid="stMarkdownContainer"] p {
    line-height: 1.6;
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
    # --- Bonus: Start Proactive Monitoring ---
    st.session_state.monitor = ProactiveMonitor(st.session_state.engine)
    st.session_state.monitor.start()
    st.session_state.monitor.run_immediate_scan()
    
    # --- Agent Graph Initialization ---
    st.session_state.agent = build_roster_graph()

# --- Session Thread Management ---
def get_all_sessions():
    """Retrieve all unique session IDs from the database."""
    try:
        conn = sqlite3.connect(DB_NAME)
        cursor = conn.cursor()
        cursor.execute("SELECT DISTINCT session_id FROM interactions ORDER BY timestamp DESC")
        sessions = [row[0] for row in cursor.fetchall()]
        conn.close()
        return sessions
    except Exception:
        return []

available_sessions = get_all_sessions()
new_session_str = "+ Start New Session"
session_options = [new_session_str] + available_sessions

if 'session_id' not in st.session_state:
    st.session_state.session_id = f"SES-{datetime.now().strftime('%H%M%S')}"


# ==========================================
# 📟 SIDEBAR: MEMORY & PROACTIVE MONITORING
# ==========================================
with st.sidebar:
    st.image("https://img.icons8.com/nolan/64/artificial-intelligence.png", width=60)
    st.title("RosterIQ")
    st.caption(f"Status: Operational | {st.session_state.session_id}")
    
    # --- A6: Session picker ---
    selected_session = st.selectbox("Select Session Thread", options=session_options)
    if selected_session == new_session_str:
        if st.button("Initialize New Thread"):
            st.session_state.session_id = f"SES-{datetime.now().strftime('%H%M%S')}"
            st.session_state.messages = []
            st.rerun()
    elif selected_session != st.session_state.session_id:
        st.session_state.session_id = selected_session
        st.session_state.messages = [] # Clear UI chat messages on switch
        st.rerun()

    st.divider()
    
    # --- A6: Memory Sidebar (Partner C output) ---
    with st.expander("🧠 Episodic Memory (Current Thread)", expanded=False):
        history_text = get_history(st.session_state.session_id, limit=5)
        st.markdown(f"<div style='font-size:0.8rem; color:#A0AEC0;'>{history_text}</div>", unsafe_allow_html=True)

    st.divider()
    
    # --- Bonus: Proactive Monitoring (Real-time Scanner) ---
    st.subheader("🚨 Live Alerts (Autonomous)")
    bg_alerts = get_active_alerts(limit=3)
    if bg_alerts:
        for alert in bg_alerts:
            color = "#E53E3E" if alert['severity'] == "High" else "#DD6B20"
            st.markdown(f"""
            <div style="background:rgba(255,255,255,0.03); border-left:4px solid {color}; padding:10px; border-radius:8px; margin-bottom:10px;">
                <p style="margin:0; font-weight:bold; font-size:0.85rem;">{alert['type']}</p>
                <p style="margin:0; font-size:0.8rem; line-height:1.3;">{alert['message']}</p>
            </div>
            """, unsafe_allow_html=True)
    else:
        st.caption("No critical anomalies detected. System Healthy.")

    st.divider()
    
    # 2. Comparison-based Anomalies (Partner A logic)
    st.subheader("📊 Operational Diff")
    change_data = st.session_state.detector.detect_all_changes()
    
    # Handle New Anomalies
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
    
    # Generate PDF when export button is clicked
    if st.button("📄 Export Pipeline Health Report"):

        report = st.session_state.reporter.generate_pipeline_health_report()

        # Remove characters not supported by latin-1
        clean_report = report.encode("latin-1", "ignore").decode("latin-1")

        pdf = FPDF()
        pdf.add_page()
        pdf.set_auto_page_break(auto=True, margin=15)

        # Title
        pdf.set_font("Arial", "B", 18)
        pdf.cell(0, 12, "Provider Roster Pipeline Health Report", ln=True)
        pdf.ln(4)

        lines = clean_report.split("\n")

        def _sanitize(text: str) -> str:
            """Strip any character that can't be encoded in latin-1 (fpdf2 Arial font limit)."""
            return text.encode("latin-1", "replace").decode("latin-1")

        for line in lines:

            # Remove common emojis and special symbols
            for ch in ["📋","🚀","⚠️","📉","🔍","💡","✅","❌","→","←","≥","≤","★","•","►","▼","▲"]:
                line = line.replace(ch, "")

            # MAIN TITLE
            if line.startswith("# "):
                pdf.set_font("Arial", "B", 18)
                pdf.cell(0, 10, line.replace("# ", ""), ln=True)
                pdf.ln(3)

            # SECTION HEADER
            elif line.startswith("## "):
                pdf.set_font("Arial", "B", 14)
                pdf.cell(0, 8, line.replace("## ", ""), ln=True)
                pdf.ln(2)

            # Skip markdown table separator
            elif line.startswith("|---"):
                continue

            # TABLE ROW
            elif "|" in line:
                columns = [c.strip() for c in line.split("|") if c.strip()]
                col_width = 190 / len(columns)

                pdf.set_font("Arial", "", 10)

                for col in columns:
                    pdf.cell(col_width, 8, _sanitize(col), border=1)

                pdf.ln()

            # NORMAL TEXT
            else:
                pdf.set_font("Arial", "", 11)
                pdf.multi_cell(0, 7, _sanitize(line))

        # Store PDF in session state
        st.session_state["pdf_report"] = pdf.output(dest="S").encode("latin-1")


    # Show download button only once
    if "pdf_report" in st.session_state:

        st.download_button(
            label="⬇ Download PDF Report",
            data=st.session_state["pdf_report"],
            file_name="pipeline_health_report.pdf",
            mime="application/pdf",
            key="download_pipeline_report_unique"
    )

# ==========================================
# 💬 MAIN INTERFACE: INTELLIGENT CHAT
# ==========================================
st.title("🧬 Provider Roster Intelligence")
st.markdown("Autonomous monitoring and diagnostic agent for provider operations.")

def stream_data(text: str):
    """Generator for streaming text with a typing effect."""
    for word in text.split(" "):
        yield word + " "
        time.sleep(0.02)

# Display Chat History (FIXED: Simplified for proper Markdown rendering)
for msg in st.session_state.messages:
    with st.chat_message(msg["role"]):
        st.markdown(msg["content"], unsafe_allow_html=True)
        if "fig" in msg and msg["fig"]:
            st.plotly_chart(msg["fig"], use_container_width=True)

# Chat Input Logic
if prompt := st.chat_input("Ask about stuck ROs, GA market trends, or anomalies..."):
    # 1. Add and display the User's message IMMEDIATELY
    st.session_state.messages.append({"role": "user", "content": prompt})
    with st.chat_message("user"):
        st.markdown(prompt)
    
    # 2. Process with the Intelligent Agent Graph
    fig = None 
    
    # Special shortcuts for visualizations (stay for UX speed)
    if "trend" in prompt.lower() or "market" in prompt.lower():
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
        # FULL AGENT GRAPH INVOCATION
        with st.spinner("Agent Reasoning..."):
            inputs = {
                "messages": [("user", prompt)],
                "session_id": st.session_state.session_id
            }
            config = {"configurable": {"thread_id": st.session_state.session_id}}
            result = st.session_state.agent.invoke(inputs, config)
            content = result.get("final_answer", "I encountered an error processing your request.")

    # 3. Log the interaction to Episodic Memory
    log_interaction(st.session_state.session_id, prompt, content)

    # 4. Display and Stream the Assistant Response (Task A6)
    with st.chat_message("assistant"):
        # This renders the "typing" effect live
        st.write_stream(stream_data(content))
        if fig:
            st.plotly_chart(fig, use_container_width=True)

    # 5. Save the Agent's message to the session state
    agent_message = {"role": "assistant", "content": content}
    if fig:
        agent_message["fig"] = fig
    st.session_state.messages.append(agent_message)

    # 5. RERUN THE SCRIPT to ensure UI state consistency
    st.rerun()

# --- Everything below this is outside the 'if prompt' block ---

# ==========================================
# 💾 AUTOMATED SNAPSHOT (Requirement A4)
# ==========================================
save_data_snapshot("stuck_ro_ids", st.session_state.engine.get_stuck_ro_ids())
save_data_snapshot("market_kpi_snapshot", st.session_state.engine.get_market_kpi_snapshot())