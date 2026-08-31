import os
import signal
import subprocess
import sys
import time
import urllib.request
import webbrowser

PROJECT_ROOT = os.path.dirname(os.path.abspath(__file__))
BACKEND_DIR = os.path.join(PROJECT_ROOT, "backend")
FRONTEND_FILE = os.path.join(PROJECT_ROOT, "frontend", "index.html")
PYTHON_EXE = sys.executable

print("=" * 65)
print(" SafeTrack - SIH Clean Demo Launcher")
print(" FastAPI + ESP32-S3 Simulator + Dashboard")
print("=" * 65)

env_override = os.environ.copy()
env_override["DATABASE_URL"] = "sqlite:///./safetrack.db"
env_override["DEMO_RESET"] = "true"
env_override["PYTHONPATH"] = f"{PROJECT_ROOT};{BACKEND_DIR}"

print("\n[1/3] Starting FastAPI Backend on http://127.0.0.1:8000 ...")
server_process = subprocess.Popen(
    [
        PYTHON_EXE,
        "-m",
        "uvicorn",
        "backend.main:app",
        "--host",
        "127.0.0.1",
        "--port",
        "8000",
    ],
    cwd=PROJECT_ROOT,
    env=env_override,
)

print("Waiting for FastAPI server to initialize...")
server_ready = False
for _ in range(20):
    try:
        with urllib.request.urlopen(
            "http://127.0.0.1:8000/docs", timeout=1
        ) as response:
            if response.status == 200:
                server_ready = True
                print("[SUCCESS] FastAPI Backend is live!")
                break
    except Exception:
        time.sleep(1)

if not server_ready:
    print("\n[ERROR] FastAPI server failed to start.")
    server_process.terminate()
    sys.exit(1)

print("\n[2/3] Starting ESP32-S3 Sensor Simulator...")
simulator_process = subprocess.Popen(
    [PYTHON_EXE, "simulate_esp32.py"],
    cwd=BACKEND_DIR,
    env=env_override,
)
print("[SUCCESS] ESP32-S3 Simulator running.")

print("\n[3/3] Launching Web Dashboard...")
if os.path.exists(FRONTEND_FILE):
    webbrowser.open(f"file:///{os.path.abspath(FRONTEND_FILE)}")
    print("[SUCCESS] Dashboard opened.")
else:
    print(f"[WARNING] Frontend file not found: {FRONTEND_FILE}")

print("\n" + "=" * 65)
print(" SafeTrack SIH Demo Running")
print(" Seal: INTACT while LDR < 800 LUX")
print(" Incident store: CLEANED at startup")
print(" Press Ctrl+C to stop all components.")
print("=" * 65)

try:
    server_process.wait()
except KeyboardInterrupt:
    print("\nShutting down...")
    if simulator_process:
        simulator_process.terminate()
    if server_process:
        server_process.terminate()
    print("SafeTrack stopped.")
