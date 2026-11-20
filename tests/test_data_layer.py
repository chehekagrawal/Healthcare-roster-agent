"""DuckDB engine, SQL views, query tool, root-cause tracer and reports."""
import pandas as pd

from src.tools.data_query import DataQueryTool, triage_stuck_ros
from src.tools.root_cause import RootCauseTracer


def test_data_loads(engine):
    assert len(engine.query("SELECT * FROM roster")) == 59975
    assert len(engine.query("SELECT * FROM market")) == 357
    assert len(engine.known_states()) == 32


def test_months_are_parsed_and_sorted_chronologically(engine):
    assert engine.query("SELECT COUNT(*) n FROM market WHERE MONTH_DATE IS NULL")["n"][0] == 0
    trend = engine.get_market_trend_data("GA")
    dates = pd.to_datetime(trend["MONTH_DATE"])
    assert dates.is_monotonic_increasing
    # As text, "01-2026" sorted before "02-2025"; it must now come last.
    assert trend["MONTH"].iloc[0] == "02-2025"
    assert trend["MONTH"].iloc[-1] == "01-2026"


def test_kpi_snapshot_uses_latest_month(engine):
    snap = engine.get_market_kpi_snapshot()
    latest_ga = engine.query(
        "SELECT SCS_PERCENT FROM market WHERE MARKET='GA' ORDER BY MONTH_DATE DESC LIMIT 1")["SCS_PERCENT"][0]
    assert snap["GA"] == latest_ga == 96.97
    assert len(snap) == 32


def test_cross_state_view_has_one_row_per_state(engine):
    df = engine.query("SELECT * FROM cross_state_health_view")
    assert df["CNT_STATE"].is_unique
    ga = DataQueryTool(engine).cross_table_join("ga")
    assert len(ga) == 1
    assert ga["failed_ros"][0] == 202
    assert round(ga["avg_scs_percent"][0], 2) == 81.95
    assert ga["min_scs_percent"][0] == 0.68


def test_health_score_is_zero_to_one_higher_is_healthier(engine):
    df = engine.pipeline_health_score()
    assert df["composite_health_score"].between(0, 1).all()
    assert 0.8 < df["composite_health_score"].mean() < 0.9


def test_state_values_are_bound_not_formatted(engine):
    tool = DataQueryTool(engine)
    # An injection attempt is treated as a (non-existent) state code.
    assert len(tool.cross_table_join("GA' OR '1'='1")) == 0
    assert tool.query_duckdb("DROP TABLE roster").startswith("SQL Error")
    assert len(engine.query("SELECT * FROM roster LIMIT 1")) == 1


def test_derive_metrics_filters_by_state(engine):
    tool = DataQueryTool(engine)
    assert len(tool.derive_metrics("health", state="GA")) == 4069
    assert set(tool.derive_metrics("completion", state="ga")["CNT_STATE"]) == {"GA"}


def test_triage_score_formula(engine):
    df = triage_stuck_ros(engine, red_weight=5, yellow_weight=1, time_weight=2)
    assert len(df) == 2
    expected = df["red_flags"] * 5 + df["yellow_flags"] * 1 + df["days_stuck"] * 2
    assert (df["escalation_score"] == expected).all()
    assert df["escalation_score"].is_monotonic_decreasing
    # Days are measured to the dataset's as-of time, not today's date.
    assert df["days_stuck"].max() < 200


def test_root_cause_trace_ga(engine):
    r = RootCauseTracer(engine).trace_market_failure("ga")
    assert r["primary_culprit_system"] == "ProviderGroup"
    assert r["primary_failure_stage"] == "PRE_PROCESSING"
    assert r["top_failing_orgs"][0]["ORG_NM"] == "Choa Hospital Based"
    assert [m["MONTH"] for m in r["breach_months"]][:2] == ["08-2025", "10-2025"]
    assert "08-2025" in r["narrative"]


def test_root_cause_unknown_state(engine):
    r = RootCauseTracer(engine).trace_market_failure("ZZ")
    assert "error" in r and "narrative" in r


def test_reports(engine):
    from src.tools.report_gen import ReportGenerator
    gen = ReportGenerator(engine)
    md = gen.generate_pipeline_health_report()
    assert "latest month" in md and "12 months" in md
    pdf = gen.generate_pdf_report()
    assert isinstance(pdf, bytes) and pdf.startswith(b"%PDF")


def test_charts(engine):
    from src.tools.visualizer import Visualizer
    v = Visualizer(engine)
    trend = v.plot_market_trend("GA")
    xs = list(pd.to_datetime(list(trend.data[0].x)))
    assert xs == sorted(xs)
    for fig in (v.plot_pipeline_health_heatmap(), v.plot_duration_anomaly(),
                v.plot_retry_lift(), v.plot_stuck_ro_tracker()):
        assert fig is not None
