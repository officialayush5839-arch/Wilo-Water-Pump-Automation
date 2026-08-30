import { Card } from "@/components/ui/card";
import { cn } from "@/lib/utils";

interface StatusCardProps {
  title: string;
  value: string;
  variant?: "default" | "success" | "warning" | "error";
  icon?: React.ReactNode;
  trend?: "up" | "down" | "stable";
}

export function StatusCard({ title, value, variant = "default", icon, trend }: StatusCardProps) {
  const getVariantClasses = () => {
    switch (variant) {
      case "success":
        return "bg-gradient-success border-green-success/20";
      case "warning":
        return "bg-gradient-warning border-orange-warning/20";
      case "error":
        return "bg-gradient-error border-red-error/20";
      default:
        return "bg-gradient-primary border-blue-primary/20";
    }
  };

  const getTrendIcon = () => {
    if (!trend) return null;
    switch (trend) {
      case "up":
        return <span className="text-green-success">↗</span>;
      case "down":
        return <span className="text-red-error">↘</span>;
      case "stable":
        return <span className="text-muted-foreground">→</span>;
    }
  };

  return (
    <Card className={cn(
      "p-4 text-white border-2 transition-all duration-200 hover:scale-105 hover:shadow-lg",
      getVariantClasses()
    )}>
      <div className="flex items-center justify-between mb-2">
        <h4 className="text-sm font-medium opacity-90">{title}</h4>
        {icon && <div className="opacity-80">{icon}</div>}
      </div>
      <div className="flex items-center gap-2">
        <span className="text-2xl font-bold">{value}</span>
        {getTrendIcon()}
      </div>
    </Card>
  );
}