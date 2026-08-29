import os

SENSOR_READER = "src/controller/sensor_reader.py"

with open(SENSOR_READER, "r", encoding="utf-8") as f:
    code = f.read()

old_current = """    def read_current_rms(self, samples: int = 60) -> Optional[float]:
        \"\"\"Return RMS current in amps, or None.\"\"\"
        if not self.available:
            return None
        try:
            raw_v = []
            for _ in range(samples):
                raw_v.append(self.chan_i.voltage / self.acs_div)
            
            # Dynamic DC offset removal to eliminate Ghost Amps
            dc_offset = sum(raw_v) / len(raw_v)
            
            sq_sum = 0.0
            for v_sensor in raw_v:
                i_inst = (v_sensor - dc_offset) / self.sensitivity
                sq_sum += i_inst * i_inst
                
            return round(math.sqrt(sq_sum / samples), 2)
        except Exception as e:
            logger.error(f"Current read error: {e}")
            return None"""

new_current = """    def read_current_rms(self, samples: int = 60) -> Optional[float]:
        \"\"\"Return RMS current in amps, or None.\"\"\"
        if not self.available:
            return None
        try:
            raw_v = []
            for _ in range(samples):
                raw_v.append(self.chan_i.voltage / self.acs_div)
                time.sleep(0.002) # Anti-flood delay
            
            dc_offset = sum(raw_v) / len(raw_v)
            
            sq_sum = 0.0
            for v_sensor in raw_v:
                i_inst = (v_sensor - dc_offset) / self.sensitivity
                sq_sum += i_inst * i_inst
                
            rms_amps = math.sqrt(sq_sum / samples)
            
            # 1.55 Calibration Scaling Factor
            current_a = rms_amps * 1.55
            
            # Noise Floor Deadband
            if current_a < 0.30:
                current_a = 0.0
                
            return round(current_a, 2)
        except Exception as e:
            logger.error(f"Current read error: {e}")
            return None"""

old_voltage = """    def read_voltage_rms(self, samples: int = 60) -> Optional[float]:
        \"\"\"Return RMS mains voltage, or None.\"\"\"
        if not self.available:
            return None
        try:
            raw_v = []
            for _ in range(samples):
                raw_v.append(self.chan_v.voltage / self.zmpt_div)
            
            # Dynamic DC offset removal to eliminate 82V Ghost Voltage
            dc_offset = sum(raw_v) / len(raw_v)
            
            sq_sum = 0.0
            for v_sensor in raw_v:
                v_inst = (v_sensor - dc_offset) * self.zmpt_cal
                sq_sum += v_inst * v_inst
                
            return round(math.sqrt(sq_sum / samples), 1)
        except Exception as e:
            logger.error(f"Voltage read error: {e}")
            return None"""

new_voltage = """    def read_voltage_rms(self, samples: int = 60) -> Optional[float]:
        \"\"\"Return RMS mains voltage, or None.\"\"\"
        if not self.available:
            return None
        try:
            raw_v = []
            for _ in range(samples):
                raw_v.append(self.chan_v.voltage / self.zmpt_div)
                time.sleep(0.002) # Anti-flood delay
            
            dc_offset = sum(raw_v) / len(raw_v)
            
            sq_sum = 0.0
            for v_sensor in raw_v:
                v_inst = (v_sensor - dc_offset) * self.zmpt_cal
                sq_sum += v_inst * v_inst
                
            return round(math.sqrt(sq_sum / samples), 1)
        except Exception as e:
            logger.error(f"Voltage read error: {e}")
            return None"""

if old_voltage in code:
    code = code.replace(old_current, new_current)
    code = code.replace(old_voltage, new_voltage)
    with open(SENSOR_READER, "w", encoding="utf-8") as f:
        f.write(code)
    print("✅ Wilo main sensor_reader.py patched successfully!")
else:
    print("Could not find the old code block. Maybe it was already patched?")
