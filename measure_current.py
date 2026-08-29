import time
import math
import board
import busio
import adafruit_ads1x15.ads1115 as ADS
from adafruit_ads1x15.analog_in import AnalogIn

# --- Configuration matching Arduino ---
ACS_DIVIDER = 0.5            # Reverses your hardware voltage divider
SENSITIVITY = 0.066          # 100 mV/A for 20A sensor (0.100 V/A)
SCALING_FACTOR = 1.55        # Your custom calibration scaling factor
NUM_SAMPLES_RMS = 60         # Number of samples for each RMS reading
I2C_DELAY = 0.002            # I2C anti-flood delay

def auto_midpoint(chan_i):
    """Replicates Arduino ACS.autoMidPoint()"""
    print("--- ACS712 Calibration ---")
    print("Ensure heater/pump is OFF now.")
    for i in range(3, 0, -1):
        print(f"Calibrating in {i}...")
        time.sleep(1)
        
    print("Finding zero-point... please wait.")
    
    # Read a large number of samples to find the exact DC offset
    raw_v = []
    for _ in range(250):
        raw_v.append(chan_i.voltage / ACS_DIVIDER)
        time.sleep(I2C_DELAY)
        
    calculated_midpoint = sum(raw_v) / len(raw_v)
    print(f"✅ Calibration Done. True Zero-Point found at {calculated_midpoint:.3f}V")
    print("You can turn the heater/pump ON now.\n")
    return calculated_midpoint

def measure_current(chan_i, midpoint):
    """Replicates ACS.mA_AC(50) and the scaling logic"""
    # 1. Read Raw Samples
    raw_v = []
    for _ in range(NUM_SAMPLES_RMS):
        raw_v.append(chan_i.voltage / ACS_DIVIDER)
        time.sleep(I2C_DELAY)
    
    # 2. Sum of Squares against the calibrated midpoint
    sum_squares = 0.0
    for v in raw_v:
        # v - midpoint = instantaneous voltage
        # / SENSITIVITY = instantaneous current in Amps
        i_inst = (v - midpoint) / SENSITIVITY
        sum_squares += i_inst * i_inst
        
    # 3. Calculate RMS
    rms_amps = math.sqrt(sum_squares / NUM_SAMPLES_RMS)
    
    # 4. Apply Scaling Factor
    current_a = rms_amps * SCALING_FACTOR
    
    # 5. Apply Noise floor: if current is tiny, force it to zero
    if current_a < 0.15:
        current_a = 0.0
        
    return current_a

def monitor():
    try:
        i2c = busio.I2C(board.SCL, board.SDA)
        ads = ADS.ADS1115(i2c, address=0x48)
        ads.gain = 1  
        
        # A0 = Current (ACS_PIN)
        chan_i = AnalogIn(ads, 0)
    except Exception as e:
        print(f"❌ Failed to init ADS1115: {e}")
        return

    # Run the setup() calibration
    global_midpoint = auto_midpoint(chan_i)

    print("-" * 40)

    try:
        while True:
            # Replicate loop()
            current_a = measure_current(chan_i, global_midpoint)
            
            # Calculate approximate power (Assuming 230V)
            power_w = current_a * 230.0
            
            # Print exactly like Arduino Serial output
            print(f"Current: {current_a:>4.2f} A | Appx Power: {power_w:>4.0f} W")
            
            # delay(1000)
            time.sleep(1.0)
            
    except KeyboardInterrupt:
        print("\nStopped.")

if __name__ == "__main__":
    monitor()
