"""
src/agent/nodes.py
==================
Agent graph nodes for RosterIQ.
Contains both Engineer 1's Data Integration Nodes and Engineer 2's Memory Orchestration Nodes.
"""
import json
import re
from typing import Dict, Any, List, Optional

from src.agent.state import RosterIQState
from dotenv import load_dotenv
import os

# Load environment variables (especially GOOGLE_API_KEY)
load_dotenv()
if not os.getenv("GOOGLE_API_KEY"):
    env_path = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), '.env')
    load_dotenv(dotenv_path=env_path)

# -----------------------------------------------------------------------------
# Engineer 1 (Partner) - Data & Analytics Initialization
# -----------------------------------------------------------------------------
from src.db.duckdb_engine import MetricsEngine
from src.tools.data_query import DataQueryTool
from src.tools.root_cause import RootCauseTracer
from src.tools.report_gen import ReportGenerator
from src.tools.states import detect_state, STATE_NAMES

# Initialize backend engines
engine = MetricsEngine()
query_tool = DataQueryTool(engine)
tracer = RootCauseTracer(engine)
report_gen = ReportGenerator(engine)
KNOWN_STATES = engine.known_states()

# Most rows ever placed into a prompt from one table. Tools used to dump whole
# tables (59,975 rows = 5.4 MB of JSON) into every prompt.
MAX_PROMPT_ROWS = 15

# --- Lazy LLM Getter (avoids caching None if key wasn't loaded at import time) ---
_llm = None

def get_llm():
    """Returns the LLM, initializing it lazily so it always uses the current GOOGLE_API_KEY."""
    global _llm
    if _llm is None:
        try:
            from langchain_google_genai import ChatGoogleGenerativeAI
            api_key = os.getenv("GOOGLE_API_KEY")
            if not api_key:
                load_dotenv()
                api_key = os.getenv("GOOGLE_API_KEY")
            if api_key:
                _llm = ChatGoogleGenerativeAI(
                    model="gemini-2.0-flash",
                    google_api_key=api_key,
                    max_retries=6,
                    timeout=60
                )
                print("[LLM] Gemini 2.0 Flash initialized successfully.")
            else:
                print("Warning: GOOGLE_API_KEY not found in environment.")
        except Exception as e:
            print(f"Warning: Could not initialize LLM. Error: {e}")
    return _llm


# =============================================================================
# SHARED HELPERS
# =============================================================================

def latest_user_text(messages) -> str:
    """
    The most recent message the USER sent.
    With checkpointing, `messages` holds the whole thread (old questions and
    old answers), so messages[0] is the first question ever asked and
    messages[-1] can be an agent reply. Walk back to the last human message.
    """
    for msg in reversed(messages or []):
        role = getattr(msg, "type", None)
        if role is None and isinstance(msg, (tuple, list)) and msg:
            role = msg[0]
        if role in ("human", "user"):
            content = msg.content if hasattr(msg, "content") else msg[1]
            return str(content)
    return ""


def has_word(text: str, *words: str) -> bool:
    """Whole-word / whole-phrase match, case-insensitive."""
    return any(re.search(rf"\b{re.escape(w)}\b", text, flags=re.IGNORECASE) for w in words)


def df_to_prompt(df, max_rows: int = MAX_PROMPT_ROWS) -> str:
    """A small, readable slice of a DataFrame for a prompt, with the true row count."""
    if df is None or len(df) == 0:
        return "(no rows)"
    shown = df.head(max_rows)
    text = shown.to_string(index=False, max_colwidth=40)
    if len(df) > max_rows:
        text += f"\n... ({len(df)} rows in total; first {max_rows} shown)"
    return text


def records_to_prompt(records: List[dict], max_rows: int = MAX_PROMPT_ROWS) -> str:
    import pandas as pd
    return df_to_prompt(pd.DataFrame(records), max_rows)


def summarise_with_llm(prompt: str, data_summary: str) -> str:
    """
    Asks the LLM to write the answer. If the LLM is unavailable, the user still
    gets the data findings instead of only an error message.
    """
    try:
        from langchain_core.messages import HumanMessage
        llm = get_llm()
        if not llm:
            raise ValueError("LLM not initialized (no GOOGLE_API_KEY).")
        response = llm.invoke([HumanMessage(content=prompt)])
        return response.content
    except Exception as e:
        if "429" in str(e) or "ResourceExhausted" in str(e):
            reason = "⚠️ **Rate Limit Reached (429)**: the AI is at capacity, so this is the raw finding without an AI summary. Try again in 10-15 seconds for a written explanation."
        else:
            reason = f"⚠️ AI summary unavailable ({type(e).__name__}). Here is what the data shows:"
        return f"{reason}\n\n{data_summary}"


def memory_block(memory: Dict[str, Any]) -> str:
    """Formats the loaded memory for a prompt."""
    return (
        f"- Recent conversation (this session): {memory.get('episodic', []) or 'none'}\n"
        f"- Similar past investigations (any session): {memory.get('related_history', []) or 'none'}\n"
        f"- Changes since the last session: {memory.get('change_summary', 'unknown')}\n"
        f"- Procedures available: {memory.get('procedures_loaded', [])}\n"
        f"- Domain knowledge (semantic memory): {memory.get('semantic', [])}\n"
        f"- Active alerts: {memory.get('active_alerts', [])}"
    )


# =============================================================================
# ENGINEER 2 - MEMORY & ORCHESTRATION NODES
# =============================================================================

def memory_loader_node(state: RosterIQState) -> Dict[str, Any]:
    """
    Fetches episodic context + change diff + semantic KB hits; injects into state.
    """
    session_id = state.get("session_id", "default_session")
    query = latest_user_text(state.get("messages"))

    # 1. Recent turns of THIS session (exact, from SQLite)
    try:
        from src.memory.episodic import get_history
        raw_history = get_history(session_id, limit=3)
        episodic_events = [{"context": raw_history}] if "No previous memory" not in raw_history else []
    except Exception as e:
        print(f"Warning: Episodic retrieval failed: {e}")
        episodic_events = []

    # 2. Similar past investigations from ANY session (by meaning, from ChromaDB).
    #    This is what answers "have we seen this before?" across sessions.
    related_history = []
    if query:
        try:
            from src.memory.episodic import retrieve_semantic_history
            docs = retrieve_semantic_history(query, n_results=2)
            related_history = [d[:400] for d in (docs[0] if docs else [])]
        except Exception as e:
            print(f"Warning: Semantic episodic retrieval failed: {e}")

    # 3. Top semantic KB hits for the question
    semantic_hits = []
    if query:
        try:
            from src.memory.semantic import semantic_memory
            semantic_hits = semantic_memory.fetch(query, top_k=3) or []
        except Exception as e:
            print(f"Warning: Semantic retrieval failed: {e}")

    # 4. What changed since the previous session
    try:
        from src.memory.change_detector import ChangeDetector
        changes = ChangeDetector(engine).detect_all_changes(session_id)
        change_summary = (f"Resolved: {changes['resolutions'] or 'none'}; "
                          f"newly stuck: {changes['new_anomalies'] or 'none'}; "
                          f"success-rate drift (>=1 point): {changes['kpi_drift'] or 'none'}")
    except Exception as e:
        print(f"Warning: Change detection failed: {e}")
        change_summary = "Change detection unavailable."

    # 5. Procedures loaded + versions
    try:
        from src.memory.procedural import procedural_memory
        procedures_loaded = [f"{name} (v{p.get('version', 1)})"
                             for name, p in procedural_memory.procedures.items()]
    except Exception:
        procedures_loaded = []

    # 6. Proactive alerts (bonus challenge)
    try:
        from src.agent.monitor import get_active_alerts
        alert_summary = [f"[{a['severity']}] {a['message']}" for a in get_active_alerts(limit=3)]
    except Exception:
        alert_summary = []

    return {
        "memory_context": {
            "episodic": episodic_events,
            "related_history": related_history,
            "semantic": semantic_hits,
            "change_summary": change_summary,
            "procedures_loaded": procedures_loaded,
            "active_alerts": alert_summary
        },
        # Reset per-turn outputs so a previous turn's values never leak into this one.
        "tool_outputs": [],
        "procedure_context": None,
        "final_answer": None,
    }


def memory_writer_node(state: RosterIQState) -> Dict[str, Any]:
    """
    Logs the turn to episodic memory (SQLite event + interaction, and ChromaDB).
    This is the ONLY place agent turns are logged; app.py logs only the
    shortcut answers that never reach the graph.
    """
    if not state.get("final_answer"):
        return {}

    session_id = state.get("session_id", "default_session")
    user_query = latest_user_text(state.get("messages")) or "Analyzed pipeline health"
    tools_used = [t.get("name", "unknown") for t in state.get("tool_outputs", []) or []]
    procedure = state.get("procedure_context")

    try:
        from src.memory.episodic import log_episodic_event, log_interaction
        log_episodic_event(
            session_id=session_id,
            intent=user_query[:200],
            findings=state["final_answer"],
            kpis={"tools": tools_used, "procedure": procedure},
            severity="High" if any("alert" in t or "triage" in t for t in tools_used) else "Low",
        )
        log_interaction(
            session_id=session_id,
            user_query=user_query,
            agent_response=state["final_answer"],
        )
        print(f"[Memory Writer] Logged episodic event for session {session_id}")
    except Exception as e:
        print(f"Warning: Could not log persistence events: {e}")

    return {}


MARKET_WORDS = ("market", "markets", "scs", "scs_percent", "success rate", "trend", "trends",
                "sla", "root cause", "search", "regulation", "regulations", "cms", "retry", "retries")
PIPELINE_WORDS = ("stuck", "triage", "stall", "stalled", "blocked", "slow", "slowest", "anomaly",
                  "anomalies", "bottleneck", "bottlenecks", "stage", "stages", "file", "files",
                  "pipeline", "health", "duration", "delay", "ingestion")


def keyword_route(query: str) -> str:
    """
    Fallback routing when the LLM is unavailable (whole words only).
    Market words or a named state win; otherwise pipeline words, a bare "why"
    (e.g. "why is GA low?" already has a state), or nothing at all go to the
    pipeline specialist.
    """
    if has_word(query, *MARKET_WORDS) or detect_state(query, KNOWN_STATES):
        return "market_analytics_node"
    if has_word(query, "why") and not has_word(query, *PIPELINE_WORDS):
        return "market_analytics_node"
    return "pipeline_health_node"


def supervisor_node(state: RosterIQState) -> Dict[str, Any]:
    """
    Intelligent router: decides whether the pipeline or the market specialist
    answers. Falls back to keyword routing if the LLM is unavailable.
    """
    query = latest_user_text(state.get("messages"))
    if not query:
        return {"active_agent": "pipeline_health_node"}

    prompt = f"""
    Analyze the user query and decide which agent should handle it.
    Return ONLY one of these two strings: 'pipeline_health_node' or 'market_analytics_node'.

    Rules:
    - Use 'pipeline_health_node' for queries about stuck files, pipeline stages, slow stages, file errors, or ingestion.
    - Use 'market_analytics_node' for queries about a state or market, success rates (SCS_PERCENT), trends,
      SLA breaches, retries, root cause analysis, or web searches about regulations.

    User Query: {query}
    """
    try:
        from langchain_core.messages import HumanMessage
        llm = get_llm()
        if not llm:
            raise ValueError("LLM not initialized.")
        text = llm.invoke([HumanMessage(content=prompt)]).content.lower().strip()
        next_agent = "market_analytics_node" if "market_analytics_node" in text else "pipeline_health_node"
        print(f"[Supervisor] Routing query to: {next_agent}")
    except Exception as e:
        next_agent = keyword_route(query)
        print(f"[Supervisor] LLM routing unavailable ({type(e).__name__}); keyword route -> {next_agent}")
    return {"active_agent": next_agent}


# =============================================================================
# ENGINEER 1 - DATA ANALYTICS & REPORTING NODES
# =============================================================================

def _run_procedure(name: str, overrides: Optional[dict] = None) -> dict:
    from src.memory.procedural import procedural_memory
    return procedural_memory.run_procedure(name, engine, overrides)


def pipeline_health_node(state: RosterIQState) -> Dict[str, Any]:
    """
    Pipeline Health Agent Node: stuck files, slow stages and file health.
    Runs the matching procedure from procedural memory where one exists.
    """
    query = latest_user_text(state.get("messages"))
    memory = state.get("memory_context", {})
    target_state = detect_state(query, KNOWN_STATES)
    procedure = None

    if has_word(query, "stuck", "triage", "stall", "stalled", "blocked", "escalate", "escalation"):
        result = _run_procedure("triage_stuck_ros", {"state_filter": target_state})
        procedure = "triage_stuck_ros"
        data_summary = (f"Procedure triage_stuck_ros v{result['version']} "
                        f"(weights {result['used_params']}): {result['summary']}\n"
                        f"{records_to_prompt(result['data'])}")
        tool_name = "procedure:triage_stuck_ros"

    elif has_word(query, "slow", "slowest", "anomaly", "anomalies", "bottleneck", "bottlenecks",
                  "delay", "delays", "duration", "deviation"):
        result = _run_procedure("pipeline_bottleneck_scan")
        procedure = "pipeline_bottleneck_scan"
        anomalies = query_tool.detect_anomalies()
        data_summary = (f"{len(anomalies)} file runs have at least one stage above 2x its historical average.\n"
                        f"Procedure pipeline_bottleneck_scan v{result['version']}: {result['summary']}\n"
                        f"{records_to_prompt(result['data'], 10)}")
        tool_name = "procedure:pipeline_bottleneck_scan"

    else:
        health = query_tool.derive_metrics("health", state=target_state)
        scope = target_state or "all states"
        by_state = (health.groupby("CNT_STATE")["composite_health_score"]
                    .agg(["mean", "count"]).sort_values("mean").head(10).round(3))
        worst = health.nsmallest(5, "composite_health_score")
        data_summary = (f"Composite health score (1.0 = all stages green, 0.0 = all red) for {scope}: "
                        f"average {health['composite_health_score'].mean():.3f} over {len(health)} file runs.\n"
                        f"Least healthy states:\n{df_to_prompt(by_state.reset_index())}\n"
                        f"Least healthy file runs:\n{df_to_prompt(worst)}")
        tool_name = "derive_metrics:health"

    prompt = f"""
    Data findings (computed with SQL; treat these numbers as the source of truth):
    {data_summary}

    Memory context:
    {memory_block(memory)}

    User Query: {query}

    Instruction: Answer professionally in plain language using ONLY the findings and memory above.
    Explain what is happening and what to do next. Do not invent numbers. Do not return raw JSON.
    If an alert, a past investigation or a change since last session is relevant, mention it.
    """
    answer = summarise_with_llm(prompt, data_summary)
    return {
        "messages": [("assistant", answer)],
        "final_answer": answer,
        "tool_outputs": [{"name": tool_name}],
        "procedure_context": procedure,
    }


def market_analytics_node(state: RosterIQState) -> Dict[str, Any]:
    """
    Market Analytics Agent Node: state success rates, root causes, retries and
    web research.
    """
    query = latest_user_text(state.get("messages"))
    memory = state.get("memory_context", {})
    target_state = detect_state(query, KNOWN_STATES)
    procedure = None

    if has_word(query, "root cause", "why", "cause", "reason", "explain why"):
        note = ""
        if not target_state:
            # No state named: investigate the market with the worst 12-month average.
            worst = engine.query("SELECT CNT_STATE FROM cross_state_health_view ORDER BY avg_scs_percent LIMIT 1")
            target_state = worst.iloc[0]["CNT_STATE"]
            note = f"(No state was named, so the market with the lowest 12-month average, {target_state}, was traced.) "
        analysis = tracer.trace_market_failure(target_state)
        data_summary = note + f"Root cause trace for {target_state}: {analysis['narrative']}"
        if analysis.get("breach_months"):
            data_summary += f"\nMonths below 95%: {analysis['breach_months']}"
        tool_name = "root_cause_tracer"

    elif has_word(query, "search", "regulation", "regulations", "cms", "rule", "rules", "policy", "news"):
        from src.tools.web_search import web_search
        context_type = web_search.pick_context_type(query)
        subject = STATE_NAMES.get(target_state, target_state) if target_state else query
        results = web_search.search(subject if context_type != "general" else query, context_type)
        stored = web_search.enrich_semantic_kb(results)
        hits = results.get("results", [])
        if "error" in results:
            data_summary = f"Web search unavailable: {results['error']}"
        else:
            data_summary = (f"Web search ({context_type}) for '{results.get('query_used')}':\n" +
                            "\n".join(f"- {h.get('title')} ({h.get('url')}): {str(h.get('content'))[:300]}"
                                      for h in hits) +
                            ("\n(Findings saved to semantic memory for future questions.)" if stored else ""))
        tool_name = f"web_search:{context_type}"

    elif has_word(query, "retry", "retries", "reprocess", "reprocessing", "rerun"):
        result = _run_procedure("retry_effectiveness_analysis", {"state_filter": target_state})
        procedure = "retry_effectiveness_analysis"
        data_summary = (f"Procedure retry_effectiveness_analysis v{result['version']}: {result['summary']}\n"
                        f"{records_to_prompt(result['data'], 10)}")
        tool_name = "procedure:retry_effectiveness_analysis"

    elif target_state:
        joined = query_tool.cross_table_join(target_state)
        trend = engine.get_market_trend_data(target_state)[["MONTH", "SCS_PERCENT"]]
        data_summary = (f"Market {target_state}: files vs success rate (latest month and 12-month figures):\n"
                        f"{df_to_prompt(joined)}\nMonthly SCS_PERCENT, oldest first:\n{df_to_prompt(trend, 12)}")
        tool_name = "cross_table_join"

    else:
        result = _run_procedure("market_health_report")
        procedure = "market_health_report"
        data_summary = (f"Procedure market_health_report v{result['version']}: {result['summary']}\n"
                        f"Markets below the 95% SLA (latest month or 12-month average):\n"
                        f"{records_to_prompt(result['data'])}")
        tool_name = "procedure:market_health_report"

    prompt = f"""
    Analytical findings (computed with SQL or retrieved from the web; treat as the source of truth):
    {data_summary}

    Memory context:
    {memory_block(memory)}

    User Query: {query}

    Instruction: Answer professionally in plain language using ONLY the findings and memory above.
    Distinguish the latest month from the 12-month average when both are given.
    Do not invent numbers. Do not return raw JSON.
    """
    answer = summarise_with_llm(prompt, data_summary)
    return {
        "messages": [("assistant", answer)],
        "final_answer": answer,
        "tool_outputs": [{"name": tool_name}],
        "procedure_context": procedure,
    }


def report_node(state):
    """
    Report Generation Node.
    Triggers the Markdown report generator.
    """
    report = report_gen.generate_pipeline_health_report()
    answer = f"Generated Operational Report:\n{report}"
    return {
        "messages": [("assistant", answer)],
        "final_answer": answer
    }
