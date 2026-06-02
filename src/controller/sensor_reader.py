"""
Current & Voltage Sensor Reader (ADS1115 + ACS712T + ZMPT101B)
===============================================================
Reads analog sensors via ADS1115 I2C ADC on the Raspberry Pi.

IMPORTANT: Both ACS712T and ZMPT101B output 0-5 V.
           The ADS1115 must be powered by 5V and configured with
           gain=2/3 to read the full range without a voltage divider.
           See HARDWARE.md for wiring.

If the ADS1115 is not connected, this module operates in
"degraded" mode — all reads return None and the pump controller
falls back to LoRa-only upper-tank data.
"""

import time
import math
import logging
from typing import Optional

logger = logging.getLogger('wilo.sensors')

# ── Try importing ADS1115 library (only works on real Pi) ──
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
    """Reads ACS712T (current) and ZMPT101B (voltage) via ADS1115."""

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
        self.available   = False

    def initialize(self) -> bool:
        if not _ADS_OK:
            logger.warning("ADS1115 library not installed → sensor reading disabled. "
                           "Install: pip3 install adafruit-circuitpython-ads1x15")
            return False
        try:
            i2c = busio.I2C(board.SCL, board.SDA)
            self.ads = ADS.ADS1115(i2c, address=self.adc_addr)
            self.ads.gain = 2/3                     # ±6.144 V (allows 0-5 V)
            # Newer adafruit_ads1x15 releases accept integer channel indices
            # directly and may not expose ADS.P0..ADS.P3 constants.
            self.chan_i = AnalogIn(self.ads, self.ch_i)
            self.chan_v = AnalogIn(self.ads, self.ch_v)
            self.available = True
            logger.info(f"ADS1115 OK  current→A{self.ch_i}  voltage→A{self.ch_v}")
            return True
        except Exception as e:
            logger.error(f"ADS1115 init failed: {e}")
            return False

    # ── Current (ACS712T) ────────────────────────────────────

    def read_current_rms(self, samples: int = 200) -> Optional[float]:
        """Return RMS current in amps, or None."""
        if not self.available:
            return None
        try:
            sq_sum = 0.0
            for _ in range(samples):
                v_adc    = self.chan_i.voltage
                v_sensor = v_adc / self.acs_div        # undo divider
                i_inst   = (v_sensor - self.acs_zero) / self.sensitivity
                sq_sum  += i_inst * i_inst
                time.sleep(0.0001)                     # ~100 µs → covers 50 Hz
            return round(math.sqrt(sq_sum / samples), 2)
        except Exception as e:
            logger.error(f"Current read error: {e}")
            return None

    # ── Voltage (ZMPT101B) ───────────────────────────────────

    def read_voltage_rms(self, samples: int = 200) -> Optional[float]:
        """Return RMS mains voltage, or None."""
        if not self.available:
            return None
        try:
            sq_sum = 0.0
            for _ in range(samples):
                v_adc    = self.chan_v.voltage
                v_sensor = v_adc / self.zmpt_div
                v_inst   = (v_sensor - self.zmpt_zero) * self.zmpt_cal
                sq_sum  += v_inst * v_inst
                time.sleep(0.0001)
            return round(math.sqrt(sq_sum / samples), 1)
        except Exception as e:
            logger.error(f"Voltage read error: {e}")
            return None

    # ── Combined read ────────────────────────────────────────

    def read_all(self) -> dict:
        return {
            'current_amps': self.read_current_rms(),
            'voltage_ac':   self.read_voltage_rms(),
            'available':    self.available,
        }
