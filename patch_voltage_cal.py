import re

FILE = "src/controller/tank_config.py"
with open(FILE, "r", encoding="utf-8") as f:
    code = f.read()

if "ZMPT101B_CAL_FACTOR" in code:
    # Use Regex to dynamically find and replace the old 1.0 value with 209.09
    code = re.sub(
        r"ZMPT101B_CAL_FACTOR\s*=\s*[0-9\.]+", 
        "ZMPT101B_CAL_FACTOR    = 209.09", 
        code
    )
    with open(FILE, "w", encoding="utf-8") as f:
        f.write(code)
    print("✅ ZMPT101B Calibration Factor permanently updated to 209.09!")
else:
    print("❌ Could not find ZMPT101B_CAL_FACTOR in tank_config.py")
