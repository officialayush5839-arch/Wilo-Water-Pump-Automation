import os
import re

WILO_SIM = "dashboard/src/components/WiloSimulation.tsx"

with open(WILO_SIM, "r", encoding="utf-8") as f:
    w_code = f.read()

if "Power Consumption" not in w_code:
    # Safely find the exact insertion point using Regex
    search_pattern = r'(<div className="space-y-4">\s*)(<div className="flex items-center justify-between">\s*<span className="text-sm">Current Pump Status</span>)'
    
    replacement = r'''\1<div className="flex items-center justify-between">
                  <span className="text-sm font-semibold text-primary">Power Consumption</span>
                  <span className="text-sm font-bold text-primary">
                    {mainsVoltage !== null ? `${Math.round(mainsVoltage)}V` : "--V"} @ {mainsCurrent !== null ? `${mainsCurrent.toFixed(2)}A` : "--A"}
                  </span>
                </div>
                \2'''
                
    w_code_new = re.sub(search_pattern, replacement, w_code, count=1)
    
    if w_code_new != w_code:
        with open(WILO_SIM, "w", encoding="utf-8") as f:
            f.write(w_code_new)
        print("✅ Dashboard UI fixed successfully!")
    else:
        print("❌ Could not find UI insertion point.")
else:
    print("Dashboard already has Power Consumption!")
