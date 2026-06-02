"""
GPIO Relay Control for Wilo Pump
=================================
Handles relay switching with safety interlocks and manual override buttons.
"""

import time
import logging

logger = logging.getLogger('wilo.relay')

# Lazy import — RPi.GPIO only available on real Pi
_GPIO = None

def _gpio():
    global _GPIO
    if _GPIO is None:
        import RPi.GPIO as GPIO
        _GPIO = GPIO
    return _GPIO


class RelayController:
    """Controls pump relay and reads manual-override buttons."""

    def __init__(self, pump_pin, valve_pin, active_low,
                 btn_on_pin, btn_off_pin, led_pin, debounce_ms=200):
        self.pump_pin   = pump_pin
        self.valve_pin  = valve_pin
        self.active_low = active_low
        self.btn_on     = btn_on_pin
        self.btn_off    = btn_off_pin
        self.led_pin    = led_pin
        self.debounce_s = debounce_ms / 1000.0
        self.pump_on    = False
        self._ready     = False

    # ── Init / cleanup ────────────────────────────────────────

    def initialize(self):
        """Setup GPIO pins. Call AFTER GPIO.setmode(BCM) in main."""
        gpio = _gpio()
        gpio.setup(self.pump_pin,  gpio.OUT)
        gpio.setup(self.valve_pin, gpio.OUT)
        gpio.setup(self.led_pin,   gpio.OUT)
        gpio.setup(self.btn_on,    gpio.IN, pull_up_down=gpio.PUD_UP)
        gpio.setup(self.btn_off,   gpio.IN, pull_up_down=gpio.PUD_UP)

        # Start with everything OFF
        self._relay(self.pump_pin, False)
        self._relay(self.valve_pin, False)
        gpio.output(self.led_pin, gpio.LOW)
        self._ready = True
        logger.info("Relay controller initialised  "
                     f"pump=GPIO{self.pump_pin}  valve=GPIO{self.valve_pin}  "
                     f"active_low={self.active_low}")

    def cleanup(self):
        """Ensure pump OFF before shutdown."""
        if self._ready:
            self.pump_stop()
            _gpio().output(self.led_pin, _gpio().LOW)
        self._ready = False

    # ── Relay helpers ─────────────────────────────────────────

    def _relay(self, pin, on: bool):
        gpio = _gpio()
        if self.active_low:
            gpio.output(pin, gpio.LOW if on else gpio.HIGH)
        else:
            gpio.output(pin, gpio.HIGH if on else gpio.LOW)

    # ── Pump control ─────────────────────────────────────────

    def pump_start(self) -> bool:
        if not self._ready:
            logger.error("Relay not initialised!")
            return False
        self._relay(self.pump_pin, True)
        _gpio().output(self.led_pin, _gpio().HIGH)
        self.pump_on = True
        logger.info("⚡ PUMP → ON")
        return True

    def pump_stop(self) -> bool:
        if not self._ready:
            logger.error("Relay not initialised!")
            return False
        self._relay(self.pump_pin, False)
        _gpio().output(self.led_pin, _gpio().LOW)
        self.pump_on = False
        logger.info("⏹  PUMP → OFF")
        return True

    def emergency_stop(self):
        """All relays OFF immediately — no checks."""
        gpio = _gpio()
        off = gpio.HIGH if self.active_low else gpio.LOW
        gpio.output(self.pump_pin, off)
        gpio.output(self.valve_pin, off)
        gpio.output(self.led_pin, gpio.LOW)
        self.pump_on = False
        logger.warning("🚨 EMERGENCY STOP — all relays OFF")

    # ── Manual override buttons ──────────────────────────────

    def read_override_buttons(self):
        """
        Returns 'ON', 'OFF', or None.
        Buttons are normally-open with internal pull-up → pressed = LOW.
        """
        gpio = _gpio()
        if gpio.input(self.btn_on) == gpio.LOW:
            time.sleep(self.debounce_s)
            if gpio.input(self.btn_on) == gpio.LOW:
                return 'ON'
        if gpio.input(self.btn_off) == gpio.LOW:
            time.sleep(self.debounce_s)
            if gpio.input(self.btn_off) == gpio.LOW:
                return 'OFF'
        return None
