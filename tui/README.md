# Wilo Pump Ink TUI

Terminal control panel for the Raspberry Pi pump controller.

## What it does

- Connects to the Pi over SSH
- Polls the controller runtime status file
- Sends manual override commands into the running controller loop
- Does not fight GPIO directly from a separate process

## Why this design

The Pi controller already owns the relay logic. A separate SSH script that toggles GPIO directly would race against `pump_controller.py`. This TUI writes manual override commands that the live controller consumes on its next loop.

## Run

```bash
cd tui
npm install
npm run dev
```

Optional environment variables:

```bash
WILO_PI_HOST=wilopi.local
WILO_PI_USER=wilopi
WILO_PI_PORT=22
WILO_PI_PASSWORD=...
```

## Pi-side dependency

The Pi needs the updated controller files from this repo:

- `src/controller/runtime_channel.py`
- `src/controller/remote_bridge.py`
- updated `src/controller/pump_controller.py`
- updated `src/controller/tank_config.py`
