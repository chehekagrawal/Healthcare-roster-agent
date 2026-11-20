"""State detection, routing, the LangGraph agent end to end, and the Streamlit app."""
import os
import sqlite3

import pytest

from src.paths import MEMORY_DB
from src.tools.states import detect_state

STATES = ['AR', 'AZ', 'CA', 'CO', 'CT', 'DC', 'FL', 'GA', 'IA', 'IN', 'KS', 'KY', 'LA', 'MD', 'ME', 'MO',
          'NATIONAL', 'NE', 'NH', 'NJ', 'NM', 'NV', 'NY', 'OH', 'SC', 'TN', 'TX', 'VA', 'WA', 'WI', 'WNY', 'WV']


@pytest.mark.parametrize("q,expected", [
    ("What is the root cause for FL?", "FL"),        # used to return CA ("CAUSE")
    ("why is ga failing", "GA"),
    ("Why is Georgia struggling?", "GA"),
    ("success rate in new york", "NY"),
    ("West Virginia trend", "WV"),
    ("trend for WNY", "WNY"),
    ("Kansas retries", "KS"),                       # used to be unknown (only 6 states)
    ("show me IN", "IN"),
    ("what is happening in the pipeline", None),     # "in" is a word, not Indiana
    ("tell me about the market", None),
    ("how are we doing nationally", "NATIONAL"),
])
def test_detect_state(q, expected):
    assert detect_state(q, STATES) == expected


def test_latest_user_text_skips_agent_replies():
    from src.agent.nodes import latest_user_text
    msgs = [("user", "first question"), ("assistant", "answer"), ("user", "second question"),
            ("assistant", "second answer")]
    assert latest_user_text(msgs) == "second question"


@pytest.mark.parametrize("q,expected", [
    ("which files are stuck?", "pipeline_health_node"),
    ("why are files stuck in DART?", "pipeline_health_node"),
    ("why is GA failing?", "market_analytics_node"),
    ("root cause of the drop", "market_analytics_node"),
    ("Florida success rate", "market_analytics_node"),
    ("how is the agent doing", "pipeline_health_node"),  # "ga" inside "agent" no longer matches
])
def test_keyword_fallback_routing(q, expected):
    from src.agent.nodes import keyword_route
    assert keyword_route(q) == expected


@pytest.fixture(scope="module")
def agent():
    from src.agent.graph import build_roster_graph
    return build_roster_graph()


def _interactions(session_id):
    conn = sqlite3.connect(MEMORY_DB)
    rows = conn.execute("SELECT user_query FROM interactions WHERE session_id=? ORDER BY id",
                        (session_id,)).fetchall()
    conn.close()
    return [r[0] for r in rows]


def test_agent_turns_route_answer_and_log_once(agent, monkeypatch):
    from src.agent import nodes
    prompts = []

    class FakeLLM:
        def invoke(self, messages):
            prompts.append(messages[0].content)
            class R:  # noqa: D401
                content = "pipeline_health_node" if "decide which agent" in messages[0].content else "OK"
            if "decide which agent" in messages[0].content and "Florida" in messages[0].content:
                R.content = "market_analytics_node"
            return R()

    monkeypatch.setattr(nodes, "get_llm", lambda: FakeLLM())
    config = {"configurable": {"thread_id": "SES-agent"}}

    out1 = agent.invoke({"messages": [("user", "which files are stuck?")], "session_id": "SES-agent"}, config)
    assert out1["active_agent"] == "pipeline_health_node"
    assert out1["procedure_context"] == "triage_stuck_ros"

    out2 = agent.invoke({"messages": [("user", "Why is Florida failing?")], "session_id": "SES-agent"}, config)
    assert out2["active_agent"] == "market_analytics_node"
    assert out2["final_answer"] == "OK"
    assert out2["tool_outputs"] == [{"name": "root_cause_tracer"}]
    assert any("Root cause trace for FL" in p for p in prompts)

    # Each turn logged once, with ITS question (not the thread's first one).
    assert _interactions("SES-agent") == ["which files are stuck?", "Why is Florida failing?"]

    # Prompts stay small (they used to embed 5.4 MB of JSON).
    assert max(len(p) for p in prompts) < 20000


def test_agent_without_llm_returns_data_findings(agent):
    config = {"configurable": {"thread_id": "SES-nollm"}}
    out = agent.invoke({"messages": [("user", "what is the overall pipeline health?")],
                        "session_id": "SES-nollm"}, config)
    assert "Composite health score" in out["final_answer"]
    assert "AI summary unavailable" in out["final_answer"]


@pytest.mark.slow
def test_streamlit_app_end_to_end():
    from streamlit.testing.v1 import AppTest
    root = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
    at = AppTest.from_file(os.path.join(root, "app.py"), default_timeout=300)
    at.run()
    assert not at.exception
    for question, expected in [("GA trend", "96.97%"),
                               ("which files are stuck?", "RO-2380443"),
                               ("Why is Florida failing?", "FL")]:
        at.chat_input[0].set_value(question).run()
        assert not at.exception
        answer = " ".join(md.value for md in at.chat_message[-1].markdown)
        assert expected in answer, (question, answer[:300])
