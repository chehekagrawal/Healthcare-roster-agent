import sys
from dotenv import load_dotenv
load_dotenv()
from src.agent.graph import build_roster_graph

print("building...")
try:
    agent = build_roster_graph()
    print("built!")
    inputs = {"messages": [("user", "hi")], "session_id": "test"}
    config = {"configurable": {"thread_id": "test"}}
    print("invoking...")
    out = agent.invoke(inputs, config)
    print("done!")
    print(out)
except Exception as e:
    import traceback
    traceback.print_exc()
