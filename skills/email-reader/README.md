# email-reader

Fetch unread emails from Gmail and save them as Obsidian-ready Markdown notes.

## Prerequisites

- Python 3.11+
- [`uv`](https://github.com/astral-sh/uv)
- [`gog`](https://github.com/itstoni/gog) CLI (Authenticated)
- [`defuddle`](https://github.com/itstoni/defuddle) (for HTML to MD conversion)
- Gemini CLI (for AI summaries)

## Environment Variables

| Variable | Description | Example |
|----------|-------------|---------|
| `OV_INBOX_PATH` | Path to your Obsidian Vault's **Inbox** directory | `/path/to/vault/00 - Inbox` |
| `GEMINI_MODEL` | (Optional) Gemini model for briefing | `gemini-2.5-flash-lite` |

## Usage

```bash
# Set your vault's inbox path
export OV_INBOX_PATH="/path/to/obsidian-vault/00 - Inbox"

# Run the skill
uv run email_reader.py
```

## Features

1.  **Direct-to-Vault**: Saves emails directly into `OV_INBOX_PATH/Emails/`.
2.  **Unsubscribe Manager**: Automatically adds promo links to `OV_INBOX_PATH/Unsubscribe.md`.
3.  **Deduplication**: Checks both the inbox and the entire vault to prevent duplicate imports.
4.  **Auto Mark Read**: Promotional emails are marked as read immediately to keep your Gmail clean.
5.  **HTML to MD**: Rich emails are converted to high-quality Markdown using `defuddle`.
6.  **AI Briefing**: Non-promotional emails get an AI-generated summary and a cleaned-up subject line.

## File Structure (Inside Inbox)

```text
00 - Inbox/
├── Emails/             # Where new emails go
│   └── 2026-04-27-id.md
└── Unsubscribe.md      # Centralized unsubscribe list
```
