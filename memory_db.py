import sqlite3
import datetime

# ==========================================
# EPISODIC MEMORY DATABASE (SQLite)
# ==========================================
DB_NAME = "roster_iq_memory.db"

def init_db():
    """Creates the memory table if it doesn't exist."""
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS interactions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            session_id TEXT,
            timestamp DATETIME,
            user_query TEXT,
            agent_response TEXT
        )
    ''')
    conn.commit()
    conn.close()

def log_interaction(session_id: str, user_query: str, agent_response: str):
    """Saves a conversation turn to the database."""
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    timestamp = datetime.datetime.now().isoformat()
    cursor.execute('''
        INSERT INTO interactions (session_id, timestamp, user_query, agent_response)
        VALUES (?, ?, ?, ?)
    ''', (session_id, timestamp, user_query, agent_response))
    conn.commit()
    conn.close()

def get_history(session_id: str, limit: int = 5) -> str:
    """Retrieves the last N interactions for a specific session to feed the LLM context."""
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
    
    # Reverse so chronological order is maintained
    rows.reverse() 
    
    history_text = "--- PREVIOUS EPISODIC MEMORY ---\n"
    for row in rows:
        history_text += f"Time: {row[0]}\nUser: {row[1]}\nAgent: {row[2]}\n\n"
    return history_text

# --- INITIALIZE DATABASE ON IMPORT ---
init_db()