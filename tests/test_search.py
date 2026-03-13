from src.pipeline_tools import get_web_search_tool

# Initialize the tool
search = get_web_search_tool()

# Simulate the LLM asking a question
print("Searching for CMS provider rules...")
result = search.invoke("latest CMS provider roster compliance rules 2026")

print("\n--- Search Results ---")
print(result)