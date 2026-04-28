"""SQLite schema, upsert, and query helpers."""

import logging
import sqlite3
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)

DDL = """
CREATE TABLE IF NOT EXISTS files (
    id              TEXT PRIMARY KEY,
    name            TEXT NOT NULL,
    mime_type       TEXT,
    size_bytes      INTEGER,
    owner           TEXT,
    modified_at     TEXT,
    parent_id       TEXT,
    web_view_link   TEXT,
    is_trashed      INTEGER DEFAULT 0,
    indexed_at      TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_files_name      ON files (name);
CREATE INDEX IF NOT EXISTS idx_files_mime_type ON files (mime_type);
CREATE INDEX IF NOT EXISTS idx_files_owner     ON files (owner);
CREATE INDEX IF NOT EXISTS idx_files_parent_id ON files (parent_id);

CREATE TABLE IF NOT EXISTS index_runs (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    started_at      TEXT NOT NULL,
    finished_at     TEXT,
    query           TEXT,
    last_page_token TEXT,
    files_scanned   INTEGER DEFAULT 0,
    files_added     INTEGER DEFAULT 0,
    files_updated   INTEGER DEFAULT 0,
    files_deleted   INTEGER DEFAULT 0,
    status          TEXT DEFAULT 'running',
    error_msg       TEXT
);

CREATE TABLE IF NOT EXISTS briefs (
    file_id         TEXT PRIMARY KEY REFERENCES files(id),
    brief           TEXT,
    error           TEXT,
    briefed_at      TEXT NOT NULL
);
"""


def connect(db_path: str) -> sqlite3.Connection:
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    conn.executescript(DDL)
    _migrate(conn)
    conn.commit()
    return conn


def _migrate(conn: sqlite3.Connection) -> None:
    """Add missing columns to existing tables."""
    # Add 'query' and 'last_page_token' to index_runs if they don't exist
    cursor = conn.execute("PRAGMA table_info(index_runs)")
    columns = [row["name"] for row in cursor.fetchall()]
    
    if "query" not in columns:
        logger.info("Migrating DB: adding 'query' column to index_runs")
        conn.execute("ALTER TABLE index_runs ADD COLUMN query TEXT")
    
    if "last_page_token" not in columns:
        logger.info("Migrating DB: adding 'last_page_token' column to index_runs")
        conn.execute("ALTER TABLE index_runs ADD COLUMN last_page_token TEXT")


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def upsert_file(conn: sqlite3.Connection, f: Dict[str, Any]) -> str:
    """
    Insert or update a file record.
    Returns 'added' or 'updated'.
    """
    file_id = f["id"]
    existing = conn.execute(
        "SELECT id FROM files WHERE id = ?", (file_id,)
    ).fetchone()

    owners = f.get("owners") or []
    owner = owners[0]["emailAddress"] if owners else None
    parents = f.get("parents") or []
    parent_id = parents[0] if parents else None
    size = f.get("size")
    size_bytes = int(size) if size is not None else None

    now = _now()
    conn.execute(
        """
        INSERT INTO files (id, name, mime_type, size_bytes, owner, modified_at,
                           parent_id, web_view_link, is_trashed, indexed_at)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, 0, ?)
        ON CONFLICT(id) DO UPDATE SET
            name          = excluded.name,
            mime_type     = excluded.mime_type,
            size_bytes    = excluded.size_bytes,
            owner         = excluded.owner,
            modified_at   = excluded.modified_at,
            parent_id     = excluded.parent_id,
            web_view_link = excluded.web_view_link,
            is_trashed    = 0,
            indexed_at    = excluded.indexed_at
        """,
        (
            file_id,
            f.get("name"),
            f.get("mimeType"),
            size_bytes,
            owner,
            f.get("modifiedTime"),
            parent_id,
            f.get("webViewLink"),
            now,
        ),
    )
    return "added" if existing is None else "updated"


def mark_as_trashed(conn: sqlite3.Connection, file_id: str) -> None:
    """Mark a file as trashed in the database."""
    conn.execute(
        "UPDATE files SET is_trashed = 1, indexed_at = ? WHERE id = ?",
        (_now(), file_id),
    )


def start_run(conn: sqlite3.Connection, query: Optional[str] = None) -> int:
    cur = conn.execute(
        "INSERT INTO index_runs (started_at, query, status) VALUES (?, ?, 'running')",
        (_now(), query),
    )
    conn.commit()
    return cur.lastrowid


def save_page_token(conn: sqlite3.Connection, run_id: int, token: Optional[str]) -> None:
    """Save the nextPageToken to allow resuming later."""
    conn.execute(
        "UPDATE index_runs SET last_page_token = ? WHERE id = ?",
        (token, run_id),
    )
    conn.commit()


def get_resume_token(conn: sqlite3.Connection, run_id: int) -> Optional[str]:
    """Get the last saved page token for a specific run."""
    row = conn.execute(
        "SELECT last_page_token FROM index_runs WHERE id = ?", (run_id,)
    ).fetchone()
    return row["last_page_token"] if row else None


def get_resumable_run(conn: sqlite3.Connection, query: str) -> Optional[sqlite3.Row]:
    """Find the most recent failed run with the same query that has a page token."""
    return conn.execute(
        """
        SELECT * FROM index_runs 
        WHERE query = ? AND status = 'error' AND last_page_token IS NOT NULL
        ORDER BY started_at DESC LIMIT 1
        """,
        (query,),
    ).fetchone()


def finish_run(
    conn: sqlite3.Connection,
    run_id: int,
    scanned: int,
    added: int,
    updated: int,
    deleted: int,
    status: str = "ok",
    error_msg: Optional[str] = None,
) -> None:
    conn.execute(
        """
        UPDATE index_runs
        SET finished_at = ?, files_scanned = ?, files_added = ?, files_updated = ?,
            files_deleted = ?, status = ?, error_msg = ?
        WHERE id = ?
        """,
        (_now(), scanned, added, updated, deleted, status, error_msg, run_id),
    )
    conn.commit()


def search_files(
    conn: sqlite3.Connection,
    name: Optional[str] = None,
    mime: Optional[str] = None,
    owner: Optional[str] = None,
    parent_id: Optional[str] = None,
    after: Optional[str] = None,
    before: Optional[str] = None,
    include_trashed: bool = False,
    trashed_only: bool = False,
    has_brief: Optional[bool] = None,
    brief_contains: Optional[str] = None,
    sort_by: str = "modified",
    fields: Optional[List[str]] = None,
    limit: int = 50,
) -> List[sqlite3.Row]:
    params: List[Any] = []
    
    # Handle trashed logic
    if trashed_only:
        clauses = ["f.is_trashed = 1"]
    elif include_trashed:
        clauses = []
    else:
        clauses = ["f.is_trashed = 0"]

    if name:
        # Tokenized fuzzy search (AND logic)
        tokens = name.split()
        for t in tokens:
            clauses.append("f.name LIKE ?")
            params.append(f"%{t}%")
            
    if mime:
        clauses.append("f.mime_type LIKE ?")
        params.append(f"%{mime}%")
    if owner:
        clauses.append("f.owner LIKE ?")
        params.append(f"%{owner}%")
    if parent_id:
        clauses.append("f.parent_id = ?")
        params.append(parent_id)
    
    # Date filters
    if after:
        clauses.append("f.modified_at >= ?")
        params.append(after)
    if before:
        clauses.append("f.modified_at <= ?")
        params.append(before)

    # Brief filters
    if has_brief is True:
        clauses.append("b.brief IS NOT NULL")
    elif has_brief is False:
        clauses.append("b.brief IS NULL")
    
    if brief_contains:
        clauses.append("b.brief LIKE ?")
        params.append(f"%{brief_contains}%")

    where = ""
    if clauses:
        where = "WHERE " + " AND ".join(clauses)

    # Ordering
    sort_map = {
        "modified": "f.modified_at DESC",
        "size": "f.size_bytes DESC",
        "name": "f.name ASC",
    }
    order_by = sort_map.get(sort_by, "f.modified_at DESC")

    # Field selection
    if fields:
        allowed = {
            "id", "name", "mime_type", "size_bytes", "owner", 
            "modified_at", "parent_id", "web_view_link", "is_trashed", "indexed_at",
            "brief", "briefed_at"
        }
        select_fields = []
        for f in fields:
            f = f.strip()
            if f in allowed:
                prefix = "b." if f in ["brief", "briefed_at"] else "f."
                select_fields.append(f"{prefix}{f}")
        select_clause = ", ".join(select_fields) if select_fields else "f.*, b.brief, b.briefed_at"
    else:
        select_clause = "f.*, b.brief, b.briefed_at"

    query = f"""
        SELECT {select_clause}
        FROM files f
        LEFT JOIN briefs b ON b.file_id = f.id
        {where}
        ORDER BY {order_by}
        LIMIT ?
    """
    params.append(limit)
    rows = conn.execute(query, params).fetchall()
    return rows


def save_brief(
    conn: sqlite3.Connection,
    file_id: str,
    brief: Optional[str],
    error: Optional[str] = None,
) -> None:
    """Upsert a brief (or error) for a given file."""
    conn.execute(
        """
        INSERT INTO briefs (file_id, brief, error, briefed_at)
        VALUES (?, ?, ?, ?)
        ON CONFLICT(file_id) DO UPDATE SET
            brief      = excluded.brief,
            error      = excluded.error,
            briefed_at = excluded.briefed_at
        """,
        (file_id, brief, error, _now()),
    )
    conn.commit()


def get_unbriefed_files(
    conn: sqlite3.Connection,
    since: Optional[str] = None,
    limit: int = 50,
) -> List[sqlite3.Row]:
    """
    Return files that:
    - Have a briefable MIME type (docx, pdf, xlsx, pptx)
    - Either have no brief yet, OR were modified after their last briefed_at
    """
    briefable_mimes = (
        "application/vnd.openxmlformats-officedocument",
        "application/msword",
        "application/pdf",
        "application/vnd.ms-excel",
        "application/vnd.ms-powerpoint",
    )
    mime_clause = " OR ".join(
        ["f.mime_type LIKE ?" for _ in briefable_mimes]
    )
    mime_params = [f"%{m}%" for m in briefable_mimes]

    since_clause = ""
    since_params: List[Any] = []
    if since:
        since_clause = "AND f.modified_at > ?"
        since_params = [since]

    rows = conn.execute(
        f"""
        SELECT f.*
        FROM files f
        LEFT JOIN briefs b ON b.file_id = f.id
        WHERE f.is_trashed = 0
          AND ({mime_clause})
          {since_clause}
          AND (
              b.file_id IS NULL
              OR f.modified_at > b.briefed_at
          )
        ORDER BY f.modified_at DESC
        LIMIT ?
        """,
        mime_params + since_params + [limit],
    ).fetchall()
    return rows


def get_last_brief_run(conn: sqlite3.Connection) -> Optional[str]:
    """Return the ISO timestamp of the most recent successful brief, or None."""
    row = conn.execute(
        "SELECT MAX(briefed_at) AS last FROM briefs WHERE brief IS NOT NULL"
    ).fetchone()
    return row["last"] if row else None


def get_last_successful_run(conn: sqlite3.Connection) -> Optional[str]:
    """Return the finished_at timestamp of the most recent successful index run, or None."""
    row = conn.execute(
        "SELECT finished_at FROM index_runs WHERE status = 'ok' ORDER BY finished_at DESC LIMIT 1"
    ).fetchone()
    return row["finished_at"] if row else None
