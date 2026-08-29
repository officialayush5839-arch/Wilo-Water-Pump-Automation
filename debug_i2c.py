import time
import board
import busio
from adafruit_ads1x15.ads1115 import ADS1115
from adafruit_ads1x15.analog_in import AnalogIn

def scan_bus(i2c):
    print("Scanning I2C Bus for devices...")
    try:
        while not i2c.try_lock():
            pass
        addrs = i2c.scan()
        i2c.unlock()
    except Exception as e:
        print(f"❌ Failed to scan bus: {e}")
        return []

    if not addrs:
        print("❌ NO I2C DEVICES FOUND! The wiring is completely disconnected or the chip is dead.")
    else:
        addr_hex = [hex(a) for a in addrs]
        print(f"🔍 Found devices at: {', '.join(addr_hex)}")
        if "0x48" not in addr_hex:
            print("❌ The ADS1115 is NOT at 0x48. Connect the ADDR pin to GND!")
    print("-" * 50)
    return addr_hex

def stress_test():
    print("Initializing I2C Stress Test...")
    try:
        i2c = busio.I2C(board.SCL, board.SDA)
    except Exception as e:
        print(f"❌ Failed to initialize I2C hardware: {e}")
        return
        
    found = scan_bus(i2c)
    if "0x48" not in found:
        print("Aborting stress test because ADS1115 is not at 0x48.")
        return

    try:
        ads = ADS1115(i2c, address=0x48)
        chan = AnalogIn(ads, 0)
    except Exception as e:
        print(f"❌ Failed to initialize ADS1115 object: {e}")
        return

    print("✅ Connected to ADS1115. Starting rapid-fire read test...")
    print("If it drops, gently wiggle your wires to test for loose connections!\n")
    
    success_count = 0
    fail_count = 0
    
    try:
        while True:
            try:
                # Read the voltage as fast as possible to stress the bus
                val = chan.voltage
                success_count += 1
                
                if success_count % 50 == 0:
                    print(f"✅ {success_count} consecutive successful reads... (Stable)")
                    
                time.sleep(0.05)
                
            except Exception as e:
                fail_count += 1
                print(f"❌ ERROR {e}! The connection dropped after {success_count} successful reads.")
                success_count = 0
                
                # Check if the address drifted
                scan_bus(i2c)
                time.sleep(2)
                
    except KeyboardInterrupt:
        print(f"\nTest stopped. Total Drops: {fail_count}")

if __name__ == '__main__':
    stress_test()
