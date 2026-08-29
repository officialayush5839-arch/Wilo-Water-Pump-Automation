import os

SENSOR_READER = "src/controller/sensor_reader.py"

with open(SENSOR_READER, "r", encoding="utf-8") as f:
    code = f.read()

# Lower the sample count and increase the sleep time so the 10kHz bus can keep up!
code = code.replace("samples: int = 200", "samples: int = 40")
code = code.replace("time.sleep(0.0001)", "time.sleep(0.002)")

with open(SENSOR_READER, "w", encoding="utf-8") as f:
    f.write(code)
print("✅ sensor_reader.py patched successfully to prevent I2C flooding!")
