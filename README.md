# obsidian-skills

Reusable, self-contained skills for managing Obsidian vaults via AI agents powered by the Gemini CLI.

## Skills

| Skill | Description | Status |
|---|---|---|
| [email-reader](skills/email-reader/) | Fetch unread emails from Gmail into your Obsidian vault | ✅ Ready |
| [email-processor](skills/email-processor/) | Process reviewed email notes — archive, reply, forward, or delete | ✅ Ready |
| [gdrive](skills/gdrive/) | Index Google Drive metadata locally, search offline, and generate AI briefs for documents | ✅ Ready |
| [gemini-cli](skills/gemini-cli/) | Reusable Gemini CLI wrapper — send prompts from argument, file, or stdin | ✅ Ready |

## Requirements

- Python 3.11+
- [`uv`](https://github.com/astral-sh/uv) package manager
- Gemini CLI (`gemini`) installed and configured
- `gog` CLI authenticated (required by `email-reader`, `email-processor`, `gdrive`)

## Usage

```bash
# Install a skill
npx skills add <skill-name>

# Run a skill manually
cd skills/<skill-name>
uv run <script_name>.py
```

### Quick Examples

```bash
# Read new emails into Obsidian
cd skills/email-reader && uv run email_reader.py

# Process reviewed email notes
cd skills/email-processor && uv run email_processor.py

# Index your Google Drive
cd skills/gdrive/scripts && uv run python -m gdrive.cli reindex

# Call Gemini from the command line
cd skills/gemini-cli && uv run gemini_cli.py --prompt "Summarize this: ..."

# Or pipe from stdin
cat document.txt | uv run gemini_cli.py
```

## Environment Variables

| Variable | Required by | Description |
|---|---|---|
| `OV_INBOX_PATH` | email-reader, email-processor | Absolute path to Obsidian Inbox folder |
| `GOG_ACCOUNT` | email-reader, email-processor, gdrive | Google account email for `gog` CLI |
| `OS_GDRIVE_DB_PATH` | gdrive | Path to SQLite index DB (default: `~/.gdrive/index.db`) |
| `OS_GEMINI_MODEL` | gemini-cli, gdrive | Gemini model to use (default: `gemini-2.5-flash`) |
| `OS_GEMINI_BIN` | gemini-cli, gdrive | Path to `gemini` binary (default: `gemini`) |

See `.env.example` for a full list with descriptions.
