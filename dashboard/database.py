"""SQLite database for JobRadar dashboard — job status tracking & activity log."""

import json
import os
import sqlite3
import time
from contextlib import contextmanager
from pathlib import Path
from typing import Any, Dict, List, Optional

DB_PATH = os.environ.get("JOBRADAR_DB", os.path.join(os.path.dirname(__file__), "jobradar_dashboard.db"))

VALID_STATUSES = [
    "discovered",
    "reviewing",
    "ready_to_apply",
    "applied",
    "interviewing",
    "rejected",
    "blacklisted",
]


def _connect() -> sqlite3.Connection:
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA foreign_keys=ON")
    return conn


def init_db():
    """Create tables if they don't exist."""
    conn = _connect()
    conn.executescript("""
        CREATE TABLE IF NOT EXISTS jobs (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            title TEXT NOT NULL,
            company TEXT NOT NULL,
            location TEXT DEFAULT '',
            url TEXT DEFAULT '',
            description TEXT DEFAULT '',
            salary TEXT DEFAULT '',
            source TEXT DEFAULT '',
            remote INTEGER DEFAULT 0,
            tags TEXT DEFAULT '[]',
            posted TEXT DEFAULT '',
            score INTEGER DEFAULT 0,
            rating TEXT DEFAULT '',
            reasoning TEXT DEFAULT '',
            skills_match INTEGER DEFAULT 0,
            experience_fit INTEGER DEFAULT 0,
            salary_fit INTEGER DEFAULT 0,
            remote_fit INTEGER DEFAULT 0,
            status TEXT DEFAULT 'discovered',

            created_at REAL NOT NULL,
            updated_at REAL NOT NULL,
            UNIQUE(title, company, source)
        );

        CREATE TABLE IF NOT EXISTS activity_log (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            timestamp REAL NOT NULL,
            level TEXT DEFAULT 'info',
            message TEXT NOT NULL,
            details TEXT DEFAULT ''
        );

        CREATE TABLE IF NOT EXISTS search_history (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            query TEXT NOT NULL,
            location TEXT DEFAULT '',
            sources_count INTEGER DEFAULT 0,
            jobs_found INTEGER DEFAULT 0,
            timestamp REAL NOT NULL
        );

        CREATE TABLE IF NOT EXISTS config (
            key TEXT PRIMARY KEY,
            value TEXT NOT NULL
        );

        CREATE INDEX IF NOT EXISTS idx_jobs_status ON jobs(status);
        CREATE INDEX IF NOT EXISTS idx_jobs_score ON jobs(score DESC);
        CREATE INDEX IF NOT EXISTS idx_activity_ts ON activity_log(timestamp DESC);
    """)
    conn.commit()
    conn.close()


@contextmanager
def get_db():
    conn = _connect()
    try:
        yield conn
    finally:
        conn.close()


# ─── Job CRUD ──────────────────────────────────────────────────────────────

def _row_to_dict(row: sqlite3.Row) -> Dict[str, Any]:
    d = dict(row)
    d["tags"] = json.loads(d["tags"]) if d["tags"] else []
    d["remote"] = bool(d["remote"])
    return d


def upsert_job(job_dict: Dict[str, Any]) -> Dict[str, Any]:
    """Insert or update a job. Returns the saved job dict."""
    now = time.time()
    with get_db() as conn:
        existing = conn.execute(
            "SELECT id FROM jobs WHERE title=? AND company=? AND source=?",
            (job_dict["title"], job_dict["company"], job_dict.get("source", "")),
        ).fetchone()

        if existing:
            conn.execute("""
                UPDATE jobs SET
                    location=?, url=?, description=?, salary=?, remote=?,
                    tags=?, posted=?, score=?, rating=?, reasoning=?,
                    skills_match=?, experience_fit=?, salary_fit=?, remote_fit=?,
                    updated_at=?
                WHERE id=?
            """, (
                job_dict.get("location", ""),
                job_dict.get("url", ""),
                job_dict.get("description", ""),
                job_dict.get("salary", ""),
                int(job_dict.get("remote", False)),
                json.dumps(job_dict.get("tags", [])),
                job_dict.get("posted", ""),
                job_dict.get("score", 0),
                job_dict.get("rating", ""),
                job_dict.get("reasoning", ""),
                job_dict.get("skills_match", 0),
                job_dict.get("experience_fit", 0),
                job_dict.get("salary_fit", 0),
                job_dict.get("remote_fit", 0),
                now,
                existing["id"],
            ))
            conn.commit()
            return get_job(existing["id"])
        else:
            conn.execute("""
                INSERT INTO jobs (title, company, location, url, description, salary,
                    source, remote, tags, posted, score, rating, reasoning,
                    skills_match, experience_fit, salary_fit, remote_fit,
                    created_at, updated_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                job_dict["title"],
                job_dict["company"],
                job_dict.get("location", ""),
                job_dict.get("url", ""),
                job_dict.get("description", ""),
                job_dict.get("salary", ""),
                job_dict.get("source", ""),
                int(job_dict.get("remote", False)),
                json.dumps(job_dict.get("tags", [])),
                job_dict.get("posted", ""),
                job_dict.get("score", 0),
                job_dict.get("rating", ""),
                job_dict.get("reasoning", ""),
                job_dict.get("skills_match", 0),
                job_dict.get("experience_fit", 0),
                job_dict.get("salary_fit", 0),
                job_dict.get("remote_fit", 0),
                now,
                now,
            ))
            conn.commit()
            return get_job(conn.execute("SELECT last_insert_rowid()").fetchone()[0])


def get_job(job_id: int) -> Optional[Dict[str, Any]]:
    with get_db() as conn:
        row = conn.execute("SELECT * FROM jobs WHERE id=?", (job_id,)).fetchone()
        return _row_to_dict(row) if row else None


def get_jobs(
    status: Optional[str] = None,
    min_score: int = 0,
    max_score: int = 100,
    remote_only: bool = False,
    source: Optional[str] = None,
    search: Optional[str] = None,
    sort_by: str = "created_at",
    sort_order: str = "DESC",
    limit: int = 200,
    offset: int = 0,
) -> List[Dict[str, Any]]:
    clauses = ["score >= ?", "score <= ?"]
    params: list = [min_score, max_score]

    if status:
        clauses.append("status = ?")
        params.append(status)
    if remote_only:
        clauses.append("remote = 1")
    if source:
        clauses.append("source = ?")
        params.append(source)
    if search:
        clauses.append("(title LIKE ? OR company LIKE ? OR description LIKE ?)")
        like = f"%{search}%"
        params.extend([like, like, like])

    where = " AND ".join(clauses)

    # Whitelist sort columns to prevent injection
    allowed_sorts = {"created_at", "updated_at", "score", "title", "company", "status"}
    if sort_by not in allowed_sorts:
        sort_by = "created_at"
    order = "DESC" if sort_order.upper() == "DESC" else "ASC"

    with get_db() as conn:
        rows = conn.execute(
            f"SELECT * FROM jobs WHERE {where} ORDER BY {sort_by} {order} LIMIT ? OFFSET ?",
            (*params, limit, offset),
        ).fetchall()
        return [_row_to_dict(r) for r in rows]


def update_job_status(job_id: int, new_status: str) -> Optional[Dict[str, Any]]:
    if new_status not in VALID_STATUSES:
        raise ValueError(f"Invalid status: {new_status}. Must be one of {VALID_STATUSES}")
    with get_db() as conn:
        conn.execute("UPDATE jobs SET status=?, updated_at=? WHERE id=?", (new_status, time.time(), job_id))
        conn.commit()
    return get_job(job_id)


def update_job_field(job_id: int, field: str, value: Any) -> Optional[Dict[str, Any]]:
    allowed_fields = {"status", "url", "notes"}
    if field not in allowed_fields:
        raise ValueError(f"Field '{field}' is not updatable")
    with get_db() as conn:
        conn.execute(f"UPDATE jobs SET {field}=?, updated_at=? WHERE id=?", (value, time.time(), job_id))
        conn.commit()
    return get_job(job_id)


def delete_job(job_id: int) -> bool:
    with get_db() as conn:
        cur = conn.execute("DELETE FROM jobs WHERE id=?", (job_id,))
        conn.commit()
        return cur.rowcount > 0


# ─── Stats ─────────────────────────────────────────────────────────────────

def get_stats() -> Dict[str, Any]:
    with get_db() as conn:
        total = conn.execute("SELECT COUNT(*) FROM jobs").fetchone()[0]
        by_status = {}
        for row in conn.execute("SELECT status, COUNT(*) as cnt FROM jobs GROUP BY status"):
            by_status[row["status"]] = row["cnt"]
        high_match = conn.execute("SELECT COUNT(*) FROM jobs WHERE score > 80").fetchone()[0]
        avg_score = conn.execute("SELECT COALESCE(AVG(score), 0) FROM jobs").fetchone()[0]
        by_source = {}
        for row in conn.execute("SELECT source, COUNT(*) as cnt FROM jobs GROUP BY source ORDER BY cnt DESC"):
            by_source[row["source"]] = row["cnt"]

        return {
            "total": total,
            "by_status": by_status,
            "high_match": high_match,
            "avg_score": round(avg_score, 1),
            "by_source": by_source,
        }


# ─── Activity Log ──────────────────────────────────────────────────────────

def log_activity(level: str, message: str, details: str = ""):
    with get_db() as conn:
        conn.execute(
            "INSERT INTO activity_log (timestamp, level, message, details) VALUES (?, ?, ?, ?)",
            (time.time(), level, message, details),
        )
        conn.commit()


def get_activity_log(limit: int = 100, offset: int = 0) -> List[Dict[str, Any]]:
    with get_db() as conn:
        rows = conn.execute(
            "SELECT * FROM activity_log ORDER BY timestamp DESC LIMIT ? OFFSET ?",
            (limit, offset),
        ).fetchall()
        return [dict(r) for r in rows]


# ─── Config ────────────────────────────────────────────────────────────────

def get_config(key: Optional[str] = None) -> Any:
    with get_db() as conn:
        if key:
            row = conn.execute("SELECT value FROM config WHERE key=?", (key,)).fetchone()
            return row["value"] if row else None
        rows = conn.execute("SELECT key, value FROM config").fetchall()
        return {r["key"]: r["value"] for r in rows}


def set_config(key: str, value: str):
    with get_db() as conn:
        conn.execute("INSERT OR REPLACE INTO config (key, value) VALUES (?, ?)", (key, value))
        conn.commit()


# ─── Search History ────────────────────────────────────────────────────────

def record_search(query: str, location: str, sources_count: int, jobs_found: int):
    with get_db() as conn:
        conn.execute(
            "INSERT INTO search_history (query, location, sources_count, jobs_found, timestamp) VALUES (?, ?, ?, ?, ?)",
            (query, location, sources_count, jobs_found, time.time()),
        )
        conn.commit()


# ─── Initialize on import ──────────────────────────────────────────────────
init_db()
