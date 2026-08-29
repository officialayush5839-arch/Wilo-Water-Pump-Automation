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
        
        # Initialize the A0 and A1 channels
        chan0 = AnalogIn(ads, 0)
        chan1 = AnalogIn(ads, 1)
        
    except Exception as e:
        print(f"❌ Failed to initialize ADS1115: {e}")
        return

    print("✅ Connected! Reading A0 and A1 (Press Ctrl+C to stop)...\n")
    print("      A0 PIN          |         A1 PIN      ")
    print("-" * 50)
    
    try:
        while True:
            try:
                # Read Voltage
                v0 = chan0.voltage
                v1 = chan1.voltage
                
                # Read Raw ADC Integer (0 to 32767)
                raw0 = chan0.value
                raw1 = chan1.value
                
                print(f" A0: {v0:.3f}V ({raw0:>5})  |  A1: {v1:.3f}V ({raw1:>5})")
                time.sleep(0.5)
                
            except OSError as e:
                print(f" I2C Read Error: {e}")
                time.sleep(1)
            
    except KeyboardInterrupt:
        print("\nStopped.")

if __name__ == "__main__":
    read_extra_pins()
