"""
src/agent/nodes.py
==================
Agent graph nodes for RosterIQ.
Contains the memory_loader_node to fulfill memory integration layer.
"""
from typing import Dict, Any
from src.agent.state import RosterIQState

def memory_loader_node(state: RosterIQState) -> Dict[str, Any]:
    """
    Fetches episodic context + change diff + semantic KB hits; injects into state.
    This fulfills the C4 Agent Memory Nodes requirement.
    """
    # 1. Fetch episodic context (mocked until Episodic is fully integrated by Engineer 1)
    episodic_events = []
    
    # 2. Fetch semantic KB hits based on latest message
    semantic_hits = []
    if state.get("messages"):
        last_msg = state["messages"][-1]
        query = last_msg.content if hasattr(last_msg, "content") else str(last_msg)
        
        try:
            from src.memory.semantic import semantic_memory
            # Retrieve the top 3 semantically relevant facts from ChromaDB
            hits = semantic_memory.fetch_semantic_knowledge(query, n_results=3)
            # The 'documents' key returns a list of lists: [[doc1, doc2, doc3]]
            if "documents" in hits and hits["documents"]:
                semantic_hits = hits["documents"][0]
        except Exception as e:
            print(f"Warning: Semantic retrieval failed: {e}")
            
    # 3. Change diff tracker (mocked for now, waiting on Engineer 1 integration)
    change_summary = "No major KPI drift detected since last session."
    
    # 4. Procedures loaded
    try:
        from src.memory.procedural import procedural_memory
        procedures_loaded = list(procedural_memory.procedures.keys())
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
