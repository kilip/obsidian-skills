---
name: gemini-cli
description: >
  Use this skill whenever you need to call the Gemini CLI to generate text,
  summarize content, translate, classify, or run any prompt-based AI task.
  This is a reusable wrapper around the `gemini` binary that can be called
  from other skills or directly from the command line. Supports reading
  prompts from arguments, stdin, or files, with configurable model selection.
allowed-tools:
  - "Bash"
  - "Read"
---

# SKILL: Gemini CLI Wrapper

## Overview

> A thin, reusable wrapper around the `gemini` CLI binary.
> Accepts a prompt from a CLI argument, a file, or stdin, sends it to the Gemini model,
> and returns the response to stdout. Designed to be used standalone or imported as a
> module by other skills that need AI text generation.

---

## Prerequisites

| Tool / Dependency | Notes |
|---|---|
| `gemini` CLI | Must be installed and available in PATH (or set `OS_GEMINI_BIN`) |
| `uv` | Python package manager. Run scripts via `uv run` |
| Python ≥ 3.11 | Minimum supported version |

---

## Usage

### How to invoke this skill

Use when any skill or user needs to call Gemini with a prompt and get back a text response.

```bash
cd skills/gemini-cli

# Prompt from argument
uv run gemini_cli.py --prompt "Summarize this meeting: ..."

# Prompt from a file
uv run gemini_cli.py --prompt-file ./my_prompt.txt

# Prompt from stdin
echo "Translate to French: Hello world" | uv run gemini_cli.py

# Override model for a single call
uv run gemini_cli.py --prompt "..." --model gemini-2.5-pro
```

### Input

One of the following (in priority order):
1. `--prompt TEXT` — inline prompt string
2. `--prompt-file PATH` — read prompt from a file
3. `stdin` — read prompt from standard input

### Output

- **stdout**: The Gemini response text (stripped)
- **stderr**: Error messages if the call fails
- **exit code**: `0` on success, `1` on failure

---

## Configuration

| Variable | Required | Default | Description |
|---|---|---|---|
| `OS_GEMINI_BIN` | ❌ | `gemini` | Path to the Gemini CLI binary |
| `OS_GEMINI_MODEL` | ❌ | `gemini-2.5-flash-lite` | Default Gemini model to use |

---

## Using as a Dependency in Other Skills

Add `gemini-cli` as a path dependency in the consuming skill's `pyproject.toml`:

```toml
[project]
dependencies = [
    "gemini-cli",
]

[tool.uv.sources]
gemini-cli = { path = "../../gemini-cli" }   # adjust relative path as needed
```

Then import directly:

```python
from gemini_cli import prompt

result = prompt("Summarize this: ...")
result = prompt("Translate this", model="gemini-2.5-pro")
```

Or create a thin shim for backward compatibility within your package:

```python
# myskill/gemini.py — shim
from gemini_cli import prompt, get_model, get_bin  # noqa: F401
```


---

## Behavior Rules

1. **Exactly one input source** — if multiple are given, priority: `--prompt` > `--prompt-file` > stdin.
2. **Empty prompt → exit 1** — do not call Gemini with an empty string.
3. **Never silence errors** — always surface Gemini CLI stderr to stderr.
4. **Model always explicit** — always pass `--model` to the Gemini CLI to avoid ambiguity.
5. **Timeout respected** — if `OS_GEMINI_TIMEOUT` is set, pass it as a subprocess timeout.

---

## Error Handling

| Scenario | Behavior |
|---|---|
| `gemini` binary not found | Print error to stderr, exit 1 |
| Empty prompt | Print error to stderr, exit 1 |
| Gemini CLI exits non-zero | Print stderr from Gemini, exit 1 |
| Prompt file not found | Print error to stderr, exit 1 |
| Subprocess timeout | Print timeout error to stderr, exit 1 |

---

## Example

```bash
# Summarize a document
cat document.txt | uv run gemini_cli.py

# Output:
# 📄 **Summary**: This document outlines the Q1 2025 project roadmap...
# 🎯 **Key Points**:
# - Deadline is March 31, 2025
# - Budget approval needed by January
# ⚠️ **Action Required**: Submit budget form by Jan 15.
```

---

*kilip/obsidian-skills · gemini-cli skill · reusable Gemini CLI wrapper*
