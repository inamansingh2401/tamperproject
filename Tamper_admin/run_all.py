import os
import subprocess
import sys
import time
import urllib.request
import webbrowser

PROJECT_ROOT = os.path.dirname(os.path.abspath(__file__))

# Admin project paths
BACKEND_DIR = os.path.join(PROJECT_ROOT, "backend")
ADMIN_FRONTEND_DIR = os.path.join(PROJECT_ROOT, "frontend")

USER_PROJECT_ROOT = os.path.join(
    os.path.dirname(PROJECT_ROOT),
    "Tamper_user"
)

USER_FRONTEND_DIR = os.path.join(
    USER_PROJECT_ROOT,
    "frontend"
)

PYTHON_EXE = sys.executable

BACKEND_HOST = "0.0.0.0"
LOCAL_HOST = "127.0.0.1"
BACKEND_PORT = 8000

ADMIN_PORT = 5501
USER_PORT = 5500

BACKEND_URL = f"http://{LOCAL_HOST}:{BACKEND_PORT}"
ADMIN_URL = f"http://{LOCAL_HOST}:{ADMIN_PORT}/login.html"
USER_URL = f"http://{LOCAL_HOST}:{USER_PORT}"


# ============================================================
# PRINT HEADER
# ============================================================

print("=" * 70)
print(" SafeTrack MASTER LAUNCHER")
print(" Backend + Sensor Source + Admin + User Dashboard")
print("=" * 70)


# ============================================================
# ENVIRONMENT (FIXED FOR MAC/LINUX & WINDOWS)
# ============================================================

env_override = os.environ.copy()

env_override.setdefault("DATABASE_URL", "sqlite:///./safetrack.db")
env_override["DEMO_RESET"] = "false"

# Real hardware is the default for the live demonstration.
# Simulator is only enabled if explicitly requested via --simulator argument or SAFETRACK_SIMULATOR=true environment variable.
SIMULATOR_ENABLED = ("--simulator" in sys.argv) or (os.getenv("SAFETRACK_SIMULATOR", "false").lower() == "true")
REAL_HARDWARE_MODE = not SIMULATOR_ENABLED

# Dynamic path separator (Fixes Mac vs Windows issue)
path_sep = ";" if os.name == "nt" else ":"
existing_pythonpath = env_override.get("PYTHONPATH", "")

env_override["PYTHONPATH"] = (
    f"{BACKEND_DIR}{path_sep}{PROJECT_ROOT}" + (f"{path_sep}{existing_pythonpath}" if existing_pythonpath else "")
)


# ============================================================
# PROCESS LIST
# ============================================================

server_process = None
simulator_process = None
admin_frontend_process = None
user_frontend_process = None


# ============================================================
# 1. START FASTAPI BACKEND
# ============================================================

print()
print("[1/4] Starting FastAPI Backend...")
print(f"      {BACKEND_URL}")

server_process = subprocess.Popen(
    [
        PYTHON_EXE,
        "-m",
        "uvicorn",
        "main:app",
        "--host",
        BACKEND_HOST,
        "--port",
        str(BACKEND_PORT),
    ],
    cwd=BACKEND_DIR,
    env=env_override,
)


# ============================================================
# WAIT FOR BACKEND
# ============================================================

print("      Waiting for FastAPI to initialize...")

server_ready = False

for _ in range(30):
    try:
        with urllib.request.urlopen(
            f"{BACKEND_URL}/docs",
            timeout=1
        ) as response:

            if response.status == 200:
                server_ready = True
                print("      [SUCCESS] FastAPI Backend is live!")
                break

    except Exception:
        time.sleep(1)


if not server_ready:
    print()
    print("[ERROR] FastAPI server failed to start.")

    if server_process:
        server_process.terminate()

    sys.exit(1)


# ============================================================
# 2. START ESP32 SIMULATOR
# ============================================================

print()
if SIMULATOR_ENABLED:
    print("[2/4] Starting ESP32-S3 Sensor Simulator...")

    simulator_process = subprocess.Popen(
        [
            PYTHON_EXE,
            "simulate_esp32.py",
        ],
        cwd=BACKEND_DIR,
        env=env_override,
    )

    print("      [SUCCESS] ESP32-S3 Simulator running.")
else:
    print("[2/4] ESP32 Simulator disabled - REAL HARDWARE MODE (Listening for ESP32 WiFi POST)")


# ============================================================
# 3. START ADMIN FRONTEND
# ============================================================

print()
print("[3/4] Starting Admin Dashboard...")

if os.path.isdir(ADMIN_FRONTEND_DIR):

    admin_frontend_process = subprocess.Popen(
        [
            PYTHON_EXE,
            "-m",
            "http.server",
            str(ADMIN_PORT),
        ],
        cwd=ADMIN_FRONTEND_DIR,
    )

    print(
        f"      [SUCCESS] Admin Dashboard running at:"
    )
    print(
        f"      {ADMIN_URL}"
    )

else:
    print(
        f"      [WARNING] Admin frontend not found:"
    )
    print(
        f"      {ADMIN_FRONTEND_DIR}"
    )


# ============================================================
# 4. START USER FRONTEND
# ============================================================

print()
print("[4/4] Starting User Dashboard...")

if os.path.isdir(USER_FRONTEND_DIR):

    user_frontend_process = subprocess.Popen(
        [
            PYTHON_EXE,
            "-m",
            "http.server",
            str(USER_PORT),
        ],
        cwd=USER_FRONTEND_DIR,
    )

    print(
        f"      [SUCCESS] User Dashboard running at:"
    )
    print(
        f"      {USER_URL}"
    )

else:
    print()
    print(
        "[WARNING] User frontend folder not found!"
    )
    print(
        f"          Expected:"
    )
    print(
        f"          {USER_FRONTEND_DIR}"
    )


# ============================================================
# OPEN BROWSERS
# ============================================================

time.sleep(2)

print()
print("Opening dashboards...")

if os.path.isdir(ADMIN_FRONTEND_DIR):
    webbrowser.open(ADMIN_URL)

if os.path.isdir(USER_FRONTEND_DIR):
    webbrowser.open(USER_URL)


# ============================================================
# FINAL STATUS
# ============================================================

print()
print("=" * 70)
print(" SafeTrack System Running")
print("=" * 70)

print()
print(f" Backend : {BACKEND_URL}")
print(f" Admin   : {ADMIN_URL}")
print(f" User    : {USER_URL}")

print()
print(" Data Flow:")
print(" ESP32 Simulator" if SIMULATOR_ENABLED else " ESP32 Hardware (WiFi -> /api/events)")
print("       |")
print("       v")
print(" FastAPI Backend :8000")
print("       |")
print("       v")
print(" safetrack.db")
print("       |")
print("       v")
print(" +---------------+----------------+")
print(" |               |")
print(" v               v")
print(" Admin           User")
print(":5501           :5500")

print()
print(" Press Ctrl+C to stop EVERYTHING.")
print("=" * 70)


# ============================================================
# CLEAN SHUTDOWN
# ============================================================

try:
    while True:
        time.sleep(1)

except KeyboardInterrupt:

    print()
    print("=" * 70)
    print(" Shutting down SafeTrack...")
    print("=" * 70)

    processes = [
        ("User Dashboard", user_frontend_process),
        ("Admin Dashboard", admin_frontend_process),
        ("ESP32 Simulator", simulator_process),
        ("FastAPI Backend", server_process),
    ]

    for name, process in processes:

        if process is not None:

            print(f"Stopping {name}...")

            try:
                process.terminate()
                process.wait(timeout=3)

            except Exception:

                try:
                    process.kill()
                except Exception:
                    pass

    print()
    print("SafeTrack stopped successfully.")
