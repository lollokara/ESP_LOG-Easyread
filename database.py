import sqlite3
import time
import json
import threading
from typing import List, Optional, Tuple, Dict
from log_parser import LogEntry

class DatabaseManager:
    def __init__(self, db_path: str = "serial_logs.db"):
        self.db_path = db_path
        self._local = threading.local()
        self.init_db()

    def get_connection(self):
        if not hasattr(self._local, "conn"):
            self._local.conn = sqlite3.connect(self.db_path)
            self._local.conn.row_factory = sqlite3.Row
            # Enable WAL mode for better concurrency
            self._local.conn.execute("PRAGMA journal_mode=WAL;")
        return self._local.conn

    def init_db(self):
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        cursor.execute("""
            CREATE TABLE IF NOT EXISTS sessions (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT,
                start_time REAL,
                end_time REAL,
                log_count INTEGER DEFAULT 0,
                connection_info TEXT
            )
        """)

        cursor.execute("""
            CREATE TABLE IF NOT EXISTS logs (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                session_id INTEGER,
                timestamp TEXT,
                arrival_time REAL,
                level TEXT,
                file TEXT,
                function TEXT,
                message TEXT,
                original TEXT,
                FOREIGN KEY(session_id) REFERENCES sessions(id)
            )
        """)

        # Indices for faster querying
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_logs_session ON logs(session_id)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_logs_arrival ON logs(arrival_time)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_logs_level ON logs(level)")

        conn.commit()
        conn.close()

    def create_session(self, name: str, connection_info: str = "") -> int:
        conn = self.get_connection()
        cursor = conn.cursor()
        cursor.execute(
            "INSERT INTO sessions (name, start_time, end_time, log_count, connection_info) VALUES (?, ?, ?, ?, ?)",
            (name, time.time(), None, 0, connection_info)
        )
        session_id = cursor.lastrowid
        conn.commit()
        return session_id

    def end_session(self, session_id: int):
        conn = self.get_connection()
        conn.execute("UPDATE sessions SET end_time = ? WHERE id = ?", (time.time(), session_id))
        conn.commit()

    def insert_log(self, session_id: int, entry: LogEntry):
        conn = self.get_connection()
        conn.execute(
            """INSERT INTO logs (session_id, timestamp, arrival_time, level, file, function, message, original)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
            (session_id, entry.timestamp, entry.arrival_time, entry.level, entry.file, entry.function, entry.message, entry.original)
        )
        # We can optimize this by not updating count on every insert if it's slow, but for single user it's fine
        conn.execute("UPDATE sessions SET log_count = log_count + 1 WHERE id = ?", (session_id,))
        conn.commit()

    def insert_logs_batch(self, session_id: int, entries: List[LogEntry]):
        if not entries: return
        conn = self.get_connection()
        data = [
            (session_id, e.timestamp, e.arrival_time, e.level, e.file, e.function, e.message, e.original)
            for e in entries
        ]
        conn.executemany(
            """INSERT INTO logs (session_id, timestamp, arrival_time, level, file, function, message, original)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
            data
        )
        conn.execute("UPDATE sessions SET log_count = log_count + ? WHERE id = ?", (len(entries), session_id))
        conn.commit()

    def get_sessions(self) -> List[Dict]:
        conn = self.get_connection()
        cursor = conn.execute("SELECT * FROM sessions ORDER BY start_time DESC")
        return [dict(row) for row in cursor.fetchall()]

    def delete_session(self, session_id: int):
        conn = self.get_connection()
        conn.execute("DELETE FROM logs WHERE session_id = ?", (session_id,))
        conn.execute("DELETE FROM sessions WHERE id = ?", (session_id,))
        conn.commit()

    def clear_session_logs(self, session_id: int):
        conn = self.get_connection()
        conn.execute("DELETE FROM logs WHERE session_id = ?", (session_id,))
        conn.execute("UPDATE sessions SET log_count = 0 WHERE id = ?", (session_id,))
        conn.commit()

    def get_logs(self, session_id: int, limit: int = 2000, offset: int = 0,
                 filters: Dict = None, search_term: str = None) -> List[LogEntry]:
        conn = self.get_connection()
        query = "SELECT * FROM logs WHERE session_id = ?"
        params = [session_id]

        if filters:
            if "level" in filters and filters["level"]:
                placeholders = ",".join("?" * len(filters["level"]))
                query += f" AND level IN ({placeholders})"
                params.extend(filters["level"])
            if "file" in filters and filters["file"] and "ALL" not in filters["file"]:
                placeholders = ",".join("?" * len(filters["file"]))
                query += f" AND file IN ({placeholders})"
                params.extend(filters["file"])
            if "function" in filters and filters["function"] and "ALL" not in filters["function"]:
                placeholders = ",".join("?" * len(filters["function"]))
                query += f" AND function IN ({placeholders})"
                params.extend(filters["function"])

        if search_term:
            # Simple LIKE search. For advanced, we'd need FTS or more logic.
            # Supporting wildcards * and ? requires converting them to SQL % and _
            # But user code used fnmatch. SQL LIKE uses % and _.
            # User wants * (any chars) and ? (one char).
            # SQL: % (any chars), _ (one char).
            sql_pattern = search_term.replace("*", "%").replace("?", "_")
            if "%" not in sql_pattern and "_" not in sql_pattern:
                sql_pattern = f"%{sql_pattern}%" # Default to contains

            query += " AND original LIKE ?"
            params.append(sql_pattern)

        # Optimization: To scroll UP, we might want to fetch backward?
        # But usually we just use offset/limit.
        # Assuming we want the LATEST logs first (bottom of view), we order by ID DESC?
        # Or if we want strictly chronological: ID ASC.
        # The UI usually expects chronological top-to-bottom.
        # But if we want to "load current logs", we usually want the *last* N logs.
        # If the user is scrolling, they give an explicit offset.

        # Let's standardize: The query always returns logs in chronological order (ASC).
        # The caller handles the window logic.

        query += " ORDER BY id ASC LIMIT ? OFFSET ?"
        params.append(limit)
        params.append(offset)

        cursor = conn.execute(query, params)
        rows = cursor.fetchall()

        return [LogEntry(
            timestamp=row['timestamp'],
            level=row['level'],
            file=row['file'],
            function=row['function'],
            message=row['message'],
            original=row['original'],
            arrival_time=row['arrival_time']
        ) for row in rows]

    def get_total_log_count(self, session_id: int, filters: Dict = None, search_term: str = None) -> int:
        conn = self.get_connection()
        query = "SELECT COUNT(*) FROM logs WHERE session_id = ?"
        params = [session_id]

        if filters:
             if "level" in filters and filters["level"]:
                placeholders = ",".join("?" * len(filters["level"]))
                query += f" AND level IN ({placeholders})"
                params.extend(filters["level"])
             if "file" in filters and filters["file"] and "ALL" not in filters["file"]:
                placeholders = ",".join("?" * len(filters["file"]))
                query += f" AND file IN ({placeholders})"
                params.extend(filters["file"])
             if "function" in filters and filters["function"] and "ALL" not in filters["function"]:
                placeholders = ",".join("?" * len(filters["function"]))
                query += f" AND function IN ({placeholders})"
                params.extend(filters["function"])

        if search_term:
            sql_pattern = search_term.replace("*", "%").replace("?", "_")
            if "%" not in sql_pattern and "_" not in sql_pattern:
                sql_pattern = f"%{sql_pattern}%"
            query += " AND original LIKE ?"
            params.append(sql_pattern)

        cursor = conn.execute(query, params)
        return cursor.fetchone()[0]

    def get_unique_files(self, session_id: int) -> List[str]:
        conn = self.get_connection()
        cursor = conn.execute("SELECT DISTINCT file FROM logs WHERE session_id = ? ORDER BY file", (session_id,))
        return [row[0] for row in cursor.fetchall() if row[0] != "UNDEFINED"]

    def get_unique_functions(self, session_id: int) -> List[str]:
        conn = self.get_connection()
        cursor = conn.execute("SELECT DISTINCT function FROM logs WHERE session_id = ? ORDER BY function", (session_id,))
        return [row[0] for row in cursor.fetchall() if row[0] != "UNDEFINED"]
