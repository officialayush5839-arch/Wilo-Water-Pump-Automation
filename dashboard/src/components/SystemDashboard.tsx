import { Card } from "@/components/ui/card";
import { StatusCard } from "./StatusCard";
import { Activity, Cpu, Wifi, Zap, Clock, Target } from "lucide-react";

interface SystemDashboardProps {
  systemStatus: {
    pumpStatus: string;
    aiConfidence: string;
    sensorHealth: string;
    uptime: string;
    networkStatus: string;
  };
  aiPredictions: {
    nextStart: string;
    duration: string;
    dataSource: string;
    reliability: string;
  };
}

export function SystemDashboard({ systemStatus, aiPredictions }: SystemDashboardProps) {
  const getSensorVariant = (health: string) => {
    if (health.includes("Live")) return "success";
    if (health.includes("waiting") || health.includes("Waiting")) return "warning";
    return "error";
  };

  const getNetworkVariant = (status: string) => {
    return status.includes("Connected") ? "success" : "error";
  };

  const getReliabilityVariant = (reliability: string) => {
    if (reliability === "High") return "success";
    if (reliability === "Medium") return "warning";
    return "error";
  };

  return (
    <div className="grid grid-cols-1 lg:grid-cols-2 gap-6 mb-8">
      <Card className="p-6 bg-card border-border">
        <div className="flex items-center gap-3 mb-6">
          <Activity className="h-6 w-6 text-primary" />
          <h2 className="text-xl font-semibold text-foreground">System Status</h2>
        </div>
        <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
          <StatusCard
            title="Pump Status"
            value={systemStatus.pumpStatus}
            variant={systemStatus.pumpStatus === "RUNNING" ? "success" : "default"}
            icon={<Zap className="h-4 w-4" />}
          />
          <StatusCard
            title="AI Confidence"
            value={systemStatus.aiConfidence}
            icon={<Cpu className="h-4 w-4" />}
          />
          <StatusCard
            title="Sensor Health"
            value={systemStatus.sensorHealth}
            variant={getSensorVariant(systemStatus.sensorHealth)}
            icon={<Activity className="h-4 w-4" />}
          />
          <StatusCard
            title="Network Status"
            value={systemStatus.networkStatus}
            variant={getNetworkVariant(systemStatus.networkStatus)}
            icon={<Wifi className="h-4 w-4" />}
          />
        </div>
        <div className="mt-4">
          <StatusCard
            title="System Uptime"
            value={systemStatus.uptime}
            icon={<Clock className="h-4 w-4" />}
          />
        </div>
      </Card>

      <Card className="p-6 bg-card border-border">
        <div className="flex items-center gap-3 mb-6">
          <Target className="h-6 w-6 text-primary" />
          <h2 className="text-xl font-semibold text-foreground">AI Predictions</h2>
        </div>
        <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
          <StatusCard
            title="Next Start"
            value={aiPredictions.nextStart}
            icon={<Clock className="h-4 w-4" />}
          />
          <StatusCard
            title="Duration"
            value={aiPredictions.duration}
            icon={<Activity className="h-4 w-4" />}
          />
          <StatusCard
            title="Data Source"
            value={aiPredictions.dataSource}
            icon={<Cpu className="h-4 w-4" />}
          />
          <StatusCard
            title="Reliability"
            value={aiPredictions.reliability}
            variant={getReliabilityVariant(aiPredictions.reliability)}
            icon={<Target className="h-4 w-4" />}
          />
        </div>
      </Card>
    </div>
  );
}
