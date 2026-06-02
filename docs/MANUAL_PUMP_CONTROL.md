# Manual Pump Control Status

As of 2026-05-05, direct manual pump control from the Raspberry Pi is working through:

- `src/controller/manual_pump_control.py`
- `src/controller/manual_pump_on.sh`
- `src/controller/manual_pump_off.sh`
- `src/controller/manual_pump_status.sh`

Current known-good behavior:

- relay pin: `GPIO17`
- relay logic: `RELAY_ACTIVE_LOW = False`
- manual `on` drives GPIO `HIGH`
- manual `off` drives GPIO `LOW`

Validated from the Pi:

- `status` reports relay state and GPIO level
- `on` reports `pump_relay_on=true` with `gpio_level=1`
- `off` reports `pump_relay_on=false` with `gpio_level=0`
- timed pulse works, including a verified `6.7s` pulse on 2026-05-05

Important limitation:

- if the relay board or load still behaves incorrectly while these scripts report correct GPIO state, the remaining issue is hardware-side:
  - relay board logic/input stage
  - `COM/NO/NC` load wiring
  - wrong relay channel/input wire

Useful commands on the Pi:

```bash
cd ~/Desktop/Wilo-Water-Pump-Automation/src/controller
./manual_pump_on.sh
./manual_pump_off.sh
./manual_pump_status.sh
python3 manual_pump_control.py pulse --seconds 10
```
