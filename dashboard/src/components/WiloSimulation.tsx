import { useEffect, useMemo, useState } from "react";
import { Button } from "@/components/ui/button";
import { Progress } from "@/components/ui/progress";
import { SystemDashboard } from "./SystemDashboard";
import { Card } from "@/components/ui/card";
import {
  Area,
  AreaChart,
  CartesianGrid,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";
import {
  Activity,
  AlertTriangle,
  LoaderCircle,
  Power,
  Settings,
  ShieldAlert,
  Zap,
} from "lucide-react";
import { useToast } from "@/hooks/use-toast";
import { useNavigate } from "react-router-dom";

type PumpMode = "STANDBY" | "RUNNING";

interface OperatorEvent {
  id: number;
  action: string;
  detail: string;
  timestamp: string;
}

interface PumpStatusPayload {
  available?: boolean;
  pump_relay_on?: boolean | null;
  timestamp?: string | null;
  relay_pin?: number | null;
  active_low?: boolean | null;
  gpio_level?: number | null;
  control_mode?: string | null;
  override?: string | null;
  error?: string | null;
}

interface DashboardStatusPayload {
  ok: boolean;
  manual_override_available?: boolean;
  manual_override_enabled?: boolean;
  pump?: PumpStatusPayload;
  runtime?: {
    upper_pct?: number | null;
    controller_mode?: string | null;
    decision?: {
      action?: string | null;
      reason?: string | null;
      state?: string | null;
    };
    override?: string | null;
    lora_age_s?: number | null;
  };
  telemetry?: {
    status?: string;
    timestamp?: string;
    pressure_kpa?: number | null;
    voltage?: number | null;
    packet?: number | null;
    upper_pct?: number | null;
    lora_age_s?: number | null;
  };
  timestamp?: string;
}

interface PressurePoint {
  time: string;
  pressureKpa: number;
}

const DASHBOARD_POLL_MS = 3000;
const MAX_HISTORY_POINTS = 20;

const formatTimestamp = (value?: string | null) => {
  if (!value) {
    return new Date().toLocaleTimeString([], {
      hour: "2-digit",
      minute: "2-digit",
    });
  }

  const parsed = new Date(value);
  if (Number.isNaN(parsed.getTime())) {
    return value;
  }

  return parsed.toLocaleTimeString([], {
    hour: "2-digit",
    minute: "2-digit",
  });
};

export function WiloSimulation() {
  const { toast } = useToast();
  const navigate = useNavigate();
  const apiBaseUrl = useMemo(() => import.meta.env.VITE_API_BASE_URL ?? "", []);

  const [manualOverrideEnabled, setManualOverrideEnabled] = useState(true);
  const [backendReachable, setBackendReachable] = useState(false);
  const [backendError, setBackendError] = useState<string | null>(null);
  const [pumpMode, setPumpMode] = useState<PumpMode>("STANDBY");
  const [pumpMeta, setPumpMeta] = useState<PumpStatusPayload | null>(null);
  const [pressureKpa, setPressureKpa] = useState<number | null>(null);
  const [sensorVoltage, setSensorVoltage] = useState<number | null>(null);
  const [telemetryPacket, setTelemetryPacket] = useState<number | null>(null);
  const [pressureHistory, setPressureHistory] = useState<PressurePoint[]>([]);
  const [isBootstrapping, setIsBootstrapping] = useState(true);
  const [isCommandPending, setIsCommandPending] = useState(false);
  const [systemStatus, setSystemStatus] = useState({
    pumpStatus: "STANDBY",
    aiConfidence: "Manual",
    sensorHealth: "7/7 Active",
    uptime: "Live backend",
    networkStatus: "Disconnected",
  });
  const [aiPredictions, setAiPredictions] = useState({
    nextStart: "Manual override",
    duration: "Operator controlled",
    dataSource: "Flask API",
    reliability: "High",
  });
  const [operatorEvents, setOperatorEvents] = useState<OperatorEvent[]>([
    {
      id: 1,
      action: "Dashboard ready",
      detail: "Waiting for Flask backend status.",
      timestamp: formatTimestamp(),
    },
  ]);

  const appendEvent = (action: string, detail: string, timestamp?: string | null) => {
    setOperatorEvents((current) => [
      {
        id: Date.now() + Math.floor(Math.random() * 1000),
        action,
        detail,
        timestamp: formatTimestamp(timestamp),
      },
      ...current,
    ]);
  };

  const formatMetric = (value: number | null, digits: number) => {
    if (value === null || Number.isNaN(value)) {
      return "--";
    }
    return value.toFixed(digits);
  };

  const applyDashboardStatus = (payload: DashboardStatusPayload) => {
    const relayOn = payload.pump?.pump_relay_on === true;
    const available = payload.manual_override_available !== false && payload.pump?.available !== false;
    const telemetryStatus = payload.telemetry?.status ?? "waiting";
    const telemetryOk = telemetryStatus === "ok";
    const nextPressure =
      typeof payload.telemetry?.pressure_kpa === "number" ? payload.telemetry.pressure_kpa : null;
    const loraAgeSeconds =
      typeof payload.runtime?.lora_age_s === "number"
        ? payload.runtime.lora_age_s
        : typeof payload.telemetry?.lora_age_s === "number"
          ? payload.telemetry.lora_age_s
          : null;
    const controllerReason = payload.runtime?.decision?.reason ?? null;

    setBackendReachable(true);
    setBackendError(null);
    setManualOverrideEnabled(available);
    setPumpMeta(payload.pump ?? null);
    setPumpMode(relayOn ? "RUNNING" : "STANDBY");
    setPressureKpa(nextPressure);
    setSensorVoltage(
      typeof payload.telemetry?.voltage === "number" ? payload.telemetry.voltage : null
    );
    setTelemetryPacket(
      typeof payload.telemetry?.packet === "number" ? payload.telemetry.packet : null
    );
    if (telemetryOk && nextPressure !== null) {
      setPressureHistory((current) => [
        ...current.slice(-(MAX_HISTORY_POINTS - 1)),
        {
          time: formatTimestamp(payload.telemetry?.timestamp ?? payload.timestamp),
          pressureKpa: nextPressure,
        },
      ]);
    }
    setSystemStatus({
      pumpStatus: relayOn ? "RUNNING" : "STANDBY",
      aiConfidence: available ? "Controller linked" : "Unavailable",
      sensorHealth: telemetryOk
        ? "Live telemetry"
        : telemetryStatus === "fault"
          ? "Sensor fault"
          : "Telemetry waiting",
      uptime: controllerReason ?? "Live backend",
      networkStatus: "Backend Connected",
    });
    setAiPredictions({
      nextStart: relayOn
        ? "Running now"
        : payload.runtime?.override
          ? `Override ${payload.runtime.override}`
          : available
            ? "Awaiting operator"
            : "Backend unavailable",
      duration: loraAgeSeconds !== null ? `Telemetry age ${Math.round(loraAgeSeconds)}s` : "Awaiting telemetry",
      dataSource: payload.runtime?.controller_mode ?? "Flask API",
      reliability: telemetryOk ? "High" : "Medium",
    });
  };

  const loadDashboardStatus = async (announceFailure: boolean) => {
    try {
      const response = await fetch(`${apiBaseUrl}/api/dashboard/status`, {
        headers: { Accept: "application/json" },
      });

      if (!response.ok) {
        throw new Error(`status ${response.status}`);
      }

      const payload = (await response.json()) as DashboardStatusPayload;
      applyDashboardStatus(payload);
      return true;
    } catch (error) {
      const message = error instanceof Error ? error.message : "status request failed";
      setBackendReachable(false);
      setBackendError(message);
      setManualOverrideEnabled(false);
      setSystemStatus((current) => ({
        ...current,
        aiConfidence: "Unavailable",
        sensorHealth: "Backend offline",
        networkStatus: "Backend Offline",
      }));
      setAiPredictions((current) => ({
        ...current,
        nextStart: "Backend offline",
        duration: "No backend link",
        reliability: "Conservative",
      }));

      if (announceFailure) {
        appendEvent("Backend unavailable", `Unable to load Flask API status: ${message}`);
      }

      return false;
    } finally {
      setIsBootstrapping(false);
    }
  };

  useEffect(() => {
    let active = true;

    const bootstrap = async () => {
      const ok = await loadDashboardStatus(true);
      if (ok && active) {
        appendEvent("Backend connected", "Dashboard synced with Flask control API.");
      }
    };

    void bootstrap();

    const interval = window.setInterval(() => {
      void loadDashboardStatus(false);
    }, DASHBOARD_POLL_MS);

    return () => {
      active = false;
      window.clearInterval(interval);
    };
  }, [apiBaseUrl]);

  const sendPumpCommand = async (nextMode: PumpMode) => {
    if (!manualOverrideEnabled) {
      toast({
        title: "Manual override unavailable",
        description: "The backend did not expose manual pump control.",
        variant: "destructive",
      });
      return;
    }

    const endpoint = nextMode === "RUNNING" ? "/api/pump/on" : "/api/pump/off";
    const actionLabel = nextMode === "RUNNING" ? "Pump started" : "Pump stopped";
    const detail =
      nextMode === "RUNNING"
        ? "Manual override turned the transfer pump on."
        : "Manual override turned the transfer pump off.";

    setIsCommandPending(true);

    try {
      const response = await fetch(`${apiBaseUrl}${endpoint}`, {
        method: "POST",
        headers: {
          Accept: "application/json",
          "Content-Type": "application/json",
        },
        body: JSON.stringify({ source: "dashboard-ui" }),
      });

      const payload = (await response.json()) as
        | {
            ok?: boolean;
            pump?: PumpStatusPayload;
            runtime?: DashboardStatusPayload["runtime"];
            detail?: string;
            error?: string;
          }
        | undefined;

      if (!response.ok || !payload?.ok) {
        throw new Error(payload?.detail || payload?.error || `command ${response.status}`);
      }

      appendEvent(actionLabel, detail, payload.pump?.timestamp);
      toast({
        title: actionLabel,
        description: "Controller override command queued on the Pi.",
      });

      void loadDashboardStatus(false);
    } catch (error) {
      const message = error instanceof Error ? error.message : "command failed";
      appendEvent("Command failed", message);
      toast({
        title: "Pump command failed",
        description: message,
        variant: "destructive",
      });
    } finally {
      setIsCommandPending(false);
    }
  };

  const pumpRunning = pumpMode === "RUNNING";

  return (
    <div className="min-h-screen bg-background text-foreground">
      <div className="container mx-auto max-w-7xl px-4 py-4">
        <Card className="mb-6 border-0 bg-gradient-primary p-6 text-white shadow-xl">
          <div className="relative">
            <Button
              onClick={() => navigate("/admin")}
              variant="secondary"
              size="sm"
              className="absolute right-0 top-0 flex items-center gap-2 border-white/30 bg-white/20 text-white hover:bg-white/30"
            >
              <Settings className="h-4 w-4" />
              Admin
            </Button>
            <div className="text-center">
              <div className="mb-3 flex items-center justify-center gap-3">
                <h1 className="text-3xl font-bold">Wilo AI Water Transfer System</h1>
              </div>
              <div className="mt-3 text-base">
                <span className="rounded-full bg-white/20 px-4 py-2">
                  Live dashboard with Flask-backed manual pump control
                </span>
              </div>
            </div>
          </div>
        </Card>

        <div className="mb-6 grid grid-cols-1 gap-6 lg:grid-cols-3">
          <Card className="border-border bg-card p-6">
            <div className="mb-4 flex items-center gap-3">
              <Activity className="h-6 w-6 text-primary" />
              <h3 className="text-lg font-semibold">System Health</h3>
            </div>
            <div className="space-y-3">
              <div>
                <div className="mb-1 flex justify-between text-sm">
                  <span>Water Pressure</span>
                  <span>{pressureKpa !== null ? `${formatMetric(pressureKpa, 2)} kPa` : "--"}</span>
                </div>
                <Progress value={backendReachable ? 100 : 35} className="h-2" />
              </div>
              <div>
                <div className="mb-1 flex justify-between text-sm">
                  <span>Manual Override</span>
                  <span>{manualOverrideEnabled ? "Enabled" : "Unavailable"}</span>
                </div>
                <Progress value={manualOverrideEnabled ? 100 : 0} className="h-2" />
              </div>
              <div>
                <div className="mb-1 flex justify-between text-sm">
                  <span>Latest Packet</span>
                  <span>{telemetryPacket !== null ? `#${telemetryPacket}` : "--"}</span>
                </div>
                <Progress value={telemetryPacket !== null ? 100 : 0} className="h-2" />
              </div>
            </div>
          </Card>

          <Card className="border-border bg-card p-6">
            <div className="mb-4 flex items-center gap-3">
              <Zap className="h-6 w-6 text-primary" />
              <h3 className="text-lg font-semibold">Pump State</h3>
            </div>
            <div className="space-y-4">
              <div className="flex items-center justify-between">
                <span className="text-sm">Current Pump Status</span>
                <div className="flex items-center gap-2">
                  <div
                    className={`h-3 w-3 rounded-full ${
                      pumpRunning ? "animate-pulse bg-green-500" : "bg-gray-400"
                    }`}
                  />
                  <span className="text-sm font-medium">{systemStatus.pumpStatus}</span>
                </div>
              </div>
              <div className="flex items-center justify-between">
                <span className="text-sm">Control Source</span>
                <span className="text-sm font-medium">
                  {manualOverrideEnabled ? "Flask manual API" : "Unavailable"}
                  {pumpMeta?.control_mode ? ` (${pumpMeta.control_mode})` : ""}
                </span>
              </div>
              <div className="flex items-center justify-between">
                <span className="text-sm">Network</span>
                <span className="text-sm font-medium">{systemStatus.networkStatus}</span>
              </div>
              <div className="flex items-center justify-between">
                <span className="text-sm">LoRa Packet</span>
                <span className="text-sm font-medium">
                  {telemetryPacket !== null ? `#${telemetryPacket}` : "--"}
                </span>
              </div>
            </div>
          </Card>

          <Card className="border-border bg-card p-6">
            <div className="mb-4 flex items-center gap-3">
              <AlertTriangle className="h-6 w-6 text-primary" />
              <h3 className="text-lg font-semibold">Operator Status</h3>
            </div>
            <div className="text-center">
              <div
                className={`mx-auto mb-3 flex h-20 w-20 items-center justify-center rounded-full text-2xl font-bold ${
                  manualOverrideEnabled
                    ? "bg-amber-100 text-amber-700"
                    : "bg-red-100 text-red-700"
                }`}
              >
                {manualOverrideEnabled ? "MAN" : "ERR"}
              </div>
              <p className="text-sm font-medium">
                {manualOverrideEnabled
                  ? "Manual override endpoint is available"
                  : backendError ?? "Manual override endpoint is not available"}
              </p>
            </div>
          </Card>
        </div>

        <SystemDashboard systemStatus={systemStatus} aiPredictions={aiPredictions} />

        <div className="mb-6">
          <Card className="border-border bg-card p-6">
            <div className="mb-6 flex items-start justify-between gap-4">
              <div>
                <div className="mb-2 flex items-center gap-3">
                  <Activity className="h-6 w-6 text-primary" />
                  <h2 className="text-xl font-semibold text-foreground">
                    Pressure Trend
                  </h2>
                </div>
                <p className="text-sm text-muted-foreground">
                  Live upper-tank pressure history sampled every 3 seconds from the Pi backend.
                </p>
              </div>
              <div className="rounded-lg border border-border bg-muted/30 px-4 py-2 text-right">
                <p className="text-xs uppercase tracking-[0.18em] text-muted-foreground">
                  Current pressure
                </p>
                <p className="text-xl font-semibold text-foreground">
                  {pressureKpa !== null ? `${formatMetric(pressureKpa, 2)} kPa` : "--"}
                </p>
              </div>
            </div>

            <div className="h-72 w-full">
              <ResponsiveContainer width="100%" height="100%">
                <AreaChart data={pressureHistory}>
                  <defs>
                    <linearGradient id="pressureFill" x1="0" y1="0" x2="0" y2="1">
                      <stop offset="5%" stopColor="#0ea5e9" stopOpacity={0.45} />
                      <stop offset="95%" stopColor="#0ea5e9" stopOpacity={0.05} />
                    </linearGradient>
                  </defs>
                  <CartesianGrid strokeDasharray="3 3" stroke="#dbe4ea" />
                  <XAxis dataKey="time" tick={{ fontSize: 12 }} minTickGap={24} />
                  <YAxis
                    yAxisId="pressure"
                    domain={[0, 100]}
                    tick={{ fontSize: 12 }}
                    tickFormatter={(value) => `${value}kPa`}
                  />
                  <Tooltip
                    formatter={(value: number) => [`${value.toFixed(2)} kPa`, "Pressure"]}
                  />
                  <Area
                    yAxisId="pressure"
                    type="monotone"
                    dataKey="pressureKpa"
                    name="Pressure"
                    stroke="#0284c7"
                    fill="url(#pressureFill)"
                    strokeWidth={3}
                  />
                </AreaChart>
              </ResponsiveContainer>
            </div>
          </Card>
        </div>

        <div className="grid grid-cols-1 gap-6 lg:grid-cols-[1.2fr_0.8fr]">
          <Card className="border-border bg-card p-6">
            <div className="mb-6 flex items-start justify-between gap-4">
              <div>
                <div className="mb-2 flex items-center gap-3">
                  <Power className="h-6 w-6 text-primary" />
                  <h2 className="text-xl font-semibold text-foreground">
                    Manual Pump Override
                  </h2>
                </div>
                <p className="text-sm text-muted-foreground">
                  Start or stop the pump directly through the Flask control API.
                </p>
              </div>
              {isBootstrapping || isCommandPending ? (
                <div className="flex min-w-40 items-center justify-center gap-2 rounded-lg border border-border px-4 py-2 text-sm text-muted-foreground">
                  <LoaderCircle className="h-4 w-4 animate-spin" />
                  Syncing
                </div>
              ) : null}
            </div>

            <div className="mb-6 grid grid-cols-1 gap-4 md:grid-cols-2">
              <div className="rounded-xl border border-border bg-muted/40 p-4">
                <p className="mb-2 text-xs font-semibold uppercase tracking-[0.2em] text-muted-foreground">
                  Command State
                </p>
                <p className="text-2xl font-bold text-foreground">{pumpMode}</p>
                <p className="mt-2 text-sm text-muted-foreground">
                  {pumpRunning
                    ? "Pump is currently running under controller supervision."
                    : "Pump is idle and waiting for a controller decision or operator command."}
                </p>
              </div>
              <div className="rounded-xl border border-border bg-muted/40 p-4">
                <p className="mb-2 text-xs font-semibold uppercase tracking-[0.2em] text-muted-foreground">
                  Water pressure
                </p>
                <div className="flex items-center gap-2 text-sm font-medium text-foreground">
                  <ShieldAlert className="h-4 w-4 text-primary" />
                  {pressureKpa !== null
                    ? `${formatMetric(pressureKpa, 2)} kPa at ${formatMetric(sensorVoltage, 3)} V`
                    : manualOverrideEnabled
                      ? "Waiting for a valid LoRa reading from the Pi controller."
                      : "Backend manual override is not available on this host."}
                </div>
              </div>
            </div>

            <div className="flex flex-col gap-3 sm:flex-row">
              <Button
                onClick={() => void sendPumpCommand("RUNNING")}
                disabled={!manualOverrideEnabled || pumpRunning || isCommandPending}
                className="flex-1"
              >
                Turn Pump On
              </Button>
              <Button
                onClick={() => void sendPumpCommand("STANDBY")}
                disabled={!manualOverrideEnabled || !pumpRunning || isCommandPending}
                variant="outline"
                className="flex-1"
              >
                Turn Pump Off
              </Button>
            </div>
          </Card>

          <Card className="border-border bg-card p-6">
            <div className="mb-4 flex items-center gap-3">
              <Activity className="h-6 w-6 text-primary" />
              <h2 className="text-xl font-semibold text-foreground">Recent Actions</h2>
            </div>
            <div className="space-y-3">
              {operatorEvents.slice(0, 5).map((event) => (
                <div key={event.id} className="rounded-xl border border-border bg-muted/30 p-4">
                  <div className="mb-1 flex items-center justify-between gap-3">
                    <p className="font-medium text-foreground">{event.action}</p>
                    <span className="text-xs text-muted-foreground">{event.timestamp}</span>
                  </div>
                  <p className="text-sm text-muted-foreground">{event.detail}</p>
                </div>
              ))}
            </div>
          </Card>
        </div>
      </div>
    </div>
  );
}
