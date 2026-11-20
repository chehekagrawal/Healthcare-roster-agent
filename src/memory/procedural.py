"""
src/memory/procedural.py
========================
Procedural Memory (Diagnostic Workflow Registry)
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
from src.paths import CHROMADB_PATH, SLA_THRESHOLD
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
        # Use the same lightweight hash embedder as the other collections.
        # Without it ChromaDB falls back to its default ONNX model, which it
        # downloads on first use (and crashes offline).
        from src.memory.semantic import _EMBED_FN
        try:
            self._collection = self._client.get_or_create_collection(
                name=PROCEDURE_COLLECTION,
                embedding_function=_EMBED_FN,
                metadata={"hnsw:space": "cosine"}
            )
        except ValueError:
            # A registry built with the old default embedder: rebuild it.
            self._client.delete_collection(PROCEDURE_COLLECTION)
            self._collection = self._client.create_collection(
                name=PROCEDURE_COLLECTION,
                embedding_function=_EMBED_FN,
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

        # Keep the vector index's version metadata in step with the JSON.
        self._sync_to_chroma()
        return proc

    def run_procedure(self, name: str, db_engine: Any, overrides: Dict[str, Any] = None) -> Any:
        """
        Executes the logic of a procedure using the duckdb_engine.
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
    # Each procedure runs real SQL through the MetricsEngine and returns
    # {"status", "proc", "version", "used_params", "data", "summary"}.

    def _result(self, name, params, data, summary):
        return {
            "status": "success",
            "proc": name,
            "version": self.procedures[name].get("version", 1),
            "used_params": params,
            "data": data,
            "summary": summary,
        }

    def _execute_triage(self, db_engine, params):
        """Stuck ROs ranked by red/yellow flags and days stuck (weights from params)."""
        from src.tools.data_query import triage_stuck_ros
        df = triage_stuck_ros(
            db_engine,
            red_weight=params.get("red_weight", 5),
            yellow_weight=params.get("yellow_weight", 1),
            time_weight=params.get("time_weight", 2),
            state=params.get("state_filter"),
            limit=params.get("limit", 10),
        )
        records = df.to_dict(orient="records")
        if records:
            top = records[0]
            summary = (f"{len(records)} stuck RO(s). Highest priority: {top['RO_ID']} "
                       f"({top['ORG_NM']}, {top['CNT_STATE']}) at {top['LATEST_STAGE_NM']}, "
                       f"{top['red_flags']} red / {top['yellow_flags']} yellow flags, "
                       f"{top['days_stuck']} days stuck, score {top['escalation_score']:.0f}.")
        else:
            summary = "No stuck ROs."
        return self._result("triage_stuck_ros", params, records, summary)

    def _execute_market_health(self, db_engine, params):
        """
        Per state: latest and 12-month success rate, previous month (for trend),
        stuck count and red-flag density, plus the correlation between red-flag
        density and the 12-month success rate across states.
        """
        from src.tools.data_query import _RED_COUNT
        threshold = float(params.get("scs_threshold", SLA_THRESHOLD))
        state = params.get("state_filter")
        df = db_engine.query(f"""
            WITH files AS (
                SELECT CNT_STATE,
                       COUNT(*) AS total_ros,
                       COUNT(*) FILTER (WHERE IS_STUCK = 1) AS stuck_ros,
                       AVG({_RED_COUNT}) AS red_flag_density
                FROM roster GROUP BY CNT_STATE
            ),
            months AS (
                SELECT MARKET, MONTH, SCS_PERCENT,
                       ROW_NUMBER() OVER (PARTITION BY MARKET ORDER BY MONTH_DATE DESC) AS rn
                FROM market
            ),
            yearly AS (SELECT MARKET, AVG(SCS_PERCENT) AS avg_scs_percent FROM market GROUP BY MARKET)
            SELECT f.CNT_STATE AS state,
                   cur.MONTH AS latest_month,
                   cur.SCS_PERCENT AS latest_scs_percent,
                   prev.SCS_PERCENT AS previous_scs_percent,
                   y.avg_scs_percent,
                   f.total_ros, f.stuck_ros, f.red_flag_density
            FROM files f
            JOIN months cur  ON cur.MARKET = f.CNT_STATE AND cur.rn = 1
            LEFT JOIN months prev ON prev.MARKET = f.CNT_STATE AND prev.rn = 2
            JOIN yearly y ON y.MARKET = f.CNT_STATE
            ORDER BY y.avg_scs_percent ASC
        """)
        correlation = None
        if len(df) >= 3:
            corr = df["red_flag_density"].corr(df["avg_scs_percent"])
            correlation = None if corr != corr else round(float(corr), 3)  # NaN check
        df["trend"] = [
            "n/a" if p != p or p is None else ("up" if c > p else ("down" if c < p else "flat"))
            for c, p in zip(df["latest_scs_percent"], df["previous_scs_percent"])
        ]
        df["below_threshold_latest"] = df["latest_scs_percent"] < threshold
        df["below_threshold_avg"] = df["avg_scs_percent"] < threshold
        if state:
            df = df[df["state"] == str(state).upper()]
        flagged = df[df["below_threshold_latest"] | df["below_threshold_avg"]]
        summary = (f"{int(df['below_threshold_latest'].sum())} market(s) below {threshold:g}% in their latest month, "
                   f"{int(df['below_threshold_avg'].sum())} below it on the 12-month average. "
                   f"Correlation between red-flag density and 12-month success rate across states: {correlation}.")
        result = self._result("market_health_report", params, flagged.to_dict(orient="records"), summary)
        result["correlation_red_density_vs_scs"] = correlation
        return result

    def _execute_retry_analysis(self, db_engine, params):
        """
        Retry lift per market = share of retried transactions that succeed
        (NEXT_ITER_SCS_CNT / (NEXT_ITER_SCS_CNT + NEXT_ITER_FAIL_CNT)), next to
        the share of re-run files (RUN_NO > 1) that still failed in CSV 1.
        Markets whose lift is below min_lift_pct are flagged: retries there add
        latency without recovering much.
        """
        min_lift = float(params.get("min_lift_pct", 5.0))
        state = params.get("state_filter")
        df = db_engine.query("""
            WITH lift AS (
                SELECT MARKET,
                       SUM(NEXT_ITER_SCS_CNT) AS retry_success,
                       SUM(NEXT_ITER_FAIL_CNT) AS retry_fail,
                       100.0 * SUM(NEXT_ITER_SCS_CNT)
                             / NULLIF(SUM(NEXT_ITER_SCS_CNT) + SUM(NEXT_ITER_FAIL_CNT), 0) AS retry_lift_pct
                FROM market GROUP BY MARKET
            ),
            reruns AS (
                SELECT CNT_STATE,
                       COUNT(*) FILTER (WHERE RUN_NO > 1) AS rerun_files,
                       100.0 * COUNT(*) FILTER (WHERE RUN_NO > 1 AND IS_FAILED = 1)
                             / NULLIF(COUNT(*) FILTER (WHERE RUN_NO > 1), 0) AS rerun_still_failed_pct
                FROM roster GROUP BY CNT_STATE
            )
            SELECT l.MARKET AS state, l.retry_success, l.retry_fail, l.retry_lift_pct,
                   r.rerun_files, r.rerun_still_failed_pct
            FROM lift l LEFT JOIN reruns r ON r.CNT_STATE = l.MARKET
            ORDER BY l.retry_lift_pct ASC NULLS LAST
        """)
        if state:
            df = df[df["state"] == str(state).upper()]
        df["retries_ineffective"] = df["retry_lift_pct"].fillna(0) < min_lift
        bad = df[df["retries_ineffective"]]
        summary = (f"{len(bad)} market(s) where under {min_lift:g}% of retried transactions succeed "
                   f"(retries add latency without recovering volume)." if len(bad)
                   else f"Retries recover at least {min_lift:g}% of transactions in every market.")
        return self._result("retry_effectiveness_analysis", params, df.to_dict(orient="records"), summary)

    def _execute_bottleneck_scan(self, db_engine, params):
        """
        Finds systemic bottlenecks: (stage, state, source system) groups with at
        least `min_affected_ros` files running more than `anomaly_multiplier`
        times the stage's historical average. Ranked by affected files × average
        deviation. ISF generation is excluded (its AVG column is on a different
        scale; see schema.sql).
        """
        mult = float(params.get("anomaly_multiplier", 2.0))
        min_ros = int(params.get("min_affected_ros", 3))
        df = db_engine.query("""
            WITH d AS (
                SELECT r.CNT_STATE, r.SRC_SYS, s.stage, s.ratio
                FROM roster r
                CROSS JOIN LATERAL (VALUES
                    ('DART_GENERATION',    r.DART_GEN_DURATION / NULLIF(r.AVG_DART_GENERATION_DURATION, 0)),
                    ('DART_UI_VALIDATION', r.DART_UI_VALIDATION_DURATION / NULLIF(r.AVG_DART_UI_VLDTN_DURATION, 0)),
                    ('SPS_LOAD',           r.SPS_LOAD_DURATION / NULLIF(r.AVG_SPS_LOAD_DURATION, 0))
                ) AS s(stage, ratio)
                WHERE s.ratio > ?
            )
            SELECT stage, CNT_STATE AS state, SRC_SYS AS source_system,
                   COUNT(*) AS affected_ros,
                   ROUND(AVG(ratio), 2) AS avg_deviation,
                   ROUND(MEDIAN(ratio), 2) AS median_deviation,
                   ROUND(COUNT(*) * AVG(ratio), 1) AS impact_score
            FROM d
            GROUP BY stage, CNT_STATE, SRC_SYS
            HAVING COUNT(*) >= ?
            ORDER BY impact_score DESC
            LIMIT 20
        """, [mult, min_ros])
        records = df.to_dict(orient="records")
        if records:
            t = records[0]
            summary = (f"{len(records)} systemic bottleneck group(s). Largest: {t['stage']} in {t['state']} "
                       f"from {t['source_system']}, {t['affected_ros']} files at {t['avg_deviation']}x "
                       f"the usual duration on average.")
        else:
            summary = f"No stage/state/source group has {min_ros}+ files above {mult:g}x their usual duration."
        return self._result("pipeline_bottleneck_scan", params, records, summary)


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
    
    # (Running this file used to call update_procedure_params() on the real
    # procedures.json, bumping its version every time. It no longer writes.)
    from src.db.duckdb_engine import MetricsEngine
    eng = MetricsEngine()
    for name in pm.list_procedures():
        print(f"\n{name}: {pm.run_procedure(name, eng)['summary']}")
