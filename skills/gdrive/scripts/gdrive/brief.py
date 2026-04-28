"""
Generate AI briefs for Drive files (docx, pdf, xlsx, pptx).

Flow per file:
  1. Download via `gog drive download` to a tmp file
  2. Extract text using the format-specific submodule (brief.docx / .pdf / .xlsx / .slide)
  3. Call Gemini CLI to summarize
  4. Save the brief to the DB
  5. Delete the tmp file
"""

import logging
import os
import tempfile
from typing import Optional

from gdrive import config, db, extractor as extractors, gemini, gog

logger = logging.getLogger(__name__)

# Max chars of extracted text sent to Gemini (avoid token overload)
MAX_TEXT_CHARS = 12_000

# MIME → file extension mapping for tmp file naming
_MIME_EXT = {
    "application/vnd.openxmlformats-officedocument.wordprocessingml": ".docx",
    "application/msword": ".doc",
    "application/pdf": ".pdf",
    "application/vnd.openxmlformats-officedocument.spreadsheetml": ".xlsx",
    "application/vnd.ms-excel": ".xls",
    "application/vnd.openxmlformats-officedocument.presentationml": ".pptx",
    "application/vnd.ms-powerpoint": ".ppt",
}


def _get_ext(mime_type: str) -> str:
    for prefix, ext in _MIME_EXT.items():
        if mime_type.startswith(prefix):
            return ext
    return ".bin"


def _file_type_label(mime_type: str) -> str:
    """Human-readable file type label for the Gemini prompt."""
    if "wordprocessingml" in mime_type or "msword" in mime_type:
        return "Word document"
    if "pdf" in mime_type:
        return "PDF document"
    if "spreadsheetml" in mime_type or "ms-excel" in mime_type:
        return "Excel spreadsheet"
    if "presentationml" in mime_type or "ms-powerpoint" in mime_type:
        return "PowerPoint presentation"
    return "document"


# ── Gemini call ────────────────────────────────────────────────────────────────

def _call_gemini(file_name: str, mime_type: str, text: str) -> str:
    """Call Gemini CLI to summarize the extracted text."""
    file_type = _file_type_label(mime_type)

    prompt = f"""You are a professional document analyst. Create a concise brief for the following {file_type}.

File name: {file_name}

Required output format (follow exactly):
📄 **Summary**: (2-3 sentences describing the main content)
🎯 **Key Points**:
- (most critical bullet points, max 5)
⚠️ **Action Required**: (any items that require follow-up action; if none, write "None.")

Style: formal but concise, to the point, avoid repetition.

Document content:
{text}
"""

    return gemini.prompt(prompt)


# ── Download helper ────────────────────────────────────────────────────────────

def _download_file(file_id: str, dest_path: str) -> None:
    """Download a Drive file to dest_path via gog."""
    gog.drive_download(file_id, dest_path)


# ── Main brief runner ──────────────────────────────────────────────────────────

def _brief_one(conn, row, dry_run: bool) -> bool:
    """Process a single file. Returns True if the brief was saved successfully."""
    file_id = row["id"]
    name = row["name"]
    mime = row["mime_type"] or ""
    ext = _get_ext(mime)

    prefix = "[dry-run] " if dry_run else ""
    logger.info("%sBriefing: %s (%s)", prefix, name, file_id)

    tmp_path = None
    try:
        # 1. Reserve a tmp file path
        with tempfile.NamedTemporaryFile(
            suffix=ext, delete=False, prefix="gdrive_brief_"
        ) as tf:
            tmp_path = tf.name

        if dry_run:
            logger.info("[dry-run] would download + brief: %s", name)
            return True

        # 2. Download
        _download_file(file_id, tmp_path)

        # 3. Extract text (delegated to brief subpackage)
        text = extractors.extract_text(tmp_path, mime)
        if not text.strip():
            db.save_brief(conn, file_id, brief=None, error="No extractable text found.")
            logger.warning("  Empty / no text: %s", name)
            return False

        # 4. Truncate if too long
        if len(text) > MAX_TEXT_CHARS:
            text = text[:MAX_TEXT_CHARS] + "\n\n[... text truncated ...]"

        # 5. Call Gemini
        brief = _call_gemini(name, mime, text)

        # 6. Save to DB
        db.save_brief(conn, file_id, brief=brief)
        logger.info("  ✓ Brief saved: %s", name)
        return True

    except NotImplementedError as e:
        db.save_brief(conn, file_id, brief=None, error=f"Not implemented: {e}")
        logger.warning("  [not implemented] %s: %s", name, e)
        return False

    except Exception as e:
        db.save_brief(conn, file_id, brief=None, error=str(e))
        logger.error("  ✗ Failed to brief %s: %s", name, e)
        return False

    finally:
        if tmp_path and os.path.exists(tmp_path):
            os.unlink(tmp_path)
            logger.debug("  Tmp file deleted: %s", tmp_path)


def run(conn, dry_run: Optional[bool] = None, limit: int = 50) -> None:
    """
    Brief all files that have not been briefed yet, or that were modified
    since the last brief run. Called from CLI or cron.
    """
    if dry_run is None:
        dry_run = config.is_dry_run()

    since = db.get_last_brief_run(conn)
    prefix = "[dry-run] " if dry_run else ""
    logger.info(
        "%sBrief run started (since=%s, limit=%d)",
        prefix, since or "beginning", limit
    )

    rows = db.get_unbriefed_files(conn, since=since, limit=limit)
    if not rows:
        logger.info("%sNo new files to brief.", prefix)
        return

    logger.info("%sFound %d file(s) to brief.", prefix, len(rows))
    ok = fail = 0
    for row in rows:
        success = _brief_one(conn, row, dry_run)
        if success:
            ok += 1
        else:
            fail += 1

    prefix = "[dry-run] " if dry_run else ""
    logger.info("%sBrief run complete: %d succeeded, %d failed.", prefix, ok, fail)