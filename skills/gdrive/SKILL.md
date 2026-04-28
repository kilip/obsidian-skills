---
name: gdrive
description: >
  Use this skill whenever the user wants to index Google Drive, sync Drive metadata,
  search Drive files, or generate AI summaries (briefs) for Drive documents such as
  Word, PDF, Excel, or PowerPoint files. This skill maintains a local SQLite index
  of all Drive files via the gog CLI, supports fast offline search, and can generate
  concise AI briefs using Gemini CLI for any supported document format.
allowed-tools:
  - "Bash"
  - "Read"
  - "Write"
---

# SKILL: Google Drive Indexer & Briefer

## Overview

> This skill connects Google Drive with an Obsidian vault using a local SQLite database as an index.
> It provides three core capabilities: **reindex** (sync file metadata from Drive to a local DB),
> **search** (fast offline file querying against the local index), and **brief** (generate AI summaries
> for Word/PDF/Excel/PPT documents using Gemini CLI).
> All Google Drive operations are performed via the `gog` CLI as a subprocess.

---

## Prerequisites

| Tool / Dependency | Notes |
|---|---|
| `gog` CLI | Google Drive CLI. Install from https://gogcli.sh or set its path via `OS_GDRIVE_GOG_BIN` |
| `uv` | Python package manager. All scripts are executed via `uv run` |
| Python ≥ 3.11 | Minimum supported version |
| `python-docx` | Text extraction from `.docx` files (auto-installed via pyproject.toml) |
| `pdfplumber` | Text extraction from `.pdf` files |
| `openpyxl` | Text extraction from `.xlsx` files |
| `python-pptx` | Text extraction from `.pptx` files |
| `tabulate` | Optional — pretty-print table output for the `search` command |
| Gemini CLI | Required for the `brief` feature (AI summarization) — must be available in PATH |
| `GOG_ACCOUNT` | Must be set to your Google account email |

---

## Usage

### Subcommands

#### 1. `reindex` — Sync Drive metadata to SQLite

Scans all of "My Drive" and upserts file metadata into the local DB. After indexing, it automatically triggers content extraction for new or modified documents (.docx, .pdf, .xlsx, .pptx) and saves them to the `contents` table. Run this periodically (e.g., as a daily cron job) to keep the index and content cache up to date.

```bash
uv run python -m gdrive.cli reindex
uv run python -m gdrive.cli reindex --dry-run   # preview without writing to DB
```

#### 2. `search` — Query the local index

Fast offline search — no internet connection required (all results come from SQLite).

```bash
uv run python -m gdrive.cli search --name "report"
uv run python -m gdrive.cli search --mime pdf --after 7d --limit 20
uv run python -m gdrive.cli search --brief-contains "budget" --json
```

| Flag | Shortcut | Default | Description |
|---|---|---|---|
| `--name` | `-n` | — | Filter by filename (substring match) |
| `--mime` | `-m` | — | Filter by MIME type or shortcut (`pdf`, `sheet`, `doc`, `slide`, etc.) |
| `--owner` | `-o` | — | Filter by owner email (substring match) |
| `--parent` | `-p` | — | Filter by parent folder ID |
| `--after` | — | — | Filter by modification date (ISO `YYYY-MM-DD` or relative `7d`, `24h`) |
| `--before` | — | — | Filter by modification date (ISO or relative) |
| `--has-brief` | — | — | Only show files that have a successful AI brief |
| `--no-brief` | — | — | Only show files that do not have an AI brief yet |
| `--brief-contains` | — | — | Filter by text content inside the AI brief (substring) |
| `--include-trashed` | — | — | Include files that are in the Google Drive trash |
| `--trashed-only` | — | — | Show only files that are in the trash |
| `--sort-by` | — | `modified` | Sort results by `modified`, `size`, or `name` |
| `--fields` | — | — | Comma-separated list of fields to return (e.g., `id,name,mime_type`) |
| `--limit` | `-l` | 10 | Maximum number of results |
| `--json` | `-j` | true | Output results as JSON (default) |
| `--table` | `-t` | false | Output results as a human-readable table |

##### Search Output Example (JSON)

```json
[
  {
    "id": "1O6hxCYLmv756-H2ozjZCEUWXs4KTQDs9",
    "name": "Project Proposal 2025.pdf",
    "mime_type": "application/pdf",
    "size_bytes": 882194,
    "owner": "me@gmail.com",
    "modified_at": "2025-04-27T19:04:46Z",
    "parent_id": "1myCpmY-_C3fVpjKE0d7M4fJEYcHrGcaN",
    "web_view_link": "https://drive.google.com/...",
    "is_trashed": 0,
    "has_brief": true,
    "brief_preview": "This document outlines the strategic plan for 2025, focusing on..."
  }
]
```

#### 3. `brief` — Generate AI summaries for documents

Generates AI-powered summaries (via Gemini CLI) for Word/PDF/Excel/PPT files that have never been briefed, or that have been modified since their last brief. Output is saved to the `briefs` table in SQLite.

```bash
uv run python -m gdrive.cli brief
uv run python -m gdrive.cli brief --limit 20
uv run python -m gdrive.cli brief --dry-run    # preview without downloading or calling Gemini
```

| Flag | Shortcut | Default | Description |
|---|---|---|---|
| `--limit` | `-l` | 50 | Maximum number of files to brief per run |
| `--dry-run` | — | false | Simulate without downloading files or calling Gemini |

#### 4. `service install` — Setup automatic indexing

Automates the installation of a systemd user service and timer to run `reindex` every 12 hours.

```bash
uv run python -m gdrive.cli service install
```

This command:
- Validates prerequisites (`uv`, `gog`, `GOG_ACCOUNT`).
- Generates `~/.config/systemd/user/gdrive.service` and `gdrive.timer`.
- Generates `~/.config/gdrive/env` with your current environment variables.
- Enables and starts the timer.

Verify the service:
```bash
systemctl --user status gdrive.timer
systemctl --user list-timers | grep gdrive
```

---

## Configuration

All configuration is read from environment variables. Prefix: `OS_GDRIVE_`.

| Variable | Required | Default | Description |
|---|---|---|---|
| `GOG_ACCOUNT` | ✅ | — | Google account email (used by `gog --account`) |
| `OS_GDRIVE_DB_PATH` | ❌ | `~/.gdrive/index.db` | Path to the SQLite database file |
| `OS_GDRIVE_LOG_PATH` | ❌ | `~/.gdrive/gdrive.log` | Path to the log file |
| `OS_GDRIVE_GOG_BIN` | ❌ | `gog` | Full path to the `gog` binary if not in PATH |
| `OS_GDRIVE_DRY_RUN` | ❌ | `0` | Set to `1`/`true`/`yes` to enable dry-run mode globally |
| `OS_GDRIVE_PAGE_DELAY` | ❌ | `0.1` | Delay in seconds between reindex pages |
| `OS_GDRIVE_BRIEF_DELAY` | ❌ | `0.5` | Delay in seconds between file briefing |
| `OS_GDRIVE_EXCLUDE_FOLDERS` | ❌ | — | Comma-separated folder names to skip recursively |

---

## Usage Tips & Guidance

### When to run `reindex` or `brief`
- **Empty results?** If `search` returns nothing even for broad queries, the local index might be empty. Run `uv run python -m gdrive.cli reindex` to sync metadata.
- **No briefs?** If `has_brief` is always `false`, run `uv run python -m gdrive.cli brief` to generate AI summaries for your documents.
- **Outdated data?** The index is local. If you just uploaded a file via the web UI, it won't show up in `search` until you `reindex`.

### When NOT to use this skill
- **File content editing**: This skill is for **indexing and summarizing**, not for editing the contents of Google Docs or sheets.
- **Real-time collaboration**: Use the Google Drive web interface for real-time collaboration. The local index is a snapshot.
- **Large file downloads**: While the skill can download files for briefing, it is not optimized as a general-purpose file downloader for the user.

---

## Architecture

```
CLI (cli.py)
  │
  ├── reindex.py ──► gog.py (drive_search_all) ──► gog CLI subprocess ──► Google Drive API
  │       └──────────────────────────────────────────────────────────────► db.py (upsert_file)
  │
  ├── search.py ───► db.py (search_files) ──► SQLite
  │
  └── brief.py ───► gog.py (drive_download) ──► tmp file
              │──► text extractors (docx/pdf/xlsx/pptx)
              └──► Gemini CLI subprocess ──► db.py (save_brief)
```

### SQLite Schema

**`files`** — metadata for all indexed Drive files:

| Column | Type | Description |
|---|---|---|
| `id` | TEXT PK | Google Drive file ID |
| `name` | TEXT | File name |
| `mime_type` | TEXT | MIME type |
| `size_bytes` | INTEGER | File size in bytes |
| `owner` | TEXT | Owner's email address |
| `modified_at` | TEXT | ISO timestamp of last modification |
| `parent_id` | TEXT | Parent folder ID |
| `web_view_link` | TEXT | Google Drive URL |
| `is_trashed` | INTEGER | 0 = active, 1 = in trash |
| `category` | TEXT | Document category (set by AI) |
| `tags` | TEXT | JSON array of keywords (set by AI) |
| `folder_path` | TEXT | Full path from Drive root |
| `indexed_at` | TEXT | Timestamp when the record was last indexed |

**`index_runs`** — log of each reindex session:

| Column | Description |
|---|---|
| `id` | Auto-increment run ID |
| `started_at` / `finished_at` | Session timestamps |
| `files_added` / `files_updated` | Change statistics |
| `status` | `running` / `ok` / `error` |
| `error_msg` | Error detail if the run failed |

**`briefs`** — AI-generated summaries per file:

| Column | Description |
|---|---|
| `file_id` | Foreign key to `files.id` |
| `brief` | The generated summary text (NULL if failed) |
| `error` | Error message if briefing failed |
| `briefed_at` | ISO timestamp of the last brief attempt |

**`contents`** — cached document text/markdown (feature #16):

| Column | Description |
|---|---|
| `file_id` | Foreign key to `files.id` |
| `content` | The raw extracted text/markdown |
| `extracted_at` | ISO timestamp of the last extraction |

---

## Behavior Rules

1. **Never delete files** — only upsert/update operations are allowed on the `files` table.
2. **Always respect `dry_run`** — check `config.is_dry_run()` or the `--dry-run` flag before writing to the DB or Drive.
3. **Automatic pagination** — `gog.drive_search_all()` handles all pages automatically; never query page-by-page manually.
4. **Brief only files that need it** — `db.get_unbriefed_files()` filters out files that already have an up-to-date brief.
5. **Robust since advancing** — `since` always advances after a brief run, even if all files in that run failed, to prevent infinite loops.
6. **Automatic retries** — AI briefing calls automatically retry up to 3 times with exponential backoff on failure.
7. **Automatic Content Extraction** — After `reindex` completes, `extract_pending()` is automatically called to download and extract text/markdown from new or modified documents.
8. **Document Caching** — Extracted text is saved to the `contents` table. Subsequent briefs for the same file skip download/extraction if the file hasn't been modified (feature #16).
9. **Text truncation** — `brief.py` truncates extracted text to `MAX_TEXT_CHARS = 12_000` before sending to Gemini to avoid token overload.
10. **Always clean up tmp files** — Downloaded tmp files are always deleted after extraction.
11. **Log to file AND stdout** — all log output is written to both `OS_GDRIVE_LOG_PATH` and stdout simultaneously.

---

## Error Handling

| Scenario | Behavior |
|---|---|
| `gog` binary not found | Raises `RuntimeError` with install instructions |
| `GOG_ACCOUNT` not set | Raises `RuntimeError` with an example export command |
| `gog` exits with non-zero code | Raises `RuntimeError` with full stderr output |
| Text extraction fails | `brief.py` records the error to the DB (`save_brief(error=...)`) and continues to the next file |
| File has no extractable text | Logs a warning and skips briefing for that file |
| Gemini CLI error | Raises `RuntimeError` from the subprocess, recorded to the DB |
| `NotImplementedError` | Logged as a warning, recorded to the DB, continues to the next file |

---

## Example

### Setup

```bash
export GOG_ACCOUNT="you@gmail.com"
export OS_GDRIVE_DB_PATH="~/.gdrive/index.db"
# Optional:
export OS_GDRIVE_GOG_BIN="/usr/local/bin/gog"
export OS_GDRIVE_DRY_RUN="0"
```

### Daily Workflow

```bash
# 1. Sync the index from Drive (run once or via cron)
uv run python -m gdrive.cli reindex

# 2. Search files offline
uv run python -m gdrive.cli search --name "proposal" --mime pdf

# 3. Generate AI briefs for new/updated documents
uv run python -m gdrive.cli brief --limit 20
```

### Search Output Example

```
Name                          Type    Size      Owner            Modified    Link
----------------------------  ------  --------  ---------------  ----------  --------
Project Proposal 2025.pdf     pdf     1,234 KB  me@gmail.com     2025-01-15  https://...
Q1 Budget.xlsx                xlsx      512 KB  me@gmail.com     2025-01-10  https://...

2 result(s).
```

---

## Roadmap / TODO

- [x] Implement `gog drive download` in `gog.py`
- [x] Implement Gemini CLI wrapper in `brief.py`
- [x] Add `briefs` table to SQLite schema in `db.py` (`save_brief`, `get_unbriefed_files`, `get_last_brief_run`)
- [x] Add `brief` subcommand to `cli.py`
- [x] Add `upload` subcommand to the full workflow

---

*kilip/obsidian-skills · gdrive skill · reusable Google Drive automation*
