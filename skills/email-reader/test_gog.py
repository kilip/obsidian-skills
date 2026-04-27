import json
import subprocess

def run_command(cmd_list):
    cmd_str = " ".join([f'"{arg}"' if " " in arg else arg for arg in cmd_list])
    res = subprocess.run(cmd_str, capture_output=True, text=True, shell=True)
    return res.stdout.strip()

print("Fetching first unread...")
stdout = run_command(["gog", "gmail", "search", "is:unread", "-j", "--results-only", "-n", "1"])
print(f"STDOUT: {stdout}")
try:
    data = json.loads(stdout)
    print(f"Parsed: {data}")
except Exception as e:
    print(f"Error: {e}")
