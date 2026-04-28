#!/usr/bin/env python3
"""
gemini_cli.py — Reusable Gemini CLI wrapper.

Sends a prompt to the Gemini model via the `gemini` binary and prints the response.

Usage:
    uv run gemini_cli.py --prompt "Summarize this: ..."
    uv run gemini_cli.py --prompt-file ./prompt.txt
    echo "Translate to French: Hello" | uv run gemini_cli.py
    uv run gemini_cli.py --prompt "..." --model gemini-2.5-pro

As a module:
    from gemini_cli import prompt
    result = prompt("Summarize this: ...")
"""

import os
import subprocess
import sys
from pathlib import Path
from typing import Optional

# ── Configuration ──────────────────────────────────────────────────────────────

DEFAULT_MODEL = "gemini-2.5-flash-lite"
DEFAULT_BIN = "gemini"


def get_model() -> str:
    """Return the Gemini model from env, falling back to DEFAULT_MODEL."""
    return os.environ.get("OS_GEMINI_MODEL", DEFAULT_MODEL).strip()


def get_bin() -> str:
    """Return the Gemini CLI binary from env, falling back to 'gemini'."""
    return os.environ.get("OS_GEMINI_BIN", DEFAULT_BIN).strip()


def get_timeout() -> Optional[int]:
    """Return subprocess timeout in seconds from OS_GEMINI_TIMEOUT, or None."""
    raw = os.environ.get("OS_GEMINI_TIMEOUT", "").strip()
    if raw:
        try:
            return int(raw)
        except ValueError:
            print(f"[warn] OS_GEMINI_TIMEOUT={raw!r} is not an integer, ignoring.", file=sys.stderr)
    return None


# ── Core function ──────────────────────────────────────────────────────────────

def prompt(
    text: str,
    model: Optional[str] = None,
    timeout: Optional[int] = None,
) -> str:
    """
    Send a prompt to the Gemini CLI and return the response as a string.

    Args:
        text:    The prompt string to send.
        model:   Model name override. Defaults to OS_GEMINI_MODEL or gemini-2.5-flash-lite.
        timeout: Subprocess timeout in seconds. Defaults to OS_GEMINI_TIMEOUT or None.

    Returns:
        The Gemini response as a stripped string.

    Raises:
        ValueError: if `text` is empty.
        FileNotFoundError: if the `gemini` binary is not found.
        RuntimeError: if Gemini CLI exits with a non-zero return code.
        subprocess.TimeoutExpired: if the call exceeds the timeout.
    """
    if not text or not text.strip():
        raise ValueError("Prompt cannot be empty.")

    _model = model or get_model()
    _bin = get_bin()
    _timeout = timeout if timeout is not None else get_timeout()

    result = subprocess.run(
        [_bin, "--model", _model, "--prompt", text],
        capture_output=True,
        text=True,
        timeout=_timeout,
    )

    if result.returncode == 0:
        return result.stdout.strip()

    raise RuntimeError(
        f"Gemini CLI error (exit {result.returncode}): {result.stderr.strip()}"
    )


# ── CLI entry point ────────────────────────────────────────────────────────────

def _read_prompt(args) -> Optional[str]:
    """Resolve prompt from --prompt, --prompt-file, or stdin (in priority order)."""
    import argparse

    if args.prompt:
        return args.prompt

    if args.prompt_file:
        path = Path(args.prompt_file)
        if not path.exists():
            print(f"ERROR: Prompt file not found: {path}", file=sys.stderr)
            sys.exit(1)
        return path.read_text(encoding="utf-8").strip()

    if not sys.stdin.isatty():
        return sys.stdin.read().strip()

    return None


def main() -> None:
    import argparse

    parser = argparse.ArgumentParser(
        prog="gemini_cli",
        description="Send a prompt to Gemini CLI and print the response.",
    )
    parser.add_argument(
        "--prompt", "-p",
        help="Prompt text (inline string).",
    )
    parser.add_argument(
        "--prompt-file", "-f",
        metavar="PATH",
        help="Read prompt from a file.",
    )
    parser.add_argument(
        "--model", "-m",
        default=None,
        help=f"Gemini model to use (default: {DEFAULT_MODEL} or OS_GEMINI_MODEL).",
    )
    args = parser.parse_args()

    text = _read_prompt(args)
    if not text:
        print("ERROR: No prompt provided. Use --prompt, --prompt-file, or stdin.", file=sys.stderr)
        sys.exit(1)

    try:
        response = prompt(text, model=args.model)
        print(response)
    except FileNotFoundError:
        print(
            f"ERROR: Gemini binary '{get_bin()}' not found in PATH.\n"
            f"Install it or set OS_GEMINI_BIN to the full path.",
            file=sys.stderr,
        )
        sys.exit(1)
    except subprocess.TimeoutExpired:
        print("ERROR: Gemini CLI call timed out.", file=sys.stderr)
        sys.exit(1)
    except (RuntimeError, ValueError) as e:
        print(f"ERROR: {e}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
