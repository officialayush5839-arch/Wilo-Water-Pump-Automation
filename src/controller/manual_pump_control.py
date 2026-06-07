#!/usr/bin/env python3
"""
Direct manual relay control for the pump.
"""

from __future__ import annotations

import argparse
import json
import sys
import time
from datetime import datetime

import RPi.GPIO as GPIO

import tank_config as CFG
from runtime_channel import atomic_write_json, read_json


def _output_level(turn_on: bool) -> int:
    if CFG.RELAY_ACTIVE_LOW:
        return GPIO.LOW if turn_on else GPIO.HIGH
    return GPIO.HIGH if turn_on else GPIO.LOW


def _ensure_gpio() -> None:
    GPIO.setwarnings(False)
    GPIO.setmode(GPIO.BCM)
    off_level = GPIO.LOW if CFG.RELAY_ACTIVE_LOW else GPIO.HIGH
    GPIO.setup(CFG.RELAY_PUMP_PIN, GPIO.OUT, initial=off_level)
    GPIO.setup(CFG.LED_STATUS_PIN, GPIO.OUT, initial=GPIO.LOW)


def _write_state(turn_on: bool) -> dict:
    payload = {
        'pump_relay_on': turn_on,
        'timestamp': datetime.now().isoformat(),
        'relay_pin': CFG.RELAY_PUMP_PIN,
        'active_low': CFG.RELAY_ACTIVE_LOW,
        'gpio_level': int(GPIO.input(CFG.RELAY_PUMP_PIN)),
    }
    atomic_write_json(CFG.DIRECT_PUMP_STATE_FILE, payload)
    return payload


def _notify_controller(action: str) -> None:
    """Drop a control command so the pump_controller's main loop honours the override.

    Without this, the controller will re-assert the relay on its next cycle
    because the tank-level-based automation logic does not know the operator
    flipped the switch manually. Manual override has higher priority and
    must persist until an explicit clear command is sent.
    """
    try:
        command = {
            'action': action,
            'issued_at': datetime.now().isoformat(),
            'source': 'manual_pump_control',
        }
        atomic_write_json(CFG.CONTROL_FILE, command)
    except Exception as exc:
        # Never let notification failure block the actual relay toggle.
        print(f'[manual_pump_control] WARN failed to notify controller: {exc}', file=sys.stderr)


def set_pump(turn_on: bool) -> dict:
    _ensure_gpio()
    GPIO.output(CFG.RELAY_PUMP_PIN, _output_level(turn_on))
    GPIO.output(CFG.LED_STATUS_PIN, GPIO.HIGH if turn_on else GPIO.LOW)
    _notify_controller('override_on' if turn_on else 'override_off')
    return _write_state(turn_on)


def read_status() -> dict:
    _ensure_gpio()
    saved = read_json(CFG.DIRECT_PUMP_STATE_FILE) or {}
    return {
        'pump_relay_on': saved.get('pump_relay_on'),
        'timestamp': saved.get('timestamp'),
        'relay_pin': CFG.RELAY_PUMP_PIN,
        'active_low': CFG.RELAY_ACTIVE_LOW,
        'gpio_level': int(GPIO.input(CFG.RELAY_PUMP_PIN)),
    }


def pulse_pump(seconds: float) -> dict:
    started = set_pump(True)
    time.sleep(seconds)
    ended = set_pump(False)
    return {
        'started': started,
        'ended': ended,
        'pulse_seconds': seconds,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description='Manual pump relay control')
    parser.add_argument('action', choices=['on', 'off', 'status', 'pulse'])
    parser.add_argument('--seconds', type=float, default=10.0)
    args = parser.parse_args()

    if args.action == 'on':
        result = set_pump(True)
    elif args.action == 'off':
        result = set_pump(False)
    elif args.action == 'status':
        result = read_status()
    else:
        result = pulse_pump(args.seconds)

    # Keep the output actively driven after the script exits.
    # Cleaning up here would return the pin to input mode and can let the
    # relay input float, which defeats manual ON/OFF behavior.
    print(json.dumps(result, indent=2))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
