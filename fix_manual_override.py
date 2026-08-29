import os

MANUAL_PUMP = "src/controller/manual_pump_control.py"

with open(MANUAL_PUMP, "r", encoding="utf-8") as f:
    code = f.read()

old_read = """def read_status() -> dict:
    saved = read_json(CFG.DIRECT_PUMP_STATE_FILE) or {}
    saved_on = saved.get('pump_relay_on')
    if saved_on is True:
        _set_relay_outputs_on()
    else:
        _release_relay_outputs_off()
    return {"""

new_read = """def read_status() -> dict:
    saved = read_json(CFG.DIRECT_PUMP_STATE_FILE) or {}
    saved_on = saved.get('pump_relay_on')
    # SAFETY PATCH: Never allow a 'read' function to physically assert GPIO pins!
    # This prevents the Flask server from randomly killing the pump controller's commands.
    return {"""

if old_read in code:
    code = code.replace(old_read, new_read)
    with open(MANUAL_PUMP, "w", encoding="utf-8") as f:
        f.write(code)
    print("✅ manual_pump_control.py patched successfully!")
else:
    print("Could not find the read_status block. Already patched?")
