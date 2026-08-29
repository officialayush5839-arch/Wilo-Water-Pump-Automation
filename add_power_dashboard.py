import os

SERVER = "src/dashboard/server.py"
WILO_SIM = "dashboard/src/components/WiloSimulation.tsx"

# 1. Patch server.py
with open(SERVER, "r", encoding="utf-8") as f:
    s_code = f.read()

s_old = """    return {
        "packet": runtime_status.get("lora_pkt", -1),
        "voltage": runtime_status.get("sensor_voltage", 0.0) or 0.0,
        "pressure_kpa": pressure_kpa if isinstance(pressure_kpa, (int, float)) else 0.0,
        "pressure_mpa": (pressure_kpa / 1000.0) if isinstance(pressure_kpa, (int, float)) else 0.0,
        "status": runtime_status.get("sensor_status") or ("ok" if pressure_kpa is not None else "disconnected"),
        "timestamp": runtime_status.get("timestamp") or "",
    }"""

s_new = """    return {
        "packet": runtime_status.get("lora_pkt", -1),
        "voltage": runtime_status.get("sensor_voltage", 0.0) or 0.0,
        "mains_voltage": runtime_status.get("voltage_ac", 0.0) or 0.0,
        "mains_current": runtime_status.get("current_amps", 0.0) or 0.0,
        "pressure_kpa": pressure_kpa if isinstance(pressure_kpa, (int, float)) else 0.0,
        "pressure_mpa": (pressure_kpa / 1000.0) if isinstance(pressure_kpa, (int, float)) else 0.0,
        "status": runtime_status.get("sensor_status") or ("ok" if pressure_kpa is not None else "disconnected"),
        "timestamp": runtime_status.get("timestamp") or "",
    }"""

if s_old in s_code:
    s_code = s_code.replace(s_old, s_new)
    with open(SERVER, "w", encoding="utf-8") as f:
        f.write(s_code)
    print("✅ server.py API patched successfully!")

# 2. Patch WiloSimulation.tsx (React Frontend)
with open(WILO_SIM, "r", encoding="utf-8") as f:
    w_code = f.read()

w_interface_old = """  telemetry?: {
    status?: string;
    timestamp?: string;
    pressure_kpa?: number | null;
    voltage?: number | null;
    packet?: number | null;
    upper_pct?: number | null;
    lora_age_s?: number | null;
  };"""

w_interface_new = """  telemetry?: {
    status?: string;
    timestamp?: string;
    pressure_kpa?: number | null;
    voltage?: number | null;
    mains_voltage?: number | null;
    mains_current?: number | null;
    packet?: number | null;
    upper_pct?: number | null;
    lora_age_s?: number | null;
  };"""

w_state_old = """  const [sensorVoltage, setSensorVoltage] = useState<number | null>(null);
  const [telemetryPacket, setTelemetryPacket] = useState<number | null>(null);"""

w_state_new = """  const [sensorVoltage, setSensorVoltage] = useState<number | null>(null);
  const [mainsVoltage, setMainsVoltage] = useState<number | null>(null);
  const [mainsCurrent, setMainsCurrent] = useState<number | null>(null);
  const [telemetryPacket, setTelemetryPacket] = useState<number | null>(null);"""

w_setters_old = """    setSensorVoltage(
      typeof payload.telemetry?.voltage === "number" ? payload.telemetry.voltage : null
    );
    setTelemetryPacket("""

w_setters_new = """    setSensorVoltage(
      typeof payload.telemetry?.voltage === "number" ? payload.telemetry.voltage : null
    );
    setMainsVoltage(
      typeof payload.telemetry?.mains_voltage === "number" ? payload.telemetry.mains_voltage : null
    );
    setMainsCurrent(
      typeof payload.telemetry?.mains_current === "number" ? payload.telemetry.mains_current : null
    );
    setTelemetryPacket("""

w_ui_old = """              <div className="space-y-4">
                <div className="flex items-center justify-between">
                  <span className="text-sm">Current Pump Status</span>"""

w_ui_new = """              <div className="space-y-4">
                <div className="flex items-center justify-between">
                  <span className="text-sm font-semibold text-primary">Power Consumption</span>
                  <span className="text-sm font-bold text-primary">
                    {mainsVoltage !== null ? `${Math.round(mainsVoltage)}V` : "--V"} @ {mainsCurrent !== null ? `${mainsCurrent.toFixed(2)}A` : "--A"}
                  </span>
                </div>
                <div className="flex items-center justify-between">
                  <span className="text-sm">Current Pump Status</span>"""

if w_interface_old in w_code: w_code = w_code.replace(w_interface_old, w_interface_new)
if w_state_old in w_code: w_code = w_code.replace(w_state_old, w_state_new)
if w_setters_old in w_code: w_code = w_code.replace(w_setters_old, w_setters_new)
if w_ui_old in w_code: w_code = w_code.replace(w_ui_old, w_ui_new)

with open(WILO_SIM, "w", encoding="utf-8") as f:
    f.write(w_code)
print("✅ React Dashboard UI patched successfully!")
