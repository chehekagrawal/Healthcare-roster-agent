"""
src/agent/nodes.py
==================
Agent graph nodes for RosterIQ.
Contains both Engineer 1's Data Integration Nodes and Engineer 2's Memory Orchestration Nodes.
"""
from typing import Dict, Any
from src.agent.state import RosterIQState

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
        
    return {
        "memory_context": {
            "episodic": episodic_events,
            "semantic": semantic_hits,
            "change_summary": change_summary,
            "procedures_loaded": procedures_loaded
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
         user_intent = str(raw_content)[:100]

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
        from src.memory.episodic import log_episodic_event
        log_episodic_event(
            session_id=session_id,
            intent=user_intent,
            findings=state["final_answer"],
            kpis={"tools": event["tools_used"], "procedures": event["procedures_run"]},
            severity="Low"
        )
    except Exception as e:
        print(f"Warning: Could not log episodic event: {e}")

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

    # Initialize the LLM (using gemini-2.0-flash for fast routing)
    try:
        llm = ChatGoogleGenerativeAI(model="gemini-2.0-flash", temperature=0)
        structured_llm = llm.with_structured_output(RouterDecision)
        
        prompt = f"""
        You are the Supervisor for RosterIQ. Route the user's query to the correct sub-agent.
        
        pipeline_health_node: Handles triage, file errors, bottlenecks, and stuck files.
        market_analytics_node: Handles cross-market health, retry analysis, web searches, and SCS_PERCENT trends.
        
        User Query: {query}
        """
        
        decision = structured_llm.invoke(prompt)
        next_agent = decision.next_agent
        if next_agent not in ["pipeline_health_node", "market_analytics_node"]:
             next_agent = "pipeline_health_node" # Enforce strict routing
             
        print(f"[Supervisor] Routing query to: {next_agent}")
        return {"active_agent": next_agent}

    except Exception as e:
        print(f"[Supervisor] Routing failed, defaulting to pipeline. Error: {e}")
        return {"active_agent": "pipeline_health_node"}


# =============================================================================
# ENGINEER 1 - DATA ANALYTICS & REPORTING NODES
# =============================================================================

def pipeline_health_node(state):
    """
    Pipeline Health Agent Node.
    Analyzes stuck files, health scores, and duration anomalies.
    """
    query = state["messages"][-1].content.lower()
    
    # Logic to decide which of your A2 tools to call
    if "stuck" in query:
        data = query_tool.derive_metrics("stuck_duration")
        context = f"Current stuck files and their durations: {data.to_json()}"
    elif "anomaly" in query or "slow" in query:
        data = query_tool.detect_anomalies()
        context = f"Duration anomalies detected: {data.to_json()}"
    else:
        data = query_tool.derive_metrics("health")
        context = f"Overall pipeline health scores: {data.to_json()}"
    
    return {"messages": [("system", f"Data retrieved from Pipeline Engine: {context}")]}

def market_analytics_node(state):
    """
    Market Analytics Agent Node.
    Handles cross-table joins and root cause tracing.
    """
    query = state["messages"][-1].content.upper()
    
    # Extract state code (simple logic for the demo)
    # In a real run, the LLM provides the state code to this node.
    states = ["GA", "NY", "TX", "CA", "FL", "NH"]
    target_state = next((s for s in states if s in query), "NATIONAL")

    if "root cause" in query.lower() or "why" in query.lower():
        # Call your Extraordinary Root Cause Tool (Bonus Task)
        analysis = tracer.trace_market_failure(target_state)
        context = f"Root Cause Narrative: {analysis['narrative']}"
    elif "search" in query.lower() or "what is" in query.lower() or "definition" in query.lower():
        # C3: Web Search Tool execution
        from src.tools.web_search import web_search
        
        # Decide context template based on keywords
        template = "general"
        if "validation" in query.lower() or "availity" in query.lower():
            template = "complete_validation_failure"
        elif "medicaid" in query.lower() or "cms" in query.lower() or "rule" in query.lower():
            template = "cms_rule_changes"
            
        results = web_search.search(query, context_type=template)
        
        # Try to enrich the Semantic KB immediately with these findings
        enriched = web_search.enrich_semantic_kb(results)
        enrich_status = "(These findings were saved to the Semantic KB for future reasoning)" if enriched else ""
        
        context = f"Web Search Results for '{query}' [{template}]:\n{results}\n{enrich_status}"
    else:
        # Call your Cross-Table Join tool
        data = query_tool.cross_table_join(target_state)
        context = f"Market Correlation Data for {target_state}: {data.to_json()}"

    return {"messages": [("system", f"Analysis from Market Engine: {context}")]}

def report_node(state):
    """
    Report Generation Node.
    Triggers the Markdown report generator.
    """
    report = report_gen.generate_pipeline_health_report()
    return {"messages": [("system", f"Generated Operational Report:\n{report}")]}
