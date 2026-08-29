import os

TANK_CONFIG = "src/controller/tank_config.py"
SENSOR_READER = "src/controller/sensor_reader.py"

# 1. Update the divider ratios to 2.0 (cutting voltage in half)
with open(TANK_CONFIG, "r", encoding="utf-8") as f:
    config = f.read()
    
config = config.replace("ACS712_DIVIDER_RATIO  = 1.0", "ACS712_DIVIDER_RATIO  = 2.0")
config = config.replace("ZMPT101B_DIVIDER_RATIO = 1.0", "ZMPT101B_DIVIDER_RATIO = 2.0")

with open(TANK_CONFIG, "w", encoding="utf-8") as f:
    f.write(config)

# 2. Update the ADS1115 internal gain for a 3.3V power supply
with open(SENSOR_READER, "r", encoding="utf-8") as f:
    reader = f.read()

old_gain = "self.ads.gain = 2/3"
new_gain = "self.ads.gain = 1  # 4.096V max, optimized for 3.3V supply + voltage dividers"
if old_gain in reader:
    reader = reader.replace(old_gain, new_gain)
    with open(SENSOR_READER, "w", encoding="utf-8") as f:
        f.write(reader)
    print("✅ Software successfully updated for Hardware Voltage Dividers!")
else:
    print("Could not find the gain setting. It may have already been patched.")
