import React, { useState, useEffect } from "react";
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
import { Calendar } from "@/components/ui/calendar";
import { Card } from "@/components/ui/card";
import {
  Sparkles,
  Calendar as CalendarIcon,
  Clock,
  ShieldAlert,
  CheckCircle2,
  AlertTriangle,
  RotateCcw,
  FlaskConical,
} from "lucide-react";
import { toast } from "@/components/ui/use-toast";

export interface FestivalStatus {
  mode_enabled: boolean;
  policy: "NORMAL" | "RANG_PANCHAMI";
  is_rang_panchami: boolean;
  festival_name: string | null;
  festival_date: string | null;
  restriction_active: boolean;
  automatic_start_blocked: boolean;
  release_time: string;
  status: "INACTIVE" | "NORMAL_SCHEDULE" | "WAITING_FOR_RELEASE" | "RESTRICTION_RELEASED";
  reason: string;
  current_ist_time: string;
  simulation?: {
    simulated_date: string | null;
    simulated_time: string | null;
    is_simulating: boolean;
  };
}

export interface FestivalRecord {
  year: number;
  date_str: string;
  iso_date: string;
  event: string;
  type: string;
  control_policy: string;
}

interface FestivalPolicyModalProps {
  isOpen: boolean;
  onClose: () => void;
  apiBaseUrl: string;
  festivalStatus: FestivalStatus | null;
  onRefresh: () => void;
}

export function FestivalPolicyModal({
  isOpen,
  onClose,
  apiBaseUrl,
  festivalStatus,
  onRefresh,
}: FestivalPolicyModalProps) {
  const [festivals, setFestivals] = useState<FestivalRecord[]>([]);
  const [selectedMonth, setSelectedMonth] = useState<Date>(new Date());
  const [selectedDate, setSelectedDate] = useState<Date | undefined>(
    festivalStatus?.festival_date ? new Date(festivalStatus.festival_date) : new Date()
  );
  const [isUpdating, setIsUpdating] = useState(false);

  useEffect(() => {
    if (isOpen) {
      void fetchFestivals();
    }
  }, [isOpen]);

  const fetchFestivals = async () => {
    try {
      const res = await fetch(`${apiBaseUrl}/api/festivals`);
      if (res.ok) {
        const data = await res.json();
        if (data.ok && Array.isArray(data.festivals)) {
          setFestivals(data.festivals);
        }
      }
    } catch (err) {
      console.error("Failed to load festivals:", err);
    }
  };

  const handleToggleMode = async (enabled: boolean) => {
    setIsUpdating(true);
    try {
      const res = await fetch(`${apiBaseUrl}/api/festival/mode`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ enabled }),
      });
      if (!res.ok) throw new Error("Failed to change mode");
      toast({
        title: enabled ? "Festival Mode Enabled" : "Festival Mode Disabled",
        description: enabled
          ? "Context-aware policy active. Check active restrictions."
          : "Standard automatic/manual controls active.",
      });
      onRefresh();
    } catch (err) {
      toast({
        title: "Error updating festival mode",
        description: String(err),
        variant: "destructive",
      });
    } finally {
      setIsUpdating(false);
    }
  };

  const handleSelectFestival = async (festival: FestivalRecord) => {
    setIsUpdating(true);
    try {
      const res = await fetch(`${apiBaseUrl}/api/festival/select`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          festival_name: festival.event,
          festival_date: festival.iso_date,
        }),
      });
      if (!res.ok) throw new Error("Selection failed");
      toast({
        title: `Festival Selected: ${festival.event}`,
        description: `Date: ${festival.iso_date} | Policy: ${festival.control_policy}`,
      });
      onRefresh();
    } catch (err) {
      toast({
        title: "Error selecting festival",
        description: String(err),
        variant: "destructive",
      });
    } finally {
      setIsUpdating(false);
    }
  };

  const handleSimulate = async (date: string | null, time: string | null) => {
    setIsUpdating(true);
    try {
      const res = await fetch(`${apiBaseUrl}/api/festival/simulate`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ date, time }),
      });
      if (!res.ok) throw new Error("Simulation failed");
      toast({
        title: date ? "Simulation Fixture Applied" : "Simulation Cleared",
        description: date
          ? `Simulating ${date} at ${time} IST`
          : "System returned to real-time clock.",
      });
      onRefresh();
    } catch (err) {
      toast({
        title: "Simulation error",
        description: String(err),
        variant: "destructive",
      });
    } finally {
      setIsUpdating(false);
    }
  };

  const handleReset = async () => {
    setIsUpdating(true);
    try {
      const res = await fetch(`${apiBaseUrl}/api/festival/reset`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
      });
      if (!res.ok) throw new Error("Reset failed");
      toast({
        title: "Festival Settings Reset",
        description: "Custom selection and simulation fixtures cleared.",
      });
      onRefresh();
    } catch (err) {
      toast({
        title: "Reset error",
        description: String(err),
        variant: "destructive",
      });
    } finally {
      setIsUpdating(false);
    }
  };

  // Find festival for a given Date
  const getFestivalForDate = (dateObj: Date): FestivalRecord | undefined => {
    const year = dateObj.getFullYear();
    const month = String(dateObj.getMonth() + 1).padStart(2, "0");
    const day = String(dateObj.getDate()).padStart(2, "0");
    const iso = `${year}-${month}-${day}`;
    return festivals.find((f) => f.iso_date === iso);
  };

  const selectedFestivalObj = selectedDate ? getFestivalForDate(selectedDate) : undefined;
  const isModeOn = Boolean(festivalStatus?.mode_enabled);
  const isRangPanchami = Boolean(festivalStatus?.is_rang_panchami);
  const isBlocked = Boolean(festivalStatus?.automatic_start_blocked);

  return (
    <Dialog open={isOpen} onOpenChange={(open) => !open && onClose()}>
      <DialogContent className="max-w-3xl max-h-[90vh] overflow-y-auto border-border bg-card text-card-foreground">
        <DialogHeader>
          <div className="flex items-center justify-between pr-6">
            <div className="flex items-center gap-2.5">
              <Sparkles className="h-6 w-6 text-amber-400" />
              <DialogTitle className="text-xl font-bold">
                Holiday / Festival Pump Control Policy
              </DialogTitle>
            </div>
          </div>
          <DialogDescription className="text-sm text-muted-foreground">
            Context-aware automated pump control policy with deterministic festival restrictions.
          </DialogDescription>
        </DialogHeader>

        <div className="space-y-6 pt-2">
          {/* Top Control Bar: Mode Toggle + Status Badge */}
          <div className="flex flex-wrap items-center justify-between gap-4 rounded-xl border border-border bg-accent/30 p-4">
            <div className="flex items-center gap-3">
              <Switch
                id="festival-mode-toggle"
                checked={isModeOn}
                disabled={isUpdating}
                onCheckedChange={handleToggleMode}
              />
              <label
                htmlFor="festival-mode-toggle"
                className="cursor-pointer text-sm font-semibold text-foreground"
              >
                Festival Mode: {isModeOn ? "ENABLED" : "DISABLED"}
              </label>
            </div>
            <div className="flex items-center gap-2">
              <span className="text-xs text-muted-foreground">Current Time (IST):</span>
              <Badge variant="outline" className="font-mono text-xs">
                {festivalStatus?.current_ist_time ?? "--:--"}
              </Badge>
              <Badge
                variant={isModeOn ? (isBlocked ? "destructive" : "default") : "secondary"}
                className="text-xs"
              >
                {festivalStatus?.status ?? "INACTIVE"}
              </Badge>
            </div>
          </div>

          {/* Special Rang Panchami Card if Active */}
          {isModeOn && isRangPanchami && (
            <Card
              className={`p-4 border ${
                isBlocked
                  ? "border-amber-500/50 bg-amber-500/10"
                  : "border-green-500/50 bg-green-500/10"
              }`}
            >
              <div className="flex items-start gap-3">
                {isBlocked ? (
                  <ShieldAlert className="h-6 w-6 text-amber-500 shrink-0 mt-0.5" />
                ) : (
                  <CheckCircle2 className="h-6 w-6 text-green-500 shrink-0 mt-0.5" />
                )}
                <div className="space-y-1.5 flex-1">
                  <div className="flex items-center justify-between">
                    <h4 className="font-bold text-base flex items-center gap-2">
                      RANG PANCHAMI SPECIAL PUMP POLICY
                      <Badge variant={isBlocked ? "destructive" : "default"}>
                        {isBlocked ? "RESTRICTION ACTIVE" : "RESTRICTION RELEASED"}
                      </Badge>
                    </h4>
                    <span className="text-xs font-semibold text-muted-foreground flex items-center gap-1">
                      <Clock className="h-3.5 w-3.5" /> Release: 07:00 PM IST
                    </span>
                  </div>
                  <div className="text-sm font-medium">
                    Automatic Start:{" "}
                    <span
                      className={`font-bold ${
                        isBlocked ? "text-red-500" : "text-green-500"
                      }`}
                    >
                      {isBlocked ? "BLOCKED UNTIL 07:00 PM" : "ENABLED"}
                    </span>
                  </div>
                  <p className="text-xs text-muted-foreground">{festivalStatus?.reason}</p>
                </div>
              </div>
            </Card>
          )}

          {/* Normal Festival Card if non-Rang Panchami */}
          {isModeOn && !isRangPanchami && festivalStatus?.festival_name && (
            <Card className="p-4 border border-blue-500/30 bg-blue-500/10">
              <div className="flex items-center justify-between">
                <div>
                  <h4 className="font-bold text-sm text-foreground">
                    Festival: {festivalStatus.festival_name}
                  </h4>
                  <p className="text-xs text-muted-foreground">
                    Normal Schedule Active — standard automatic threshold & ML controls operate.
                  </p>
                </div>
                <Badge variant="outline">NORMAL POLICY</Badge>
              </div>
            </Card>
          )}

          {/* Calendar & Festival Browser Section */}
          <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
            <div>
              <h3 className="text-sm font-semibold mb-2 flex items-center gap-2">
                <CalendarIcon className="h-4 w-4 text-primary" />
                Festival Calendar
              </h3>
              <div className="rounded-md border border-border bg-card p-2 flex justify-center">
                <Calendar
                  mode="single"
                  selected={selectedDate}
                  onSelect={(date) => {
                    if (date) {
                      setSelectedDate(date);
                      const f = getFestivalForDate(date);
                      if (f) {
                        void handleSelectFestival(f);
                      }
                    }
                  }}
                  month={selectedMonth}
                  onMonthChange={setSelectedMonth}
                  modifiers={{
                    festival: (date) => Boolean(getFestivalForDate(date)),
                    rangPanchami: (date) =>
                      getFestivalForDate(date)?.control_policy === "RANG_PANCHAMI",
                  }}
                  modifiersClassNames={{
                    festival: "bg-blue-500/20 text-blue-400 font-bold",
                    rangPanchami: "bg-amber-500/30 text-amber-400 font-extrabold border border-amber-500",
                  }}
                />
              </div>
              <div className="mt-2 flex items-center justify-center gap-4 text-xs text-muted-foreground">
                <span className="flex items-center gap-1.5">
                  <span className="h-2.5 w-2.5 rounded-full bg-blue-500/40" /> Normal Festival
                </span>
                <span className="flex items-center gap-1.5">
                  <span className="h-2.5 w-2.5 rounded-full bg-amber-500 border border-amber-400" /> Rang Panchami (Special)
                </span>
              </div>
            </div>

            {/* Selected Date Details */}
            <div className="space-y-4">
              <h3 className="text-sm font-semibold flex items-center gap-2">
                <Sparkles className="h-4 w-4 text-primary" />
                Festival Details
              </h3>
              <Card className="p-4 border-border bg-accent/10 space-y-3">
                {selectedFestivalObj ? (
                  <>
                    <div className="flex items-center justify-between">
                      <h4 className="font-bold text-base text-foreground">
                        {selectedFestivalObj.event}
                      </h4>
                      <Badge
                        variant={
                          selectedFestivalObj.control_policy === "RANG_PANCHAMI"
                            ? "default"
                            : "secondary"
                        }
                      >
                        {selectedFestivalObj.control_policy}
                      </Badge>
                    </div>
                    <div className="text-xs text-muted-foreground space-y-1">
                      <div>Date: <span className="font-mono text-foreground">{selectedFestivalObj.date_str}</span></div>
                      <div>Type: <span className="text-foreground">{selectedFestivalObj.type}</span></div>
                    </div>
                    <Button
                      size="sm"
                      className="w-full"
                      onClick={() => handleSelectFestival(selectedFestivalObj)}
                      disabled={isUpdating}
                    >
                      Apply Festival Policy
                    </Button>
                  </>
                ) : (
                  <div className="py-6 text-center text-xs text-muted-foreground">
                    No festival recorded on this date. Click a highlighted date to inspect and apply.
                  </div>
                )}
              </Card>

              {/* Developer / Demo Simulation Box */}
              <div className="rounded-lg border border-dashed border-border p-3 space-y-2.5 bg-accent/5">
                <div className="flex items-center justify-between">
                  <span className="text-xs font-semibold flex items-center gap-1.5 text-muted-foreground">
                    <FlaskConical className="h-3.5 w-3.5 text-amber-400" />
                    Developer Test & Simulation
                  </span>
                  {festivalStatus?.simulation?.is_simulating && (
                    <Badge variant="outline" className="text-[10px] text-amber-400 border-amber-400">
                      Simulating Active
                    </Badge>
                  )}
                </div>
                <div className="flex flex-col gap-2">
                  <Button
                    variant="outline"
                    size="sm"
                    className="w-full justify-between h-auto py-2 px-3 text-xs font-normal border-border hover:bg-accent whitespace-normal"
                    onClick={() => handleSimulate("2027-03-27", "14:45")}
                    disabled={isUpdating}
                  >
                    <span className="font-medium text-foreground">RP @ 2:45 PM</span>
                    <Badge variant="destructive" className="text-[10px] ml-2 font-semibold shrink-0">
                      Blocked
                    </Badge>
                  </Button>
                  <Button
                    variant="outline"
                    size="sm"
                    className="w-full justify-between h-auto py-2 px-3 text-xs font-normal border-border hover:bg-accent whitespace-normal"
                    onClick={() => handleSimulate("2027-03-27", "19:01")}
                    disabled={isUpdating}
                  >
                    <span className="font-medium text-foreground">RP @ 7:01 PM</span>
                    <Badge variant="default" className="text-[10px] ml-2 font-semibold shrink-0 bg-green-600 hover:bg-green-700">
                      Released
                    </Badge>
                  </Button>
                </div>
                <div className="flex justify-end gap-2 pt-1">
                  <Button
                    variant="ghost"
                    size="sm"
                    className="text-xs h-7 text-muted-foreground"
                    onClick={handleReset}
                    disabled={isUpdating}
                  >
                    <RotateCcw className="h-3 w-3 mr-1" /> Reset All
                  </Button>
                </div>
              </div>
            </div>
          </div>
        </div>
      </DialogContent>
    </Dialog>
  );
}
