"""
src/memory/procedural.py
========================
Partner C — Procedural Memory (Diagnostic Workflow Registry)
Manages the 4 parameterized SQL-based procedures used by the agent.
Allows the LLM to retrieve, run, and update procedures at runtime.
"""

import json
import os
from typing import Dict, Any, List
import chromadb
from chromadb.config import Settings
import datetime

PROCEDURES_FILE = os.path.join(os.path.dirname(__file__), "procedures.json")
CHROMADB_PATH = os.getenv("CHROMADB_PATH", "memory/chromadb")
PROCEDURE_COLLECTION = "procedure_registry"

class ProceduralMemory:
    """
    Manages diagnostic workflows (procedures).
    - Loads from procedures.json
    - Seeds a ChromaDB collection for fuzzy natural language lookup
    - Allows the LLM to update parameters and bump versions
    """

    def __init__(self, json_path: str = PROCEDURES_FILE, db_path: str = CHROMADB_PATH):
        self.json_path = json_path
        
        # Load JSON definition
        if not os.path.exists(self.json_path):
            raise FileNotFoundError(f"Procedures file not found at {self.json_path}")
        with open(self.json_path, 'r', encoding='utf-8') as f:
            self.procedures = json.load(f)

        # Connect to ChromaDB for semantic lookup
        self._client = chromadb.PersistentClient(
            path=db_path,
            settings=Settings(anonymized_telemetry=False)
        )
        self._collection = self._client.get_or_create_collection(
            name=PROCEDURE_COLLECTION,
            metadata={"hnsw:space": "cosine"}
        )
        self._sync_to_chroma()

    def _sync_to_chroma(self):
        """
        Upserts all loaded procedures into ChromaDB so the agent can find them 
        using natural language (e.g. 'find bottlenecks' -> pipeline_bottleneck_scan).
        """
        ids = list(self.procedures.keys())
        docs = [p["description"] for p in self.procedures.values()]
        metas = [{"name": name, "version": p.get("version", 1)} for name, p in self.procedures.items()]

        self._collection.upsert(
            ids=ids,
            documents=docs,
            metadatas=metas
        )

    def list_procedures(self) -> Dict[str, str]:
        """Returns a dict of procedure_name -> description."""
        return {name: p["description"] for name, p in self.procedures.items()}

    def get_procedure(self, name: str) -> Dict[str, Any]:
        """Returns the full definition of a specific procedure."""
        if name not in self.procedures:
            raise ValueError(f"Procedure '{name}' not found in registry.")
        return self.procedures[name]

    def find_relevant_procedures(self, query: str, top_k: int = 1) -> List[Dict[str, Any]]:
        """
        Fuzzy lookup for procedures based on agent intent.
        Example: query="scan for slow stages" returns the pipeline_bottleneck_scan procedure.
        """
        if self._collection.count() == 0:
            return []

        results = self._collection.query(
            query_texts=[query],
            n_results=min(top_k, self._collection.count()),
            include=["documents", "metadatas", "distances"]
        )
        
        found = []
        for doc, meta, dist in zip(results["documents"][0], results["metadatas"][0], results["distances"][0]):
            name = meta["name"]
            found.append({
                "name": name,
                "description": doc,
                "relevance_score": round(1 - dist, 4),
                "params": self.procedures[name]["params"]
            })
        return found

    def update_procedure_params(self, name: str, new_params: Dict[str, Any], user_id: str = "system") -> Dict[str, Any]:
        """
        Allows the agent to modify procedure parameters (e.g., weighting a red flag heavier).
        Bumps the version number and records updated_at/created_by logic.
        """
        if name not in self.procedures:
            raise ValueError(f"Procedure '{name}' not found.")

        proc = self.procedures[name]
        
        # Update params
        proc["params"].update(new_params)
        
        # Bump version and set metadata
        proc["version"] = proc.get("version", 1) + 1
        proc["updated_at"] = datetime.datetime.now().strftime("%Y-%m-%d")
        proc["created_by"] = user_id

        # Save back to JSON
        with open(self.json_path, 'w', encoding='utf-8') as f:
            json.dump(self.procedures, f, indent=2)

        return proc

    def run_procedure(self, name: str, db_engine: Any, overrides: Dict[str, Any] = None) -> Any:
        """
        Executes the logic of a procedure using Partner A's duckdb_engine.
        This is a router that delegates to specific execute_* methods based on name.
        """
        if name not in self.procedures:
            raise ValueError(f"Procedure '{name}' not found.")
            
        params = self.procedures[name]["params"].copy()
        if overrides:
            params.update(overrides)

        # Delegate execution based on the procedure name
        if name == "triage_stuck_ros":
            return self._execute_triage(db_engine, params)
        elif name == "market_health_report":
            return self._execute_market_health(db_engine, params)
        elif name == "retry_effectiveness_analysis":
            return self._execute_retry_analysis(db_engine, params)
        elif name == "pipeline_bottleneck_scan":
            return self._execute_bottleneck_scan(db_engine, params)
        else:
            raise NotImplementedError(f"Execution logic for '{name}' is not yet implemented.")

    # ── Internal Execution Logic ────────────────────────────────────────────────────────
    
    def _execute_triage(self, db_engine, params):
        # Calls DuckDB to execute triage scoring
        # (Will hook into Partner A's db wrapper here)
        return {"status": "success", "proc": "triage_stuck_ros", "used_params": params, "data": []}

    def _execute_market_health(self, db_engine, params):
        return {"status": "success", "proc": "market_health_report", "used_params": params, "data": []}
        
    def _execute_retry_analysis(self, db_engine, params):
        return {"status": "success", "proc": "retry_effectiveness_analysis", "used_params": params, "data": []}
        
    def _execute_bottleneck_scan(self, db_engine, params):
        return {"status": "success", "proc": "pipeline_bottleneck_scan", "used_params": params, "data": []}


# ── Convenience Singleton ─────────────────────────────────────────────────────────────
# Usage:
#   from src.memory.procedural import procedural_memory
#   proc = procedural_memory.get_procedure("triage_stuck_ros")
procedural_memory = ProceduralMemory()

if __name__ == "__main__":
    pm = ProceduralMemory()
    print("Loaded Procedures:")
    for name, desc in pm.list_procedures().items():
        print(f" - {name}: (v{pm.get_procedure(name).get('version', 1)}) {desc}")
        
    print("\nTesting Fuzzy Lookup ('scan for slow stages'):")
    res = pm.find_relevant_procedures("scan for slow stages", top_k=1)
    print(res)
    
    print("\nTesting Parameter Update:")
    updated = pm.update_procedure_params("triage_stuck_ros", {"red_weight": 5})
    print(f"Updated triage_stuck_ros to v{updated['version']}, red_weight is now {updated['params']['red_weight']}")
