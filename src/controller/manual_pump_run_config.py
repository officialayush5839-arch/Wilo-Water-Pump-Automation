#!/usr/bin/env python3
"""
Edit PULSE_SECONDS and run the pump once for that duration.
"""

from __future__ import annotations

import json
import time

from manual_pump_control import set_pump


PULSE_SECONDS = 15.0


def main():
    started = set_pump(True)
    try:
        time.sleep(PULSE_SECONDS)
    finally:
        ended = set_pump(False)

    print(
        json.dumps(
            {
                'started': started,
                'ended': ended,
                'pulse_seconds': PULSE_SECONDS,
            },
            indent=2,
        )
    )


if __name__ == '__main__':
    main()
