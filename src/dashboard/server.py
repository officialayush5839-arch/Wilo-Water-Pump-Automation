#!/usr/bin/env python3
"""
Pressure Sensor Dashboard Server
Serves live ESP32 data via SSE to the browser dashboard.

Usage: python3 server.py [--port 5050] [--fresh]
"""

import serial
import serial.tools.list_ports
import re, csv, threading, queue, time, os, json, argparse, sys, traceback
from datetime import datetime
from flask import Flask, Response, jsonify, request

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


def _get_water_cut_manager():
    try:
        import tank_config as CFG
        from water_cut_manager import WaterCutManager

        return WaterCutManager(
            cuts_file_path=CFG.WATER_CUTS_FILE,
            default_reserve_pct=getattr(CFG, 'WATER_CUT_DEFAULT_RESERVE', 95.0),
            default_prefill_hours=getattr(CFG, 'WATER_CUT_DEFAULT_PREFILL_HOURS', 4.0),
        )
    except Exception as exc:
        return None


def _get_festival_engine():
    try:
        import tank_config as CFG
        from festival_policy import FestivalPolicyEngine

        return FestivalPolicyEngine(
            csv_path=getattr(CFG, 'HOLIDAY_CSV_PATH', None),
            state_file=getattr(CFG, 'FESTIVAL_STATE_FILE', None),
        )
    except Exception as exc:
        return None


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

    wc_mgr = _get_water_cut_manager()
    water_cut_status = (runtime_payload.get('water_cut')) or (wc_mgr.get_status() if wc_mgr else {})
    runtime_payload["water_cut"] = water_cut_status

    fest_eng = _get_festival_engine()
    fest_status = (runtime_payload.get('festival_policy')) or (fest_eng.evaluate_policy() if fest_eng else {})
    runtime_payload["festival_policy"] = fest_status

    cur_class = runtime_payload.get('current_classification')
    if not cur_class:
        cur_amps = telemetry.get('mains_current') or runtime_payload.get('current_amps')
        relay_on = bool(runtime_payload.get('pump_relay_on'))
        if not relay_on:
            cur_class = {
                'raw_amps': cur_amps,
                'filtered_amps': None,
                'state': 'UNKNOWN',
                'full_persisted': False,
                'full_persistence_seconds': 0.0,
                'startup_blanking': False,
                'status_detail': 'Pump is OFF',
            }
        else:
            cur_class = {
                'raw_amps': cur_amps,
                'filtered_amps': cur_amps,
                'state': 'FULL' if (cur_amps is not None and cur_amps <= 6.5) else (
                    'EMPTY' if (cur_amps is not None and cur_amps >= 11.5) else (
                        'MID' if (cur_amps is not None and 8.0 <= cur_amps <= 10.0) else 'MID'
                    )
                ) if cur_amps is not None and cur_amps >= 1.5 else 'UNKNOWN',
                'full_persisted': False,
                'full_persistence_seconds': 0.0,
                'startup_blanking': False,
                'status_detail': 'Live classification',
            }
    runtime_payload["current_classification"] = cur_class
    runtime_payload["current_tank_state"] = cur_class.get('state', 'UNKNOWN')

    return {
        "ok": True,
        "manual_override_available": pump_status.get("available", False),
        "manual_override_enabled": pump_status.get("available", False),
        "pump": pump_status,
        "telemetry": telemetry,
        "runtime": runtime_payload,
        "water_cut": water_cut_status,
        "festival_policy": fest_status,
        "current_classification": cur_class,
        "runtime_error": str(runtime_error) if runtime_error else None,
        "auto_control": auto_control,
        "system_mode": system_mode,
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


# ── Water Cut REST Endpoints ───────────────────────────────────────────────────

@app.route('/api/water-cuts', methods=['GET', 'POST', 'OPTIONS'])
def handle_water_cuts():
    if request.method == 'OPTIONS':
        return ('', 204)

    mgr = _get_water_cut_manager()
    if not mgr:
        return _json_error("Water cut manager unavailable", 500)

    if request.method == 'GET':
        return jsonify({
            "ok": True,
            "cuts": mgr.get_all_cuts(),
            "status": mgr.get_status(),
        })

    # POST: create water cut
    data = request.get_json(silent=True) or {}
    ok, err, created = mgr.add_cut(data)
    if not ok:
        return _json_error(f"Failed to create water cut: {err}", 400)

    return jsonify({
        "ok": True,
        "cut": created,
        "status": mgr.get_status(),
        "message": "Water cut scheduled successfully",
    }), 201


@app.route('/api/water-cuts/<cut_id>', methods=['PUT', 'DELETE', 'OPTIONS'])
def handle_single_water_cut(cut_id: str):
    if request.method == 'OPTIONS':
        return ('', 204)

    mgr = _get_water_cut_manager()
    if not mgr:
        return _json_error("Water cut manager unavailable", 500)

    if request.method == 'DELETE':
        ok, err = mgr.delete_cut(cut_id)
        if not ok:
            return _json_error(f"Failed to delete water cut: {err}", 404)
        return jsonify({
            "ok": True,
            "status": mgr.get_status(),
            "message": "Water cut deleted successfully",
        })

    # PUT: update water cut
    data = request.get_json(silent=True) or {}
    ok, err, updated = mgr.update_cut(cut_id, data)
    if not ok:
        return _json_error(f"Failed to update water cut: {err}", 400)

    return jsonify({
        "ok": True,
        "cut": updated,
        "status": mgr.get_status(),
        "message": "Water cut updated successfully",
    })


# ── Festival & Holiday Policy REST Endpoints ────────────────────────────────────

@app.route('/api/festival/status', methods=['GET', 'OPTIONS'])
def handle_festival_status():
    if request.method == 'OPTIONS':
        return ('', 204)
    engine = _get_festival_engine()
    if not engine:
        return _json_error("Festival policy engine unavailable", 500)
    return jsonify({
        "ok": True,
        "status": engine.evaluate_policy(),
        "mode_enabled": engine.mode_enabled,
        "selected_festival": engine.selected_festival,
        "simulated_datetime": engine.simulated_datetime.isoformat() if engine.simulated_datetime else None,
    })


@app.route('/api/festival/mode', methods=['POST', 'OPTIONS'])
def handle_festival_mode():
    if request.method == 'OPTIONS':
        return ('', 204)
    engine = _get_festival_engine()
    if not engine:
        return _json_error("Festival policy engine unavailable", 500)

    data = request.get_json(silent=True) or {}
    if 'enabled' not in data and 'mode' not in data:
        return _json_error("Missing 'enabled' (boolean) or 'mode' ('on'/'off') in payload", 400)

    if 'enabled' in data:
        enabled = bool(data['enabled'])
    else:
        enabled = str(data.get('mode', '')).strip().lower() in ('on', 'true', '1', 'enable', 'enabled')

    status = engine.set_mode(enabled)
    return jsonify({
        "ok": True,
        "mode_enabled": engine.mode_enabled,
        "status": status,
        "message": f"Festival Policy Mode turned {'ON' if engine.mode_enabled else 'OFF'}",
    })


@app.route('/api/festival/select', methods=['POST', 'OPTIONS'])
def handle_festival_select():
    if request.method == 'OPTIONS':
        return ('', 204)
    engine = _get_festival_engine()
    if not engine:
        return _json_error("Festival policy engine unavailable", 500)

    data = request.get_json(silent=True) or {}
    event_name = data.get('event') or data.get('festival_name')
    event_date = data.get('date') or data.get('festival_date')

    if not event_name:
        return _json_error("Missing 'event' or 'festival_name' in payload", 400)

    ok, err, status = engine.select_festival(event_name, event_date)
    if not ok:
        return _json_error(err or "Failed to select festival", 400)

    return jsonify({
        "ok": True,
        "selected_festival": engine.selected_festival,
        "status": status,
        "message": f"Selected festival: {event_name}",
    })


@app.route('/api/festival/reset', methods=['POST', 'OPTIONS'])
def handle_festival_reset():
    if request.method == 'OPTIONS':
        return ('', 204)
    engine = _get_festival_engine()
    if not engine:
        return _json_error("Festival policy engine unavailable", 500)

    status = engine.reset_festival()
    return jsonify({
        "ok": True,
        "status": status,
        "message": "Festival selection and simulation overrides reset to defaults",
    })


@app.route('/api/festival/simulate', methods=['POST', 'OPTIONS'])
def handle_festival_simulate():
    if request.method == 'OPTIONS':
        return ('', 204)
    engine = _get_festival_engine()
    if not engine:
        return _json_error("Festival policy engine unavailable", 500)

    data = request.get_json(silent=True) or {}
    date_str = data.get('date')
    time_str = data.get('time')

    if not date_str or not time_str:
        return _json_error("Both 'date' (YYYY-MM-DD) and 'time' (HH:MM) are required", 400)

    ok, err, status = engine.simulate_datetime(date_str, time_str)
    if not ok:
        return _json_error(err or "Failed to set simulation datetime", 400)

    return jsonify({
        "ok": True,
        "simulated_datetime": engine.simulated_datetime.isoformat() if engine.simulated_datetime else None,
        "status": status,
        "message": f"Simulated datetime set to {date_str} {time_str} IST",
    })


@app.route('/api/festivals/today', methods=['GET', 'OPTIONS'])
def handle_festivals_today():
    if request.method == 'OPTIONS':
        return ('', 204)
    engine = _get_festival_engine()
    if not engine:
        return _json_error("Festival policy engine unavailable", 500)

    now_ist = engine.get_current_ist_datetime()
    today_str = now_ist.strftime('%Y-%m-%d')
    fest = engine.get_festival_for_date(today_str)
    return jsonify({
        "ok": True,
        "today_date": today_str,
        "festival": fest,
        "is_festival_today": fest is not None,
    })


@app.route('/api/festivals/upcoming', methods=['GET', 'OPTIONS'])
def handle_festivals_upcoming():
    if request.method == 'OPTIONS':
        return ('', 204)
    engine = _get_festival_engine()
    if not engine:
        return _json_error("Festival policy engine unavailable", 500)

    try:
        days = int(request.args.get('days', 90))
    except ValueError:
        days = 90

    from_date = request.args.get('from_date')
    upcoming = engine.get_upcoming_festivals(days=days, from_date=from_date)
    return jsonify({
        "ok": True,
        "count": len(upcoming),
        "days": days,
        "festivals": upcoming,
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
    print(f"\n  Dashboard → http://localhost:{args.port}\n")
    app.run(host='0.0.0.0', port=args.port, threaded=True)
