"""
Municipal Water Cut Management Module
====================================
Handles scheduling, calculation, persistence, and state evaluation for municipal
water cutouts and pre-fill reserve targets.
"""

from __future__ import annotations

import json
import logging
import os
import uuid
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional, Tuple

logger = logging.getLogger('wilo.water_cut')


class WaterCutManager:
    """Manages municipal water cut events and pre-fill logic."""

    def __init__(self, cuts_file_path: str, default_reserve_pct: float = 95.0, default_prefill_hours: float = 4.0):
        self.cuts_file_path = cuts_file_path
        self.default_reserve_pct = float(default_reserve_pct)
        self.default_prefill_hours = float(default_prefill_hours)
        self.cuts: List[Dict[str, Any]] = []
        self.load_cuts()

    # ── Persistence ───────────────────────────────────────────

    def load_cuts(self) -> List[Dict[str, Any]]:
        """Load water-cut events from persistent JSON file."""
        if not os.path.exists(self.cuts_file_path):
            self.cuts = []
            self._save_cuts()
            return self.cuts

        try:
            with open(self.cuts_file_path, 'r', encoding='utf-8') as f:
                data = json.load(f)
                if isinstance(data, list):
                    self.cuts = data
                else:
                    self.cuts = []
            logger.info("Loaded %d water cut event(s) from %s", len(self.cuts), self.cuts_file_path)
        except Exception as e:
            logger.error("Failed to load water cuts from %s: %s", self.cuts_file_path, e)
            self.cuts = []

        return self.cuts

    def _save_cuts(self) -> bool:
        """Atomically persist cuts list to disk."""
        try:
            os.makedirs(os.path.dirname(os.path.abspath(self.cuts_file_path)), exist_ok=True)
            temp_file = f"{self.cuts_file_path}.tmp"
            with open(temp_file, 'w', encoding='utf-8') as f:
                json.dump(self.cuts, f, indent=2, sort_keys=True)
            if os.name == 'nt' and os.path.exists(self.cuts_file_path):
                os.remove(self.cuts_file_path)
            os.replace(temp_file, self.cuts_file_path)
            return True
        except Exception as e:
            logger.error("Failed to save water cuts to %s: %s", self.cuts_file_path, e)
            return False

    # ── Validation ────────────────────────────────────────────

    @staticmethod
    def _parse_iso(ts_str: str) -> Optional[datetime]:
        if not ts_str or not isinstance(ts_str, str):
            return None
        try:
            return datetime.fromisoformat(ts_str)
        except ValueError:
            return None

    def validate_cut_payload(self, payload: Dict[str, Any]) -> Tuple[bool, Optional[str], Optional[Dict[str, Any]]]:
        """Validate an incoming water cut creation/update payload."""
        if not isinstance(payload, dict):
            return False, "Payload must be a JSON object", None

        start_time_str = payload.get('start_time')
        end_time_str = payload.get('end_time')

        start_dt = self._parse_iso(start_time_str)
        if not start_dt:
            return False, "Invalid start_time format (must be ISO-8601 string)", None

        end_dt = self._parse_iso(end_time_str)
        if not end_dt:
            return False, "Invalid end_time format (must be ISO-8601 string)", None

        if end_dt <= start_dt:
            return False, "end_time must be strictly after start_time", None

        try:
            reserve_pct = float(payload.get('target_reserve_pct', self.default_reserve_pct))
            if not (10.0 <= reserve_pct <= 100.0):
                return False, "target_reserve_pct must be between 10 and 100", None
        except (ValueError, TypeError):
            return False, "target_reserve_pct must be a valid number", None

        try:
            prefill_hours = float(payload.get('pre_fill_hours', self.default_prefill_hours))
            if not (0.1 <= prefill_hours <= 72.0):
                return False, "pre_fill_hours must be between 0.1 and 72 hours", None
        except (ValueError, TypeError):
            return False, "pre_fill_hours must be a valid number", None

        reason = str(payload.get('reason', 'Municipal water maintenance')).strip()
        if not reason:
            reason = "Municipal water maintenance"

        cut_id = str(payload.get('id', f"cut-{start_dt.strftime('%Y%m%d-%H%M')}-{uuid.uuid4().hex[:4]}"))

        validated = {
            'id': cut_id,
            'start_time': start_dt.isoformat(),
            'end_time': end_dt.isoformat(),
            'target_reserve_pct': round(reserve_pct, 1),
            'pre_fill_hours': round(prefill_hours, 1),
            'reason': reason,
            'created_at': payload.get('created_at', datetime.now().isoformat()),
        }

        return True, None, validated

    # ── CRUD Operations ───────────────────────────────────────

    def get_all_cuts(self) -> List[Dict[str, Any]]:
        self.load_cuts()
        # Sort chronologically by start_time
        return sorted(self.cuts, key=lambda c: c.get('start_time', ''))

    def add_cut(self, payload: Dict[str, Any]) -> Tuple[bool, Optional[str], Optional[Dict[str, Any]]]:
        valid, err, validated = self.validate_cut_payload(payload)
        if not valid or not validated:
            return False, err, None

        self.load_cuts()
        # Check if ID already exists
        if any(c['id'] == validated['id'] for c in self.cuts):
            validated['id'] = f"{validated['id']}-{uuid.uuid4().hex[:4]}"

        self.cuts.append(validated)
        self._save_cuts()
        logger.info("WATER_CUT_CREATED id=%s start=%s end=%s target=%.1f%%",
                    validated['id'], validated['start_time'], validated['end_time'], validated['target_reserve_pct'])
        return True, None, validated

    def update_cut(self, cut_id: str, payload: Dict[str, Any]) -> Tuple[bool, Optional[str], Optional[Dict[str, Any]]]:
        self.load_cuts()
        for idx, cut in enumerate(self.cuts):
            if cut['id'] == cut_id:
                payload['id'] = cut_id
                payload['created_at'] = cut.get('created_at', datetime.now().isoformat())
                valid, err, validated = self.validate_cut_payload(payload)
                if not valid or not validated:
                    return False, err, None
                self.cuts[idx] = validated
                self._save_cuts()
                logger.info("WATER_CUT_UPDATED id=%s", cut_id)
                return True, None, validated
        return False, f"Water cut with id '{cut_id}' not found", None

    def delete_cut(self, cut_id: str) -> Tuple[bool, Optional[str]]:
        self.load_cuts()
        initial_len = len(self.cuts)
        self.cuts = [c for c in self.cuts if c['id'] != cut_id]
        if len(self.cuts) < initial_len:
            self._save_cuts()
            logger.info("WATER_CUT_DELETED id=%s", cut_id)
            return True, None
        return False, f"Water cut with id '{cut_id}' not found"

    # ── State Evaluation ──────────────────────────────────────

    def get_active_cut(self, now: Optional[datetime] = None) -> Optional[Dict[str, Any]]:
        """Return the currently active water cut event if now is within [start, end]."""
        now = now or datetime.now()
        for cut in self.cuts:
            start_dt = self._parse_iso(cut.get('start_time'))
            end_dt = self._parse_iso(cut.get('end_time'))
            if start_dt and end_dt and start_dt <= now <= end_dt:
                return cut
        return None

    def get_prefill_cut(self, now: Optional[datetime] = None) -> Optional[Dict[str, Any]]:
        """Return the cut currently in its pre-fill window [start - prefill_hours, start]."""
        now = now or datetime.now()
        for cut in self.cuts:
            start_dt = self._parse_iso(cut.get('start_time'))
            end_dt = self._parse_iso(cut.get('end_time'))
            prefill_h = float(cut.get('pre_fill_hours', self.default_prefill_hours))
            if start_dt and end_dt:
                prefill_start = start_dt - timedelta(hours=prefill_h)
                if prefill_start <= now < start_dt:
                    return cut
        return None

    def get_upcoming_cut(self, now: Optional[datetime] = None) -> Optional[Dict[str, Any]]:
        """Return the next future water cut event."""
        now = now or datetime.now()
        future_cuts = []
        for cut in self.cuts:
            start_dt = self._parse_iso(cut.get('start_time'))
            if start_dt and start_dt > now:
                future_cuts.append((start_dt, cut))
        if future_cuts:
            future_cuts.sort(key=lambda pair: pair[0])
            return future_cuts[0][1]
        return None

    def get_status(self, now: Optional[datetime] = None) -> Dict[str, Any]:
        """Compute comprehensive water cut status for API and runtime controller."""
        now = now or datetime.now()
        self.load_cuts()

        active_cut = self.get_active_cut(now)
        prefill_cut = self.get_prefill_cut(now)
        upcoming_cut = self.get_upcoming_cut(now)

        if active_cut:
            state = "WATER_CUT_ACTIVE"
            target_reserve_pct = float(active_cut.get('target_reserve_pct', self.default_reserve_pct))
            current_event = active_cut
            end_dt = self._parse_iso(active_cut['end_time'])
            remaining_s = (end_dt - now).total_seconds() if end_dt else 0
            prefill_remaining_min = None
            cut_remaining_min = max(0, round(remaining_s / 60.0, 1))
        elif prefill_cut:
            state = "PREFILL"
            target_reserve_pct = float(prefill_cut.get('target_reserve_pct', self.default_reserve_pct))
            current_event = prefill_cut
            start_dt = self._parse_iso(prefill_cut['start_time'])
            remaining_s = (start_dt - now).total_seconds() if start_dt else 0
            prefill_remaining_min = max(0, round(remaining_s / 60.0, 1))
            cut_remaining_min = None
        else:
            state = "NORMAL"
            target_reserve_pct = None
            current_event = upcoming_cut
            prefill_remaining_min = None
            cut_remaining_min = None

        return {
            'state': state,
            'is_cut_active': active_cut is not None,
            'is_prefill_active': prefill_cut is not None,
            'active_cut': active_cut,
            'prefill_cut': prefill_cut,
            'upcoming_cut': upcoming_cut,
            'current_event': current_event,
            'target_reserve_pct': target_reserve_pct,
            'prefill_remaining_min': prefill_remaining_min,
            'cut_remaining_min': cut_remaining_min,
            'cuts_count': len(self.cuts),
            'timestamp': now.isoformat(),
        }
