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
import time
from typing import Optional

from gdrive import config, db, extractor as extractors, gemini, gog

logger = logging.getLogger(__name__)

# Max chars of extracted text sent to Gemini (avoid token overload)
MAX_TEXT_CHARS = 12_000

# MIME → file extension mapping for tmp file naming
_MIME_EXT = {
    "wordprocessingml": ".docx",
    "application/msword": ".doc",
    "pdf": ".pdf",
    "spreadsheetml": ".xlsx",
    "ms-excel": ".xls",
    "presentationml": ".pptx",
    "ms-powerpoint": ".ppt",
}


def _get_ext(mime_type: str) -> str:
    for key, ext in _MIME_EXT.items():
        if key in mime_type:
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


def _call_gemini_with_retry(
    file_name: str, mime_type: str, text: str, max_retries: int = 3
) -> str:
    """Call Gemini with simple exponential backoff retry logic."""
    last_err = None
    for attempt in range(max_retries):
        try:
            return _call_gemini(file_name, mime_type, text)
        except Exception as e:
            last_err = e
            wait = 2 ** (attempt + 1)
            logger.warning(
                "  Gemini attempt %d failed: %s. Retrying in %ds...",
                attempt + 1, e, wait
            )
            time.sleep(wait)
    
    raise last_err or RuntimeError("Gemini call failed after retries")


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

    # 1. Check cache (issue #16)
    content_record = db.get_content_record(conn, file_id)
    text = None
    
    if content_record:
        extracted_at = content_record["extracted_at"]
        modified_at = row["modified_at"]
        if modified_at <= extracted_at:
            logger.info("  ✓ Using cached content (last extracted: %s)", extracted_at)
            text = content_record["content"]

    tmp_path = None
    try:
        if text is None:
            # Reserve a tmp file path
            fd, tmp_path = tempfile.mkstemp(suffix=ext, prefix="gdrive_brief_")
            os.close(fd)

            if dry_run:
                logger.info("[dry-run] would download + extract: %s", name)
                # For dry-run, we don't have text, but we skip Gemini anyway
                return True

            # 2. Download
            _download_file(file_id, tmp_path)

            # 3. Extract text
            text = extractors.extract_text(tmp_path, mime)
            if not text.strip():
                db.save_brief(conn, file_id, brief=None, error="No extractable text found.")
                logger.warning("  Empty / no text: %s", name)
                return False

            # 4. Save to cache (issue #16)
            db.save_content(conn, file_id, text)
            logger.debug("  Content cached for: %s", name)

        if dry_run:
            logger.info("[dry-run] would call Gemini to summarize: %s", name)
            return True

        # 5. Truncate if too long
        if len(text) > MAX_TEXT_CHARS:
            text = text[:MAX_TEXT_CHARS] + "\n\n[... text truncated ...]"

        # 6. Call Gemini
        brief = _call_gemini_with_retry(name, mime, text)

        # 7. Save brief to DB
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
    delay = config.get_brief_delay()

    for i, row in enumerate(rows):
        if i > 0 and delay > 0:
            time.sleep(delay)

        success = _brief_one(conn, row, dry_run)
        if success:
            ok += 1
        else:
            fail += 1

    prefix = "[dry-run] " if dry_run else ""
    logger.info("%sBrief run complete: %d succeeded, %d failed.", prefix, ok, fail)
