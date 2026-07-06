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

## 📝 License

This project is licensed under the MIT License - see the LICENSE file for details.

## 🤝 Contributing

1. Fork the repository
2. Create a feature branch
3. Make your changes
4. Add tests for new functionality
5. Submit a pull request

## 📞 Support

For support and questions:

- Create an issue in the repository
- Check the documentation in `docs/`
- Review the troubleshooting section

## 🔄 Version History

### v1.0.0

- Initial release
- Core pump automation functionality
- Professional terminal dashboard
- Historical pattern analysis
- Simulation capabilities
- Comprehensive documentation
