"""
Runtime status + command file helpers.
"""

from __future__ import annotations

import json
import os
import tempfile
import uuid
from datetime import datetime


def _ensure_parent(path: str) -> None:
    os.makedirs(os.path.dirname(os.path.abspath(path)), exist_ok=True)


def atomic_write_json(path: str, payload: dict) -> None:
    _ensure_parent(path)
    fd, temp_path = tempfile.mkstemp(
        prefix='.tmp-runtime-', suffix='.json', dir=os.path.dirname(os.path.abspath(path))
    )
    try:
        with os.fdopen(fd, 'w', encoding='utf-8') as handle:
            json.dump(payload, handle, indent=2, sort_keys=True)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temp_path, path)
    finally:
        if os.path.exists(temp_path):
            os.unlink(temp_path)


def read_json(path: str) -> dict | None:
    if not os.path.exists(path):
        return None
    with open(path, encoding='utf-8') as handle:
        return json.load(handle)


def remove_file(path: str) -> None:
    try:
        os.remove(path)
    except FileNotFoundError:
        return


def new_command(action: str, source: str = 'unknown', metadata: dict | None = None) -> dict:
    return {
        'command_id': str(uuid.uuid4()),
        'action': action,
        'source': source,
        'metadata': metadata or {},
        'issued_at': datetime.now().isoformat(),
    }
