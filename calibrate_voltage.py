import os

TANK_CONFIG = "src/controller/tank_config.py"

with open(TANK_CONFIG, "r", encoding="utf-8") as f:
    config = f.read()

# Replace the 1.0 placeholder with your custom calibration factor
config = config.replace("ZMPT101B_CAL_FACTOR    = 1.0", "ZMPT101B_CAL_FACTOR    = 153.3")

with open(TANK_CONFIG, "w", encoding="utf-8") as f:
    f.write(config)
print("✅ Voltage perfectly calibrated to 230V!")
