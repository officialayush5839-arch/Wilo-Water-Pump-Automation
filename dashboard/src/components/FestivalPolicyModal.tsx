import React, { useState, useEffect, useCallback } from "react";
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
  DialogDescription,
} from "@/components/ui/dialog";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { Switch } from "@/components/ui/switch";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Card } from "@/components/ui/card";
import {
  Calendar,
  Clock,
  ShieldAlert,
  ShieldCheck,
  RotateCcw,
  Sparkles,
  AlertTriangle,
  Flame,
  CheckCircle2,
  RefreshCw,
} from "lucide-react";
import { useToast } from "@/hooks/use-toast";

interface FestivalPolicyModalProps {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  onStateChange?: () => void;
}

interface FestivalStatus {
  mode_enabled: boolean;
  state: "RESTRICTION_ACTIVE" | "RESTRICTION_RELEASED" | "NORMAL" | "DISABLED";
  policy: "RANG_PANCHAMI" | "NORMAL";
  festival_name: string | null;
  festival_date: string | null;
  is_rang_panchami: boolean;
  restriction_active: boolean;
  automatic_start_blocked: boolean;
  release_time: string | null;
  release_time_display: string;
  current_time_ist: string;
  remaining_minutes: number;
  reason: string;
  is_simulated: boolean;
}

interface HolidayRecord {
  year: number;
  date: string;
  event: string;
  type: string;
  policy: string;
}

export const FestivalPolicyModal: React.FC<FestivalPolicyModalProps> = ({
  open,
  onOpenChange,
  onStateChange,
}) => {
  const { toast } = useToast();
  const [loading, setLoading] = useState(false);
  const [status, setStatus] = useState<FestivalStatus | null>(null);
  const [upcoming, setUpcoming] = useState<HolidayRecord[]>([]);
  const [error, setError] = useState<string | null>(null);

  // Simulation Form State
  const [simDate, setSimDate] = useState("2026-03-08");
  const [simTime, setSimTime] = useState("18:30");

  const fetchFestivalStatus = useCallback(async () => {
    try {
      const res = await fetch("/api/festival/status");
      if (!res.ok) throw new Error(`HTTP ${res.status}`);
      const data = await res.json();
      if (data.ok && data.status) {
        setStatus(data.status);
        setError(null);
      }
    } catch (err: any) {
      console.error("Failed to fetch festival status:", err);
      setError("Unable to connect to festival backend API.");
    }
  }, []);

  const fetchUpcoming = useCallback(async () => {
    try {
      const res = await fetch("/api/festivals/upcoming?days=120");
      if (!res.ok) throw new Error(`HTTP ${res.status}`);
      const data = await res.json();
      if (data.ok && Array.isArray(data.festivals)) {
        setUpcoming(data.festivals);
      }
    } catch (err: any) {
      console.error("Failed to fetch upcoming festivals:", err);
    }
  }, []);

  useEffect(() => {
    if (open) {
      fetchFestivalStatus();
      fetchUpcoming();
      const interval = setInterval(fetchFestivalStatus, 3000);
      return () => clearInterval(interval);
    }
  }, [open, fetchFestivalStatus, fetchUpcoming]);

  const handleToggleMode = async (enabled: boolean) => {
    setLoading(true);
    try {
      const res = await fetch("/api/festival/mode", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ enabled }),
      });
      const data = await res.json();
      if (data.ok) {
        setStatus(data.status);
        toast({
          title: enabled ? "Festival Mode ON" : "Festival Mode OFF",
          description: data.message,
        });
        onStateChange?.();
      } else {
        throw new Error(data.error || "Failed to update mode");
      }
    } catch (err: any) {
      toast({
        title: "Error",
        description: err.message,
        variant: "destructive",
      });
    } finally {
      setLoading(false);
    }
  };

  const handleSelectFestival = async (eventName: string, eventDate: string) => {
    setLoading(true);
    try {
      const res = await fetch("/api/festival/select", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ event: eventName, date: eventDate }),
      });
      const data = await res.json();
      if (data.ok) {
        setStatus(data.status);
        toast({
          title: "Festival Selected",
          description: `Active festival set to ${eventName} (${eventDate})`,
        });
        onStateChange?.();
      } else {
        throw new Error(data.error || "Failed to select festival");
      }
    } catch (err: any) {
      toast({
        title: "Selection Error",
        description: err.message,
        variant: "destructive",
      });
    } finally {
      setLoading(false);
    }
  };

  const handleSimulate = async (customDate?: string, customTime?: string) => {
    const targetDate = customDate || simDate;
    const targetTime = customTime || simTime;
    setLoading(true);
    try {
      const res = await fetch("/api/festival/simulate", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ date: targetDate, time: targetTime }),
      });
      const data = await res.json();
      if (data.ok) {
        setStatus(data.status);
        toast({
          title: "Simulation Active",
          description: `Simulating ${targetDate} at ${targetTime} IST`,
        });
        onStateChange?.();
      } else {
        throw new Error(data.error || "Failed to run simulation");
      }
    } catch (err: any) {
      toast({
        title: "Simulation Error",
        description: err.message,
        variant: "destructive",
      });
    } finally {
      setLoading(false);
    }
  };

  const handleReset = async () => {
    setLoading(true);
    try {
      const res = await fetch("/api/festival/reset", {
        method: "POST",
      });
      const data = await res.json();
      if (data.ok) {
        setStatus(data.status);
        toast({
          title: "Reset Successful",
          description: "Festival state and simulation restored to live defaults.",
        });
        onStateChange?.();
      }
    } catch (err: any) {
      toast({
        title: "Reset Failed",
        description: err.message,
        variant: "destructive",
      });
    } finally {
      setLoading(false);
    }
  };

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="max-w-3xl max-h-[88vh] overflow-y-auto bg-card text-card-foreground border-border shadow-2xl p-6">
        <DialogHeader className="border-b border-border pb-4">
          <div className="flex items-center justify-between flex-wrap gap-4">
            <div className="flex items-center gap-3">
              <div className="p-2.5 rounded-xl bg-blue-500/10 border border-blue-500/20 text-blue-600">
                <Calendar className="h-6 w-6" />
              </div>
              <div>
                <DialogTitle className="text-xl font-bold tracking-tight text-foreground flex items-center gap-2">
                  Festival & Holiday Pump Policy
                  {status?.is_simulated && (
                    <Badge variant="outline" className="border-amber-500/40 text-amber-600 bg-amber-50 text-xs font-semibold">
                      Simulation Mode
                    </Badge>
                  )}
                </DialogTitle>
                <DialogDescription className="text-muted-foreground text-xs sm:text-sm mt-0.5">
                  Holiday-aware pump scheduling & Rang Panchami 07:00 PM IST policy.
                </DialogDescription>
              </div>
            </div>

            {/* Mode Switch */}
            <div className="flex items-center gap-3 bg-muted/60 px-3.5 py-1.5 rounded-xl border border-border">
              <Label htmlFor="fest-mode" className="text-xs font-semibold uppercase tracking-wider text-foreground cursor-pointer">
                Festival Mode
              </Label>
              <Switch
                id="fest-mode"
                checked={status?.mode_enabled ?? true}
                onCheckedChange={handleToggleMode}
                disabled={loading}
              />
            </div>
          </div>
        </DialogHeader>

        {error && (
          <div className="p-3.5 rounded-xl bg-red-50 border border-red-200 text-red-700 text-sm flex items-center justify-between">
            <div className="flex items-center gap-2">
              <AlertTriangle className="h-4 w-4 text-red-500" />
              <span>{error}</span>
            </div>
            <Button size="sm" variant="ghost" onClick={fetchFestivalStatus} className="h-7 text-xs text-red-700 hover:text-red-800 hover:bg-red-100">
              <RefreshCw className="h-3 w-3 mr-1" /> Retry
            </Button>
          </div>
        )}

        {/* Active Policy Status Banner */}
        {status && (
          <div className="space-y-4">
            {status.state === "RESTRICTION_ACTIVE" ? (
              <Card className="p-4 bg-red-500/10 border-red-500/30 text-red-950 shadow-sm">
                <div className="flex items-start justify-between flex-wrap gap-4">
                  <div className="flex items-start gap-3">
                    <div className="p-2 rounded-lg bg-red-500/20 border border-red-500/30 text-red-600 mt-0.5 animate-pulse">
                      <ShieldAlert className="h-5 w-5" />
                    </div>
                    <div>
                      <div className="flex items-center gap-2">
                        <span className="text-xs font-bold uppercase tracking-wider text-red-700">
                          {status.festival_name || "Rang Panchami"} Special Policy
                        </span>
                        <Badge variant="destructive" className="font-mono text-xs animate-pulse">
                          BLOCKED UNTIL 07:00 PM IST
                        </Badge>
                      </div>
                      <h4 className="text-base font-bold text-foreground mt-1">
                        Automatic Pump Starts Inhibited
                      </h4>
                      <p className="text-xs text-muted-foreground mt-1 max-w-xl">
                        {status.reason}
                      </p>
                    </div>
                  </div>

                  <div className="text-right">
                    <div className="text-2xl font-bold font-mono text-red-600">
                      {status.remaining_minutes}m
                    </div>
                    <span className="text-[10px] text-muted-foreground font-semibold tracking-wider uppercase">
                      Remaining
                    </span>
                  </div>
                </div>
              </Card>
            ) : status.state === "RESTRICTION_RELEASED" ? (
              <Card className="p-4 bg-emerald-500/10 border-emerald-500/30 text-emerald-950 shadow-sm">
                <div className="flex items-center gap-3">
                  <div className="p-2 rounded-lg bg-emerald-500/20 text-emerald-600">
                    <ShieldCheck className="h-5 w-5" />
                  </div>
                  <div>
                    <div className="flex items-center gap-2">
                      <span className="text-xs font-bold uppercase tracking-wider text-emerald-700">
                        {status.festival_name}
                      </span>
                      <Badge className="bg-emerald-600 text-white text-xs">RELEASED</Badge>
                    </div>
                    <p className="text-sm text-foreground font-medium mt-0.5">
                      07:00 PM IST Reached — Normal Automation Allowed
                    </p>
                  </div>
                </div>
              </Card>
            ) : (
              <Card className="p-4 bg-muted/40 border-border shadow-sm">
                <div className="flex items-center justify-between flex-wrap gap-4">
                  <div className="flex items-center gap-3">
                    <div className="p-2 rounded-lg bg-blue-500/10 text-blue-600 border border-blue-500/20">
                      <CheckCircle2 className="h-5 w-5" />
                    </div>
                    <div>
                      <div className="text-xs font-semibold text-muted-foreground uppercase tracking-wider">
                        Current Policy Status
                      </div>
                      <div className="text-sm font-bold text-foreground mt-0.5">
                        {status.mode_enabled
                          ? `Standard Automated Operation (${status.festival_name || "Regular Day"})`
                          : "Festival Policy Disabled (Manual Bypass)"}
                      </div>
                    </div>
                  </div>

                  <div className="text-right text-xs text-muted-foreground">
                    <div className="font-mono text-foreground font-semibold">{status.current_time_ist}</div>
                    <div className="text-[11px] text-muted-foreground">Asia/Kolkata Clock</div>
                  </div>
                </div>
              </Card>
            )}

            {/* Policy Parameters Card */}
            <div className="grid grid-cols-2 sm:grid-cols-4 gap-3">
              <Card className="p-3 bg-card border-border shadow-sm">
                <span className="text-[11px] font-semibold text-muted-foreground uppercase tracking-wider">Active Festival</span>
                <p className="text-sm font-bold text-foreground mt-1 truncate">
                  {status.festival_name || "None (Regular Day)"}
                </p>
              </Card>

              <Card className="p-3 bg-card border-border shadow-sm">
                <span className="text-[11px] font-semibold text-muted-foreground uppercase tracking-wider">Control Policy</span>
                <p className={`text-sm font-bold mt-1 ${status.policy === "RANG_PANCHAMI" ? "text-red-600" : "text-blue-600"}`}>
                  {status.policy}
                </p>
              </Card>

              <Card className="p-3 bg-card border-border shadow-sm">
                <span className="text-[11px] font-semibold text-muted-foreground uppercase tracking-wider">Release Time</span>
                <p className="text-sm font-bold text-foreground mt-1">
                  {status.release_time_display}
                </p>
              </Card>

              <Card className="p-3 bg-card border-border shadow-sm">
                <span className="text-[11px] font-semibold text-muted-foreground uppercase tracking-wider">Auto Starts</span>
                <p className={`text-sm font-bold mt-1 ${status.automatic_start_blocked ? "text-red-600" : "text-emerald-600"}`}>
                  {status.automatic_start_blocked ? "BLOCKED" : "ALLOWED"}
                </p>
              </Card>
            </div>

            {/* Quick Demo & QA Testing Sandbox */}
            <Card className="p-4 bg-muted/30 border-border space-y-3 shadow-sm">
              <div className="flex items-center justify-between">
                <h4 className="text-xs font-bold uppercase tracking-wider text-foreground flex items-center gap-2">
                  <Sparkles className="h-4 w-4 text-blue-500" /> QA Simulation Sandbox
                </h4>
                {status.is_simulated && (
                  <Button
                    size="sm"
                    variant="ghost"
                    onClick={handleReset}
                    className="h-7 text-xs text-amber-700 hover:text-amber-800 hover:bg-amber-100"
                  >
                    <RotateCcw className="h-3 w-3 mr-1" /> Reset to Live
                  </Button>
                )}
              </div>

              {/* Quick Presets */}
              <div className="flex flex-wrap gap-2">
                <Button
                  size="sm"
                  variant="outline"
                  onClick={() => handleSimulate("2026-03-08", "18:30")}
                  className="h-7 text-xs border-red-200 bg-white hover:bg-red-50 text-red-700 hover:text-red-800"
                >
                  <Flame className="h-3 w-3 mr-1 text-red-500" />
                  RP 18:30 (Blocked)
                </Button>
                <Button
                  size="sm"
                  variant="outline"
                  onClick={() => handleSimulate("2026-03-08", "18:59")}
                  className="h-7 text-xs border-red-200 bg-white hover:bg-red-50 text-red-700 hover:text-red-800"
                >
                  <Clock className="h-3 w-3 mr-1 text-red-500" />
                  RP 18:59 (1m Left)
                </Button>
                <Button
                  size="sm"
                  variant="outline"
                  onClick={() => handleSimulate("2026-03-08", "19:00")}
                  className="h-7 text-xs border-emerald-200 bg-white hover:bg-emerald-50 text-emerald-700 hover:text-emerald-800"
                >
                  <ShieldCheck className="h-3 w-3 mr-1 text-emerald-500" />
                  RP 19:00 (Release)
                </Button>
                <Button
                  size="sm"
                  variant="outline"
                  onClick={() => handleSimulate("2026-03-08", "19:05")}
                  className="h-7 text-xs border-emerald-200 bg-white hover:bg-emerald-50 text-emerald-700 hover:text-emerald-800"
                >
                  <CheckCircle2 className="h-3 w-3 mr-1 text-emerald-500" />
                  RP 19:05 (Normal)
                </Button>
                <Button
                  size="sm"
                  variant="outline"
                  onClick={() => handleSelectFestival("Diwali", "2026-11-08")}
                  className="h-7 text-xs border-blue-200 bg-white hover:bg-blue-50 text-blue-700 hover:text-blue-800"
                >
                  Diwali (Normal)
                </Button>
              </div>

              {/* Custom Date / Time Input */}
              <div className="grid grid-cols-1 sm:grid-cols-3 gap-3 pt-1">
                <div>
                  <Label className="text-[11px] font-medium text-muted-foreground">Simulate Date</Label>
                  <Input
                    type="date"
                    value={simDate}
                    onChange={(e) => setSimDate(e.target.value)}
                    className="h-8 text-xs bg-background border-border text-foreground mt-1"
                  />
                </div>
                <div>
                  <Label className="text-[11px] font-medium text-muted-foreground">Simulate Time (IST)</Label>
                  <Input
                    type="time"
                    value={simTime}
                    onChange={(e) => setSimTime(e.target.value)}
                    className="h-8 text-xs bg-background border-border text-foreground mt-1"
                  />
                </div>
                <div className="flex items-end">
                  <Button
                    size="sm"
                    onClick={() => handleSimulate()}
                    disabled={loading}
                    className="h-8 w-full text-xs bg-primary hover:bg-primary/90 text-primary-foreground font-semibold"
                  >
                    Apply Simulation
                  </Button>
                </div>
              </div>
            </Card>

            {/* Upcoming Holiday Calendar */}
            <div className="space-y-2">
              <h4 className="text-xs font-bold uppercase tracking-wider text-foreground flex items-center gap-2">
                <Calendar className="h-4 w-4 text-blue-500" /> Holiday Calendar (2020–2030)
              </h4>
              <div className="border border-border rounded-xl overflow-hidden max-h-48 overflow-y-auto bg-card shadow-sm">
                <table className="w-full text-left text-xs">
                  <thead className="bg-muted/60 text-muted-foreground sticky top-0 border-b border-border">
                    <tr>
                      <th className="py-2 px-3 font-semibold">Date</th>
                      <th className="py-2 px-3 font-semibold">Festival Name</th>
                      <th className="py-2 px-3 font-semibold">Type</th>
                      <th className="py-2 px-3 font-semibold">Policy</th>
                      <th className="py-2 px-3 font-semibold text-right">Action</th>
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-border">
                    {upcoming.slice(0, 20).map((h, i) => (
                      <tr key={i} className="hover:bg-muted/40 transition-colors">
                        <td className="py-2 px-3 font-mono text-foreground">{h.date}</td>
                        <td className="py-2 px-3 font-medium text-foreground">{h.event}</td>
                        <td className="py-2 px-3 text-muted-foreground">{h.type}</td>
                        <td className="py-2 px-3">
                          {h.policy === "RANG_PANCHAMI" ? (
                            <Badge className="bg-red-500/10 text-red-600 border border-red-500/20 text-[10px] font-medium">
                              RANG_PANCHAMI (19:00 IST)
                            </Badge>
                          ) : (
                            <Badge variant="outline" className="border-border text-muted-foreground text-[10px]">
                              NORMAL
                            </Badge>
                          )}
                        </td>
                        <td className="py-2 px-3 text-right">
                          <Button
                            size="sm"
                            variant="ghost"
                            onClick={() => handleSelectFestival(h.event, h.date)}
                            className="h-6 text-[11px] text-primary hover:text-primary hover:bg-primary/10 px-2 font-medium"
                          >
                            Select
                          </Button>
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </div>
          </div>
        )}
      </DialogContent>
    </Dialog>
  );
};
