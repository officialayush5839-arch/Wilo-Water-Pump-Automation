import time
import sys

# Import your existing config and sensor reader
import src.controller.tank_config as CFG
from src.controller.sensor_reader import SensorReader

def monitor():
    print("Initializing Power Monitor...")
    
    # Initialize using your exact config settings
    reader = SensorReader(
        acs_model=CFG.ACS712_MODEL, 
        acs_zero_v=CFG.ACS712_ZERO_V,
        acs_divider=CFG.ACS712_DIVIDER_RATIO,
        zmpt_cal=CFG.ZMPT101B_CAL_FACTOR, 
        zmpt_zero_v=CFG.ZMPT101B_ZERO_V,
        zmpt_divider=CFG.ZMPT101B_DIVIDER_RATIO,
        adc_addr=CFG.ADS1115_ADDRESS
    )
    
    if not reader.initialize():
        print("❌ ERROR: Failed to connect to ADS1115.")
        sys.exit(1)
        
    print("✅ ADS1115 Connected successfully!")
    print(f"Hardware Config: Current Divider={CFG.ACS712_DIVIDER_RATIO}x, Voltage Divider={CFG.ZMPT101B_DIVIDER_RATIO}x")
    print("Monitoring Live Data (Press Ctrl+C to stop)...\n")
    print("-" * 50)
    
    try:
        while True:
            # Read from the sensors
            data = reader.read_all()
            amps = data.get('current_amps')
            volts = data.get('voltage_ac')
            
            # Format the output
            amps_str = f"{amps:>5.2f} A" if amps is not None else "  N/A  "
            volts_str = f"{volts:>5.1f} V" if volts is not None else "  N/A  "
            
            # Calculate Power (Watts) if both sensors are working
            if amps is not None and volts is not None:
                watts_str = f"{(amps * volts):>6.1f} W"
            else:
                watts_str = "   N/A   "
                
            print(f"Voltage: {volts_str}   |   Current: {amps_str}   |   Power: {watts_str}")
            time.sleep(1)
            
    except KeyboardInterrupt:
        print("\nMonitoring stopped.")

if __name__ == "__main__":
    monitor()
