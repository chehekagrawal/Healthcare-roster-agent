-- schema.sql: Core Analytical Views for RosterIQ

-- 1. Composite Health Score View
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
FROM roster_ops;

-- 2. Duration Deviation View
CREATE OR REPLACE VIEW duration_deviation_view AS
SELECT 
    RO_ID,
    DART_GEN_DURATION / NULLIF(AVG_DART_GENERATION_DURATION, 0) AS dart_deviation,
    DART_UI_VALIDATION_DURATION / NULLIF(AVG_DART_UI_VLDTN_DURATION, 0) AS dart_ui_deviation,
    SPS_LOAD_DURATION / NULLIF(AVG_SPS_LOAD_DURATION, 0) AS sps_deviation
FROM roster_ops;

-- 3. Cross-State Join View
CREATE OR REPLACE VIEW cross_state_health_view AS
SELECT 
    r.CNT_STATE,
    COUNT(*) FILTER (WHERE r.IS_FAILED = 1) AS failed_ros,
    COUNT(*) FILTER (WHERE r.IS_STUCK = 1) AS stuck_ros,
    m.SCS_PERCENT
FROM roster_ops r
JOIN market_ops m ON r.CNT_STATE = m.MARKET
GROUP BY r.CNT_STATE, m.SCS_PERCENT;