"""Load configuration from environment variables (OS_GDRIVE_ prefix)."""

import os
from pathlib import Path


def _expand(val: str) -> str:
    return str(Path(val).expanduser())


def get_db_path() -> str:
    raw = os.environ.get("OS_GDRIVE_DB_PATH", "~/.gdrive/index.db")
    path = _expand(raw)
    Path(path).parent.mkdir(parents=True, exist_ok=True)
    return path


def get_gog_bin() -> str:
    return os.environ.get("OS_GDRIVE_GOG_BIN", "gog")


def get_log_path() -> str:
    raw = os.environ.get("OS_GDRIVE_LOG_PATH", "~/.gdrive/gdrive.log")
    path = _expand(raw)
    Path(path).parent.mkdir(parents=True, exist_ok=True)
    return path


def get_account() -> str:
    account = os.environ.get("GOG_ACCOUNT", "")
    if not account:
        raise RuntimeError(
            "GOG_ACCOUNT env var is not set. "
            "Set it to your Google account email, e.g.:\n"
            "  export GOG_ACCOUNT=you@gmail.com"
        )
    return account


def is_dry_run() -> bool:
    return os.environ.get("OS_GDRIVE_DRY_RUN", "0").strip() in ("1", "true", "yes")


def get_gemini_model() -> str:
    return os.environ.get("OS_GEMINI_MODEL", "gemini-2.5-flash-lite").strip()


def get_gemini_bin() -> str:
    return os.environ.get("OS_GEMINI_BIN", "gemini").strip()


def get_page_delay() -> float:
    return float(os.environ.get("OS_GDRIVE_PAGE_DELAY", "0.1"))

