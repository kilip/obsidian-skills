"""Query the local SQLite index."""

import logging
from typing import Optional

from gdrive import db

import re
from datetime import datetime, timedelta, timezone

logger = logging.getLogger(__name__)

_MIME_SHORTCUTS = {
    "doc": "wordprocessingml",
    "docx": "wordprocessingml",
    "sheet": "spreadsheetml",
    "xlsx": "spreadsheetml",
    "slide": "presentationml",
    "pptx": "presentationml",
    "pdf": "application/pdf",
    "image": "image/",
    "folder": "application/vnd.google-apps.folder",
    "gdoc": "application/vnd.google-apps.document",
    "gsheet": "application/vnd.google-apps.spreadsheet",
    "gslide": "application/vnd.google-apps.presentation",
}


def _resolve_mime(mime: Optional[str]) -> Optional[str]:
    if not mime:
        return None
    return _MIME_SHORTCUTS.get(mime.lower(), mime)


def _parse_date(val: Optional[str]) -> Optional[str]:
    if not val:
        return None
    
    # Check for relative date (e.g., 7d, 30d)
    match = re.match(r"^(\d+)([dw])$", val.lower())
    if match:
        amount = int(match.group(1))
        unit = match.group(2)
        days = amount * 7 if unit == "w" else amount
        dt = datetime.now(timezone.utc) - timedelta(days=days)
        return dt.isoformat()

    # Fallback/Try ISO
    try:
        # Just validate it's a valid date string
        datetime.fromisoformat(val.replace("Z", "+00:00"))
        return val
    except ValueError:
        logger.warning(f"Could not parse date: {val}. Expected ISO or relative (7d).")
        return val


def run(
    conn,
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
    limit: int = 50,
):
    resolved_mime = _resolve_mime(mime)
    parsed_after = _parse_date(after)
    parsed_before = _parse_date(before)

    rows = db.search_files(
        conn,
        name=name,
        mime=resolved_mime,
        owner=owner,
        parent_id=parent_id,
        after=parsed_after,
        before=parsed_before,
        include_trashed=include_trashed,
        trashed_only=trashed_only,
        has_brief=has_brief,
        brief_contains=brief_contains,
        limit=limit,
    )
    return rows
