-- schema.sql: Core Analytical Views for RosterIQ
-- Views read from the `roster` and `market` tables created by MetricsEngine,
-- so the CSVs are parsed once at startup instead of on every query.

-- 0. Latest month per market
-- CSV 2 has one row per market per month (up to 12). Anything that needs
-- "the current SCS_PERCENT" must use the most recent month, not an arbitrary row.
CREATE OR REPLACE VIEW market_latest AS
SELECT MARKET, MONTH, MONTH_DATE, SCS_PERCENT
FROM market
QUALIFY ROW_NUMBER() OVER (PARTITION BY MARKET ORDER BY MONTH_DATE DESC) = 1;

-- 1. Composite Health Score View
-- Green = 1, Yellow = 0.5, Red = 0, averaged over the 7 stages.
-- Range 0.0 (all Red) to 1.0 (all Green). Higher is healthier.
CREATE OR REPLACE VIEW composite_health_view AS
SELECT
    RO_ID,
    ORG_NM,
    CNT_STATE,
    (
        (CASE PRE_PROCESSING_HEALTH WHEN 'Green' THEN 1 WHEN 'Yellow' THEN 0.5 ELSE 0 END) +
        (CASE MAPPING_APROVAL_HEALTH WHEN 'Green' THEN 1 WHEN 'Yellow' THEN 0.5 ELSE 0 END) +
        (CASE ISF_GEN_HEALTH WHEN 'Green' THEN 1 WHEN 'Yellow' THEN 0.5 ELSE 0 END) +
        (CASE DART_GEN_HEALTH WHEN 'Green' THEN 1 WHEN 'Yellow' THEN 0.5 ELSE 0 END) +
        (CASE DART_REVIEW_HEALTH WHEN 'Green' THEN 1 WHEN 'Yellow' THEN 0.5 ELSE 0 END) +
        (CASE DART_UI_VALIDATION_HEALTH WHEN 'Green' THEN 1 WHEN 'Yellow' THEN 0.5 ELSE 0 END) +
        (CASE SPS_LOAD_HEALTH WHEN 'Green' THEN 1 WHEN 'Yellow' THEN 0.5 ELSE 0 END)
    ) / 7.0 AS composite_health_score
FROM roster;

-- 2. Duration Deviation View (actual / historical average; >2 anomaly, >3 critical)
CREATE OR REPLACE VIEW duration_deviation_view AS
SELECT
    RO_ID,
    -- ISF generation is deliberately left out: AVG_ISF_GENERATION_DURATION is not
    -- on the same scale as ISF_GEN_DURATION in this extract (median 0.6 vs ~3.6),
    -- so its ratio would flag almost every file as a 5x+ anomaly.
    DART_GEN_DURATION / NULLIF(AVG_DART_GENERATION_DURATION, 0) AS dart_deviation,
    DART_UI_VALIDATION_DURATION / NULLIF(AVG_DART_UI_VLDTN_DURATION, 0) AS dart_ui_deviation,
    SPS_LOAD_DURATION / NULLIF(AVG_SPS_LOAD_DURATION, 0) AS sps_deviation
FROM roster;

-- 3. Cross-State Join View: one row per state.
-- File-level failure counts (CSV 1) next to the state's latest-month and
-- 12-month-average success rate (CSV 2).
CREATE OR REPLACE VIEW cross_state_health_view AS
WITH files AS (
    SELECT
        CNT_STATE,
        COUNT(*) AS total_ros,
        COUNT(*) FILTER (WHERE IS_FAILED = 1) AS failed_ros,
        COUNT(*) FILTER (WHERE IS_STUCK = 1) AS stuck_ros
    FROM roster
    GROUP BY CNT_STATE
),
yearly AS (
    SELECT MARKET, AVG(SCS_PERCENT) AS avg_scs_percent, MIN(SCS_PERCENT) AS min_scs_percent
    FROM market
    GROUP BY MARKET
)
SELECT
    f.CNT_STATE,
    f.total_ros,
    f.failed_ros,
    f.stuck_ros,
    l.SCS_PERCENT,
    l.MONTH AS latest_month,
    y.avg_scs_percent,
    y.min_scs_percent
FROM files f
JOIN market_latest l ON f.CNT_STATE = l.MARKET
JOIN yearly y ON f.CNT_STATE = y.MARKET;
