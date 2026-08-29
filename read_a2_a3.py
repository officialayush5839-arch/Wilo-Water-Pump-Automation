import time
import board
import busio
import adafruit_ads1x15.ads1115 as ADS
from adafruit_ads1x15.analog_in import AnalogIn

def read_extra_pins():
    print("Initializing I2C and ADS1115...")
    try:
        i2c = busio.I2C(board.SCL, board.SDA)
        ads = ADS.ADS1115(i2c, address=0x48)
        
        # Set gain to 1 (reads up to 4.096V max). 
        ads.gain = 1
        
        # Initialize the A2 and A3 channels using just integer numbers!
        chan2 = AnalogIn(ads, 2)
        chan3 = AnalogIn(ads, 3)
        
    except Exception as e:
        print(f"❌ Failed to initialize ADS1115: {e}")
        return

    print("✅ Connected! Reading A2 and A3 (Press Ctrl+C to stop)...\n")
    print("      A2 PIN          |         A3 PIN      ")
    print("-" * 50)
    
    try:
        while True:
            try:
                # Read Voltage
                v2 = chan2.voltage
                v3 = chan3.voltage
                
                # Read Raw ADC Integer (0 to 32767)
                raw2 = chan2.value
                raw3 = chan3.value
                
                print(f" A2: {v2:.3f}V ({raw2:>5})  |  A3: {v3:.3f}V ({raw3:>5})")
                time.sleep(0.5)
                
            except OSError as e:
                print(f" I2C Read Error: {e}")
                time.sleep(1)
            
    except KeyboardInterrupt:
        print("\nStopped.")

if __name__ == "__main__":
    read_extra_pins()
