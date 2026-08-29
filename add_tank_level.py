import sys
import os

WILO_TSX = "dashboard/src/components/WiloSimulation.tsx"

if not os.path.exists(WILO_TSX):
    print(f"Error: Could not find {WILO_TSX}")
    sys.exit(1)

with open(WILO_TSX, "r", encoding="utf-8") as f:
    code = f.read()

# 1. Add state variable
if "const [tankLevelPct, setTankLevelPct]" not in code:
    code = code.replace(
        "const [pressureKpa, setPressureKpa] = useState<number | null>(null);",
        "const [pressureKpa, setPressureKpa] = useState<number | null>(null);\n  const [tankLevelPct, setTankLevelPct] = useState<number | null>(null);"
    )

# 2. Update state from the live backend payload
if "setTankLevelPct(" not in code:
    code = code.replace(
        "setPressureKpa(nextPressure);",
        "setPressureKpa(nextPressure);\n    setTankLevelPct(payload.runtime?.upper_pct ?? null);"
    )

# 3. Add UI progress bar block in the System Health card
ui_block = """
              <div>
                <div className="mb-1 flex justify-between text-sm items-center">
                  <span>Tank Level</span>
                  <span className="font-bold text-blue-400">{tankLevelPct !== null ? `${tankLevelPct.toFixed(1)}%` : "--"}</span>
                </div>
                <Progress value={tankLevelPct ?? 0} className="h-2 bg-slate-800 [&>div]:bg-blue-500" />
              </div>"""

if "Tank Level" not in code:
    code = code.replace(
        "<div className=\"space-y-3\">",
        "<div className=\"space-y-3\">\n" + ui_block
    )

with open(WILO_TSX, "w", encoding="utf-8") as f:
    f.write(code)

print("✅ Successfully added Tank Level to the main dashboard UI!")
