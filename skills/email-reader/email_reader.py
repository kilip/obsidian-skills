# /// script
# dependencies = [
#   "pathlib",
# ]
# ///

import os
import sys
import json
import subprocess
import re
import time
import tempfile
from pathlib import Path
from datetime import datetime
from typing import List, Dict, Any, Optional

# --- Configuration (Mandatory ENV) ---
INBOX_PATH_ENV = os.environ.get("OV_INBOX_PATH")
GEMINI_MODEL = os.environ.get("GEMINI_MODEL", "gemini-2.5-flash-lite")
GOG_BIN = os.environ.get("GOG_BIN", "gog")

# Global paths
SCRIPT_DIR = Path(__file__).parent
EMAIL_TEMPLATE = SCRIPT_DIR / "template" / "Email.md"
UNSUB_TEMPLATE = SCRIPT_DIR / "template" / "Unsubscribe.md"

# Derived paths
INBOX_PATH = Path(".")
EMAILS_DIR = Path(".")
VAULT_ROOT = Path(".")

def validate_env() -> None:
    """Strictly validates environment and dependencies."""
    global INBOX_PATH, EMAILS_DIR, VAULT_ROOT
    if not INBOX_PATH_ENV:
        print("\n[ERROR] OV_INBOX_PATH is not set.", file=sys.stderr)
        sys.exit(1)
    INBOX_PATH = Path(INBOX_PATH_ENV)
    EMAILS_DIR = INBOX_PATH / "Emails"
    VAULT_ROOT = INBOX_PATH.parent
    if not EMAIL_TEMPLATE.exists():
        print(f"[ERROR] Email Template not found.", file=sys.stderr)
        sys.exit(1)
    EMAILS_DIR.mkdir(parents=True, exist_ok=True)
    try:
        subprocess.run([GOG_BIN, "--version"], capture_output=True, check=True, shell=True)
    except:
        print(f"[ERROR] '{GOG_BIN}' CLI not found.", file=sys.stderr)
        sys.exit(1)

def run_command(cmd: List[str], input_data: Optional[str] = None) -> str:
    try:
        cmd_str = " ".join([f'"{arg}"' if " " in arg or "\n" in arg else arg for arg in cmd])
        result = subprocess.run(cmd_str, input=input_data, capture_output=True, text=True, check=True, encoding='utf-8', shell=True)
        return result.stdout.strip()
    except subprocess.CalledProcessError as e:
        # print(f"Command failed: {e.cmd} - {e.stderr}")
        return ""

def convert_html_to_md(html_content: str) -> str:
    """Converts HTML to Markdown using defuddle CLI."""
    if not html_content.strip(): return ""
    with tempfile.NamedTemporaryFile(suffix=".html", delete=False, mode="w", encoding="utf-8") as tmp:
        tmp.write(html_content)
        tmp_path = tmp.name
    try:
        return run_command(["npx", "-y", "defuddle", "parse", tmp_path, "--md"])
    finally:
        if os.path.exists(tmp_path): os.remove(tmp_path)

def update_unsubscribe_list(sender: str, raw_header: str) -> None:
    """Maintains Unsubscribe.md. Format: - [ ] [Name](link) <email>"""
    links = re.findall(r'<(https?://[^>]+)>', raw_header)
    if not links: return
    link = links[0]
    unsub_file = INBOX_PATH / "Unsubscribe.md"
    
    if not unsub_file.exists():
        if UNSUB_TEMPLATE.exists():
            unsub_file.write_text(UNSUB_TEMPLATE.read_text(encoding="utf-8"), encoding="utf-8")
        else:
            unsub_file.write_text("# 🚫 Unsubscribe List\n\n## ⏳ Pending\n\n{{pending}}\n\n## ✅ Done\n", encoding="utf-8")

    current_content = unsub_file.read_text(encoding="utf-8")
    
    email_match = re.search(r'<([^>]+)>', sender)
    sender_email = email_match.group(1) if email_match else sender
    clean_sender_name = sender.split("<")[0].strip() or sender_email
    
    if link in current_content: return
    if f"[{clean_sender_name}]" in current_content: 
        print(f"    [SKIP] {clean_sender_name} is already in the list.")
        return
        
    new_entry = f"- [ ] [{clean_sender_name}]({link}) `<{sender_email}>`"
    
    if "{{pending}}" in current_content:
        new_content = current_content.replace("{{pending}}", f"{new_entry}\n{{{{pending}}}}")
    elif "## ⏳ Pending" in current_content:
        pattern = r"(## ⏳ Pending\s*)"
        new_content = re.sub(pattern, rf"\1\n{new_entry}\n", current_content, count=1)
    else:
        new_content = current_content + f"\n\n## ⏳ Pending\n\n{new_entry}\n"
        
    unsub_file.write_text(new_content, encoding="utf-8")
    print(f"    [LISTED] Added {clean_sender_name} <{sender_email}> to Unsubscribe.md")

def mark_as_read(msg_id: str, account: str) -> None:
    # Correct gog command: gog gmail mark-read <msgId>
    res = run_command([GOG_BIN, "gmail", "mark-read", msg_id, "-a", account, "--no-input"])
    print(f"    [READ] Marked {msg_id} as read.")

def get_accounts() -> List[str]:
    stdout = run_command([GOG_BIN, "auth", "list", "--plain"])
    return [line.split("\t")[0] for line in stdout.splitlines() if line.strip()]

def get_processed_ids() -> set:
    processed_ids = set()
    for f in EMAILS_DIR.glob("*.md"):
        match = re.search(r"\d{4}-\d{2}-\d{2}-([a-f0-9]+)\.md", f.name)
        if match: processed_ids.add(match.group(1))
    for f in VAULT_ROOT.rglob("*.md"):
        if "00 - Inbox/Emails" in str(f): continue
        match = re.search(r"\d{4}-\d{2}-\d{2}-([a-f0-9]+)\.md", f.name)
        if match: processed_ids.add(match.group(1))
    return processed_ids

def get_ai_brief(subject: str, snippet: str) -> Dict[str, str]:
    prompt = f"Summarize this email for an Obsidian daily log.\nSubject: {subject}\nSnippet: {snippet}\n\nReturn ONLY raw JSON: {{\"brief\": \"...\", \"cleaned_subject\": \"...\"}}"
    stdout = run_command(["gemini", "-m", GEMINI_MODEL, prompt])
    try:
        match = re.search(r"\{.*\}", stdout, re.DOTALL)
        return json.loads(match.group(0)) if match else json.loads(stdout)
    except:
        return {"brief": "Failed to parse AI response.", "cleaned_subject": subject}

def parse_gmail_date(date_str: str) -> datetime:
    clean_date = re.sub(r"\s*\([^)]*\)$", "", date_str)
    try: return datetime.strptime(clean_date, "%a, %d %b %Y %H:%M:%S %z")
    except:
        try: return datetime.strptime(clean_date, "%d %b %Y %H:%M:%S %z")
        except: return datetime.now()

def save_email_as_markdown(msg_data: Dict[str, Any], body_content: str, ai_data: Dict[str, str]) -> Path:
    msg_id = msg_data.get("id", "no-id")
    headers = msg_data.get("payload", {}).get("headers", [])
    sender, to_val, subject, raw_date = "Unknown", "Unknown", "No Subject", ""
    for h in headers:
        n = h.get("name", "").lower()
        if n == "from": sender = h.get("value")
        elif n == "to": to_val = h.get("value")
        elif n == "subject": subject = h.get("value")
        elif n == "date": raw_date = h.get("value")
    dt = parse_gmail_date(raw_date)
    cleaned_subject = ai_data.get("cleaned_subject", subject)
    file_path = EMAILS_DIR / f"{dt.strftime('%Y-%m-%d')}-{msg_id}.md"
    content = EMAIL_TEMPLATE.read_text(encoding="utf-8")
    replacements = {
        "{{date}}": dt.strftime("%Y-%m-%d %H:%M"), "{{sender}}": sender, "{{to}}": to_val, "{{subject}}": subject,
        "{{title}}": cleaned_subject, "{{date_long}}": dt.strftime("%d %B %Y, %H:%M"),
        "{{brief}}": ai_data.get("brief", ""), "{{body}}": body_content
    }
    for tag, val in replacements.items(): content = content.replace(tag, str(val))
    file_path.write_text(content, encoding="utf-8")
    return file_path

def main():
    validate_env()
    print(f"USING MODEL: {GEMINI_MODEL}")
    accounts = get_accounts()
    processed_ids = get_processed_ids()
    print(f"Checking {len(accounts)} accounts. Vault has {len(processed_ids)} processed emails.")

    for account in accounts:
        print(f"Fetching unread for {account}...")
        search_out = run_command([GOG_BIN, "gmail", "messages", "search", "is:unread", "-a", account, "--json", "--no-input"])
        if not search_out: continue
        try: messages = json.loads(search_out).get("messages", [])
        except: continue
        for msg_meta in messages:
            msg_id = msg_meta.get("id")
            
            if msg_id in processed_ids:
                print(f"  Syncing state for {msg_id} (already in vault)...")
                mark_as_read(msg_id, account)
                continue

            print(f"  Processing {msg_id}...", flush=True)
            get_out = run_command([GOG_BIN, "gmail", "get", msg_id, "-a", account, "--json", "--no-input"])
            try:
                res = json.loads(get_out)
                msg_full = res.get("message")
                html_raw = res.get("body", "")
            except: continue
            headers = msg_full.get("payload", {}).get("headers", [])
            is_promo, unsub_header, subject, sender = False, "", "No Subject", "Unknown"
            for h in headers:
                n = h.get("name", "").lower()
                if n == "list-unsubscribe": is_promo, unsub_header = True, h.get("value")
                elif n == "subject": subject = h.get("value")
                elif n == "from": sender = h.get("value")
            
            body_md = convert_html_to_md(html_raw) if html_raw else msg_full.get("snippet", "")
            
            # Robust promo detection: check body/snippet if header missing
            if not is_promo:
                promo_keywords = ["unsubscribe", "view in browser", "click here to", "email preferences", "manage preferences"]
                combined_text = (subject + " " + body_md + " " + msg_full.get("snippet", "")).lower()
                if any(kw in combined_text for kw in promo_keywords):
                    is_promo = True
                    print(f"    [PROMO] Detected via keywords.")
            if is_promo:
                ai_data = {"brief": "Promo skipped AI.", "cleaned_subject": subject}
                if unsub_header: 
                    update_unsubscribe_list(sender, unsub_header)
                mark_as_read(msg_id, account)
            else:
                ai_data = get_ai_brief(subject, msg_full.get("snippet", ""))
                save_email_as_markdown(msg_full, body_md, ai_data)
                # Regular emails stay unread for email-processor
                print(f"    Saved to {EMAILS_DIR} (remains UNREAD for processor)")

if __name__ == "__main__":
    main()
