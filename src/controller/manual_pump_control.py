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

RELAY_CONTROL_PINS = (CFG.RELAY_PUMP_PIN, CFG.RELAY_VALVE_PIN)


def _relay_pins() -> tuple[int, ...]:
    return tuple(dict.fromkeys(RELAY_CONTROL_PINS))


def _set_relay_outputs_on() -> None:
    GPIO.setwarnings(False)
    GPIO.setmode(GPIO.BCM)
    for pin in _relay_pins():
        GPIO.setup(pin, GPIO.OUT, initial=GPIO.LOW)
        GPIO.output(pin, GPIO.LOW)
    GPIO.setup(CFG.LED_STATUS_PIN, GPIO.OUT, initial=GPIO.HIGH)


def _release_relay_outputs_off() -> None:
    GPIO.setwarnings(False)
    GPIO.setmode(GPIO.BCM)
    for pin in _relay_pins():
        GPIO.setup(pin, GPIO.IN, pull_up_down=GPIO.PUD_UP)
    GPIO.setup(CFG.LED_STATUS_PIN, GPIO.OUT, initial=GPIO.LOW)


def _write_state(turn_on: bool) -> dict:
    gpio_level = int(GPIO.input(CFG.RELAY_PUMP_PIN))
    payload = {
        'pump_relay_on': turn_on,
        'timestamp': datetime.now().isoformat(),
        'relay_pin': CFG.RELAY_PUMP_PIN,
        'relay_control_pins': list(_relay_pins()),
        'off_mode': 'input_pullup',
        'on_mode': 'output_low',
        'active_low': True,
        'gpio_level': gpio_level,
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


def set_pump(turn_on: bool, notify_controller: bool = True) -> dict:
    if turn_on:
        _set_relay_outputs_on()
    else:
        _release_relay_outputs_off()
    if notify_controller:
        _notify_controller('override_on' if turn_on else 'override_off')
    return _write_state(turn_on)


def read_status() -> dict:
    saved = read_json(CFG.DIRECT_PUMP_STATE_FILE) or {}
    saved_on = saved.get('pump_relay_on')
    # SAFETY PATCH: Never allow a 'read' function to physically assert GPIO pins!
    # This prevents the Flask server from randomly killing the pump controller's commands.
    return {
        'pump_relay_on': saved_on,
        'timestamp': saved.get('timestamp'),
        'relay_pin': CFG.RELAY_PUMP_PIN,
        'relay_control_pins': list(_relay_pins()),
        'off_mode': 'input_pullup',
        'on_mode': 'output_low',
        'active_low': True,
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
