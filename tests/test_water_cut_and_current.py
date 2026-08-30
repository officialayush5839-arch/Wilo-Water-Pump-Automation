"""
Unit Tests for Wilo Municipal Water Cut & Current Classifier Features
=====================================================================
Validates all features, edge cases, filtering, and priority stacks.
"""

import os
import sys
import json
import unittest
from datetime import datetime, timedelta

# Path setup
PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
SRC_CONTROLLER = os.path.join(PROJECT_ROOT, 'src', 'controller')
sys.path.insert(0, PROJECT_ROOT)
sys.path.insert(0, SRC_CONTROLLER)

from water_cut_manager import WaterCutManager
from current_classifier import CurrentClassifier
from pump_logic import HybridPumpLogic, PumpState
import tank_config as CFG


class TestWaterCutManager(unittest.TestCase):
    def setUp(self):
        self.test_cuts_file = os.path.join(PROJECT_ROOT, 'config', 'test_water_cuts.json')
        if os.path.exists(self.test_cuts_file):
            os.remove(self.test_cuts_file)
        self.manager = WaterCutManager(self.test_cuts_file, default_reserve_pct=95.0, default_prefill_hours=4.0)

    def tearDown(self):
        if os.path.exists(self.test_cuts_file):
            os.remove(self.test_cuts_file)

    def test_add_and_load_cut(self):
        now = datetime.now()
        start = (now + timedelta(hours=2)).isoformat()
        end = (now + timedelta(hours=6)).isoformat()

        payload = {
            'start_time': start,
            'end_time': end,
            'target_reserve_pct': 95,
            'pre_fill_hours': 3,
            'reason': 'Pipeline pressure maintenance',
        }
        ok, err, cut = self.manager.add_cut(payload)
        self.assertTrue(ok)
        self.assertIsNotNone(cut)
        self.assertEqual(cut['target_reserve_pct'], 95.0)

        # Verify disk persistence
        reloaded = WaterCutManager(self.test_cuts_file)
        all_cuts = reloaded.get_all_cuts()
        self.assertEqual(len(all_cuts), 1)
        self.assertEqual(all_cuts[0]['reason'], 'Pipeline pressure maintenance')

    def test_validation_errors(self):
        # Invalid time ordering (end before start)
        now = datetime.now()
        ok, err, _ = self.manager.add_cut({
            'start_time': (now + timedelta(hours=5)).isoformat(),
            'end_time': (now + timedelta(hours=2)).isoformat(),
            'target_reserve_pct': 95,
            'pre_fill_hours': 4,
        })
        self.assertFalse(ok)
        self.assertIn("strictly after start_time", err)

        # Invalid reserve percentage
        ok, err, _ = self.manager.add_cut({
            'start_time': now.isoformat(),
            'end_time': (now + timedelta(hours=2)).isoformat(),
            'target_reserve_pct': 150,
            'pre_fill_hours': 4,
        })
        self.assertFalse(ok)

    def test_state_evaluation_prefill_and_active(self):
        now = datetime.now()
        # Cut is 2 hours in future, prefill is 4 hours -> we are currently in PREFILL
        start = now + timedelta(hours=2)
        end = now + timedelta(hours=6)

        self.manager.add_cut({
            'start_time': start.isoformat(),
            'end_time': end.isoformat(),
            'target_reserve_pct': 95,
            'pre_fill_hours': 4,
            'reason': 'Pre-fill test cut',
        })

        status_prefill = self.manager.get_status(now=now)
        self.assertEqual(status_prefill['state'], 'PREFILL')
        self.assertTrue(status_prefill['is_prefill_active'])
        self.assertFalse(status_prefill['is_cut_active'])
        self.assertEqual(status_prefill['target_reserve_pct'], 95.0)

        # Advance time to inside cut window
        inside_cut_time = start + timedelta(minutes=30)
        status_active = self.manager.get_status(now=inside_cut_time)
        self.assertEqual(status_active['state'], 'WATER_CUT_ACTIVE')
        self.assertTrue(status_active['is_cut_active'])
        self.assertFalse(status_active['is_prefill_active'])


class TestCurrentClassifier(unittest.TestCase):
    def setUp(self):
        self.classifier = CurrentClassifier(
            empty_threshold=11.5,
            mid_low=8.0,
            mid_high=10.0,
            full_threshold=6.5,
            dry_run_threshold=1.5,
            filter_window=10,
            startup_blanking_sec=5.0,
            full_persistence_sec=5.0,
        )

    def test_pump_off_is_unknown_not_empty(self):
        # 0A when pump is OFF must be UNKNOWN, never EMPTY
        res = self.classifier.update(current_amps=0.0, pump_is_on=False)
        self.assertEqual(res['state'], 'UNKNOWN')
        self.assertFalse(res['full_persisted'])

    def test_startup_blanking_window(self):
        t0 = datetime.now()
        # First sample after pump start (t = t0 + 1s)
        res1 = self.classifier.update(current_amps=6.0, pump_is_on=True, now=t0 + timedelta(seconds=1))
        self.assertEqual(res1['state'], 'STARTING')
        self.assertTrue(res1['startup_blanking'])
        self.assertFalse(res1['full_persisted'])

        # 4 seconds in (still in 5s blanking)
        res2 = self.classifier.update(current_amps=6.0, pump_is_on=True, now=t0 + timedelta(seconds=4))
        self.assertEqual(res2['state'], 'STARTING')

    def test_hydraulic_states_and_full_persistence(self):
        t0 = datetime.now()
        # Start pump with steady EMPTY readings
        for i in range(10):
            self.classifier.update(current_amps=12.0, pump_is_on=True, now=t0 + timedelta(seconds=i*0.5))

        # After blanking (t0 + 6s) with ~12A (>= 11.5A) -> EMPTY
        res_empty = self.classifier.update(current_amps=12.1, pump_is_on=True, now=t0 + timedelta(seconds=6))
        self.assertEqual(res_empty['state'], 'EMPTY')

        # Transition to ~9A (8.0 - 10.0A) -> feed steady samples to establish median
        for i in range(10):
            res_mid = self.classifier.update(current_amps=9.0, pump_is_on=True, now=t0 + timedelta(seconds=7 + i*0.2))
        self.assertEqual(res_mid['state'], 'MID')

        # Transition to ~6A (<= 6.5A) -> FULL, test 5s persistence
        t_full = t0 + timedelta(seconds=10)
        # Feed samples to shift median to 6.0A
        for i in range(10):
            res_full1 = self.classifier.update(current_amps=6.0, pump_is_on=True, now=t_full + timedelta(seconds=i*0.1))
        self.assertEqual(res_full1['state'], 'FULL')
        self.assertFalse(res_full1['full_persisted']) # Just reached full

        # 3 seconds later (still FULL but persistence < 5s)
        res_full2 = self.classifier.update(current_amps=6.1, pump_is_on=True, now=t_full + timedelta(seconds=3))
        self.assertEqual(res_full2['state'], 'FULL')
        self.assertFalse(res_full2['full_persisted'])

        # 6 seconds later (persisted >= 5s) -> full_persisted = True
        res_full3 = self.classifier.update(current_amps=6.2, pump_is_on=True, now=t_full + timedelta(seconds=6))
        self.assertEqual(res_full3['state'], 'FULL')
        self.assertTrue(res_full3['full_persisted'])


class TestPumpLogicIntegration(unittest.TestCase):
    def setUp(self):
        self.logic = HybridPumpLogic(
            critical_low=10, low=25, high=85, critical_high=95,
            lora_timeout_s=60, max_run_min=180, dry_run_a=1.5,
            dry_run_enabled=True, power_delay_s=30,
            require_valid_lora_before_start=False,
            voltage_guard_enabled=False, min_voltage_ac=180.0,
            override_timeout_min=1440, ml_enabled=False, ml_window_min=5
        )

    def test_current_cutoff_when_full(self):
        # Pump running, tank level 75%, current classifier indicates full_persisted = True
        current_class = {
            'state': 'FULL',
            'filtered_amps': 6.1,
            'full_persisted': True,
            'full_persistence_seconds': 5.5,
        }
        dec = self.logic.decide(
            upper_pct=75.0,
            pump_is_on=True,
            current_amps=6.1,
            current_classification=current_class,
        )
        self.assertEqual(dec.action, 'OFF')
        self.assertEqual(dec.state, PumpState.OFF_CURRENT_FULL)

    def test_water_cut_active_holds_pump(self):
        # When water cut is active, pump should be OFF / HOLD to conserve water
        water_cut_status = {
            'state': 'WATER_CUT_ACTIVE',
            'is_cut_active': True,
            'is_prefill_active': False,
        }
        # If tank is low (20%), normally it turns on, but water cut active holds it
        dec = self.logic.decide(
            upper_pct=20.0,
            pump_is_on=False,
            water_cut_status=water_cut_status,
        )
        self.assertEqual(dec.action, 'HOLD')
        self.assertEqual(dec.state, PumpState.OFF_WATER_CUT)

    def test_water_cut_prefill_targets_95_percent(self):
        # When prefill is active, fills to 95%
        water_cut_status = {
            'state': 'PREFILL',
            'is_cut_active': False,
            'is_prefill_active': True,
            'target_reserve_pct': 95.0,
            'prefill_remaining_min': 120,
        }
        # Tank at 70% (above normal start threshold 25%, but below prefill target 95%) -> turns ON
        dec = self.logic.decide(
            upper_pct=70.0,
            pump_is_on=False,
            water_cut_status=water_cut_status,
        )
        self.assertEqual(dec.action, 'ON')
        self.assertEqual(dec.state, PumpState.ON_WATER_CUT_PREFILL)

        # When tank reaches 95% -> stops
        dec_full = self.logic.decide(
            upper_pct=95.2,
            pump_is_on=True,
            water_cut_status=water_cut_status,
        )
        self.assertEqual(dec_full.action, 'OFF')


if __name__ == '__main__':
    unittest.main()
