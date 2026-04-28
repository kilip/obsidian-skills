"""Recursively index My Drive into SQLite."""

import logging
from typing import Optional

from gdrive import config, db, gog

logger = logging.getLogger(__name__)

# Drive API query that returns all non-trashed files in My Drive
_QUERY = "trashed = false"


def run(conn, dry_run: Optional[bool] = None) -> None:
    if dry_run is None:
        dry_run = config.is_dry_run()

    run_id = db.start_run(conn) if not dry_run else -1
    added = updated = 0

    logger.info("Starting reindex (dry_run=%s) ...", dry_run)

    try:
        for f in gog.drive_search_all(_QUERY):
            action = "DRY-RUN"
            if not dry_run:
                action = db.upsert_file(conn, f)
                if action == "added":
                    added += 1
                else:
                    updated += 1
                if (added + updated) % 100 == 0:
                    conn.commit()
                    logger.info("  ... %d added, %d updated so far", added, updated)
            else:
                logger.info("[dry-run] would upsert: %s (%s)", f.get("name"), f.get("id"))

        if not dry_run:
            conn.commit()
            db.finish_run(conn, run_id, added, updated, deleted=0, status="ok")
            logger.info(
                "Reindex complete: %d added, %d updated.", added, updated
            )
        else:
            logger.info("Dry-run complete — no writes performed.")

    except Exception as exc:
        logger.error("Reindex failed: %s", exc)
        if not dry_run and run_id != -1:
            db.finish_run(
                conn, run_id, added, updated, deleted=0,
                status="error", error_msg=str(exc)
            )
        raise
