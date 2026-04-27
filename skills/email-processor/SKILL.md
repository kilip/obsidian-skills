# SKILL: Email Processor

## Overview
> Reads the raw email cache produced by `email-reader`, routes each email (promo vs regular), generates AI summaries via Gemini CLI, writes structured Markdown notes to the Obsidian vault, and marks emails as read **only after** successful file write.

## Prerequisites

- `gog` — Google OAuth CLI tool (for marking emails as read)
- `gemini` — Gemini CLI configured with `gemini-2.5-flash-lite`
- Output cache from `email-reader` skill
- `VAULT_PATH` — path to target Obsidian vault

## Usage

### How to invoke this skill
Run **after** `email-reader` has produced its cache file.

```bash
cd skills/email-processor
uv run email_processor.py
```

### Input
- Cache JSON file from `email-reader`: `[OS_TMPDIR]/obsidian-skills/[datetime]-unread.json`

### Output
- Promo emails → link appended to `{VAULT_PATH}/00 - Inbox/Unsubscribe.md` under `## ⏳ Pending`
- Regular emails → Markdown note written to `{VAULT_PATH}/00 - Inbox/Emails/`
- Naming convention: `YYYY-MM-DD-[Gmail-ID]-[Cleaned-Subject].md`

## Configuration

| Variable | Required | Default | Description |
|---|---|---|---|
| `VAULT_PATH` | ✅ | — | Absolute path to the Obsidian vault |
| `GOG_BIN` | ❌ | `gog` | Path to `gog` binary |
| `GEMINI_MODEL` | ❌ | `gemini-2.5-flash-lite` | Gemini model to use |
| `CACHE_FILE` | ❌ | auto-detect latest | Path to specific cache JSON file |

## Behavior Rules
- **STOP-ON-FAIL policy**: if file write fails, do NOT mark email as read
- Mark email as read **only after** file is verified on disk
- Promo detection: check `List-Unsubscribe` header first, then scan body for "unsubscribe" keyword
- AI subject cleaning: replace original subject entirely with Gemini-cleaned version
- Duplicate check: verify Gmail ID against existing files before writing
- Process sequentially — no parallel processing (respect rate limits)

## Error Handling
- Cache file not found → exit 1
- Gemini CLI failure → halt current email, log error, do NOT mark as read
- File write failure → halt, log error, do NOT mark as read
- Unsubscribe.md not found → create it from template before appending

## Example
```bash
export VAULT_PATH="/home/user/obsidian/diary"
uv run email_processor.py
# Writes: /home/user/obsidian/diary/00 - Inbox/Emails/2026-04-27-18abc-Project-Update.md
```

## Changelog
| Version | Date | Notes |
|---|---|---|
| 0.1.0 | 2026-04-27 | Initial placeholder |
