import sqlite3
import json
import chromadb
from chromadb.config import Settings
from datetime import datetime
from src.memory.semantic import _EMBED_FN

# ==========================================
# EPISODIC MEMORY DATABASE (SQLite)
# ==========================================
# This database handles both Interaction History (Text) 
# and Data State Snapshots (KPIs over time).
DB_NAME = "roster_iq_memory.db"
# Initialize ChromaDB for Semantic Search (Requirement A4)
chroma_client = chromadb.PersistentClient(path="memory/chromadb")
try:
    episodic_collection = chroma_client.get_or_create_collection(name="episodic_memory", embedding_function=_EMBED_FN)
except ValueError:
    # Embedding function conflict: old collection used a different embedder. Delete and recreate.
    print("[EpisodicMemory] Embedding conflict detected. Recreating 'episodic_memory' collection...")
    chroma_client.delete_collection("episodic_memory")
    episodic_collection = chroma_client.create_collection(name="episodic_memory", embedding_function=_EMBED_FN)

def init_db():
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    
    # Keep your existing interactions table
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS interactions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            session_id TEXT,
            timestamp DATETIME,
            user_query TEXT,
            agent_response TEXT
        )
    ''')

    # UPDATED for Task A4: Added episodic_events with required columns
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS episodic_events (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            session_id TEXT,
            query_intent TEXT,
            key_findings TEXT,
            kpi_snapshot TEXT, 
            severity TEXT,
            resolved INTEGER DEFAULT 0,
            timestamp DATETIME
        )
    ''')
    
    # Keep your existing snapshots table
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

def log_episodic_event(session_id: str, intent: str, findings: str, kpis: dict, severity: str = "Low"):
    """
    Task A4: Logs a high-level investigation event to both SQLite and ChromaDB.
    This allows for both structured tracking and semantic retrieval.
    """
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    timestamp = datetime.now().isoformat()
    kpi_json = json.dumps(kpis)

    # 1. Log to SQLite (Structured Store)
    cursor.execute('''
        INSERT INTO episodic_events (session_id, query_intent, key_findings, kpi_snapshot, severity, timestamp)
        VALUES (?, ?, ?, ?, ?, ?)
    ''', (session_id, intent, findings, kpi_json, severity, timestamp))
    
    row_id = cursor.lastrowid
    conn.commit()
    conn.close()

    # 2. Log to ChromaDB (Semantic Store for 'What did we investigate before?')
    episodic_collection.add(
        documents=[f"Investigation into {intent}. Findings: {findings}"],
        metadatas=[{"session_id": session_id, "severity": severity, "sqlite_id": row_id}],
        ids=[f"event_{row_id}"]
    )
    return row_id

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

# -------------------------------------------------
# SEMANTIC HISTORY RETRIEVAL (Requirement A4)
# -------------------------------------------------

def retrieve_semantic_history(query: str, n_results: int = 3):
    """
    Performs a semantic search over past investigations using ChromaDB.
    Allows the agent to 'remember' context and past findings across sessions.
    """
    results = episodic_collection.query(
        query_texts=[query],
        n_results=n_results
    )
    return results['documents']

# --- INITIALIZE DATABASE ON IMPORT ---
init_db()