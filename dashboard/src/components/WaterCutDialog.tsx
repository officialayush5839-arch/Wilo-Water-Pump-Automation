import React, { useState, useEffect } from "react";
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
  DialogDescription,
  DialogFooter,
} from "@/components/ui/dialog";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Badge } from "@/components/ui/badge";
import { Card } from "@/components/ui/card";
import { useToast } from "@/hooks/use-toast";
import {
  Droplets,
  Calendar,
  Clock,
  Plus,
  Trash2,
  AlertTriangle,
  CheckCircle2,
  ShieldAlert,
  LoaderCircle,
  HelpCircle,
} from "lucide-react";

export interface WaterCutEvent {
  id: string;
  start_time: string;
  end_time: string;
  target_reserve_pct: number;
  pre_fill_hours: number;
  reason: string;
  created_at?: string;
}

export interface WaterCutStatus {
  state: "NORMAL" | "PREFILL" | "WATER_CUT_ACTIVE";
  is_cut_active: boolean;
  is_prefill_active: boolean;
  active_cut?: WaterCutEvent | null;
  prefill_cut?: WaterCutEvent | null;
  upcoming_cut?: WaterCutEvent | null;
  current_event?: WaterCutEvent | null;
  target_reserve_pct?: number | null;
  prefill_remaining_min?: number | null;
  cut_remaining_min?: number | null;
  cuts_count: number;
}

interface WaterCutDialogProps {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  apiBaseUrl?: string;
  currentTankLevel?: number | null;
  onStatusUpdated?: (status: WaterCutStatus) => void;
}

export function WaterCutDialog({
  open,
  onOpenChange,
  apiBaseUrl = "",
  currentTankLevel,
  onStatusUpdated,
}: WaterCutDialogProps) {
  const { toast } = useToast();
  const [cuts, setCuts] = useState<WaterCutEvent[]>([]);
  const [status, setStatus] = useState<WaterCutStatus | null>(null);
  const [isLoading, setIsLoading] = useState(false);
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [showAddForm, setShowAddForm] = useState(false);

  // Form State
  const todayStr = new Date().toISOString().split("T")[0];
  const [startDate, setStartDate] = useState(todayStr);
  const [startTime, setStartTime] = useState("08:00");
  const [endDate, setEndDate] = useState(todayStr);
  const [endTime, setEndTime] = useState("18:00");
  const [targetReserve, setTargetReserve] = useState("95");
  const [prefillHours, setPrefillHours] = useState("4");
  const [reason, setReason] = useState("Municipal pipeline maintenance");

  const fetchCuts = async () => {
    setIsLoading(true);
    try {
      const res = await fetch(`${apiBaseUrl}/api/water-cuts`);
      if (!res.ok) throw new Error("Failed to fetch water cut events");
      const data = await res.json();
      if (data.ok) {
        setCuts(data.cuts || []);
        setStatus(data.status || null);
        if (onStatusUpdated && data.status) {
          onStatusUpdated(data.status);
        }
      }
    } catch (err) {
      console.error("Failed to load water cuts:", err);
    } finally {
      setIsLoading(false);
    }
  };

  useEffect(() => {
    if (open) {
      fetchCuts();
    }
  }, [open]);

  const handleCreateCut = async (e: React.FormEvent) => {
    e.preventDefault();
    setIsSubmitting(true);

    try {
      const startDateTime = `${startDate}T${startTime}:00`;
      const endDateTime = `${endDate}T${endTime}:00`;

      const payload = {
        start_time: startDateTime,
        end_time: endDateTime,
        target_reserve_pct: parseFloat(targetReserve) || 95.0,
        pre_fill_hours: parseFloat(prefillHours) || 4.0,
        reason: reason.trim() || "Municipal pipeline maintenance",
      };

      const res = await fetch(`${apiBaseUrl}/api/water-cuts`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(payload),
      });

      const data = await res.json();
      if (!res.ok || !data.ok) {
        throw new Error(data.error || "Failed to schedule water cut");
      }

      toast({
        title: "Water Cut Scheduled",
        description: `Pre-fill will target ${payload.target_reserve_pct}% reserve ${payload.pre_fill_hours}h before outage.`,
      });

      setShowAddForm(false);
      await fetchCuts();
    } catch (err) {
      const message = err instanceof Error ? err.message : "Submission failed";
      toast({
        title: "Validation Error",
        description: message,
        variant: "destructive",
      });
    } finally {
      setIsSubmitting(false);
    }
  };

  const handleDeleteCut = async (id: string) => {
    try {
      const res = await fetch(`${apiBaseUrl}/api/water-cuts/${id}`, {
        method: "DELETE",
      });
      const data = await res.json();
      if (!res.ok || !data.ok) {
        throw new Error(data.error || "Failed to delete water cut");
      }

      toast({
        title: "Event Removed",
        description: "The municipal water cut event was successfully deleted.",
      });

      await fetchCuts();
    } catch (err) {
      const message = err instanceof Error ? err.message : "Delete failed";
      toast({
        title: "Delete Failed",
        description: message,
        variant: "destructive",
      });
    }
  };

  const formatDateTime = (isoStr: string) => {
    try {
      const dt = new Date(isoStr);
      return dt.toLocaleString([], {
        month: "short",
        day: "numeric",
        year: "numeric",
        hour: "2-digit",
        minute: "2-digit",
      });
    } catch {
      return isoStr;
    }
  };

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="max-w-3xl max-h-[90vh] overflow-y-auto bg-card text-card-foreground border-border shadow-2xl">
        <DialogHeader>
          <div className="flex items-center gap-3">
            <div className="p-2 rounded-xl bg-blue-500/10 text-blue-500 border border-blue-500/20">
              <Droplets className="h-6 w-6" />
            </div>
            <div>
              <DialogTitle className="text-xl font-bold">Municipal Water Cut Management</DialogTitle>
              <DialogDescription className="text-muted-foreground text-xs sm:text-sm">
                Schedule advance municipal water outages. The system automatically elevates the Master Tank reserve before the cut begins.
              </DialogDescription>
            </div>
          </div>
        </DialogHeader>

        {/* Current State Banner */}
        <div className="my-2">
          {status?.state === "WATER_CUT_ACTIVE" ? (
            <Card className="p-4 bg-amber-500/10 border-amber-500/30 text-amber-900 dark:text-amber-200">
              <div className="flex items-start gap-3">
                <AlertTriangle className="h-5 w-5 text-amber-500 shrink-0 mt-0.5" />
                <div className="space-y-1">
                  <div className="flex items-center gap-2">
                    <span className="font-bold text-sm tracking-wide uppercase">Municipal Water Cut Active</span>
                    <Badge variant="destructive" className="animate-pulse text-[10px]">
                      CONSERVING SUPPLY
                    </Badge>
                  </div>
                  <p className="text-xs text-muted-foreground">
                    Municipal mains are offline. Automated low-level pumping is held to prevent running dry.
                  </p>
                  {status.active_cut && (
                    <div className="text-xs pt-1 flex flex-wrap gap-4 text-foreground/80 font-medium">
                      <span>Reason: {status.active_cut.reason}</span>
                      <span>Ends: {formatDateTime(status.active_cut.end_time)}</span>
                      {status.cut_remaining_min !== null && (
                        <span>Remaining: {Math.floor(status.cut_remaining_min / 60)}h {Math.round(status.cut_remaining_min % 60)}m</span>
                      )}
                    </div>
                  )}
                </div>
              </div>
            </Card>
          ) : status?.state === "PREFILL" ? (
            <Card className="p-4 bg-blue-500/10 border-blue-500/30 text-blue-900 dark:text-blue-200">
              <div className="flex items-start gap-3">
                <Droplets className="h-5 w-5 text-blue-500 shrink-0 mt-0.5 animate-bounce" />
                <div className="space-y-1">
                  <div className="flex items-center gap-2">
                    <span className="font-bold text-sm tracking-wide uppercase">Pre-Fill Window Active</span>
                    <Badge className="bg-blue-600 text-white text-[10px]">
                      TARGET: {status.target_reserve_pct ?? 95}%
                    </Badge>
                  </div>
                  <p className="text-xs text-muted-foreground">
                    Filling Master Tank toward elevated reserve before the scheduled municipal outage.
                  </p>
                  {status.prefill_cut && (
                    <div className="text-xs pt-1 flex flex-wrap gap-4 text-foreground/80 font-medium">
                      <span>Outage starts: {formatDateTime(status.prefill_cut.start_time)}</span>
                      {status.prefill_remaining_min !== null && (
                        <span>Time to outage: {Math.floor(status.prefill_remaining_min / 60)}h {Math.round(status.prefill_remaining_min % 60)}m</span>
                      )}
                      <span>Current Tank: {currentTankLevel !== null && currentTankLevel !== undefined ? `${currentTankLevel.toFixed(1)}%` : "--"}</span>
                    </div>
                  )}
                </div>
              </div>
            </Card>
          ) : (
            <Card className="p-3 bg-muted/40 border-border">
              <div className="flex items-center justify-between text-xs">
                <div className="flex items-center gap-2">
                  <CheckCircle2 className="h-4 w-4 text-green-500" />
                  <span className="font-medium text-foreground">Municipal Supply Status: Normal</span>
                </div>
                <span className="text-muted-foreground">
                  {cuts.length} scheduled outage{cuts.length === 1 ? "" : "s"} on record
                </span>
              </div>
            </Card>
          )}
        </div>

        {/* Action Toggle */}
        <div className="flex items-center justify-between pt-2">
          <h4 className="text-sm font-semibold text-foreground">Scheduled Municipal Water Cuts</h4>
          <Button
            size="sm"
            onClick={() => setShowAddForm(!showAddForm)}
            className="gap-1.5 text-xs"
            variant={showAddForm ? "outline" : "default"}
          >
            {showAddForm ? "Cancel" : <><Plus className="h-3.5 w-3.5" /> Add Outage</>}
          </Button>
        </div>

        {/* Create Cut Form */}
        {showAddForm && (
          <form onSubmit={handleCreateCut} className="rounded-xl border border-border bg-muted/20 p-4 space-y-4 transition-all">
            <div className="text-xs font-semibold text-primary uppercase tracking-wider">
              New Municipal Outage Details
            </div>

            <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
              <div className="space-y-1.5">
                <Label className="text-xs font-medium">Start Date</Label>
                <Input
                  type="date"
                  value={startDate}
                  onChange={(e) => setStartDate(e.target.value)}
                  required
                  className="h-9 text-xs"
                />
              </div>
              <div className="space-y-1.5">
                <Label className="text-xs font-medium">Start Time</Label>
                <Input
                  type="time"
                  value={startTime}
                  onChange={(e) => setStartTime(e.target.value)}
                  required
                  className="h-9 text-xs"
                />
              </div>
            </div>

            <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
              <div className="space-y-1.5">
                <Label className="text-xs font-medium">End Date</Label>
                <Input
                  type="date"
                  value={endDate}
                  onChange={(e) => setEndDate(e.target.value)}
                  required
                  className="h-9 text-xs"
                />
              </div>
              <div className="space-y-1.5">
                <Label className="text-xs font-medium">End Time</Label>
                <Input
                  type="time"
                  value={endTime}
                  onChange={(e) => setEndTime(e.target.value)}
                  required
                  className="h-9 text-xs"
                />
              </div>
            </div>

            <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
              <div className="space-y-1.5">
                <Label className="text-xs font-medium">Target Reserve (%)</Label>
                <Input
                  type="number"
                  min="50"
                  max="95"
                  step="1"
                  value={targetReserve}
                  onChange={(e) => setTargetReserve(e.target.value)}
                  required
                  className="h-9 text-xs"
                />
                <p className="text-[10px] text-muted-foreground">Default 95% (Max safe target below 95% overflow threshold).</p>
              </div>
              <div className="space-y-1.5">
                <Label className="text-xs font-medium">Pre-fill Lead Time (Hours)</Label>
                <Input
                  type="number"
                  min="1"
                  max="24"
                  step="0.5"
                  value={prefillHours}
                  onChange={(e) => setPrefillHours(e.target.value)}
                  required
                  className="h-9 text-xs"
                />
                <p className="text-[10px] text-muted-foreground">Hours before start to initiate elevated reserve filling.</p>
              </div>
            </div>

            <div className="space-y-1.5">
              <Label className="text-xs font-medium">Outage Reason / Notes</Label>
              <Input
                type="text"
                placeholder="e.g. Municipal pipeline maintenance / Valve replacement"
                value={reason}
                onChange={(e) => setReason(e.target.value)}
                className="h-9 text-xs"
              />
            </div>

            <div className="flex justify-end gap-2 pt-2">
              <Button type="button" variant="ghost" size="sm" onClick={() => setShowAddForm(false)}>
                Cancel
              </Button>
              <Button type="submit" size="sm" disabled={isSubmitting} className="gap-1.5">
                {isSubmitting ? <LoaderCircle className="h-4 w-4 animate-spin" /> : <CheckCircle2 className="h-4 w-4" />}
                Save Water Cut
              </Button>
            </div>
          </form>
        )}

        {/* Cuts List */}
        <div className="space-y-2">
          {isLoading ? (
            <div className="py-8 flex justify-center items-center gap-2 text-sm text-muted-foreground">
              <LoaderCircle className="h-5 w-5 animate-spin text-primary" />
              Loading water cuts...
            </div>
          ) : cuts.length === 0 ? (
            <div className="py-8 text-center border border-dashed border-border rounded-xl">
              <Droplets className="h-8 w-8 mx-auto text-muted-foreground mb-2 opacity-50" />
              <p className="text-sm font-medium text-foreground">No upcoming water cuts scheduled</p>
              <p className="text-xs text-muted-foreground mt-1">
                Click "+ Add Outage" above to configure a future municipal supply interruption.
              </p>
            </div>
          ) : (
            cuts.map((cut) => {
              const now = new Date();
              const start = new Date(cut.start_time);
              const end = new Date(cut.end_time);
              const isOngoing = now >= start && now <= end;
              const isPast = now > end;

              return (
                <div
                  key={cut.id}
                  className={`p-3.5 rounded-xl border transition-all flex items-center justify-between gap-4 ${
                    isOngoing
                      ? "border-amber-500/40 bg-amber-500/5"
                      : isPast
                      ? "border-border bg-muted/20 opacity-60"
                      : "border-border bg-card hover:bg-muted/10"
                  }`}
                >
                  <div className="space-y-1 text-xs">
                    <div className="flex items-center gap-2 flex-wrap">
                      <span className="font-semibold text-sm text-foreground">{cut.reason}</span>
                      {isOngoing ? (
                        <Badge variant="destructive" className="text-[10px]">ACTIVE NOW</Badge>
                      ) : isPast ? (
                        <Badge variant="secondary" className="text-[10px]">COMPLETED</Badge>
                      ) : (
                        <Badge variant="outline" className="text-[10px] text-blue-500 border-blue-500/30">UPCOMING</Badge>
                      )}
                    </div>
                    <div className="text-muted-foreground flex items-center gap-3 flex-wrap">
                      <span className="flex items-center gap-1">
                        <Clock className="h-3.5 w-3.5 text-primary" />
                        {formatDateTime(cut.start_time)} → {formatDateTime(cut.end_time)}
                      </span>
                    </div>
                    <div className="flex items-center gap-3 text-[11px] text-muted-foreground pt-0.5">
                      <span>Reserve Target: <strong className="text-foreground">{cut.target_reserve_pct}%</strong></span>
                      <span>•</span>
                      <span>Pre-fill Window: <strong className="text-foreground">{cut.pre_fill_hours}h prior</strong></span>
                    </div>
                  </div>

                  <Button
                    variant="ghost"
                    size="sm"
                    onClick={() => handleDeleteCut(cut.id)}
                    className="text-destructive hover:bg-destructive/10 hover:text-destructive shrink-0 h-8 w-8 p-0"
                    title="Delete water cut"
                  >
                    <Trash2 className="h-4 w-4" />
                  </Button>
                </div>
              );
            })
          )}
        </div>

        <DialogFooter className="border-t border-border pt-3">
          <div className="w-full flex justify-between items-center text-xs text-muted-foreground">
            <span className="flex items-center gap-1">
              <ShieldAlert className="h-3.5 w-3.5 text-primary" />
              Safety guards & overflow thresholds remain dominant
            </span>
            <Button variant="outline" size="sm" onClick={() => onOpenChange(false)}>
              Close
            </Button>
          </div>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}
