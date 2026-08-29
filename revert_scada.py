import os
import shutil

ADMIN_TSX = "dashboard/src/components/AdminDashboard.tsx"
SERVER_PY = "src/dashboard/server.py"

def restore(file_path):
    if os.path.exists(file_path + ".backup"):
        shutil.copy(file_path + ".backup", file_path)
        print(f"Restored {file_path}")
    else:
        print(f"No backup found for {file_path}")

print("Reverting changes...")
restore(ADMIN_TSX)
restore(SERVER_PY)
print("✅ Revert completed! Please restart your Flask and React servers to pick up the original files.")
