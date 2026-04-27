# obsidian-skills

Reusable, self-contained skills for managing Obsidian vaults.

## Skills

| Skill | Description | Status |
|---|---|---|
| [email-reader](skills/email-reader/) | Fetch unread emails from Gmail directly into your vault | ✅ Ready |

## Requirements

- Python 3.11+
- [`uv`](https://github.com/astral-sh/uv) package manager
- Gemini CLI configured
- `gog` CLI authenticated

## Usage

```bash
# Set required environment variable
export OV_INBOX_PATH="/path/to/your/obsidian/vault/00 - Inbox"

# Run a skill
cd skills/email-reader
uv run email_reader.py
```
