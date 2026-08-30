import { useState, useEffect } from "react";
import { Button } from "@/components/ui/button";
import { Card } from "@/components/ui/card";
import { Switch } from "@/components/ui/switch";
import { Label } from "@/components/ui/label";
import { Progress } from "@/components/ui/progress";
import { Badge } from "@/components/ui/badge";
import { ChartContainer, ChartTooltip, ChartTooltipContent } from "@/components/ui/chart";
import { LineChart, Line, ResponsiveContainer, PieChart, Pie, Cell } from "recharts";
import { useNavigate } from "react-router-dom";
import {
    Settings,
    Power,
    AlertTriangle,
    Activity,
    Droplets,
    Gauge,
    Thermometer,
    Wifi,
    Calendar,
    Play,
    Pause,
    Trash2,
    RotateCcw,
    Plus,
    Clock,
    Moon,
    Sun,
    Zap,
    TrendingUp,
    ArrowLeft,
} from "lucide-react";
import { Input } from "@/components/ui/input";
import { useToast } from "@/hooks/use-toast";

function AdminDashboard() {
    const navigate = useNavigate();
    const { toast } = useToast();

    // System Override States
    const [systemOverride, setSystemOverride] = useState(false);
    const [pumpOverride, setPumpOverride] = useState(false);
    const [emergencyStop, setEmergencyStop] = useState(false);

    // Tank Status
    const [tankData, setTankData] = useState({
        masterTank: { level: 80, capacity: 10000, temperature: 22, currentVolume: 8000 },
        building1Tank: { level: 30, capacity: 5000, temperature: 21, currentVolume: 1500 },
        building2Tank: { level: 40, capacity: 5000, temperature: 23, currentVolume: 2000 }
    });

    // Pump Status
    const [pumpData, setPumpData] = useState({
        mainPump: { status: "standby", health: 95, pressure: 0, flow: 0 }
    });

    // Simulation state
    const [isSimulationRunning, setIsSimulationRunning] = useState(false);
    const [simulationInterval, setSimulationInterval] = useState<NodeJS.Timeout | null>(null);

    // Energy consumption tracking
    const [energyData, setEnergyData] = useState({
        currentUsage: 0,        // kW
        dailyConsumption: 45.2, // kWh
        weeklyConsumption: 312.5, // kWh
        efficiency: 92          // %
    });

    // Sensor Health
    const initialSensorData = {
        waterLevel: { status: "active", health: 98, lastReading: "2 min ago", history: [95, 96, 97, 98, 98] },
        pressure: { status: "active", health: 95, lastReading: "1 min ago", history: [92, 93, 94, 95, 95] },
        temperature: { status: "active", health: 92, lastReading: "3 min ago", history: [90, 91, 91, 92, 92] },
        flow: { status: "warning", health: 78, lastReading: "5 min ago", history: [82, 80, 79, 78, 78] },
        ph: { status: "active", health: 89, lastReading: "2 min ago", history: [87, 88, 88, 89, 89] },
        turbidity: { status: "error", health: 45, lastReading: "15 min ago", history: [65, 58, 52, 48, 45] },
        conductivity: { status: "active", health: 91, lastReading: "1 min ago", history: [89, 90, 90, 91, 91] }
    };

    const [sensorData, setSensorData] = useState({
        waterLevel: { status: "active", health: 98, lastReading: "2 min ago", history: [95, 96, 97, 98, 98] },
        pressure: { status: "active", health: 95, lastReading: "1 min ago", history: [92, 93, 94, 95, 95] },
        temperature: { status: "active", health: 92, lastReading: "3 min ago", history: [90, 91, 91, 92, 92] },
        flow: { status: "warning", health: 78, lastReading: "5 min ago", history: [82, 80, 79, 78, 78] },
        ph: { status: "active", health: 89, lastReading: "2 min ago", history: [87, 88, 88, 89, 89] },
        turbidity: { status: "error", health: 45, lastReading: "15 min ago", history: [65, 58, 52, 48, 45] },
        conductivity: { status: "active", health: 91, lastReading: "1 min ago", history: [89, 90, 90, 91, 91] }
    });



    // Manual Scheduling State
    const [isManualMode, setIsManualMode] = useState(false);
    const [scheduleDate, setScheduleDate] = useState(() => {
        const today = new Date();
        return today.toISOString().split('T')[0];
    });
    const [scheduleTime, setScheduleTime] = useState(() => {
        const now = new Date();
        now.setMinutes(now.getMinutes() + 1); // Default to 1 minute from now
        return now.toTimeString().slice(0, 5);
    });
    const [scheduleDuration, setScheduleDuration] = useState("30");
    const [scheduledTasks, setScheduledTasks] = useState<Array<{
        id: string;
        date: string;
        time: string;
        duration: string;
        status: "scheduled" | "running" | "completed" | "expired";
        type: "manual" | "routine" | "maintenance" | "emergency";
        timeoutId?: NodeJS.Timeout;
        endTimeoutId?: NodeJS.Timeout;
    }>>([]);

    // Water Cut Management
    const [waterCuts, setWaterCuts] = useState<Array<{
        id: string | number;
        area: string;
        startTime: string;
        endTime: string;
        reason: string;
        status: "active" | "scheduled";
    }>>([]);

    const fetchAdminWaterCuts = async () => {
        try {
            const res = await fetch("/api/water-cuts");
            if (res.ok) {
                const data = await res.json();
                if (data.ok && Array.isArray(data.cuts)) {
                    setWaterCuts(data.cuts.map((c: any) => {
                        const now = new Date();
                        const start = new Date(c.start_time);
                        const end = new Date(c.end_time);
                        const isActive = now >= start && now <= end;
                        return {
                            id: c.id,
                            area: c.reason || "Municipal Water Cut",
                            startTime: c.start_time ? c.start_time.split("T")[1]?.slice(0, 5) : "08:00",
                            endTime: c.end_time ? c.end_time.split("T")[1]?.slice(0, 5) : "18:00",
                            reason: `Target: ${c.target_reserve_pct}% (${c.pre_fill_hours}h lead)`,
                            status: isActive ? ("active" as const) : ("scheduled" as const)
                        };
                    }));
                }
            }
        } catch (e) {
            console.error("Failed to load water cuts in admin:", e);
        }
    };

    useEffect(() => {
        fetchAdminWaterCuts();
    }, []);

    const handleDeleteWaterCut = async (id: string | number) => {
        try {
            await fetch(`/api/water-cuts/${id}`, { method: "DELETE" });
        } catch (e) {
            console.error("Failed to delete water cut:", e);
        }
        setWaterCuts(prev => prev.filter(c => c.id !== id));
        toast({
            title: "Water Cut Removed",
            description: "The municipal water cut event was successfully deleted.",
        });
    };

    // Water Cut Form State
    const [newWaterCut, setNewWaterCut] = useState({
        area: "Sector C",
        startTime: "08:00",
        endTime: "12:00",
        reason: "Scheduled Maintenance"
    });
    const [showWaterCutForm, setShowWaterCutForm] = useState(false);

    const handleEmergencyStop = () => {
        const newState = !emergencyStop;
        setEmergencyStop(newState);

        if (newState) {
            // Stop all operations when emergency stop is activated
            stopSimulation();

            // Update sensor health to reflect emergency state
            setSensorData(prev => {
                const updatedSensors = { ...prev };
                Object.keys(updatedSensors).forEach(key => {
                    updatedSensors[key as keyof typeof updatedSensors] = {
                        ...updatedSensors[key as keyof typeof updatedSensors],
                        status: "error",
                        lastReading: "System halted"
                    };
                });
                return updatedSensors;
            });

            toast({
                title: "Emergency Stop Activated",
                description: "All pumps stopped immediately. System in safe mode.",
                variant: "destructive"
            });
        } else {
            // Reset sensor health when emergency stop is deactivated
            setSensorData(initialSensorData);

            toast({
                title: "Emergency Stop Deactivated",
                description: "System operations resumed. Sensors recalibrating.",
                variant: "default"
            });
        }
    };

    // Water flow simulation
    const startSimulation = () => {
        if (isSimulationRunning || emergencyStop) return;

        // Start the pump
        setPumpData({
            mainPump: {
                status: "running",
                health: 95,
                pressure: 2.8,
                flow: 120
            }
        });

        setIsSimulationRunning(true);

        // Update sensor data when simulation starts
        setSensorData(prev => ({
            ...prev,
            flow: {
                ...prev.flow,
                status: "active",
                health: Math.min(prev.flow.health + 10, 95),
                lastReading: "Active"
            },
            pressure: {
                ...prev.pressure,
                status: "active",
                health: 95,
                lastReading: "2.8 bar"
            }
        }));

        // Create interval to update tank levels
        const interval = setInterval(() => {
            setTankData(prev => {
                // Calculate new volumes
                const transferRate = 50; // 50L per second

                let masterVolume = prev.masterTank.currentVolume - transferRate;
                let building1Volume = prev.building1Tank.currentVolume + transferRate * 0.6; // 60% to building 1
                let building2Volume = prev.building2Tank.currentVolume + transferRate * 0.4; // 40% to building 2

                // Ensure volumes stay within capacity
                masterVolume = Math.max(0, masterVolume);
                building1Volume = Math.min(prev.building1Tank.capacity, building1Volume);
                building2Volume = Math.min(prev.building2Tank.capacity, building2Volume);

                // Calculate new levels as percentages
                const masterLevel = (masterVolume / prev.masterTank.capacity) * 100;
                const building1Level = (building1Volume / prev.building1Tank.capacity) * 100;
                const building2Level = (building2Volume / prev.building2Tank.capacity) * 100;

                // Update energy consumption data
                setEnergyData(prevEnergy => {
                    // Calculate energy consumption based on flow rate and pressure
                    const currentUsage = 2.5 + (Math.random() * 0.6); // Fluctuate between 2.5-3.1 kW
                    const dailyConsumption = prevEnergy.dailyConsumption + (currentUsage / 3600); // Add kWh (1 second worth)

                    return {
                        ...prevEnergy,
                        currentUsage: parseFloat(currentUsage.toFixed(2)),
                        dailyConsumption: parseFloat(dailyConsumption.toFixed(2)),
                        efficiency: Math.floor(90 + Math.random() * 5) // Random efficiency between 90-95%
                    };
                });

                // Update sensor readings based on current levels and simulation state
                setSensorData(prevSensor => {
                    // Randomly select a sensor to update for more dynamic display
                    const sensorKeys = Object.keys(prevSensor);
                    const randomSensor = sensorKeys[Math.floor(Math.random() * sensorKeys.length)] as keyof typeof prevSensor;

                    const updatedSensors = { ...prevSensor };

                    // Always update water level sensor
                    updatedSensors.waterLevel = {
                        ...updatedSensors.waterLevel,
                        lastReading: "Just now",
                        health: masterLevel < 20 ? 80 : 98
                    };

                    // Update the randomly selected sensor
                    if (randomSensor !== 'waterLevel') {
                        updatedSensors[randomSensor] = {
                            ...updatedSensors[randomSensor],
                            lastReading: "Just now",
                            // Small random fluctuation in health
                            health: Math.min(Math.max(updatedSensors[randomSensor].health + (Math.random() > 0.5 ? 1 : -1), 70), 99)
                        };
                    }

                    // Update flow sensor based on transfer rate
                    updatedSensors.flow = {
                        ...updatedSensors.flow,
                        lastReading: `${transferRate} L/s`,
                        health: Math.min(updatedSensors.flow.health + 0.2, 95) // Gradually improve as system runs
                    };

                    return updatedSensors;
                });

                // Stop simulation if master tank is empty or building tanks are full
                if (masterVolume <= 0 ||
                    (building1Volume >= prev.building1Tank.capacity &&
                        building2Volume >= prev.building2Tank.capacity)) {
                    stopSimulation();
                }

                return {
                    masterTank: {
                        ...prev.masterTank,
                        level: Math.round(masterLevel),
                        currentVolume: Math.round(masterVolume)
                    },
                    building1Tank: {
                        ...prev.building1Tank,
                        level: Math.round(building1Level),
                        currentVolume: Math.round(building1Volume)
                    },
                    building2Tank: {
                        ...prev.building2Tank,
                        level: Math.round(building2Level),
                        currentVolume: Math.round(building2Volume)
                    }
                };
            });
        }, 1000);

        setSimulationInterval(interval);

        toast({
            title: "Pump Started",
            description: "Water transfer simulation started",
        });
    };

    const stopSimulation = () => {
        if (!isSimulationRunning) return;

        // Stop the pump
        setPumpData({
            mainPump: {
                status: "standby",
                health: 95,
                pressure: 0,
                flow: 0
            }
        });

        // Clear the interval
        if (simulationInterval) {
            clearInterval(simulationInterval);
            setSimulationInterval(null);
        }

        setIsSimulationRunning(false);

        toast({
            title: "Pump Stopped",
            description: "Water transfer simulation stopped",
        });
    };

    const resetSimulation = () => {
        // Stop any running simulation
        if (isSimulationRunning) {
            stopSimulation();
        }

        // Reset tank data to initial values
        setTankData({
            masterTank: { level: 80, capacity: 10000, temperature: 22, currentVolume: 8000 },
            building1Tank: { level: 30, capacity: 5000, temperature: 21, currentVolume: 1500 },
            building2Tank: { level: 40, capacity: 5000, temperature: 23, currentVolume: 2000 }
        });

        toast({
            title: "Simulation Reset",
            description: "Tank levels have been reset to initial values",
        });
    };

    const handlePumpToggle = (pumpId: string) => {
        if (pumpData[pumpId as keyof typeof pumpData].status === "running") {
            stopSimulation();
        } else {
            startSimulation();
        }
    };

    // Real-time scheduling functions
    const handleScheduleTask = () => {
        const taskDateTime = new Date(`${scheduleDate}T${scheduleTime}`);
        const now = new Date();
        const timeUntilStart = taskDateTime.getTime() - now.getTime();

        if (timeUntilStart <= 0) {
            toast({
                title: "Invalid Schedule Time",
                description: "Please select a future time for the task",
                variant: "destructive"
            });
            return;
        }

        const newTask = {
            id: `task-${Date.now()}`,
            date: scheduleDate,
            time: scheduleTime,
            duration: scheduleDuration,
            status: "scheduled" as const,
            type: "manual" as const
        };

        // Set timeout to start the task
        const startTimeoutId = setTimeout(() => {
            // Start the simulation
            startSimulation();

            // Update task status to running
            setScheduledTasks(prev =>
                prev.map(task =>
                    task.id === newTask.id
                        ? { ...task, status: "running" as const }
                        : task
                )
            );

            toast({
                title: "Scheduled Task Started",
                description: `Water transfer task is now running for ${scheduleDuration} seconds`,
            });

            // Set timeout to stop the task after duration
            const endTimeoutId = setTimeout(() => {
                stopSimulation();

                setScheduledTasks(prev =>
                    prev.map(task =>
                        task.id === newTask.id
                            ? { ...task, status: "completed" as const }
                            : task
                    )
                );

                toast({
                    title: "Scheduled Task Completed",
                    description: "Water transfer task finished successfully",
                });
            }, parseInt(scheduleDuration) * 1000);

            // Update the task with end timeout ID
            setScheduledTasks(prev =>
                prev.map(task =>
                    task.id === newTask.id
                        ? { ...task, endTimeoutId }
                        : task
                )
            );

        }, timeUntilStart);

        // Add the task with timeout ID
        const taskWithTimeout = { ...newTask, timeoutId: startTimeoutId };
        setScheduledTasks(prev => [...prev, taskWithTimeout]);

        const timeUntilStartMinutes = Math.round(timeUntilStart / 60000);
        toast({
            title: "Task Scheduled",
            description: `Water transfer will start in ${timeUntilStartMinutes} minute(s) and run for ${scheduleDuration} seconds`,
        });
    };

    const handleDeleteTask = (taskId: string) => {
        const task = scheduledTasks.find(t => t.id === taskId);

        // Clear any existing timeouts
        if (task?.timeoutId) {
            clearTimeout(task.timeoutId);
        }
        if (task?.endTimeoutId) {
            clearTimeout(task.endTimeoutId);
        }

        // If task is currently running, stop the simulation
        if (task?.status === "running") {
            stopSimulation();
        }

        setScheduledTasks(prev => prev.filter(task => task.id !== taskId));
        toast({
            title: "Task Deleted",
            description: "Scheduled task removed and any running operations stopped",
        });
    };

    const handleRunTask = (taskId: string) => {
        const task = scheduledTasks.find(t => t.id === taskId);
        if (!task || task.status !== "scheduled") return;

        // Clear the original start timeout since we're running now
        if (task.timeoutId) {
            clearTimeout(task.timeoutId);
        }

        // Start the simulation immediately
        startSimulation();

        // Update task status to running
        setScheduledTasks(prev =>
            prev.map(t =>
                t.id === taskId
                    ? { ...t, status: "running" as const, timeoutId: undefined }
                    : t
            )
        );

        toast({
            title: "Task Started Manually",
            description: `Water transfer task is now running for ${task.duration} seconds`,
        });

        // Set timeout to stop the task after duration
        const endTimeoutId = setTimeout(() => {
            stopSimulation();

            setScheduledTasks(prev =>
                prev.map(t =>
                    t.id === taskId
                        ? { ...t, status: "completed" as const, endTimeoutId: undefined }
                        : t
                )
            );

            toast({
                title: "Task Completed",
                description: "Water transfer task finished successfully",
            });
        }, parseInt(task.duration) * 1000);

        // Update the task with end timeout ID
        setScheduledTasks(prev =>
            prev.map(t =>
                t.id === taskId
                    ? { ...t, endTimeoutId }
                    : t
            )
        );
    };

    // Live sensor chart updates
    useEffect(() => {
        const sensorUpdateInterval = setInterval(() => {
            setSensorData(prev => {
                const updatedSensors = { ...prev };

                // Update each sensor's history with new data points
                Object.keys(updatedSensors).forEach(sensorKey => {
                    const sensor = updatedSensors[sensorKey as keyof typeof updatedSensors];
                    const currentHealth = sensor.health;

                    // Generate slight variation in health (±2%)
                    const variation = (Math.random() - 0.5) * 4;
                    let newHealth = currentHealth + variation;

                    // Keep health within realistic bounds based on sensor status
                    if (sensor.status === 'active') {
                        newHealth = Math.max(85, Math.min(99, newHealth));
                    } else if (sensor.status === 'warning') {
                        newHealth = Math.max(60, Math.min(85, newHealth));
                    } else if (sensor.status === 'error') {
                        newHealth = Math.max(20, Math.min(60, newHealth));
                    }

                    // Update history (keep last 10 points)
                    const newHistory = [...sensor.history.slice(-9), Math.round(newHealth)];

                    updatedSensors[sensorKey as keyof typeof updatedSensors] = {
                        ...sensor,
                        health: Math.round(newHealth),
                        history: newHistory
                    };
                });

                return updatedSensors;
            });
        }, 2000); // Update every 2 seconds

        return () => clearInterval(sensorUpdateInterval);
    }, []);

    // Cleanup timeouts on component unmount
    useEffect(() => {
        return () => {
            scheduledTasks.forEach(task => {
                if (task.timeoutId) clearTimeout(task.timeoutId);
                if (task.endTimeoutId) clearTimeout(task.endTimeoutId);
            });
        };
    }, [scheduledTasks]);



    const getTankColor = (level: number) => {
        if (level > 70) return "bg-blue-500";
        if (level > 30) return "bg-yellow-500";
        return "bg-red-500";
    };

    const getStatusColor = (status: string) => {
        switch (status) {
            case "active": case "running": return "bg-green-500";
            case "warning": case "standby": return "bg-yellow-500";
            case "error": case "maintenance": return "bg-red-500";
            default: return "bg-gray-500";
        }
    };

    // PieChartWithNeedle component
    const PieChartWithNeedle = ({ value, title }: { value: number; title: string }) => {
        const data = [
            { name: 'Used', value: value, fill: value > 80 ? '#22c55e' : value > 60 ? '#eab308' : '#ef4444' },
            { name: 'Remaining', value: 100 - value, fill: '#e5e7eb' }
        ];

        // Calculate needle angle (180 degrees for semicircle)
        const needleAngle = (value / 100) * 180 - 90; // -90 to start from left

        return (
            <div className="flex flex-col items-center">
                <div className="relative w-20 h-10 mb-1">
                    <ChartContainer
                        config={{
                            used: { label: "Used", color: data[0].fill },
                            remaining: { label: "Remaining", color: data[1].fill }
                        }}
                        className="w-full h-full"
                    >
                        <PieChart>
                            <Pie
                                data={data}
                                cx="50%"
                                cy="100%"
                                startAngle={180}
                                endAngle={0}
                                innerRadius={6}
                                outerRadius={16}
                                dataKey="value"
                            >
                                {data.map((entry, index) => (
                                    <Cell key={`cell-${index}`} fill={entry.fill} />
                                ))}
                            </Pie>
                        </PieChart>
                    </ChartContainer>

                    {/* Needle */}
                    <div
                        className="absolute bottom-0 left-1/2 w-0.5 h-4 bg-gray-800 origin-bottom transition-transform duration-500"
                        style={{ transform: `translateX(-50%) rotate(${needleAngle}deg)` }}
                    />

                    {/* Center dot */}
                    <div className="absolute bottom-0 left-1/2 w-1 h-1 bg-gray-800 rounded-full transform -translate-x-1/2" />
                </div>

                {/* Value display */}
                <div className="text-xs font-medium">{value}%</div>
                <div className="text-xs text-muted-foreground">{title}</div>
            </div>
        );
    };

    return (
        <div className="min-h-screen bg-background text-foreground">
            <div className="container mx-auto px-4 py-4 max-w-7xl">
                {/* Header */}
                <Card className="p-6 mb-6 bg-gradient-to-r from-red-600 to-red-700 text-white border-0 shadow-xl">
                    <div className="flex items-center justify-between">
                        <div className="flex items-center gap-3">
                            <Settings className="h-8 w-8" />
                            <div>
                                <h1 className="text-3xl font-bold">Admin Control Panel</h1>
                                <p className="text-red-100">Water Transfer System Management</p>
                            </div>
                        </div>
                        <div className="flex items-center gap-4">
                            <Button
                                onClick={() => navigate("/")}
                                variant="secondary"
                                size="lg"
                                className="flex items-center gap-2 border-white/30 bg-white/20 text-white hover:bg-white/30"
                            >
                                <ArrowLeft className="h-5 w-5" />
                                Live Dashboard
                            </Button>
                            <Button
                                onClick={handleEmergencyStop}
                                variant={emergencyStop ? "secondary" : "destructive"}
                                size="lg"
                                className="flex items-center gap-2"
                            >
                                <Power className="h-5 w-5" />
                                {emergencyStop ? "Resume System" : "Emergency Stop"}
                            </Button>
                        </div>
                    </div>
                </Card>

                {/* System Override Controls */}
                <div className="grid grid-cols-1 lg:grid-cols-3 gap-6 mb-6">
                    <Card className="p-6">
                        <div className="flex items-center gap-3 mb-4">
                            <Settings className="h-6 w-6 text-primary" />
                            <h3 className="text-lg font-semibold">System Override</h3>
                        </div>
                        <div className="space-y-4">
                            <div className="flex items-center justify-between">
                                <Label htmlFor="system-override">Manual Control</Label>
                                <Switch
                                    id="system-override"
                                    checked={systemOverride}
                                    onCheckedChange={setSystemOverride}
                                />
                            </div>
                            <div className="flex items-center justify-between">
                                <Label htmlFor="pump-override">Pump Override</Label>
                                <Switch
                                    id="pump-override"
                                    checked={pumpOverride}
                                    onCheckedChange={setPumpOverride}
                                />
                            </div>
                            <div className="flex items-center justify-between">
                                <Label htmlFor="emergency-stop">Emergency Mode</Label>
                                <Switch
                                    id="emergency-stop"
                                    checked={emergencyStop}
                                    onCheckedChange={setEmergencyStop}
                                />
                            </div>
                        </div>
                    </Card>

                    <Card className="p-6">
                        <div className="flex items-center gap-3 mb-4">
                            <Activity className="h-6 w-6 text-primary" />
                            <h3 className="text-lg font-semibold">System Status</h3>
                        </div>
                        <div className="space-y-3">
                            <div className="flex items-center justify-between">
                                <span className="text-sm">AI Control</span>
                                <Badge variant={systemOverride ? "destructive" : "default"}>
                                    {systemOverride ? "Manual" : "Auto"}
                                </Badge>
                            </div>
                            <div className="flex items-center justify-between">
                                <span className="text-sm">Network</span>
                                <div className="flex items-center gap-2">
                                    <Wifi className="h-4 w-4 text-green-500" />
                                    <span className="text-sm">Connected</span>
                                </div>
                            </div>
                            <div className="flex items-center justify-between">
                                <span className="text-sm">System Health</span>
                                <Badge variant="default" className="bg-green-500">Optimal</Badge>
                            </div>
                        </div>
                    </Card>

                    <Card className="p-6">
                        <div className="flex items-center gap-3 mb-4">
                            <AlertTriangle className="h-6 w-6 text-primary" />
                            <h3 className="text-lg font-semibold">Alerts</h3>
                        </div>
                        <div className="space-y-2">
                            <div className="flex items-center gap-2 text-sm">
                                <div className="w-2 h-2 bg-yellow-500 rounded-full"></div>
                                <span>Flow sensor degraded</span>
                            </div>
                            <div className="flex items-center gap-2 text-sm">
                                <div className="w-2 h-2 bg-red-500 rounded-full"></div>
                                <span>Turbidity sensor offline</span>
                            </div>
                            <div className="flex items-center gap-2 text-sm">
                                <div className="w-2 h-2 bg-blue-500 rounded-full"></div>
                                <span>Maintenance due in 3 days</span>
                            </div>
                        </div>
                    </Card>
                </div>

                {/* Tank Visualization */}
                <Card className="p-6 mb-6">
                    <div className="flex items-center gap-3 mb-6">
                        <Droplets className="h-6 w-6 text-primary" />
                        <h3 className="text-xl font-semibold">Tank Status & Visualization</h3>
                    </div>
                    <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
                        {Object.entries(tankData).map(([tankName, data]) => (
                            <div key={tankName} className="text-center">
                                <h4 className="font-semibold mb-4 capitalize">{tankName.replace(/([A-Z])/g, ' $1').trim()}</h4>

                                {/* 3D-like Tank Visualization */}
                                <div className="relative mx-auto mb-4" style={{ width: '120px', height: '160px' }}>
                                    {/* Tank Container */}
                                    <div className="absolute inset-0 border-4 border-gray-300 rounded-lg bg-gray-50">
                                        {/* Water Level */}
                                        <div
                                            className={`absolute bottom-0 left-0 right-0 ${getTankColor(data.level)} rounded-b-md transition-all duration-1000 opacity-80`}
                                            style={{ height: `${data.level}%` }}
                                        >
                                            {/* Water Animation Effect */}
                                            <div className="absolute top-0 left-0 right-0 h-2 bg-white opacity-30 animate-pulse"></div>
                                        </div>

                                    </div>

                                    {/* Tank Level Indicators - moved outside */}
                                    <div className="absolute -right-6 top-2 bottom-2 w-1 bg-gray-400 rounded"></div>

                                    {/* External Level Labels */}
                                    <div className="absolute -right-16 top-2 bottom-2 flex flex-col justify-between text-xs text-gray-600">
                                        <div>100%</div>
                                        <div>50%</div>
                                        <div>0%</div>
                                    </div>

                                    {/* Tank Cap */}
                                    <div className="absolute -top-2 left-2 right-2 h-4 bg-gray-400 rounded-t-lg border-2 border-gray-500"></div>

                                    {/* Pipes */}
                                    <div className="absolute -bottom-2 left-1/2 transform -translate-x-1/2 w-4 h-6 bg-gray-400 rounded-b"></div>
                                </div>

                                {/* Tank Data */}
                                <div className="space-y-2 text-sm">
                                    <div className="flex justify-between">
                                        <span>Level:</span>
                                        <span className="font-semibold">{data.level}%</span>
                                    </div>
                                    <div className="flex justify-between">
                                        <span>Capacity:</span>
                                        <span>{data.capacity}L</span>
                                    </div>
                                    <div className="flex justify-between">
                                        <span>Temp:</span>
                                        <span className="flex items-center gap-1">
                                            <Thermometer className="h-3 w-3" />
                                            {data.temperature}°C
                                        </span>
                                    </div>
                                    <Progress value={data.level} className="h-2 mt-2" />
                                </div>
                            </div>
                        ))}
                    </div>
                </Card>

                {/* Pump Status */}
                <Card className="p-6 mb-6">
                    <div className="flex items-center justify-between mb-6">
                        <div className="flex items-center gap-3">
                            <Gauge className="h-6 w-6 text-primary" />
                            <h3 className="text-xl font-semibold">Pump Control & Status</h3>
                        </div>
                        <Button
                            onClick={resetSimulation}
                            variant="outline"
                            className="flex items-center gap-2"
                        >
                            <RotateCcw className="h-4 w-4" />
                            Reset Simulation
                        </Button>
                    </div>
                    <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
                        {Object.entries(pumpData).map(([pumpName, data]) => (
                            <Card key={pumpName} className="p-4">
                                <div className="flex items-center justify-between mb-4">
                                    <h4 className="font-semibold capitalize">{pumpName.replace(/([A-Z])/g, ' $1').trim()}</h4>
                                    <div className="flex items-center gap-2">
                                        <div className={`w-3 h-3 rounded-full ${getStatusColor(data.status)} ${data.status === 'running' ? 'animate-pulse' : ''}`}></div>
                                        <Badge variant={data.status === 'running' ? 'default' : 'secondary'}>
                                            {data.status}
                                        </Badge>
                                    </div>
                                </div>

                                <div className="space-y-3">
                                    <div>
                                        <div className="flex justify-between text-sm mb-1">
                                            <span>Health</span>
                                            <span>{data.health}%</span>
                                        </div>
                                        <Progress value={data.health} className="h-2" />
                                    </div>

                                    {/* Small PieChartWithNeedle for pump usage */}
                                    <div className="flex justify-center py-2">
                                        <PieChartWithNeedle
                                            value={data.status === 'running' ? Math.round((data.flow / 150) * 100) : 0}
                                            title="Usage"
                                        />
                                    </div>

                                    <div className="grid grid-cols-2 gap-4 text-sm">
                                        <div>
                                            <span className="text-muted-foreground">Pressure</span>
                                            <div className="font-semibold">{data.pressure} bar</div>
                                        </div>
                                        <div>
                                            <span className="text-muted-foreground">Flow</span>
                                            <div className="font-semibold">{data.flow} L/min</div>
                                        </div>
                                    </div>

                                    <Button
                                        onClick={() => handlePumpToggle(pumpName)}
                                        variant={data.status === 'running' ? 'destructive' : 'default'}
                                        size="sm"
                                        className="w-full"
                                    >
                                        {data.status === 'running' ? (
                                            <>
                                                <Pause className="h-4 w-4 mr-2" />
                                                Stop Pump
                                            </>
                                        ) : (
                                            <>
                                                <Play className="h-4 w-4 mr-2" />
                                                Start Pump
                                            </>
                                        )}
                                    </Button>
                                </div>
                            </Card>
                        ))}

                        {/* Water Flow Visualization */}
                        <div className="col-span-1 md:col-span-2 p-4 bg-muted/20 rounded-lg">
                            <h4 className="font-semibold mb-4">Water Flow Visualization</h4>
                            <div className="relative h-40">
                                {/* Master Tank */}
                                <div className="absolute left-0 top-0 w-1/4 h-full flex flex-col items-center">
                                    <div className="text-sm font-medium mb-1">Master Tank</div>
                                    <div className="relative w-16 h-24 border-2 border-gray-400 rounded-md bg-gray-100">
                                        <div
                                            className={`absolute bottom-0 left-0 right-0 ${getTankColor(tankData.masterTank.level)} transition-all duration-500`}
                                            style={{ height: `${tankData.masterTank.level}%` }}
                                        ></div>
                                        <div className="absolute inset-0 flex items-center justify-center text-xs font-bold">
                                            {tankData.masterTank.level}%
                                        </div>
                                    </div>
                                </div>

                                {/* Flow Lines */}
                                <div className="absolute left-1/4 top-1/2 w-1/2 h-0 border-t-2 border-blue-500 transform -translate-y-1/2">
                                    {pumpData.mainPump.status === "running" && (
                                        <>
                                            <div className="absolute top-0 left-0 h-2 w-2 bg-blue-500 rounded-full animate-ping"></div>
                                            <div className="absolute top-0 left-1/4 h-2 w-2 bg-blue-500 rounded-full animate-ping" style={{ animationDelay: "0.2s" }}></div>
                                            <div className="absolute top-0 left-1/2 h-2 w-2 bg-blue-500 rounded-full animate-ping" style={{ animationDelay: "0.4s" }}></div>
                                            <div className="absolute top-0 left-3/4 h-2 w-2 bg-blue-500 rounded-full animate-ping" style={{ animationDelay: "0.6s" }}></div>
                                        </>
                                    )}
                                </div>

                                {/* Split Point */}
                                <div className="absolute left-3/4 top-1/2 transform -translate-y-1/2 -translate-x-1/2">
                                    <div className="w-4 h-4 bg-gray-400 rounded-full"></div>
                                    {pumpData.mainPump.status === "running" && (
                                        <>
                                            <div className="absolute top-0 left-0 right-0 bottom-0 bg-blue-500 rounded-full animate-pulse"></div>
                                            <div className="absolute top-0 w-2 h-10 border-r-2 border-blue-500"></div>
                                            <div className="absolute bottom-0 w-2 h-10 border-r-2 border-blue-500"></div>
                                        </>
                                    )}
                                </div>

                                {/* Building Tanks */}
                                <div className="absolute right-0 top-0 w-1/4 h-2/5 flex flex-col items-center">
                                    <div className="text-sm font-medium mb-1">Building 1</div>
                                    <div className="relative w-12 h-16 border-2 border-gray-400 rounded-md bg-gray-100">
                                        <div
                                            className={`absolute bottom-0 left-0 right-0 ${getTankColor(tankData.building1Tank.level)} transition-all duration-500`}
                                            style={{ height: `${tankData.building1Tank.level}%` }}
                                        ></div>
                                        <div className="absolute inset-0 flex items-center justify-center text-xs font-bold">
                                            {tankData.building1Tank.level}%
                                        </div>
                                    </div>
                                </div>

                                <div className="absolute right-0 bottom-0 w-1/4 h-2/5 flex flex-col items-center">
                                    <div className="text-sm font-medium mb-1">Building 2</div>
                                    <div className="relative w-12 h-16 border-2 border-gray-400 rounded-md bg-gray-100">
                                        <div
                                            className={`absolute bottom-0 left-0 right-0 ${getTankColor(tankData.building2Tank.level)} transition-all duration-500`}
                                            style={{ height: `${tankData.building2Tank.level}%` }}
                                        ></div>
                                        <div className="absolute inset-0 flex items-center justify-center text-xs font-bold">
                                            {tankData.building2Tank.level}%
                                        </div>
                                    </div>
                                </div>
                            </div>

                            <div className="mt-4 text-sm text-center text-muted-foreground">
                                {pumpData.mainPump.status === "running"
                                    ? "Water is flowing from Master Tank to Building Tanks"
                                    : "Pump is idle. Start the pump to transfer water."}
                            </div>
                        </div>
                    </div>
                </Card>



                {/* Sensor Health Monitor with Energy Consumption */}
                <Card className="p-6 mb-6">
                    <div className="flex items-center gap-3 mb-6">
                        <Activity className="h-6 w-6 text-primary" />
                        <h3 className="text-xl font-semibold">Sensor Health Monitor</h3>
                    </div>



                    {/* Sensor Health Grid */}
                    <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4">
                        {Object.entries(sensorData).map(([sensorName, data]) => (
                            <Card key={sensorName} className="p-4">
                                <div className="flex items-center justify-between mb-2">
                                    <h5 className="font-medium capitalize">{sensorName.replace(/([A-Z])/g, ' $1').trim()}</h5>
                                    <div className={`w-3 h-3 rounded-full ${getStatusColor(data.status)}`}></div>
                                </div>
                                <div className="space-y-2">
                                    <div>
                                        <div className="flex justify-between text-sm mb-1">
                                            <span>Health</span>
                                            <span>{data.health}%</span>
                                        </div>
                                        {/* Mini Chart */}
                                        <div className="h-8 w-full">
                                            <ResponsiveContainer width="100%" height="100%">
                                                <LineChart data={data.history.map((value, index) => ({ value, time: index }))}>
                                                    <Line
                                                        type="monotone"
                                                        dataKey="value"
                                                        stroke={data.status === 'active' ? '#22c55e' : data.status === 'warning' ? '#f59e0b' : '#ef4444'}
                                                        strokeWidth={2}
                                                        dot={false}
                                                        animationDuration={300}
                                                    />
                                                </LineChart>
                                            </ResponsiveContainer>
                                        </div>
                                    </div>
                                    <div className="text-xs text-muted-foreground">
                                        Last reading: {data.lastReading}
                                    </div>
                                    <Badge
                                        variant={data.status === 'active' ? 'default' : data.status === 'warning' ? 'secondary' : 'destructive'}
                                        className="text-xs"
                                    >
                                        {data.status}
                                    </Badge>
                                </div>
                            </Card>
                        ))}

                        {/* Energy Consumption Card */}
                        <Card className="p-4">
                            <div className="flex items-center justify-between mb-2">
                                <h5 className="font-medium">Energy Usage</h5>
                                <div className={`w-3 h-3 rounded-full ${pumpData.mainPump.status === "running" ? "bg-green-500" : "bg-gray-500"}`}></div>
                            </div>
                            <div className="space-y-2">
                                <div>
                                    <div className="flex justify-between text-sm mb-1">
                                        <span>Current</span>
                                        <span>{energyData.currentUsage} kW</span>
                                    </div>
                                    <Progress value={(energyData.currentUsage / 5) * 100} className="h-1" />
                                </div>
                                <div className="text-xs text-muted-foreground">
                                    Last reading: {pumpData.mainPump.status === "running" ? "Just now" : "Idle"}
                                </div>
                                <Badge
                                    variant={pumpData.mainPump.status === "running" ? 'default' : 'secondary'}
                                    className="text-xs"
                                >
                                    {pumpData.mainPump.status === "running" ? "active" : "standby"}
                                </Badge>
                            </div>
                        </Card>
                    </div>
                </Card>

                {/* Manual Scheduling Controls */}
                <Card className="p-6 mb-6">
                    <div className="flex items-center justify-between mb-6">
                        <div className="flex items-center gap-3">
                            <Settings className="h-6 w-6 text-primary" />
                            <h3 className="text-xl font-semibold">Manual Scheduling</h3>
                        </div>
                        <div className="flex items-center gap-2">
                            <Label htmlFor="manual-mode" className="text-sm font-medium">
                                Manual Mode
                            </Label>
                            <Switch
                                id="manual-mode"
                                checked={isManualMode}
                                onCheckedChange={setIsManualMode}
                            />
                        </div>
                    </div>

                    {isManualMode && (
                        <div className="space-y-6">
                            {/* Schedule New Task */}
                            <div className="grid grid-cols-1 md:grid-cols-4 gap-4 p-4 bg-muted/50 rounded-lg">
                                <div className="space-y-2">
                                    <Label htmlFor="schedule-date" className="text-sm font-medium flex items-center gap-2">
                                        <Calendar className="h-4 w-4" />
                                        Date
                                    </Label>
                                    <Input
                                        id="schedule-date"
                                        type="date"
                                        value={scheduleDate}
                                        onChange={(e) => setScheduleDate(e.target.value)}
                                        className="w-full"
                                    />
                                </div>

                                <div className="space-y-2">
                                    <Label htmlFor="schedule-time" className="text-sm font-medium flex items-center gap-2">
                                        <Clock className="h-4 w-4" />
                                        Time
                                    </Label>
                                    <Input
                                        id="schedule-time"
                                        type="time"
                                        value={scheduleTime}
                                        onChange={(e) => setScheduleTime(e.target.value)}
                                        className="w-full"
                                    />
                                </div>

                                <div className="space-y-2">
                                    <Label htmlFor="schedule-duration" className="text-sm font-medium flex items-center gap-2">
                                        <Activity className="h-4 w-4" />
                                        Duration (min)
                                    </Label>
                                    <Input
                                        id="schedule-duration"
                                        type="number"
                                        min="1"
                                        max="120"
                                        value={scheduleDuration}
                                        onChange={(e) => setScheduleDuration(e.target.value)}
                                        className="w-full"
                                        placeholder="45"
                                    />
                                </div>

                                <div className="flex items-end">
                                    <Button
                                        onClick={handleScheduleTask}
                                        className="w-full flex items-center gap-2"
                                    >
                                        <Play className="h-4 w-4" />
                                        Schedule Task
                                    </Button>
                                </div>
                            </div>

                            {/* Scheduled Tasks List */}
                            {scheduledTasks.length > 0 && (
                                <div className="space-y-3">
                                    <h4 className="text-md font-semibold text-foreground">Scheduled Tasks</h4>
                                    <div className="space-y-2">
                                        {scheduledTasks.map((task) => (
                                            <div
                                                key={task.id}
                                                className={`flex items-center justify-between p-3 rounded-lg border ${task.status === "running" ? "bg-blue-50 border-blue-200" :
                                                    task.status === "completed" ? "bg-green-50 border-green-200" :
                                                        "bg-gray-50 border-gray-200"
                                                    }`}
                                            >
                                                <div className="flex items-center gap-4">
                                                    <div className={`w-3 h-3 rounded-full ${task.status === "running" ? "bg-blue-500 animate-pulse" :
                                                        task.status === "completed" ? "bg-green-500" :
                                                            "bg-gray-400"
                                                        }`} />
                                                    <div className="text-sm">
                                                        <span className="font-medium">{task.date}</span> at{" "}
                                                        <span className="font-medium">{task.time}</span> for{" "}
                                                        <span className="font-medium">{task.duration} min</span>
                                                        <span className="ml-2 text-xs text-muted-foreground">({task.type})</span>
                                                    </div>
                                                    <div className={`px-2 py-1 rounded-full text-xs font-medium ${task.status === "running" ? "bg-blue-100 text-blue-700" :
                                                        task.status === "completed" ? "bg-green-100 text-green-700" :
                                                            "bg-gray-100 text-gray-700"
                                                        }`}>
                                                        {task.status.charAt(0).toUpperCase() + task.status.slice(1)}
                                                    </div>
                                                </div>

                                                <div className="flex items-center gap-2">
                                                    {task.status === "scheduled" && (
                                                        <Button
                                                            onClick={() => handleRunTask(task.id)}
                                                            size="sm"
                                                            variant="outline"
                                                            className="flex items-center gap-1"
                                                        >
                                                            <Play className="h-3 w-3" />
                                                            Run Now
                                                        </Button>
                                                    )}
                                                    <Button
                                                        onClick={() => handleDeleteTask(task.id)}
                                                        size="sm"
                                                        variant="outline"
                                                        className="text-red-600 hover:text-red-700"
                                                    >
                                                        Delete
                                                    </Button>
                                                </div>
                                            </div>
                                        ))}
                                    </div>
                                </div>
                            )}

                            {scheduledTasks.length === 0 && (
                                <div className="text-center py-8 text-muted-foreground">
                                    <Calendar className="h-12 w-12 mx-auto mb-3 opacity-50" />
                                    <p className="text-sm">No scheduled tasks. Create your first manual water transfer schedule above.</p>
                                </div>
                            )}
                        </div>
                    )}

                    {!isManualMode && (
                        <div className="text-center py-8 text-muted-foreground">
                            <Settings className="h-12 w-12 mx-auto mb-3 opacity-50" />
                            <p className="text-sm">Enable Manual Mode to schedule custom water transfer tasks</p>
                        </div>
                    )}
                </Card>

                {/* Water Cut Management */}
                <Card className="p-6">
                    <div className="flex items-center justify-between mb-6">
                        <div className="flex items-center gap-3">
                            <Calendar className="h-6 w-6 text-primary" />
                            <h3 className="text-xl font-semibold">Water Cut Management</h3>
                        </div>
                        <Button
                            className="flex items-center gap-2"
                            onClick={() => setShowWaterCutForm(!showWaterCutForm)}
                        >
                            <Plus className="h-4 w-4" />
                            Schedule Cut
                        </Button>
                    </div>

                    {/* Water Cut Form */}
                    {showWaterCutForm && (
                        <div className="mb-6 p-4 bg-muted/30 rounded-lg">
                            <h4 className="text-md font-semibold mb-4">Schedule New Water Cut</h4>
                            <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                                <div className="space-y-2">
                                    <Label htmlFor="area" className="text-sm">Area</Label>
                                    <Input
                                        id="area"
                                        value={newWaterCut.area}
                                        onChange={(e) => setNewWaterCut({ ...newWaterCut, area: e.target.value })}
                                    />
                                </div>
                                <div className="space-y-2">
                                    <Label htmlFor="reason" className="text-sm">Reason</Label>
                                    <Input
                                        id="reason"
                                        value={newWaterCut.reason}
                                        onChange={(e) => setNewWaterCut({ ...newWaterCut, reason: e.target.value })}
                                    />
                                </div>
                                <div className="space-y-2">
                                    <Label htmlFor="startTime" className="text-sm">Start Time</Label>
                                    <Input
                                        id="startTime"
                                        type="time"
                                        value={newWaterCut.startTime}
                                        onChange={(e) => setNewWaterCut({ ...newWaterCut, startTime: e.target.value })}
                                    />
                                </div>
                                <div className="space-y-2">
                                    <Label htmlFor="endTime" className="text-sm">End Time</Label>
                                    <Input
                                        id="endTime"
                                        type="time"
                                        value={newWaterCut.endTime}
                                        onChange={(e) => setNewWaterCut({ ...newWaterCut, endTime: e.target.value })}
                                    />
                                </div>
                            </div>
                            <div className="flex justify-end mt-4 gap-2">
                                <Button
                                    variant="outline"
                                    onClick={() => setShowWaterCutForm(false)}
                                >
                                    Cancel
                                </Button>
                                <Button
                                    onClick={async () => {
                                        const today = new Date().toISOString().split("T")[0];
                                        const payload = {
                                            start_time: `${today}T${newWaterCut.startTime}:00`,
                                            end_time: `${today}T${newWaterCut.endTime}:00`,
                                            reason: `${newWaterCut.area} - ${newWaterCut.reason}`,
                                            target_reserve_pct: 95.0,
                                            pre_fill_hours: 4.0,
                                        };

                                        try {
                                            const res = await fetch("/api/water-cuts", {
                                                method: "POST",
                                                headers: { "Content-Type": "application/json" },
                                                body: JSON.stringify(payload),
                                            });
                                            if (res.ok) {
                                                toast({
                                                    title: "Water Cut Scheduled",
                                                    description: `${newWaterCut.area} scheduled from ${newWaterCut.startTime} to ${newWaterCut.endTime}`,
                                                });
                                                fetchAdminWaterCuts();
                                            } else {
                                                const err = await res.json();
                                                toast({
                                                    title: "Scheduling Failed",
                                                    description: err.error || "Failed to save water cut",
                                                    variant: "destructive",
                                                });
                                            }
                                        } catch (e) {
                                            console.error("Failed to post water cut:", e);
                                        }

                                        setShowWaterCutForm(false);
                                    }}
                                >
                                    Schedule
                                </Button>
                            </div>
                        </div>
                    )}

                    <div className="space-y-4">
                        {waterCuts.map((cut) => (
                            <Card key={cut.id} className="p-4">
                                <div className="flex items-center justify-between">
                                    <div className="flex items-center gap-4">
                                        <div className={`w-4 h-4 rounded-full ${cut.status === 'active' ? 'bg-red-500 animate-pulse' : 'bg-yellow-500'}`}></div>
                                        <div>
                                            <h5 className="font-semibold">{cut.area}</h5>
                                            <p className="text-sm text-muted-foreground">
                                                {cut.startTime} - {cut.endTime} | {cut.reason}
                                            </p>
                                        </div>
                                    </div>
                                    <div className="flex items-center gap-2">
                                        <Badge variant={cut.status === 'active' ? 'destructive' : 'secondary'}>
                                            {cut.status}
                                        </Badge>
                                        {cut.status === 'scheduled' && (
                                            <Button
                                                variant="outline"
                                                size="sm"
                                                onClick={() => {
                                                    // Activate the water cut
                                                    setWaterCuts(prev =>
                                                        prev.map(c =>
                                                            c.id === cut.id ? { ...c, status: 'active' } : c
                                                        )
                                                    );

                                                    // Start the simulation
                                                    startSimulation();

                                                    // Update sensor data
                                                    setSensorData(prev => ({
                                                        ...prev,
                                                        flow: {
                                                            ...prev.flow,
                                                            status: "warning",
                                                            health: Math.max(prev.flow.health - 15, 30),
                                                            lastReading: "Cut active"
                                                        }
                                                    }));

                                                    toast({
                                                        title: "Water Cut Activated",
                                                        description: `${cut.area} water cut is now active`,
                                                        variant: "destructive"
                                                    });
                                                }}
                                            >
                                                Activate
                                            </Button>
                                        )}
                                        <Button
                                            variant="outline"
                                            size="sm"
                                            onClick={() => {
                                                handleDeleteWaterCut(cut.id);

                                                // If this was an active cut, update sensor data
                                                if (cut.status === 'active') {
                                                    setSensorData(prev => ({
                                                        ...prev,
                                                        flow: {
                                                            ...prev.flow,
                                                            status: "active",
                                                            health: Math.min(prev.flow.health + 10, 90),
                                                            lastReading: "1 min ago"
                                                        }
                                                    }));

                                                    // Stop the simulation if it was running
                                                    if (isSimulationRunning) {
                                                        stopSimulation();
                                                    }
                                                }
                                            }}
                                        >
                                            <Trash2 className="h-4 w-4" />
                                        </Button>
                                    </div>
                                </div>
                            </Card>
                        ))}

                        {waterCuts.length === 0 && (
                            <div className="text-center py-8 text-muted-foreground">
                                <Calendar className="h-12 w-12 mx-auto mb-3 opacity-50" />
                                <p className="text-sm">No water cuts scheduled. Use the Schedule Cut button to create one.</p>
                            </div>
                        )}
                    </div>
                </Card>
            </div>
        </div>
    );
}

export default AdminDashboard;