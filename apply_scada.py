import os
import shutil
import json

ADMIN_TSX = "dashboard/src/components/AdminDashboard.tsx"
SERVER_PY = "src/dashboard/server.py"

def backup(file_path):
    if not os.path.exists(file_path + ".backup"):
        shutil.copy(file_path, file_path + ".backup")
        print(f"Backed up {file_path}")

print("Creating backups...")
backup(ADMIN_TSX)
backup(SERVER_PY)

# 1. Update server.py
with open(SERVER_PY, "r", encoding="utf-8") as f:
    server_code = f.read()

sse_code = """
# --- SCADA Dashboard SSE Extension ---
dashboard_subscribers = []
dashboard_subscribers_lock = threading.Lock()
last_dashboard_payload_str = ""

def dashboard_sse_loop():
    global last_dashboard_payload_str
    while True:
        try:
            payload = _dashboard_status_payload()
            payload_str = json.dumps(payload)
            if payload_str != last_dashboard_payload_str:
                last_dashboard_payload_str = payload_str
                msg = f"data: {payload_str}\\n\\n"
                with dashboard_subscribers_lock:
                    dead = []
                    for q in dashboard_subscribers:
                        try:
                            q.put_nowait(msg)
                        except queue.Full:
                            dead.append(q)
                    for q in dead:
                        dashboard_subscribers.remove(q)
        except Exception as e:
            pass
        time.sleep(1)

threading.Thread(target=dashboard_sse_loop, daemon=True).start()

@app.route('/api/stream/dashboard')
def stream_dashboard():
    q = queue.Queue(maxsize=5)
    with dashboard_subscribers_lock:
        dashboard_subscribers.append(q)
    
    try:
        q.put_nowait(f"data: {json.dumps(_dashboard_status_payload())}\\n\\n")
    except:
        pass

    def generate():
        try:
            while True:
                try:
                    yield q.get(timeout=20)
                except queue.Empty:
                    yield ": keep-alive\\n\\n"
        finally:
            with dashboard_subscribers_lock:
                if q in dashboard_subscribers:
                    dashboard_subscribers.remove(q)

    return Response(generate(), mimetype='text/event-stream',
                    headers={'Cache-Control': 'no-cache', 'X-Accel-Buffering': 'no'})
# -------------------------------------
"""

if "stream_dashboard" not in server_code:
    with open(SERVER_PY, "a", encoding="utf-8") as f:
        f.write("\n" + sse_code)
    print("Patched server.py with /api/stream/dashboard")
else:
    print("server.py is already patched.")

# 2. Update AdminDashboard.tsx
admin_code = """import { useState, useEffect } from "react";
import { Card } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Activity, Power, Settings, Droplets, Gauge, Clock, AlertTriangle, Wifi, Zap } from "lucide-react";

export default function AdminDashboard() {
    const [data, setData] = useState<any>(null);
    const [connected, setConnected] = useState(false);

    useEffect(() => {
        const es = new EventSource('/api/stream/dashboard');
        es.onmessage = (e) => {
            setData(JSON.parse(e.data));
            setConnected(true);
        };
        es.onerror = () => setConnected(false);
        return () => es.close();
    }, []);

    if (!data) {
        return <div className="flex h-screen items-center justify-center p-8 bg-slate-950 text-white"><Activity className="animate-spin mr-2"/> Connecting to Live SCADA Backend...</div>;
    }

    const { runtime, pump, telemetry } = data;
    const level = runtime?.upper_pct ?? 0;
    const pressure = telemetry?.pressure_kpa ?? 0;
    const isRunning = pump?.pump_relay_on ?? false;
    const mode = runtime?.system_mode ?? "auto";

    return (
        <div className="p-6 max-w-7xl mx-auto space-y-6 bg-slate-950 min-h-screen text-slate-100">
            <div className="flex justify-between items-center mb-8">
                <h1 className="text-3xl font-bold tracking-tight text-white flex items-center gap-3">
                    <Activity className="h-8 w-8 text-blue-500" /> Live SCADA Monitoring Panel
                </h1>
                <Badge variant={connected ? "default" : "destructive"} className="px-4 py-2 text-sm uppercase tracking-wider font-bold shadow-lg">
                    {connected ? "🟢 Backend Connected" : "🔴 Backend Offline"}
                </Badge>
            </div>

            <div className="grid grid-cols-1 lg:grid-cols-3 gap-8">
                {/* Master Tank Visualization */}
                <Card className="lg:col-span-1 bg-slate-900 border-slate-800 p-8 flex flex-col items-center justify-center min-h-[550px] shadow-2xl relative overflow-hidden">
                    <div className="absolute top-0 left-0 w-full h-1 bg-gradient-to-r from-blue-600 to-teal-400"></div>
                    <h2 className="text-2xl font-black mb-10 text-slate-200 tracking-widest uppercase">MASTER TANK</h2>
                    <div className="relative w-56 h-80 border-[6px] border-slate-700 rounded-b-3xl rounded-t-md bg-slate-950 overflow-hidden shadow-inner flex flex-col justify-end items-center">
                        {/* Water Fill */}
                        <div 
                            className="w-full bg-gradient-to-t from-blue-700 to-blue-400 transition-all duration-1000 ease-in-out opacity-90 shadow-[0_-5px_15px_rgba(59,130,246,0.5)]"
                            style={{ height: `${Math.max(0, Math.min(100, level))}%` }}
                        >
                            <div className="w-full h-2 bg-blue-300 opacity-60 blur-sm"></div>
                        </div>
                        {/* Level Text overlay */}
                        <div className="absolute inset-0 flex flex-col items-center justify-center z-10 pointer-events-none">
                            <span className="text-5xl font-black text-white drop-shadow-[0_2px_4px_rgba(0,0,0,0.8)]">
                                {typeof level === 'number' ? level.toFixed(1) : '?'}%
                            </span>
                            <span className="text-sm font-bold text-blue-200 uppercase tracking-widest mt-2 drop-shadow-md">
                                Live Level
                            </span>
                        </div>
                    </div>
                </Card>

                {/* Telemetry Grid */}
                <div className="lg:col-span-2 grid grid-cols-1 md:grid-cols-2 gap-5">
                    <TelemetryCard title="Live Tank Level" value={`${typeof level === 'number' ? level.toFixed(1) : '?'} %`} subValue="From Pressure Sensor" icon={<Droplets className="text-blue-400 h-6 w-6"/>} />
                    <TelemetryCard title="Water Pressure" value={`${pressure.toFixed(2)} kPa`} subValue={`${(pressure/100).toFixed(3)} Bar`} icon={<Gauge className="text-purple-400 h-6 w-6"/>} />
                    <TelemetryCard title="Pump Status" value={isRunning ? "RUNNING" : "STANDBY"} status={isRunning ? "success" : "neutral"} icon={<Power className={isRunning ? "text-green-500 h-6 w-6" : "text-slate-500 h-6 w-6"}/>} />
                    <TelemetryCard title="Control Mode" value={mode.toUpperCase()} status={mode === 'auto' ? "success" : "warning"} icon={<Settings className="text-orange-400 h-6 w-6"/>} />
                    <TelemetryCard title="LoRa Telemetry" value={`Packet #${telemetry?.packet ?? '?'}`} subValue={`Age: ${runtime?.lora_age_s ?? '?'}s`} status={(runtime?.lora_age_s ?? 999) > 60 ? "error" : "success"} icon={<Wifi className="text-teal-400 h-6 w-6"/>} />
                    <TelemetryCard title="Relay Circuit" value={isRunning ? "ACTIVE (CLOSED)" : "INACTIVE (OPEN)"} status={isRunning ? "warning" : "neutral"} icon={<Zap className="text-yellow-400 h-6 w-6"/>} />
                    <TelemetryCard title="AI Scheduler" value={runtime?.ml_prediction?.duration ? "PREDICTION ACTIVE" : "IDLE"} subValue={runtime?.ml_prediction?.duration ? `Est. Fill: ${runtime.ml_prediction.duration.toFixed(1)} mins` : "Awaiting Drop"} icon={<Clock className="text-indigo-400 h-6 w-6"/>} />
                    <TelemetryCard title="Sensor Health" value={(runtime?.lora_age_s ?? 999) < 60 ? "HEALTHY" : "OFFLINE"} status={(runtime?.lora_age_s ?? 999) < 60 ? "success" : "error"} icon={<AlertTriangle className="text-red-400 h-6 w-6"/>} />
                </div>
            </div>
        </div>
    );
}

function TelemetryCard({ title, value, subValue, icon, status }: any) {
    const statusColors = {
        success: "text-green-400",
        warning: "text-orange-400",
        error: "text-red-500",
        neutral: "text-slate-300"
    };
    const colorClass = statusColors[status as keyof typeof statusColors] || statusColors.neutral;

    return (
        <Card className="bg-slate-900 border-slate-800 p-6 flex flex-col justify-center space-y-4 hover:bg-slate-800 transition-all duration-300 border-l-4" style={{borderLeftColor: status === 'error' ? '#ef4444' : status === 'success' ? '#22c55e' : status === 'warning' ? '#f97316' : '#334155'}}>
            <div className="flex items-center space-x-4">
                <div className="p-3 bg-slate-950 rounded-lg shadow-inner">{icon}</div>
                <div className="flex-1">
                    <p className="text-sm text-slate-400 font-bold uppercase tracking-wider">{title}</p>
                    <h3 className={`text-2xl font-black tracking-tight mt-1 ${colorClass}`}>{value}</h3>
                    {subValue && <p className="text-xs text-slate-500 mt-2 font-medium bg-slate-950 inline-block px-2 py-1 rounded">{subValue}</p>}
                </div>
            </div>
        </Card>
    );
}
"""

with open(ADMIN_TSX, "w", encoding="utf-8") as f:
    f.write(admin_code)
print("Replaced AdminDashboard.tsx with Live SCADA Dashboard")
print("✅ Patch applied successfully! Please restart your Flask and React servers to see changes.")
