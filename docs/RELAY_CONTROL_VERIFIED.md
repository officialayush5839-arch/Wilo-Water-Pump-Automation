# Relay Control - Verified Field Behavior

Date verified: 2026-06-08

This note records what actually worked on the installed Raspberry Pi relay setup.
It intentionally overrides the older assumptions in the code and wiring docs.

## Summary

The relay module behaves like an active-low input:

- ON: drive the relay input LOW.
- OFF: release the relay input as an input with pull-up.

Driving a GPIO HIGH as an output did not reliably turn the relay off in this setup.
Releasing the pin to input mode with an internal pull-up did turn it off.

This matches common Raspberry Pi relay-module behavior: many 5V optocoupled relay
modules are active-low, and some are unreliable when driven directly by a 3.3V Pi
output. In those cases, the relay input may need to be released or externally
pulled up to switch off cleanly.

## Verified Commands

Run these on the Raspberry Pi.

### Turn Relay ON

```bash
python3 - <<'PY'
import RPi.GPIO as GPIO

pins = [17, 24, 27]

GPIO.setwarnings(False)
GPIO.setmode(GPIO.BCM)

for pin in pins:
    GPIO.setup(pin, GPIO.OUT, initial=GPIO.LOW)
    GPIO.output(pin, GPIO.LOW)

print({"relay_on_active_low_pins": pins})
PY
```

Verified result:

```text
GPIO17 = output low
GPIO24 = output low
GPIO27 = output low
```

### Turn Relay OFF

```bash
python3 - <<'PY'
import RPi.GPIO as GPIO

pins = [17, 24, 27]

GPIO.setwarnings(False)
GPIO.setmode(GPIO.BCM)

for pin in pins:
    GPIO.setup(pin, GPIO.IN, pull_up_down=GPIO.PUD_UP)

print({"relay_off_input_pullup_pins": pins})
PY
```

Verified result:

```text
GPIO17 = input high
GPIO27 = input high
GPIO24 = input low
```

The relay turned off with this release-to-input-pullup approach.

## Important Observation: GPIO24

GPIO24 stayed LOW even when configured as input with pull-up.

That means something external is pulling GPIO24 down, or the attached module is
holding the line low. If the relay input is connected to GPIO24, an active-low
relay will tend to stay energized unless the software releases the pin in a way
that lets the module's input circuit settle.

GPIO24 is also documented elsewhere as the LoRa DIO0 pin. Do not assume GPIO24 is
free for relay control unless the wiring has been physically checked.

## Why The Backend Was Wrong

The backend and scripts assumed a clean software model:

```text
active-low relay:
  LOW  = ON
  HIGH = OFF
```

That is electrically true for many relay boards, but this installed setup did not
turn off reliably when the Pi drove the GPIO HIGH as an output.

The working OFF behavior was:

```text
set GPIO to input mode with pull-up
```

So future relay code should not simply write `GPIO.HIGH` and assume the relay is
off. It should use the verified release-to-input-pullup OFF path, or the hardware
should be rewired with a proper transistor/level shifter/pull-up so output HIGH
is a reliable OFF state.

## Recommended Code Model

For this installation:

```python
def relay_on(pin: int) -> None:
    GPIO.setup(pin, GPIO.OUT, initial=GPIO.LOW)
    GPIO.output(pin, GPIO.LOW)


def relay_off(pin: int) -> None:
    GPIO.setup(pin, GPIO.IN, pull_up_down=GPIO.PUD_UP)
```

Do not use `GPIO.cleanup()` as the main control method. It is too broad and can
reset unrelated pins such as LoRa, I2C, buttons, or LEDs.

## Hardware Fix To Make This Cleaner

The robust fix is hardware-side:

- Use a relay module explicitly compatible with 3.3V Raspberry Pi GPIO.
- Or use a transistor/MOSFET/ULN2003 driver between Pi GPIO and relay input.
- Add the correct pull-up/pull-down resistor for the relay input circuit.
- Keep relay control on one known pin. Prefer GPIO17 if following the existing
  project config.
- Avoid GPIO24 if LoRa DIO0 is connected there.

Once hardware is fixed, the software can go back to a simpler explicit
`LOW = ON`, `HIGH = OFF` model.

