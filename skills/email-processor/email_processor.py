#!/usr/bin/env python3
# /// script
# dependencies = []
# ///
"""
email_processor.py — Obsidian Email Processor Skill.

Reads reviewed email notes from {OV_INBOX_PATH}/Emails/, executes checked
actions (Reply, Forward, Archive), and deletes files that have only [x] Read.

Usage:
    cd skills/email-processor
    export OV_INBOX_PATH="/path/to/obsidian/inbox"
    uv run email_processor.py
"""

import os
import re
import sys
import shutil
import subprocess
from datetime import datetime
from pathlib import Path
from typing import Optional

# --- Configuration ---
OV_INBOX_PATH_ENV = os.environ.get("OV_INBOX_PATH", "")
GOG_BIN = os.environ.get("GOG_BIN", "gog")

# Globals (resolved after validate_env)
INBOX_PATH: Path = Path(".")
EMAILS_DIR: Path = Path(".")
ARCHIVE_DIR: Path = Path(".")

PLACEHOLDER_REPLY = "*(isi di sini → AI agent akan otomatis kirim)*"


# ---------------------------------------------------------------------------
# Env Validation
# ---------------------------------------------------------------------------

def validate_env() -> None:
    global INBOX_PATH, EMAILS_DIR, ARCHIVE_DIR

    if not OV_INBOX_PATH_ENV:
        print("[ERROR] OV_INBOX_PATH is not set.", file=sys.stderr)
        sys.exit(1)

    INBOX_PATH = Path(OV_INBOX_PATH_ENV)
    if not INBOX_PATH.exists():
        print(f"[ERROR] OV_INBOX_PATH does not exist: {INBOX_PATH}", file=sys.stderr)
        sys.exit(1)

    EMAILS_DIR = INBOX_PATH / "Emails"
    if not EMAILS_DIR.exists():
        print(f"[ERROR] Emails dir not found: {EMAILS_DIR}", file=sys.stderr)
        sys.exit(1)

    # Archive dir lives next to inbox: {OV_INBOX_PATH}/../05 - Archive/Emails
    ARCHIVE_DIR = INBOX_PATH.parent / "05 - Archive" / "Emails"

    # Verify gog binary
    try:
        subprocess.run(
            [GOG_BIN, "--version"],
            capture_output=True, check=True, shell=True
        )
    except Exception:
        print(f"[ERROR] '{GOG_BIN}' CLI not found or not executable.", file=sys.stderr)
        sys.exit(1)


# ---------------------------------------------------------------------------
# Frontmatter helpers
# ---------------------------------------------------------------------------

def parse_frontmatter(text: str) -> dict:
    """Parse YAML-like frontmatter from markdown text. Returns dict."""
    fm: dict = {}
    if not text.startswith("---"):
        return fm
    end = text.find("---", 3)
    if end == -1:
        return fm
    block = text[3:end].strip()
    for line in block.splitlines():
        if ":" in line:
            key, _, val = line.partition(":")
            fm[key.strip()] = val.strip()
    return fm


def update_frontmatter_status(filepath: Path, new_status: str) -> None:
    """Updates the 'status' field in frontmatter in-place."""
    text = filepath.read_text(encoding="utf-8")
    # Replace status: <anything> inside the frontmatter block
    updated = re.sub(
        r"(^---.*?^status:\s*)(\S+)",
        lambda m: m.group(1) + new_status,
        text,
        count=1,
        flags=re.MULTILINE | re.DOTALL,
    )
    filepath.write_text(updated, encoding="utf-8")


# ---------------------------------------------------------------------------
# Action Parsing
# ---------------------------------------------------------------------------

def parse_actions(filepath: Path) -> dict:
    """
    Parse the '## # Action' section of an email note.

    Returns:
        {
            "read":    bool,
            "reply":   bool,
            "archive": bool,
            "forward": str | None,
        }
    """
    actions: dict = {"read": False, "reply": False, "archive": False, "forward": None}
    text = filepath.read_text(encoding="utf-8")

    in_action = False
    for line in text.splitlines():
        stripped = line.strip()
        # Enter action section
        if re.match(r"^##\s+#\s+Action", stripped, re.IGNORECASE):
            in_action = True
            continue
        # Leave action section on any other heading
        if in_action and stripped.startswith("#"):
            break
        if in_action:
            # Checked: - [x] ...
            checked = re.match(r"^-\s+\[x\]\s+(.+)", stripped, re.IGNORECASE)
            if checked:
                label = checked.group(1).strip()
                label_lower = label.lower()
                if label_lower.startswith("read"):
                    actions["read"] = True
                elif label_lower.startswith("reply"):
                    actions["reply"] = True
                elif label_lower.startswith("archive"):
                    actions["archive"] = True
                elif label_lower.startswith("forward"):
                    # Extract target after →
                    after_arrow = re.split(r"→|->", label, maxsplit=1)
                    target = after_arrow[1].strip() if len(after_arrow) > 1 else ""
                    actions["forward"] = target if target else None

    return actions


# ---------------------------------------------------------------------------
# Section parsing
# ---------------------------------------------------------------------------

def parse_section(filepath: Path, section_heading: str) -> str:
    """Returns the text content of a given markdown section (until next ##)."""
    text = filepath.read_text(encoding="utf-8")
    pattern = rf"^##\s+{re.escape(section_heading)}\s*$"
    lines = text.splitlines()
    in_section = False
    content_lines = []

    for line in lines:
        if re.match(pattern, line.strip(), re.IGNORECASE):
            in_section = True
            continue
        if in_section:
            if line.strip().startswith("##"):
                break
            content_lines.append(line)

    return "\n".join(content_lines).strip()


# ---------------------------------------------------------------------------
# gog command runner (sync, no timeout)
# ---------------------------------------------------------------------------

def run_gog(args: list[str]) -> None:
    """Run a gog command synchronously. Raises on failure."""
    cmd = [GOG_BIN] + args
    cmd_str = " ".join(
        f'"{a}"' if (" " in a or "\n" in a or "→" in a) else a for a in cmd
    )
    result = subprocess.run(cmd_str, shell=True, text=True, encoding="utf-8")
    if result.returncode != 0:
        raise RuntimeError(f"gog command failed (exit {result.returncode}): {cmd_str}")


def mark_as_read(gmail_id: str, account: str) -> None:
    """Mark a Gmail message as read. Called after all actions are completed."""
    cmd = f'"{GOG_BIN}" gmail mark-read "{gmail_id}" -a "{account}" --no-input'
    result = subprocess.run(cmd, capture_output=True, text=True, encoding="utf-8", shell=True)
    if result.returncode == 0:
        print(f"    [READ] Marked {gmail_id} as read in Gmail.")
    else:
        print(f"    [WARN] Could not mark {gmail_id} as read. stderr: {result.stderr.strip()}", file=sys.stderr)


# ---------------------------------------------------------------------------
# Action Executors
# ---------------------------------------------------------------------------

def extract_gmail_id(filepath: Path) -> str:
    """Extract Gmail ID from filename: YYYY-MM-DD-{gmail_id}.md"""
    match = re.search(r"\d{4}-\d{2}-\d{2}-([a-f0-9]+)\.md", filepath.name)
    if not match:
        raise ValueError(f"Cannot extract Gmail ID from filename: {filepath.name}")
    return match.group(1)


def extract_account(filepath: Path) -> str:
    """Extract account (Gmail address) from frontmatter field 'to'."""
    text = filepath.read_text(encoding="utf-8")
    fm = parse_frontmatter(text)
    to_field = fm.get("to", "")
    # Extract email from "Name <email@domain.com>" or plain "email@domain.com"
    email_match = re.search(r"<([^>]+)>", to_field)
    if email_match:
        return email_match.group(1).strip()
    return to_field.strip()


def execute_reply(filepath: Path) -> None:
    """Send reply via gog gmail send --reply-to-message-id."""
    gmail_id = extract_gmail_id(filepath)
    account = extract_account(filepath)
    reply_body = parse_section(filepath, "Reply")

    if not reply_body or reply_body == PLACEHOLDER_REPLY:
        print(f"    [WARN] Reply section empty — skipping send.")
        return

    # Extract sender from frontmatter to use as --to
    text = filepath.read_text(encoding="utf-8")
    fm = parse_frontmatter(text)
    sender = fm.get("sender", "")
    # Extract email from "Name <email>" or plain email
    sender_match = re.search(r"<([^>]+)>", sender)
    reply_to = sender_match.group(1).strip() if sender_match else sender.strip()

    # Extract subject from frontmatter for reply subject
    subject = fm.get("subject", "Re: (no subject)")
    reply_subject = subject if subject.lower().startswith("re:") else f"Re: {subject}"

    print(f"    [REPLY] Sending reply to {reply_to} via {account}...")
    run_gog([
        "gmail", "send",
        "-a", account,
        "--reply-to-message-id", gmail_id,
        "--to", reply_to,
        "--subject", reply_subject,
        "--body", reply_body,
        "--no-input",
    ])
    print(f"    [REPLY] OK Sent.")


def execute_forward(filepath: Path, target: str) -> None:
    """Forward email via gog gmail forward."""
    gmail_id = extract_gmail_id(filepath)
    account = extract_account(filepath)

    print(f"    [FORWARD] Forwarding to {target} via {account}...")
    run_gog(["gmail", "forward", "--to", target, gmail_id, "-a", account, "--no-input"])
    print(f"    [FORWARD] OK Sent.")


def move_to_archive(filepath: Path) -> None:
    """Move file to archive dir, appending timestamp if name conflicts."""
    ARCHIVE_DIR.mkdir(parents=True, exist_ok=True)
    dest = ARCHIVE_DIR / filepath.name
    if dest.exists():
        ts = datetime.now().strftime("%Y%m%d%H%M%S")
        dest = ARCHIVE_DIR / f"{filepath.stem}-{ts}{filepath.suffix}"
    shutil.move(str(filepath), str(dest))
    print(f"    [ARCHIVE] Moved to {dest}")


# ---------------------------------------------------------------------------
# Core processor
# ---------------------------------------------------------------------------

def process_email(filepath: Path) -> None:
    print(f"\nProcessing: {filepath.name}")

    # --- Step 1: Check status ---
    text = filepath.read_text(encoding="utf-8")
    fm = parse_frontmatter(text)
    if fm.get("status", "").lower() == "processed":
        print(f"  [SKIP] Already processed.")
        return

    # --- Step 2: Parse actions ---
    actions = parse_actions(filepath)
    read = actions["read"]
    reply = actions["reply"]
    archive = actions["archive"]
    forward = actions["forward"]

    any_checked = read or reply or archive or (forward is not None)

    # --- Step 3: No action at all → skip ---
    if not any_checked:
        print(f"  [SKIP] No action checked — not yet reviewed.")
        return

    # Resolve Gmail ID and account once — needed for mark-read
    try:
        gmail_id = extract_gmail_id(filepath)
        account = extract_account(filepath)
    except (ValueError, Exception) as e:
        print(f"  [ERROR] Cannot resolve Gmail ID/account: {e}", file=sys.stderr)
        return

    # --- Step 4: Only [x] Read → delete permanently then mark read ---
    if read and not reply and not archive and forward is None:
        filepath.unlink()
        print(f"  [DELETE] Only Read checked. Deleted permanently.")
        mark_as_read(gmail_id, account)
        return

    # --- Step 5: Execute reply/forward (STOP-ON-FAIL blocks archive) ---
    try:
        if reply:
            execute_reply(filepath)

        if forward is not None:
            execute_forward(filepath, forward)

    except (RuntimeError, ValueError) as e:
        print(f"  [ERROR] {e}", file=sys.stderr)
        print(f"  [ABORT] Action failed — file stays in inbox, archive cancelled.")
        return

    # --- Step 6: Archive if [x] Archive ---
    if archive:
        update_frontmatter_status(filepath, "Processed")
        move_to_archive(filepath)
    else:
        print(f"  [DONE] Actions executed. No [x] Archive — file stays in inbox.")

    # --- Step 7: Mark as read in Gmail (after all actions succeed) ---
    mark_as_read(gmail_id, account)


# ---------------------------------------------------------------------------
# Entrypoint
# ---------------------------------------------------------------------------

def get_inbox_files() -> list[Path]:
    return sorted(EMAILS_DIR.glob("*.md"))


def main() -> None:
    validate_env()
    files = get_inbox_files()
    print(f"Email Processor — {len(files)} file(s) found in {EMAILS_DIR}\n")

    processed = deleted = skipped = 0
    for f in files:
        before_exists = f.exists()
        process_email(f)
        if not f.exists() and before_exists:
            deleted += 1
        elif not (EMAILS_DIR / f.name).exists() and before_exists:
            processed += 1
        else:
            skipped += 1

    print(f"\nDone. {processed} archived, {deleted} deleted, {skipped} skipped/stayed.")
    sys.exit(0)


if __name__ == "__main__":
    main()
