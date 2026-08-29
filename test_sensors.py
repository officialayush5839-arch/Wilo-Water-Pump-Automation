import time
import sys

# Import your existing sensor reader class
from src.controller.sensor_reader import SensorReader

def test():
    print("Initializing SensorReader...")
    reader = SensorReader(acs_model='30A', adc_addr=0x48)
    
    if not reader.initialize():
        print("❌ ERROR: Failed to connect to ADS1115.")
        print("Please check your wiring: 5V, GND, SDA, and SCL.")
        sys.exit(1)
        
    print("✅ ADS1115 Connected successfully!")
    print("Reading data (Press Ctrl+C to stop)...\n")
    
    try:
        while True:
            data = reader.read_all()
            amps = data.get('current_amps')
            volts = data.get('voltage_ac')
            
            # Formatting to handle None if a read fails
            amps_str = f"{amps:.2f} A" if amps is not None else "N/A"
            volts_str = f"{volts:.1f} V" if volts is not None else "N/A"
            
            print(f"Current: {amps_str}   |   Voltage: {volts_str}")
            time.sleep(1)
            
    except KeyboardInterrupt:
        print("\nTest stopped.")

if __name__ == "__main__":
    test()
