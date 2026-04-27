# SKILL: Email Reader

## Overview
> Fetches unread emails from all connected Gmail accounts using `gog cli`, identifies promotional emails for the unsubscribe list, and saves regular emails to the Obsidian Inbox for processing.

## Prerequisites

- `gog` — Google OAuth CLI tool for Gmail access
- `gemini` — Gemini CLI tool for generating briefs
- `OV_INBOX_PATH` — path to your Obsidian Inbox (e.g., `path/to/vault/00 - Inbox`)

## Usage

### How to invoke this skill
Use this skill when you need to pull fresh unread emails from Gmail into your Obsidian Inbox.

```bash
cd skills/email-reader
export OV_INBOX_PATH="/path/to/obsidian/inbox"
uv run email_reader.py
```

### Input
- Gmail accounts authenticated via `gog auth`
- `OV_INBOX_PATH` environment variable

### Output
- Markdown files in `OV_INBOX_PATH/Emails/`
- Updated `OV_INBOX_PATH/Unsubscribe.md` for promotional emails

## Configuration

| Variable | Required | Default | Description |
|---|---|---|---|
| `OV_INBOX_PATH` | ✅ | — | Absolute path to the Obsidian Inbox folder |
| `GOG_BIN` | ❌ | `gog` | Path to `gog` binary |
| `GEMINI_MODEL` | ❌ | `gemini-2.5-flash-lite` | Gemini model for briefs |

## Behavior Rules
- Fetch emails from **all** authenticated accounts, not just one
- **Do NOT mark regular emails as read** — they must remain unread for downstream processing or manual review.
- **Auto mark as read for promotional emails** only after they are successfully added to the unsubscribe list.
- Identify promotional emails using `List-Unsubscribe` headers or keywords in the body (e.g., "unsubscribe", "view in browser").
- Deduplicate based on Email ID (scans entire vault) and Sender Name (for unsubscribe list).
- If an account fails, log the error and continue with the next account.

## Error Handling
- Missing `gog` binary → exit 1 with clear error message
- No authenticated accounts → exit 1
- Partial failure (one account fails) → log warning, continue

## Example
```bash
export OV_INBOX_PATH="D:/Vault/00 - Inbox"
uv run email_reader.py
```

## Changelog
| Version | Date | Notes |
|---|---|---|
| 0.2.0 | 2026-04-27 | Fixed ENV names and updated to Obsidian-centric workflow |
| 0.1.0 | 2026-04-27 | Initial placeholder |
