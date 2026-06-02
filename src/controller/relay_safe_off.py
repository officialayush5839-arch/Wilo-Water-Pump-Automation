#!/usr/bin/env python3
"""
Drive the pump relay to a known-safe OFF state.
"""

from __future__ import annotations

import sys

import RPi.GPIO as GPIO

import tank_config as CFG


def main() -> int:
    GPIO.setwarnings(False)
    GPIO.setmode(GPIO.BCM)
    off_level = GPIO.HIGH if CFG.RELAY_ACTIVE_LOW else GPIO.LOW
    GPIO.setup(CFG.RELAY_PUMP_PIN, GPIO.OUT, initial=off_level)
    GPIO.setup(CFG.RELAY_VALVE_PIN, GPIO.OUT, initial=off_level)
    GPIO.setup(CFG.LED_STATUS_PIN, GPIO.OUT, initial=GPIO.LOW)
    GPIO.output(CFG.RELAY_PUMP_PIN, off_level)
    GPIO.output(CFG.RELAY_VALVE_PIN, off_level)
    GPIO.output(CFG.LED_STATUS_PIN, GPIO.LOW)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
