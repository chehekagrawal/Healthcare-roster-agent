"""
src/tools/web_search.py
=======================
Partner C — Web Search Tool for KB Enrichment
Uses Tavily API to fetch targeted external health data.
Includes 4 specific templates to satisfy the Web Integration judging criteria.
"""

import os
from typing import Dict, Any, List
try:
    from tavily import TavilyClient
except ImportError:
    TavilyClient = None

class WebSearchTool:
    def __init__(self):
        self.api_key = os.getenv("TAVILY_API_KEY")
        if self.api_key and TavilyClient:
            self.client = TavilyClient(api_key=self.api_key)
        else:
            self.client = None
            print("WARNING: TavilyClient not initialized. Check TAVILY_API_KEY and tavily-python package.")

    def search(self, query: str, context_type: str = "general") -> Dict[str, Any]:
        """
        Executes a targeted search using the Tavily API.
        context_type determines which template is applied to the raw query.
        """
        if not self.client:
            return {"error": "Tavily client not configured. Cannot perform search."}

        # Apply templates based on context_type
        templated_query = self._apply_template(query, context_type)
        
        try:
            # Execute actual search
            response = self.client.search(
                query=templated_query,
                search_depth="advanced",
                max_results=3
            )
            
            # Extract and format results
            results = []
            for item in response.get("results", []):
                results.append({
                    "title": item.get("title"),
                    "url": item.get("url"),
                    "content": item.get("content")
                })
                
            return {
                "query_used": templated_query,
                "results": results
            }
        except Exception as e:
            return {"error": f"Search failed: {str(e)}"}

    def _apply_template(self, query: str, context_type: str) -> str:
        """
        4 specific templates mapped directly to the implementation plan:
        1. complete_validation_failure
        2. cms_rule_changes
        3. lob_compliance
        4. provider_lookup
        """
        if context_type == "complete_validation_failure":
            return f"Healthcare roster EDI 834 data processing {query} complete validation failure AvailityPDM solutions"
            
        elif context_type == "cms_rule_changes":
            return f"CMS Medicaid recent rule changes regarding provider directory accuracy in {query}"
            
        elif context_type == "lob_compliance":
            return f"{query} Line of Business (LOB) healthcare data submission compliance standards penalties"
            
        elif context_type == "provider_lookup":
            return f"{query} healthcare provider organization details locations"
            
        else:
            # "general" or anything else
            return query

# Convenience singleton
web_search = WebSearchTool()

if __name__ == "__main__":
    print("Testing WebSearchTool Templates...")
    tool = WebSearchTool()
    print("1. Failure Template:", tool._apply_template("demographics", "complete_validation_failure"))
    print("2. CMS Template:", tool._apply_template("Florida", "cms_rule_changes"))
    print("3. LOB Template:", tool._apply_template("Medicare Advantage", "lob_compliance"))
    print("4. Provider Template:", tool._apply_template("Norton Hospitals", "provider_lookup"))
