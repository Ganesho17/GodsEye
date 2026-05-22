import sqlite3
import os
from datetime import datetime

DB_DIR = os.path.dirname(os.path.abspath(__file__))
DB_PATH = os.path.join(DB_DIR, 'incidents.db')

def get_db_connection():
    """Establishes and returns a thread-safe connection to the SQLite database."""
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row  # Returns query results as dictionary-like objects
    return conn

def init_db():
    """Initializes the database schema if the incidents table does not exist."""
    os.makedirs(DB_DIR, exist_ok=True)
    conn = get_db_connection()
    cursor = conn.cursor()
    
    # Create high-performance indexable incidents table
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS incidents (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            timestamp TEXT NOT NULL,
            threat_type TEXT NOT NULL,
            threat_score INTEGER NOT NULL,
            threat_level TEXT NOT NULL,
            crowd_count INTEGER NOT NULL,
            screenshot_path TEXT
        )
    ''')
    
    # Create speed index for query optimizations
    cursor.execute('CREATE INDEX IF NOT EXISTS idx_threat_level ON incidents(threat_level)')
    cursor.execute('CREATE INDEX IF NOT EXISTS idx_timestamp ON incidents(timestamp DESC)')
    
    conn.commit()
    conn.close()
    print(f"GodsEye DB: SQLite database successfully initialized at {DB_PATH}")

def add_incident(threat_type, threat_score, threat_level, crowd_count, screenshot_path=None):
    """
    Inserts a newly detected threat incident into the database.
    Returns the inserted record as a serialized dictionary.
    """
    timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    
    # Clean file path relative to client for serving static assets
    served_screenshot = None
    if screenshot_path:
        served_screenshot = os.path.basename(screenshot_path)

    conn = get_db_connection()
    cursor = conn.cursor()
    
    cursor.execute('''
        INSERT INTO incidents (timestamp, threat_type, threat_score, threat_level, crowd_count, screenshot_path)
        VALUES (?, ?, ?, ?, ?, ?)
    ''', (timestamp, threat_type, threat_score, threat_level, crowd_count, served_screenshot))
    
    record_id = cursor.lastrowid
    conn.commit()
    conn.close()
    
    print(f"GodsEye DB: Logged incident #{record_id} [{threat_type}] // Severity: {threat_level} // Score: {threat_score}")
    
    return {
        "id": record_id,
        "timestamp": timestamp,
        "incident_type": threat_type,
        "threat_score": threat_score,
        "threat_level": threat_level,
        "crowd_count": crowd_count,
        "screenshot": served_screenshot
    }

def get_incidents(threat_level="ALL"):
    """
    Retrieves incident logs from the database, sorted chronologically (newest first).
    Supports optional filtering by threat_level ('HIGH', 'MEDIUM', 'LOW').
    """
    conn = get_db_connection()
    cursor = conn.cursor()
    
    if threat_level.upper() == "ALL":
        cursor.execute('SELECT * FROM incidents ORDER BY timestamp DESC LIMIT 200')
    else:
        cursor.execute('''
            SELECT * FROM incidents 
            WHERE upper(threat_level) = ? 
            ORDER BY timestamp DESC LIMIT 200
        ''', (threat_level.upper(),))
        
    rows = cursor.fetchall()
    conn.close()
    
    logs = []
    for row in rows:
        logs.append({
            "id": row["id"],
            "timestamp": row["timestamp"],
            "incident_type": row["threat_type"],
            "threat_score": row["threat_score"],
            "threat_level": row["threat_level"],
            "crowd_count": row["crowd_count"],
            "screenshot": row["screenshot_path"]
        })
        
    return logs

def clear_incidents():
    """Wipes all rows from the security log history."""
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute('DELETE FROM incidents')
    conn.commit()
    conn.close()
    print("GodsEye DB: All logs permanently cleared.")