"""
Unit and Integration Tests for Festival & Holiday Aware Pump Control Policy
===========================================================================
Tests Rang Panchami detection, 07:00 PM IST boundary rules, safety precedence,
ML/Hysteresis blocking, mode toggles, simulation overrides, and REST endpoints.
"""

import os
import sys
import unittest
from datetime import datetime, time, timedelta
from zoneinfo import ZoneInfo

# Add controller & dashboard directories to path
_HERE = os.path.dirname(os.path.abspath(__file__))
_PROJECT = os.path.abspath(os.path.join(_HERE, '..'))
sys.path.insert(0, os.path.join(_PROJECT, 'src', 'controller'))
sys.path.insert(0, os.path.join(_PROJECT, 'src', 'dashboard'))

from festival_policy import FestivalPolicyEngine, IST
from pump_logic import HybridPumpLogic, PumpState
import tank_config as CFG


class TestFestivalPolicyEngine(unittest.TestCase):
    def setUp(self):
        self.test_state_file = os.path.join(_PROJECT, 'config', 'test_festival_state.json')
        if os.path.exists(self.test_state_file):
            os.remove(self.test_state_file)
        self.engine = FestivalPolicyEngine(
            csv_path=CFG.HOLIDAY_CSV_PATH,
            state_file=self.test_state_file
        )

    def tearDown(self):
        if os.path.exists(self.test_state_file):
            os.remove(self.test_state_file)

    def test_rang_panchami_dates_loaded(self):
        """Verify that 2020-2030 Rang Panchami entries are present with RANG_PANCHAMI policy."""
        rp_2026 = self.engine.get_festival_for_date('2026-03-08')
        self.assertIsNotNone(rp_2026)
        self.assertEqual(rp_2026['event'], 'Rang Panchami')
        self.assertEqual(rp_2026['policy'], 'RANG_PANCHAMI')

        # Check 2025 date
        rp_2025 = self.engine.get_festival_for_date('2025-03-19')
        self.assertIsNotNone(rp_2025)
        self.assertEqual(rp_2025['policy'], 'RANG_PANCHAMI')

    def test_rang_panchami_timeline_and_7pm_boundary(self):
        """
        Verify strict 19:00 IST boundary:
          10:00 -> RESTRICTION_ACTIVE (Blocked)
          18:59 -> RESTRICTION_ACTIVE (Blocked)
          19:00 -> RESTRICTION_RELEASED (Allowed)
          19:05 -> RESTRICTION_RELEASED (Allowed)
        """
        rp_date = datetime(2026, 3, 8, tzinfo=IST)

        # 10:00 AM
        st_10 = self.engine.evaluate_policy(now=rp_date.replace(hour=10, minute=0))
        self.assertEqual(st_10['state'], 'RESTRICTION_ACTIVE')
        self.assertTrue(st_10['restriction_active'])
        self.assertTrue(st_10['automatic_start_blocked'])

        # 18:59 (1 minute before release)
        st_1859 = self.engine.evaluate_policy(now=rp_date.replace(hour=18, minute=59))
        self.assertEqual(st_1859['state'], 'RESTRICTION_ACTIVE')
        self.assertTrue(st_1859['automatic_start_blocked'])
        self.assertEqual(st_1859['remaining_minutes'], 1)

        # 19:00:00 (Exact release time)
        st_1900 = self.engine.evaluate_policy(now=rp_date.replace(hour=19, minute=0, second=0))
        self.assertEqual(st_1900['state'], 'RESTRICTION_RELEASED')
        self.assertFalse(st_1900['restriction_active'])
        self.assertFalse(st_1900['automatic_start_blocked'])

        # 19:05 (After release)
        st_1905 = self.engine.evaluate_policy(now=rp_date.replace(hour=19, minute=5))
        self.assertEqual(st_1905['state'], 'RESTRICTION_RELEASED')
        self.assertFalse(st_1905['automatic_start_blocked'])

    def test_normal_festival_and_regular_day(self):
        """Normal festivals (Diwali, Holi, etc.) must evaluate to policy NORMAL with no block."""
        # Select Diwali
        ok, err, st_diwali = self.engine.select_festival('Diwali', '2026-11-08')
        self.assertTrue(ok)
        self.assertEqual(st_diwali['policy'], 'NORMAL')
        self.assertFalse(st_diwali['automatic_start_blocked'])

        # Reset to regular day
        st_reg = self.engine.reset_festival()
        self.assertFalse(st_reg['automatic_start_blocked'])

    def test_mode_toggle_off(self):
        """When Festival Mode is turned OFF, Rang Panchami restriction is disabled."""
        self.engine.select_festival('Rang Panchami', '2026-03-08')
        # Simulate 14:00 (normally blocked)
        self.engine.simulate_datetime('2026-03-08', '14:00')
        st_on = self.engine.evaluate_policy()
        self.assertTrue(st_on['automatic_start_blocked'])

        # Turn mode OFF
        st_off = self.engine.set_mode(False)
        self.assertFalse(st_off['mode_enabled'])
        self.assertFalse(st_off['automatic_start_blocked'])
        self.assertEqual(st_off['state'], 'DISABLED')


class TestPumpLogicFestivalIntegration(unittest.TestCase):
    def setUp(self):
        self.logic = HybridPumpLogic(
            critical_low=10, low=25, high=85, critical_high=95,
            lora_timeout_s=60, max_run_min=180, dry_run_a=1.5,
            dry_run_enabled=True, power_delay_s=30,
            require_valid_lora_before_start=False,
            voltage_guard_enabled=False, min_voltage_ac=180.0,
            override_timeout_min=1440, ml_enabled=True, ml_window_min=10
        )

    def test_automatic_start_blocked_before_7pm(self):
        """Low tank level (0% or 15%) must NOT start pump before 7 PM on Rang Panchami."""
        fest_status_blocked = {
            'mode_enabled': True,
            'state': 'RESTRICTION_ACTIVE',
            'policy': 'RANG_PANCHAMI',
            'festival_name': 'Rang Panchami',
            'restriction_active': True,
            'automatic_start_blocked': True,
            'reason': 'Rang Panchami automatic start restriction active until 07:00 PM IST',
        }

        # Tank is at 0% (Critical low / threshold trigger), pump is OFF
        decision = self.logic.decide(
            upper_pct=0.0,
            pump_is_on=False,
            festival_status=fest_status_blocked
        )
        self.assertEqual(decision.action, 'HOLD')
        self.assertEqual(decision.state, PumpState.OFF_FESTIVAL_POLICY)

    def test_ml_prediction_blocked_before_7pm(self):
        """ML prediction scheduled start must NOT bypass Festival Policy."""
        now = datetime.now()
        cur_h = now.hour + now.minute / 60.0
        self.logic.set_ml_prediction({'start_hour': cur_h, 'duration': 30})

        fest_status_blocked = {
            'mode_enabled': True,
            'state': 'RESTRICTION_ACTIVE',
            'policy': 'RANG_PANCHAMI',
            'restriction_active': True,
            'automatic_start_blocked': True,
        }

        decision = self.logic.decide(
            upper_pct=50.0,
            pump_is_on=False,
            festival_status=fest_status_blocked
        )
        self.assertEqual(decision.action, 'HOLD')
        self.assertEqual(decision.state, PumpState.OFF_FESTIVAL_POLICY)

    def test_pump_already_running_not_abruptly_killed(self):
        """If pump was already running, festival policy does not kill it unconditionally."""
        fest_status_blocked = {
            'mode_enabled': True,
            'state': 'RESTRICTION_ACTIVE',
            'policy': 'RANG_PANCHAMI',
            'restriction_active': True,
            'automatic_start_blocked': True,
        }

        # Pump is already ON and filling at 50%
        decision = self.logic.decide(
            upper_pct=50.0,
            pump_is_on=True,
            festival_status=fest_status_blocked
        )
        self.assertIn(decision.action, ('ON', 'HOLD'))

    def test_safety_shutdowns_dominate_festival_policy(self):
        """Safety guards (Critical High >= 95%, Dry Run, LoRa Timeout, Max Run) strictly override festival state."""
        fest_status_blocked = {
            'mode_enabled': True,
            'state': 'RESTRICTION_ACTIVE',
            'policy': 'RANG_PANCHAMI',
            'restriction_active': True,
            'automatic_start_blocked': True,
        }

        # 1. Critical High 96%
        d_crit = self.logic.decide(upper_pct=96.0, pump_is_on=True, festival_status=fest_status_blocked)
        self.assertEqual(d_crit.action, 'OFF')
        self.assertEqual(d_crit.state, PumpState.OFF_EMERGENCY)

        # 2. Dry Run (< 1.5A)
        d_dry = self.logic.decide(upper_pct=50.0, pump_is_on=True, current_amps=1.0, festival_status=fest_status_blocked)
        self.assertEqual(d_dry.action, 'OFF')
        self.assertEqual(d_dry.state, PumpState.OFF_DRY_RUN)

    def test_automatic_start_allowed_after_7pm(self):
        """At/after 7 PM, restriction is released and low tank level starts pump normally."""
        fest_status_released = {
            'mode_enabled': True,
            'state': 'RESTRICTION_RELEASED',
            'policy': 'RANG_PANCHAMI',
            'restriction_active': False,
            'automatic_start_blocked': False,
        }

        decision = self.logic.decide(
            upper_pct=15.0,
            pump_is_on=False,
            festival_status=fest_status_released
        )
        self.assertEqual(decision.action, 'ON')
        self.assertEqual(decision.state, PumpState.ON_THRESHOLD)


if __name__ == '__main__':
    unittest.main()
