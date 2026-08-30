"""
Current-Based Tank Hydraulic State Classifier
============================================
Classifies Master Tank hydraulic state from pump electrical current while running:
  - ~12 A (>= 11.5 A)  -> Tank EMPTY
  - ~9 A  (8.0 - 10.0 A) -> Tank MID (~50%)
  - ~6 A  (<= 6.5 A)   -> Tank FULL (triggers auto pump stop after persistence)

Features:
  - Rolling median filter (10 samples)
  - 5-second startup blanking window
  - 5-second persistence requirement for full-tank detection
  - Distinct < 1.5 A dry-run threshold
  - 0 A when pump is OFF evaluates strictly to UNKNOWN (never EMPTY)
"""

from __future__ import annotations

import logging
import statistics
from collections import deque
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional

logger = logging.getLogger('wilo.current_classifier')


class CurrentClassifier:
    """Stateful filter and classifier for pump current measurements."""

    def __init__(
        self,
        *,
        empty_threshold: float = 11.5,
        mid_low: float = 8.0,
        mid_high: float = 10.0,
        full_threshold: float = 6.5,
        dry_run_threshold: float = 1.5,
        filter_window: int = 10,
        startup_blanking_sec: float = 5.0,
        full_persistence_sec: float = 5.0,
    ):
        self.empty_threshold = float(empty_threshold)
        self.mid_low = float(mid_low)
        self.mid_high = float(mid_high)
        self.full_threshold = float(full_threshold)
        self.dry_run_threshold = float(dry_run_threshold)
        self.filter_window = max(1, int(filter_window))
        self.startup_blanking_s = timedelta(seconds=float(startup_blanking_sec))
        self.full_persistence_s = timedelta(seconds=float(full_persistence_sec))

        # Runtime state buffers
        self.samples: deque[float] = deque(maxlen=self.filter_window)
        self.pump_was_on: bool = False
        self.pump_on_start_time: Optional[datetime] = None
        self.full_condition_start: Optional[datetime] = None
        self.last_state: str = "UNKNOWN"
        self.last_filtered_a: Optional[float] = None

    def reset(self) -> None:
        """Reset internal history and persistence timers."""
        self.samples.clear()
        self.pump_was_on = False
        self.pump_on_start_time = None
        self.full_condition_start = None
        self.last_state = "UNKNOWN"
        self.last_filtered_a = None

    def update(
        self,
        current_amps: Optional[float],
        pump_is_on: bool,
        now: Optional[datetime] = None,
    ) -> Dict[str, Any]:
        """
        Process a new current sample and update classification.

        Args:
            current_amps: Measured RMS current in amps, or None.
            pump_is_on: True if relay is energizing pump.
            now: Current timestamp (defaults to datetime.now()).
        """
        now = now or datetime.now()

        # Handle Pump OFF
        if not pump_is_on:
            self.reset()
            return {
                'raw_amps': current_amps,
                'filtered_amps': None,
                'state': 'UNKNOWN',
                'full_persisted': False,
                'full_persistence_seconds': 0.0,
                'startup_blanking': False,
                'status_detail': 'Pump is OFF — current not evaluated for tank state',
                'samples_count': 0,
            }

        # Track pump startup
        if not self.pump_was_on:
            self.pump_was_on = True
            self.pump_on_start_time = now
            self.samples.clear()
            self.full_condition_start = None
            logger.info("CURRENT_CLASSIFIER_STARTED (blanking window active for %.1fs)",
                        self.startup_blanking_s.total_seconds())

        # Check startup blanking window (5s)
        time_running = now - (self.pump_on_start_time or now)
        is_in_blanking = time_running < self.startup_blanking_s

        # Feed sample buffer if valid
        if current_amps is not None and isinstance(current_amps, (int, float)) and current_amps >= 0:
            self.samples.append(float(current_amps))

        if not self.samples:
            self.last_filtered_a = None
            self.last_state = "UNKNOWN"
            return {
                'raw_amps': current_amps,
                'filtered_amps': None,
                'state': 'UNKNOWN',
                'full_persisted': False,
                'full_persistence_seconds': 0.0,
                'startup_blanking': is_in_blanking,
                'status_detail': 'No valid current samples available',
                'samples_count': 0,
            }

        # Rolling median filter
        filtered_a = round(statistics.median(self.samples), 2)
        self.last_filtered_a = filtered_a

        if is_in_blanking:
            self.last_state = "STARTING"
            self.full_condition_start = None
            rem_blanking = max(0.0, round((self.startup_blanking_s - time_running).total_seconds(), 1))
            return {
                'raw_amps': current_amps,
                'filtered_amps': filtered_a,
                'state': 'STARTING',
                'full_persisted': False,
                'full_persistence_seconds': 0.0,
                'startup_blanking': True,
                'status_detail': f'Startup blanking active ({rem_blanking}s remaining)',
                'samples_count': len(self.samples),
            }

        # Check dry-run / zero current anomaly
        if filtered_a < self.dry_run_threshold:
            self.last_state = "UNKNOWN"
            self.full_condition_start = None
            return {
                'raw_amps': current_amps,
                'filtered_amps': filtered_a,
                'state': 'UNKNOWN',
                'full_persisted': False,
                'full_persistence_seconds': 0.0,
                'startup_blanking': False,
                'status_detail': f'Low current ({filtered_a}A < {self.dry_run_threshold}A) — possible dry run or idling',
                'samples_count': len(self.samples),
            }

        # Classify hydraulic state
        full_persisted = False
        full_persistence_sec = 0.0

        if filtered_a <= self.full_threshold:
            state = "FULL"
            if self.full_condition_start is None:
                self.full_condition_start = now
                logger.debug("CURRENT_STATE_FULL detected (I_filt=%.2fA <= %.1fA), monitoring persistence",
                             filtered_a, self.full_threshold)

            duration = now - self.full_condition_start
            full_persistence_sec = round(duration.total_seconds(), 1)
            if duration >= self.full_persistence_s:
                full_persisted = True
                logger.info("CURRENT_FULL_PERSISTENCE reached: %.2fA persisted for %.1fs >= %.1fs",
                            filtered_a, full_persistence_sec, self.full_persistence_s.total_seconds())
            detail = f"Tank FULL (I_filt={filtered_a}A <= {self.full_threshold}A, persisted {full_persistence_sec}s)"
        else:
            self.full_condition_start = None
            if filtered_a >= self.empty_threshold:
                state = "EMPTY"
                detail = f"Tank EMPTY / High Load (I_filt={filtered_a}A >= {self.empty_threshold}A)"
            elif self.mid_low <= filtered_a <= self.mid_high:
                state = "MID"
                detail = f"Tank ~50% MID LEVEL (I_filt={filtered_a}A in [{self.mid_low}A, {self.mid_high}A])"
            else:
                # Transition band (between FULL-MID or MID-EMPTY)
                state = "MID"
                detail = f"Tank Hydraulic State (I_filt={filtered_a}A)"

        self.last_state = state

        return {
            'raw_amps': current_amps,
            'filtered_amps': filtered_a,
            'state': state,
            'full_persisted': full_persisted,
            'full_persistence_seconds': full_persistence_sec,
            'startup_blanking': False,
            'status_detail': detail,
            'samples_count': len(self.samples),
        }
