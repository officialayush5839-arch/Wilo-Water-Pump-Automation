#!/usr/bin/env python3
"""
Small CLI bridge for remote status polling and manual overrides.
"""

from __future__ import annotations

import argparse
import csv
import json
import os
import socket
import sys
from datetime import datetime

_HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, _HERE)

import tank_config as CFG
from runtime_channel import atomic_write_json, new_command, read_json


def print_json(payload: dict) -> None:
    print(json.dumps(payload, indent=2, sort_keys=True))


def read_status() -> dict:
    payload = read_json(CFG.STATUS_FILE)
    if payload is not None:
        return payload

    latest_packet = _read_latest_lora_packet()
    sensor_data = _read_sensor_data()
    direct_state = read_json(CFG.DIRECT_PUMP_STATE_FILE) or {}

    return {
        'connected': True,
        'controller_mode': 'bridge-only',
        'current_amps': sensor_data.get('current_amps'),
        'decision': {
            'action': None,
            'reason': 'pump controller service is not publishing runtime status',
            'state': 'BRIDGE_ONLY',
            'ts': datetime.now().isoformat(),
        },
        'error': 'status-unavailable',
        'host': socket.gethostname(),
        'lora_age_s': latest_packet.get('lora_age_s'),
        'lora_pkt': latest_packet.get('pkt'),
        'pressure_kpa': latest_packet.get('pressure_kpa'),
        'pump_relay_on': direct_state.get('pump_relay_on'),
        'sensor_status': latest_packet.get('status'),
        'sensor_voltage': latest_packet.get('voltage'),
        'timestamp': datetime.now().isoformat(),
        'upper_pct': None,
        'voltage_ac': sensor_data.get('voltage_ac'),
    }


def write_override(action: str, source: str) -> dict:
    payload = new_command(action=action, source=source)
    atomic_write_json(CFG.CONTROL_FILE, payload)
    return {
        'ok': True,
        'control_file': CFG.CONTROL_FILE,
        'command': payload,
    }


def _read_latest_lora_packet() -> dict:
    candidates = [
        os.path.join(CFG._PROJECT, 'logs', 'lora', 'esp32_pressure_packets.csv'),
        os.path.join(CFG._PROJECT, 'logs', 'lora', 'received_packets.csv'),
    ]
    path = next((candidate for candidate in candidates if os.path.exists(candidate)), None)
    if not path:
        return {}

    latest = None
    with open(path, newline='', encoding='utf-8') as handle:
        for row in csv.DictReader(handle):
            if row.get('pkt') and row.get('pressure_kpa'):
                latest = row

    if not latest:
        return {}

    packet = {
        'status': latest.get('status'),
        'pkt': int(latest['pkt']) if latest.get('pkt') else None,
        'pressure_kpa': float(latest['pressure_kpa']) if latest.get('pressure_kpa') else None,
        'voltage': float(latest['voltage']) if latest.get('voltage') else (
            float(latest['voltage_v']) if latest.get('voltage_v') else None
        ),
    }

    if latest.get('timestamp'):
        try:
            packet['lora_age_s'] = round(
                (datetime.now() - datetime.fromisoformat(latest['timestamp'])).total_seconds(), 1
            )
        except ValueError:
            packet['lora_age_s'] = None

    return packet


def _read_sensor_data() -> dict:
    try:
        from sensor_reader import SensorReader

        sensor = SensorReader(
            acs_model=CFG.ACS712_MODEL,
            acs_zero_v=CFG.ACS712_ZERO_V,
            acs_divider=CFG.ACS712_DIVIDER_RATIO,
            zmpt_cal=CFG.ZMPT101B_CAL_FACTOR,
            zmpt_zero_v=CFG.ZMPT101B_ZERO_V,
            zmpt_divider=CFG.ZMPT101B_DIVIDER_RATIO,
            adc_addr=CFG.ADS1115_ADDRESS,
            ch_current=CFG.ADC_CH_CURRENT,
            ch_voltage=CFG.ADC_CH_VOLTAGE,
        )
        sensor.initialize()
        return sensor.read_all()
    except Exception:
        return {}


def set_pump_state(turn_on: bool) -> dict:
    import RPi.GPIO as GPIO

    GPIO.setwarnings(False)
    GPIO.setmode(GPIO.BCM)
    target_level = GPIO.HIGH if turn_on else GPIO.LOW
    if CFG.RELAY_ACTIVE_LOW:
        target_level = GPIO.LOW if turn_on else GPIO.HIGH
    GPIO.setup(CFG.RELAY_PUMP_PIN, GPIO.OUT, initial=target_level)
    GPIO.setup(CFG.LED_STATUS_PIN, GPIO.OUT, initial=GPIO.HIGH if turn_on else GPIO.LOW)
    GPIO.output(CFG.RELAY_PUMP_PIN, target_level)

    GPIO.output(CFG.LED_STATUS_PIN, GPIO.HIGH if turn_on else GPIO.LOW)

    state = {
        'pump_relay_on': turn_on,
        'timestamp': datetime.now().isoformat(),
    }
    atomic_write_json(CFG.DIRECT_PUMP_STATE_FILE, state)
    return state


def main() -> int:
    parser = argparse.ArgumentParser(description='Remote pump bridge')
    subparsers = parser.add_subparsers(dest='command', required=True)

    subparsers.add_parser('status', help='Print latest controller runtime status')

    override_parser = subparsers.add_parser('override', help='Write a manual override command')
    override_parser.add_argument('mode', choices=['on', 'off', 'clear'])
    override_parser.add_argument('--source', default='ink-tui')

    pump_parser = subparsers.add_parser('pump', help='Direct relay control for manual pump tests')
    pump_parser.add_argument('mode', choices=['on', 'off'])

    args = parser.parse_args()

    if args.command == 'status':
        print_json(read_status())
        return 0

    if args.command == 'override':
        action_map = {
            'on': 'override_on',
            'off': 'override_off',
            'clear': 'override_clear',
        }
        print_json(write_override(action_map[args.mode], args.source))
        return 0

    if args.command == 'pump':
        print_json(set_pump_state(args.mode == 'on'))
        return 0

    return 1


if __name__ == '__main__':
    raise SystemExit(main())
