import sqlite3
from langgraph.graph import StateGraph, START, END
from langgraph.checkpoint.sqlite import SqliteSaver

from src.agent.state import RosterIQState
from src.agent.nodes import (
    memory_loader_node,
    supervisor_node,
    pipeline_health_node,
    market_analytics_node,
    memory_writer_node
)

def build_roster_graph():
    """
    Assembles the RosterIQ Agent Graph, combining both Partner A's data nodes 
    and Partner C's orchestration and memory nodes.
    """
    # 1. Initialize StateGraph
    workflow = StateGraph(RosterIQState)

    # 2. Add Nodes
    workflow.add_node("memory_loader", memory_loader_node)
    workflow.add_node("supervisor", supervisor_node)
    workflow.add_node("pipeline_agent", pipeline_health_node)
    workflow.add_node("market_agent", market_analytics_node)
    workflow.add_node("memory_writer", memory_writer_node)

    # 3. Define Edges (The Flow)
    workflow.add_edge(START, "memory_loader")
    workflow.add_edge("memory_loader", "supervisor")
    
    # Conditional routing from supervisor based on intent
    def route_after_supervisor(state: RosterIQState) -> str:
        # Defaults to pipeline agent if routing fails
        return state.get("active_agent", "pipeline_health_node")
        
    workflow.add_conditional_edges(
        "supervisor",
        route_after_supervisor,
        {
            "pipeline_health_node": "pipeline_agent",
            "market_analytics_node": "market_agent"
        }
    )

    # Both sub-agents funnel into the memory writer before completing
    workflow.add_edge("pipeline_agent", "memory_writer")
    workflow.add_edge("market_agent", "memory_writer")
    
    workflow.add_edge("memory_writer", END)

    # 4. Set up the SqliteSaver checkpointer for long-term thread state storage
    conn = sqlite3.connect("roster_iq_threads.db", check_same_thread=False)
    memory = SqliteSaver(conn)

    # 5. Compile the graph
    app = workflow.compile(checkpointer=memory)
    return app


def smoke_test():
    """End-to-end smoke test hitting data tools + memory layers."""
    app = build_roster_graph()
    
    config = {"configurable": {"thread_id": "smoke-test-thread-1"}}
    
    # Test query designed to trigger market logic and memory injection
    input_state = {
        "messages": [("user", "Why is the GA market failing and what is the root cause?")],
        "session_id": "test_session_1"
    }
    
    print("--- Starting RosterIQ Smoke Test ---")
    
    for event in app.stream(input_state, config, stream_mode="values"):
        msgs = event.get("messages", [])
        if msgs:
            last_msg = msgs[-1]
            content = last_msg.content if hasattr(last_msg, 'content') else str(last_msg)
            print(f"State Update -> Messages Count: {len(msgs)} | Active Agent: {event.get('active_agent', 'Initializing')}")
            print(f"Latest Agent Message: {content[:150]}...\n")
            
    print("--- Smoke Test Complete ---")


if __name__ == "__main__":
    smoke_test()
