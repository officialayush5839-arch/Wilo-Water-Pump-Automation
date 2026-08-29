import time
import math
import board
import busio
import adafruit_ads1x15.ads1115 as ADS
from adafruit_ads1x15.analog_in import AnalogIn

# --- ZMPT101B Configuration ---
ZMPT_DIVIDER = 1.0           # Hardware voltage divider ratio (if any)
ZMPT_CAL = 209.09090909               # Calibration Multiplier (Tune this to match a multimeter!)
NUM_SAMPLES_RMS = 60         # Number of samples for each RMS reading
I2C_DELAY = 0.002            # I2C anti-flood delay (2ms)

def auto_midpoint(chan_v):
    print("--- ZMPT101B Voltage Calibration ---")
    print("Ensure pump is OFF now.")
    for i in range(3, 0, -1):
        print(f"Calibrating in {i}...")
        time.sleep(1)
        
    print("Finding zero-point... please wait.")
    
    raw_v = []
    for _ in range(250):
        raw_v.append(chan_v.voltage / ZMPT_DIVIDER)
        time.sleep(I2C_DELAY)
        
    midpoint = sum(raw_v) / len(raw_v)
    print(f"✅ Calibration Done. True Zero-Point found at {midpoint:.3f}V")
    print("You can turn the pump ON now.\n")
    print("-" * 40)
    return midpoint

def monitor():
    print("Initializing I2C and ADS1115...")
    try:
        i2c = busio.I2C(board.SCL, board.SDA)
        ads = ADS.ADS1115(i2c, address=0x48)
        
        # Set gain to 2/3 (reads up to 6.144V max)
        ads.gain = 2/3 
        
        # ZMPT101B Voltage sensor is connected to A1
        chan_v = AnalogIn(ads, 1)
        
    except Exception as e:
        print(f"❌ Failed to initialize ADS1115: {e}")
        return
        
    # Calculate the exact zero point before starting
    midpoint = auto_midpoint(chan_v)
    
    try:
        while True:
            raw_v = []
            for _ in range(NUM_SAMPLES_RMS):
                raw_v.append(chan_v.voltage / ZMPT_DIVIDER)
                time.sleep(I2C_DELAY)
                
            sq_sum = 0.0
            for v_sensor in raw_v:
                # Calculate instantaneous voltage variation from zero point
                v_inst = (v_sensor - midpoint) * ZMPT_CAL
                sq_sum += v_inst * v_inst
                
            # Calculate True RMS
            rms_volts = math.sqrt(sq_sum / NUM_SAMPLES_RMS)
            
            print(f"Mains Voltage: {rms_volts:.1f} V")
            time.sleep(1.0)
            
    except KeyboardInterrupt:
        print("\nStopped.")

if __name__ == "__main__":
    monitor()
