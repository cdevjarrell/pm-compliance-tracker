"""SQLite storage so PM history builds up across imports."""

import sqlite3
from datetime import datetime

SCHEMA = """
CREATE TABLE IF NOT EXISTS imports (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    imported_at TEXT NOT NULL,
    source TEXT NOT NULL,
    filename TEXT NOT NULL,
    rows_saved INTEGER NOT NULL,
    issues INTEGER NOT NULL
);
    
CREATE TABLE IF NOT EXISTS work_orders (
    wo_no TEXT PRIMARY KEY,
    object_id TEXT NOT NULL,
    object_description TEXT,
    directive TEXT NOT NULL,
    status TEXT NOT NULL,
    planned_start TEXT NOT NULL,
    cell TEXT NOT NULL,
    frequency TEXT NOT NULL,
    month TEXT NOT NULL,
    week INTEGER NOT NULL,
    completed INTEGER NOT NULL,
    import_id INTEGER REFERENCES imports(id)
);
"""
COLUMNS = [
    "wo_no", "object_id", "object_description", "directive", "status", "planned_start", "cell", "frequency", "month", "week", "completed",
]

def connect(path="pm_tracker.db"):
    """Open (or create) the database and make sure the table exists!"""
    conn = sqlite3.connect(path)
    conn.executescript(SCHEMA)
    return conn

def save_work_orders(conn, df, source, filename, issue_count):
    """Insert or update work orders and log the import. Returns the import id.
    
    A work order that was open last time and is Finished now is simply replaced, because wo_no is the primary key.
    """
    cur = conn.execute(
        "INSERT INTO imports (imported_at, source, filename, rows_saved, issues) VALUES (?, ?, ?, ?, ?)",
        (datetime.now().isoformat(timespec="seconds"), source, filename, len(df), issue_count),
    )
    import_id = cur.lastrowid
    rows = [tuple(rec[c] for c in COLUMNS) + (import_id,) for rec in df.to_dict("records")]
    placeholders = ", ".join("?" * (len(COLUMNS) + 1))
    conn.executemany(
        f"INSERT OR REPLACE INTO work_orders ({', '.join(COLUMNS)}, import_id) VALUES ({placeholders})",
        rows
    )
    conn.commit()
    return import_id