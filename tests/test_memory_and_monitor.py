"""Semantic, procedural and episodic memory, change detection, monitor, web-search enrichment."""
import json
import shutil
import sqlite3

import pytest

from src.paths import MEMORY_DB


# ── Semantic memory ────────────────────────────────────────────────────────

def test_knowledge_base_size_and_retrieval():
    from src.memory.semantic import semantic_memory, KNOWLEDGE_ITEMS
    assert len(KNOWLEDGE_ITEMS) == 42
    assert semantic_memory.count() >= 42
    hits = semantic_memory.fetch("what does IS_STUCK mean", top_k=3)
    assert len(hits) == 3 and any("IS_STUCK" in h for h in hits)


def test_health_score_fact_matches_the_sql():
    from src.memory.semantic import KNOWLEDGE_ITEMS
    text = next(k["text"] for k in KNOWLEDGE_ITEMS if k["id"] == "metric_01")
    assert "1.0 (all Green" in text and "count of Red" not in text


def test_stale_fact_is_refreshed_on_startup():
    from src.memory.semantic import SemanticMemory, semantic_memory
    semantic_memory._collection.upsert(ids=["metric_01"], documents=["OUTDATED"],
                                       metadatas=[{"category": "derived_metric"}])
    fresh = SemanticMemory()
    doc = fresh._collection.get(ids=["metric_01"], include=["documents"])["documents"][0]
    assert doc != "OUTDATED"


# ── Web search -> semantic memory enrichment ───────────────────────────────

def test_web_results_are_saved_to_semantic_memory():
    from src.tools.web_search import WebSearchTool
    from src.memory.semantic import semantic_memory
    tool = WebSearchTool()
    results = {"context_type": "cms_rule_changes", "query_used": "CMS rules Georgia test",
               "results": [{"title": "Rule A", "content": "Directory accuracy rule"}]}
    before = semantic_memory.count()
    assert tool.enrich_semantic_kb(results) is True
    assert tool.enrich_semantic_kb(results) is True       # same query: overwritten,
    assert semantic_memory.count() == before + 1          # not duplicated
    assert tool.enrich_semantic_kb({"context_type": "general", "results": []}) is False


@pytest.mark.parametrize("q,expected", [
    ("any new CMS rule for Florida?", "cms_rule_changes"),
    ("EDI 834 complete validation failure", "complete_validation_failure"),
    ("medicare compliance standards", "lob_compliance"),
    ("who is Choa Hospital", "provider_lookup"),
    ("what is DART", "general"),
])
def test_search_template_choice(q, expected):
    from src.tools.web_search import WebSearchTool
    assert WebSearchTool.pick_context_type(q) == expected


def test_search_without_key_returns_error_not_exception():
    from src.tools.web_search import WebSearchTool
    assert "error" in WebSearchTool().search("anything")


# ── Procedural memory ──────────────────────────────────────────────────────

@pytest.fixture()
def procedures(tmp_path):
    from src.memory.procedural import ProceduralMemory, PROCEDURES_FILE
    path = tmp_path / "procedures.json"
    shutil.copy(PROCEDURES_FILE, path)
    return ProceduralMemory(json_path=str(path))


@pytest.mark.parametrize("name", ["triage_stuck_ros", "market_health_report",
                                  "retry_effectiveness_analysis", "pipeline_bottleneck_scan"])
def test_every_procedure_returns_real_data(procedures, engine, name):
    result = procedures.run_procedure(name, engine)
    assert result["status"] == "success"
    assert len(result["data"]) > 0
    assert result["summary"]


def test_procedure_params_change_results_and_versions_persist(procedures, engine, tmp_path):
    base = procedures.run_procedure("triage_stuck_ros", engine)["data"]
    updated = procedures.update_procedure_params("triage_stuck_ros", {"time_weight": 0}, user_id="test")
    assert updated["version"] == 3
    reloaded = json.loads((tmp_path / "procedures.json").read_text())
    assert reloaded["triage_stuck_ros"]["version"] == 3
    assert reloaded["triage_stuck_ros"]["params"]["time_weight"] == 0
    new = procedures.run_procedure("triage_stuck_ros", engine)["data"]
    assert [r["escalation_score"] for r in new] != [r["escalation_score"] for r in base]


def test_market_health_report_state_filter(procedures, engine):
    rows = procedures.run_procedure("market_health_report", engine, {"state_filter": "GA"})["data"]
    assert len(rows) == 1 and rows[0]["state"] == "GA"
    assert rows[0]["below_threshold_avg"] and not rows[0]["below_threshold_latest"]


def test_procedure_lookup_by_meaning(procedures):
    assert procedures.find_relevant_procedures("scan for slow stages")[0]["name"] == "pipeline_bottleneck_scan"


# ── Episodic memory + change detection ─────────────────────────────────────

def test_snapshot_saved_once_per_session(engine):
    from src.memory.episodic import save_session_snapshot_once
    assert save_session_snapshot_once("stuck_ro_ids", engine.get_stuck_ro_ids(), "SES-once") is True
    assert save_session_snapshot_once("stuck_ro_ids", engine.get_stuck_ro_ids(), "SES-once") is False


def test_change_detection_compares_with_previous_session(fresh_engine):
    from src.memory.change_detector import ChangeDetector
    from src.memory.episodic import save_session_snapshot_once
    detector = ChangeDetector(fresh_engine)

    prev_kpis = fresh_engine.get_market_kpi_snapshot()
    prev_kpis["GA"] = 99.0
    save_session_snapshot_once("stuck_ro_ids", ["RO-OLD", "RO-2380443"], "SES-A")
    save_session_snapshot_once("market_kpi_snapshot", prev_kpis, "SES-A")

    changes = detector.detect_all_changes("SES-B")
    assert changes["baseline"] is False
    assert changes["resolutions"] == ["RO-OLD"]
    assert changes["new_anomalies"] == ["RO-2340485"]
    assert changes["kpi_drift"] == {"GA": {"old": 99.0, "new": 96.97}}
    assert "RO-OLD" in detector.format_report("SES-B")


def test_episodic_semantic_recall():
    from src.memory.episodic import log_episodic_event, retrieve_semantic_history
    log_episodic_event("SES-recall", "why is NM below SLA", "NM fails at pre-processing", {})
    docs = retrieve_semantic_history("NM below SLA", n_results=1)[0]
    assert docs and "NM" in docs[0]


# ── Proactive monitor ──────────────────────────────────────────────────────

def _alert_counts():
    conn = sqlite3.connect(MEMORY_DB)
    rows = conn.execute("SELECT type, resolved, COUNT(*) FROM active_alerts GROUP BY 1, 2").fetchall()
    conn.close()
    return {(t, r): n for t, r, n in rows}


def test_monitor_reconciles_alerts(fresh_engine):
    from src.agent.monitor import ProactiveMonitor, get_active_alerts
    conn = sqlite3.connect(MEMORY_DB)
    conn.execute("DROP TABLE IF EXISTS active_alerts")
    conn.commit()
    conn.close()

    monitor = ProactiveMonitor(fresh_engine)
    monitor.run_immediate_scan()
    monitor.run_immediate_scan()                      # no duplicates
    counts = _alert_counts()
    assert counts[("PIPELINE_STALL", 0)] == 1
    assert counts[("MARKET_SLIPPAGE", 0)] == 8        # latest month only (was 129)
    assert get_active_alerts(1)[0]["severity"] == "High"

    fresh_engine.con.execute("UPDATE roster SET IS_STUCK = 0 WHERE RO_ID = 'RO-2340485'")
    monitor.run_immediate_scan()                      # changed: old resolved, new raised
    counts = _alert_counts()
    assert counts[("PIPELINE_STALL", 0)] == 1 and counts[("PIPELINE_STALL", 1)] == 1
    assert "1 Roster Operation" in get_active_alerts(1)[0]["message"]

    fresh_engine.con.execute("UPDATE roster SET IS_STUCK = 0")
    monitor.run_immediate_scan()                      # cleared: resolved
    assert ("PIPELINE_STALL", 0) not in _alert_counts()


def test_monitor_start_is_idempotent(engine):
    from src.agent.monitor import ProactiveMonitor
    monitor = ProactiveMonitor(engine)
    monitor.start()
    monitor.start()
    assert [j.id for j in monitor.scheduler.get_jobs()] == ["proactive_scan"]
    monitor.shutdown()
