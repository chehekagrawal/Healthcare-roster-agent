"""
src/agent/nodes.py
==================
Agent graph nodes for RosterIQ.
Contains both Engineer 1's Data Integration Nodes and Engineer 2's Memory Orchestration Nodes.
"""
from typing import Dict, Any
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
try:
    from src.db.duckdb_engine import MetricsEngine
    from src.tools.data_query import DataQueryTool
    from src.tools.root_cause import RootCauseTracer
    from src.tools.report_gen import ReportGenerator

    # Initialize backend engines
    engine = MetricsEngine()
    query_tool = DataQueryTool(engine)
    tracer = RootCauseTracer(engine)
    report_gen = ReportGenerator(engine)
except ImportError as e:
    print(f"Warning: Could not initialize reporting/query engines. Error: {e}")

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
                    google_api_key=api_key
                )
                print("[LLM] Gemini 2.0 Flash initialized successfully.")
            else:
                print("Warning: GOOGLE_API_KEY not found in environment.")
        except Exception as e:
            print(f"Warning: Could not initialize LLM. Error: {e}")
    return _llm

# =============================================================================
# ENGINEER 2 - MEMORY & ORCHESTRATION NODES
# =============================================================================

def memory_loader_node(state: RosterIQState) -> Dict[str, Any]:
    """
    Fetches episodic context + change diff + semantic KB hits; injects into state.
    This fulfills the C4 Agent Memory Nodes requirement.
    """
    # 1. Fetch episodic context (mocked until Episodic is fully integrated by Engineer 1)
    try:
        from src.memory.episodic import get_history
        session_id = state.get("session_id", "default_session")
        # get_history returns formatted string, convert a brief summary list for the agent
        raw_history = get_history(session_id, limit=3)
        episodic_events = [{"context": raw_history}] if "No previous memory" not in raw_history else []
    except Exception as e:
        print(f"Warning: Episodic retrieval failed: {e}")
        episodic_events = []
    
    # 2. Fetch semantic KB hits based on latest message
    semantic_hits = []
    if state.get("messages"):
        last_msg = state["messages"][-1]
        query = last_msg.content if hasattr(last_msg, "content") else str(last_msg)
        
        try:
            from src.memory.semantic import semantic_memory
            # Retrieve the top 3 semantically relevant facts from ChromaDB
            hits = semantic_memory.fetch(query, top_k=3)
            # fetch() returns List[str] directly
            if hits:
                semantic_hits = hits
        except Exception as e:
            print(f"Warning: Semantic retrieval failed: {e}")
            
    # 3. Change diff tracker (mocked for now, waiting on Engineer 1 integration)
    try:
        from src.memory.change_detector import ChangeDetector
        # We need the initialized engine; checking if it was imported successfully
        if 'engine' in globals():
            detector = ChangeDetector(engine)
            changes = detector.detect_all_changes()
            change_summary = f"Resolutions: {len(changes['resolutions'])}, New Anomalies: {len(changes['new_anomalies'])}, KPI Drifts: {len(changes['kpi_drift'])}"
        else:
            change_summary = "Engine not available for ChangeDetector."
    except Exception as e:
        print(f"Warning: Change detection failed: {e}")
        change_summary = "Change detection unvailable."
    
    # 4. Procedures loaded + versions
    try:
        from src.memory.procedural import procedural_memory
        procedures_loaded = []
        for name, proc_data in procedural_memory.procedures.items():
            version = proc_data.get("version", "1.0")
            procedures_loaded.append(f"{name} (v{version})")
    except Exception:
        procedures_loaded = []
        
    # 5. FETCH PROACTIVE ALERTS (Bonus Challenge)
    try:
        from src.agent.monitor import get_active_alerts
        active_alerts = get_active_alerts(limit=3)
        alert_summary = [f"[{a['severity']}] {a['message']}" for a in active_alerts]
    except Exception:
        alert_summary = []
        
    return {
        "memory_context": {
            "episodic": episodic_events,
            "semantic": semantic_hits,
            "change_summary": change_summary,
            "procedures_loaded": procedures_loaded,
            "active_alerts": alert_summary
        }
    }

def memory_writer_node(state: RosterIQState) -> Dict[str, Any]:
    """
    Builds and logs `EpisodicEvent` after every agent turn.
    Extracts the final answer and used tools to persist the agent's recent reasoning.
    This fulfills the second half of C4: Agent Memory Nodes.
    """
    if not state.get("final_answer"):
        return {} # Nothing to log if no final action was taken
        
    session_id = state.get("session_id", "default_session")
    
    # In a full run, we would extract the specific user query from messages
    user_intent = "Analyzed pipeline health" 
    if state.get("messages") and len(state["messages"]) > 0:
         msg = state["messages"][0]
         raw_content = msg.content if hasattr(msg, "content") else str(msg)
         raw_summary = str(raw_content)
         user_intent = raw_summary[:100]

    # Structure the episodic event
    event = {
        "session_id": session_id,
        "intent": user_intent,
        "tools_used": [t.get("name", "unknown") for t in state.get("tool_outputs", [])],
        "final_output": state["final_answer"],
        "procedures_run": state.get("procedure_context", None)
    }
    
    # Note: Calling Engineer 1's SQLite/Chroma Episodic DB writer here
    try:
        from src.memory.episodic import log_episodic_event, log_interaction
        # 1. Log the structured diagnostic event
        log_episodic_event(
            session_id=session_id,
            intent=user_intent,
            findings=state["final_answer"],
            kpis={"tools": event["tools_used"], "procedures": event["procedures_run"]},
            severity="Low"
        )
        # 2. Log the general conversation interaction (for chat history retrieval)
        log_interaction(
            session_id=session_id,
            user_query=user_intent,
            agent_response=state["final_answer"]
        )
    except Exception as e:
        print(f"Warning: Could not log persistence events: {e}")

    print(f"[Memory Writer] Logged episodic event for session {session_id}")
    
    return {} # No direct state changes, just side object logging

def supervisor_node(state: RosterIQState) -> Dict[str, Any]:
    """
    Acts as the intelligent router.
    Reads the latest user message and the memory context, then decides
    whether to route execution to the 'pipeline_health_node' or 'market_analytics_node'.
    Fulfills C4: Agent Memory Nodes orchestration requirement.
    """
    try:
        from langchain_google_genai import ChatGoogleGenerativeAI
        from pydantic import BaseModel, Field
    except ImportError:
        print("Required packages not installed for supervisor node.")
        return {"active_agent": "pipeline_health_node"} # Fallback

    if not state.get("messages"):
        return {"active_agent": "pipeline_health_node"}

    last_msg = state["messages"][-1]
    query = last_msg.content if hasattr(last_msg, "content") else str(last_msg)

    # Define the structured output for the router
    class RouterDecision(BaseModel):
        next_agent: str = Field(
            description="Must be 'pipeline_health_node' for system/file errors, or 'market_analytics_node' for SLA/Market/Trend questions."
        )

    # Initialize the LLM
    try:
        from langchain_core.messages import HumanMessage
        
        prompt = f"""
        Analyze the user query and decide which agent should handle it.
        Return ONLY one of these two strings: 'pipeline_health_node' or 'market_analytics_node'.
        
        Rules:
        - Use 'pipeline_health_node' for queries about stuck files, pipeline stages, file errors, or ingestion.
        - Use 'market_analytics_node' for queries about market trends, SCS_PERCENT, root cause analysis, or web searches.
        
        User Query: {query}
        """
        
        llm = get_llm()
        if llm:
            response = llm.invoke([HumanMessage(content=prompt)])
            text = response.content.lower().strip()
        else:
            raise ValueError("LLM not initialized.")
        
        if "market_analytics_node" in text:
            next_agent = "market_analytics_node"
        else:
            next_agent = "pipeline_health_node"
             
        print(f"[Supervisor] Routing query to: {next_agent}")
        return {"active_agent": next_agent}

    except Exception as e:
        print(f"[Supervisor] Routing failed, using keyword fallback. Error: {e}")
        # Keyword fallback
        market_keywords = ["market", "scs", "trend", "search", "root cause", "ga", "ca", "ny", "tx"]
        if any(kw in query.lower() for kw in market_keywords):
            next_agent = "market_analytics_node"
        else:
            next_agent = "pipeline_health_node"
        return {"active_agent": next_agent}


# =============================================================================
# ENGINEER 1 - DATA ANALYTICS & REPORTING NODES
# =============================================================================

def pipeline_health_node(state: RosterIQState) -> Dict[str, Any]:
    """
    Pipeline Health Agent Node.
    Analyzes stuck files, health scores, and duration anomalies.
    Summarizes findings using LLM for a natural language experience.
    """
    query = state["messages"][-1].content
    memory = state.get("memory_context", {})
    
    # 1. Retrieve Data Context
    if "stuck" in query.lower():
        data = query_tool.derive_metrics("stuck_duration")
        data_context = f"Current stuck files: {data.to_json()}"
    elif "anomaly" in query.lower() or "slow" in query.lower():
        data = query_tool.detect_anomalies()
        data_context = f"Duration anomalies: {data.to_json()}"
    else:
        data = query_tool.derive_metrics("health")
        data_context = f"Pipeline health scores: {data.to_json()}"
    
    # 2. Construct LLM Summary Prompt
    prompt = f"""
    Internal Data Engine Result: {data_context}
    
    Memory Context:
    - Procedural Memory (Rules): {memory.get('procedures_loaded', [])}
    - Semantic Knowledge: {memory.get('semantic', [])}
    - Active Alerts: {memory.get('active_alerts', [])}
    
    User Query: {query}
    
    Instruction: Provide a professional natural language summary of the data. 
    Explain what's happening. DO NOT return raw JSON. 
    If referencing rules or alerts from memory, explain their relevance.
    """
    
    try:
        from langchain_core.messages import HumanMessage
        llm = get_llm()
        if llm:
            response = llm.invoke([HumanMessage(content=prompt)])
            answer = response.content
        else:
            raise ValueError("LLM not initialized correctly.")
    except Exception as e:
        answer = f"⚠️ Could not generate an AI summary. Raw data was retrieved but the LLM is unavailable (check GOOGLE_API_KEY). Error: {type(e).__name__}"

    return {
        "messages": [("system", answer)],
        "final_answer": answer
    }

def market_analytics_node(state: RosterIQState) -> Dict[str, Any]:
    """
    Market Analytics Agent Node.
    Handles cross-table joins, root cause tracing, and web searches.
    Summarizes complex analytics for the user.
    """
    query = state["messages"][-1].content
    memory = state.get("memory_context", {})
    
    states = ["GA", "NY", "TX", "CA", "FL", "NH"]
    target_state = next((s for s in states if s in query.upper()), "NATIONAL")

    # 1. Retrieve Analysis Context
    if "root cause" in query.lower() or "why" in query.lower():
        analysis = tracer.trace_market_failure(target_state)
        data_context = f"Root Cause Analysis for {target_state}: {analysis['narrative']}"
    elif "search" in query.lower() or "what is" in query.lower() or "explanation" in query.lower():
        from src.tools.web_search import web_search
        results = web_search.search(query)
        data_context = f"Web Research Findings: {results}"
    else:
        data = query_tool.cross_table_join(target_state)
        data_context = f"Market Correlation Data for {target_state}: {data.to_json()}"

    # 2. Summarize with Knowledge Base Context
    prompt = f"""
    Analytical Findings: {data_context}
    
    Procedural Knowledge (Workflows): {memory.get('procedures_loaded', [])}
    Knowledge Base (Semantic): {memory.get('semantic', [])}
    Active Anomalies: {memory.get('active_alerts', [])}
    
    User Query: {query}
    
    Instruction: Answer the user's query professionally. If they are asking for an EXPLANATION 
    of a stage (like DART) or a rule, use the Procedural Knowledge provided. 
    Summarize any data findings naturally. DO NOT show raw JSON.
    """
    
    try:
        from langchain_core.messages import HumanMessage
        llm = get_llm()
        if llm:
            response = llm.invoke([HumanMessage(content=prompt)])
            answer = response.content
        else:
            raise ValueError("LLM not initialized correctly.")
    except Exception as e:
        answer = f"⚠️ Could not generate an AI summary. Raw data was retrieved but the LLM is unavailable (check GOOGLE_API_KEY). Error: {type(e).__name__}"

        
    return {
        "messages": [("system", answer)],
        "final_answer": answer
    }

def report_node(state):
    """
    Report Generation Node.
    Triggers the Markdown report generator.
    """
    report = report_gen.generate_pipeline_health_report()
    answer = f"Generated Operational Report:\n{report}"
    return {
        "messages": [("system", answer)],
        "final_answer": answer
    }
