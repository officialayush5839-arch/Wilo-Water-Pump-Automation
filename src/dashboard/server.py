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


def _set_manual_pump(turn_on: bool):
    manual_pump_control, import_error = _load_manual_pump_module()
    if manual_pump_control is None:
        raise RuntimeError(f"manual pump control unavailable: {import_error}")
    return manual_pump_control.set_pump(turn_on)


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


def _queue_manual_override(turn_on: bool, source: str):
    remote_bridge, import_error = _load_remote_bridge_module()
    if remote_bridge is None:
        raise RuntimeError(f"remote bridge unavailable: {import_error}")

    action = 'override_on' if turn_on else 'override_off'
    return remote_bridge.write_override(action, source)


def _await_manual_override(turn_on: bool, timeout_s: float = 2.5):
    expected_override = "ON" if turn_on else "OFF"
    deadline = time.time() + timeout_s
    last_runtime = None

    while time.time() < deadline:
        runtime_status, _ = _runtime_bridge_status()
        last_runtime = runtime_status
        if runtime_status and runtime_status.get("override") == expected_override:
            return runtime_status, True
        time.sleep(0.1)

    return last_runtime, False


def _telemetry_from_runtime(runtime_status):
    if not runtime_status:
        return None

    pressure_kpa = runtime_status.get("pressure_kpa")
    sensor_voltage = runtime_status.get("sensor_voltage")
    upper_pct = runtime_status.get("upper_pct")
    lora_pkt = runtime_status.get("lora_pkt")
    lora_age_s = runtime_status.get("lora_age_s")
    sensor_status = runtime_status.get("sensor_status")
    telemetry_status = "waiting"

    if sensor_status == "fault":
        telemetry_status = "fault"
    elif isinstance(pressure_kpa, (int, float)) and lora_pkt is not None:
        telemetry_status = "ok"
    elif runtime_status.get("last_lora_ts"):
        telemetry_status = "stale"

    return {
        "packet": lora_pkt,
        "voltage": sensor_voltage if isinstance(sensor_voltage, (int, float)) else None,
        "pressure_kpa": pressure_kpa if isinstance(pressure_kpa, (int, float)) else None,
        "pressure_mpa": (pressure_kpa / 1000.0) if isinstance(pressure_kpa, (int, float)) else None,
        "upper_pct": upper_pct if isinstance(upper_pct, (int, float)) else None,
        "lora_age_s": lora_age_s if isinstance(lora_age_s, (int, float)) else None,
        "status": telemetry_status,
        "timestamp": runtime_status.get("last_lora_ts") or runtime_status.get("timestamp") or "",
    }


def _pump_status_payload(pump_status, runtime_status):
    gpio_relay_on = pump_status.get("pump_relay_on")
    runtime_relay_on = runtime_status.get("pump_relay_on") if runtime_status else None
    runtime_timestamp = runtime_status.get("timestamp") if runtime_status else None

    return {
        "available": bool(pump_status.get("available", False)),
        "pump_relay_on": gpio_relay_on if isinstance(gpio_relay_on, bool) else runtime_relay_on,
        "timestamp": runtime_timestamp or pump_status.get("timestamp"),
        "relay_pin": pump_status.get("relay_pin"),
        "active_low": pump_status.get("active_low"),
        "gpio_level": pump_status.get("gpio_level"),
        "error": pump_status.get("error"),
        "control_mode": runtime_status.get("controller_mode") if runtime_status else None,
        "override": runtime_status.get("override") if runtime_status else None,
    }


def _dashboard_status_payload():
    pump_status = _read_manual_pump_status()
    runtime_status, runtime_error = _runtime_bridge_status()
    telemetry = _telemetry_from_runtime(runtime_status) or latest
    pump = _pump_status_payload(pump_status, runtime_status)
    return {
        "ok": True,
        "manual_override_available": pump.get("available", False),
        "manual_override_enabled": pump.get("available", False),
        "pump": pump,
        "telemetry": telemetry,
        "runtime": runtime_status,
        "runtime_error": str(runtime_error) if runtime_error else None,
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
    dashboard_status = _dashboard_status_payload()
    pump = dashboard_status["pump"]
    response_status = 200 if pump.get("available") else 503
    return jsonify({"ok": pump.get("available", False), "pump": pump, "runtime": dashboard_status.get("runtime")}), response_status


@app.route('/api/pump/on', methods=['POST', 'OPTIONS'])
def pump_on():
    if request.method == 'OPTIONS':
        return ('', 204)
    try:
        source = (request.get_json(silent=True) or {}).get("source", "dashboard-ui")
        try:
            _set_manual_pump(True)
        except Exception as exc:
            print(f"[pump_on] direct GPIO toggle unavailable: {exc}", flush=True)
        command = _queue_manual_override(True, source)
        runtime_status, acknowledged = _await_manual_override(True)
        payload = _dashboard_status_payload()
        return jsonify({
            "ok": True,
            "command": command,
            "acknowledged": acknowledged,
            "pump": payload["pump"],
            "runtime": runtime_status or payload.get("runtime"),
            "message": "Pump override command accepted" if acknowledged else "Pump override command queued",
        })
    except Exception as exc:
        traceback.print_exc()
        return _json_error("failed to turn pump on", 500, detail=str(exc))


@app.route('/api/pump/off', methods=['POST', 'OPTIONS'])
def pump_off():
    if request.method == 'OPTIONS':
        return ('', 204)
    try:
        source = (request.get_json(silent=True) or {}).get("source", "dashboard-ui")
        try:
            _set_manual_pump(False)
        except Exception as exc:
            print(f"[pump_off] direct GPIO toggle unavailable: {exc}", flush=True)
        command = _queue_manual_override(False, source)
        runtime_status, acknowledged = _await_manual_override(False)
        payload = _dashboard_status_payload()
        return jsonify({
            "ok": True,
            "command": command,
            "acknowledged": acknowledged,
            "pump": payload["pump"],
            "runtime": runtime_status or payload.get("runtime"),
            "message": "Pump override command accepted" if acknowledged else "Pump override command queued",
        })
    except Exception as exc:
        traceback.print_exc()
        return _json_error("failed to turn pump off", 500, detail=str(exc))

# ── Main ───────────────────────────────────────────────────────────────────────

if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--port', type=int, default=5050)
    parser.add_argument('--serial-port', default=None)
    parser.add_argument('--fresh', action='store_true')
    args = parser.parse_args()
    SERIAL_PORT = args.serial_port
    start_reader(fresh=args.fresh)
    print(f"\n  Dashboard @ http://localhost:{args.port}\n")
    app.run(host='0.0.0.0', port=args.port, threaded=True)
