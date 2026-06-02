#!/usr/bin/env python3
"""
Pulse the pump relay for a fixed duration while logging current/voltage samples.
"""

from __future__ import annotations

import argparse
import csv
import os
import time
from datetime import datetime

import tank_config as CFG
from manual_pump_control import read_status, set_pump
from sensor_reader import SensorReader


def parse_args():
    parser = argparse.ArgumentParser(description='Manual pump pulse with current logging')
    parser.add_argument('--seconds', type=float, required=True)
    parser.add_argument('--interval', type=float, default=1.0)
    parser.add_argument(
        '--csv',
        default=os.path.join(CFG.LOG_DIR, 'manual_pump_current_pulse.csv'),
    )
    return parser.parse_args()


def open_csv(path: str):
    abs_path = os.path.abspath(path)
    os.makedirs(os.path.dirname(abs_path), exist_ok=True)
    write_header = (not os.path.exists(abs_path)) or os.path.getsize(abs_path) == 0
    handle = open(abs_path, 'a', newline='', encoding='utf-8')
    writer = csv.writer(handle)
    if write_header:
        writer.writerow([
            'timestamp',
            'current_amps',
            'voltage_ac',
            'pump_relay_on',
            'gpio_level',
        ])
        handle.flush()
    return handle, writer, abs_path


def build_sensor() -> SensorReader:
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
    return sensor


def main():
    args = parse_args()
    sensor = build_sensor()
    csv_file, csv_writer, csv_path = open_csv(args.csv)
    started = set_pump(True)
    t_end = time.time() + args.seconds

    try:
        while time.time() < t_end:
            reading = sensor.read_all()
            status = read_status()
            csv_writer.writerow([
                datetime.now().isoformat(),
                reading.get('current_amps'),
                reading.get('voltage_ac'),
                status.get('pump_relay_on'),
                status.get('gpio_level'),
            ])
            csv_file.flush()
            time.sleep(args.interval)
    finally:
        ended = set_pump(False)
        csv_file.close()

    print(
        {
            'started': started,
            'ended': ended,
            'pulse_seconds': args.seconds,
            'interval_seconds': args.interval,
            'csv_path': csv_path,
        }
    )


if __name__ == '__main__':
    main()
