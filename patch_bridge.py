import re
import os

file_path = 'src/controller/remote_bridge.py'

if not os.path.exists(file_path):
    print(f"Error: Could not find {file_path}")
    exit(1)

with open(file_path, 'r') as f:
    content = f.read()

# Find the exact buggy block of code
pattern = r"def read_status\(\) -> dict:\s+payload = read_json\(CFG\.STATUS_FILE\)\s+if payload is not None:\s+latest_packet = _read_latest_lora_packet\(\)\s+if latest_packet:\s+payload\.update\(\{[^}]+\}\)\s+return payload"

new_text = """def read_status() -> dict:
    payload = read_json(CFG.STATUS_FILE)
    if payload is not None:
        return payload"""

if re.search(pattern, content):
    content = re.sub(pattern, new_text, content)
    with open(file_path, 'w') as f:
        f.write(content)
    print("✅ Bug successfully patched! The dashboard will no longer overwrite live data with stale CSV data.")
else:
    print("⚠️ Could not find the bug. It might have already been patched!")

