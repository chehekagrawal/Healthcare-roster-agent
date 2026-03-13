import sqlite3
import json
from datetime import datetime

# ==========================================
# EPISODIC MEMORY DATABASE (SQLite)
# ==========================================
# This database handles both Interaction History (Text) 
# and Data State Snapshots (KPIs over time).
DB_NAME = "roster_iq_memory.db"

def init_db():
    """
    Creates the memory tables if they don't exist.
    We use two tables: one for chat, one for data state tracking.
    """
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    
    # TABLE 1: Interaction History (Episodic Chat)
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS interactions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            session_id TEXT,
            timestamp DATETIME,
            user_query TEXT,
            agent_response TEXT
        )
    ''')
    
    # TABLE 2: Data Snapshots (For Detecting State Changes since last session)
    # This stores JSON blobs of metrics like 'stuck_ro_ids' or 'market_success_rates'
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS data_snapshots (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            snapshot_type TEXT, 
            snapshot_data TEXT, 
            timestamp DATETIME
        )
    ''')
    
    conn.commit()
    conn.close()

# -------------------------------------------------
# CHAT INTERACTION LOGGING
# -------------------------------------------------

def log_interaction(session_id: str, user_query: str, agent_response: str):
    """
    Saves a conversation turn to the database.
    Essential for answering: "What did we investigate before?"
    """
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    timestamp = datetime.now().isoformat()
    cursor.execute('''
        INSERT INTO interactions (session_id, timestamp, user_query, agent_response)
        VALUES (?, ?, ?, ?)
    ''', (session_id, timestamp, user_query, agent_response))
    conn.commit()
    conn.close()

# -------------------------------------------------
# DATA SNAPSHOT LOGGING (State Change Detection)
# -------------------------------------------------

def save_data_snapshot(snapshot_type: str, data: list):
    """
    Stores the current state of a metric (e.g. list of Stuck RO IDs).
    Allows the agent to detect if an issue has been resolved since last time.
    """
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    timestamp = datetime.now().isoformat()
    cursor.execute('''
        INSERT INTO data_snapshots (snapshot_type, snapshot_data, timestamp)
        VALUES (?, ?, ?)
    ''', (snapshot_type, json.dumps(data), timestamp))
    conn.commit()
    conn.close()

def get_last_snapshot(snapshot_type: str):
    """
    Retrieves the most recent previous snapshot for comparison.
    Used for: "What changed since my last session?"
    """
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    # We look for the previous state (LIMIT 1 OFFSET 1 because current state was just saved)
    cursor.execute('''
        SELECT snapshot_data FROM data_snapshots 
        WHERE snapshot_type = ? 
        ORDER BY timestamp DESC LIMIT 1 OFFSET 1
    ''', (snapshot_type,))
    row = cursor.fetchone()
    conn.close()
    
    return json.loads(row[0]) if row else None

# -------------------------------------------------
# HISTORY RETRIEVAL
# -------------------------------------------------

def get_history(session_id: str, limit: int = 5) -> str:
    """
    Retrieves the last N interactions for context.
    Strictly aligned with the requirement to 'remember past queries'.
    """
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    cursor.execute('''
        SELECT timestamp, user_query, agent_response 
        FROM interactions 
        WHERE session_id = ? 
        ORDER BY timestamp DESC LIMIT ?
    ''', (session_id, limit))
    rows = cursor.fetchall()
    conn.close()
    
    if not rows:
        return "No previous memory found for this session."
    
    # Reverse so chronological order is maintained for the LLM
    rows.reverse() 
    
    history_text = "--- PREVIOUS EPISODIC MEMORY ---\n"
    for row in rows:
        # row[0] is timestamp, row[1] is query, row[2] is response
        history_text += f"Time: {row[0]}\nUser: {row[1]}\nAgent: {row[2]}\n\n"
    return history_text

# --- INITIALIZE DATABASE ON IMPORT ---
init_db()