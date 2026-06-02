#!/usr/bin/env python3
"""
Send relay test commands to an ESP32 over USB serial.

This is meant to pair with firmware/esp32_relay_test/esp32_relay_test.ino.
Commands:
  on
  off
  status
  pulse --seconds 3

No third-party Python packages are required.
"""

from __future__ import annotations

import argparse
import glob
import os
import select
import sys
import termios
import time


def _auto_port() -> str | None:
    candidates = []
    candidates.extend(sorted(glob.glob("/dev/cu.usbserial*")))
    candidates.extend(sorted(glob.glob("/dev/cu.usbmodem*")))
    candidates.extend(sorted(glob.glob("/dev/tty.usbserial*")))
    candidates.extend(sorted(glob.glob("/dev/tty.usbmodem*")))
    return candidates[0] if candidates else None


def _set_baud(attrs, baud: int):
    speed = {
        9600: termios.B9600,
        19200: termios.B19200,
        38400: termios.B38400,
        57600: termios.B57600,
        115200: termios.B115200,
        230400: termios.B230400 if hasattr(termios, "B230400") else termios.B115200,
    }.get(baud, termios.B115200)
    attrs[4] = speed
    attrs[5] = speed


class SerialPort:
    def __init__(self, port: str, baud: int):
        self.port = port
        self.baud = baud
        self.fd = os.open(port, os.O_RDWR | os.O_NOCTTY | os.O_NONBLOCK)
        attrs = termios.tcgetattr(self.fd)
        attrs[0] = 0
        attrs[1] = 0
        attrs[2] |= termios.CREAD | termios.CLOCAL
        attrs[3] = 0
        _set_baud(attrs, baud)
        termios.tcsetattr(self.fd, termios.TCSANOW, attrs)

    def write_line(self, text: str) -> None:
        if not text.endswith("\n"):
            text += "\n"
        os.write(self.fd, text.encode("utf-8"))

    def read_for(self, seconds: float) -> str:
        deadline = time.time() + seconds
        chunks: list[bytes] = []
        while time.time() < deadline:
            r, _, _ = select.select([self.fd], [], [], 0.1)
            if self.fd not in r:
                continue
            try:
                data = os.read(self.fd, 4096)
            except BlockingIOError:
                continue
            if data:
                chunks.append(data)
        return b"".join(chunks).decode("utf-8", errors="replace")

    def close(self) -> None:
        try:
            os.close(self.fd)
        except OSError:
            pass


def main() -> int:
    parser = argparse.ArgumentParser(description="ESP32 relay serial test CLI")
    parser.add_argument("command", choices=["on", "off", "status", "pulse"])
    parser.add_argument("--seconds", type=float, default=3.0)
    parser.add_argument("--port", help="Serial port (auto-detect if omitted)")
    parser.add_argument("--baud", type=int, default=115200)
    args = parser.parse_args()

    port = args.port or _auto_port()
    if not port:
        print("ERROR: no ESP32 serial port found", file=sys.stderr)
        return 1

    ser = SerialPort(port, args.baud)
    try:
        # Wake the board and print any boot banner.
        ser.write_line("")
        boot = ser.read_for(1.0)
        if boot.strip():
            print(boot, end="" if boot.endswith("\n") else "\n")

        if args.command == "pulse":
            ser.write_line("on")
            print(">>> on")
            out = ser.read_for(0.5)
            if out.strip():
                print(out, end="" if out.endswith("\n") else "\n")
            time.sleep(args.seconds)
            ser.write_line("off")
            print(">>> off")
            out = ser.read_for(0.8)
            if out.strip():
                print(out, end="" if out.endswith("\n") else "\n")
            return 0

        ser.write_line(args.command)
        print(f">>> {args.command}")
        out = ser.read_for(1.2)
        if out.strip():
            print(out, end="" if out.endswith("\n") else "\n")
        return 0
    finally:
        ser.close()


if __name__ == "__main__":
    raise SystemExit(main())
