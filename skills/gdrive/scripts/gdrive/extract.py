"""
extract.py — Decoupled content extraction logic for GDrive files.
"""

import logging
import os
import tempfile
from typing import List

from gdrive import db, extractor, gog

logger = logging.getLogger(__name__)

# MIME → file extension mapping for tmp file naming
MIME_EXT = {
    "wordprocessingml": ".docx",
    "application/msword": ".doc",
    "pdf": ".pdf",
    "spreadsheetml": ".xlsx",
    "ms-excel": ".xls",
    "presentationml": ".pptx",
    "ms-powerpoint": ".ppt",
}


def _get_ext(mime_type: str) -> str:
    """Return the file extension for a given MIME type."""
    for key, ext in MIME_EXT.items():
        if key in mime_type:
            return ext
    return ".bin"


def extract_pending(conn, dry_run: bool = False, limit: int = 50) -> None:
    """
    Extract content for new/modified files and save to contents table.
    Called automatically after reindex.
    """
    files = db.get_unextracted_files(conn, limit=limit)
    if not files:
        return

    prefix = "[dry-run] " if dry_run else ""
    logger.info("%sStarting content extraction for %d pending file(s)...", prefix, len(files))

    count = 0
    for row in files:
        file_id = row["id"]
        name = row["name"]
        mime = row["mime_type"] or ""
        ext = _get_ext(mime)

        if dry_run:
            logger.info("[dry-run] would download + extract: %s", name)
            count += 1
            continue

        tmp_path = None
        try:
            # Create a tmp file
            fd, tmp_path = tempfile.mkstemp(suffix=ext, prefix="gdrive_ext_")
            os.close(fd)

            # Download
            gog.drive_download(file_id, tmp_path)

            # Extract
            text = extractor.extract_text(tmp_path, mime)

            # Save (even if empty, to mark as extracted)
            db.save_content(conn, file_id, text or "")
            
            if text.strip():
                logger.info("  ✓ Extracted: %s", name)
            else:
                logger.warning("  ! No text found in: %s", name)
            
            count += 1
        except Exception as e:
            logger.error("  ✗ Failed to extract %s: %s", name, e)
        finally:
            if tmp_path and os.path.exists(tmp_path):
                os.unlink(tmp_path)

    if count > 0:
        logger.info("%sExtraction complete: %d file(s) processed.", prefix, count)
