"use client";

import { useEffect, useMemo, useState } from "react";

type RuntimeDecision = {
  action?: string | null;
  reason?: string | null;
  state?: string | null;
  ts?: string | null;
};

type RuntimePayload = {
  connected?: boolean;
  controller_mode?: string;
  current_amps?: number | null;
  decision?: RuntimeDecision;
  host?: string;
  lora_age_s?: number | null;
  lora_pkt?: number | null;
  lora_rssi?: number | null;
  lora_snr?: number | null;
  ml_prediction?: {
    start_hour?: number;
    duration?: number;
  } | null;
  override?: string | null;
  packet?: number | null;
  pressure_kpa?: number | null;
  pump_relay_on?: boolean | null;
  sensor_status?: string | null;
  sensor_voltage?: number | null;
  timestamp?: string | null;
  upper_pct?: number | null;
  voltage_ac?: number | null;
  main_pct?: number | null;
};

type DashboardState = {
  connected: boolean;
  controllerMode: string;
  currentAmps: number | null;
  decision: RuntimeDecision;
  host: string;
  loraAgeS: number | null;
  loraPkt: number | null;
  loraRssi: number | null;
  loraSnr: number | null;
  mlPrediction: { start_hour?: number; duration?: number } | null;
  override: string | null;
  pressureKpa: number | null;
  pumpRelayOn: boolean;
  sensorStatus: string;
  sensorVoltage: number | null;
  timestamp: string | null;
  upperPct: number | null;
  voltageAc: number | null;
  mainPct: number | null;
  live: boolean;
};

const initialState: DashboardState = {
  connected: false,
  controllerMode: "website-demo",
  currentAmps: 4.8,
  decision: {
    action: "HOLD",
    reason: "Awaiting controller runtime feed",
    state: "BOOT",
    ts: null,
  },
  host: "wilo-rpi",
  loraAgeS: 5.2,
  loraPkt: 182,
  loraRssi: -74,
  loraSnr: 8.4,
  mlPrediction: {
    start_hour: 6,
    duration: 42,
  },
  override: null,
  pressureKpa: 18.2,
  pumpRelayOn: false,
  sensorStatus: "ok",
  sensorVoltage: 1.228,
  timestamp: null,
  upperPct: 61,
  voltageAc: 229.4,
  mainPct: 74,
  live: false,
};

const FALLBACK_INTERVAL_MS = 2400;

function clamp(value: number, min: number, max: number) {
  return Math.min(max, Math.max(min, value));
}

function formatNumber(value: number | null | undefined, digits = 1) {
  if (typeof value !== "number" || Number.isNaN(value)) {
    return "--";
  }
  return value.toFixed(digits);
}

function formatPct(value: number | null | undefined) {
  if (typeof value !== "number" || Number.isNaN(value)) {
    return "--";
  }
  return `${Math.round(value)}%`;
}

function formatPrediction(prediction: DashboardState["mlPrediction"]) {
  if (!prediction?.start_hour || !prediction?.duration) {
    return "Not loaded";
  }
  const hh = Math.floor(prediction.start_hour);
  const mm = Math.round((prediction.start_hour - hh) * 60)
    .toString()
    .padStart(2, "0");
  return `${hh.toString().padStart(2, "0")}:${mm} / ${Math.round(prediction.duration)} min`;
}

function withPayload(prev: DashboardState, payload: RuntimePayload): DashboardState {
  return {
    connected: payload.connected ?? prev.connected,
    controllerMode: payload.controller_mode ?? prev.controllerMode,
    currentAmps:
      typeof payload.current_amps === "number" ? payload.current_amps : prev.currentAmps,
    decision: payload.decision ?? prev.decision,
    host: payload.host ?? prev.host,
    loraAgeS: typeof payload.lora_age_s === "number" ? payload.lora_age_s : prev.loraAgeS,
    loraPkt:
      typeof payload.lora_pkt === "number"
        ? payload.lora_pkt
        : typeof payload.packet === "number"
          ? payload.packet
          : prev.loraPkt,
    loraRssi: typeof payload.lora_rssi === "number" ? payload.lora_rssi : prev.loraRssi,
    loraSnr: typeof payload.lora_snr === "number" ? payload.lora_snr : prev.loraSnr,
    mlPrediction: payload.ml_prediction ?? prev.mlPrediction,
    override: payload.override ?? prev.override,
    pressureKpa:
      typeof payload.pressure_kpa === "number" ? payload.pressure_kpa : prev.pressureKpa,
    pumpRelayOn: payload.pump_relay_on ?? prev.pumpRelayOn,
    sensorStatus: payload.sensor_status ?? prev.sensorStatus,
    sensorVoltage:
      typeof payload.sensor_voltage === "number" ? payload.sensor_voltage : prev.sensorVoltage,
    timestamp: payload.timestamp ?? prev.timestamp,
    upperPct: typeof payload.upper_pct === "number" ? payload.upper_pct : prev.upperPct,
    voltageAc: typeof payload.voltage_ac === "number" ? payload.voltage_ac : prev.voltageAc,
    mainPct: typeof payload.main_pct === "number" ? payload.main_pct : prev.mainPct,
    live: true,
  };
}

function fallbackTick(prev: DashboardState): DashboardState {
  const nextUpper = clamp((prev.upperPct ?? 60) + (Math.random() - 0.52) * 3.2, 18, 88);
  const nextMain = clamp((prev.mainPct ?? 72) + (Math.random() - 0.48) * 2.4, 22, 93);
  const pressureKpa = nextUpper * 0.32;
  const sensorVoltage = 0.5 + (pressureKpa / 100) * 4;
  const pumpRelayOn = nextUpper < 33 ? true : nextUpper > 81 ? false : prev.pumpRelayOn;

  return {
    ...prev,
    connected: true,
    controllerMode: "website-demo",
    currentAmps: pumpRelayOn
      ? clamp((prev.currentAmps ?? 4.8) + (Math.random() - 0.5) * 0.7, 3.6, 7.6)
      : 0,
    decision: {
      action: pumpRelayOn ? "ON" : "HOLD",
      reason: pumpRelayOn
        ? "Upper tank below refill band; simulated threshold response"
        : "Tank inside stable band; simulated hold state",
      state: pumpRelayOn ? "ON_THRESHOLD" : "OFF",
      ts: new Date().toISOString(),
    },
    loraAgeS: clamp((prev.loraAgeS ?? 4) + (Math.random() - 0.45) * 1.4, 0.8, 8.4),
    loraPkt: (prev.loraPkt ?? 180) + 1,
    loraRssi: clamp((prev.loraRssi ?? -74) + (Math.random() - 0.5) * 3, -92, -56),
    loraSnr: clamp((prev.loraSnr ?? 8.4) + (Math.random() - 0.5) * 1.8, 4.2, 11.6),
    pressureKpa,
    pumpRelayOn,
    sensorStatus: "ok",
    sensorVoltage,
    timestamp: new Date().toISOString(),
    upperPct: nextUpper,
    voltageAc: clamp((prev.voltageAc ?? 229) + (Math.random() - 0.5) * 4.2, 218, 238),
    mainPct: nextMain,
    live: false,
  };
}

function statusTone(sensorStatus: string, live: boolean) {
  if (sensorStatus === "fault") {
    return "bg-[#d8653b]";
  }
  if (live) {
    return "bg-[var(--wilo-green)]";
  }
  return "bg-[#c7d654]";
}

function levelTone(percent: number | null | undefined) {
  if (typeof percent !== "number") {
    return "bg-slate-300";
  }
  if (percent < 25) {
    return "bg-[#d56f3f]";
  }
  if (percent < 60) {
    return "bg-[#c7d654]";
  }
  return "bg-[var(--wilo-green)]";
}

function StatCard({
  label,
  value,
  note,
}: {
  label: string;
  value: string;
  note: string;
}) {
  return (
    <article className="metric-card">
      <div className="font-mono text-[0.68rem] uppercase tracking-[0.22em] text-[var(--wilo-muted)]">
        {label}
      </div>
      <div className="mt-3 text-[1.9rem] font-semibold tracking-[-0.05em] text-[var(--wilo-ink)] sm:text-[2.15rem]">
        {value}
      </div>
      <div className="mt-2 text-sm text-[var(--wilo-muted)]">{note}</div>
    </article>
  );
}

function InfoCard({
  label,
  value,
  note,
}: {
  label: string;
  value: string;
  note?: string;
}) {
  return (
    <div className="rounded-2xl border border-[var(--wilo-border)] bg-[#f9fbf6] px-4 py-4">
      <div className="font-mono text-[0.68rem] uppercase tracking-[0.18em] text-[var(--wilo-muted)]">
        {label}
      </div>
      <div className="mt-2 text-lg font-semibold tracking-[-0.03em] text-[var(--wilo-ink)]">
        {value}
      </div>
      {note ? <div className="mt-1 text-xs text-[var(--wilo-muted)]">{note}</div> : null}
    </div>
  );
}

function TankCard({
  title,
  subtitle,
  percent,
  badge,
  metrics,
}: {
  title: string;
  subtitle: string;
  percent: number | null;
  badge: string;
  metrics: Array<{ label: string; value: string; note?: string }>;
}) {
  return (
    <article className="rounded-[1.5rem] border border-[var(--wilo-border)] bg-[#fbfdf9] p-4 sm:p-5">
      <div className="flex items-start justify-between gap-3">
        <div>
          <p className="eyebrow">{title}</p>
          <h3 className="mt-1 text-xl font-semibold text-[var(--wilo-ink)]">{subtitle}</h3>
        </div>
        <span className="font-mono text-[0.68rem] uppercase tracking-[0.18em] text-[var(--wilo-muted)]">
          {badge}
        </span>
      </div>

      <div className="mt-5 rounded-2xl border border-[var(--wilo-border)] bg-white p-4">
        <div className="flex items-center justify-between gap-3">
          <span className="text-sm text-[var(--wilo-muted)]">Level</span>
          <strong className="text-2xl tracking-[-0.05em] text-[var(--wilo-ink)]">
            {formatPct(percent)}
          </strong>
        </div>
        <div className="mt-4 h-4 overflow-hidden rounded-full bg-[#e8efe1]">
          <div
            className={`h-full rounded-full ${levelTone(percent)} transition-all duration-700`}
            style={{ width: `${clamp(percent ?? 0, 0, 100)}%` }}
          />
        </div>
      </div>

      <div className="mt-4 grid gap-3 sm:grid-cols-2">
        {metrics.map((metric) => (
          <InfoCard
            key={metric.label}
            label={metric.label}
            note={metric.note}
            value={metric.value}
          />
        ))}
      </div>
    </article>
  );
}

export function SystemDashboard() {
  const [state, setState] = useState<DashboardState>(initialState);
  const [events, setEvents] = useState<string[]>(["[boot] operator dashboard ready"]);
  const baseUrl = useMemo(() => process.env.NEXT_PUBLIC_TELEMETRY_BASE_URL ?? "", []);

  useEffect(() => {
    const addEvent = (entry: string) => {
      setEvents((current) => [entry, ...current].slice(0, 7));
    };

    let closed = false;
    const fallback = window.setInterval(() => {
      setState((current) => fallbackTick(current));
    }, FALLBACK_INTERVAL_MS);

    fetch(`${baseUrl}/latest`, {
      headers: { Accept: "application/json" },
      cache: "no-store",
    })
      .then(async (response) => {
        if (!response.ok) {
          throw new Error(`latest ${response.status}`);
        }
        return response.json() as Promise<RuntimePayload>;
      })
      .then((payload) => {
        if (closed) {
          return;
        }
        setState((current) => withPayload(current, payload));
        addEvent("[latest] controller payload loaded");
      })
      .catch(() => {
        addEvent("[fallback] no live latest endpoint detected");
      });

    let source: EventSource | null = null;
    try {
      source = new EventSource(`${baseUrl}/stream`);
      source.onmessage = (event) => {
        try {
          const payload = JSON.parse(event.data) as RuntimePayload;
          setState((current) => withPayload(current, payload));
          addEvent(
            `[stream] pkt ${payload.lora_pkt ?? payload.packet ?? "--"} | upper ${typeof payload.upper_pct === "number" ? Math.round(payload.upper_pct) : "--"}%`,
          );
        } catch {
          // Ignore malformed stream data.
        }
      };
      source.onerror = () => {
        addEvent("[stream] connection dropped; holding last payload");
        source?.close();
      };
    } catch {
      addEvent("[fallback] EventSource unavailable");
    }

    return () => {
      closed = true;
      window.clearInterval(fallback);
      source?.close();
    };
  }, [baseUrl]);

  return (
    <div className="grid gap-6">
      <section className="grid gap-4 sm:grid-cols-2 xl:grid-cols-4">
        <StatCard label="Upper tank" note="Slave tank via LoRa" value={formatPct(state.upperPct)} />
        <StatCard label="Main tank" note="Pump room estimate" value={formatPct(state.mainPct)} />
        <StatCard
          label="Pump"
          note={state.decision.state ?? "No state"}
          value={state.pumpRelayOn ? "Running" : "Stopped"}
        />
        <StatCard
          label="LoRa"
          note={`Age ${formatNumber(state.loraAgeS, 1)} s`}
          value={state.loraPkt !== null ? `#${state.loraPkt}` : "--"}
        />
      </section>

      <section className="grid gap-6 xl:grid-cols-[minmax(0,1.55fr)_minmax(300px,0.95fr)]">
        <div className="grid gap-6">
          <article className="glass-card p-4 sm:p-5 lg:p-6">
            <div className="flex flex-col gap-3 lg:flex-row lg:items-center lg:justify-between">
              <div>
                <p className="eyebrow">Tank overview</p>
                <h2 className="mt-1 text-2xl font-semibold tracking-[-0.04em] text-[var(--wilo-ink)] md:text-3xl">
                  Water storage status
                </h2>
              </div>
              <div className="flex items-center gap-3 self-start rounded-full border border-[var(--wilo-border)] bg-[var(--wilo-green-soft)] px-4 py-2">
                <span className={`h-3 w-3 rounded-full ${statusTone(state.sensorStatus, state.live)}`} />
                <span className="font-mono text-xs uppercase tracking-[0.18em] text-[var(--wilo-green-deep)]">
                  {state.live ? "live runtime" : "fallback preview"}
                </span>
              </div>
            </div>

            <div className="mt-6 grid gap-4 lg:grid-cols-2">
              <TankCard
                badge="estimated"
                percent={state.mainPct}
                subtitle="Pump room storage"
                title="Main tank"
                metrics={[
                  { label: "Capacity", value: "25,000 L", note: "Configured storage volume" },
                  {
                    label: "Pump relay",
                    value: state.pumpRelayOn ? "Running" : "Stopped",
                    note: state.pumpRelayOn ? "Relay energised" : "Relay idle",
                  },
                  {
                    label: "Current draw",
                    value: `${formatNumber(state.currentAmps, 2)} A`,
                    note: "Local ACS712 path",
                  },
                  {
                    label: "Mains voltage",
                    value: `${formatNumber(state.voltageAc, 1)} V`,
                    note: "Local ZMPT101B path",
                  },
                ]}
              />

              <TankCard
                badge="live source"
                percent={state.upperPct}
                subtitle="Upper tank via LoRa"
                title="Slave tank"
                metrics={[
                  {
                    label: "Pressure",
                    value: `${formatNumber(state.pressureKpa, 2)} kPa`,
                    note: "Received from ESP32 payload",
                  },
                  {
                    label: "Sensor voltage",
                    value: `${formatNumber(state.sensorVoltage, 3)} V`,
                    note:
                      state.sensorStatus === "fault"
                        ? "Sensor fault reported"
                        : "Pressure probe status OK",
                  },
                  {
                    label: "LoRa packet",
                    value: state.loraPkt !== null ? `#${state.loraPkt}` : "--",
                    note: `Age ${formatNumber(state.loraAgeS, 1)} s`,
                  },
                  {
                    label: "Signal quality",
                    value: `RSSI ${formatNumber(state.loraRssi, 0)} / SNR ${formatNumber(state.loraSnr, 1)}`,
                    note: "Receiver health",
                  },
                ]}
              />
            </div>
          </article>
        </div>

        <div className="grid gap-6">
          <article className="rounded-[1.7rem] border border-[var(--wilo-border)] bg-[var(--wilo-green-soft)] p-5 shadow-haze">
            <p className="font-mono text-[0.68rem] uppercase tracking-[0.22em] text-[var(--wilo-green-deep)]">
              Controller decision
            </p>
            <div className="mt-3 text-3xl font-semibold tracking-[-0.05em] text-[var(--wilo-ink)]">
              {state.decision.state ?? "UNKNOWN"}
            </div>
            <p className="mt-3 text-sm leading-7 text-[var(--wilo-muted)]">
              {state.decision.reason ?? "No decision reason provided"}
            </p>
            <div className="mt-5 grid gap-3 sm:grid-cols-2 xl:grid-cols-1">
              <InfoCard label="Controller mode" value={state.controllerMode} />
              <InfoCard label="Manual override" value={state.override ?? "none"} />
              <InfoCard label="ML prediction window" value={formatPrediction(state.mlPrediction)} />
              <InfoCard label="Host" value={state.host} />
            </div>
          </article>

          <article className="glass-card p-5">
            <p className="eyebrow">Runtime checklist</p>
            <div className="mt-4 grid gap-3">
              {[
                ["Controller feed", state.connected ? "Connected" : "Standby"],
                ["LoRa status", state.sensorStatus === "fault" ? "Fault" : "Receiving"],
                ["Pump action", state.decision.action ?? "HOLD"],
                [
                  "Last update",
                  state.timestamp ? new Date(state.timestamp).toLocaleTimeString() : "Waiting",
                ],
              ].map(([label, value]) => (
                <div
                  key={label}
                  className="flex items-center justify-between gap-3 rounded-2xl border border-[var(--wilo-border)] bg-[#f9fbf6] px-4 py-3"
                >
                  <span className="text-sm text-[var(--wilo-muted)]">{label}</span>
                  <strong className="font-mono text-xs uppercase tracking-[0.16em] text-[var(--wilo-ink)]">
                    {value}
                  </strong>
                </div>
              ))}
            </div>
          </article>

          <article className="glass-card p-5">
            <p className="eyebrow">Operator notes</p>
            <div className="mt-4 rounded-2xl border border-[var(--wilo-border)] bg-[#f9fbf6] p-4 font-mono text-xs leading-7 text-[var(--wilo-muted)]">
              {events.map((entry) => (
                <div key={entry}>{entry}</div>
              ))}
            </div>
          </article>
        </div>
      </section>
    </div>
  );
}
