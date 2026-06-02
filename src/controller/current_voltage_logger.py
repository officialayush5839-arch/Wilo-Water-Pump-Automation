#!/usr/bin/env python3
"""
Standalone CSV logger for ADS1115 current and voltage readings.
"""

from __future__ import annotations

import csv
import os
import signal
import time
from datetime import datetime

import tank_config as CFG
from sensor_reader import SensorReader


RUNNING = True


def handle_signal(_sig, _frame):
    global RUNNING
    RUNNING = False


def ensure_csv(path: str):
    os.makedirs(os.path.dirname(os.path.abspath(path)), exist_ok=True)
    write_header = (not os.path.exists(path)) or os.path.getsize(path) == 0
    handle = open(path, 'a', newline='', encoding='utf-8')
    writer = csv.writer(handle)
    if write_header:
        writer.writerow([
            'timestamp',
            'current_amps',
            'voltage_ac',
            'sensor_available',
        ])
        handle.flush()
    return handle, writer


def main():
    signal.signal(signal.SIGINT, handle_signal)
    signal.signal(signal.SIGTERM, handle_signal)

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

    csv_file, csv_writer = ensure_csv(CFG.SENSOR_CSV_LOG_PATH)

    try:
        while RUNNING:
            reading = sensor.read_all()
            csv_writer.writerow([
                datetime.now().isoformat(),
                reading.get('current_amps'),
                reading.get('voltage_ac'),
                reading.get('available'),
            ])
            csv_file.flush()
            time.sleep(CFG.LOOP_INTERVAL_S)
    finally:
        csv_file.flush()
        csv_file.close()


if __name__ == '__main__':
    main()
