"""
src/agent/state.py
==================
RosterIQ shared state schema — used by ALL agent nodes.
Both partners import this. Do NOT modify without syncing.

Partner A uses: tool_outputs, chart_outputs, final_answer
Partner C uses: memory_context, procedure_context, session_id
"""

from __future__ import annotations

from typing import Annotated, Any, Dict, List, Optional
from typing_extensions import TypedDict

from langchain_core.messages import AnyMessage
from langgraph.graph.message import add_messages


class RosterIQState(TypedDict):
    # ── Core conversation ──────────────────────────────────────
    messages: Annotated[List[AnyMessage], add_messages]
    """Full message history. add_messages reducer appends (never overwrites)."""

    session_id: str
    """Unique session identifier — maps to LangGraph thread_id and SQLite session."""

    # ── Agent routing ──────────────────────────────────────────
    active_agent: str
    """Which agent is currently handling the turn.
    Values: 'supervisor' | 'pipeline_agent' | 'market_agent'"""

    # ── Tool outputs (Partner A) ───────────────────────────────
    tool_outputs: List[Dict[str, Any]]
    """Raw structured results from data tools (DuckDB queries, procedures)."""

    chart_outputs: List[Any]
    """Plotly figure objects to be rendered inline in Streamlit."""

    # ── Memory context (Partner C) ────────────────────────────
    memory_context: Dict[str, Any]
    """Populated by memory_loader_node. Contains:
    - 'episodic': list of recent EpisodicEvent dicts
    - 'semantic': list of top-3 domain KB strings retrieved for current query
    - 'change_summary': natural language diff from change_detector
    - 'procedures_loaded': list of procedure names available this session
    """

    procedure_context: Optional[str]
    """Name of the active procedure being executed (if any)."""

    # ── Final output ───────────────────────────────────────────
    final_answer: Optional[str]
    """The agent's compiled natural language response for this turn."""


# ── Default factory ────────────────────────────────────────────
def default_state(session_id: str) -> RosterIQState:
    """Returns a clean initial state for a new session."""
    return RosterIQState(
        messages=[],
        session_id=session_id,
        active_agent="supervisor",
        tool_outputs=[],
        chart_outputs=[],
        memory_context={
            "episodic": [],
            "semantic": [],
            "change_summary": "",
            "procedures_loaded": [],
        },
        procedure_context=None,
        final_answer=None,
    )
