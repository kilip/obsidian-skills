"""Recursively index My Drive into SQLite."""

import logging
from typing import Optional

from gdrive import config, db, gog

logger = logging.getLogger(__name__)

# Drive API query that returns all non-trashed files in My Drive
_QUERY_FULL = "trashed = false"
_QUERY_INCREMENTAL = "trashed = false and modifiedTime > '{since}'"
_QUERY_TRASHED = "trashed = true"


def run(
    conn,
    dry_run: Optional[bool] = None,
    limit: Optional[int] = None,
    incremental: bool = True,
) -> None:
    if dry_run is None:
        dry_run = config.is_dry_run()

    since = db.get_last_successful_run(conn) if incremental else None
    query = _QUERY_INCREMENTAL.format(since=since) if since else _QUERY_FULL

    run_id = db.start_run(conn, query=query) if not dry_run else -1
    added = updated = deleted = 0

    # Resume logic
    resume_token = None
    resumable = db.get_resumable_run(conn, query)
    if resumable:
        resume_token = resumable["last_page_token"]
        logger.info("Resuming from previous failed run (ID %d, token=%s)", resumable["id"], resume_token)

    prefix = "[dry-run] " if dry_run else ""
    logger.info(
        "%sStarting reindex (mode=%s, limit=%s, resume=%s) ...",
        prefix,
        "incremental" if since else "full",
        limit,
        bool(resume_token),
    )
    if since:
        logger.info("%sFetching files modified since %s", prefix, since)

    try:
        count = 0
        current_token = resume_token
        for f, next_token in gog.drive_search_all(query, resume_token=resume_token):
            if limit and count >= limit:
                logger.info("%sLimit reached (%d), stopping.", prefix, limit)
                break

            action = "DRY-RUN"
            if not dry_run:
                action = db.upsert_file(conn, f)
                if action == "added":
                    added += 1
                else:
                    updated += 1
                
                # Update progress in DB
                if next_token != current_token:
                    db.save_page_token(conn, run_id, next_token)
                    current_token = next_token

                if (added + updated) % 100 == 0:
                    conn.commit()
                    logger.info("  ... %d added, %d updated so far", added, updated)
            else:
                logger.info("[dry-run] would upsert: %s (%s)", f.get("name"), f.get("id"))
            
            count += 1

        deleted = _mark_trashed(conn, dry_run)

        if not dry_run:
            conn.commit()
            db.finish_run(
                conn,
                run_id,
                scanned=count,
                added=added,
                updated=updated,
                deleted=deleted,
                status="ok",
            )
            logger.info(
                "Reindex complete: %d scanned, %d added, %d updated, %d trashed.",
                count, added, updated, deleted
            )
        else:
            logger.info("[dry-run] complete — no writes performed.")

    except Exception as exc:
        logger.error("Reindex failed: %s", exc)
        if not dry_run and run_id != -1:
            db.finish_run(
                conn, run_id, scanned=count, added=added, updated=updated, deleted=deleted,
                status="error", error_msg=str(exc)
            )
        raise


def _mark_trashed(conn, dry_run: bool) -> int:
    """Find trashed files in Drive and mark them in DB."""
    count = 0
    prefix = "[dry-run] " if dry_run else ""
    logger.info("%sChecking for trashed files in Drive...", prefix)
    for f, _ in gog.drive_search_all(_QUERY_TRASHED):
        file_id = f["id"]
        # Only update if it exists in our DB and is not already marked trashed
        existing = conn.execute(
            "SELECT id FROM files WHERE id = ? AND is_trashed = 0", (file_id,)
        ).fetchone()

        if existing:
            if not dry_run:
                db.mark_as_trashed(conn, file_id)
                count += 1
            else:
                logger.info("[dry-run] would mark trashed: %s (%s)", f.get("name"), file_id)
                count += 1

    if not dry_run and count > 0:
        conn.commit()
    
    if count > 0:
        prefix = "[dry-run] " if dry_run else ""
        logger.info("%sDetected %d trashed files.", prefix, count)
    return count
