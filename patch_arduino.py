import os

FILE = "arduino_monitor.py"

with open(FILE, "r", encoding="utf-8") as f:
    code = f.read()

# Add time.sleep(0.002) to the voltage loop
old_v_loop = """    for _ in range(NUM_SAMPLES):
        raw_v.append(chan_v.voltage / ZMPT_DIVIDER)"""

new_v_loop = """    for _ in range(NUM_SAMPLES):
        raw_v.append(chan_v.voltage / ZMPT_DIVIDER)
        time.sleep(0.002)"""

# Add time.sleep(0.002) to the current loop
old_i_loop = """    for _ in range(NUM_SAMPLES):
        raw_v.append(chan_i.voltage / ACS_DIVIDER)"""

new_i_loop = """    for _ in range(NUM_SAMPLES):
        raw_v.append(chan_i.voltage / ACS_DIVIDER)
        time.sleep(0.002)"""

code = code.replace(old_v_loop, new_v_loop)
code = code.replace(old_i_loop, new_i_loop)

with open(FILE, "w", encoding="utf-8") as f:
    f.write(code)
print("✅ arduino_monitor.py patched with I2C anti-flood delays!")
