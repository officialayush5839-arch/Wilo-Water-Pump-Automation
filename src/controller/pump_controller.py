#!/usr/bin/env python3
"""
Wilo Water Pump Controller — Main Service
===========================================
Runs on Raspberry Pi. Receives LoRa data from ESP32 (upper tank pressure),
reads local current/voltage sensors (main tank estimation),
and controls the pump relay using hybrid logic.

Usage:
    python3 pump_controller.py                # normal operation
    python3 pump_controller.py --dry-run      # no GPIO, for testing
    python3 pump_controller.py --verbose       # extra debug output
"""

import sys
import os
import json
import time
import signal
import logging
import argparse
from datetime import datetime

# ── Add project root to path for ML imports ──────────────────
_HERE = os.path.dirname(os.path.abspath(__file__))
_PROJECT = os.path.abspath(os.path.join(_HERE, '..', '..'))
sys.path.insert(0, _PROJECT)
sys.path.insert(0, _HERE)

import tank_config as CFG
from pump_logic import HybridPumpLogic, PumpDecision
from data_logger import DataLogger
from runtime_channel import atomic_write_json, read_json, remove_file

# ── Logging setup ────────────────────────────────────────────

def setup_logging(verbose=False):
    fmt = '%(asctime)s [%(name)-12s] %(levelname)-7s %(message)s'
    level = logging.DEBUG if verbose else logging.INFO
    logging.basicConfig(level=level, format=fmt, datefmt='%H:%M:%S')
    # File log
    os.makedirs(CFG.LOG_DIR, exist_ok=True)
    fh = logging.FileHandler(os.path.join(CFG.LOG_DIR, 'pump_controller.log'))
    fh.setFormatter(logging.Formatter(fmt))
    fh.setLevel(logging.DEBUG)
    logging.getLogger().addHandler(fh)

logger = logging.getLogger('wilo.main')


# ── Pressure → water level conversion ───────────────────────

def pressure_to_level_pct(pressure_kpa):
    """
    Convert pressure at bottom of upper tank to water level percentage.
    P = ρ × g × h  →  h = P / (ρ × g)
    """
    if pressure_kpa is None or pressure_kpa < 0:
        return None
    # Pressure in Pascals
    pressure_pa = pressure_kpa * 1000.0
    # Water column height in metres
    h_m = pressure_pa / (CFG.WATER_DENSITY * CFG.GRAVITY)
    # Height in cm
    h_cm = h_m * 100.0
    # Percentage of tank height
    pct = (h_cm / CFG.UPPER_TANK_HEIGHT_CM) * 100.0
    return max(0.0, min(100.0, pct))


# ── LoRa packet parser ──────────────────────────────────────

def parse_lora_packet(raw_str):
    """
    Parse JSON payload from ESP32.
    Expected: {"device":"esp32","sensor":"PR12P210","status":"ok",
               "voltage":1.234,"pressure_kpa":12.50,"pkt":42}
    Returns dict or None on failure.
    """
    try:
        data = json.loads(raw_str)
        return {
            'device':       data.get('device', ''),
            'sensor':       data.get('sensor', ''),
            'status':       data.get('status', 'unknown'),
            'voltage':      float(data.get('voltage', 0)),
            'pressure_kpa': float(data.get('pressure_kpa', -1)),
            'pkt':          int(data.get('pkt', -1)),
        }
    except (json.JSONDecodeError, ValueError, TypeError) as e:
        logger.warning(f"Packet parse error: {e}  raw='{raw_str[:80]}'")
        return None


# ── Main controller class ───────────────────────────────────

class PumpController:
    """Top-level controller tying all subsystems together."""

    def __init__(self, dry_run=False):
        self.dry_run = dry_run
        self.running = True

        # ── Subsystems ──
        self.lora   = None
        self.relay  = None
        self.sensor = None
        self.csv    = None
        self.logic  = None

        # ── Latest data ──
        self.last_packet = None
        self.upper_pct   = None
        self.last_decision = None
        self.last_rssi = None
        self.last_snr = None

    def initialize(self):
        logger.info("=" * 60)
        logger.info("  WILO WATER PUMP CONTROLLER")
        logger.info(f"  Mode: {'DRY-RUN (no GPIO)' if self.dry_run else 'LIVE'}")
        logger.info(f"  Time: {datetime.now()}")
        logger.info("=" * 60)

        # ── 1. LoRa receiver ──
        try:
            from sx127x import SX127x
            self.lora = SX127x(
                spi_bus=CFG.LORA_SPI_BUS, spi_cs=CFG.LORA_SPI_CS,
                reset_pin=CFG.LORA_RESET_PIN, dio0_pin=CFG.LORA_DIO0_PIN,
                frequency=CFG.LORA_FREQUENCY
            )
            self.lora.receive()
            logger.info("LoRa receiver initialised — listening on 433 MHz")
        except Exception as e:
            if self.dry_run:
                logger.warning(f"LoRa init skipped (dry-run): {e}")
                self.lora = None
            else:
                logger.critical(f"LoRa init FAILED: {e}")
                raise

        # ── 2. Relay controller ──
        if not self.dry_run:
            import RPi.GPIO as GPIO
            GPIO.setmode(GPIO.BCM)
            GPIO.setwarnings(False)
            from relay_control import RelayController
            self.relay = RelayController(
                pump_pin=CFG.RELAY_PUMP_PIN, valve_pin=CFG.RELAY_VALVE_PIN,
                active_low=CFG.RELAY_ACTIVE_LOW,
                btn_on_pin=CFG.BUTTON_FORCE_ON, btn_off_pin=CFG.BUTTON_FORCE_OFF,
                led_pin=CFG.LED_STATUS_PIN, debounce_ms=CFG.OVERRIDE_DEBOUNCE_MS
            )
            self.relay.initialize()
        else:
            logger.info("Relay control SKIPPED (dry-run)")

        # ── 3. Current / voltage sensors ──
        from sensor_reader import SensorReader
        self.sensor = SensorReader(
            acs_model=CFG.ACS712_MODEL, acs_zero_v=CFG.ACS712_ZERO_V,
            acs_divider=CFG.ACS712_DIVIDER_RATIO,
            zmpt_cal=CFG.ZMPT101B_CAL_FACTOR, zmpt_zero_v=CFG.ZMPT101B_ZERO_V,
            zmpt_divider=CFG.ZMPT101B_DIVIDER_RATIO,
            adc_addr=CFG.ADS1115_ADDRESS,
            ch_current=CFG.ADC_CH_CURRENT, ch_voltage=CFG.ADC_CH_VOLTAGE
        )
        self.sensor.initialize()

        # ── 4. Data logger ──
        self.csv = DataLogger(CFG.CSV_LOG_PATH, CFG.LOG_INTERVAL_S)
        self.csv.initialize()

        # ── 5. Hybrid pump logic ──
        self.logic = HybridPumpLogic(
            state_file=CFG.STATE_FILE,
            critical_low=CFG.UPPER_CRITICAL_LOW, low=CFG.UPPER_LOW,
            high=CFG.UPPER_HIGH, critical_high=CFG.UPPER_CRITICAL_HIGH,
            lora_timeout_s=CFG.LORA_TIMEOUT_S, max_run_min=CFG.MAX_CONTINUOUS_RUN_MIN,
            dry_run_a=CFG.PUMP_DRY_RUN_CURRENT_A, dry_run_enabled=CFG.DRY_RUN_PROTECTION,
            power_delay_s=CFG.POWER_RESTORE_DELAY_S,
            require_valid_lora_before_start=CFG.REQUIRE_VALID_LORA_BEFORE_START,
            voltage_guard_enabled=CFG.POWER_VOLTAGE_PROTECTION,
            min_voltage_ac=CFG.MIN_MAINS_VOLTAGE_AC,
            override_timeout_min=CFG.OVERRIDE_TIMEOUT_MIN,
            ml_enabled=CFG.ML_ENABLED, ml_window_min=CFG.ML_ACTIVATION_WINDOW_MIN
        )

        # ── 6. Try loading ML prediction ──
        self._update_ml_prediction()

        logger.info("All subsystems initialised ✓")
        self._write_runtime_status(decision=None, current_a=None, voltage_v=None)

    # ── ML prediction (optional) ──────────────────────────────

    def _update_ml_prediction(self):
        if not CFG.ML_ENABLED:
            return
        try:
            from src.models.prediction import get_comprehensive_prediction
            from src.utils.sensors import get_fallback_sensor_data
            sensor_data = get_fallback_sensor_data()
            result = get_comprehensive_prediction(sensor_data)
            self.logic.set_ml_prediction({
                'start_hour': result['start_hour'],
                'duration':   result['duration'],
            })
        except Exception as e:
            logger.warning(f"ML prediction unavailable: {e}")

    def _consume_control_command(self):
        try:
            command = read_json(CFG.CONTROL_FILE)
        except Exception as e:
            logger.warning(f"Control command read failed: {e}")
            return

        if not command:
            return

        remove_file(CFG.CONTROL_FILE)
        issued_at = command.get('issued_at')
        action = command.get('action')

        if issued_at:
            try:
                age_s = (datetime.now() - datetime.fromisoformat(issued_at)).total_seconds()
                if age_s > CFG.CONTROL_COMMAND_TTL_S:
                    logger.warning("Ignoring stale control command %s age=%.1fs", action, age_s)
                    return
            except ValueError:
                logger.warning("Ignoring malformed control command timestamp: %s", issued_at)
                return

        if action == 'override_on':
            self.logic.set_override('ON')
            logger.info("Control command accepted: override ON")
        elif action == 'override_off':
            self.logic.set_override('OFF')
            logger.info("Control command accepted: override OFF")
        elif action == 'override_clear':
            self.logic.set_override(None)
            logger.info("Control command accepted: override CLEAR")
        else:
            logger.warning("Unknown control command: %s", action)

    def _write_runtime_status(self, decision, current_a, voltage_v):
        packet = self.last_packet or {}
        payload = {
            'connected': True,
            'controller_mode': 'dry-run' if self.dry_run else 'live',
            'current_amps': current_a,
            'decision': {
                'action': decision.action if decision else None,
                'reason': decision.reason if decision else None,
                'state': decision.state.value if decision else None,
                'ts': decision.ts.isoformat() if decision else None,
            },
            'host': os.uname().nodename,
            'last_lora_ts': self.logic.last_lora_ts.isoformat() if self.logic and self.logic.last_lora_ts else None,
            'lora_age_s': (
                round((datetime.now() - self.logic.last_lora_ts).total_seconds(), 1)
                if self.logic and self.logic.last_lora_ts else None
            ),
            'lora_pkt': packet.get('pkt'),
            'lora_rssi': self.last_rssi,
            'lora_snr': self.last_snr,
            'ml_prediction': self.logic.ml_prediction if self.logic else None,
            'override': self.logic.override if self.logic else None,
            'pressure_kpa': packet.get('pressure_kpa'),
            'pump_relay_on': self.relay.pump_on if self.relay else False,
            'sensor_status': packet.get('status'),
            'sensor_voltage': packet.get('voltage'),
            'timestamp': datetime.now().isoformat(),
            'upper_pct': self.upper_pct,
            'voltage_ac': voltage_v,
        }

        try:
            atomic_write_json(CFG.STATUS_FILE, payload)
        except Exception as e:
            logger.debug(f"Runtime status write failed: {e}")

    # ── Main loop ─────────────────────────────────────────────

    def run(self):
        logger.info("Main loop started — Ctrl+C to stop")
        cycle = 0
        ml_last = datetime.now()

        while self.running:
            try:
                cycle += 1
                rssi = snr = None
                self._consume_control_command()

                # ── Read LoRa ──
                if self.lora and self.lora.available():
                    try:
                        raw = self.lora.read_payload()
                        raw_str = ''.join(chr(c) for c in raw)
                        rssi = self.lora.get_packet_rssi()
                        snr  = self.lora.get_packet_snr()
                        self.last_rssi = rssi
                        self.last_snr = snr
                        pkt_data = parse_lora_packet(raw_str)

                        if pkt_data:
                            self.last_packet = pkt_data

                            if pkt_data['status'] == 'fault':
                                self.logic.signal_lora_fault()
                                self.upper_pct = None
                                logger.debug(f"LoRa #{pkt_data['pkt']}  SENSOR FAULT  RSSI={rssi}")
                            else:
                                upper_pct = pressure_to_level_pct(pkt_data['pressure_kpa'])
                                if upper_pct is None:
                                    self.logic.signal_lora_fault()
                                    self.upper_pct = None
                                    logger.warning(
                                        "LoRa #%s invalid pressure payload %.2fkPa",
                                        pkt_data['pkt'],
                                        pkt_data['pressure_kpa'],
                                    )
                                else:
                                    self.logic.signal_lora_ok()
                                    self.upper_pct = upper_pct
                                    logger.debug(
                                        f"LoRa #{pkt_data['pkt']}  "
                                        f"{pkt_data['pressure_kpa']:.2f}kPa → "
                                        f"{self.upper_pct:.1f}%  "
                                        f"RSSI={rssi}  SNR={snr:.1f}"
                                    )
                    except Exception as e:
                        logger.error(f"LoRa read error: {e}")

                # ── Read current/voltage ──
                cv = self.sensor.read_all()
                current_a = cv['current_amps']
                voltage_v = cv['voltage_ac']

                # ── Manual override buttons ──
                if self.relay:
                    btn = self.relay.read_override_buttons()
                    if btn:
                        self.logic.set_override(btn)

                # ── Decide ──
                pump_is_on = self.relay.pump_on if self.relay else False
                decision = self.logic.decide(
                    upper_pct=self.upper_pct,
                    pump_is_on=pump_is_on,
                    current_amps=current_a,
                    voltage_ac=voltage_v
                )
                self.last_decision = decision

                # ── Act ──
                if decision.action == 'ON' and not pump_is_on:
                    if self.relay:
                        self.relay.pump_start()
                    logger.info(f"▶ PUMP ON  — {decision.reason}")
                elif decision.action == 'OFF' and pump_is_on:
                    if self.relay:
                        self.relay.pump_stop()
                    logger.info(f"⏹ PUMP OFF — {decision.reason}")

                # ── Log (every cycle) ──
                p = self.last_packet or {}
                self.csv.log(
                    upper_pct=self.upper_pct,
                    pressure_kpa=p.get('pressure_kpa'),
                    sensor_v=p.get('voltage'),
                    sensor_status=p.get('status'),
                    rssi=rssi, snr=snr,
                    current_a=current_a, voltage_v=voltage_v,
                    pump_relay=(self.relay.pump_on if self.relay else False),
                    decision=decision,
                )
                self._write_runtime_status(decision=decision, current_a=current_a, voltage_v=voltage_v)

                # ── Periodic ML update ──
                if CFG.ML_ENABLED:
                    elapsed = (datetime.now() - ml_last).total_seconds() / 60
                    if elapsed >= CFG.ML_CHECK_INTERVAL_MIN:
                        self._update_ml_prediction()
                        ml_last = datetime.now()

                # ── Status print (every 10 cycles) ──
                if cycle % 10 == 0:
                    level_str = f"{self.upper_pct:.1f}%" if self.upper_pct is not None else "?"
                    pump_str  = "ON" if (self.relay and self.relay.pump_on) else "OFF"
                    curr_str  = f"{current_a:.2f}A" if current_a else "N/A"
                    logger.info(
                        f"[cycle {cycle}]  upper={level_str}  "
                        f"pump={pump_str}  I={curr_str}  "
                        f"state={decision.state.value}"
                    )

                time.sleep(CFG.LOOP_INTERVAL_S)

            except KeyboardInterrupt:
                break
            except Exception as e:
                logger.error(f"Loop error: {e}", exc_info=True)
                # Safety: stop pump on unexpected error
                if self.relay and self.relay.pump_on:
                    self.relay.emergency_stop()
                time.sleep(5)

    def shutdown(self):
        logger.info("Shutting down…")
        self.running = False
        if self.relay:
            self.relay.cleanup()
        if self.csv:
            self.csv.close()
        if self.lora:
            try:
                self.lora.close()
            except Exception:
                pass
        logger.info("Shutdown complete.")


# ── Entry point ──────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(description='Wilo Water Pump Controller')
    parser.add_argument('--dry-run', action='store_true',
                        help='Run without GPIO (for testing on non-Pi)')
    parser.add_argument('--verbose', '-v', action='store_true',
                        help='Enable debug logging')
    args = parser.parse_args()

    setup_logging(verbose=args.verbose)

    ctrl = PumpController(dry_run=args.dry_run)

    def handle_signal(sig, frame):
        ctrl.shutdown()
        sys.exit(0)
    signal.signal(signal.SIGTERM, handle_signal)
    signal.signal(signal.SIGINT, handle_signal)

    try:
        ctrl.initialize()
        ctrl.run()
    except Exception as e:
        logger.critical(f"Fatal error: {e}", exc_info=True)
    finally:
        ctrl.shutdown()


if __name__ == '__main__':
    main()
