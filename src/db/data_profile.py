from src.db.duckdb_engine import MetricsEngine
import json

def generate_profile():
    engine = MetricsEngine()
    
    profile = {
        "roster_ops": {
            "total_rows": int(engine.query("SELECT COUNT(*) FROM roster_ops").iloc[0,0]),
            "null_counts": engine.query("SELECT * FROM roster_ops LIMIT 1").isnull().sum().to_dict(),
            "unique_states": engine.query("SELECT DISTINCT CNT_STATE FROM roster_ops").iloc[:,0].tolist(),
            "date_range": {
                "min": str(engine.query("SELECT MIN(FILE_RECEIVED_DT) FROM roster_ops").iloc[0,0]),
                "max": str(engine.query("SELECT MAX(FILE_RECEIVED_DT) FROM roster_ops").iloc[0,0])
            }
        },
        "market_ops": {
            "total_rows": int(engine.query("SELECT COUNT(*) FROM market_ops").iloc[0,0]),
            "unique_markets": engine.query("SELECT DISTINCT MARKET FROM market_ops").iloc[:,0].tolist(),
            "avg_scs_percent": float(engine.query("SELECT AVG(SCS_PERCENT) FROM market_ops").iloc[0,0])
        }
    }
    
    with open("data_profile_report.json", "w") as f:
        json.dump(profile, f, indent=4)
    print("✅ Data Profile Report generated: data_profile_report.json")

if __name__ == "__main__":
    generate_profile()