"""
Wilo Water Pump Automation — RPi Configuration
================================================
All hardware pins, thresholds, and parameters in one place.
Edit this file before deployment. Placeholders marked with # PLACEHOLDER.
"""

import os

# ============================================================
# GPIO PIN ASSIGNMENTS (BCM numbering)
# See HARDWARE.md for full wiring diagram
# ============================================================

# ── LoRa SX1278 Module (SPI0) ──
LORA_SPI_BUS      = 0
LORA_SPI_CS       = 0        # CE0 → GPIO 8  (Physical Pin 24)
LORA_RESET_PIN    = 25       # GPIO 25 (Physical Pin 22)
LORA_DIO0_PIN     = 24       # GPIO 24 (Physical Pin 18)
LORA_FREQUENCY    = 433E6    # Must match ESP32
LORA_SYNC_WORD    = 0xF3     # Must match ESP32

# ── Relay Module ──
RELAY_PUMP_PIN    = 17       # GPIO 17 (Physical Pin 11)
RELAY_VALVE_PIN   = 27       # GPIO 27 (Physical Pin 13) — spare / inlet valve
RELAY_ACTIVE_LOW  = False     # True = active-LOW (GPIO LOW → relay ON, HIGH → relay OFF) for standard 1ch 5V relay

# ── Manual Override Buttons (normally-open, pull-up) ──
BUTTON_FORCE_ON   = 22       # GPIO 22 (Physical Pin 15)
BUTTON_FORCE_OFF  = 5        # GPIO 5  (Physical Pin 29)

# ── Status LED (optional) ──
LED_STATUS_PIN    = 6        # GPIO 6  (Physical Pin 31)

# ── ADS1115 ADC (I2C1) ──
ADS1115_ADDRESS   = 0x48     # ADDR → GND
ADC_CH_CURRENT    = 0        # ACS712T  → A0
ADC_CH_VOLTAGE    = 1        # ZMPT101B → A1

# ============================================================
# TANK CONFIGURATION
# ============================================================

# Upper Tank (rooftop) — measured by ESP32 pressure sensor
UPPER_TANK_CAPACITY_L  = 25000
UPPER_TANK_HEIGHT_CM   = 200     # PLACEHOLDER — measure and update!
UPPER_TANK_DIAMETER_CM = 180     # PLACEHOLDER — measure and update!
WATER_DENSITY = 998.0   # kg/m³ at ~20 °C
GRAVITY       = 9.81    # m/s²

# Pressure sensor calibration — subtract this from raw reading to zero the sensor
# (sensor reads atmospheric + water column; this removes the atmospheric baseline)
# Set by reading the sensor with an EMPTY tank and updating this value
PRESSURE_OFFSET_KPA = 23.0   # Calibrated 2026-06-04: empty-tank LoRa reading ~22.5-23.5 kPa

# ============================================================
# PUMP CONTROL THRESHOLDS (percentage of upper tank)
# ============================================================

UPPER_CRITICAL_LOW  = 10   # Emergency ON — tank nearly empty
UPPER_LOW           = 25   # Normal threshold — pump should be running
UPPER_HIGH          = 85   # Normal threshold — pump can stop
UPPER_CRITICAL_HIGH = 95   # Emergency OFF — overflow risk

# Hysteresis band: pump turns ON at LOW, turns OFF at HIGH
# Prevents rapid cycling

# ============================================================
# ACS712T CURRENT SENSOR
# ============================================================

ACS712_MODEL          = '30A'           # '5A', '20A', or '30A'
ACS712_ZERO_V         = 2.5             # Midpoint of 0–5 V supply (V at 0 A)
ACS712_DIVIDER_RATIO  = 0.5   # No voltage divider used

# ============================================================
# ZMPT101B VOLTAGE SENSOR
# ============================================================

ZMPT101B_CAL_FACTOR    = 209.09    # PLACEHOLDER — calibrate with multimeter
ZMPT101B_ZERO_V        = 2.5   # Midpoint of 0–5 V supply
ZMPT101B_DIVIDER_RATIO = 0.5

# ============================================================
# PUMP SPECIFICATIONS (Wilo)
# ============================================================

PUMP_RATED_CURRENT_A     = 8.0    # PLACEHOLDER — check nameplate
PUMP_MIN_RUNNING_A       = 3.0    # Below = not pumping properly
PUMP_DRY_RUN_CURRENT_A   = 1.5    # Below while relay ON = dry run
PUMP_FLOW_RATE_LPM       = 100    # PLACEHOLDER — check Wilo datasheet

# ============================================================
# SAFETY SETTINGS
# ============================================================

LORA_TIMEOUT_S           = 60     # No LoRa packet in this time → pump OFF
REQUIRE_VALID_LORA_BEFORE_START = True  # Block starts until at least one clean LoRa packet arrives
MAX_CONTINUOUS_RUN_MIN   = 180    # Hard limit — auto-stop
DRY_RUN_PROTECTION       = False   # Enable only after ACS712 is installed and calibrated on the real pump line
POWER_VOLTAGE_PROTECTION = False   # Enable only after ZMPT101B is calibrated with real mains input
MIN_MAINS_VOLTAGE_AC     = 180.0   # Placeholder undervoltage cutoff for future use
POWER_RESTORE_DELAY_S    = 30     # Wait after power-cut before pump

# ============================================================
# MANUAL OVERRIDE
# ============================================================

OVERRIDE_TIMEOUT_MIN     = 1440   # Auto-release override after this (24h safety net)
OVERRIDE_DEBOUNCE_MS     = 200    # Button debounce

# ============================================================
# ML PREDICTION
# ============================================================

ML_ENABLED               = True
ML_CHECK_INTERVAL_MIN    = 15     # Re-run prediction cycle
ML_ACTIVATION_WINDOW_MIN = 5      # Tolerance around predicted start

# ============================================================
# CURRENT-BASED TANK STATE CLASSIFICATION (Wilo Pump Load)
# ============================================================

CURRENT_EMPTY_THRESHOLD        = 11.5   # >= 11.5 A: Tank considered EMPTY / high load
CURRENT_MID_LOW                = 8.0    # 8.0 A - 10.0 A: Tank considered ~50% MID LEVEL
CURRENT_MID_HIGH               = 10.0   #
CURRENT_FULL_THRESHOLD         = 6.5    # <= 6.5 A: Tank considered FULL / high backpressure
CURRENT_FILTER_WINDOW          = 10     # Rolling median filter sample window
CURRENT_STARTUP_BLANKING_SEC   = 5.0    # Ignore current classification for 5s on pump startup
CURRENT_FULL_PERSISTENCE_SEC   = 5.0    # Must persist <= 6.5 A for 5s continuously to trigger FULL stop
CURRENT_STOP_ON_FULL_ENABLED   = True   # Automatically stop pump when current-based FULL persists

# ============================================================
# MUNICIPAL WATER CUT & FESTIVAL POLICY MANAGEMENT
# ============================================================

WATER_CUT_DEFAULT_RESERVE      = 95.0   # Target tank reserve (%) prior to municipal cut
WATER_CUT_DEFAULT_PREFILL_HOURS = 4.0   # Pre-fill lead time window in hours

FESTIVAL_MODE_DEFAULT          = True   # Festival policy active by default
FESTIVAL_RELEASE_HOUR          = 19     # 19:00 IST release time for Rang Panchami

# ============================================================
# LOGGING & PATHS
# ============================================================

_BASE = os.path.dirname(os.path.abspath(__file__))
_PROJECT = os.path.join(_BASE, '..', '..')

LOG_DIR        = os.path.join(_PROJECT, 'logs', 'pump')
LORA_LOG_DIR   = os.path.join(_PROJECT, 'logs', 'lora')
DATA_DIR       = os.path.join(_PROJECT, 'data')
CONFIG_DIR     = os.path.join(_PROJECT, 'config')
WATER_CUTS_FILE = os.path.join(CONFIG_DIR, 'water_cuts.json')
FESTIVAL_STATE_FILE = os.path.join(CONFIG_DIR, 'festival_state.json')
HOLIDAY_CSV_PATH = os.path.join(DATA_DIR, 'raw', 'Holidays_2020_2030.csv')
CSV_LOG_PATH   = os.path.join(LOG_DIR, 'rpi_pump_log.csv')
LORA_PACKET_CSV_PATH = os.path.join(LORA_LOG_DIR, 'esp32_pressure_packets.csv')
SENSOR_CSV_LOG_PATH = os.path.join(LOG_DIR, 'sensor_readings.csv')
STATE_FILE     = os.path.join(LOG_DIR, 'pump_state.json')
STATUS_FILE    = os.path.join(LOG_DIR, 'runtime_status.json')
CONTROL_FILE   = os.path.join(LOG_DIR, 'control_command.json')
DIRECT_PUMP_STATE_FILE = os.path.join(LOG_DIR, 'direct_pump_state.json')
CONTROL_COMMAND_TTL_S = 120

LOOP_INTERVAL_S  = 1    # Main loop cycle
LOG_INTERVAL_S   = 5    # CSV write interval

