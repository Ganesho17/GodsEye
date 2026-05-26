"""
database/database.py
God's Eye — SQLite Persistence Layer

Extended safely with new tables while preserving the existing schema:
  - incidents    : existing table (unchanged)
  - devices      : NEW — registered camera devices
  - crowd_history: NEW — time-series crowd count logging per camera
  - annotated_screenshots: NEW — links raw/annotated image pairs to incidents

All new tables use CREATE TABLE IF NOT EXISTS.
New columns on existing tables use ALTER TABLE ... ADD COLUMN with error handling.
"""

import sqlite3
import os
from datetime import datetime

DB_DIR  = os.path.dirname(os.path.abspath(__file__))
DB_PATH = os.path.join(DB_DIR, 'incidents.db')


def get_db_connection():
    """Establishes a thread-safe connection. Returns rows as dict-like objects."""
    conn = sqlite3.connect(DB_PATH, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")  # Write-Ahead Logging for concurrent access
    return conn


def _add_column_if_missing(cursor, table, column, col_type):
    """Safely adds a column to an existing table if it doesn't already exist."""
    try:
        cursor.execute(f"ALTER TABLE {table} ADD COLUMN {column} {col_type}")
    except sqlite3.OperationalError:
        pass  # Column already exists — ignore silently


def init_db():
    """
    Initializes all database tables and indices.
    Safe to call multiple times — idempotent.
    """
    os.makedirs(DB_DIR, exist_ok=True)
    conn   = get_db_connection()
    cursor = conn.cursor()

    # ---- 1. Original incidents table (preserved exactly) ----
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS incidents (
            id              INTEGER PRIMARY KEY AUTOINCREMENT,
            timestamp       TEXT NOT NULL,
            threat_type     TEXT NOT NULL,
            threat_score    INTEGER NOT NULL,
            threat_level    TEXT NOT NULL,
            crowd_count     INTEGER NOT NULL,
            screenshot_path TEXT
        )
    ''')

    # ---- Extend incidents with new columns (non-breaking) ----
    _add_column_if_missing(cursor, 'incidents', 'camera_id',       'TEXT DEFAULT "cam_0"')
    _add_column_if_missing(cursor, 'incidents', 'camera_name',     'TEXT DEFAULT "Primary Webcam"')
    _add_column_if_missing(cursor, 'incidents', 'annotated_path',  'TEXT')
    _add_column_if_missing(cursor, 'incidents', 'explanation',     'TEXT')
    _add_column_if_missing(cursor, 'incidents', 'is_resolved',     'INTEGER DEFAULT 0')

    # ---- 2. Devices registry table (NEW) ----
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS devices (
            id          TEXT PRIMARY KEY,
            name        TEXT NOT NULL,
            type        TEXT NOT NULL,
            source      TEXT NOT NULL,
            location    TEXT DEFAULT "Unknown",
            is_active   INTEGER DEFAULT 1,
            created_at  TEXT NOT NULL
        )
    ''')

    # ---- 3. Crowd history time-series (NEW) ----
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS crowd_history (
            id          INTEGER PRIMARY KEY AUTOINCREMENT,
            camera_id   TEXT NOT NULL,
            count       INTEGER NOT NULL,
            density     TEXT NOT NULL,
            timestamp   TEXT NOT NULL
        )
    ''')

    # ---- 4. Annotated screenshot registry (NEW) ----
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS annotated_screenshots (
            id              INTEGER PRIMARY KEY AUTOINCREMENT,
            incident_id     INTEGER,
            camera_id       TEXT NOT NULL,
            raw_path        TEXT NOT NULL,
            annotated_path  TEXT NOT NULL,
            timestamp       TEXT NOT NULL,
            FOREIGN KEY (incident_id) REFERENCES incidents(id)
        )
    ''')

    # ---- Speed indices ----
    cursor.execute('CREATE INDEX IF NOT EXISTS idx_threat_level  ON incidents(threat_level)')
    cursor.execute('CREATE INDEX IF NOT EXISTS idx_timestamp     ON incidents(timestamp DESC)')
    cursor.execute('CREATE INDEX IF NOT EXISTS idx_camera_id     ON incidents(camera_id)')
    cursor.execute('CREATE INDEX IF NOT EXISTS idx_is_resolved   ON incidents(is_resolved)')
    cursor.execute('CREATE INDEX IF NOT EXISTS idx_crowd_cam     ON crowd_history(camera_id)')
    cursor.execute('CREATE INDEX IF NOT EXISTS idx_crowd_ts      ON crowd_history(timestamp DESC)')

    conn.commit()
    conn.close()
    print(f"[GodsEye DB] SQLite database initialized at {DB_PATH}")


# ============================================================
# INCIDENTS
# ============================================================

def add_incident(threat_type, threat_score, threat_level, crowd_count,
                 screenshot_path=None, camera_id="cam_0", camera_name="Primary Webcam",
                 annotated_path=None, explanation=None):
    """
    Inserts a new threat incident into the database.

    Parameters (new, optional):
        camera_id:      ID of the source camera device
        camera_name:    Human-readable camera label
        annotated_path: Path to the annotated alert image
        explanation:    AI-style text explanation of the threat

    Returns:
        The inserted record as a serialized dictionary.
    """
    timestamp         = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    served_screenshot = os.path.basename(screenshot_path) if screenshot_path else None
    served_annotated  = os.path.basename(annotated_path)  if annotated_path  else None

    conn   = get_db_connection()
    cursor = conn.cursor()

    cursor.execute('''
        INSERT INTO incidents
            (timestamp, threat_type, threat_score, threat_level, crowd_count,
             screenshot_path, camera_id, camera_name, annotated_path, explanation)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    ''', (timestamp, threat_type, threat_score, threat_level, crowd_count,
          served_screenshot, camera_id, camera_name, served_annotated, explanation))

    record_id = cursor.lastrowid
    conn.commit()
    conn.close()

    print(f"[GodsEye DB] Incident #{record_id} [{threat_type}] | {threat_level} | Score:{threat_score} | Cam:{camera_name}")

    return {
        'id':             record_id,
        'timestamp':      timestamp,
        'incident_type':  threat_type,
        'threat_score':   threat_score,
        'threat_level':   threat_level,
        'crowd_count':    crowd_count,
        'screenshot':     served_screenshot,
        'annotated_path': served_annotated,
        'camera_id':      camera_id,
        'camera_name':    camera_name,
        'explanation':    explanation,
        'is_resolved':    False
    }


def get_incidents(threat_level="ALL", camera_id=None, limit=200):
    """
    Retrieves incident logs, newest first.
    Supports filtering by threat_level and/or camera_id.
    """
    conn   = get_db_connection()
    cursor = conn.cursor()

    conditions = []
    params     = []

    if threat_level.upper() != "ALL":
        conditions.append("upper(threat_level) = ?")
        params.append(threat_level.upper())

    if camera_id:
        conditions.append("camera_id = ?")
        params.append(camera_id)

    where = f"WHERE {' AND '.join(conditions)}" if conditions else ""
    params.append(limit)

    cursor.execute(f'''
        SELECT * FROM incidents {where}
        ORDER BY timestamp DESC LIMIT ?
    ''', params)

    rows = cursor.fetchall()
    conn.close()

    logs = []
    for row in rows:
        logs.append({
            'id':             row['id'],
            'timestamp':      row['timestamp'],
            'incident_type':  row['threat_type'],
            'threat_score':   row['threat_score'],
            'threat_level':   row['threat_level'],
            'crowd_count':    row['crowd_count'],
            'screenshot':     row['screenshot_path'],
            'annotated_path': row['annotated_path'] if 'annotated_path' in row.keys() else None,
            'camera_id':      row['camera_id']      if 'camera_id'      in row.keys() else 'cam_0',
            'camera_name':    row['camera_name']    if 'camera_name'    in row.keys() else 'Primary Webcam',
            'explanation':    row['explanation']    if 'explanation'    in row.keys() else None,
            'is_resolved':    bool(row['is_resolved'] if 'is_resolved' in row.keys() else False)
        })

    return logs


def resolve_incident(incident_id):
    """Marks a single incident as resolved."""
    conn = get_db_connection()
    conn.execute('UPDATE incidents SET is_resolved = 1 WHERE id = ?', (incident_id,))
    conn.commit()
    conn.close()


def resolve_all_incidents():
    """Marks all incidents as resolved."""
    conn = get_db_connection()
    conn.execute('UPDATE incidents SET is_resolved = 1')
    conn.commit()
    conn.close()


def get_alert_stats():
    """Returns summary statistics for all incidents."""
    conn   = get_db_connection()
    cursor = conn.cursor()

    cursor.execute('''
        SELECT
            COUNT(*) as total,
            SUM(CASE WHEN is_resolved = 0 THEN 1 ELSE 0 END) as unresolved,
            SUM(CASE WHEN threat_level = "CRITICAL" THEN 1 ELSE 0 END) as critical_count,
            SUM(CASE WHEN threat_level = "HIGH"     THEN 1 ELSE 0 END) as high_count,
            SUM(CASE WHEN threat_level = "MEDIUM"   THEN 1 ELSE 0 END) as medium_count,
            SUM(CASE WHEN threat_level = "LOW"      THEN 1 ELSE 0 END) as low_count,
            MAX(threat_score) as peak_score
        FROM incidents
    ''')
    row  = cursor.fetchone()
    conn.close()

    return {
        'total':          row['total']          or 0,
        'unresolved':     row['unresolved']      or 0,
        'critical_count': row['critical_count']  or 0,
        'high_count':     row['high_count']      or 0,
        'medium_count':   row['medium_count']    or 0,
        'low_count':      row['low_count']       or 0,
        'peak_score':     row['peak_score']      or 0
    }


def clear_incidents():
    """Permanently wipes all incident logs."""
    conn = get_db_connection()
    conn.execute('DELETE FROM incidents')
    conn.commit()
    conn.close()
    print("[GodsEye DB] All incident logs cleared.")


# ============================================================
# DEVICES
# ============================================================

def register_device(device_id, name, device_type, source, location="Unknown"):
    """Upserts a camera device registration into the devices table."""
    timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    conn      = get_db_connection()
    conn.execute('''
        INSERT OR REPLACE INTO devices (id, name, type, source, location, is_active, created_at)
        VALUES (?, ?, ?, ?, ?, 1, ?)
    ''', (device_id, name, device_type, str(source), location, timestamp))
    conn.commit()
    conn.close()


def get_devices():
    """Returns all registered camera devices."""
    conn   = get_db_connection()
    cursor = conn.cursor()
    cursor.execute('SELECT * FROM devices ORDER BY created_at DESC')
    rows   = cursor.fetchall()
    conn.close()
    return [dict(row) for row in rows]


def update_device_status(device_id, is_active):
    """Updates the online/offline status of a device."""
    conn = get_db_connection()
    conn.execute('UPDATE devices SET is_active = ? WHERE id = ?', (int(is_active), device_id))
    conn.commit()
    conn.close()


def delete_device(device_id):
    """Removes a device from the registry."""
    conn = get_db_connection()
    conn.execute('DELETE FROM devices WHERE id = ?', (device_id,))
    conn.commit()
    conn.close()


# ============================================================
# CROWD HISTORY
# ============================================================

def log_crowd(camera_id, count, density):
    """Inserts one crowd count data point into the time-series table."""
    timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    conn      = get_db_connection()
    conn.execute(
        'INSERT INTO crowd_history (camera_id, count, density, timestamp) VALUES (?, ?, ?, ?)',
        (camera_id, count, density, timestamp)
    )
    conn.commit()
    conn.close()


def get_crowd_history(camera_id=None, hours=24, limit=500):
    """
    Returns time-series crowd count data.

    Parameters:
        camera_id: Optional — filter by specific camera
        hours:     How many hours of history to return
        limit:     Max data points to return
    """
    conn   = get_db_connection()
    cursor = conn.cursor()

    cutoff = datetime.now().strftime('%Y-%m-%d %H:%M:%S')

    if camera_id:
        cursor.execute('''
            SELECT camera_id, count, density, timestamp FROM crowd_history
            WHERE camera_id = ?
            ORDER BY timestamp DESC LIMIT ?
        ''', (camera_id, limit))
    else:
        cursor.execute('''
            SELECT camera_id, count, density, timestamp FROM crowd_history
            ORDER BY timestamp DESC LIMIT ?
        ''', (limit,))

    rows   = cursor.fetchall()
    conn.close()

    return [
        {
            'camera_id': row['camera_id'],
            'count':     row['count'],
            'density':   row['density'],
            'timestamp': row['timestamp']
        }
        for row in reversed(rows)  # Return in chronological order
    ]