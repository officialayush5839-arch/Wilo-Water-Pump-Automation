"""
Hybrid Pump Control Logic
==========================
Decision engine evaluates triggers in strict priority order:

  P0 — Manual mode freeze     (operator froze automation; only manual override commands work)
  P1 — Power-cut recovery     (delay after power restore)
  P2 — Manual override        (button force ON/OFF, auto-expires)
  P3 — Emergency thresholds   (tank critical LOW → ON, critical HIGH → OFF)
  P4 — Safety guards          (LoRa timeout, sensor fault, max-run, dry-run, undervoltage → OFF)
  P5 — ML prediction          (scheduled ON window from trained model)
  P6 — Normal threshold       (hysteresis: ON at LOW%, OFF at HIGH%)

If no trigger fires, the current pump state is held (HOLD).

"""

import logging
from enum import Enum
from datetime import datetime, timedelta

logger = logging.getLogger('wilo.logic')


# ── Pump state enum ──────────────────────────────────────────

class PumpState(Enum):
    OFF                = 'OFF'
    ON_EMERGENCY       = 'ON_EMERGENCY'
    ON_THRESHOLD       = 'ON_THRESHOLD'
    ON_ML_SCHEDULED    = 'ON_ML_SCHEDULED'
    ON_MANUAL          = 'ON_MANUAL'
    OFF_EMERGENCY      = 'OFF_EMERGENCY'
    OFF_SAFETY         = 'OFF_SAFETY'
    OFF_MANUAL         = 'OFF_MANUAL'
    OFF_SENSOR_FAULT   = 'OFF_SENSOR_FAULT'
    OFF_POWER_RESTORE  = 'OFF_POWER_RESTORE'
    OFF_DRY_RUN        = 'OFF_DRY_RUN'
    OFF_MAX_RUN        = 'OFF_MAX_RUN'
    OFF_LORA_TIMEOUT   = 'OFF_LORA_TIMEOUT'
    OFF_UNDERVOLTAGE   = 'OFF_UNDERVOLTAGE'


class PumpDecision:
    """Immutable result of a decide() call."""
    __slots__ = ('action', 'state', 'reason', 'ts')

    def __init__(self, action: str, state: PumpState, reason: str):
        self.action = action        # 'ON', 'OFF', or 'HOLD'
        self.state  = state
        self.reason = reason
        self.ts     = datetime.now()

    def __repr__(self):
        return f"{self.action} [{self.state.value}] {self.reason}"


# ── Decision engine ──────────────────────────────────────────

class HybridPumpLogic:
    """Stateful pump decision engine."""

    def __init__(self, *, critical_low, low, high, critical_high,
                 lora_timeout_s, max_run_min, dry_run_a,
                 dry_run_enabled, power_delay_s,
                 require_valid_lora_before_start,
                 voltage_guard_enabled, min_voltage_ac,
                 override_timeout_min,
                 ml_enabled, ml_window_min):
        # Thresholds
        self.crit_low  = critical_low
        self.low       = low
        self.high      = high
        self.crit_high = critical_high

        # Safety
        self.lora_timeout  = timedelta(seconds=lora_timeout_s)
        self.max_run       = timedelta(minutes=max_run_min)
        self.dry_run_a     = dry_run_a
        self.dry_run_on    = dry_run_enabled
        self.power_delay   = timedelta(seconds=power_delay_s)
        self.require_valid_lora_before_start = require_valid_lora_before_start
        self.voltage_guard_enabled = voltage_guard_enabled
        self.min_voltage_ac = min_voltage_ac

        # Override
        self.ovr_timeout   = timedelta(minutes=override_timeout_min)

        # ML
        self.ml_enabled    = ml_enabled
        self.ml_window     = timedelta(minutes=ml_window_min)

        # State
        self.current_state    = PumpState.OFF
        self.pump_start_time  = None
        self.override         = None        # 'ON' | 'OFF' | None
        self.override_time    = None
        self.last_lora_ts     = None
        self.consec_faults    = 0
        self.power_restore_ts = None
        self.ml_prediction    = None        # {'start_hour':float, 'duration':float}
        self.ml_check_ts      = None
        self.manual_mode      = False       # True = automation frozen, only manual override works

    # ── External updates ─────────────────────────────────────

    def signal_lora_ok(self):
        """Call when a clean (non-fault) LoRa packet is received."""
        self.last_lora_ts = datetime.now()
        self.consec_faults = 0

    def signal_lora_fault(self):
        """Call when a LoRa packet arrives but sensor reports fault."""
        self.last_lora_ts = datetime.now()   # still alive, just bad reading
        self.consec_faults += 1

    def set_override(self, mode):
        """mode: 'ON', 'OFF', or None to clear."""
        self.override = mode
        self.override_time = datetime.now() if mode else None
        if mode:
            logger.info(f"Manual override → {mode}")

    def set_manual_mode(self, enabled: bool):
        self.manual_mode = enabled
        if not enabled:
            self.override = None
            self.override_time = None
        logger.info(f"Manual mode {'ENABLED' if enabled else 'DISABLED'} — automation {'frozen' if enabled else 'resumed'}")

    def set_ml_prediction(self, pred: dict):
        self.ml_prediction = pred
        self.ml_check_ts = datetime.now()
        logger.info(f"ML prediction: start={pred.get('start_hour',0):.2f}h  "
                     f"dur={pred.get('duration',0):.0f}min")

    # ── Main decision ────────────────────────────────────────

    def decide(self, upper_pct, pump_is_on, current_amps=None, voltage_ac=None) -> PumpDecision:
        """
        Args:
            upper_pct:   Upper tank level 0-100 (None if unknown)
            pump_is_on:  Current relay state
            current_amps: Measured pump current (None if ADC unavailable)
        Returns:
            PumpDecision with .action in {'ON','OFF','HOLD'}
        """
        now = datetime.now()

        # ── P0  Manual mode — freeze all automation ──────────
        # When manual mode is active, only explicit override ON/OFF commands
        # from the operator are honoured. All tank levels, ML predictions,
        # thresholds, and safety guards are bypassed — the operator has
        # full authority.
        if self.manual_mode:
            if self.override:
                if self.override == 'ON':
                    return self._on(PumpState.ON_MANUAL, now, "Manual mode ON")
                elif self.override == 'OFF':
                    return self._off(PumpState.OFF_MANUAL, "Manual mode OFF")
            return PumpDecision('HOLD', self.current_state,
                "Manual mode active — automation frozen, awaiting operator command")

        # ── P1  Power-cut recovery ───────────────────────────
        if self.power_restore_ts:
            elapsed = now - self.power_restore_ts
            if elapsed < self.power_delay:
                rem = (self.power_delay - elapsed).total_seconds()
                return PumpDecision('OFF', PumpState.OFF_POWER_RESTORE,
                    f"Power restored {elapsed.total_seconds():.0f}s ago, waiting {rem:.0f}s")
            self.power_restore_ts = None

        # ── P2  Manual override ──────────────────────────────
        # Operator commands must override automation, including emergency thresholds.
        # An explicit OFF must be respected even when the tank is CRITICAL LOW —
        # the operator has decided the pump stays off, full stop.
        if self.override:
            if self.override_time and (now - self.override_time) > self.ovr_timeout:
                logger.info("Manual override expired")
                self.override = None
                self.override_time = None
            elif self.override == 'ON':
                return self._on(PumpState.ON_MANUAL, now, "Manual override ON")
            elif self.override == 'OFF':
                return self._off(PumpState.OFF_MANUAL, "Manual override OFF")

        if self.require_valid_lora_before_start:
            if self.last_lora_ts is None:
                return self._off(PumpState.OFF_LORA_TIMEOUT,
                    "No valid LoRa packet received yet")
            if (now - self.last_lora_ts) > self.lora_timeout:
                return self._off(PumpState.OFF_LORA_TIMEOUT,
                    f"LoRa data stale ({(now - self.last_lora_ts).total_seconds():.0f}s old)")

        # ── P2  Emergency thresholds ─────────────────────────
        if upper_pct is not None:
            if upper_pct >= self.crit_high:
                return self._off(PumpState.OFF_EMERGENCY,
                    f"Upper tank CRITICAL HIGH {upper_pct:.1f}% ≥ {self.crit_high}%")
            if upper_pct <= self.crit_low:
                return self._on(PumpState.ON_EMERGENCY, now,
                    f"Upper tank CRITICAL LOW {upper_pct:.1f}% ≤ {self.crit_low}%")

        # ── P3  Safety guards ────────────────────────────────
        # LoRa timeout
        if self.last_lora_ts and (now - self.last_lora_ts) > self.lora_timeout:
            return self._off(PumpState.OFF_LORA_TIMEOUT,
                f"No LoRa data for {(now - self.last_lora_ts).total_seconds():.0f}s")

        # Sensor fault (3+ consecutive)
        if self.consec_faults >= 3:
            return self._off(PumpState.OFF_SENSOR_FAULT,
                f"{self.consec_faults} consecutive sensor faults")

        # Max continuous run
        if pump_is_on and self.pump_start_time:
            run_time = now - self.pump_start_time
            if run_time > self.max_run:
                return self._off(PumpState.OFF_MAX_RUN,
                    f"Max run exceeded ({run_time.total_seconds()/60:.0f}min)")

        # Dry-run protection
        if (self.dry_run_on and pump_is_on
                and current_amps is not None
                and current_amps < self.dry_run_a):
            return self._off(PumpState.OFF_DRY_RUN,
                f"Dry-run detected: {current_amps:.2f}A < {self.dry_run_a}A")

        if (self.voltage_guard_enabled and pump_is_on
                and voltage_ac is not None
                and voltage_ac < self.min_voltage_ac):
            return self._off(PumpState.OFF_UNDERVOLTAGE,
                f"Undervoltage detected: {voltage_ac:.1f}V < {self.min_voltage_ac:.1f}V")

        # ── P4  ML prediction ────────────────────────────────
        if self.ml_enabled and self.ml_prediction:
            pred_h = self.ml_prediction.get('start_hour', -1)
            pred_d = self.ml_prediction.get('duration', 0)
            cur_h  = now.hour + now.minute / 60.0
            window = self.ml_window.total_seconds() / 3600.0
            delta_h = abs(cur_h - pred_h)
            circular_delta_h = min(delta_h, 24.0 - delta_h)

            if circular_delta_h < window:
                # Inside ML window — check if scheduled duration has elapsed
                if pump_is_on and self.pump_start_time:
                    run_min = (now - self.pump_start_time).total_seconds() / 60
                    if run_min >= pred_d:
                        return self._off(PumpState.OFF,
                            f"ML schedule complete ({run_min:.0f}/{pred_d:.0f}min)")
                return self._on(PumpState.ON_ML_SCHEDULED, now,
                    f"ML schedule: {pred_h:.2f}h for {pred_d:.0f}min")

        # ── P5  Normal threshold hysteresis ──────────────────
        if upper_pct is not None:
            if not pump_is_on and upper_pct <= self.low:
                return self._on(PumpState.ON_THRESHOLD, now,
                    f"Upper tank {upper_pct:.1f}% ≤ {self.low}%")
            if pump_is_on and upper_pct >= self.high:
                return self._off(PumpState.OFF,
                    f"Upper tank {upper_pct:.1f}% ≥ {self.high}%")

        # ── Default: hold current state ──────────────────────
        return PumpDecision('HOLD', self.current_state, "No trigger — holding")

    # ── Internal helpers ─────────────────────────────────────

    def _on(self, state, now, reason):
        if self.pump_start_time is None:
            self.pump_start_time = now
        self.current_state = state
        return PumpDecision('ON', state, reason)

    def _off(self, state, reason):
        self.pump_start_time = None
        self.current_state = state
        return PumpDecision('OFF', state, reason)
