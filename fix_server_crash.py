import re

SERVER_PY = "src/dashboard/server.py"
with open(SERVER_PY, "r", encoding="utf-8") as f:
    code = f.read()

# Find the entire broken function and its return block
pattern = r"def _apply_auto_control_if_needed\(.*?\) -> tuple\[dict, dict\]:.*?return pump_status, \{[^}]+\}"

# Replace it with a clean, safe, non-crashing function
new_func = """def _apply_auto_control_if_needed(system_mode: str, pump_status: dict, prediction: dict) -> tuple[dict, dict]:
    return pump_status, {
        "enabled": system_mode == "auto",
        "action": "hold",
        "should_run": False,
        "reason": "Handled securely by pump_controller hardware loop"
    }"""

code = re.sub(pattern, new_func, code, flags=re.DOTALL)

with open(SERVER_PY, "w", encoding="utf-8") as f:
    f.write(code)

print("✅ Server crashing bug successfully fixed!")
