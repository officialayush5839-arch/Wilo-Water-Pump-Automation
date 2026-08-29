import os

FILE = "src/controller/sensor_reader.py"
with open(FILE, "r") as f:
    code = f.read()

old_code = 'logger.info("Calibrating True Zero-Point for sensors... (Ensure pump is OFF)")'
new_code = '''logger.info("Waiting 3 seconds to ensure pump is completely off before calibration...")
            time.sleep(3)
            logger.info("Calibrating True Zero-Point for sensors...")'''

if old_code in code:
    with open(FILE, "w") as f:
        f.write(code.replace(old_code, new_code))
    print("✅ 3-second safety delay added successfully!")
else:
    print("❌ Could not find calibration line. Are you sure you ran the previous script?")
