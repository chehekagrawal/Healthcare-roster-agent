"""
src/memory/semantic.py
======================
Semantic Memory (Domain Knowledge Base)
ChromaDB-backed store of 40+ healthcare roster pipeline knowledge items.

Usage:
    from src.memory.semantic import SemanticMemory
    sm = SemanticMemory()
    results = sm.fetch(\"what does IS_STUCK mean\")
"""

from __future__ import annotations

import os
import hashlib
import numpy as np
from typing import List, Dict, Any

import chromadb
from chromadb.config import Settings
from chromadb import EmbeddingFunction, Documents, Embeddings

# ── Constants ──────────────────────────────────────────────────────────────────
CHROMADB_PATH = os.getenv("CHROMADB_PATH", "memory/chromadb")
COLLECTION_NAME = "semantic_knowledge"

# ── Lightweight Hash Embedding (no model download needed) ─────────────────────
class SimpleHashEmbeddingFunction(EmbeddingFunction):
    """
    A deterministic, fast embedding function using hashing.
    Avoids the large ONNX model download while staying fully compatible with ChromaDB.
    Not as accurate as neural embeddings but sufficient for keyword-level semantic retrieval.
    """
    DIM = 256

    def __call__(self, input: Documents) -> Embeddings:
        embeddings = []
        for text in input:
            vec = np.zeros(self.DIM, dtype=np.float32)
            words = str(text).lower().split()
            for word in words:
                idx = int(hashlib.md5(word.encode()).hexdigest(), 16) % self.DIM
                vec[idx] += 1.0
            norm = np.linalg.norm(vec)
            if norm > 0:
                vec /= norm
            embeddings.append(vec.tolist())
        return embeddings

_EMBED_FN = SimpleHashEmbeddingFunction()

# ── Knowledge Base ─────────────────────────────────────────────────────────────
# Each entry: {"id": unique str, "text": the knowledge item, "metadata": dict}
# The agent will embed "text" and retrieve the top-k most similar items.

KNOWLEDGE_ITEMS: List[Dict[str, Any]] = [

    # ── CATEGORY 1: Pipeline Stages ──────────────────────────────────────────
    {
        "id": "stage_01",
        "text": (
            "PRE_PROCESSING is the first pipeline stage. It validates the incoming "
            "roster file structure, checks encoding, and maps to internal formats. "
            "Failures here usually indicate file-format or encoding errors at source."
        ),
        "metadata": {"category": "pipeline_stage", "concept": "PRE_PROCESSING"},
    },
    {
        "id": "stage_02",
        "text": (
            "MAPPING_APPROVAL is the second pipeline stage. It requires a human or "
            "automated reviewer to approve data mapping configurations. "
            "Long MAPPING_APROVAL_DURATION values indicate manual intervention delay — "
            "a human-in-the-loop bottleneck, not a data quality issue."
        ),
        "metadata": {"category": "pipeline_stage", "concept": "MAPPING_APPROVAL"},
    },
    {
        "id": "stage_03",
        "text": (
            "ISF_GENERATION (Internal Staging Format generation) is the third stage. "
            "It converts the approved mapping into an intermediate format before DART. "
            "ISF = Internal Staging Format. Slowness here often signals data volume spikes."
        ),
        "metadata": {"category": "pipeline_stage", "concept": "ISF_GENERATION"},
    },
    {
        "id": "stage_04",
        "text": (
            "DART_GENERATION is the fourth stage. DART = Data Aggregation and Reporting Tool. "
            "It aggregates the ISF data and prepares it for validation in DART UI. "
            "This is the most common stage where 'Complete Validation Failure' occurs. "
            "A DART_GEN_DURATION more than 3x the historical average signals a critical bottleneck."
        ),
        "metadata": {"category": "pipeline_stage", "concept": "DART_GENERATION"},
    },
    {
        "id": "stage_05",
        "text": (
            "DART_REVIEW is the fifth pipeline stage. After DART generation, a review step "
            "validates the aggregated data before it is loaded to the UI for full validation. "
            "DART_REVIEW_DURATION inflating across retries (RUN_NO > 1) without IS_STUCK "
            "resolving indicates retries are adding latency but not recovering the file."
        ),
        "metadata": {"category": "pipeline_stage", "concept": "DART_REVIEW"},
    },
    {
        "id": "stage_06",
        "text": (
            "DART_UI_VALIDATION is the sixth stage. It runs the full automated validation "
            "suite in the DART user interface — checking provider NPI, taxonomy codes, "
            "address completeness, and compliance fields. Failures here are often tied "
            "to CMS or state Medicaid rule changes."
        ),
        "metadata": {"category": "pipeline_stage", "concept": "DART_UI_VALIDATION"},
    },
    {
        "id": "stage_07",
        "text": (
            "SPS_LOAD is the final pipeline stage. SPS = System of Provider Services. "
            "It loads successfully validated provider records into the production system. "
            "SPS_LOAD_HEALTH is the most important single health flag: Red here means "
            "the file failed to enter SPS cleanly and is the primary quality proxy "
            "when record-level counts are not available."
        ),
        "metadata": {"category": "pipeline_stage", "concept": "SPS_LOAD"},
    },

    # ── CATEGORY 2: FILE_STATUS_CD Decoder ───────────────────────────────────
    {
        "id": "status_01",
        "text": (
            "FILE_STATUS_CD = 9 means STOPPED. The pipeline has terminated abnormally. "
            "An RO with FILE_STATUS_CD=9 and IS_STUCK=0 has failed completely; "
            "with IS_STUCK=1 it may still recover via operator intervention."
        ),
        "metadata": {"category": "file_status", "concept": "FILE_STATUS_CD_9"},
    },
    {
        "id": "status_02",
        "text": (
            "FILE_STATUS_CD = 45 means the RO is currently in DART_REVIEW stage. "
            "The file has passed DART_GENERATION and is awaiting reviewer approval."
        ),
        "metadata": {"category": "file_status", "concept": "FILE_STATUS_CD_45"},
    },
    {
        "id": "status_03",
        "text": (
            "FILE_STATUS_CD = 49 means the RO is currently in DART_GENERATION stage. "
            "The file is actively being aggregated by the DART system."
        ),
        "metadata": {"category": "file_status", "concept": "FILE_STATUS_CD_49"},
    },
    {
        "id": "status_04",
        "text": (
            "FILE_STATUS_CD = 65 means the RO is in SPS_LOAD stage. "
            "The DART processing is complete; records are being loaded into SPS."
        ),
        "metadata": {"category": "file_status", "concept": "FILE_STATUS_CD_65"},
    },
    {
        "id": "status_05",
        "text": (
            "FILE_STATUS_CD = 99 means RESOLVED. The RO has completed successfully "
            "and all provider records have been loaded into SPS. "
            "A transition from FILE_STATUS_CD=9 to 99 across RUN_NO iterations means "
            "reprocessing successfully recovered the file."
        ),
        "metadata": {"category": "file_status", "concept": "FILE_STATUS_CD_99"},
    },

    # ── CATEGORY 3: Health Flags ──────────────────────────────────────────────
    {
        "id": "health_01",
        "text": (
            "Health flag Green means the pipeline stage completed within its expected SLA duration. "
            "Green across all 7 stages means the file is processing normally."
        ),
        "metadata": {"category": "health_flags", "concept": "GREEN_FLAG"},
    },
    {
        "id": "health_02",
        "text": (
            "Health flag Yellow means the pipeline stage is degraded — it is approaching "
            "its SLA limit but has not breached it yet. Yellow flags are early warnings; "
            "a cluster of Yellow flags in the same stage across many ROs signals an "
            "emerging systemic bottleneck."
        ),
        "metadata": {"category": "health_flags", "concept": "YELLOW_FLAG"},
    },
    {
        "id": "health_03",
        "text": (
            "Health flag Red means the pipeline stage has breached its SLA threshold. "
            "Red flags require immediate investigation. Composite health score for an RO "
            "is calculated as: count of Red flags across all 7 stage-health columns (range 0-7). "
            "A score of 7 means every stage is in SLA breach."
        ),
        "metadata": {"category": "health_flags", "concept": "RED_FLAG"},
    },
    {
        "id": "health_04",
        "text": (
            "SPS_LOAD_HEALTH is the most important single health flag. "
            "It acts as a proxy for overall file success when record-level counts are not available. "
            "Red SPS_LOAD_HEALTH means the file failed to load records into SPS. "
            "Green SPS_LOAD_HEALTH means the bulk of records loaded successfully."
        ),
        "metadata": {"category": "health_flags", "concept": "SPS_LOAD_HEALTH"},
    },

    # ── CATEGORY 4: Operational States ───────────────────────────────────────
    {
        "id": "opstate_01",
        "text": (
            "IS_STUCK = 1 means the RO has stalled at a pipeline stage without making "
            "forward progress. Stuck ROs can potentially recover — operator intervention "
            "or a reprocess trigger (RUN_NO++) can restart them. "
            "Stuck ROs should be ranked by composite escalation score: "
            "(Red flags × 3) + (Yellow flags × 1) + (days stuck × 2)."
        ),
        "metadata": {"category": "operational_state", "concept": "IS_STUCK"},
    },
    {
        "id": "opstate_02",
        "text": (
            "IS_FAILED = 1 means the RO has reached a terminal failure state. "
            "Unlike IS_STUCK, failed ROs cannot recover on their own — they require "
            "resubmission of the source file after fixing the root cause. "
            "FAILURE_STATUS contains the free-text reason for the failure."
        ),
        "metadata": {"category": "operational_state", "concept": "IS_FAILED"},
    },
    {
        "id": "opstate_03",
        "text": (
            "IS_STUCK vs IS_FAILED: these are distinct operational states requiring different actions. "
            "IS_STUCK: pipeline stalled, recovery possible via operator trigger or auto-retry. "
            "IS_FAILED: terminal, requires source file resubmission after root cause fix. "
            "An RO should never have both IS_STUCK=1 and IS_FAILED=1 simultaneously."
        ),
        "metadata": {"category": "operational_state", "concept": "IS_STUCK_VS_IS_FAILED"},
    },
    {
        "id": "opstate_04",
        "text": (
            "FAILURE_STATUS is a free-text field containing the reason for pipeline failure. "
            "Common values: 'Complete Validation Failure' (source data non-conformant), "
            "'Schema mismatch' (source format changed), 'Encoding issue' (character set problem), "
            "'Incompatible' (version incompatibility between source system and pipeline). "
            "Each failure type requires a different remediation strategy."
        ),
        "metadata": {"category": "operational_state", "concept": "FAILURE_STATUS"},
    },
    {
        "id": "opstate_05",
        "text": (
            "'Complete Validation Failure' in FAILURE_STATUS is the most common terminal failure. "
            "It means the DART UI validation suite rejected the file entirely. "
            "This is almost always caused by source data that is non-conformant with CMS or "
            "state Medicaid provider data standards — not a pipeline bug. "
            "Most commonly sourced from AvailityPDM when NPI or taxonomy codes are invalid."
        ),
        "metadata": {"category": "operational_state", "concept": "COMPLETE_VALIDATION_FAILURE"},
    },

    # ── CATEGORY 5: Derived Metric Formulas ──────────────────────────────────
    {
        "id": "metric_01",
        "text": (
            "Composite Health Score = count of Red health flags across all 7 stage-health columns. "
            "Range: 0 (all Green, healthy) to 7 (all Red, critical). "
            "Thresholds: 0-1 = healthy, 2-3 = watch, 4-5 = warning, 6-7 = critical escalation. "
            "Calculated as SQL: SUM(CASE WHEN col='Red' THEN 1 ELSE 0 END) for all _HEALTH cols."
        ),
        "metadata": {"category": "derived_metric", "concept": "COMPOSITE_HEALTH_SCORE"},
    },
    {
        "id": "metric_02",
        "text": (
            "Duration Deviation Ratio = actual_stage_duration / AVG_stage_DURATION. "
            "Ratio > 2.0 = anomaly, investigate. "
            "Ratio > 3.0 = critical bottleneck, immediate escalation required. "
            "The AVG_* columns in the dataset contain historical averages for each stage, "
            "enabling per-RO deviation computation without external benchmarks."
        ),
        "metadata": {"category": "derived_metric", "concept": "DURATION_DEVIATION_RATIO"},
    },
    {
        "id": "metric_03",
        "text": (
            "Pipeline Completion Rate = count(FILE_STATUS_CD=99) / count(*) per state or org. "
            "This is the primary file-level success metric derived from existing columns. "
            "A declining completion rate in a state correlates with rising SCS_PERCENT drops in CSV2."
        ),
        "metadata": {"category": "derived_metric", "concept": "PIPELINE_COMPLETION_RATE"},
    },
    {
        "id": "metric_04",
        "text": (
            "Retry Overhead = RUN_NO - 1. For RUN_NO=1 there is no retry. "
            "For RUN_NO=3 there have been 2 reprocessing attempts. "
            "High retry overhead with no improvement in FILE_STATUS_CD (still 9 or 49) "
            "means reprocessing is consuming resources without recovering the file. "
            "Cross-reference with CSV2 NEXT_ITER_FAIL_CNT to confirm market-level retry futility."
        ),
        "metadata": {"category": "derived_metric", "concept": "RETRY_OVERHEAD"},
    },
    {
        "id": "metric_05",
        "text": (
            "Stuck Duration = DATEDIFF('minute', LATEST_OBJECT_RUN_DT, NOW()) where IS_STUCK=1. "
            "This measures how long an RO has been stuck. "
            "Used in triage escalation score alongside Red flag count and Yellow flag count."
        ),
        "metadata": {"category": "derived_metric", "concept": "STUCK_DURATION"},
    },

    # ── CATEGORY 6: Business Context ─────────────────────────────────────────
    {
        "id": "lob_01",
        "text": (
            "LOB = Line of Business. Values and meanings: "
            "Medicare HMO = Medicare Advantage managed care; "
            "Medicare FFS = traditional fee-for-service Medicare; "
            "Medicare PPO = Medicare preferred provider organization; "
            "Medicaid HMO = state Medicaid managed care; "
            "Medicaid FFS = traditional state Medicaid fee-for-service; "
            "Commercial HMO = employer-sponsored managed care; "
            "Commercial PPO = employer-sponsored preferred provider; "
            "Commercial EPO = exclusive provider organization; "
            "DSNP = Dual Special Needs Plan (Medicare+Medicaid)."
        ),
        "metadata": {"category": "business_context", "concept": "LOB_DECODER"},
    },
    {
        "id": "lob_02",
        "text": (
            "Medicaid FFS rosters are most frequently affected by CMS rule changes. "
            "When a market's SCS_PERCENT drops sharply and the LOB is Medicaid FFS, "
            "check for recent CMS or state Medicaid agency rule updates affecting "
            "NPI validation, taxonomy code requirements, or address standards. "
            "This is the highest-risk LOB for regulatory-triggered failures."
        ),
        "metadata": {"category": "business_context", "concept": "MEDICAID_FFS_RISK"},
    },
    {
        "id": "srcsys_01",
        "text": (
            "SRC_SYS = Source System. Values: "
            "AvailityPDM = PDM-integrated payer, submits through Availity Provider Data Management; "
            "Demographic = direct demographic data submission; "
            "ProviderGroup = group-level provider submissions; "
            "DPE = Data Processing Entity, third-party data processor."
        ),
        "metadata": {"category": "business_context", "concept": "SRC_SYS_DECODER"},
    },
    {
        "id": "srcsys_02",
        "text": (
            "AvailityPDM is the source system most associated with Complete Validation Failure. "
            "PDM-sourced records are most sensitive to CMS NPI database updates, because "
            "AvailityPDM validates provider NPIs against the CMS NPI registry at submission time. "
            "When CMS updates its quarterly NPI data, PDM-sourced rosters may suddenly fail "
            "validation that previously passed."
        ),
        "metadata": {"category": "business_context", "concept": "AVAILITYPDM_RISK"},
    },
    {
        "id": "retry_01",
        "text": (
            "RUN_NO links CSV1 pipeline retries to CSV2 market-level retry metrics. "
            "CSV1 RUN_NO > 1 = a specific RO has been reprocessed. "
            "CSV2 NEXT_ITER_SCS_CNT = market-level transactions that succeeded on retry. "
            "CSV2 NEXT_ITER_FAIL_CNT = transactions that still failed even after retry. "
            "High NEXT_ITER_FAIL_CNT in CSV2 alongside many RUN_NO > 1 in CSV1 for the same "
            "state means reprocessing is market-wide and not recovering most files."
        ),
        "metadata": {"category": "business_context", "concept": "RUN_NO_NEXT_ITER_LINK"},
    },

    # ── CATEGORY 7: KPI Thresholds ────────────────────────────────────────────
    {
        "id": "kpi_01",
        "text": (
            "SCS_PERCENT threshold = 95%. Markets with SCS_PERCENT below 95% require "
            "immediate investigation. This is the official threshold per the problem statement "
            "visualization specification. Markets below 85% are in critical failure territory. "
            "Trending markets (SCS_PERCENT declining over 3+ consecutive months) should be "
            "flagged even before they cross the 95% threshold."
        ),
        "metadata": {"category": "kpi_threshold", "concept": "SCS_PERCENT_THRESHOLD"},
    },
    {
        "id": "kpi_02",
        "text": (
            "FIRST_ITER_SCS_CNT vs NEXT_ITER_SCS_CNT in CSV2 shows retry recovery. "
            "Retry lift rate = NEXT_ITER_SCS_CNT / (NEXT_ITER_SCS_CNT + NEXT_ITER_FAIL_CNT). "
            "A high retry lift (>50%) means retries are effective. "
            "A low retry lift (<20%) means the underlying data problem is not fixable by reprocessing — "
            "source file correction or regulatory compliance update is needed."
        ),
        "metadata": {"category": "kpi_threshold", "concept": "RETRY_LIFT_RATE"},
    },
    {
        "id": "kpi_03",
        "text": (
            "Pipeline completion rate threshold: below 80% for a state indicates systemic failure. "
            "Between 80-95% is degraded — watchlist. "
            "Above 95% is healthy. "
            "Sudden drops in completion rate for a state correlate strongly with "
            "SCS_PERCENT drops in CSV2 for the same market."
        ),
        "metadata": {"category": "kpi_threshold", "concept": "COMPLETION_RATE_THRESHOLD"},
    },

    # ── CATEGORY 8: Compliance & External Context ───────────────────────────
    {
        "id": "compliance_01",
        "text": (
            "NCPDP and X12 834 EDI are the data standards governing provider roster submissions. "
            "The X12 834 EDI transaction set is used for healthcare enrollment and maintenance; "
            "about 40% of provider roster records have source-level data errors (industry statistic). "
            "When an entire org's files fail validation, suspect non-compliance with these standards "
            "rather than a pipeline infrastructure issue."
        ),
        "metadata": {"category": "compliance", "concept": "NCPDP_X12_834"},
    },
    {
        "id": "compliance_02",
        "text": (
            "CMS (Centers for Medicare and Medicaid Services) issues quarterly updates to the "
            "National Provider Identifier (NPI) registry. After a CMS NPI update, providers that "
            "have changed taxonomy codes, deactivated, or updated addresses may suddenly fail "
            "DART_UI_VALIDATION. This is the most common external trigger for sudden SCS_PERCENT drops."
        ),
        "metadata": {"category": "compliance", "concept": "CMS_NPI_UPDATES"},
    },
    {
        "id": "compliance_03",
        "text": (
            "State Medicaid agencies issue their own provider data submission rules independently of CMS. "
            "A rule change in a single state (e.g., KS requiring new taxonomy code format) "
            "will cause SCS_PERCENT to drop only in that market — not nationally. "
            "If one market drops while others hold steady, suspect a state-specific rule change."
        ),
        "metadata": {"category": "compliance", "concept": "STATE_MEDICAID_RULES"},
    },

    # ── CATEGORY 9: Cross-CSV Reasoning ──────────────────────────────────────
    {
        "id": "cross_csv_01",
        "text": (
            "Cross-CSV analysis: join CSV1 (CNT_STATE) with CSV2 (MARKET) to connect "
            "file-level pipeline problems to market-level business outcomes. "
            "High Red flag density in CSV1 for a state should correlate with low SCS_PERCENT "
            "in CSV2 for the same state. If CSV2 SCS_PERCENT drops but CSV1 flags are normal, "
            "the issue is probably in CSV2 transaction processing, not the pipeline files."
        ),
        "metadata": {"category": "cross_csv", "concept": "CSV1_CSV2_JOIN"},
    },
    {
        "id": "cross_csv_02",
        "text": (
            "Leading vs lagging indicators: CSV1 pipeline health flags are LEADING indicators — "
            "they show problems before they appear in CSV2 SCS_PERCENT (which aggregates monthly). "
            "If a state has rising Red flags in CSV1 this week but SCS_PERCENT in CSV2 still looks "
            "fine, the market degradation has not yet been captured in the monthly aggregate. "
            "Use CSV1 as the early warning system."
        ),
        "metadata": {"category": "cross_csv", "concept": "LEADING_LAGGING_INDICATORS"},
    },

    # ── CATEGORY 10: Explainability Templates ────────────────────────────────
    {
        "id": "explain_01",
        "text": (
            "When flagging an RO for duration anomaly, explain: "
            "'RO [ID] has a [STAGE]_DURATION that is [X]x its historical average "
            "(actual: [A] min, historical avg: [B] min). "
            "This typically indicates a data volume spike or a downstream validation bottleneck. "
            "Ratio > 3x requires immediate escalation.'"
        ),
        "metadata": {"category": "explainability", "concept": "DURATION_ANOMALY_EXPLANATION"},
    },
    {
        "id": "explain_02",
        "text": (
            "When flagging a market for low SCS_PERCENT, explain: "
            "'[MARKET] SCS_PERCENT is [X]%, below the 95% threshold. "
            "CSV1 shows [N] stuck ROs and [M] Red health flags in this state. "
            "The dominant LOB is [LOB] and primary source system is [SRC_SYS]. "
            "Consider checking for recent CMS or state Medicaid rule changes affecting this LOB.'"
        ),
        "metadata": {"category": "explainability", "concept": "MARKET_FAILURE_EXPLANATION"},
    },
    {
        "id": "explain_03",
        "text": (
            "When reporting IS_STUCK RO triage, explain: "
            "'[N] ROs are currently stuck. Top priority: RO [ID] in [ORG], [STATE], "
            "stuck in [STAGE] for [DURATION]. Composite score: [SCORE] "
            "([R] Red flags, [Y] Yellow flags). Recommended action: [ACTION].'"
        ),
        "metadata": {"category": "explainability", "concept": "TRIAGE_EXPLANATION"},
    },
]


# ── SemanticMemory Class ──────────────────────────────────────────────────────

class SemanticMemory:
    """
    Persistent ChromaDB-backed domain knowledge base.
    Seeds healthcare roster pipeline knowledge on first run.
    Provides top-k semantic retrieval for agent context injection.
    """

    def __init__(self, path: str = CHROMADB_PATH, collection: str = COLLECTION_NAME):
        self._client = chromadb.PersistentClient(
            path=path,
            settings=Settings(anonymized_telemetry=False),
        )
        self._collection = self._client.get_or_create_collection(
            name=collection,
            embedding_function=_EMBED_FN,
            metadata={"hnsw:space": "cosine"},
        )
        self._seed_if_empty()

    # ── Seeding ───────────────────────────────────────────────────────────────

    def _seed_if_empty(self) -> None:
        """Seeds all knowledge items on first run. Idempotent — checks by ID."""
        existing_ids = set(self._collection.get(include=[])["ids"])
        new_items = [ki for ki in KNOWLEDGE_ITEMS if ki["id"] not in existing_ids]
        if not new_items:
            return

        self._collection.add(
            ids=[ki["id"] for ki in new_items],
            documents=[ki["text"] for ki in new_items],
            metadatas=[ki["metadata"] for ki in new_items],
        )
        print(f"[SemanticMemory] Seeded {len(new_items)} knowledge items.")

    # ── Retrieval ─────────────────────────────────────────────────────────────

    def fetch(self, query: str, top_k: int = 3) -> List[str]:
        """
        Returns the top-k most semantically similar knowledge items as strings.
        These are injected into the agent's system prompt on every turn.

        Args:
            query: User query or agent reasoning step to match against.
            top_k: Number of items to return (default 3 per problem statement).

        Returns:
            List of knowledge text strings, most relevant first.
        """
        if self._collection.count() == 0:
            return []

        results = self._collection.query(
            query_texts=[query],
            n_results=min(top_k, self._collection.count()),
            include=["documents", "metadatas", "distances"],
        )
        docs = results["documents"][0]
        return docs

    def fetch_with_metadata(self, query: str, top_k: int = 3) -> List[Dict[str, Any]]:
        """
        Same as fetch() but returns dicts with text + metadata.
        Useful for logging which concepts were retrieved.
        """
        if self._collection.count() == 0:
            return []

        results = self._collection.query(
            query_texts=[query],
            n_results=min(top_k, self._collection.count()),
            include=["documents", "metadatas", "distances"],
        )
        return [
            {
                "text": doc,
                "concept": meta.get("concept", ""),
                "category": meta.get("category", ""),
                "relevance_score": round(1 - dist, 4),
            }
            for doc, meta, dist in zip(
                results["documents"][0],
                results["metadatas"][0],
                results["distances"][0],
            )
        ]

    def fetch_by_category(self, category: str) -> List[str]:
        """Returns all knowledge items in a specific category."""
        results = self._collection.get(
            where={"category": category},
            include=["documents"],
        )
        return results["documents"]

    # ── KB Enrichment (called by web search tool) ────────────────────────────

    def add_knowledge(
        self,
        item_id: str,
        text: str,
        category: str = "web_search",
        concept: str = "",
        overwrite: bool = False,
    ) -> bool:
        """
        Adds a new knowledge item to the KB (used by web_search enrichment).
        Returns True if added, False if already exists and overwrite=False.
        """
        existing = self._collection.get(ids=[item_id], include=[])
        if existing["ids"] and not overwrite:
            return False

        if existing["ids"] and overwrite:
            self._collection.delete(ids=[item_id])

        self._collection.add(
            ids=[item_id],
            documents=[text],
            metadatas=[{"category": category, "concept": concept, "source": "web_search"}],
        )
        return True

    # ── Stats ─────────────────────────────────────────────────────────────────

    def count(self) -> int:
        """Returns total number of knowledge items in the collection."""
        return self._collection.count()

    def list_concepts(self) -> List[str]:
        """Returns all unique concept names stored in the KB."""
        results = self._collection.get(include=["metadatas"])
        return list({m.get("concept", "") for m in results["metadatas"] if m.get("concept")})


# ── Convenience singleton ─────────────────────────────────────────────────────
# Import and use `semantic_memory` directly in agent nodes:
#   from src.memory.semantic import semantic_memory
#   context = semantic_memory.fetch(user_query)
semantic_memory = SemanticMemory()


# ── Manual test ───────────────────────────────────────────────────────────────
if __name__ == "__main__":
    sm = SemanticMemory()
    print(f"\nTotal knowledge items: {sm.count()}")
    print(f"\nConcepts stored: {sm.list_concepts()}")

    test_queries = [
        "what does IS_STUCK mean",
        "why did DART generation fail",
        "how is SCS_PERCENT threshold defined",
        "what is Complete Validation Failure",
        "why is KS market SCS_PERCENT dropping",
    ]
    for q in test_queries:
        print(f"\n{'='*60}")
        print(f"Query: {q}")
        results = sm.fetch_with_metadata(q, top_k=2)
        for r in results:
            print(f"  [{r['category']}:{r['concept']}] (score={r['relevance_score']})")
            print(f"  {r['text'][:120]}...")
