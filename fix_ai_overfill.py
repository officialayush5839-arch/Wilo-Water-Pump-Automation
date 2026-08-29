import os

PUMP_LOGIC = "src/controller/pump_logic.py"

with open(PUMP_LOGIC, "r", encoding="utf-8") as f:
    code = f.read()

old_ml_trigger = """                return self._on(PumpState.ON_ML_SCHEDULED, now,
                    f"ML schedule: {pred_h:.2f}h for {pred_d:.0f}min")"""

new_ml_trigger = """                # SAFETY CHECK: Cancel AI schedule if tank is already full
                if upper_pct is not None and upper_pct >= self.high:
                    return self._off(PumpState.OFF,
                        f"ML schedule skipped: tank already full ({upper_pct:.1f}% >= {self.high}%)")

                return self._on(PumpState.ON_ML_SCHEDULED, now,
                    f"ML schedule: {pred_h:.2f}h for {pred_d:.0f}min")"""

if old_ml_trigger in code:
    code = code.replace(old_ml_trigger, new_ml_trigger)
    with open(PUMP_LOGIC, "w", encoding="utf-8") as f:
        f.write(code)
    print("✅ Logic patched successfully! The AI will no longer pump if the tank is full.")
else:
    print("Could not find the ML trigger block. It may have already been patched.")
