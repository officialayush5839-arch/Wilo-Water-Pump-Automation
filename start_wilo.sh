#!/bin/bash
echo "🧹 Cleaning up any old ghost processes..."
pkill -f "src/controller/pump_controller.py"
pkill -f "src/dashboard/server.py"
sleep 1

# Catch Ctrl+C and kill all background jobs automatically!
trap 'echo -e "\n🛑 Stopping all Wilo systems cleanly..."; kill $(jobs -p) 2>/dev/null; exit' SIGINT SIGTERM EXIT

echo "🚀 Starting Pump Controller..."
python3 src/controller/pump_controller.py &

echo "🚀 Starting Flask API..."
python3 src/dashboard/server.py &

echo "🚀 Starting React Dashboard..."
cd dashboard
npm run dev -- --host 0.0.0.0 --port 8082
