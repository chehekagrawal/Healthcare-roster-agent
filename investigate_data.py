import pandas as pd

print("\n==============================")
print("DATASET INVESTIGATION STARTED")
print("==============================\n")

# -------------------------------
# LOAD DATASETS
# -------------------------------

roster = pd.read_csv("data/roster_processing_details.csv")
market = pd.read_csv("data/aggregated_operational_metrics.csv")

print("ROSTER SHAPE:", roster.shape)
print("MARKET SHAPE:", market.shape)

# -------------------------------
# COLUMN INFORMATION
# -------------------------------

print("\n==============================")
print("ROSTER COLUMNS")
print("==============================")
print(roster.columns)

print("\n==============================")
print("MARKET COLUMNS")
print("==============================")
print(market.columns)

# -------------------------------
# SAMPLE ROWS
# -------------------------------

print("\n==============================")
print("ROSTER SAMPLE")
print("==============================")
print(roster.head())

print("\n==============================")
print("MARKET SAMPLE")
print("==============================")
print(market.head())

# -------------------------------
# MISSING VALUES
# -------------------------------

print("\n==============================")
print("MISSING VALUES (ROSTER)")
print("==============================")
print(roster.isnull().sum())

print("\n==============================")
print("MISSING VALUES (MARKET)")
print("==============================")
print(market.isnull().sum())

# -------------------------------
# STUCK ROSTER OPERATIONS
# -------------------------------

print("\n==============================")
print("STUCK ROs COUNT")
print("==============================")

if "IS_STUCK" in roster.columns:
    print(roster["IS_STUCK"].value_counts())

    stuck = roster[roster["IS_STUCK"] == 1]

    print("\nTOP STUCK ROs")
    cols = ["RO_ID", "ORG_NM", "CNT_STATE", "LATEST_STAGE_NM"]
    available_cols = [c for c in cols if c in roster.columns]
    print(stuck[available_cols].head(10))

else:
    print("Column IS_STUCK not found")

# -------------------------------
# FAILED ROSTER OPERATIONS
# -------------------------------

print("\n==============================")
print("FAILED ROs")
print("==============================")

if "IS_FAILED" in roster.columns:
    print(roster["IS_FAILED"].value_counts())

    failed = roster[roster["IS_FAILED"] == 1]

    if "FAILURE_STATUS" in roster.columns:
        print("\nTOP FAILURE REASONS")
        print(failed["FAILURE_STATUS"].value_counts().head(10))

else:
    print("Column IS_FAILED not found")

# -------------------------------
# PIPELINE STAGE DISTRIBUTION
# -------------------------------

print("\n==============================")
print("LATEST STAGE DISTRIBUTION")
print("==============================")

if "LATEST_STAGE_NM" in roster.columns:
    print(roster["LATEST_STAGE_NM"].value_counts())
else:
    print("LATEST_STAGE_NM column missing")

# -------------------------------
# SOURCE SYSTEM ANALYSIS
# -------------------------------

print("\n==============================")
print("SOURCE SYSTEM DISTRIBUTION")
print("==============================")

if "SRC_SYS" in roster.columns:
    print(roster["SRC_SYS"].value_counts())
else:
    print("SRC_SYS column missing")

# -------------------------------
# STATE DISTRIBUTION
# -------------------------------

print("\n==============================")
print("STATE DISTRIBUTION")
print("==============================")

if "CNT_STATE" in roster.columns:
    print(roster["CNT_STATE"].value_counts().head(20))
else:
    print("CNT_STATE column missing")

# -------------------------------
# HEALTH FLAG ANALYSIS
# -------------------------------

print("\n==============================")
print("HEALTH FLAG DISTRIBUTION")
print("==============================")

health_cols = [
    "PRE_PROCESSING_HEALTH",
    "DART_GEN_HEALTH",
    "SPS_LOAD_HEALTH"
]

for col in health_cols:
    if col in roster.columns:
        print("\n", col)
        print(roster[col].value_counts())

# -------------------------------
# DURATION ANOMALY CHECK
# -------------------------------

print("\n==============================")
print("DURATION ANOMALY CHECK")
print("==============================")

if "DART_GEN_DURATION" in roster.columns and "AVG_DART_GEN_DURATION" in roster.columns:
    anomaly = roster[
        roster["DART_GEN_DURATION"] >
        2 * roster["AVG_DART_GEN_DURATION"]
    ]

    print("DART GENERATION ANOMALIES:", len(anomaly))

# -------------------------------
# MARKET SUCCESS RATE ANALYSIS
# -------------------------------

print("\n==============================")
print("LOWEST SUCCESS MARKETS")
print("==============================")

if "SCS_PERCENT" in market.columns:
    print(
        market.sort_values("SCS_PERCENT")
        .head(10)[["MARKET", "SCS_PERCENT"]]
    )

# -------------------------------
# RETRY IMPROVEMENT ANALYSIS
# -------------------------------

print("\n==============================")
print("RETRY IMPROVEMENT ANALYSIS")
print("==============================")

if "NEXT_ITER_SCS_CNT" in market.columns:
    market["retry_improvement"] = market["NEXT_ITER_SCS_CNT"]

    print(
        market.sort_values("retry_improvement", ascending=False)
        .head(10)[["MARKET", "retry_improvement"]]
    )

# -------------------------------
# STATE FAILURE RATE
# -------------------------------

print("\n==============================")
print("STATE FAILURE RATE")
print("==============================")

if "CNT_STATE" in roster.columns and "IS_FAILED" in roster.columns:
    state_failure = roster.groupby("CNT_STATE")["IS_FAILED"].mean()

    print(
        state_failure
        .sort_values(ascending=False)
        .head(10)
    )

# -------------------------------
# SUMMARY
# -------------------------------

print("\n==============================")
print("DATA SUMMARY")
print("==============================")

total_ros = len(roster)
total_markets = len(market)

stuck_count = roster["IS_STUCK"].sum() if "IS_STUCK" in roster.columns else 0
failed_count = roster["IS_FAILED"].sum() if "IS_FAILED" in roster.columns else 0

summary = {
    "total_ros": total_ros,
    "total_markets": total_markets,
    "stuck_ros": stuck_count,
    "failed_ros": failed_count
}

print(summary)

print("\n==============================")
print("INVESTIGATION COMPLETE")
print("==============================")