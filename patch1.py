cat << 'EOF' > src/controller/sensor_reader.py
"""
Current & Voltage Sensor Reader (ADS1115 + ACS712T + ZMPT101B)
===============================================================
Reads analog sensors via ADS1115 I2C ADC on the Raspberry Pi.

IMPORTANT: Both ACS712T and ZMPT101B output 0-5 V.
           The ADS1115 must be powered by 5V and configured with
           gain=2/3 to read the full range without a voltage divider.
           See HARDWARE.md for wiring.
"""

import time
import math
import logging
from typing import Optional

logger = logging.getLogger('wilo.sensors')

_ADS_OK = False
try:
    import board
    import busio
    import adafruit_ads1x15.ads1115 as ADS
    from adafruit_ads1x15.analog_in import AnalogIn
    _ADS_OK = True
except ImportError:
    pass

class SensorReader:
    def __init__(self, acs_model='30A', acs_zero_v=2.5,
                 acs_divider=1.0, zmpt_cal=1.0,
                 zmpt_zero_v=2.5, zmpt_divider=1.0,
                 adc_addr=0x48, ch_current=0, ch_voltage=1):
        self.sensitivity = {'5A': 0.185, '20A': 0.100, '30A': 0.066}[acs_model]
        self.acs_zero    = acs_zero_v
        self.acs_div     = acs_divider
        self.zmpt_cal    = zmpt_cal
        self.zmpt_zero   = zmpt_zero_v
        self.zmpt_div    = zmpt_divider
        self.adc_addr    = adc_addr
        self.ch_i        = ch_current
        self.ch_v        = ch_voltage

        self.ads         = None
        self.chan_i       = None
        self.chan_v       = None
        self.acs_midpoint = 2.5
        self.zmpt_midpoint = 2.5
        self.available   = False

    def initialize(self) -> bool:
        if not _ADS_OK:
            logger.warning("ADS1115 library not installed -> sensor reading disabled.")
            return False
        try:
            i2c = busio.I2C(board.SCL, board.SDA)
            self.ads = ADS.ADS1115(i2c, address=self.adc_addr)
            self.ads.gain = 2/3                     # +/- 6.144 V (allows 0-5 V)
            
            self.chan_i = AnalogIn(self.ads, self.ch_i)
            self.chan_v = AnalogIn(self.ads, self.ch_v)
            
            logger.info("Calibrating True Zero-Point for sensors... (Ensure pump is OFF)")
            raw_i = []
            raw_v_list = []
            for _ in range(250):
                raw_i.append(self.chan_i.voltage / self.acs_div)
                raw_v_list.append(self.chan_v.voltage / self.zmpt_div)
                time.sleep(0.002)
                
            # FREEZE THE MIDPOINTS FOREVER!
            self.acs_midpoint = sum(raw_i) / len(raw_i)
            self.zmpt_midpoint = sum(raw_v_list) / len(raw_v_list)
            
            self.available = True
            logger.info(f"ADS1115 OK  current->A{self.ch_i} ({self.acs_midpoint:.3f}V zero)  voltage->A{self.ch_v} ({self.zmpt_midpoint:.3f}V zero)")
            return True
        except Exception as e:
            logger.error(f"ADS1115 init failed: {e}")
            return False

    def read_current_rms(self, samples: int = 60) -> Optional[float]:
        if not self.available:
            return None
        try:
            raw_v = []
            for _ in range(samples):
                raw_v.append(self.chan_i.voltage / self.acs_div)
                time.sleep(0.002)
            
            dc_offset = self.acs_midpoint
            
            sq_sum = 0.0
            for v_sensor in raw_v:
                i_inst = (v_sensor - dc_offset) / self.sensitivity
                sq_sum += i_inst * i_inst
                
            rms_amps = math.sqrt(sq_sum / samples)
            current_a = rms_amps * 1.55 # Calibration Scaling Factor
            
            if current_a < 0.30: # Noise Deadband
                current_a = 0.0
                
            return round(current_a, 2)
        except Exception as e:
            logger.error(f"Current read error: {e}")
            return None

    def read_voltage_rms(self, samples: int = 60) -> Optional[float]:
        if not self.available:
            return None
        try:
            raw_v = []
            for _ in range(samples):
                raw_v.append(self.chan_v.voltage / self.zmpt_div)
                time.sleep(0.002)
            
            dc_offset = self.zmpt_midpoint
            
            sq_sum = 0.0
            for v_sensor in raw_v:
                v_inst = (v_sensor - dc_offset) * self.zmpt_cal
                sq_sum += v_inst * v_inst
                
            return round(math.sqrt(sq_sum / samples), 1)
        except Exception as e:
            logger.error(f"Voltage read error: {e}")
            return None

    def read_all(self) -> dict:
        return {
            'current_amps': self.read_current_rms(),
            'voltage_ac':   self.read_voltage_rms(),
            'available':    self.available,
        }
EOF
