"""
Festival & Holiday Aware Pump Control Policy Engine
===================================================
Authoritative engine for Indian festival detection, holiday calendar management,
and special pump scheduling rules (e.g., Rang Panchami 07:00 PM IST release policy).

Timezone: Asia/Kolkata (IST)
"""

from __future__ import annotations

import csv
import json
import logging
import os
from datetime import datetime, time, timedelta
from typing import Any, Dict, List, Optional, Tuple
from zoneinfo import ZoneInfo

logger = logging.getLogger('wilo.festival')

# Default IST Timezone
IST = ZoneInfo('Asia/Kolkata')

# Default Rang Panchami Dates (2020-2030) — 5th day after Holi (Chaitra Krishna Panchami)
RANG_PANCHAMI_DATES = {
    2020: '2020-03-14',
    2021: '2021-04-02',
    2022: '2022-03-22',
    2023: '2023-03-12',
    2024: '2024-03-30',
    2025: '2025-03-19',
    2026: '2026-03-08',
    2027: '2027-03-27',
    2028: '2028-03-16',
    2029: '2029-04-03',
    2030: '2030-03-24',
}


class FestivalPolicyEngine:
    """Stateful policy engine evaluating holiday calendars and pump control rules."""

    def __init__(
        self,
        csv_path: Optional[str] = None,
        state_file: Optional[str] = None,
    ):
        self.csv_path = csv_path
        self.state_file = state_file

        # Runtime State
        self.mode_enabled: bool = True
        self.selected_festival: Optional[Dict[str, Any]] = None
        self.simulated_datetime: Optional[datetime] = None  # In IST

        # Holiday Calendar Data: List of dicts {'year': int, 'date': 'YYYY-MM-DD', 'event': str, 'type': str, 'policy': str}
        self.holidays: List[Dict[str, Any]] = []
        self._load_csv()
        self._load_state()

    # ── Persistence ───────────────────────────────────────────

    def _load_state(self) -> None:
        """Load persistent festival settings from JSON file."""
        if not self.state_file or not os.path.exists(self.state_file):
            return
        try:
            with open(self.state_file, 'r', encoding='utf-8') as f:
                data = json.load(f)
                if isinstance(data, dict):
                    self.mode_enabled = bool(data.get('mode_enabled', True))
                    self.selected_festival = data.get('selected_festival')
                    sim_dt = data.get('simulated_datetime')
                    if sim_dt:
                        try:
                            self.simulated_datetime = datetime.fromisoformat(sim_dt)
                        except ValueError:
                            self.simulated_datetime = None
            logger.info("Loaded festival policy state: enabled=%s, selected=%s",
                        self.mode_enabled, self.selected_festival)
        except Exception as e:
            logger.error("Failed to load festival state from %s: %s", self.state_file, e)

    def _save_state(self) -> bool:
        """Persist current festival settings to disk atomically."""
        if not self.state_file:
            return False
        try:
            os.makedirs(os.path.dirname(os.path.abspath(self.state_file)), exist_ok=True)
            temp_file = f"{self.state_file}.tmp"
            payload = {
                'mode_enabled': self.mode_enabled,
                'selected_festival': self.selected_festival,
                'simulated_datetime': self.simulated_datetime.isoformat() if self.simulated_datetime else None,
                'updated_at': datetime.now(IST).isoformat(),
            }
            with open(temp_file, 'w', encoding='utf-8') as f:
                json.dump(payload, f, indent=2)
            if os.name == 'nt' and os.path.exists(self.state_file):
                os.remove(self.state_file)
            os.replace(temp_file, self.state_file)
            return True
        except Exception as e:
            logger.error("Failed to save festival state: %s", e)
            return False

    # ── CSV Loading ───────────────────────────────────────────

    def _load_csv(self) -> None:
        """Load and parse holiday records, injecting verified Rang Panchami entries."""
        self.holidays = []
        parsed_dates = set()

        if self.csv_path and os.path.exists(self.csv_path):
            try:
                with open(self.csv_path, 'r', encoding='utf-8') as f:
                    reader = csv.reader(f)
                    header = next(reader, None)
                    for row in reader:
                        if len(row) < 3:
                            continue
                        year_str = row[0].strip()
                        date_raw = row[1].strip()
                        event_name = row[2].strip()
                        event_type = row[3].strip() if len(row) > 3 else "General"
                        policy = row[4].strip() if len(row) > 4 else "NORMAL"

                        # Parse date string e.g. "April 10, 2020, Friday" or "YYYY-MM-DD"
                        iso_date = self._parse_csv_date(date_raw, year_str)
                        if iso_date:
                            if 'rang panchami' in event_name.lower():
                                policy = "RANG_PANCHAMI"
                            self.holidays.append({
                                'year': int(year_str) if year_str.isdigit() else 2026,
                                'date': iso_date,
                                'event': event_name,
                                'type': event_type,
                                'policy': policy,
                            })
                            parsed_dates.add((iso_date, event_name.lower()))
            except Exception as e:
                logger.error("Error reading holidays CSV (%s): %s", self.csv_path, e)

        # Inject verified Rang Panchami entries if not already in CSV
        for year, rp_date in RANG_PANCHAMI_DATES.items():
            if (rp_date, 'rang panchami') not in parsed_dates:
                self.holidays.append({
                    'year': year,
                    'date': rp_date,
                    'event': 'Rang Panchami',
                    'type': 'Hindu',
                    'policy': 'RANG_PANCHAMI',
                })

        # Sort chronologically
        self.holidays.sort(key=lambda h: h.get('date', ''))
        logger.info("FestivalPolicyEngine initialized with %d total holiday records", len(self.holidays))

    @staticmethod
    def _parse_csv_date(date_str: str, year_str: str) -> Optional[str]:
        if not date_str:
            return None
        # Try YYYY-MM-DD
        if len(date_str) == 10 and date_str[4] == '-' and date_str[7] == '-':
            return date_str
        # Try "Month DD, YYYY, Day" or "Month DD, YYYY"
        parts = [p.strip() for p in date_str.split(',') if p.strip()]
        if len(parts) >= 2:
            try:
                date_part = f"{parts[0]}, {parts[1]}"
                dt = datetime.strptime(date_part, "%B %d, %Y")
                return dt.strftime("%Y-%m-%d")
            except ValueError:
                pass
        return None

    # ── Time & Timezone Helper ────────────────────────────────

    def get_current_ist_datetime(self, override_now: Optional[datetime] = None) -> datetime:
        """Return the current datetime in Asia/Kolkata (IST), respecting simulation mode."""
        if override_now:
            if override_now.tzinfo is None:
                return override_now.replace(tzinfo=IST)
            return override_now.astimezone(IST)

        if self.simulated_datetime:
            if self.simulated_datetime.tzinfo is None:
                return self.simulated_datetime.replace(tzinfo=IST)
            return self.simulated_datetime.astimezone(IST)

        return datetime.now(IST)

    # ── Festival Lookups ──────────────────────────────────────

    def get_festival_for_date(self, target_date_str: str) -> Optional[Dict[str, Any]]:
        """Return the holiday record matching YYYY-MM-DD, prioritizing special policies if multiple events occur."""
        matches = [h for h in self.holidays if h.get('date') == target_date_str]
        if not matches:
            return None
        for m in matches:
            if m.get('policy') == 'RANG_PANCHAMI' or 'rang panchami' in m.get('event', '').lower():
                return m
        return matches[0]

    def get_upcoming_festivals(self, days: int = 60, from_date: Optional[str] = None) -> List[Dict[str, Any]]:
        """Return upcoming festivals within the given lookahead window."""
        now_dt = self.get_current_ist_datetime()
        start_date = from_date or now_dt.strftime('%Y-%m-%d')
        end_date = (now_dt + timedelta(days=days)).strftime('%Y-%m-%d')

        upcoming = [
            h for h in self.holidays
            if start_date <= h.get('date', '') <= end_date
        ]
        return sorted(upcoming, key=lambda x: x.get('date', ''))

    # ── Policy Evaluation ─────────────────────────────────────

    def evaluate_policy(self, now: Optional[datetime] = None) -> Dict[str, Any]:
        """
        Evaluate festival restriction status.

        Rules:
          - If mode is disabled -> Policy is NORMAL, unblocked.
          - If selected festival or today's festival has policy RANG_PANCHAMI:
              - Before 19:00 IST -> Automatic start BLOCKED.
              - At/after 19:00 IST -> Restriction RELEASED, normal auto allowed.
          - Other festivals -> Policy is NORMAL.
        """
        now_ist = self.get_current_ist_datetime(now)
        today_str = now_ist.strftime('%Y-%m-%d')

        # Determine active festival event
        active_event = self.selected_festival or self.get_festival_for_date(today_str)
        festival_name = active_event.get('event') if active_event else None
        festival_date = active_event.get('date') if active_event else today_str
        policy = active_event.get('policy', 'NORMAL') if active_event else 'NORMAL'

        if not self.mode_enabled:
            return {
                'mode_enabled': False,
                'state': 'DISABLED',
                'policy': 'NORMAL',
                'festival_name': festival_name,
                'festival_date': festival_date,
                'is_rang_panchami': False,
                'restriction_active': False,
                'automatic_start_blocked': False,
                'release_time': None,
                'release_time_display': '07:00 PM IST',
                'current_time_ist': now_ist.strftime('%Y-%m-%d %H:%M:%S IST'),
                'remaining_minutes': 0,
                'reason': 'Festival policy mode is turned OFF by operator',
                'is_simulated': self.simulated_datetime is not None,
            }

        is_rang_panchami = (policy == 'RANG_PANCHAMI') or (festival_name and 'rang panchami' in festival_name.lower())

        if is_rang_panchami:
            release_time = time(19, 0, 0)  # 19:00:00 IST
            cur_time = now_ist.time()

            if cur_time < release_time:
                # Before 7:00 PM IST -> BLOCKED
                release_dt = datetime.combine(now_ist.date(), release_time, tzinfo=IST)
                diff_s = (release_dt - now_ist).total_seconds()
                rem_min = max(0, int(diff_s // 60))

                return {
                    'mode_enabled': True,
                    'state': 'RESTRICTION_ACTIVE',
                    'policy': 'RANG_PANCHAMI',
                    'festival_name': festival_name or 'Rang Panchami',
                    'festival_date': festival_date,
                    'is_rang_panchami': True,
                    'restriction_active': True,
                    'automatic_start_blocked': True,
                    'release_time': '19:00:00',
                    'release_time_display': '07:00 PM IST',
                    'current_time_ist': now_ist.strftime('%Y-%m-%d %H:%M:%S IST'),
                    'remaining_minutes': rem_min,
                    'reason': f"Rang Panchami special policy — automatic pump starts blocked until 07:00 PM IST ({rem_min}m remaining)",
                    'is_simulated': self.simulated_datetime is not None,
                }
            else:
                # 7:00 PM IST or later -> RELEASED
                return {
                    'mode_enabled': True,
                    'state': 'RESTRICTION_RELEASED',
                    'policy': 'RANG_PANCHAMI',
                    'festival_name': festival_name or 'Rang Panchami',
                    'festival_date': festival_date,
                    'is_rang_panchami': True,
                    'restriction_active': False,
                    'automatic_start_blocked': False,
                    'release_time': '19:00:00',
                    'release_time_display': '07:00 PM IST',
                    'current_time_ist': now_ist.strftime('%Y-%m-%d %H:%M:%S IST'),
                    'remaining_minutes': 0,
                    'reason': 'Rang Panchami 07:00 PM IST time reached — restriction released, normal automation allowed',
                    'is_simulated': self.simulated_datetime is not None,
                }

        # Normal Festival or Regular Day
        return {
            'mode_enabled': True,
            'state': 'NORMAL',
            'policy': 'NORMAL',
            'festival_name': festival_name,
            'festival_date': festival_date,
            'is_rang_panchami': False,
            'restriction_active': False,
            'automatic_start_blocked': False,
            'release_time': None,
            'release_time_display': 'N/A',
            'current_time_ist': now_ist.strftime('%Y-%m-%d %H:%M:%S IST'),
            'remaining_minutes': 0,
            'reason': f"Standard operation ({festival_name if festival_name else 'Regular Day'})",
            'is_simulated': self.simulated_datetime is not None,
        }

    # ── State Mutations & API Helpers ─────────────────────────

    def set_mode(self, enabled: bool) -> Dict[str, Any]:
        """Turn Festival Mode ON or OFF."""
        self.mode_enabled = bool(enabled)
        self._save_state()
        logger.info("Festival Mode set to %s", "ON" if self.mode_enabled else "OFF")
        return self.evaluate_policy()

    def select_festival(self, event_name: str, event_date: Optional[str] = None) -> Tuple[bool, Optional[str], Dict[str, Any]]:
        """Explicitly select an active festival for testing or operational overrides."""
        if not event_name:
            return False, "Festival name required", self.evaluate_policy()

        # Find matching holiday or create entry
        policy = "RANG_PANCHAMI" if "rang panchami" in event_name.lower() else "NORMAL"
        target_date = event_date or datetime.now(IST).strftime("%Y-%m-%d")

        self.selected_festival = {
            'event': event_name.strip(),
            'date': target_date,
            'type': 'Hindu' if policy == 'RANG_PANCHAMI' else 'General',
            'policy': policy,
        }
        self.mode_enabled = True
        self._save_state()
        logger.info("Selected festival override: %s (%s)", event_name, target_date)
        return True, None, self.evaluate_policy()

    def reset_festival(self) -> Dict[str, Any]:
        """Clear manual festival selection and simulation overrides."""
        self.selected_festival = None
        self.simulated_datetime = None
        self._save_state()
        logger.info("Festival state reset to live defaults")
        return self.evaluate_policy()

    def simulate_datetime(self, date_str: str, time_str: str) -> Tuple[bool, Optional[str], Dict[str, Any]]:
        """Simulate a specific IST date and time for QA verification."""
        try:
            full_str = f"{date_str.strip()} {time_str.strip()}"
            sim_dt = datetime.strptime(full_str, "%Y-%m-%d %H:%M")
            self.simulated_datetime = sim_dt.replace(tzinfo=IST)
            self._save_state()
            logger.info("Simulated IST datetime set to: %s", self.simulated_datetime)
            return True, None, self.evaluate_policy()
        except ValueError as e:
            return False, f"Invalid date/time format (expected YYYY-MM-DD and HH:MM): {e}", self.evaluate_policy()
