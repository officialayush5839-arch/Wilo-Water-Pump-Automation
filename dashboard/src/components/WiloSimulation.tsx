import { useEffect, useMemo, useRef, useState } from "react";
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
  Calendar,
  Droplets,
  LoaderCircle,
  PartyPopper,
  Power,
  Settings,
  ShieldAlert,
  Zap,
} from "lucide-react";
import { useToast } from "@/hooks/use-toast";
import { useNavigate } from "react-router-dom";
import { WaterCutDialog, WaterCutStatus } from "./WaterCutDialog";
import { FestivalPolicyModal } from "./FestivalPolicyModal";

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
    ml_prediction?: {
      start_hour?: number;
      duration?: number;
    } | null;
    water_cut?: WaterCutStatus | null;
    current_classification?: {
      raw_amps?: number | null;
      filtered_amps?: number | null;
      state?: string;
      full_persisted?: boolean;
      full_persistence_seconds?: number;
      startup_blanking?: boolean;
      status_detail?: string;
    } | null;
    current_tank_state?: string;
  };
  water_cut?: WaterCutStatus | null;
  current_classification?: {
    raw_amps?: number | null;
    filtered_amps?: number | null;
    state?: string;
    full_persisted?: boolean;
    full_persistence_seconds?: number;
    startup_blanking?: boolean;
    status_detail?: string;
  } | null;
  auto_control?: {
    enabled?: boolean;
    action?: string;
    should_run?: boolean;
    reason?: string;
  };
  system_mode?: "auto" | "manual";
  telemetry?: {
    status?: string;
    timestamp?: string;
    pressure_kpa?: number | null;
    voltage?: number | null;
    mains_voltage?: number | null;
    mains_current?: number | null;
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
const DEFAULT_API_BASE_URL = "";

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
  const apiBaseUrl = useMemo(
    () => import.meta.env.VITE_API_BASE_URL ?? DEFAULT_API_BASE_URL,
    [],
  );

  const [controlMode, setControlMode] = useState<"auto" | "manual">("auto");
  const lastModeToggleAt = useRef(0);
  const MODE_SYNC_GRACE_MS = 5000;
  const [manualOverrideEnabled, setManualOverrideEnabled] = useState(true);
  const [backendReachable, setBackendReachable] = useState(false);
  const [backendError, setBackendError] = useState<string | null>(null);
  const [pumpMode, setPumpMode] = useState<PumpMode>("STANDBY");
  const [pumpMeta, setPumpMeta] = useState<PumpStatusPayload | null>(null);
  const [pressureKpa, setPressureKpa] = useState<number | null>(null);
  const [tankLevelPct, setTankLevelPct] = useState<number | null>(null);
  const [sensorVoltage, setSensorVoltage] = useState<number | null>(null);
  const [mainsVoltage, setMainsVoltage] = useState<number | null>(null);
  const [mainsCurrent, setMainsCurrent] = useState<number | null>(null);
  const [telemetryPacket, setTelemetryPacket] = useState<number | null>(null);
  const [pressureHistory, setPressureHistory] = useState<PressurePoint[]>([]);
  const [isBootstrapping, setIsBootstrapping] = useState(true);
  const [isCommandPending, setIsCommandPending] = useState(false);
  const [isWaterCutOpen, setIsWaterCutOpen] = useState(false);
  const [waterCutStatus, setWaterCutStatus] = useState<WaterCutStatus | null>(null);
  const [isFestivalModalOpen, setIsFestivalModalOpen] = useState(false);
  const [festivalStatus, setFestivalStatus] = useState<any | null>(null);
  const [currentClassification, setCurrentClassification] = useState<{
    raw_amps?: number | null;
    filtered_amps?: number | null;
    state?: string;
    full_persisted?: boolean;
    full_persistence_seconds?: number;
    startup_blanking?: boolean;
    status_detail?: string;
  } | null>(null);

  const [systemStatus, setSystemStatus] = useState({
    pumpStatus: "STANDBY",
    aiConfidence: "Auto",
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
  const [autoControl, setAutoControl] = useState({
    enabled: false,
    shouldRun: false,
    reason: "Waiting for backend status",
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
    const available = payload.manual_override_available !== false && payload.pump?.available !== false;
    // Manual relay commands are applied directly by the backend, while runtime
    // status can be stale if the main controller service is stopped.
    const decisionAction = (payload.runtime?.decision?.action ?? "").toUpperCase();
    const directRelayState =
      typeof payload.pump?.pump_relay_on === "boolean" ? payload.pump.pump_relay_on : null;
    const relayOn = available && directRelayState !== null ? directRelayState : decisionAction === "ON";
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
    const mlPrediction = payload.runtime?.ml_prediction;
    const mlStartHour = typeof mlPrediction?.start_hour === "number" ? mlPrediction.start_hour : null;
    const mlDuration = typeof mlPrediction?.duration === "number" ? mlPrediction.duration : null;

    const override = payload.runtime?.override ?? null;
    const backendMode = payload.system_mode ?? (override ? "manual" : "auto");
    const effectiveOverride = backendMode === "manual" ? override : null;
    const graceRemaining = Date.now() - lastModeToggleAt.current;
    if (graceRemaining > MODE_SYNC_GRACE_MS) {
      setControlMode(backendMode);
    }
    setAutoControl({
      enabled: payload.auto_control?.enabled === true,
      shouldRun: payload.auto_control?.should_run === true,
      reason: payload.auto_control?.reason ?? "No auto-control decision yet",
    });
    setBackendReachable(true);
    setBackendError(null);
    setManualOverrideEnabled(available);
    setPumpMeta(payload.pump ?? null);
    setPumpMode(relayOn ? "RUNNING" : "STANDBY");
    setPressureKpa(nextPressure);
    setTankLevelPct(payload.runtime?.upper_pct ?? null);
    setSensorVoltage(
      typeof payload.telemetry?.voltage === "number" ? payload.telemetry.voltage : null
    );
    setMainsVoltage(
      typeof payload.telemetry?.mains_voltage === "number" ? payload.telemetry.mains_voltage : null
    );
    setMainsCurrent(
      typeof payload.telemetry?.mains_current === "number" ? payload.telemetry.mains_current : null
    );
    setTelemetryPacket(
      typeof payload.telemetry?.packet === "number" ? payload.telemetry.packet : null
    );

    const wc = payload.water_cut || payload.runtime?.water_cut || null;
    if (wc) {
      setWaterCutStatus(wc);
    }
    const fp = (payload as any).festival_policy || (payload.runtime as any)?.festival_policy || null;
    if (fp) {
      setFestivalStatus(fp);
    }
    const cc = payload.current_classification || payload.runtime?.current_classification || null;
    if (cc) {
      setCurrentClassification(cc);
    }

    if (telemetryOk && nextPressure !== null) {
      setPressureHistory((current) => [
        ...current.slice(-(MAX_HISTORY_POINTS - 1)),
        {
          time: formatTimestamp(payload.telemetry?.timestamp ?? payload.timestamp),
          pressureKpa: nextPressure,
        },
      ]);
    }
    const controllerMode = payload.runtime?.controller_mode ?? null;
    const isDryRun = controllerMode === "dry-run";

    setSystemStatus({
      pumpStatus: relayOn ? "RUNNING" : "STANDBY",
      aiConfidence: mlStartHour !== null ? "ML Active" : available ? "Controller linked" : "Unavailable",
      sensorHealth: telemetryOk
        ? "Live telemetry"
        : telemetryStatus === "fault"
          ? "Sensor fault"
          : isDryRun
            ? "Dry-run mode"
            : "Telemetry waiting",
      uptime: controllerReason ?? "Live backend",
      networkStatus: "Backend Connected",
    });

    setAiPredictions({
      nextStart: relayOn
        ? "Running now"
        : effectiveOverride
          ? `Override ${effectiveOverride} (held by safety)`
          : mlStartHour !== null
            ? `${Math.floor(mlStartHour)}:${String(Math.round((mlStartHour % 1) * 60)).padStart(2, "0")}`
            : "Awaiting data",
      duration: mlDuration !== null
        ? `${Math.round(mlDuration)} min`
        : loraAgeSeconds !== null
          ? `Telemetry age ${Math.round(loraAgeSeconds)}s`
          : "Awaiting telemetry",
      dataSource: "Flask API",
      reliability: telemetryOk ? "High" : mlStartHour !== null ? "Medium" : "Low",
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

  const clearManualOverride = async () => {
    if (!manualOverrideEnabled) {
      toast({
        title: "Manual override unavailable",
        description: "The backend did not expose manual pump control.",
        variant: "destructive",
      });
      return;
    }

    setIsCommandPending(true);
    try {
      const response = await fetch(`${apiBaseUrl}/api/pump/clear-override`, {
        method: "POST",
        headers: {
          Accept: "application/json",
          "Content-Type": "application/json",
        },
        body: JSON.stringify({ source: "dashboard-ui" }),
      });

      const payload = (await response.json()) as
        | { ok?: boolean; message?: string; detail?: string; error?: string }
        | undefined;

      if (!response.ok || !payload?.ok) {
        throw new Error(payload?.detail || payload?.error || `command ${response.status}`);
      }

      appendEvent("Override cleared", "Controller resumed automated mode.");
      toast({
        title: "Manual override cleared",
        description: "Controller is back in automated mode.",
      });

      void loadDashboardStatus(false);
    } catch (error) {
      const message = error instanceof Error ? error.message : "command failed";
      appendEvent("Clear override failed", message);
      toast({
        title: "Clear override failed",
        description: message,
        variant: "destructive",
      });
    } finally {
      setIsCommandPending(false);
    }
  };

  const handleModeToggle = async (mode: "auto" | "manual") => {
    if (!backendReachable) {
      toast({
        title: "Backend unreachable",
        description: "Cannot switch modes while backend is offline.",
        variant: "destructive",
      });
      return;
    }

    setIsCommandPending(true);
    try {
      const response = await fetch(`${apiBaseUrl}/api/mode`, {
        method: "POST",
        headers: {
          Accept: "application/json",
          "Content-Type": "application/json",
        },
        body: JSON.stringify({ mode, source: "dashboard-ui" }),
      });

      const payload = (await response.json()) as { ok?: boolean; message?: string; error?: string } | undefined;

      if (!response.ok || !payload?.ok) {
        throw new Error(payload?.error || payload?.message || `mode switch ${response.status}`);
      }

      appendEvent(
        mode === "auto" ? "Auto mode engaged" : "Manual mode engaged",
        mode === "auto"
          ? "Controller resumed automatic operation — AI and tank levels in control."
          : "Operator assumed full authority — automation frozen.",
      );
      toast({
        title: mode === "auto" ? "Automatic mode" : "Manual mode",
        description: payload?.message ?? `Switched to ${mode} mode.`,
      });
      lastModeToggleAt.current = Date.now();
      setControlMode(mode);
    } catch (error) {
      const message = error instanceof Error ? error.message : "mode switch failed";
      appendEvent("Mode switch failed", message);
      toast({
        title: "Mode switch failed",
        description: message,
        variant: "destructive",
      });
    } finally {
      setIsCommandPending(false);
    }
  };

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
            <div className="absolute right-0 top-0 flex items-center gap-2">
              <Button
                onClick={() => setIsWaterCutOpen(true)}
                variant="secondary"
                size="sm"
                className="flex items-center gap-1.5 border-white/30 bg-blue-500/30 text-white hover:bg-blue-500/50 shadow-sm transition-all"
              >
                <Droplets className="h-4 w-4 text-cyan-200" />
                <span>Water Cut</span>
                {waterCutStatus?.is_cut_active ? (
                  <span className="ml-1 rounded-full bg-red-500 px-1.5 py-0.5 text-[9px] font-bold uppercase tracking-wider text-white animate-pulse">
                    CUT ACTIVE
                  </span>
                ) : waterCutStatus?.is_prefill_active ? (
                  <span className="ml-1 rounded-full bg-amber-400 px-1.5 py-0.5 text-[9px] font-bold uppercase tracking-wider text-slate-900">
                    PREFILL
                  </span>
                ) : null}
              </Button>
              <Button
                onClick={() => setIsFestivalModalOpen(true)}
                variant="secondary"
                size="sm"
                className="flex items-center gap-1.5 border-white/30 bg-white/20 text-white hover:bg-white/30 shadow-sm transition-all"
              >
                <Calendar className="h-4 w-4 text-cyan-100" />
                <span>Festivals</span>
                {festivalStatus?.restriction_active ? (
                  <span className="ml-1 rounded-full bg-red-500 px-1.5 py-0.5 text-[9px] font-bold uppercase tracking-wider text-white animate-pulse">
                    BLOCKED
                  </span>
                ) : festivalStatus?.is_rang_panchami ? (
                  <span className="ml-1 rounded-full bg-emerald-500 px-1.5 py-0.5 text-[9px] font-bold uppercase tracking-wider text-white">
                    RELEASED
                  </span>
                ) : null}
              </Button>
              <Button
                onClick={() => navigate("/admin")}
                variant="secondary"
                size="sm"
                className="flex items-center gap-2 border-white/30 bg-white/20 text-white hover:bg-white/30"
              >
                <Settings className="h-4 w-4" />
                Admin
              </Button>
            </div>
            <div className="text-center">
              <div className="mb-3 flex items-center justify-center gap-3">
                <h1 className="text-3xl font-bold">Wilo AI Water Transfer System</h1>
              </div>
              <div className="mt-2 flex items-center justify-center gap-4">
                <div className="inline-flex items-center rounded-full bg-white/10 p-1">
                  <button
                    onClick={() => handleModeToggle("auto")}
                    disabled={isCommandPending}
                    className={`rounded-full px-6 py-2 text-sm font-semibold transition-all ${
                      controlMode === "auto"
                        ? "bg-white text-green-800 shadow-lg"
                        : "text-white/70 hover:text-white"
                    } ${isCommandPending ? "cursor-not-allowed opacity-50" : ""}`}
                  >
                    AUTO
                  </button>
                  <button
                    onClick={() => handleModeToggle("manual")}
                    disabled={isCommandPending || !backendReachable}
                    className={`rounded-full px-6 py-2 text-sm font-semibold transition-all ${
                      controlMode === "manual"
                        ? "bg-amber-400 text-amber-900 shadow-lg"
                        : "text-white/70 hover:text-white"
                    } ${isCommandPending || !backendReachable ? "cursor-not-allowed opacity-50" : ""}`}
                  >
                    MANUAL
                  </button>
                </div>
                {controlMode === "auto" ? (
                  <span className="inline-flex items-center gap-1.5 rounded-full bg-green-500/20 px-4 py-1.5 text-xs font-semibold uppercase tracking-wider text-green-200">
                    <span className="h-2 w-2 rounded-full bg-green-400" />
                    Automatic
                  </span>
                ) : (
                  <span className="inline-flex items-center gap-1.5 rounded-full bg-amber-500/20 px-4 py-1.5 text-xs font-semibold uppercase tracking-wider text-amber-200">
                    <span className="h-2 w-2 rounded-full bg-amber-400" />
                    Manual
                  </span>
                )}
              </div>
              <div className="mt-3 text-base">
                <span className="rounded-full bg-white/20 px-4 py-2">
                  {controlMode === "auto"
                    ? "Automatic control — system manages pump based on tank levels"
                    : "Manual control — operator has direct pump authority"}
                </span>
              </div>
            </div>
          </div>
        </Card>

        {/* Municipal Water Cut Banner */}
        {waterCutStatus && (waterCutStatus.is_cut_active || waterCutStatus.is_prefill_active) && (
          <div className="mb-6">
            {waterCutStatus.is_cut_active ? (
              <Card className="p-4 bg-gradient-to-r from-amber-500/15 via-red-500/10 to-card border-amber-500/40 shadow-lg">
                <div className="flex items-center justify-between flex-wrap gap-4">
                  <div className="flex items-center gap-3">
                    <AlertTriangle className="h-6 w-6 text-amber-500 shrink-0 animate-pulse" />
                    <div>
                      <div className="flex items-center gap-2">
                        <h4 className="font-bold text-sm text-foreground">Municipal Water Cut In Progress</h4>
                        <span className="rounded-full bg-red-500 px-2 py-0.5 text-[10px] font-bold text-white uppercase">
                          Conserving Supply
                        </span>
                      </div>
                      <p className="text-xs text-muted-foreground mt-0.5">
                        {waterCutStatus.active_cut?.reason || "Municipal maintenance"} • Automation held to protect tank supply.
                      </p>
                    </div>
                  </div>
                  <Button size="sm" variant="outline" onClick={() => setIsWaterCutOpen(true)} className="text-xs border-amber-500/40">
                    Manage Schedule
                  </Button>
                </div>
              </Card>
            ) : (
              <Card className="p-4 bg-gradient-to-r from-blue-500/15 via-cyan-500/10 to-card border-blue-500/40 shadow-lg">
                <div className="flex items-center justify-between flex-wrap gap-4">
                  <div className="flex items-center gap-3">
                    <Droplets className="h-6 w-6 text-blue-500 shrink-0 animate-bounce" />
                    <div>
                      <div className="flex items-center gap-2">
                        <h4 className="font-bold text-sm text-foreground">Municipal Water Cut Pre-Fill Active</h4>
                        <span className="rounded-full bg-blue-600 px-2 py-0.5 text-[10px] font-bold text-white uppercase">
                          Target Reserve: {waterCutStatus.target_reserve_pct ?? 95}%
                        </span>
                      </div>
                      <p className="text-xs text-muted-foreground mt-0.5">
                        System is actively filling Master Tank before municipal outage.
                      </p>
                    </div>
                  </div>
                  <Button size="sm" variant="outline" onClick={() => setIsWaterCutOpen(true)} className="text-xs border-blue-500/40">
                    Manage Schedule
                  </Button>
                </div>
              </Card>
            )}
          </div>
        )}

        {/* Festival / Rang Panchami Alert Banner */}
        {festivalStatus && festivalStatus.mode_enabled && festivalStatus.restriction_active && (
          <div className="mb-6">
            <Card className="p-4 bg-amber-500/10 border-amber-500/30 text-amber-950 dark:text-amber-200 shadow-sm">
              <div className="flex items-center justify-between flex-wrap gap-4">
                <div className="flex items-center gap-3">
                  <div className="p-2 rounded-xl bg-amber-500/20 text-amber-600 animate-pulse">
                    <Calendar className="h-6 w-6" />
                  </div>
                  <div>
                    <div className="flex items-center gap-2">
                      <h4 className="font-bold text-sm text-foreground">
                        {festivalStatus.festival_name || "Rang Panchami"} — Automatic Start Blocked
                      </h4>
                      <span className="rounded-full bg-red-600 px-2 py-0.5 text-[10px] font-bold text-white uppercase">
                        Release: 07:00 PM IST ({festivalStatus.remaining_minutes ?? 0}m left)
                      </span>
                    </div>
                    <p className="text-xs text-muted-foreground mt-0.5">
                      {festivalStatus.reason || "Automatic pump starts restricted on Rang Panchami until 7 PM IST."}
                    </p>
                  </div>
                </div>
                <Button size="sm" variant="outline" onClick={() => setIsFestivalModalOpen(true)} className="text-xs border-amber-500/40 text-amber-900 dark:text-amber-100 hover:bg-amber-500/20">
                  Festival Policy Details
                </Button>
              </div>
            </Card>
          </div>
        )}

        <div className="mb-6 grid grid-cols-1 gap-6 lg:grid-cols-3">
          <Card className="border-border bg-card p-6">
            <div className="mb-4 flex items-center gap-3">
              <Activity className="h-6 w-6 text-primary" />
              <h3 className="text-lg font-semibold">System Health</h3>
            </div>
            <div className="space-y-3">
              <div>
                <div className="mb-1 flex justify-between text-sm items-center">
                  <span>Tank Level</span>
                  <span className="font-bold text-blue-400">{tankLevelPct !== null ? `${tankLevelPct.toFixed(1)}%` : "--"}</span>
                </div>
                <Progress value={tankLevelPct ?? 0} className="h-2 bg-slate-800 [&>div]:bg-blue-500" />
              </div>
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
                <span className="text-sm">Power Consumption</span>
                <span className="text-sm font-bold text-primary">
                  {mainsVoltage !== null ? `${Math.round(mainsVoltage)}V` : "--V"} @ {mainsCurrent !== null ? `${mainsCurrent.toFixed(2)}A` : "--A"}
                </span>
              </div>

              {/* Current-Based Tank Hydraulic Status */}
              <div className="rounded-xl border border-border bg-muted/20 p-3 space-y-2">
                <div className="flex items-center justify-between">
                  <span className="text-xs font-semibold uppercase tracking-wider text-muted-foreground">
                    Hydraulic Tank State
                  </span>
                  {currentClassification?.state === "FULL" ? (
                    <span className="rounded-md bg-green-500/20 px-2 py-0.5 text-xs font-bold text-green-600 dark:text-green-300 border border-green-500/40">
                      TANK FULL (≈6A)
                    </span>
                  ) : currentClassification?.state === "EMPTY" ? (
                    <span className="rounded-md bg-red-500/20 px-2 py-0.5 text-xs font-bold text-red-600 dark:text-red-300 border border-red-500/40 animate-pulse">
                      TANK EMPTY (≈12A)
                    </span>
                  ) : currentClassification?.state === "MID" ? (
                    <span className="rounded-md bg-blue-500/20 px-2 py-0.5 text-xs font-bold text-blue-600 dark:text-blue-300 border border-blue-500/40">
                      TANK ≈50% (≈9A)
                    </span>
                  ) : currentClassification?.state === "STARTING" ? (
                    <span className="rounded-md bg-purple-500/20 px-2 py-0.5 text-xs font-bold text-purple-600 dark:text-purple-300 border border-purple-500/40">
                      STARTING (5s)
                    </span>
                  ) : (
                    <span className="rounded-md bg-muted px-2 py-0.5 text-xs font-medium text-muted-foreground border border-border">
                      IDLE / UNKNOWN
                    </span>
                  )}
                </div>
                <div className="flex items-center justify-between text-[11px] text-muted-foreground">
                  <span>Filtered: {currentClassification?.filtered_amps !== null && currentClassification?.filtered_amps !== undefined ? `${currentClassification.filtered_amps.toFixed(2)} A` : mainsCurrent !== null ? `${mainsCurrent.toFixed(2)} A` : "--"}</span>
                  {currentClassification?.state === "FULL" && (
                    <span className="font-semibold text-green-600 dark:text-green-400">
                      Persistence: {currentClassification.full_persistence_seconds ?? 0}s / 5s
                    </span>
                  )}
                </div>
              </div>

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
                <span className="text-sm">System Mode</span>
                <div className="flex items-center gap-1.5">
                  <span
                    className={`h-2 w-2 rounded-full ${
                      controlMode === "auto" ? "bg-green-500" : "bg-amber-500"
                    }`}
                  />
                  <span className="text-sm font-medium">
                    {controlMode === "auto" ? "Auto" : "Manual"}
                  </span>
                </div>
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
              <h3 className="text-lg font-semibold">System Mode</h3>
            </div>
            <div className="text-center">
              <div
                className={`mx-auto mb-3 flex h-20 w-20 items-center justify-center rounded-full text-2xl font-bold ${
                  controlMode === "auto"
                    ? "bg-green-100 text-green-700"
                    : "bg-amber-100 text-amber-700"
                }`}
              >
                {controlMode === "auto" ? "AUTO" : "MAN"}
              </div>
              <p className="text-sm font-medium">
                {controlMode === "auto"
                  ? "System is in automatic control mode"
                  : "Operator has manual control authority"}
              </p>
              <p className="mt-1 text-xs text-muted-foreground">
                {backendReachable ? "Backend connected" : backendError ?? "Backend offline"}
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
            {controlMode === "auto" ? (
              <div className="py-6 text-center">
                <div className="mx-auto mb-4 flex h-16 w-16 items-center justify-center rounded-full bg-green-100">
                  <Zap className="h-8 w-8 text-green-600" />
                </div>
                <h2 className="mb-2 text-xl font-semibold text-foreground">
                  Automatic Mode Active
                </h2>
                <p className="mx-auto mb-6 max-w-md text-sm text-muted-foreground">
                  The system is controlling the pump based on tank levels and ML predictions.
                  Switch to manual mode for direct relay control.
                </p>
                <div className="mb-4 inline-flex items-center gap-2 rounded-full bg-green-50 px-4 py-2 text-sm text-green-700">
                  <span className="h-2 w-2 rounded-full bg-green-500" />
                  Controller managing pump automatically
                </div>
                <div className="mx-auto mb-6 grid max-w-xl grid-cols-1 gap-3 text-left sm:grid-cols-3">
                  <div className="rounded-xl border border-border bg-muted/40 p-4">
                    <p className="mb-1 text-xs font-semibold uppercase tracking-[0.18em] text-muted-foreground">
                      Predicted Start
                    </p>
                    <p className="text-xl font-bold text-foreground">{aiPredictions.nextStart}</p>
                  </div>
                  <div className="rounded-xl border border-border bg-muted/40 p-4">
                    <p className="mb-1 text-xs font-semibold uppercase tracking-[0.18em] text-muted-foreground">
                      Duration
                    </p>
                    <p className="text-xl font-bold text-foreground">{aiPredictions.duration}</p>
                  </div>
                  <div className="rounded-xl border border-border bg-muted/40 p-4">
                    <p className="mb-1 text-xs font-semibold uppercase tracking-[0.18em] text-muted-foreground">
                      Auto Decision
                    </p>
                    <p className="text-sm font-semibold text-foreground">
                      {autoControl.enabled
                        ? autoControl.shouldRun
                          ? "Relay should be ON"
                          : "Relay should be OFF"
                        : "Auto control inactive"}
                    </p>
                    <p className="mt-1 text-xs text-muted-foreground">{autoControl.reason}</p>
                  </div>
                </div>
                <div className="mt-4">
                  <Button
                    onClick={() => handleModeToggle("manual")}
                    disabled={!backendReachable || isCommandPending}
                    variant="outline"
                    className="gap-2"
                  >
                    <Power className="h-4 w-4" />
                    Switch to Manual Mode
                  </Button>
                </div>
              </div>
            ) : (
              <>
                <div className="mb-6 flex items-start justify-between gap-4">
                  <div>
                    <div className="mb-2 flex items-center gap-3">
                      <Power className="h-6 w-6 text-amber-500" />
                      <h2 className="text-xl font-semibold text-foreground">
                        Manual Pump Override
                      </h2>
                    </div>
                    <p className="text-sm text-muted-foreground">
                      Direct relay control — operator is in charge.
                    </p>
                  </div>
                  <div className="flex items-center gap-2 rounded-full border border-amber-200 bg-amber-50 px-3 py-1.5 text-xs font-semibold uppercase tracking-wider text-amber-700">
                    <span className="h-2 w-2 rounded-full bg-amber-500" />
                    Manual Override
                  </div>
                  {isCommandPending ? (
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
                        ? "Pump is running under manual override."
                        : "Pump is idle — operator command required."}
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
                  <Button
                    onClick={() => void handleModeToggle("auto")}
                    disabled={!manualOverrideEnabled || isCommandPending || !pumpMeta}
                    variant="ghost"
                    className="flex-1"
                  >
                    Clear Override
                  </Button>
                </div>
              </>
            )}
          </Card>

          <Card className="border-border bg-card p-6">
            <div className="mb-4 flex items-center gap-3">
              <Activity className="h-6 w-6 text-primary" />
              <h2 className="text-xl font-semibold text-foreground">Recent Actions</h2>
            </div>
            <div className="space-y-3">
              <div>
                <div className="mb-1 flex justify-between text-sm items-center">
                  <span>Tank Level</span>
                  <span className="font-bold text-blue-400">{tankLevelPct !== null ? `${tankLevelPct.toFixed(1)}%` : "--"}</span>
                </div>
                <Progress value={tankLevelPct ?? 0} className="h-2 bg-slate-800 [&>div]:bg-blue-500" />
              </div>
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

      <WaterCutDialog
        open={isWaterCutOpen}
        onOpenChange={setIsWaterCutOpen}
        apiBaseUrl={apiBaseUrl}
        currentTankLevel={tankLevelPct}
        onStatusUpdated={setWaterCutStatus}
      />

      <FestivalPolicyModal
        open={isFestivalModalOpen}
        onOpenChange={setIsFestivalModalOpen}
        onStateChange={() => { void loadDashboardStatus(false); }}
      />
    </div>
  );
}
