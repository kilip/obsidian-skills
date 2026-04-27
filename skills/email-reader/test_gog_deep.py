import json
import subprocess
import sys

def run_command(cmd_list):
    cmd_str = " ".join([f'"{arg}"' if " " in arg else arg for arg in cmd_list])
    res = subprocess.run(cmd_str, capture_output=True, text=True, shell=True)
    return res.stdout.strip()

# Get first unread to get a valid ID
print("Searching...")
search_out = run_command(["gog", "gmail", "search", "is:unread", "-j", "--results-only", "-n", "1"])
if not search_out:
    print("No unread found.")
    sys.exit(0)

msg_meta = json.loads(search_out)[0]
msg_id = msg_meta.get("id")
print(f"ID found: {msg_id}")

print(f"Getting full message for {msg_id}...")
# Note: I need the account name. Let's assume the first account from auth list.
acc_out = run_command(["gog", "auth", "list", "--plain"])
account = acc_out.splitlines()[0].split("\t")[0]
print(f"Using account: {account}")

full_out = run_command(["gog", "gmail", "get", msg_id, "-a", account, "-j", "--results-only"])
print(f"FULL STDOUT LENGTH: {len(full_out)}")
if full_out:
    try:
        data = json.loads(full_out)
        print("Keys in JSON:", data.keys())
        # Check for snippet and headers
        print("Snippet:", data.get("snippet"))
        payload = data.get("payload", {})
        headers = payload.get("headers", [])
        print(f"Number of headers: {len(headers)}")
        for h in headers[:5]:
            print(f"  {h.get('name')}: {h.get('value')}")
    except Exception as e:
        print(f"Parse error: {e}")
        print(f"RAW: {full_out[:500]}")
else:
    print("No output from gmail get.")
