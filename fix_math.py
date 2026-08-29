import os

TANK_CONFIG = "src/controller/tank_config.py"

with open(TANK_CONFIG, "r", encoding="utf-8") as f:
    config = f.read()

# Fix the division math to properly undo the hardware voltage divider
config = config.replace("ACS712_DIVIDER_RATIO  = 2.0", "ACS712_DIVIDER_RATIO  = 0.5")
config = config.replace("ZMPT101B_DIVIDER_RATIO = 2.0", "ZMPT101B_DIVIDER_RATIO = 0.5")

with open(TANK_CONFIG, "w", encoding="utf-8") as f:
    f.write(config)
print("✅ Math multipliers successfully fixed!")
