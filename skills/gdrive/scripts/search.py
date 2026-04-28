"""Query the local SQLite index."""

import logging
from typing import Optional

from gdrive import db

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


def run(
    conn,
    name: Optional[str] = None,
    mime: Optional[str] = None,
    owner: Optional[str] = None,
    parent_id: Optional[str] = None,
    limit: int = 50,
):
    resolved_mime = _resolve_mime(mime)
    rows = db.search_files(
        conn,
        name=name,
        mime=resolved_mime,
        owner=owner,
        parent_id=parent_id,
        limit=limit,
    )
    return rows
