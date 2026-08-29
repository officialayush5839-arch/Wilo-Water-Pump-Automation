import time
import math
import board
import busio
import adafruit_ads1x15.ads1115 as ADS
from adafruit_ads1x15.analog_in import AnalogIn

# --- Calibration Factors (From your config) ---
ZMPT_DIVIDER = 0.5  
ACS_DIVIDER = 0.5
VOLTAGE_CAL_FACTOR = 235.1
CURRENT_SCALING_FACTOR = 1.0
SENSITIVITY = 0.066  # 66mV/A for ACS712-30A
NUM_SAMPLES = 60

def measure_voltage(chan_v):
    # 1. Read Raw Samples
    raw_v = []
    for _ in range(NUM_SAMPLES):
        raw_v.append(chan_v.voltage / ZMPT_DIVIDER)
        time.sleep(0.002) # Anti-flood delay for the slow 10kHz I2C bus
        
    # 2. Find DC Offset (Arduino's 'offset' variable)
    offset = sum(raw_v) / len(raw_v)
    
    # 3. Sum of Squares
    sum_squares = 0.0
    for v in raw_v:
        v_inst = (v - offset)
        sum_squares += v_inst * v_inst
        
    # 4. RMS and Scale
    rms = math.sqrt(sum_squares / NUM_SAMPLES)
    return rms * VOLTAGE_CAL_FACTOR

def measure_current(chan_i):
    # 1. Read Raw Samples
    raw_v = []
    for _ in range(NUM_SAMPLES):
        raw_v.append(chan_i.voltage / ACS_DIVIDER)
        time.sleep(0.002) # Anti-flood delay for the slow 10kHz I2C bus
        
    # 2. Auto MidPoint (Replicates ACS.autoMidPoint())
    midpoint = sum(raw_v) / len(raw_v)
    
    # 3. Sum of Squares
    sum_squares = 0.0
    for v in raw_v:
        i_inst = (v - midpoint) / SENSITIVITY
        sum_squares += i_inst * i_inst
        
    rms_amps = math.sqrt(sum_squares / NUM_SAMPLES)
    
    # 4. Scale and apply DEADBAND NOISE FILTER (Replicates Arduino logic!)
    current_a = rms_amps * CURRENT_SCALING_FACTOR
    
    # If the reading is below the 0.30A magnetic noise floor, force it to 0.0A
    if current_a < 0.30: 
        current_a = 0.0
        
    return current_a

def monitor():
    print("Initializing I2C and ADS1115...")
    try:
        i2c = busio.I2C(board.SCL, board.SDA)
        ads = ADS.ADS1115(i2c, address=0x48)
        ads.gain = 1  # 4.096V max range
        
        # A1 = Voltage (ZMPT_PIN), A0 = Current (ACS_PIN)
        chan_v = AnalogIn(ads, 1)
        chan_i = AnalogIn(ads, 0)
    except Exception as e:
        print(f"Failed to init ADS1115: {e}")
        return

    print("✅ Ready! Starting Arduino-Style Monitor Loop...")
    print("-" * 60)

    try:
        while True:
            # 1. Measure Voltage
            voltage = measure_voltage(chan_v)
            
            # 2. Measure Current
            current_a = measure_current(chan_i)
            
            # 3. Calculate Power
            power_w = voltage * current_a
            
            # --- Relay Logic ---
            if power_w > 200.0:
                relay1_state = "LOW (Overload)"
            else:
                relay1_state = "HIGH (Normal)"
            
            # --- Serial Output ---
            print(f"V: {voltage:>5.1f} | A: {current_a:>4.2f} | W: {power_w:>4.0f} | Relay1: {relay1_state}")
            
            time.sleep(0.5)
            
    except KeyboardInterrupt:
        print("\nStopped.")

if __name__ == "__main__":
    monitor()
