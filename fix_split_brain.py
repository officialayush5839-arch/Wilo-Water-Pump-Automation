import os

SERVER_PY = "src/dashboard/server.py"

with open(SERVER_PY, "r", encoding="utf-8") as f:
    code = f.read()

# 1. Neutralize the rogue Flask auto-control
old_auto_control = """def _apply_auto_control_if_needed(system_mode: str, pump_status: dict, prediction: dict) -> tuple[dict, dict]:
    if system_mode != "auto" or not pump_status.get("available", False):
        return pump_status, {"enabled": False}

    should_run = _is_in_prediction_window(prediction)
    current_state = pump_status.get("pump_relay_on")
    action = "hold"

    if isinstance(current_state, bool) and current_state != should_run:
        pump_status = {
            "available": True,
            **_set_manual_pump(should_run, notify_controller=False),
        }
        action = "on" if should_run else "off"

    return pump_status, {"""

new_auto_control = """def _apply_auto_control_if_needed(system_mode: str, pump_status: dict, prediction: dict) -> tuple[dict, dict]:
    # Disable duplicate Flask auto-control to prevent it from ignoring tank safety levels.
    # The actual pump_controller.py hardware loop now natively handles the AI schedule securely.
    return pump_status, {"""

if "should_run = _is_in_prediction_window" in code:
    code = code.replace(old_auto_control, new_auto_control)

# 2. Stop Flask from overwriting the true hardware state sent to the dashboard
old_overwrite = """    runtime_payload["system_mode"] = system_mode
    runtime_payload["pump_relay_on"] = pump_status.get("pump_relay_on")
    return {"""

new_overwrite = """    runtime_payload["system_mode"] = system_mode
    # DO NOT overwrite the true hardware relay state reported by pump_controller.py!
    return {"""

if "runtime_payload[\"pump_relay_on\"]" in code:
    code = code.replace(old_overwrite, new_overwrite)
    
with open(SERVER_PY, "w", encoding="utf-8") as f:
    f.write(code)

print("✅ Server successfully patched to cure Split-Brain architecture!")
