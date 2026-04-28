"""Upload a local file to Google Drive via gog."""

import logging
import os
from typing import Optional

from gdrive import config, db, gog

logger = logging.getLogger(__name__)


def run(
    conn,
    local_path: str,
    parent: Optional[str] = None,
    name: Optional[str] = None,
    replace: Optional[str] = None,
    dry_run: Optional[bool] = None,
) -> dict:
    if dry_run is None:
        dry_run = config.is_dry_run()

    if not os.path.isfile(local_path):
        raise FileNotFoundError(f"File not found: {local_path}")

    if dry_run:
        logger.info(
            "[dry-run] would upload: %s → parent=%s name=%s replace=%s",
            local_path, parent, name, replace,
        )
        return {"dry_run": True, "local_path": local_path}

    logger.info("Uploading %s ...", local_path)
    result = gog.drive_upload(
        local_path,
        parent=parent,
        name=name,
        replace=replace,
    )

    # Index the uploaded file immediately
    file_data = result.get("file") or result  # gog may nest under "file"
    if file_data and file_data.get("id"):
        db.upsert_file(conn, file_data)
        conn.commit()
        logger.info("Indexed uploaded file: %s (%s)", file_data.get("name"), file_data.get("id"))

    return result
