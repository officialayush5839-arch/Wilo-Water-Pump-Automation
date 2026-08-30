"""
Comprehensive Unit Tests for Festival Policy Engine & Pump Logic Integration
=============================================================================
Tests all 12 scenarios mandated by the project specification:
  TEST 1: Normal day, Automatic mode, Upper tank low -> Starts normally
  TEST 2: Normal day, Automatic mode, Upper tank empty -> Starts normally (ON_EMERGENCY)
  TEST 3: Rang Panchami, Mode ON, 10:00 AM, Upper tank = 0% -> Pump remains OFF, start blocked
  TEST 4: Rang Panchami, Mode ON, 14:45, ML predicts start -> Pump remains OFF, reason = Festival Policy
  TEST 5: Rang Panchami, Mode ON, 18:59 -> Automatic start remains blocked
  TEST 6: Rang Panchami, Mode ON, 19:00 -> Restriction released
  TEST 7: Rang Panchami, 19:05, Upper tank low -> Existing automatic logic starts pump
  TEST 8: Rang Panchami, Pump running, Safety fault occurs -> Pump OFF immediately (safety never blocked)
  TEST 9: Other festival, Mode ON -> Normal automatic behavior
  TEST 10: Festival Mode OFF -> Existing system behaves exactly as before
  TEST 11: Manual Mode -> Manual controls take precedence
  TEST 12: Invalid/missing holiday data -> System safely falls back
"""

import os
import sys
import pytest
from datetime import datetime, date, time as dtime, timedelta

# Path setup
_HERE = os.path.dirname(os.path.abspath(__file__))
_PROJECT_ROOT = os.path.abspath(os.path.join(_HERE, '..', '..'))
if _PROJECT_ROOT not in sys.path:
    sys.path.insert(0, _PROJECT_ROOT)
_SRC_CONTROLLER = os.path.join(_PROJECT_ROOT, 'src', 'controller')
if _SRC_CONTROLLER not in sys.path:
    sys.path.insert(0, _SRC_CONTROLLER)

from src.controller.festival_policy import (
    FestivalPolicyEngine,
    POLICY_NORMAL,
    POLICY_RANG_PANCHAMI,
    IST,
)
from src.controller.pump_logic import HybridPumpLogic, PumpState, PumpDecision


@pytest.fixture
def temp_state_path(tmp_path):
    """Provide isolated state file path for each test."""
    return str(tmp_path / "festival_state.json")


@pytest.fixture
def festival_engine(temp_state_path):
    """Provide fresh FestivalPolicyEngine instance."""
    engine = FestivalPolicyEngine(state_path=temp_state_path)
    engine.reset()
    engine.set_mode(False)
    return engine


@pytest.fixture
def pump_logic(festival_engine):
    """Provide HybridPumpLogic wired to test festival engine."""
    logic = HybridPumpLogic(
        critical_low=10,
        low=25,
        high=85,
        critical_high=95,
        lora_timeout_s=60,
        max_run_min=180,
        dry_run_a=1.5,
        dry_run_enabled=True,
        power_delay_s=30,
        require_valid_lora_before_start=False,
        voltage_guard_enabled=True,
        min_voltage_ac=180.0,
        override_timeout_min=1440,
        ml_enabled=True,
        ml_window_min=15,
        festival_policy=festival_engine,
    )
    return logic


# ── TEST 1: Normal Day - Upper Tank Low ───────────────────────────────────────

def test_1_normal_day_automatic_low_tank(pump_logic, festival_engine):
    """On a normal non-festival day, low upper tank starts the pump normally."""
    festival_engine.set_mode(True)
    festival_engine.select_festival(None, None)
    # Simulate a normal day (e.g. 2026-05-15 10:00 AM)
    sim_dt = datetime(2026, 5, 15, 10, 0, 0, tzinfo=IST)

    decision = pump_logic.decide(
        upper_pct=20.0,  # <= low (25%)
        pump_is_on=False,
        now=sim_dt,
    )
    assert decision.action == 'ON'
    assert decision.state == PumpState.ON_THRESHOLD


# ── TEST 2: Normal Day - Upper Tank Empty ─────────────────────────────────────

def test_2_normal_day_automatic_empty_tank(pump_logic, festival_engine):
    """On a normal day, empty upper tank triggers emergency automatic start."""
    festival_engine.set_mode(True)
    festival_engine.select_festival(None, None)
    sim_dt = datetime(2026, 5, 15, 10, 0, 0, tzinfo=IST)

    decision = pump_logic.decide(
        upper_pct=0.0,  # <= crit_low (10%)
        pump_is_on=False,
        now=sim_dt,
    )
    assert decision.action == 'ON'
    assert decision.state == PumpState.ON_EMERGENCY


# ── TEST 3: Rang Panchami - 10:00 AM, Tank Empty (0%) ────────────────────────

def test_3_rang_panchami_morning_tank_empty_blocked(pump_logic, festival_engine):
    """On Rang Panchami before 19:00, pump start is blocked even when upper tank is 0%."""
    festival_engine.set_mode(True)
    # Rang Panchami 2027 is on 2027-03-27
    festival_engine.select_festival("Rang Panchami", "2027-03-27")
    sim_dt = datetime(2027, 3, 27, 10, 0, 0, tzinfo=IST)

    decision = pump_logic.decide(
        upper_pct=0.0,  # Empty upper tank!
        pump_is_on=False,
        now=sim_dt,
    )
    # Must remain OFF / HOLD, not start
    assert decision.action in ('HOLD', 'OFF')
    assert decision.state == PumpState.OFF_FESTIVAL_POLICY
    assert "Rang Panchami" in decision.reason
    assert "07:00 PM" in decision.reason


# ── TEST 4: Rang Panchami - 14:45, ML Predicts Start ──────────────────────────

def test_4_rang_panchami_ml_schedule_blocked(pump_logic, festival_engine):
    """On Rang Panchami before 19:00, ML prediction window cannot start the pump."""
    festival_engine.set_mode(True)
    festival_engine.select_festival("Rang Panchami", "2027-03-27")
    sim_dt = datetime(2027, 3, 27, 14, 45, 0, tzinfo=IST)

    # ML predicts start at 14:45 (14.75h)
    pump_logic.set_ml_prediction({'start_hour': 14.75, 'duration': 60.0})

    decision = pump_logic.decide(
        upper_pct=50.0,
        pump_is_on=False,
        now=sim_dt,
    )
    assert decision.action in ('HOLD', 'OFF')
    assert decision.state == PumpState.OFF_FESTIVAL_POLICY
    assert "Rang Panchami" in decision.reason


# ── TEST 5: Rang Panchami - 18:59, Right Before Release ───────────────────────

def test_5_rang_panchami_1859_still_blocked(pump_logic, festival_engine):
    """At 18:59 on Rang Panchami, restriction is still active."""
    festival_engine.set_mode(True)
    festival_engine.select_festival("Rang Panchami", "2027-03-27")
    sim_dt = datetime(2027, 3, 27, 18, 59, 59, tzinfo=IST)

    decision = pump_logic.decide(
        upper_pct=5.0,
        pump_is_on=False,
        now=sim_dt,
    )
    assert decision.action in ('HOLD', 'OFF')
    assert decision.state == PumpState.OFF_FESTIVAL_POLICY


# ── TEST 6: Rang Panchami - 19:00, Release Time Reached ───────────────────────

def test_6_rang_panchami_1900_restriction_released(pump_logic, festival_engine):
    """At exactly 19:00 on Rang Panchami, restriction expires and start_blocked becomes False."""
    festival_engine.set_mode(True)
    festival_engine.select_festival("Rang Panchami", "2027-03-27")
    sim_dt = datetime(2027, 3, 27, 19, 0, 0, tzinfo=IST)

    assert not festival_engine.is_start_blocked(sim_dt)
    status = festival_engine.get_status(sim_dt)
    assert status['status'] == 'RESTRICTION_RELEASED'
    assert status['automatic_start_blocked'] is False


# ── TEST 7: Rang Panchami - 19:05, Upper Tank Low -> Starts Automatically ─────

def test_7_rang_panchami_after_1900_automatic_start_permitted(pump_logic, festival_engine):
    """After 19:00 on Rang Panchami, normal automatic logic resumes and starts the pump."""
    festival_engine.set_mode(True)
    festival_engine.select_festival("Rang Panchami", "2027-03-27")
    sim_dt = datetime(2027, 3, 27, 19, 5, 0, tzinfo=IST)

    decision = pump_logic.decide(
        upper_pct=15.0,  # <= low (25%)
        pump_is_on=False,
        now=sim_dt,
    )
    assert decision.action == 'ON'
    assert decision.state == PumpState.ON_THRESHOLD


# ── TEST 8: Rang Panchami - Pump Running + Safety Fault -> Immediate OFF ──────

def test_8_rang_panchami_safety_shutdown_never_blocked(pump_logic, festival_engine):
    """Festival policy must NEVER prevent a safety shutdown (dry-run, overfill, faults)."""
    festival_engine.set_mode(True)
    festival_engine.select_festival("Rang Panchami", "2027-03-27")
    sim_dt = datetime(2027, 3, 27, 14, 0, 0, tzinfo=IST)

    # 1. Dry-run safety fault
    pump_logic.current_state = PumpState.ON_MANUAL
    decision_dry = pump_logic.decide(
        upper_pct=50.0,
        pump_is_on=True,
        current_amps=0.5,  # < dry_run_a (1.5A)
        now=sim_dt,
    )
    assert decision_dry.action == 'OFF'
    assert decision_dry.state == PumpState.OFF_DRY_RUN

    # 2. Critical high overfill fault
    decision_high = pump_logic.decide(
        upper_pct=98.0,  # >= crit_high (95%)
        pump_is_on=True,
        current_amps=5.0,
        now=sim_dt,
    )
    assert decision_high.action == 'OFF'
    assert decision_high.state == PumpState.OFF_EMERGENCY

    # 3. Undervoltage fault
    decision_uv = pump_logic.decide(
        upper_pct=50.0,
        pump_is_on=True,
        current_amps=5.0,
        voltage_ac=150.0,  # < min_voltage_ac (180V)
        now=sim_dt,
    )
    assert decision_uv.action == 'OFF'
    assert decision_uv.state == PumpState.OFF_UNDERVOLTAGE


# ── TEST 9: Other Festival (Diwali) - Mode ON -> Normal Behavior ──────────────

def test_9_other_festival_normal_automatic_behavior(pump_logic, festival_engine):
    """Other festivals (e.g. Diwali) do not inhibit pump start."""
    festival_engine.set_mode(True)
    festival_engine.select_festival("Diwali", "2026-11-08")
    sim_dt = datetime(2026, 11, 8, 14, 0, 0, tzinfo=IST)

    assert not festival_engine.is_start_blocked(sim_dt)
    decision = pump_logic.decide(
        upper_pct=15.0,
        pump_is_on=False,
        now=sim_dt,
    )
    assert decision.action == 'ON'
    assert decision.state == PumpState.ON_THRESHOLD


# ── TEST 10: Festival Mode OFF -> Standard System Behavior ───────────────────

def test_10_festival_mode_off_behaves_normally(pump_logic, festival_engine):
    """When Festival Mode is OFF, Rang Panchami date has no restriction."""
    festival_engine.set_mode(False)
    festival_engine.select_festival("Rang Panchami", "2027-03-27")
    sim_dt = datetime(2027, 3, 27, 10, 0, 0, tzinfo=IST)

    assert not festival_engine.is_start_blocked(sim_dt)
    decision = pump_logic.decide(
        upper_pct=5.0,
        pump_is_on=False,
        now=sim_dt,
    )
    assert decision.action == 'ON'
    assert decision.state == PumpState.ON_EMERGENCY


# ── TEST 11: Manual Mode Preserved During Rang Panchami ────────────────────────

def test_11_manual_mode_override_functional_on_rang_panchami(pump_logic, festival_engine):
    """Operator manual override works even on Rang Panchami before 19:00."""
    festival_engine.set_mode(True)
    festival_engine.select_festival("Rang Panchami", "2027-03-27")
    sim_dt = datetime(2027, 3, 27, 14, 0, 0, tzinfo=IST)

    # 1. Manual mode ON
    pump_logic.set_manual_mode(True)
    pump_logic.set_override('ON')
    decision_on = pump_logic.decide(
        upper_pct=50.0,
        pump_is_on=False,
        now=sim_dt,
    )
    assert decision_on.action == 'ON'
    assert decision_on.state == PumpState.ON_MANUAL

    # 2. Manual mode OFF
    pump_logic.set_override('OFF')
    decision_off = pump_logic.decide(
        upper_pct=50.0,
        pump_is_on=True,
        now=sim_dt,
    )
    assert decision_off.action == 'OFF'
    assert decision_off.state == PumpState.OFF_MANUAL


# ── TEST 12: Invalid or Missing Holiday Data -> Graceful Fallback ──────────────

def test_12_invalid_or_missing_holiday_data_fails_safe(tmp_path):
    """Missing or corrupted CSV file degrades gracefully without breaking pump logic."""
    bogus_csv = str(tmp_path / "non_existent_holidays.csv")
    bogus_state = str(tmp_path / "bogus_state.json")
    safe_engine = FestivalPolicyEngine(csv_path=bogus_csv, state_path=bogus_state)

    # Must not crash, should return safe fallback status
    status = safe_engine.get_status()
    assert status['policy'] == POLICY_NORMAL
    assert status['automatic_start_blocked'] is False

    logic = HybridPumpLogic(
        critical_low=10,
        low=25,
        high=85,
        critical_high=95,
        lora_timeout_s=60,
        max_run_min=180,
        dry_run_a=1.5,
        dry_run_enabled=False,
        power_delay_s=0,
        require_valid_lora_before_start=False,
        voltage_guard_enabled=False,
        min_voltage_ac=180.0,
        override_timeout_min=1440,
        ml_enabled=False,
        ml_window_min=15,
        festival_policy=safe_engine,
    )

    # Normal pump decision continues safely
    decision = logic.decide(upper_pct=15.0, pump_is_on=False)
    assert decision.action == 'ON'
    assert decision.state == PumpState.ON_THRESHOLD
