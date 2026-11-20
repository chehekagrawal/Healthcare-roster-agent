import streamlit as st
import pandas as pd
import plotly.graph_objects as go
from datetime import datetime
from fpdf import FPDF
import time
from dotenv import load_dotenv
load_dotenv()  # Load .env FIRST before any src imports that need API keys

# Import your Tier 1/2/3 Backend
from src.db.duckdb_engine import MetricsEngine
from src.tools.visualizer import Visualizer
from src.tools.report_gen import ReportGenerator
from src.memory.episodic import log_interaction, get_history, save_session_snapshot_once, DB_NAME
from src.memory.change_detector import ChangeDetector
from src.agent.monitor import ProactiveMonitor, get_active_alerts
from src.agent.graph import build_roster_graph
from src.tools.states import detect_state
import sqlite3

# ==========================================
# 🎨 EXTRAORDINARY UI CONFIGURATION
# ==========================================
st.set_page_config(page_title="RosterIQ | Intelligence Agent", page_icon="🧬", layout="wide")
st.markdown("""
<style>
.main { background-color: #0E1117; }

[data-testid="stSidebar"] {
    background-color: rgba(255, 255, 255, 0.05);
    backdrop-filter: blur(10px);
}

.stButton > button {
    background: linear-gradient(90deg, #00C9FF 0%, #92FE9D 100%);
    color: black;
    font-weight: bold;
    border-radius: 8px;
    width: 100%;
    border: none;
    transition: opacity 0.2s;
}
.stButton > button:hover { opacity: 0.85; }

[data-testid="stChatMessageContent"] > div {
    padding: 14px;
    border-radius: 12px;
    border: 1px solid rgba(255,255,255,0.1);
    font-size: 0.9rem;
    line-height: 1.55;
}
div[data-testid="stChatMessageUser"] [data-testid="stChatMessageContent"] > div {
    background-color: rgba(0, 201, 255, 0.1);
    border-left: 4px solid #00C9FF;
}
div[data-testid="stChatMessageAssistant"] [data-testid="stChatMessageContent"] > div {
    background-color: rgba(146, 254, 157, 0.05);
    border-left: 4px solid #92FE9D;
}

[data-testid="stChatMessageContent"] h3 { font-size: 1.2rem; }
[data-testid="stChatMessageContent"] h4 { font-size: 1rem; }
[data-testid="stChatMessageContent"] p  { font-size: 0.9rem; }
[data-testid="stMarkdownContainer"] p   { line-height: 1.6; }

[data-testid="stMetric"] {
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
@st.cache_resource
def get_shared_resources():
    """
    Created ONCE per server process and shared by every browser tab.
    (These used to live in st.session_state, which is per tab: every new tab
    loaded the data again and started another background monitor.)
    The agent's nodes already hold a MetricsEngine, so the app reuses it.
    """
    from src.agent import nodes
    engine = nodes.engine
    monitor = ProactiveMonitor(engine)
    monitor.run_immediate_scan()   # alerts visible straight away
    monitor.start()                # then every 5 minutes
    return {
        "engine": engine,
        "viz": Visualizer(engine),
        "reporter": ReportGenerator(engine),
        "detector": ChangeDetector(engine),
        "monitor": monitor,
        "agent": build_roster_graph(),
    }

_shared = get_shared_resources()
for _name, _obj in _shared.items():
    st.session_state[_name] = _obj
if 'messages' not in st.session_state:
    st.session_state.messages = []

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
    st.session_state.session_id = f"SES-{datetime.now().strftime('%Y%m%d-%H%M%S')}"

# Snapshot the pipeline ONCE per session. "What changed since last session"
# compares the live data with the snapshot of the previous session.
# (Saving on every rerun made "last session" mean "a few seconds ago".)
save_session_snapshot_once("stuck_ro_ids", st.session_state.engine.get_stuck_ro_ids(),
                           st.session_state.session_id)
save_session_snapshot_once("market_kpi_snapshot", st.session_state.engine.get_market_kpi_snapshot(),
                           st.session_state.session_id)


# ==========================================
# 📟 SIDEBAR: MEMORY & PROACTIVE MONITORING
# ==========================================
with st.sidebar:
    st.image("https://img.icons8.com/nolan/64/artificial-intelligence.png", width=60)
    st.title("RosterIQ")
    st.caption(f"Status: Operational | {st.session_state.session_id}")

    # --- Option B: Always-visible New Session button + Session switcher ---
    if st.button("＋ New Session"):
        st.session_state.session_id = f"SES-{datetime.now().strftime('%Y%m%d-%H%M%S')}"
        st.session_state.messages = []
        st.rerun()

    available_sessions = get_all_sessions()
    if available_sessions:
        # Include current session in options to prevent unwanted default reruns
        all_opts = available_sessions.copy()
        if st.session_state.session_id not in all_opts:
            all_opts.insert(0, st.session_state.session_id)
            
        current_idx = all_opts.index(st.session_state.session_id)
        selected_session = st.selectbox("Switch to past session", options=all_opts, index=current_idx)
        
        if selected_session != st.session_state.session_id:
            st.session_state.session_id = selected_session
            st.session_state.messages = []
            st.rerun()

    st.divider()
    
    # --- A6: Memory Sidebar (Partner C output) ---
    with st.expander("🧠 Episodic Memory (Current Thread)", expanded=False):
        history_text = get_history(st.session_state.session_id, limit=5)
        st.markdown(f"<div style='font-size:0.8rem; color:#A0AEC0;'>{history_text}</div>", unsafe_allow_html=True)

    st.divider()
    
    # --- Bonus: Proactive Monitoring (Real-time Scanner) ---
    st.markdown("<p style='font-size:0.7rem;text-transform:uppercase;letter-spacing:1.5px;color:#718096;margin-bottom:8px;'>🚨 Live Alerts (Autonomous)</p>", unsafe_allow_html=True)
    bg_alerts = get_active_alerts(limit=3)
    if bg_alerts:
        for alert in bg_alerts:
            color = "#FF4D6D" if alert['severity'] == "High" else "#FF9A3C"
            glow  = "rgba(255,77,109,0.15)" if alert['severity'] == "High" else "rgba(255,154,60,0.12)"
            st.markdown(f"""
            <div style="background:linear-gradient(135deg,{glow},rgba(255,255,255,0.02));
                        border:1px solid {color}40; border-left:3px solid {color};
                        padding:10px 12px; border-radius:10px; margin-bottom:8px;
                        box-shadow:0 2px 12px {glow};">
                <p style="margin:0;font-size:0.7rem;font-weight:700;letter-spacing:1px;
                           text-transform:uppercase;color:{color};">{alert['type']}</p>
                <p style="margin:4px 0 0;font-size:0.78rem;line-height:1.4;color:#CBD5E0;">{alert['message']}</p>
            </div>
            """, unsafe_allow_html=True)
    else:
        st.markdown("""
        <div style="background:linear-gradient(135deg,rgba(0,255,179,0.06),rgba(0,207,255,0.03));
                    border:1px solid rgba(0,255,179,0.25); border-left:3px solid #00FFB3;
                    padding:10px 12px; border-radius:10px;">
            <p style="margin:0;font-size:0.78rem;color:#00FFB3;">✓ No critical anomalies detected</p>
        </div>
        """, unsafe_allow_html=True)

    st.divider()
    
    # 2. Comparison-based Anomalies (Partner A logic)
    st.markdown("<p style='font-size:0.7rem;text-transform:uppercase;letter-spacing:1.5px;color:#718096;margin-bottom:8px;'>📊 Operational Diff</p>", unsafe_allow_html=True)
    change_data = st.session_state.detector.detect_all_changes(st.session_state.session_id)
    
    # Handle New Anomalies
    if change_data["new_anomalies"]:
        for ro_id in change_data["new_anomalies"]:
            st.markdown(f"""
            <div style="background:linear-gradient(135deg,rgba(255,77,109,0.08),rgba(255,255,255,0.02));
                        border:1px solid rgba(255,77,109,0.3); border-left:3px solid #FF4D6D;
                        padding:10px 12px; border-radius:10px; margin-bottom:6px;">
                <p style="margin:0;font-size:0.68rem;font-weight:700;letter-spacing:1px;
                           text-transform:uppercase;color:#FF4D6D;">⚠ NEW ANOMALY</p>
                <p style="margin:3px 0 0;font-size:0.82rem;font-weight:600;color:#E2E8F0;">{ro_id}</p>
                <p style="margin:2px 0 0;font-size:0.75rem;color:#718096;">Stall detected since last session.</p>
            </div>
            """, unsafe_allow_html=True)
            
    # 2. Handle Resolutions
    if change_data["resolutions"]:
        for ro_id in change_data["resolutions"]:
            st.markdown(f"""
            <div style="background:linear-gradient(135deg,rgba(0,255,179,0.07),rgba(255,255,255,0.02));
                        border:1px solid rgba(0,255,179,0.25); border-left:3px solid #00FFB3;
                        padding:10px 12px; border-radius:10px; margin-bottom:6px;">
                <p style="margin:0;font-size:0.68rem;font-weight:700;letter-spacing:1px;
                           text-transform:uppercase;color:#00FFB3;">✓ RESOLVED</p>
                <p style="margin:3px 0 0;font-size:0.82rem;font-weight:600;color:#E2E8F0;">{ro_id}</p>
                <p style="margin:2px 0 0;font-size:0.75rem;color:#718096;">Pipeline stall successfully cleared.</p>
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

    # 4. First session / no changes
    if change_data.get("baseline"):
        st.info("First session: today's state is saved as the baseline for next time.")
    elif not any([change_data["new_anomalies"], change_data["resolutions"], change_data["kpi_drift"]]):
        st.success("No changes since the last session.")

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
      try:
        # Use the high-fidelity ReportGenerator for the clean corporate PDF report
        pdf_bytes = st.session_state.reporter.generate_pdf_report()
        st.session_state["pdf_report"] = pdf_bytes
        st.success("✅ High-fidelity report ready! Click Download below.")
      except Exception as e:
        st.error(f"❌ PDF generation failed: {type(e).__name__}: {str(e)}")


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
for i, msg in enumerate(st.session_state.messages):
    with st.chat_message(msg["role"]):
        st.markdown(msg["content"], unsafe_allow_html=True)
        if "fig" in msg and msg["fig"]:
            st.plotly_chart(msg["fig"], width="stretch", key=f"hist_chart_{i}")

# Chat Input Logic
if prompt := st.chat_input("Ask about stuck ROs, a state's success-rate trend (e.g. 'GA trend'), or why a market is failing..."):
    # 1. Add and display the User's message IMMEDIATELY
    st.session_state.messages.append({"role": "user", "content": prompt})
    with st.chat_message("user"):
        st.markdown(prompt)
    
    # 2. Process with the Intelligent Agent Graph
    fig = None 
    
    p = prompt.lower()
    engine = st.session_state.engine
    asked_state = detect_state(prompt, engine.known_states())
    # "why", "root cause", "search" etc. always go to the agent: they need
    # reasoning and memory, not just a chart.
    needs_agent = any(w in p for w in ("why", "root cause", "cause", "search", "regulation",
                                       "cms", "compare", "retry", "retries", "explain", "remember",
                                       "last time", "last session", "before"))
    shortcut_used = True
    # Fast chart shortcuts (no LLM call). They now carry a short finding
    # computed from the data, not just a "working on it" line.
    if not needs_agent and ("trend" in p or "scs" in p or "success rate" in p or "percent" in p or "market" in p):
        market = asked_state or "NATIONAL"
        trend = engine.get_market_trend_data(market)
        fig = st.session_state.viz.plot_market_trend(market)
        if trend.empty:
            content = f"No monthly data for {market}."
        else:
            latest = trend.iloc[-1]
            below = trend[trend["SCS_PERCENT"] < 95]
            content = (f"**{market}** success rate: {latest['SCS_PERCENT']:.2f}% in {latest['MONTH']} "
                       f"(12-month average {trend['SCS_PERCENT'].mean():.2f}%). "
                       f"{len(below)} of {len(trend)} months were below the 95% SLA."
                       + ("" if asked_state else " Name a state (e.g. 'GA trend') to see one market."))
    elif not needs_agent and any(w in p for w in ("stuck", "triage", "stall", "frozen", "hung", "blocked", "pending")):
        from src.memory.procedural import procedural_memory
        triage = procedural_memory.run_procedure("triage_stuck_ros", engine)
        content = f"Triage (procedure triage_stuck_ros v{triage['version']}): {triage['summary']}"
        fig = st.session_state.viz.plot_stuck_ro_tracker()
    elif not needs_agent and any(w in p for w in ("anomal", "slow", "duration", "delay", "deviation", "bottleneck")):
        from src.memory.procedural import procedural_memory
        scan = procedural_memory.run_procedure("pipeline_bottleneck_scan", engine)
        content = f"Bottleneck scan (procedure pipeline_bottleneck_scan v{scan['version']}): {scan['summary']}"
        fig = st.session_state.viz.plot_duration_anomaly()
    elif not needs_agent and any(w in p for w in ("report", "pipeline status", "summary")):
        content = st.session_state.reporter.generate_pipeline_health_report()
    else:
        shortcut_used = False
        # FULL AGENT GRAPH INVOCATION
        try:
            with st.spinner("Agent Reasoning..."):
                inputs = {
                    "messages": [("user", prompt)],
                    "session_id": st.session_state.session_id
                }
                config = {"configurable": {"thread_id": st.session_state.session_id}}
                result = st.session_state.agent.invoke(inputs, config)
                content = result.get("final_answer") or "I encountered an error processing your request."
        except Exception as e:
            content = f"⚠️ Agent error: {type(e).__name__}: {str(e)[:400]}"
            shortcut_used = True  # the graph's memory writer never ran; log it here

    # 3. Log to episodic memory. Agent turns are logged by the graph's
    #    memory_writer node; logging them here too duplicated every turn.
    if shortcut_used:
        log_interaction(st.session_state.session_id, prompt, content)

    # 4. Display and Stream the Assistant Response (Task A6)
    with st.chat_message("assistant"):
        # This renders the "typing" effect live
        st.write_stream(stream_data(content))
        if fig:
            st.plotly_chart(fig, width="stretch", key=f"live_chart_{len(st.session_state.messages)}")

    # 5. Save the Agent's message to the session state
    agent_message = {"role": "assistant", "content": content}
    if fig:
        agent_message["fig"] = fig
    st.session_state.messages.append(agent_message)

    # 5. RERUN THE SCRIPT to ensure UI state consistency
    st.rerun()

# (Snapshots are saved once per session near the top of this script.)