---
name: email-processor
description: >
  Use this skill whenever the user wants to process email, proses email,
  eksekusi email, archive email, reply email, forward email, kirim balasan,
  bersihkan inbox, or execute pending email actions in Obsidian. This skill
  reads reviewed email notes in the Obsidian Inbox, executes the checked
  action checkboxes (Archive, Reply, Forward), moves processed notes to the
  archive folder, and permanently deletes notes that are marked read-only.
allowed-tools:
  - "Bash"
  - "Read"
  - "Write"
---

# SKILL: Email Processor

## Overview
> Processes reviewed email notes in `00 - Inbox/Emails/`. Reads the action checklist in each note, executes checked actions (Archive, Reply, Forward), then moves the note to `05 - Archive/Emails/`. If only `[x] Read` is checked and all other actions are empty, the file is permanently deleted. If nothing is checked, the file is skipped.

## Prerequisites

- `gog` — Google OAuth CLI tool (for reply/forward via Gmail)
- `OS_INBOX_PATH` — path to the Obsidian Inbox folder

## Usage

### How to invoke this skill
Run this skill after the user has finished reviewing emails in `00 - Inbox/Emails/` and has checked the desired actions.

```bash
cd skills/email-processor
export OS_INBOX_PATH="/path/to/obsidian/inbox"
uv run email_processor.py
```

### Input
- `.md` files in `{OS_INBOX_PATH}/Emails/`
- Files must follow the `email-reader/template/Email.md` format
- Files with frontmatter `status: Processed` will be skipped (idempotent)

### Output
- Files with `[x] Archive` → executed → moved to `{OS_INBOX_PATH}/../05 - Archive/Emails/`
- Files with `[x] Reply` or `[x] Forward` → executed → **not** auto-moved unless `[x] Archive` is also checked
- Files with only `[x] Read` checked → permanently deleted
- Files with no actions checked → skipped
- Frontmatter `status` is updated to `Processed` before moving

## Configuration

| Variable | Required | Default | Description |
|---|---|---|---|
| `OS_INBOX_PATH` | ✅ | — | Absolute path to the Obsidian Inbox folder |
| `OS_GOG_BIN` | ❌ | `gog` | Path to `gog` binary |
| `OS_GEMINI_MODEL` | ❌ | `gemini-2.5-flash-lite` | Gemini model (for reply assistance) |

## Script Logic: `email_processor.py`

### 1. Entrypoint & Validation
```
main()
  └── validate_env()         # check OS_INBOX_PATH exists, gog binary available
  └── get_inbox_files()      # glob all *.md in {OS_INBOX_PATH}/Emails/
  └── for each file → process_email(file)
```

### 2. `process_email(filepath)`
```
1. parse_frontmatter(filepath)
   - If status == "Processed" → skip (log: already processed)

2. parse_actions(filepath)
   - Read section "## # Action"
   - Detect checked [x] checkboxes:
     * read      → bool
     * reply     → bool
     * archive   → bool
     * forward   → str (text after "→")

3. If NO actions are checked (all false/None):
   - skip file (not yet reviewed)
   - return

4. If ONLY `read` is checked (all others false/None):
   - os.remove(filepath)
   - log: "Deleted {filename} (read only, no action)"
   - return

5. Execute actions (order: reply → forward):
   - execute_reply(filepath)                  # only if reply == True
   - execute_forward(filepath, forward_target) # only if forward != None

6. If `archive` == True:
   - Update frontmatter status → "Processed"
   - move_to_archive(filepath)
     - Move to {OS_INBOX_PATH}/../05 - Archive/Emails/{filename}
     - If file already exists in archive → append timestamp suffix
```

### 3. `parse_actions(filepath) → dict`
```
Read file line by line, find section "## # Action"
Parse lines matching pattern (case-insensitive): "- [x] <action>"

Valid action names (per Email.md template):
  - "Read"    → read: True/False
  - "Reply"   → reply: True/False
  - "Archive" → archive: True/False
  - "Forward" → forward: str (text after "→") or None
                  - Line: "- [x] Forward → email@example.com" → forward = "email@example.com"
                  - Line: "- [x] Forward → " (empty) → forward = None (skip, do not execute)

Return:
{
  "read": True/False,
  "reply": True/False,
  "archive": True/False,
  "forward": "email@example.com" or None
}
```

### 4. `execute_reply(filepath)`
```
1. Extract Gmail ID from filename: YYYY-MM-DD-{gmail_id}.md
2. Get `account` from frontmatter field `to` (original recipient = our Gmail account)
3. Read content of "## Reply" section from file
4. If Reply section is empty or contains only the placeholder
   "*(fill in here → AI agent will auto-send)*":
   - log warning: "Reply section empty, skipping send"
   - return (do not fail the entire process)
5. Run (sync, wait): gog gmail reply {gmail_id} -a {account} --body "{reply_content}"
6. On failure → raise Exception (STOP-ON-FAIL: file stays in inbox, archive cancelled)
```

### 5. `execute_forward(filepath, target)`
```
1. Extract Gmail ID from filename: YYYY-MM-DD-{gmail_id}.md
2. Get `account` from frontmatter field `to`
3. Run (sync, wait): gog gmail forward {gmail_id} -a {account} --to "{target}"
4. On failure → raise Exception (STOP-ON-FAIL: file stays in inbox, archive cancelled)
```

### 6. `move_to_archive(filepath)`
```
1. Ensure {OS_INBOX_PATH}/../05 - Archive/Emails/ exists (mkdir if needed)
2. shutil.move(filepath, archive_dir / filepath.name)
```

## Behavior Rules
- **STOP-ON-FAIL:** If reply or forward fails (raises Exception), **cancel all remaining actions** including archive — file stays in inbox, continue to next file.
- **Idempotent:** Files with `status: Processed` in frontmatter → skip.
- **Sequential:** Process one file at a time, no parallelism.
- **Sync execution:** All `gog` commands are awaited synchronously, no timeout.
- **Only Read = Delete:** If only `[x] Read` is checked, call `os.remove()`.
- **No action = Skip:** If nothing is checked, skip the file.
- **Empty reply section:** Log warning but continue (do not stop); archive can still proceed.
- **Forward empty target:** If text after `→` is empty, skip `execute_forward` (log warning), continue.

## Error Handling
- `gog` binary not found → `exit(1)` with clear error message
- `OS_INBOX_PATH` does not exist → `exit(1)`
- Reply/Forward failure → log error, **do NOT move file**, continue to next file
- File permission error → log error, skip that file

## Example
```bash
export OS_INBOX_PATH="/home/toni/obsidian/second-brain/00 - Inbox"
uv run email_processor.py
# Processing: 2026-04-27-19dce188c43be970.md
#   [REPLY] Sending reply to info@futureskills.id...
#   [ARCHIVE] Moved to 05 - Archive/Emails/
# Processing: 2026-04-27-19dce1aabb3f1234.md
#   [REPLY] Sending reply to boss@company.com...
#   (no [x] Archive → file stays in inbox)
# Processing: 2026-04-26-19dc97c483b45cd7.md
#   [DELETE] Only Read checked. Deleting...
# Done. 2 processed, 1 deleted.
```

## Changelog
| Version | Date | Notes |
|---|---|---|
| 0.4.0 | 2026-04-27 | Translated to English for AI compatibility |
| 0.3.0 | 2026-04-27 | Patch: clarify action names, account source, forward empty, STOP-ON-FAIL scope |
| 0.2.0 | 2026-04-27 | Sync env to OS_INBOX_PATH; archive only when [x] Archive is checked |
| 0.1.0 | 2026-04-27 | Initial spec |
