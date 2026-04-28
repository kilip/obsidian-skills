"""Subprocess wrapper for the gog CLI."""

import json
import logging
import os
import shutil
import subprocess
import time
from typing import Any, Dict, Iterator, List, Optional

from gdrive import config

logger = logging.getLogger(__name__)

_GOG_SEARCH_LOCATIONS = [
    "/usr/local/bin/gog",
    "/usr/bin/gog",
    "/opt/homebrew/bin/gog",
    os.path.expanduser("~/.local/bin/gog"),
]

MAX_RETRIES = 3



def _find_gog() -> str:
    bin_name = config.get_gog_bin()
    # 1. Check PATH
    found = shutil.which(bin_name)
    if found:
        return found
    # 2. Check common Linux locations
    for loc in _GOG_SEARCH_LOCATIONS:
        if os.path.isfile(loc) and os.access(loc, os.X_OK):
            return loc
    raise RuntimeError(
        f"gog binary not found (looked in PATH and common locations). "
        f"Install it from https://gogcli.sh or set OS_GDRIVE_GOG_BIN to its full path."
    )


def _run(args: List[str], capture: bool = True) -> subprocess.CompletedProcess:
    """Run gog with the given args. Raises on non-zero exit."""
    gog = _find_gog()
    account = config.get_account()
    cmd = [gog, "--account", account, "--no-input"] + args
    logger.debug("Running: %s", " ".join(cmd))

    for attempt in range(MAX_RETRIES):
        result = subprocess.run(
            cmd,
            capture_output=capture,
            text=True,
        )
        if result.returncode == 0:
            return result

        stderr = result.stderr.strip() if result.stderr else "(no stderr)"
        if "429" in stderr or "rateLimitExceeded" in stderr:
            delay = 2**attempt  # 1s, 2s, 4s
            logger.warning(
                "Rate limited. Retrying in %ds (attempt %d/%d)...",
                delay,
                attempt + 1,
                MAX_RETRIES,
            )
            time.sleep(delay)
            continue

        raise RuntimeError(
            f"gog exited with code {result.returncode}.\n"
            f"Command: {' '.join(cmd)}\n"
            f"Stderr: {stderr}"
        )

    raise RuntimeError("Max retries exceeded due to rate limiting.")


def drive_search_page(
    query: str, page_token: Optional[str] = None
) -> Dict[str, Any]:
    """Run `gog drive search` for one page, return parsed JSON dict."""
    args = ["drive", "search", query, "--json"]
    if page_token:
        args += ["--page-token", page_token]
    result = _run(args)
    return json.loads(result.stdout)


def drive_search_all(query: str) -> Iterator[Dict[str, Any]]:
    """Paginate through all results for a search query, yielding each file dict."""
    page_token: Optional[str] = None
    page_num = 0
    while True:
        page_num += 1
        logger.debug("Fetching page %d (token=%s)", page_num, page_token)
        data = drive_search_page(query, page_token)
        files = data.get("files", [])
        for f in files:
            yield f
        page_token = data.get("nextPageToken")
        if not page_token:
            break
        time.sleep(config.get_page_delay())  # pause between pages


def drive_download(file_id: str, output_path: str) -> None:
    """
    Download a Drive file by ID to output_path via `gog drive download`.
    Raises RuntimeError if gog exits with a non-zero code.
    """
    args = ["drive", "download", file_id, "--output", output_path]
    _run(args)


def drive_upload(
    local_path: str,
    parent: Optional[str] = None,
    name: Optional[str] = None,
    replace: Optional[str] = None,
    dry_run: bool = False,
) -> Dict[str, Any]:
    """Upload a file to Drive. Returns parsed JSON response."""
    args = ["drive", "upload", local_path, "--json"]
    if parent:
        args += ["--parent", parent]
    if name:
        args += ["--name", name]
    if replace:
        args += ["--replace", replace]
    if dry_run:
        args += ["--dry-run"]
    result = _run(args)
    return json.loads(result.stdout)
