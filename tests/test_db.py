import duckdb
import os
import traceback

con = duckdb.connect(database=':memory:')

base_path = os.path.abspath(os.path.join(os.path.dirname('c:/Users/Atharv Priyadarshi/Documents/Healthcare-roster-agent/src/db/duckdb_engine.py'), "..", ".."))
roster_path = os.path.join(base_path, "data", "roster_processing_details.csv")
market_path = os.path.join(base_path, "data", "aggregated_operational_metrics.csv")

try:
    print("Loading CSVs...")
    con.execute(f"CREATE VIEW roster_ops AS SELECT * FROM read_csv_auto('{roster_path}')")
    con.execute(f"CREATE VIEW market_ops AS SELECT * FROM read_csv_auto('{market_path}')")
    con.execute("CREATE TABLE roster AS SELECT * FROM roster_ops")
    con.execute("CREATE TABLE market AS SELECT * FROM market_ops")
    print("CSVs loaded successfully.")
    
    schema_path = "c:/Users/Atharv Priyadarshi/Documents/Healthcare-roster-agent/src/db/schema.sql"
    with open(schema_path, 'r') as f:
        sql_script = f.read()
    
    print("Loading schema.sql...")
    con.execute(sql_script)
    print("Schema loaded successfully!")
    
except Exception as e:
    print(f"Error: {e}")
    traceback.print_exc()
