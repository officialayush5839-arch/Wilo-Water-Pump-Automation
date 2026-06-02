"""
CSV Data Logger + State Persistence
=====================================
Logs all sensor readings, pump decisions, and state changes to CSV.
"""

import os
import csv
import logging
from datetime import datetime

logger = logging.getLogger('wilo.logger')

CSV_HEADER = [
    'timestamp',
    'upper_tank_pct',
    'pressure_kpa',
    'sensor_voltage',
    'sensor_status',
    'lora_rssi',
    'lora_snr',
    'pump_current_a',
    'mains_voltage_v',
    'pump_relay',
    'decision_action',
    'decision_state',
    'decision_reason',
]


class DataLogger:
    """Append-only CSV logger with periodic flush."""

    def __init__(self, csv_path, flush_interval_s=5):
        self.csv_path  = csv_path
        self.interval  = flush_interval_s
        self._file     = None
        self._writer   = None
        self._last_flush = None
        self._count    = 0

    def initialize(self):
        os.makedirs(os.path.dirname(os.path.abspath(self.csv_path)), exist_ok=True)
        write_header = (not os.path.exists(self.csv_path)
                        or os.path.getsize(self.csv_path) == 0)
        self._file = open(self.csv_path, 'a', newline='')
        self._writer = csv.writer(self._file)
        if write_header:
            self._writer.writerow(CSV_HEADER)
            self._file.flush()
        self._last_flush = datetime.now()
        logger.info(f"CSV logger → {os.path.abspath(self.csv_path)}")

    def log(self, upper_pct, pressure_kpa, sensor_v, sensor_status,
            rssi, snr, current_a, voltage_v,
            pump_relay, decision):
        """Write one row."""
        if self._writer is None:
            return
        self._writer.writerow([
            datetime.now().isoformat(),
            f"{upper_pct:.1f}" if upper_pct is not None else '',
            f"{pressure_kpa:.2f}" if pressure_kpa is not None else '',
            f"{sensor_v:.3f}" if sensor_v is not None else '',
            sensor_status or '',
            rssi if rssi is not None else '',
            f"{snr:.2f}" if snr is not None else '',
            f"{current_a:.2f}" if current_a is not None else '',
            f"{voltage_v:.1f}" if voltage_v is not None else '',
            'ON' if pump_relay else 'OFF',
            decision.action if decision else '',
            decision.state.value if decision else '',
            decision.reason if decision else '',
        ])
        self._count += 1

        # Periodic flush
        now = datetime.now()
        if (now - self._last_flush).total_seconds() >= self.interval:
            self._file.flush()
            self._last_flush = now

    def close(self):
        if not self._file:
            return
        if not self._file.closed:
            self._file.flush()
            self._file.close()
        logger.info(f"CSV closed — {self._count} rows written")
