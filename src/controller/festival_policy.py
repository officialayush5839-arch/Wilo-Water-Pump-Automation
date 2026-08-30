"""
Festival / Holiday Aware Pump Control Policy
=============================================
Provides deterministic, context-aware festival policy evaluation for pump control.
On Rang Panchami, automatic pump start is inhibited prior to 19:00 (07:00 PM) IST.
At 19:00 IST, restriction is released to resume normal automatic control.
Safety shutdowns (dry-run, overfill, faults) and manual operations are never blocked.
"""

from __future__ import annotations

import os
import sys
import logging
from datetime import datetime, date, time as dtime, timedelta
import pandas as pd

try:
    from zoneinfo import ZoneInfo
except ImportError:
    from pytz import timezone as ZoneInfo

_HERE = os.path.dirname(os.path.abspath(__file__))
_PROJECT_ROOT = os.path.abspath(os.path.join(_HERE, '..', '..'))
if _PROJECT_ROOT not in sys.path:
    sys.path.insert(0, _PROJECT_ROOT)
if _HERE not in sys.path:
    sys.path.insert(0, _HERE)

import tank_config as CFG
from runtime_channel import atomic_write_json, read_json

logger = logging.getLogger('wilo.festival')

# Central timezone configuration for India
try:
    IST = ZoneInfo('Asia/Kolkata')
except Exception:
    # Fallback to fixed offset UTC+05:30 if system tz database missing
    from datetime import timezone
    IST = timezone(timedelta(hours=5, minutes=30))

HOLIDAY_CSV_PATH = os.path.join(_PROJECT_ROOT, 'data', 'raw', 'Holidays_2020_2030.csv')
FESTIVAL_STATE_PATH = os.path.join(CFG.LOG_DIR, 'festival_state.json')

# Release time for Rang Panchami automatic start restriction: 19:00 (07:00 PM IST)
RANG_PANCHAMI_RELEASE_HOUR = 19
RANG_PANCHAMI_RELEASE_MINUTE = 0

POLICY_NORMAL = 'NORMAL'
POLICY_RANG_PANCHAMI = 'RANG_PANCHAMI'


class FestivalPolicyEngine:
    """
    Deterministic rule engine for festival-aware pump control.
    """

    def __init__(self, csv_path: str = HOLIDAY_CSV_PATH, state_path: str = FESTIVAL_STATE_PATH):
        self.csv_path = csv_path
        self.state_path = state_path
        self.holiday_df: pd.DataFrame | None = None
        self._load_holiday_data()
        self._ensure_state_file()

    # ── Data Loading & State Management ──────────────────────────────────────────

    def _load_holiday_data(self) -> None:
        """Load and parse holiday data with error handling."""
        try:
            if not os.path.exists(self.csv_path):
                logger.warning(f"Holiday CSV file not found at {self.csv_path}")
                self.holiday_df = None
                return

            df = pd.read_csv(self.csv_path)
            # Standardize date column
            df['parsed_date'] = pd.to_datetime(df['date'], format='%B %d, %Y, %A', errors='coerce')
            df['iso_date'] = df['parsed_date'].dt.strftime('%Y-%m-%d')
            if 'control_policy' not in df.columns:
                df['control_policy'] = POLICY_NORMAL
            else:
                df['control_policy'] = df['control_policy'].fillna(POLICY_NORMAL)

            self.holiday_df = df
            logger.info(f"Loaded {len(df)} festival records into FestivalPolicyEngine")
        except Exception as exc:
            logger.error(f"Failed to load holiday data: {exc}", exc_info=True)
            self.holiday_df = None

    def _ensure_state_file(self) -> None:
        """Ensure state file exists with default schema."""
        state = self.read_state()
        if state is None:
            initial = {
                'mode_enabled': False,
                'selected_festival': None,
                'selected_date': None,
                'simulated_date': None,
                'simulated_time': None,
                'updated_at': datetime.now(IST).isoformat(),
            }
            try:
                atomic_write_json(self.state_path, initial)
            except Exception as exc:
                logger.warning(f"Unable to write initial festival state: {exc}")

    def read_state(self) -> dict:
        """Read saved state safely."""
        try:
            state = read_json(self.state_path)
            if isinstance(state, dict):
                return state
        except Exception as exc:
            logger.warning(f"Error reading festival state: {exc}")
        return {
            'mode_enabled': False,
            'selected_festival': None,
            'selected_date': None,
            'simulated_date': None,
            'simulated_time': None,
            'updated_at': datetime.now(IST).isoformat(),
        }

    def save_state(self, updates: dict) -> dict:
        """Atomically update state."""
        current = self.read_state()
        current.update(updates)
        current['updated_at'] = datetime.now(IST).isoformat()
        try:
            atomic_write_json(self.state_path, current)
        except Exception as exc:
            logger.error(f"Failed to save festival state: {exc}")
        return current

    # ── Time and Date Resolution ───────────────────────────────────────────────

    def get_current_time(self, now: datetime | None = None) -> datetime:
        """
        Returns the current datetime in IST.
        Supports optional simulation override (simulated_date / simulated_time) for developer testing.
        """
        if now is not None:
            # Ensure timezone awareness
            if now.tzinfo is None:
                return now.replace(tzinfo=IST)
            return now.astimezone(IST)

        state = self.read_state()
        sim_date_str = state.get('simulated_date')
        sim_time_str = state.get('simulated_time')

        if sim_date_str:
            try:
                d = datetime.strptime(sim_date_str, '%Y-%m-%d').date()
                if sim_time_str:
                    t = datetime.strptime(sim_time_str, '%H:%M').time()
                else:
                    t = datetime.now(IST).time()
                return datetime.combine(d, t).replace(tzinfo=IST)
            except Exception as exc:
                logger.warning(f"Malformed simulated datetime '{sim_date_str} {sim_time_str}': {exc}")

        return datetime.now(IST)

    # ── Festival Queries ────────────────────────────────────────────────────────

    def get_all_festivals(self) -> list[dict]:
        """Return list of all parsed festival entries."""
        if self.holiday_df is None:
            return []
        records = []
        for _, row in self.holiday_df.iterrows():
            if pd.isna(row.get('iso_date')):
                continue
            records.append({
                'year': int(row['year']),
                'date_str': str(row['date']),
                'iso_date': str(row['iso_date']),
                'event': str(row['event']),
                'type': str(row.get('type', 'Other')),
                'control_policy': str(row.get('control_policy', POLICY_NORMAL)),
            })
        return records

    def get_festivals_for_date(self, target_date: date | str) -> list[dict]:
        """Return all festival entries matching a specific date (YYYY-MM-DD)."""
        if self.holiday_df is None:
            return []
        if isinstance(target_date, date):
            iso_str = target_date.strftime('%Y-%m-%d')
        else:
            iso_str = str(target_date)

        matched = self.holiday_df[self.holiday_df['iso_date'] == iso_str]
        results = []
        for _, row in matched.iterrows():
            results.append({
                'year': int(row['year']),
                'date_str': str(row['date']),
                'iso_date': str(row['iso_date']),
                'event': str(row['event']),
                'type': str(row.get('type', 'Other')),
                'control_policy': str(row.get('control_policy', POLICY_NORMAL)),
            })
        return results

    def get_today_festival(self, now: datetime | None = None) -> dict | None:
        """
        Return the primary festival on today's date (prioritizing RANG_PANCHAMI if multiple).
        """
        current_dt = self.get_current_time(now)
        festivals = self.get_festivals_for_date(current_dt.date())
        if not festivals:
            return None
        # If Rang Panchami is present on this date, return it
        for f in festivals:
            if f.get('control_policy') == POLICY_RANG_PANCHAMI or 'rang panchami' in f.get('event', '').lower():
                return f
        return festivals[0]

    def is_festival_day(self, now: datetime | None = None) -> bool:
        """Check if today is any festival day."""
        return self.get_today_festival(now) is not None

    def is_rang_panchami(self, now: datetime | None = None) -> bool:
        """
        Determine if current date is Rang Panchami with strict date validation.
        """
        current_dt = self.get_current_time(now)
        state = self.read_state()

        # Check if selected festival is Rang Panchami and corresponds to actual/simulated date
        selected_name = state.get('selected_festival')
        selected_date = state.get('selected_date')
        today_iso = current_dt.date().strftime('%Y-%m-%d')

        if selected_name and 'rang panchami' in selected_name.lower():
            # Validate that selected date matches current date
            if selected_date == today_iso:
                return True

        # Check natural calendar match for today's date
        today_f = self.get_today_festival(now)
        if today_f:
            if today_f.get('control_policy') == POLICY_RANG_PANCHAMI or 'rang panchami' in today_f.get('event', '').lower():
                return True

        return False

    def get_policy(self, now: datetime | None = None) -> str:
        """
        Return active policy: RANG_PANCHAMI or NORMAL.
        """
        state = self.read_state()
        if not state.get('mode_enabled', False):
            return POLICY_NORMAL

        if self.is_rang_panchami(now):
            return POLICY_RANG_PANCHAMI

        return POLICY_NORMAL

    # ── Policy Enforcement Rules ────────────────────────────────────────────────

    def is_release_time_reached(self, now: datetime | None = None) -> bool:
        """
        Check whether 19:00:00 (07:00 PM) IST has arrived.
        """
        current_dt = self.get_current_time(now)
        release_threshold = dtime(RANG_PANCHAMI_RELEASE_HOUR, RANG_PANCHAMI_RELEASE_MINUTE, 0)
        return current_dt.time() >= release_threshold

    def is_start_blocked(self, now: datetime | None = None) -> bool:
        """
        Core decision rule:
        Returns True IF and ONLY IF:
          - Festival Mode is enabled
          - Policy is RANG_PANCHAMI
          - Current time is before 19:00 IST
        Returns False in all other cases.
        """
        state = self.read_state()
        if not state.get('mode_enabled', False):
            return False

        if not self.is_rang_panchami(now):
            return False

        # On Rang Panchami, start is blocked before 19:00 IST
        if not self.is_release_time_reached(now):
            return True

        return False

    def get_status(self, now: datetime | None = None) -> dict:
        """
        Returns full status dictionary suitable for backend API and frontend display.
        """
        current_dt = self.get_current_time(now)
        state = self.read_state()
        mode_enabled = bool(state.get('mode_enabled', False))
        is_rp = self.is_rang_panchami(now)
        policy = POLICY_RANG_PANCHAMI if (mode_enabled and is_rp) else POLICY_NORMAL
        release_reached = self.is_release_time_reached(now)
        start_blocked = mode_enabled and is_rp and (not release_reached)

        today_fest = self.get_today_festival(now)
        fest_name = state.get('selected_festival') or (today_fest.get('event') if today_fest else None)
        fest_date = state.get('selected_date') or (today_fest.get('iso_date') if today_fest else current_dt.date().strftime('%Y-%m-%d'))

        if not mode_enabled:
            status_text = "INACTIVE"
            reason = "Festival Mode is OFF — standard automatic/manual control active"
        elif not is_rp:
            status_text = "NORMAL_SCHEDULE"
            reason = f"{fest_name or 'Normal day'} — standard pump scheduling (no festival restriction)"
        elif start_blocked:
            status_text = "WAITING_FOR_RELEASE"
            reason = "Rang Panchami automatic-start restriction active until 07:00 PM IST"
        else:
            status_text = "RESTRICTION_RELEASED"
            reason = "Rang Panchami restriction released (after 07:00 PM IST) — standard automatic control resumed"

        return {
            'mode_enabled': mode_enabled,
            'policy': policy,
            'is_rang_panchami': is_rp,
            'festival_name': fest_name,
            'festival_date': fest_date,
            'restriction_active': start_blocked,
            'automatic_start_blocked': start_blocked,
            'release_time': f"{RANG_PANCHAMI_RELEASE_HOUR:02d}:{RANG_PANCHAMI_RELEASE_MINUTE:02d}",
            'status': status_text,
            'reason': reason,
            'current_ist_time': current_dt.strftime('%Y-%m-%d %H:%M:%S'),
            'simulation': {
                'simulated_date': state.get('simulated_date'),
                'simulated_time': state.get('simulated_time'),
                'is_simulating': bool(state.get('simulated_date')),
            }
        }

    # ── State Mutation Methods ──────────────────────────────────────────────────

    def set_mode(self, enabled: bool) -> dict:
        """Enable or disable festival mode."""
        logger.info(f"[FESTIVAL] Festival mode {'ENABLED' if enabled else 'DISABLED'}")
        return self.save_state({'mode_enabled': bool(enabled)})

    def select_festival(self, festival_name: str | None, festival_date: str | None) -> dict:
        """Set user-selected festival and date (with validation)."""
        logger.info(f"[FESTIVAL] Selected festival: {festival_name} on {festival_date}")
        return self.save_state({
            'selected_festival': festival_name,
            'selected_date': festival_date,
        })

    def reset(self) -> dict:
        """Reset selections and simulations."""
        logger.info("[FESTIVAL] Festival state reset")
        return self.save_state({
            'selected_festival': None,
            'selected_date': None,
            'simulated_date': None,
            'simulated_time': None,
        })

    def set_simulation(self, sim_date: str | None, sim_time: str | None) -> dict:
        """Set developer/demo simulation date (YYYY-MM-DD) and time (HH:MM)."""
        logger.info(f"[FESTIVAL] Developer simulation set: date={sim_date}, time={sim_time}")
        return self.save_state({
            'simulated_date': sim_date,
            'simulated_time': sim_time,
        })


# Singleton instance for system-wide use
_festival_engine_instance: FestivalPolicyEngine | None = None

def get_festival_policy_engine() -> FestivalPolicyEngine:
    global _festival_engine_instance
    if _festival_engine_instance is None:
        _festival_engine_instance = FestivalPolicyEngine()
    return _festival_engine_instance
