#!/usr/bin/env python3
"""
Pressure Sensor Dashboard Server
Serves live ESP32 data via SSE to the browser dashboard.

Usage: python3 server.py [--port 5050] [--fresh]
"""

import serial
import serial.tools.list_ports
import re, csv, threading, queue, time, os, json, argparse, sys, traceback, logging
from datetime import datetime, timedelta
from flask import Flask, Response, jsonify, request

logger = logging.getLogger('wilo.dashboard')
app = Flask(__name__)

CSV_PATH = os.path.join(os.path.dirname(__file__), '..', 'data', 'pressure_log.csv')
SERIAL_PORT = None
BAUD = 115200
_CONTROLLER_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', 'controller'))
_PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..'))
if _PROJECT_ROOT not in sys.path:
    sys.path.insert(0, _PROJECT_ROOT)
if _CONTROLLER_DIR not in sys.path:
    sys.path.insert(0, _CONTROLLER_DIR)

subscribers = []
subscribers_lock = threading.Lock()
latest = {"packet": -1, "voltage": 0.0, "pressure_kpa": 0.0, "pressure_mpa": 0.0, "status": "connecting", "timestamp": ""}
reader_thread = None
stop_event = threading.Event()


def _json_error(message: str, status_code: int = 500, **extra):
    payload = {"ok": False, "error": message}
    payload.update(extra)
    response = jsonify(payload)
    response.status_code = status_code
    return response


def _load_manual_pump_module():
    try:
        import manual_pump_control  # type: ignore

        return manual_pump_control, None
    except Exception as exc:
        return None, exc


def _read_manual_pump_status():
    manual_pump_control, import_error = _load_manual_pump_module()
    if manual_pump_control is None:
        return {
            "available": False,
            "pump_relay_on": None,
            "timestamp": None,
            "relay_pin": None,
            "active_low": None,
            "gpio_level": None,
            "error": str(import_error),
        }

    try:
        status = manual_pump_control.read_status()
        return {
            "available": True,
            **status,
        }
    except Exception as exc:
        return {
            "available": False,
            "pump_relay_on": None,
            "timestamp": None,
            "relay_pin": None,
            "active_low": None,
            "gpio_level": None,
            "error": str(exc),
        }


def _set_manual_pump(turn_on: bool, notify_controller: bool = True):
    manual_pump_control, import_error = _load_manual_pump_module()
    if manual_pump_control is None:
        raise RuntimeError(f"manual pump control unavailable: {import_error}")
    return manual_pump_control.set_pump(turn_on, notify_controller=notify_controller)


def _load_remote_bridge_module():
    try:
        import remote_bridge  # type: ignore

        return remote_bridge, None
    except Exception as exc:
        return None, exc


def _runtime_bridge_status():
    remote_bridge, import_error = _load_remote_bridge_module()
    if remote_bridge is None:
        return None, import_error

    try:
        return remote_bridge.read_status(), None
    except Exception as exc:
        return None, exc


def _dashboard_mode_file():
    import tank_config as CFG

    return os.path.join(CFG.LOG_DIR, 'dashboard_mode.json')


def _read_dashboard_mode(runtime_status=None):
    try:
        from runtime_channel import read_json

        saved = read_json(_dashboard_mode_file()) or {}
        mode = saved.get('mode')
        if mode in ('auto', 'manual'):
            return mode
    except Exception:
        pass

    if runtime_status and runtime_status.get('system_mode') in ('auto', 'manual'):
        return runtime_status.get('system_mode')

    return 'manual' if runtime_status and runtime_status.get('override') else 'auto'


def _write_dashboard_mode(mode: str):
    from runtime_channel import atomic_write_json

    atomic_write_json(_dashboard_mode_file(), {
        'mode': mode,
        'timestamp': datetime.now().isoformat(),
        'source': 'dashboard-ui',
    })


def _prediction_payload():
    try:
        from config.settings import FALLBACK_START_HOUR, FALLBACK_DURATION
    except Exception:
        FALLBACK_START_HOUR = 7.0
        FALLBACK_DURATION = 90

    try:
        from src.models.prediction import get_comprehensive_prediction
        from src.utils.sensors import get_fallback_sensor_data

        prediction = get_comprehensive_prediction(get_fallback_sensor_data())
        return {
            "start_hour": float(prediction["start_hour"]),
            "duration": float(prediction["duration"]),
            "method": prediction.get("method", "prediction"),
            "confidence": prediction.get("confidence", "medium"),
        }
    except Exception as exc:
        return {
            "start_hour": float(FALLBACK_START_HOUR),
            "duration": float(FALLBACK_DURATION),
            "method": "fallback",
            "confidence": "low",
            "error": str(exc),
        }


def _is_in_prediction_window(prediction: dict, now: datetime | None = None) -> bool:
    now = now or datetime.now()
    start_min = int(round(float(prediction.get("start_hour", 7.0)) * 60)) % (24 * 60)
    duration_min = max(0, int(round(float(prediction.get("duration", 0)))))
    current_min = now.hour * 60 + now.minute

    if duration_min <= 0:
        return False
    if duration_min >= 24 * 60:
        return True

    elapsed = (current_min - start_min) % (24 * 60)
    return elapsed < duration_min


def _apply_auto_control_if_needed(system_mode: str, pump_status: dict, prediction: dict) -> tuple[dict, dict]:
    return pump_status, {
        "enabled": system_mode == "auto",
        "action": "hold",
        "should_run": False,
        "reason": "Handled securely by pump_controller hardware loop"
    }


def _telemetry_from_runtime(runtime_status):
    if not runtime_status:
        return None

    pressure_kpa = runtime_status.get("pressure_kpa")
    return {
        "packet": runtime_status.get("lora_pkt", -1),
        "voltage": runtime_status.get("sensor_voltage", 0.0) or 0.0,
        "mains_voltage": runtime_status.get("voltage_ac", 0.0) or 0.0,
        "mains_current": runtime_status.get("current_amps", 0.0) or 0.0,
        "pressure_kpa": pressure_kpa if isinstance(pressure_kpa, (int, float)) else 0.0,
        "pressure_mpa": (pressure_kpa / 1000.0) if isinstance(pressure_kpa, (int, float)) else 0.0,
        "status": runtime_status.get("sensor_status") or ("ok" if pressure_kpa is not None else "disconnected"),
        "timestamp": runtime_status.get("timestamp") or "",
    }


def _load_festival_engine():
    try:
        from festival_policy import get_festival_policy_engine
        return get_festival_policy_engine(), None
    except Exception:
        try:
            from src.controller.festival_policy import get_festival_policy_engine
            return get_festival_policy_engine(), None
        except Exception as exc:
            return None, exc


def _dashboard_status_payload():
    pump_status = _read_manual_pump_status()
    runtime_status, runtime_error = _runtime_bridge_status()
    telemetry = _telemetry_from_runtime(runtime_status) or latest
    system_mode = _read_dashboard_mode(runtime_status)
    prediction = _prediction_payload()
    pump_status, auto_control = _apply_auto_control_if_needed(system_mode, pump_status, prediction)
    runtime_payload = dict(runtime_status or {})
    runtime_payload["ml_prediction"] = runtime_payload.get("ml_prediction") or prediction
    runtime_payload["system_mode"] = system_mode

    festival_engine, _ = _load_festival_engine()
    festival_status = None
    if runtime_status and runtime_status.get("festival"):
        festival_status = runtime_status.get("festival")
    elif festival_engine:
        festival_status = festival_engine.get_status()

    # DO NOT overwrite the true hardware relay state reported by pump_controller.py!
    return {
        "ok": True,
        "manual_override_available": pump_status.get("available", False),
        "manual_override_enabled": pump_status.get("available", False),
        "pump": pump_status,
        "telemetry": telemetry,
        "runtime": runtime_payload,
        "runtime_error": str(runtime_error) if runtime_error else None,
        "auto_control": auto_control,
        "system_mode": system_mode,
        "festival": festival_status,
        "timestamp": datetime.now().isoformat(),
    }


@app.after_request
def add_cors_headers(response):
    response.headers["Access-Control-Allow-Origin"] = request.headers.get("Origin", "*")
    response.headers["Access-Control-Allow-Headers"] = "Content-Type"
    response.headers["Access-Control-Allow-Methods"] = "GET,POST,OPTIONS"
    return response

# ── Serial reader ──────────────────────────────────────────────────────────────

def find_port():
    for p in serial.tools.list_ports.comports():
        device = (p.device or '').lower()
        description = (p.description or '').lower()
        hwid = (p.hwid or '').lower()
        if any(k in device for k in ('usbserial', 'usbmodem', 'ttyusb', 'ttyacm', 'com')):
            return p.device
        if any(k in description for k in ('cp210', 'ch340', 'usb serial', 'uart bridge', 'silicon labs')):
            return p.device
        if any(k in hwid for k in ('vid:pid=10c4:ea60', 'vid_10c4&pid_ea60', 'vid:pid=1a86:7523')):
            return p.device
    ports = serial.tools.list_ports.comports()
    return ports[0].device if ports else None

def broadcast(data: dict):
    global latest
    latest = data
    msg = f"data: {json.dumps(data)}\n\n"
    with subscribers_lock:
        dead = []
        for q in subscribers:
            try:
                q.put_nowait(msg)
            except queue.Full:
                dead.append(q)
        for q in dead:
            subscribers.remove(q)

def reader_loop(port, fresh_csv, stop_evt):
    os.makedirs(os.path.dirname(os.path.abspath(CSV_PATH)), exist_ok=True)
    mode = 'w' if fresh_csv else 'a'
    write_header = fresh_csv or not os.path.exists(CSV_PATH) or os.path.getsize(CSV_PATH) == 0
    f = open(CSV_PATH, mode, newline='')
    writer = csv.writer(f)
    if write_header:
        writer.writerow(['timestamp', 'packet', 'voltage_V', 'pressure_kPa', 'pressure_MPa', 'status'])
        f.flush()

    s = None
    v = st = pkt = None

    while not stop_evt.is_set():
        try:
            if s is None or not s.is_open:
                s = serial.Serial(port, BAUD, timeout=2, dsrdtr=False, rtscts=False)
                s.setDTR(False); s.setRTS(False)
                print(f'[serial] opened {port}', flush=True)
                broadcast({**latest, "status": "connecting"})

            raw = s.readline()
            if not raw:
                continue
            line = raw.decode('utf-8', errors='replace').strip()
            if not line:
                continue

            if line.startswith('Sensor Voltage'):
                m = re.search(r'([\d.]+) V', line)
                if m: v = float(m.group(1))
                st = 'ok'
            elif 'SENSOR FAULT' in line:
                st = 'fault'
            elif line.startswith('LoRa sent'):
                m = re.search(r'#(\d+)', line)
                if m: pkt = int(m.group(1))
                if v is not None:
                    kpa = max(0.0, (v - 0.5) / 4.0 * 100.0) if st == 'ok' else -1.0
                    mpa = kpa / 1000.0 if st == 'ok' else -1.0
                    ts  = datetime.now().isoformat()
                    writer.writerow([ts, pkt, round(v,3), round(kpa,2), round(mpa,4), st])
                    f.flush()
                    broadcast({"packet": pkt, "voltage": round(v,3),
                               "pressure_kpa": round(kpa,2), "pressure_mpa": round(mpa,4),
                               "status": st, "timestamp": ts})
                    print(f'[data] pkt={pkt} {round(v,3)}V {round(kpa,2)}kPa', flush=True)
                    v = st = pkt = None

        except Exception as e:
            print(f'[serial error] {e}', flush=True)
            broadcast({**latest, "status": "disconnected"})
            time.sleep(2)
            if s:
                try: s.close()
                except: pass
                s = None
    if s:
        try: s.close()
        except: pass
    f.close()

def start_reader(fresh=False):
    global reader_thread, stop_event, _v, _st, _pkt
    _v = _st = _pkt = None
    if reader_thread and reader_thread.is_alive():
        stop_event.set()
        reader_thread.join(timeout=3)
    stop_event = threading.Event()
    port = SERIAL_PORT or find_port()
    if not port:
        broadcast({**latest, "status": "disconnected"})
        print("[serial] no matching serial port found; dashboard will use runtime bridge status", flush=True)
        return
    reader_thread = threading.Thread(target=reader_loop, args=(port, fresh, stop_event), daemon=True)
    reader_thread.start()

# ── Routes ─────────────────────────────────────────────────────────────────────

@app.route('/')
def index():
    with open(os.path.join(os.path.dirname(__file__), 'dashboard.html')) as fh:
        return fh.read()

@app.route('/stream')
def stream():
    q = queue.Queue(maxsize=50)
    with subscribers_lock:
        subscribers.append(q)
    # send current state immediately
    q.put_nowait(f"data: {json.dumps(latest)}\n\n")

    def generate():
        try:
            while True:
                try:
                    yield q.get(timeout=20)
                except queue.Empty:
                    yield ": keep-alive\n\n"
        finally:
            with subscribers_lock:
                if q in subscribers:
                    subscribers.remove(q)

    return Response(generate(), mimetype='text/event-stream',
                    headers={'Cache-Control': 'no-cache', 'X-Accel-Buffering': 'no'})

@app.route('/restart', methods=['POST'])
def restart():
    start_reader(fresh=True)
    return ('', 204)

@app.route('/latest')
def get_latest():
    return jsonify(latest)


@app.route('/api/dashboard/status')
def get_dashboard_status():
    return jsonify(_dashboard_status_payload())


@app.route('/api/pump/status')
def get_pump_status():
    status = _read_manual_pump_status()
    response_status = 200 if status.get("available") else 503
    return jsonify({"ok": status.get("available", False), "pump": status}), response_status


@app.route('/api/pump/on', methods=['POST', 'OPTIONS'])
def pump_on():
    if request.method == 'OPTIONS':
        return ('', 204)
    try:
        status = _set_manual_pump(True)
        return jsonify({"ok": True, "pump": status, "message": "Pump turned on"})
    except Exception as exc:
        traceback.print_exc()
        return _json_error("failed to turn pump on", 500, detail=str(exc))


@app.route('/api/pump/off', methods=['POST', 'OPTIONS'])
def pump_off():
    if request.method == 'OPTIONS':
        return ('', 204)
    try:
        status = _set_manual_pump(False)
        return jsonify({"ok": True, "pump": status, "message": "Pump turned off"})
    except Exception as exc:
        traceback.print_exc()
        return _json_error("failed to turn pump off", 500, detail=str(exc))


@app.route('/api/mode', methods=['GET', 'POST', 'OPTIONS'])
def system_mode():
    if request.method == 'OPTIONS':
        return ('', 204)
    if request.method == 'GET':
        payload = _dashboard_status_payload()
        return jsonify({"ok": True, "mode": payload.get('system_mode', 'auto')})
    data = request.get_json(silent=True) or {}
    mode = data.get('mode', 'auto')
    try:
        import tank_config as CFG
        from runtime_channel import atomic_write_json
        from datetime import datetime
        action = 'manual_mode_on' if mode == 'manual' else 'manual_mode_off'
        command = {
            'action': action,
            'issued_at': datetime.now().isoformat(),
            'source': 'dashboard-ui',
        }
        atomic_write_json(CFG.CONTROL_FILE, command)
        _write_dashboard_mode(mode)
        return jsonify({"ok": True, "mode": mode, "message": f"Switched to {mode} mode"})
    except Exception as exc:
        traceback.print_exc()
        return _json_error(f"failed to switch to {mode} mode", 500, detail=str(exc))


@app.route('/api/pump/clear-override', methods=['POST', 'OPTIONS'])
def pump_clear_override():
    """Drop the manual override so the controller returns to automated mode."""
    if request.method == 'OPTIONS':
        return ('', 204)
    try:
        import tank_config as CFG
        from runtime_channel import atomic_write_json
        from datetime import datetime
        command = {
            'action': 'override_clear',
            'issued_at': datetime.now().isoformat(),
            'source': 'dashboard-ui',
        }
        atomic_write_json(CFG.CONTROL_FILE, command)
        _write_dashboard_mode('auto')
        return jsonify({"ok": True, "message": "Manual override cleared; controller resumed automated mode"})
    except Exception as exc:
        traceback.print_exc()
        return _json_error("failed to clear override", 500, detail=str(exc))


# ── Festival Policy Endpoints ─────────────────────────────────────────────────

@app.route('/api/festivals', methods=['GET'])
def get_festivals():
    """List all available holidays and festivals from the dataset."""
    festival_engine, err = _load_festival_engine()
    if festival_engine is None:
        return _json_error("Festival policy engine unavailable", 503, detail=str(err))
    return jsonify({
        "ok": True,
        "festivals": festival_engine.get_all_festivals()
    })


@app.route('/api/festivals/today', methods=['GET'])
def get_today_festival():
    """Return festival occurring on current date (IST)."""
    festival_engine, err = _load_festival_engine()
    if festival_engine is None:
        return _json_error("Festival policy engine unavailable", 503, detail=str(err))
    today_f = festival_engine.get_today_festival()
    return jsonify({
        "ok": True,
        "today": today_f,
        "is_festival_day": today_f is not None,
    })


@app.route('/api/festivals/upcoming', methods=['GET'])
def get_upcoming_festivals():
    """Return upcoming festivals within N days (default 30)."""
    festival_engine, err = _load_festival_engine()
    if festival_engine is None:
        return _json_error("Festival policy engine unavailable", 503, detail=str(err))
    try:
        days = int(request.args.get('days', 30))
    except ValueError:
        days = 30
    current_dt = festival_engine.get_current_time()
    upcoming = []
    for day_offset in range(max(1, days)):
        check_date = current_dt.date() + timedelta(days=day_offset)
        matches = festival_engine.get_festivals_for_date(check_date)
        for m in matches:
            upcoming.append(m)
    return jsonify({
        "ok": True,
        "upcoming": upcoming,
        "count": len(upcoming),
    })


@app.route('/api/festival/status', methods=['GET'])
def get_festival_status():
    """Get current festival policy status, including whether start is blocked."""
    festival_engine, err = _load_festival_engine()
    if festival_engine is None:
        return _json_error("Festival policy engine unavailable", 503, detail=str(err))
    return jsonify({
        "ok": True,
        "festival": festival_engine.get_status()
    })


@app.route('/api/festival/mode', methods=['POST', 'OPTIONS'])
def set_festival_mode():
    """Enable or disable Festival Mode."""
    if request.method == 'OPTIONS':
        return ('', 204)
    festival_engine, err = _load_festival_engine()
    if festival_engine is None:
        return _json_error("Festival policy engine unavailable", 503, detail=str(err))
    data = request.get_json(silent=True) or {}
    if 'enabled' not in data:
        return _json_error("Missing required field 'enabled' (boolean)", 400)
    enabled = bool(data['enabled'])
    new_state = festival_engine.set_mode(enabled)

    # Notify controller via control channel
    try:
        import tank_config as CFG
        from runtime_channel import atomic_write_json
        command = {
            'action': 'festival_mode',
            'issued_at': datetime.now().isoformat(),
            'source': 'dashboard-ui',
            'metadata': {'enabled': enabled},
        }
        atomic_write_json(CFG.CONTROL_FILE, command)
    except Exception as exc:
        logger.warning(f"Could not forward festival_mode to controller: {exc}")

    status = festival_engine.get_status()
    return jsonify({
        "ok": True,
        "mode_enabled": enabled,
        "festival": status,
        "message": f"Festival mode {'enabled' if enabled else 'disabled'}"
    })


@app.route('/api/festival/select', methods=['POST', 'OPTIONS'])
def select_festival():
    """Select a specific festival and date."""
    if request.method == 'OPTIONS':
        return ('', 204)
    festival_engine, err = _load_festival_engine()
    if festival_engine is None:
        return _json_error("Festival policy engine unavailable", 503, detail=str(err))
    data = request.get_json(silent=True) or {}
    festival_name = data.get('festival_name')
    festival_date = data.get('festival_date')

    if not festival_name or not festival_date:
        return _json_error("Both 'festival_name' and 'festival_date' (YYYY-MM-DD) are required", 400)

    try:
        datetime.strptime(festival_date, '%Y-%m-%d')
    except ValueError:
        return _json_error("Invalid date format for 'festival_date', expected YYYY-MM-DD", 400)

    festival_engine.select_festival(festival_name, festival_date)

    try:
        import tank_config as CFG
        from runtime_channel import atomic_write_json
        command = {
            'action': 'festival_select',
            'issued_at': datetime.now().isoformat(),
            'source': 'dashboard-ui',
            'metadata': {'festival_name': festival_name, 'festival_date': festival_date},
        }
        atomic_write_json(CFG.CONTROL_FILE, command)
    except Exception as exc:
        logger.warning(f"Could not forward festival_select to controller: {exc}")

    status = festival_engine.get_status()
    return jsonify({
        "ok": True,
        "festival": status,
        "message": f"Selected festival '{festival_name}' on {festival_date}"
    })


@app.route('/api/festival/reset', methods=['POST', 'OPTIONS'])
def reset_festival():
    """Reset festival selection and simulation fixtures."""
    if request.method == 'OPTIONS':
        return ('', 204)
    festival_engine, err = _load_festival_engine()
    if festival_engine is None:
        return _json_error("Festival policy engine unavailable", 503, detail=str(err))
    festival_engine.reset()

    try:
        import tank_config as CFG
        from runtime_channel import atomic_write_json
        command = {
            'action': 'festival_reset',
            'issued_at': datetime.now().isoformat(),
            'source': 'dashboard-ui',
            'metadata': {},
        }
        atomic_write_json(CFG.CONTROL_FILE, command)
    except Exception as exc:
        logger.warning(f"Could not forward festival_reset to controller: {exc}")

    status = festival_engine.get_status()
    return jsonify({
        "ok": True,
        "festival": status,
        "message": "Festival settings and simulation state reset"
    })


@app.route('/api/festival/simulate', methods=['POST', 'OPTIONS'])
def simulate_festival():
    """Set or clear developer simulation fixture (date YYYY-MM-DD, time HH:MM)."""
    if request.method == 'OPTIONS':
        return ('', 204)
    festival_engine, err = _load_festival_engine()
    if festival_engine is None:
        return _json_error("Festival policy engine unavailable", 503, detail=str(err))
    data = request.get_json(silent=True) or {}
    sim_date = data.get('date')
    sim_time = data.get('time')

    if sim_date:
        try:
            datetime.strptime(sim_date, '%Y-%m-%d')
        except ValueError:
            return _json_error("Invalid date format for 'date', expected YYYY-MM-DD", 400)
    if sim_time:
        try:
            datetime.strptime(sim_time, '%H:%M')
        except ValueError:
            return _json_error("Invalid time format for 'time', expected HH:MM", 400)

    festival_engine.set_simulation(sim_date, sim_time)

    try:
        import tank_config as CFG
        from runtime_channel import atomic_write_json
        command = {
            'action': 'festival_simulate',
            'issued_at': datetime.now().isoformat(),
            'source': 'dashboard-ui',
            'metadata': {'date': sim_date, 'time': sim_time},
        }
        atomic_write_json(CFG.CONTROL_FILE, command)
    except Exception as exc:
        logger.warning(f"Could not forward festival_simulate to controller: {exc}")

    status = festival_engine.get_status()
    return jsonify({
        "ok": True,
        "festival": status,
        "message": f"Simulation set to date={sim_date}, time={sim_time}" if sim_date else "Simulation cleared"
    })


# ── Main ───────────────────────────────────────────────────────────────────────

if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--port', type=int, default=5050)
    parser.add_argument('--serial-port', default=None)
    parser.add_argument('--fresh', action='store_true')
    args = parser.parse_args()
    SERIAL_PORT = args.serial_port
    start_reader(fresh=args.fresh)
    print(f"\n  Dashboard -> http://localhost:{args.port}\n")
    app.run(host='0.0.0.0', port=args.port, threaded=True)
