# Wilo Water Pump Automation System

A professional water pump automation system with predictive control, historical pattern analysis, and intelligent scheduling capabilities.

## 🏗️ Project Structure

```
Wilo Water Pump Automation/
├── config/                     # Configuration files
│   └── settings.py             # Main configuration settings
├── data/                       # Data storage
│   ├── raw/                    # Raw data files (CSV, logs)
│   └── processed/              # Processed data outputs
├── docs/                       # Documentation
│   ├── api/                    # API documentation
│   └── user/                   # User guides
├── logs/                       # Application logs
│   ├── pump/                   # Pump operation logs
│   └── simulation/             # Simulation logs
├── models/                     # Machine learning models
│   └── trained/                # Trained model files (.pkl)
├── scripts/                    # Utility scripts
│   ├── deploy/                 # Deployment scripts
│   └── maintenance/            # Maintenance utilities
├── src/                        # Source code
│   ├── core/                   # Core application logic
│   │   └── main.py             # Main application file
│   ├── dashboard/              # Terminal UI components
│   │   └── terminal_ui.py      # Professional dashboard styling
│   ├── models/                 # ML model handlers
│   │   └── prediction.py       # Prediction algorithms
│   ├── simulation/             # Simulation modules
│   │   ├── run_simulation.py   # Basic simulation
│   │   └── simulation_30days.py # Extended simulation
│   └── utils/                  # Utility modules
│       ├── data_handler.py     # Data processing utilities
│       └── sensors.py          # Sensor data handling
├── tests/                      # Test files
│   ├── unit/                   # Unit tests
│   └── integration/            # Integration tests
├── .gitignore                  # Git ignore rules
├── requirements.txt            # Python dependencies
└── run.py                      # Main entry point
```

## 🚀 Features

### Core Functionality

- **Predictive Pump Control**: AI-powered prediction of optimal pump operation times
- **Historical Pattern Analysis**: 2-year historical data analysis for pattern recognition
- **Intelligent Scheduling**: Smart scheduling based on usage patterns and environmental factors
- **Professional Dashboard**: Beautiful terminal-based monitoring interface

### Advanced Capabilities

- **Fallback Mechanisms**: Robust fallback systems for sensor failures
- **Environmental Adaptation**: Adaptive algorithms based on temperature, humidity, and seasonal patterns
- **Real-time Monitoring**: Continuous sensor data monitoring and analysis
- **Comprehensive Logging**: Detailed operation logging for trend analysis

### LoRa Test Folder

For direct ESP32-to-ESP32 LoRa validation, use:

- [`firmware/lora_testing/README.md`](firmware/lora_testing/README.md)

### ESP32 Sender -> Raspberry Pi CSV Logger

For the production path where the ESP32 sender transmits pressure packets and the
Raspberry Pi receives them and appends them to a CSV, use:

- [`src/controller/lora_csv_receiver.py`](src/controller/lora_csv_receiver.py)

Run on the Pi:

```bash
python3 src/controller/lora_csv_receiver.py
```

To auto-start on boot, install:

```bash
sudo cp src/controller/wilo-lora-csv-receiver.service /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable wilo-lora-csv-receiver
sudo systemctl start wilo-lora-csv-receiver
```

The CSV is created automatically at:

```text
logs/lora/esp32_pressure_packets.csv
```

### Simulation Features

- **Fast-Forward Simulation**: 30-day simulation with 60x speed
- **Basic Simulation**: Real-time simulation for testing
- **Pattern Validation**: Historical pattern validation through simulation

## 📋 Requirements

### System Requirements

- Python 3.8 or higher
- Windows/Linux/macOS
- Minimum 4GB RAM
- 1GB free disk space

### Python Dependencies

```
joblib>=1.3.0
numpy>=1.21.0
pandas>=1.3.0
scikit-learn>=1.0.0
```

## 🔧 Installation

1. **Clone the repository**

   ```bash
   git clone <repository-url>
   cd "Wilo Water Pump Automation"
   ```

2. **Create virtual environment**

   ```bash
   python -m venv env
   source env/bin/activate  # Linux/macOS
   # or
   env\Scripts\activate  # Windows
   ```

3. **Install dependencies**

   ```bash
   pip install -r requirements.txt
   ```

4. **Verify installation**

   ```bash
   python run.py --help
   ```

## 🏃 How to Run

This is a multi-device system. Each component runs on a **specific device** — read the table first, then jump to the section for the device you're setting up.

### System Overview — who runs what

| # | Device | Component | Path | Command | Port |
|---|--------|-----------|------|---------|------|
| 1 | **ESP32** (sender) | Sensor firmware | `firmware/esp32_sender/` | Flash via Arduino IDE | LoRa 433 MHz |
| 2 | **Raspberry Pi** | Pump controller (the brain) | `src/controller/pump_controller.py` | `python3 pump_controller.py` | — (GPIO) |
| 3 | **Raspberry Pi** | Backend API + live dashboard | `src/dashboard/server.py` | `python3 server.py` | `5050` |
| 4 | **Any PC / the Pi** | Frontend web dashboard (React) | `dashboard/` | `bun dev` / `npm run dev` | `8080` |
| 5 | **Any PC** (optional) | Terminal control panel (TUI) | `tui/` | `npm run dev` (over SSH) | — |
| 6 | **Any PC** (optional) | ML simulation / offline app | `run.py` | `python run.py` | — |

**Data flow:** ESP32 → *(LoRa)* → Pi controller → *(status JSON + `/api`)* → Backend `server.py` → *(HTTP :5050)* → Frontend dashboard.

> The **backend** (`server.py`) both serves the built-in HTML dashboard on port `5050` **and** exposes the `/api/*` endpoints that the React **frontend** talks to. The React app (port `8080`) proxies `/api`, `/latest`, `/stream` to `127.0.0.1:5050`.

---

### 1. ESP32 — Sensor Node (sender)

The ESP32 reads the PR12-P210 pressure sensor on the upper tank and broadcasts JSON packets over LoRa.

1. Open `firmware/esp32_sender/esp32_sender.ino` in the **Arduino IDE** (or `arduino-cli`).
2. Install the ESP32 board package and a LoRa (SX127x) library.
3. Select your ESP32 board + port, then **Upload**.
4. Wire per `docs/HARDWARE_GUIDE.md` (sensor on GPIO34, LoRa on the SPI pins defined at the top of the sketch).

Test sketches also live in `firmware/`: `esp32_relay_test/`, `esp32_lora_hello/`, `esp32_receiver/`.

---

### 2. Raspberry Pi — Backend (controller + server)

The Pi is the backend. It needs two processes running: the **controller** (owns the relay/GPIO) and the **dashboard server** (serves the UI + API).

**Install dependencies (on the Pi):**

```bash
cd Wilo-Water-Pump-Automation
python3 -m venv env && source env/bin/activate

# ML + core
pip install -r requirements.txt
# Pi hardware drivers (GPIO, SPI, ADC)
pip install -r src/controller/requirements.txt
# Backend web server
pip install flask pyserial
```

**a) Pump controller** — the decision engine + relay control:

```bash
cd src/controller
python3 pump_controller.py            # LIVE — drives real GPIO/relay
python3 pump_controller.py --dry-run  # no GPIO, safe to test off-Pi
python3 pump_controller.py --verbose  # extra debug logging
```

**b) Backend / dashboard server** — Flask API + Server-Sent-Events feed:

```bash
cd src/dashboard
python3 server.py                 # serves on http://<pi-ip>:5050
python3 server.py --port 5050 --fresh
```

Open `http://<pi-ip>:5050` for the simple built-in dashboard, or point the React frontend (below) at it for the full UI.

**Run on boot (systemd, recommended for production):**

```bash
sudo cp src/controller/wilo-pump.service /etc/systemd/system/
sudo cp src/controller/wilo-lora-csv-receiver.service /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable --now wilo-pump wilo-lora-csv-receiver
# check status / logs
systemctl status wilo-pump
journalctl -u wilo-pump -f
```

> ⚠️ The `.service` files hardcode `User=` and `WorkingDirectory=` (`pi` / `wilopi`). Edit them to match your Pi's username and clone path before installing.

---

### 3. Frontend — React Web Dashboard

The full UI lives in `dashboard/` (Vite + React + shadcn/ui). It can run on the Pi or any PC on the same network as the backend.

```bash
cd dashboard
bun install        # or: npm install
bun dev            # or: npm run dev  → http://localhost:8080
```

- In **dev**, Vite (port `8080`) proxies `/api`, `/stream`, `/latest` to `http://127.0.0.1:5050` — so run it **on the Pi**, or set `VITE_API_BASE_URL` to the Pi's address:

  ```bash
  VITE_API_BASE_URL="http://<pi-ip>:5050" bun dev
  ```

- For a **production build**:

  ```bash
  bun run build      # outputs to dashboard/dist
  bun run preview    # or serve dist/ with any static host
  ```

---

### 4. Optional — Terminal UI (remote control over SSH)

Controls the Pi's live controller from your laptop without racing GPIO (it writes override commands the controller consumes):

```bash
cd tui
npm install
WILO_PI_HOST=wilopi.local WILO_PI_USER=wilopi npm run dev
```

---

### 5. Optional — ML Simulation / Offline App

Runs anywhere (no hardware needed) — the predictive dashboard, simulations, and tests:

```bash
python run.py                              # predictive terminal app
python src/simulation/run_simulation.py    # basic simulation
python src/simulation/simulation_30days.py # 30-day fast-forward simulation
python -m pytest tests/unit/               # tests
```

### Configuration

Two separate config files — don't mix them up:

- `config/settings.py` — the **ML / simulation app** (model paths, fallbacks, dashboard widths).
- `src/controller/tank_config.py` — the **Pi hardware** (GPIO pins, tank thresholds, LoRa/sensor calibration, safety guards).

## 📊 Data Structure

### Historical Data Format

- **Date**: YYYY-MM-DD format
- **Hour**: Hour of operation (0-23)
- **Duration**: Operation duration in minutes
- **TopTankLevel**: Water level percentage (0-100)
- **Voltage**: System voltage (V)
- **Current**: System current (A)
- **Temperature**: Ambient temperature (°C)
- **Humidity**: Relative humidity (%)

### Log Data Format

- **date**: Operation date
- **start_hour**: Predicted start hour
- **duration**: Predicted duration
- **sensor_data**: Real-time sensor readings

## 🎛️ Dashboard Interface

The professional terminal dashboard provides:

### Visual Elements

- **Color-coded status indicators**
- **Real-time sensor data display**
- **Historical analysis summaries**
- **Prediction results**
- **System alerts and notifications**

### Information Panels

- **System Header**: Application title and version
- **Configuration Panel**: Current settings and file paths
- **Historical Analysis**: 2-year pattern analysis
- **Real-time Monitoring**: Live sensor data and predictions
- **Status Updates**: Operation logs and alerts

## 🔮 Prediction Algorithms

### Machine Learning Models

- **Start Hour Prediction**: Predicts optimal pump start time
- **Duration Prediction**: Predicts optimal operation duration
- **Pattern Recognition**: Identifies historical usage patterns

### Fallback Systems

1. **Historical Pattern Matching**: Uses similar historical conditions
2. **Statistical Averages**: Falls back to statistical patterns
3. **Default Parameters**: Final fallback with safe defaults

## 🧪 Testing

### Unit Tests

```bash
# Run all unit tests
python -m pytest tests/unit/

# Run specific test
python tests/unit/test_analysis.py
```

### Integration Tests

```bash
# Run integration tests
python -m pytest tests/integration/
```

## 📈 Monitoring & Logging

### Log Files

- **Pump Operations**: `logs/pump/pump_usage_log.csv`
- **System Events**: Console output with timestamps
- **Simulation Results**: `data/processed/simulation_results.csv`

### Dashboard Tags

- `[INFO]`: General information
- `[SUCCESS]`: Successful operations
- `[WARNING]`: Warning messages
- `[ERROR]`: Error conditions
- `[CONFIG]`: Configuration information
- `[CONTROL]`: Pump control operations
- `[SENSORS]`: Sensor data
- `[PREDICT]`: Prediction results

## 🔧 Customization

### Adding New Sensors

1. Modify `src/utils/sensors.py`
2. Update data structure in `src/utils/data_handler.py`
3. Adjust prediction models if needed

### Custom Prediction Algorithms

1. Create new module in `src/models/`
2. Implement prediction interface
3. Update main application to use new algorithm

### Dashboard Customization

1. Modify `src/dashboard/terminal_ui.py`
2. Adjust colors, layouts, and formatting
3. Add new display components

## 🚨 Troubleshooting

### Common Issues

**Model Loading Errors**

- Ensure model files exist in `models/trained/`
- Check file permissions
- Verify Python dependencies

**Data Loading Issues**

- Verify CSV file format
- Check file paths in configuration
- Ensure sufficient disk space

**Permission Errors**

- Run with appropriate permissions
- Check directory write access
- Verify log directory exists

### Debug Mode

Set `LOG_LEVEL = 'DEBUG'` in `config/settings.py` for detailed logging.

## 🔌 Connecting the Laptop to the Raspberry Pi over SSH (Mobile Hotspot)

The Pi runs headless — you control it from your laptop over SSH. In the field there's usually no router, so the simplest setup is a **phone hotspot** that both the Pi and the laptop join. Both devices must be on the **same hotspot**.

```
   📱 Phone Hotspot  (e.g. "Sarthak-iPhone")
        │
   ┌────┴─────┐
   │          │
 💻 Laptop   🍓 Raspberry Pi
              (headless — SSH target)
```

### 1. Enable SSH on the Raspberry Pi

- **Raspberry Pi Imager**: enable SSH (and set hostname/user/password) in the advanced options before flashing, **or**
- On a running Pi: `sudo raspi-config` → *Interface Options* → *SSH* → *Enable*, **or**
- Headless: drop an empty file named `ssh` into the boot partition of the SD card.

Default project user/hostname (from the systemd + TUI config): user `wilopi`, hostname `wilopi.local`.

### 2. Make the Pi auto-join the phone hotspot

Since the Pi is headless, it must already know the hotspot's Wi-Fi so it connects on boot. Set a **fixed SSID + password** on the phone hotspot, then tell the Pi about it:

- **Easiest (before flashing):** in Raspberry Pi Imager advanced options, set the Wi-Fi SSID/password to your **hotspot's** name and password.
- **Headless SD-card edit:** create `wpa_supplicant.conf` in the SD card's boot partition:

  ```text
  country=IN
  ctrl_interface=DIR=/var/run/wpa_supplicant GROUP=netdev
  update_config=1

  network={
      ssid="YOUR_HOTSPOT_NAME"
      psk="YOUR_HOTSPOT_PASSWORD"
  }
  ```

- **On a Pi you can already reach:** `sudo raspi-config` → *System Options* → *Wireless LAN*, or `sudo nmcli dev wifi connect "YOUR_HOTSPOT_NAME" password "YOUR_HOTSPOT_PASSWORD"`.

> 💡 Turn the phone hotspot **on first**, then power the Pi — it joins automatically. Keep the SSID/password the same every time so the Pi always reconnects.

### 3. Connect the laptop to the **same** hotspot, then find the Pi's IP

Join the laptop to the same phone hotspot. Phone hotspots often **don't** resolve `wilopi.local` (no mDNS), so find the Pi's IP address:

- **On the phone:** open *Hotspot / Connected Devices* — it lists each connected device's name and IP (the Pi shows up as `wilopi` or `raspberrypi`).
- **From the laptop:** scan the hotspot subnet (commonly `172.20.10.x` on iPhone, `192.168.43.x` on Android):

  ```bash
  # try the hostname first (sometimes works)
  ping wilopi.local

  # otherwise scan the subnet (install nmap, or use arp)
  nmap -sn 172.20.10.0/24
  arp -a | grep -iE 'b8:27:eb|dc:a6:32|e4:5f:01'   # Raspberry Pi MAC prefixes
  ```

### 4. SSH in from the laptop

```bash
# macOS / Linux / Windows (PowerShell or Terminal)
# use the IP you found on the hotspot in step 3
ssh wilopi@172.20.10.5
# …or by hostname if mDNS works on your hotspot
ssh wilopi@wilopi.local
```

First connection asks to confirm the host fingerprint — type `yes`. Then enter the Pi password.

### 5. Passwordless login (SSH keys — recommended)

Generate a key on the **laptop** (skip if you already have `~/.ssh/id_ed25519.pub`), then copy it to the Pi:

```bash
ssh-keygen -t ed25519            # press Enter through the prompts
ssh-copy-id wilopi@wilopi.local  # copies your public key to the Pi
```

Now `ssh wilopi@wilopi.local` logs in with no password. Add a shortcut in `~/.ssh/config` on the laptop:

```text
Host wilopi
    HostName wilopi.local
    User wilopi
```

…then just `ssh wilopi`.

### 6. Reach the dashboard from the laptop browser

On the same hotspot you can usually just open the Pi's IP directly — start `server.py` on the Pi and browse to `http://172.20.10.5:5050` from the laptop.

If a port isn't reachable, tunnel it over SSH instead:

```bash
# Forward Pi's :5050 to laptop's localhost:5050
ssh -L 5050:localhost:5050 wilopi@172.20.10.5
# Then open http://localhost:5050 in the laptop browser
```

### 7. Run the controller / server over the SSH session

```bash
ssh wilopi@172.20.10.5
cd Wilo-Water-Pump-Automation

# start the pieces (see the "How to Run" section for details)
python3 src/controller/pump_controller.py &
python3 src/dashboard/server.py &

# or manage the systemd services
sudo systemctl status wilo-pump
journalctl -u wilo-pump -f
```

> To control a **running** controller from the laptop without racing GPIO, use the terminal UI in `tui/` (it sends override commands over SSH) — set `WILO_PI_HOST=wilopi.local` and `WILO_PI_USER=wilopi`.

### Troubleshooting SSH

- **Pi never appears on the hotspot** — the hotspot SSID/password changed, or the Pi booted before the hotspot was on. Fix the Wi-Fi in step 2 and power-cycle the Pi with the hotspot already running.
- **`ssh: connect to host … port 22: Connection refused`** — SSH isn't enabled on the Pi (see step 1).
- **`wilopi.local` not found** — phone hotspots usually don't do mDNS; use the raw IP from step 3 instead.
- **`Connection timed out`** — Pi and laptop aren't on the **same** hotspot, or the Pi is off. Some hotspots also enable *client isolation* (AP isolation) which blocks device-to-device traffic — turn it off in the phone's hotspot settings if available.
- **`REMOTE HOST IDENTIFICATION HAS CHANGED`** — the Pi was reimaged or got a new IP; clear the old key with `ssh-keygen -R 172.20.10.5`.
