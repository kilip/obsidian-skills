"""
Thin re-export of gemini_cli.

All logic lives in skills/gemini-cli/gemini_cli.py.
This shim exists for backward compatibility within the gdrive package.

Usage (internal):
    from gdrive import gemini
    result = gemini.prompt("Summarize this: ...")

To use directly:
    from gemini_cli import prompt
"""

from gemini_cli import (  # noqa: F401
    DEFAULT_BIN,
    DEFAULT_MODEL,
    get_bin,
    get_model,
    get_timeout,
    prompt,
)

__all__ = ["prompt", "get_model", "get_bin", "get_timeout", "DEFAULT_MODEL", "DEFAULT_BIN"]
