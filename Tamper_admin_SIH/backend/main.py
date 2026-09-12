import hashlib
import json
import math
import os
import hmac
from typing import List, Optional
from fastapi import Depends, FastAPI, Header, HTTPException, Request, status
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, ConfigDict, Field, field_validator
from sqlalchemy import inspect, text
from sqlalchemy.orm import Session

from database import Base, SessionLocal, engine, get_db
from models import Device, SensorEvent, Shipment, ShipmentAlert, SystemSetting, User, Vehicle
from auth import create_access_token, decode_access_token, get_password_hash, verify_password
from auth import IS_PRODUCTION

# Initialize FastAPI App
app = FastAPI(title="SafeTrack Unified Admin & Operations API", version="3.0.0")

# These are the two current deployments and explicit local development origins.
ALLOWED_ORIGINS = os.getenv("CORS_ORIGINS", ",".join([
    "https://safetrack-admin-live-mu.vercel.app",
    "https://safetrack-user-live-chi.vercel.app",
    "http://localhost:5500", "http://localhost:5501",
    "http://127.0.0.1:5500", "http://127.0.0.1:5501", "http://127.0.0.1:5511",
])).split(",")
app.add_middleware(
    CORSMiddleware,
    allow_origins=[origin.strip() for origin in ALLOWED_ORIGINS if origin.strip()],
    allow_credentials=False,
    allow_methods=["GET", "POST", "PUT", "DELETE"],
    allow_headers=["Authorization", "Content-Type", "X-Device-Key", "Idempotency-Key"],
)

SEAL_TAMPER_LUX_THRESHOLD = 800.0
DEMO_RESET = os.getenv("DEMO_RESET", "false").lower() == "true"
DEVICE_API_KEY = os.getenv("DEVICE_API_KEY", "").strip()
if IS_PRODUCTION and len(DEVICE_API_KEY) < 32:
    raise RuntimeError("Set a unique DEVICE_API_KEY of at least 32 characters before deploying.")


@app.middleware("http")
async def security_headers(request: Request, call_next):
    response = await call_next(request)
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["Cache-Control"] = "no-store"
    response.headers["Referrer-Policy"] = "no-referrer"
    response.headers["X-Frame-Options"] = "DENY"
    return response

# Ensure Tables exist
Base.metadata.create_all(bind=engine)

def ensure_schema_migrations():
    """Add telemetry columns on both PostgreSQL and legacy SQLite databases."""
    try:
        existing_cols = {column["name"] for column in inspect(engine).get_columns("sensor_events")}
        with engine.begin() as conn:
            new_cols = {
                "event_id": "VARCHAR(128)",
                "accel_x": "FLOAT DEFAULT 0.0",
                "accel_y": "FLOAT DEFAULT 0.0",
                "accel_z": "FLOAT DEFAULT 1.0",
                "gyro_x": "FLOAT DEFAULT 0.0",
                "gyro_y": "FLOAT DEFAULT 0.0",
                "gyro_z": "FLOAT DEFAULT 0.0",
                "shock_g": "FLOAT DEFAULT 0.0",
                "pitch": "FLOAT DEFAULT 0.0",
                "roll": "FLOAT DEFAULT 0.0",
            }
            for col_name, col_def in new_cols.items():
                if col_name not in existing_cols:
                    conn.execute(text(f"ALTER TABLE sensor_events ADD COLUMN {col_name} {col_def}"))
            conn.execute(text("CREATE UNIQUE INDEX IF NOT EXISTS ix_sensor_events_event_id ON sensor_events (event_id)"))
    except Exception as exc:
        print(f"[SCHEMA MIGRATION NOTE] {exc}")

ensure_schema_migrations()


def normalize_legacy_vehicle_ids(db: Session):
    """Migrate the old demo vehicle codes that incorrectly reused shipment codes."""
    legacy_to_new = {
        "PRCL-2024-05-21-001": "TRK-MH-001",
        "PRCL-2024-05-21-002": "TRK-WB-002",
        "PRCL-2024-05-21-003": "TRK-TN-003",
        "PRCL-2024-05-21-004": "TRK-GJ-004",
        "PRCL-2024-05-21-005": "TRK-RJ-005",
        "PRCL-2024-05-21-006": "TRK-DL-006",
    }

    for old_code, new_code in legacy_to_new.items():
        vehicle = db.query(Vehicle).filter(Vehicle.vehicle_code == old_code).first()
        if vehicle:
            vehicle.vehicle_code = new_code

        db.query(Shipment).filter(Shipment.vehicle_id == old_code).update(
            {Shipment.vehicle_id: new_code}, synchronize_session=False
        )
        db.query(ShipmentAlert).filter(ShipmentAlert.vehicle_id == old_code).update(
            {ShipmentAlert.vehicle_id: new_code}, synchronize_session=False
        )


@app.on_event("startup")
def startup_db_seed():
    db = SessionLocal()
    try:
        normalize_legacy_vehicle_ids(db)
        db.commit()

        # Seed Default Users
        admin_password = os.getenv("BOOTSTRAP_ADMIN_PASSWORD", "")
        demo_password = os.getenv("DEMO_USER_PASSWORD", "")
        demo_users = [
            ("admin", "admin@safetrack.com", admin_password, "admin", ["All Vehicles"]),
            ("Rahul Sharma", "rahul.sharma@safetrack.com", demo_password, "user", ["PRCL-2024-05-21-001", "PRCL-2024-05-21-007"]),
            ("Priya Sharma", "priya.sharma@safetrack.com", demo_password, "user", ["PRCL-2024-05-21-002", "PRCL-2024-05-21-008"]),
            ("Arjun Reddy", "arjun.reddy@safetrack.com", demo_password, "user", ["PRCL-2024-05-21-003", "PRCL-2024-05-21-009"]),
            ("Neha Kapoor", "neha.kapoor@safetrack.com", demo_password, "user", ["PRCL-2024-05-21-004", "PRCL-2024-05-21-010"]),
        ]
        for username, email, password, role, assignments in demo_users:
            existing = db.query(User).filter(User.username == username).first()
            if not existing and password:
                if not 12 <= len(password) <= 72 or len(password.encode("utf-8")) > 72:
                    raise RuntimeError("Bootstrap passwords must contain 12–72 UTF-8 bytes.")
                db.add(User(username=username, email=email, hashed_password=get_password_hash(password), role=role, assigned_vehicles=json.dumps(assignments)))
            elif existing:
                if existing.role not in ("admin", "user"):
                    existing.role = "user"

        # Seed Default Devices
        for i in range(1, 11):
            device_id = f"ESP32-S3-TRACKER-{i:02d}"
            if DEVICE_API_KEY and not db.query(Device).filter(Device.device_id == device_id).first():
                db.add(Device(device_id=device_id, api_key=DEVICE_API_KEY))

        # Seed Default Vehicles
        initial_vehicles = [
            {"vehicle_code": "TRK-MH-001", "name": "Mumbai-Delhi Cold Express 01", "license_plate": "MH-04-JK-9021", "driver": "Rajesh Kumar (DRV-882)", "assigned_shipments": json.dumps(["PRCL-2024-05-21-001", "PRCL-2024-05-21-007"]), "origin": "Mumbai Central Warehouse", "destination": "Delhi Central Facility", "current_hub": "Rewari Transit Hub, HR", "status": "In Transit"},
            {"vehicle_code": "TRK-WB-002", "name": "Kolkata-Bangalore Reefer 02", "license_plate": "MH-12-PQ-4410", "driver": "Amitabh Sen (DRV-419)", "assigned_shipments": json.dumps(["PRCL-2024-05-21-002", "PRCL-2024-05-21-008"]), "origin": "Kolkata Hub", "destination": "Bangalore Hub", "current_hub": "Visakhapatnam Port Hub, AP", "status": "In Transit"},
            {"vehicle_code": "TRK-TN-003", "name": "Chennai-Hyderabad Security Van 14", "license_plate": "DL-01-AX-3341", "driver": "Srinivasan R. (DRV-305)", "assigned_shipments": json.dumps(["PRCL-2024-05-21-003", "PRCL-2024-05-21-009"]), "origin": "Chennai Hub", "destination": "Hyderabad Hub", "current_hub": "Vijayawada Transit Yard, AP", "status": "In Transit"},
            {"vehicle_code": "TRK-GJ-004", "name": "Pune-Mumbai Reefer Van 09", "license_plate": "GJ-01-HG-8812", "driver": "Vikram Patil (DRV-771)", "assigned_shipments": json.dumps(["PRCL-2024-05-21-004"]), "origin": "Pune Warehouse", "destination": "Mumbai Hub", "current_hub": "Panvel Checkpoint, MH", "status": "Delayed"},
            {"vehicle_code": "TRK-RJ-005", "name": "Ahmedabad-Delhi Heavy Cargo 21", "license_plate": "UP-32-CD-5520", "driver": "Karan Shah (DRV-612)", "assigned_shipments": json.dumps(["PRCL-2024-05-21-005"]), "origin": "Ahmedabad Hub", "destination": "Delhi Facility", "current_hub": "Jaipur Highway Hub, RJ", "status": "In Transit"},
            {"vehicle_code": "TRK-DL-006", "name": "Delhi-Lucknow Medical Carrier 06", "license_plate": "DL-07-RK-6112", "driver": "Sana Khan (DRV-244)", "assigned_shipments": json.dumps(["PRCL-2024-05-21-006", "PRCL-2024-05-21-010"]), "origin": "Delhi Central Facility", "destination": "Lucknow Medical Hub", "current_hub": "Agra Transit Hub, UP", "status": "In Transit"}
        ]

        for v in initial_vehicles:
            existing_vehicle = db.query(Vehicle).filter(Vehicle.vehicle_code == v["vehicle_code"]).first()
            if not existing_vehicle:
                db.add(Vehicle(**v))
            else:
                existing_vehicle.assigned_shipments = v["assigned_shipments"]

        # Seed Default Shipments
        initial_shipments = [
            {"shipment_code": "PRCL-2024-05-21-001", "vehicle_id": "TRK-MH-001", "title": "Cold-Chain Medicine & Vaccines", "sender": "Serum Bio-Tech Mumbai Hub", "recipient_name": "Rahul Sharma", "origin": "Mumbai Central Warehouse", "destination": "Delhi Central Facility", "current_warehouse": "Rewari Transit Hub, HR", "status": "In Transit", "seal_status": "Intact", "health_level": "Optimal", "latest_temperature": 4.2, "latest_light": 0.0, "latest_humidity": 45.0, "latest_shock": "Normal (0.2g)"},
            {"shipment_code": "PRCL-2024-05-21-007", "vehicle_id": "TRK-MH-001", "title": "Insulin Injection Pens & Cold Syringes", "sender": "Serum Bio-Tech Mumbai Hub", "recipient_name": "Priya Sharma", "origin": "Mumbai Central Warehouse", "destination": "Delhi Central Facility", "current_warehouse": "Rewari Transit Hub, HR", "status": "In Transit", "seal_status": "Intact", "health_level": "Optimal", "latest_temperature": 4.0, "latest_light": 0.0, "latest_humidity": 44.0, "latest_shock": "Normal (0.1g)"},
            {"shipment_code": "PRCL-2024-05-21-002", "vehicle_id": "TRK-WB-002", "title": "Oncology Biologic Cancer Therapy", "sender": "Kolkata Medical Depot", "recipient_name": "Dr. A. K. Roy", "origin": "Kolkata Hub", "destination": "Bangalore Hub", "current_warehouse": "Visakhapatnam Port Hub, AP", "status": "In Transit", "seal_status": "Intact", "health_level": "Degraded", "latest_temperature": 5.1, "latest_light": 12.0, "latest_humidity": 52.0, "latest_shock": "Minor Bump (0.8g)"},
            {"shipment_code": "PRCL-2024-05-21-003", "vehicle_id": "TRK-TN-003", "title": "mRNA Booster Doses & Cell Cultures", "sender": "Chennai Vaccine Research", "recipient_name": "Hyderabad Hospital", "origin": "Chennai Hub", "destination": "Hyderabad Hub", "current_warehouse": "Vijayawada Transit Yard, AP", "status": "In Transit", "seal_status": "Intact", "health_level": "Optimal", "latest_temperature": 3.8, "latest_light": 0.0, "latest_humidity": 38.0, "latest_shock": "Normal (0.1g)"},
            {"shipment_code": "PRCL-2024-05-21-004", "vehicle_id": "TRK-GJ-004", "title": "Monoclonal Antibodies & Immunotherapy", "sender": "Pune Bio-Tech Park", "recipient_name": "Mumbai Air Cargo Terminal", "origin": "Pune Warehouse", "destination": "Mumbai Hub", "current_warehouse": "Panvel Checkpoint, MH", "status": "Compromised", "seal_status": "BREACHED", "health_level": "Compromised", "latest_temperature": 16.5, "latest_light": 850.0, "latest_humidity": 68.0, "latest_shock": "High Impact (3.4g)"},
            {"shipment_code": "PRCL-2024-05-21-005", "vehicle_id": "TRK-RJ-005", "title": "Ophthalmic Sterile Solutions & Drops", "sender": "Ahmedabad Formulations", "recipient_name": "Delhi Eye Institute", "origin": "Ahmedabad Hub", "destination": "Delhi Facility", "current_warehouse": "Jaipur Highway Hub, RJ", "status": "In Transit", "seal_status": "Intact", "health_level": "Optimal", "latest_temperature": 4.0, "latest_light": 0.0, "latest_humidity": 40.0, "latest_shock": "Normal (0.2g)"},
            {"shipment_code": "PRCL-2024-05-21-006", "vehicle_id": "TRK-DL-006", "title": "Insulin Cold-Storage Vials", "sender": "Delhi Biologics Depot", "recipient_name": "Lucknow Care Network", "origin": "Delhi Central Facility", "destination": "Lucknow Medical Hub", "current_warehouse": "Agra Transit Hub, UP", "status": "At Warehouse", "seal_status": "Intact", "health_level": "Optimal", "latest_temperature": 4.6, "latest_light": 0.0, "latest_humidity": 42.0, "latest_shock": "Normal (0.2g)"},
            {"shipment_code": "PRCL-2024-05-21-008", "vehicle_id": "TRK-WB-002", "title": "Temperature-Sensitive Oncology Samples", "sender": "Kolkata Medical Depot", "recipient_name": "Bangalore Oncology Centre", "origin": "Kolkata Hub", "destination": "Bangalore Hub", "current_warehouse": "Visakhapatnam Port Hub, AP", "status": "In Transit", "seal_status": "Intact", "health_level": "Optimal", "latest_temperature": 4.7, "latest_light": 5.0, "latest_humidity": 47.0, "latest_shock": "Normal (0.2g)"},
            {"shipment_code": "PRCL-2024-05-21-009", "vehicle_id": "TRK-TN-003", "title": "Research Cell Culture Samples", "sender": "Chennai Vaccine Research", "recipient_name": "Hyderabad Research Lab", "origin": "Chennai Hub", "destination": "Hyderabad Hub", "current_warehouse": "Vijayawada Transit Yard, AP", "status": "In Transit", "seal_status": "Intact", "health_level": "Optimal", "latest_temperature": 3.9, "latest_light": 0.0, "latest_humidity": 41.0, "latest_shock": "Normal (0.1g)"},
            {"shipment_code": "PRCL-2024-05-21-010", "vehicle_id": "TRK-DL-006", "title": "Emergency Vaccine Reserve", "sender": "National Vaccine Store", "recipient_name": "Lucknow Medical Hub", "origin": "Delhi Central Facility", "destination": "Lucknow Medical Hub", "current_warehouse": "Agra Transit Hub, UP", "status": "In Transit", "seal_status": "Intact", "health_level": "Optimal", "latest_temperature": 4.3, "latest_light": 0.0, "latest_humidity": 43.0, "latest_shock": "Normal (0.2g)"}
        ]

        for s in initial_shipments:
            if not db.query(Shipment).filter(Shipment.shipment_code == s["shipment_code"]).first():
                db.add(Shipment(**s))

        db.commit()

        # Seed Alerts
        if db.query(ShipmentAlert).count() == 0:
            shipment4 = db.query(Shipment).filter(Shipment.shipment_code == "PRCL-2024-05-21-004").first()
            if shipment4:
                db.add(ShipmentAlert(shipment_id=shipment4.id, vehicle_id="PRCL-2024-05-21-004", severity="Critical", alert_type="Seal Breach / Light Exposure", warehouse_location="Panvel Checkpoint, MH", message="CRITICAL TAMPER: Container opened (850 LUX; threshold 800 LUX) at Panvel Checkpoint!", status="Active"))
                db.add(ShipmentAlert(shipment_id=shipment4.id, vehicle_id="PRCL-2024-05-21-004", severity="Critical", alert_type="Severe Impact Shock", warehouse_location="Panvel Checkpoint, MH", message="CRITICAL EXCURSION: Severe impact shock (3.4g) detected on MPU6050 sensor!", status="Active"))

            shipment2 = db.query(Shipment).filter(Shipment.shipment_code == "PRCL-2024-05-21-002").first()
            if shipment2:
                db.add(ShipmentAlert(shipment_id=shipment2.id, vehicle_id="PRCL-2024-05-21-002", severity="Warning", alert_type="Temperature Warning", warehouse_location="Visakhapatnam Port Hub, AP", message="WARNING: Stress parameter (Temp: 5.1°C slightly above target threshold).", status="Active"))

            db.commit()

    finally:
        db.close()


# --- PYDANTIC SCHEMAS ---

class LoginRequest(BaseModel):
    username: str = Field(min_length=1, max_length=64)
    password: str = Field(min_length=1, max_length=72)
    shipment_code: Optional[str] = "PRCL-2024-05-21-001"


class VehicleCreatePayload(BaseModel):
    id: Optional[str] = None
    name: str
    origin: str
    destination: str
    driver: str
    status: str = "In Transit"
    license_plate: Optional[str] = "MH-04-JK-9021"


class ShipmentCreatePayload(BaseModel):
    id: str
    title: str
    vehicle_id: str
    origin: str
    destination: str
    sender: Optional[str] = "Serum Bio-Tech Hub"
    recipient_name: Optional[str] = "Rahul Sharma"
    status: str = "In Transit"


class UserCreatePayload(BaseModel):
    name: str
    email: str
    password: str = Field(min_length=12, max_length=72)
    role: str = "user"
    assigned_vehicles: Optional[List[str]] = ["PRCL-2024-05-21-001"]

    @field_validator("password")
    @classmethod
    def password_byte_limit(cls, value):
        if len(value.encode("utf-8")) > 72:
            raise ValueError("Password must not exceed 72 UTF-8 bytes")
        return value


class GPSSensorIngestPayload(BaseModel):
    model_config = ConfigDict(extra="allow", allow_inf_nan=False, str_max_length=512)
    event_id: Optional[str] = Field(default=None, min_length=1, max_length=128)
    device_id: str = Field(min_length=1, max_length=64, pattern=r"^[A-Za-z0-9_.:-]+$")
    shipment_code: str = Field(min_length=1, max_length=64, pattern=r"^[A-Za-z0-9_.:-]+$")
    temperature: float = Field(ge=-100, le=150)
    humidity: float = Field(ge=0, le=100)
    warehouse_location: str = Field(default="Rewari Transit Hub, HR", max_length=128)
    device_key: Optional[str] = None

    # Flexible Light Ingest (supports both lux and raw ADC readings)
    light_lux: Optional[float] = None
    ldr_raw: Optional[float] = Field(default=None, ge=0, le=4095)

    # Accelerometer (supports scalar accel_g and 3-axis readings)
    accel_g: Optional[float] = None
    accel_x_g: Optional[float] = None
    accel_y_g: Optional[float] = None
    accel_z_g: Optional[float] = None

    # Gyroscope (supports scalar gyro_dps and 3-axis readings)
    gyro_dps: Optional[float] = None
    gyro_x_dps: Optional[float] = None
    gyro_y_dps: Optional[float] = None
    gyro_z_dps: Optional[float] = None

    # Shock and hardware diagnostics
    shock_reading_g: Optional[float] = None
    shock_detected: Optional[bool] = None
    mpu_available: Optional[bool] = None
    mpu_read_ok: Optional[bool] = None

class VehicleUpdatePayload(BaseModel):
    name: Optional[str] = None
    license_plate: Optional[str] = None
    driver: Optional[str] = None
    origin: Optional[str] = None
    destination: Optional[str] = None
    current_hub: Optional[str] = None
    status: Optional[str] = None


class VehicleAssignShipmentPayload(BaseModel):
    shipment_code: str


class ShipmentUpdatePayload(BaseModel):
    title: Optional[str] = None
    origin: Optional[str] = None
    destination: Optional[str] = None
    current_hub: Optional[str] = None
    sender: Optional[str] = None
    recipient_name: Optional[str] = None
    status: Optional[str] = None


class UserUpdatePayload(BaseModel):
    email: Optional[str] = None
    role: Optional[str] = None
    assigned_vehicles: Optional[List[str]] = None
    status: Optional[str] = None


class SystemSettingsPayload(BaseModel):
    system_name: Optional[str] = "SafeTrack Logistics & Security Control Center"
    default_temp_threshold: Optional[float] = 8.0
    default_alert_threshold: Optional[float] = 800.0
    language: Optional[str] = "English"
    alert_notifications: Optional[bool] = True
    shipment_updates: Optional[bool] = True
    email_notifications: Optional[bool] = True
    session_timeout: Optional[int] = 30


class ChangePasswordPayload(BaseModel):
    current_password: str
    new_password: str


# --- API ENDPOINTS ---

@app.post("/api/auth/login")
def login(payload: LoginRequest, db: Session = Depends(get_db)):
    user = db.query(User).filter(User.username == payload.username).first()
    if not user or user.status != "Active" or not verify_password(payload.password, user.hashed_password):
        raise HTTPException(status_code=401, detail="Invalid credentials")

    if not user.hashed_password.startswith("$2"):
        user.hashed_password = get_password_hash(payload.password)

    user.last_login = "Just now"
    db.commit()

    try:
        assignments = json.loads(user.assigned_vehicles) if user.assigned_vehicles else []
    except (TypeError, json.JSONDecodeError):
        assignments = []

    if user.role == "user" and payload.shipment_code and payload.shipment_code not in assignments:
        payload.shipment_code = assignments[0] if assignments else None

    token = create_access_token({"sub": user.username, "role": user.role})
    return {
        "access_token": token,
        "token_type": "bearer",
        "username": user.username,
        "role": user.role,
        "assigned_shipments": assignments,
        "shipment_code": payload.shipment_code
    }


def get_current_user(authorization: Optional[str] = Header(None), db: Session = Depends(get_db)):
    if not authorization or not authorization.lower().startswith("bearer "):
        raise HTTPException(status_code=401, detail="Authentication required")
    token = authorization.split(" ", 1)[1].strip()
    try:
        payload = decode_access_token(token)
        username = payload.get("sub")
        role = payload.get("role")
        if not username or role not in ("admin", "user"):
            raise ValueError("Invalid token claims")
    except Exception:
        raise HTTPException(status_code=401, detail="Invalid or expired token")
    user = db.query(User).filter(User.username == username, User.status == "Active").first()
    if not user:
        raise HTTPException(status_code=401, detail="User not found or disabled")
    return user


def require_admin(current_user: User = Depends(get_current_user)):
    if current_user.role != "admin":
        raise HTTPException(status_code=403, detail="Admin access required")
    return current_user


@app.get("/api/admin/dashboard")
def get_admin_dashboard_metrics(db: Session = Depends(get_db), current_user: User = Depends(require_admin)):
    total_shipments = db.query(Shipment).count()
    active_vehicles = db.query(Vehicle).filter(Vehicle.status != "Stopped").count()
    in_transit = db.query(Shipment).filter(Shipment.status == "In Transit").count()
    active_alerts = db.query(ShipmentAlert).filter(ShipmentAlert.status == "Active").count()
    
    return {
        "total_shipments": total_shipments,
        "active_vehicles": active_vehicles,
        "in_transit": in_transit,
        "alerts_count": active_alerts,
        "avg_temperature": 4.2,
        "system_status": "Optimal"
    }


@app.get("/api/vehicles")
def get_vehicles(db: Session = Depends(get_db), current_user: User = Depends(require_admin)):
    vehicles = db.query(Vehicle).all()
    result = []
    for v in vehicles:
        try:
            assigned = json.loads(v.assigned_shipments) if v.assigned_shipments else []
        except:
            assigned = []
        result.append({
            "id": v.vehicle_code,
            "name": v.name,
            "license_plate": v.license_plate,
            "driver": v.driver,
            "assigned_shipments": assigned,
            "origin": v.origin,
            "destination": v.destination,
            "current_hub": v.current_hub,
            "status": v.status,
            "last_update": v.last_update
        })
    return result


@app.get("/api/vehicles/{vehicle_id}")
def get_vehicle_details(vehicle_id: str, db: Session = Depends(get_db), current_user: User = Depends(require_admin)):
    v = db.query(Vehicle).filter(Vehicle.vehicle_code == vehicle_id).first()
    if not v:
        raise HTTPException(status_code=404, detail="Vehicle not found")
    
    try:
        assigned = json.loads(v.assigned_shipments) if v.assigned_shipments else []
    except:
        assigned = []
        
    return {
        "id": v.vehicle_code,
        "name": v.name,
        "license_plate": v.license_plate,
        "driver": v.driver,
        "assigned_shipments": assigned,
        "origin": v.origin,
        "destination": v.destination,
        "current_hub": v.current_hub,
        "status": v.status,
        "last_update": v.last_update
    }


@app.post("/api/vehicles")
def create_vehicle(payload: VehicleCreatePayload, db: Session = Depends(get_db), current_user: User = Depends(require_admin)):
    v_code = payload.id or f"TRK-AUTO-{db.query(Vehicle).count() + 1:03d}"
    vehicle = Vehicle(
        vehicle_code=v_code,
        name=payload.name,
        license_plate=payload.license_plate,
        driver=payload.driver,
        origin=payload.origin,
        destination=payload.destination,
        current_hub=payload.origin,
        status=payload.status,
        assigned_shipments="[]"
    )
    db.add(vehicle)
    db.commit()
    db.refresh(vehicle)
    return {"id": vehicle.vehicle_code, "name": vehicle.name, "origin": vehicle.origin, "destination": vehicle.destination, "status": vehicle.status, "driver": vehicle.driver, "assigned_shipments": []}


@app.put("/api/vehicles/{vehicle_id}")
def update_vehicle(vehicle_id: str, payload: VehicleUpdatePayload, db: Session = Depends(get_db), current_user: User = Depends(require_admin)):
    vehicle = db.query(Vehicle).filter(Vehicle.vehicle_code == vehicle_id).first()
    if not vehicle:
        raise HTTPException(status_code=404, detail="Vehicle not found")

    if payload.name is not None:
        vehicle.name = payload.name
    if payload.license_plate is not None:
        vehicle.license_plate = payload.license_plate
    if payload.driver is not None:
        vehicle.driver = payload.driver
    if payload.origin is not None:
        vehicle.origin = payload.origin
    if payload.destination is not None:
        vehicle.destination = payload.destination
    if payload.current_hub is not None:
        vehicle.current_hub = payload.current_hub
    if payload.status is not None:
        vehicle.status = payload.status

    vehicle.last_update = "Just now"
    db.commit()
    db.refresh(vehicle)

    try:
        assigned = json.loads(vehicle.assigned_shipments) if vehicle.assigned_shipments else []
    except:
        assigned = []

    return {
        "id": vehicle.vehicle_code,
        "name": vehicle.name,
        "license_plate": vehicle.license_plate,
        "driver": vehicle.driver,
        "assigned_shipments": assigned,
        "origin": vehicle.origin,
        "destination": vehicle.destination,
        "current_hub": vehicle.current_hub,
        "status": vehicle.status,
        "last_update": vehicle.last_update
    }


@app.delete("/api/vehicles/{vehicle_id}")
def delete_vehicle(vehicle_id: str, db: Session = Depends(get_db), current_user: User = Depends(require_admin)):
    vehicle = db.query(Vehicle).filter(Vehicle.vehicle_code == vehicle_id).first()
    if not vehicle:
        raise HTTPException(status_code=404, detail="Vehicle not found")

    # Unlink any shipments attached to this vehicle so we never leave broken references
    db.query(Shipment).filter(Shipment.vehicle_id == vehicle_id).update(
        {Shipment.vehicle_id: "Unassigned"}, synchronize_session=False
    )
    db.query(ShipmentAlert).filter(ShipmentAlert.vehicle_id == vehicle_id).update(
        {ShipmentAlert.vehicle_id: "Unassigned"}, synchronize_session=False
    )

    db.delete(vehicle)
    db.commit()
    return {"message": f"Vehicle {vehicle_id} deleted successfully"}


@app.post("/api/vehicles/{vehicle_id}/assign-shipment")
def assign_shipment_to_vehicle(vehicle_id: str, payload: VehicleAssignShipmentPayload, db: Session = Depends(get_db), current_user: User = Depends(require_admin)):
    vehicle = db.query(Vehicle).filter(Vehicle.vehicle_code == vehicle_id).first()
    if not vehicle:
        raise HTTPException(status_code=404, detail="Vehicle not found")

    shipment = db.query(Shipment).filter(Shipment.shipment_code == payload.shipment_code).first()
    if not shipment:
        raise HTTPException(status_code=404, detail="Shipment not found")

    # If already on another vehicle, remove from that vehicle
    if shipment.vehicle_id and shipment.vehicle_id != vehicle_id:
        old_v = db.query(Vehicle).filter(Vehicle.vehicle_code == shipment.vehicle_id).first()
        if old_v and old_v.assigned_shipments:
            try:
                old_list = json.loads(old_v.assigned_shipments)
                old_list = [s for s in old_list if s != payload.shipment_code]
                old_v.assigned_shipments = json.dumps(old_list)
            except:
                pass

    try:
        assigned = json.loads(vehicle.assigned_shipments) if vehicle.assigned_shipments else []
    except:
        assigned = []

    if payload.shipment_code not in assigned:
        assigned.append(payload.shipment_code)
        vehicle.assigned_shipments = json.dumps(assigned)

    shipment.vehicle_id = vehicle_id
    db.commit()
    return {"status": "success", "vehicle_id": vehicle_id, "assigned_shipments": assigned}


@app.post("/api/vehicles/{vehicle_id}/remove-shipment")
def remove_shipment_from_vehicle(vehicle_id: str, payload: VehicleAssignShipmentPayload, db: Session = Depends(get_db), current_user: User = Depends(require_admin)):
    vehicle = db.query(Vehicle).filter(Vehicle.vehicle_code == vehicle_id).first()
    if not vehicle:
        raise HTTPException(status_code=404, detail="Vehicle not found")

    try:
        assigned = json.loads(vehicle.assigned_shipments) if vehicle.assigned_shipments else []
    except:
        assigned = []

    assigned = [s for s in assigned if s != payload.shipment_code]
    vehicle.assigned_shipments = json.dumps(assigned)

    shipment = db.query(Shipment).filter(Shipment.shipment_code == payload.shipment_code).first()
    if shipment and shipment.vehicle_id == vehicle_id:
        shipment.vehicle_id = "Unassigned"

    db.commit()
    return {"status": "success", "vehicle_id": vehicle_id, "assigned_shipments": assigned}


@app.get("/api/shipments")
def get_shipments(db: Session = Depends(get_db), current_user: User = Depends(require_admin)):
    shipments = db.query(Shipment).all()
    result = []
    for s in shipments:
        vehicle = db.query(Vehicle).filter(Vehicle.vehicle_code == s.vehicle_id).first()
        result.append({
            "id": s.shipment_code,
            "title": s.title,
            "vehicle_id": s.vehicle_id,
            "vehicle_registration": vehicle.license_plate if vehicle else None,
            "sender": s.sender,
            "recipient": s.recipient_name,
            "origin": s.origin,
            "destination": s.destination,
            "current_hub": s.current_warehouse,
            "status": s.status,
            "seal_status": s.seal_status,
            "health_level": s.health_level,
            "latest_temperature": s.latest_temperature,
            "latest_light": s.latest_light,
            "latest_humidity": s.latest_humidity,
            "latest_shock": s.latest_shock,
            "last_update": "Just now"
        })
    return result


@app.get("/api/shipments/{code}")
def get_shipment_by_code(
    code: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    shipment = (
        db.query(Shipment)
        .filter(Shipment.shipment_code == code)
        .first()
    )

    if not shipment:
        raise HTTPException(
            status_code=404,
            detail="Shipment not found"
        )

    if current_user.role != "admin":
        try:
            assigned_shipments = json.loads(current_user.assigned_vehicles or "[]")
        except (TypeError, json.JSONDecodeError):
            assigned_shipments = []
        if code not in assigned_shipments:
            raise HTTPException(status_code=403, detail="Shipment not assigned to this user")

    vehicle = db.query(Vehicle).filter(Vehicle.vehicle_code == shipment.vehicle_id).first()

    recent_events = (
        db.query(SensorEvent)
        .filter(SensorEvent.shipment_id == shipment.id)
        .order_by(SensorEvent.id.desc())
        .limit(30)
        .all()
    )

    alerts = (
        db.query(ShipmentAlert)
        .filter(ShipmentAlert.shipment_id == shipment.id)
        .order_by(ShipmentAlert.id.desc())
        .limit(10)
        .all()
    )

    events_data = []
    for event in recent_events:
        events_data.append({
            "id": event.id,
            "shipment_id": event.shipment_id,
            "device_id": event.device_id,
            "light_lux": float(event.light_lux or 0),
            "temperature": float(event.temperature or 0),
            "humidity": float(event.humidity or 0),
            "light_unit": "LUX",
            "accel_g": float(event.accel_g or 0),
            "gyro_dps": float(event.gyro_dps or 0),
            "accel_x": float(getattr(event, "accel_x", 0.0) if getattr(event, "accel_x", None) is not None else 0.0),
            "accel_y": float(getattr(event, "accel_y", 0.0) if getattr(event, "accel_y", None) is not None else 0.0),
            "accel_z": float(getattr(event, "accel_z", 1.0) if getattr(event, "accel_z", None) is not None else 1.0),
            "gyro_x": float(getattr(event, "gyro_x", 0.0) if getattr(event, "gyro_x", None) is not None else 0.0),
            "gyro_y": float(getattr(event, "gyro_y", 0.0) if getattr(event, "gyro_y", None) is not None else 0.0),
            "gyro_z": float(getattr(event, "gyro_z", 0.0) if getattr(event, "gyro_z", None) is not None else 0.0),
            "shock_g": float(getattr(event, "shock_g", 0.0) if getattr(event, "shock_g", None) is not None else 0.0),
            "pitch": float(getattr(event, "pitch", 0.0) if getattr(event, "pitch", None) is not None else 0.0),
            "roll": float(getattr(event, "roll", 0.0) if getattr(event, "roll", None) is not None else 0.0),
            "health_level": event.health_level or "Optimal",
            "previous_hash": event.previous_hash,
            "record_hash": event.record_hash,
            "created_at": (
                event.created_at.isoformat()
                if event.created_at
                else None
            )
        })

    alerts_data = []
    for alert in alerts:
        alerts_data.append({
            "id": alert.id,
            "shipment_id": alert.shipment_id,
            "vehicle_id": alert.vehicle_id,
            "severity": alert.severity,
            "alert_type": alert.alert_type,
            "warehouse_location": alert.warehouse_location,
            "message": alert.message,
            "status": alert.status,
            "created_at": (
                alert.created_at.isoformat()
                if alert.created_at
                else None
            )
        })

    latest = events_data[0] if events_data else None

    return {
        "shipment": {
            "id": shipment.shipment_code,
            "code": shipment.shipment_code,
            "title": shipment.title,
            "vehicle_id": shipment.vehicle_id,
            "vehicle_registration": vehicle.license_plate if vehicle else None,
            "vehicle_name": vehicle.name if vehicle else None,
            "sender": shipment.sender,
            "recipient": shipment.recipient_name,
            "origin": shipment.origin,
            "destination": shipment.destination,
            "current_warehouse": shipment.current_warehouse,
            "status": shipment.status,
            "seal_status": shipment.seal_status,
            "health_level": shipment.health_level
        },
        "latest_telemetry": latest,
        "events": events_data,
        "alerts": alerts_data
    }


@app.post("/api/shipments")
def create_shipment(payload: ShipmentCreatePayload, db: Session = Depends(get_db), current_user: User = Depends(require_admin)):
    shipment = Shipment(
        shipment_code=payload.id,
        title=payload.title,
        vehicle_id=payload.vehicle_id,
        origin=payload.origin,
        destination=payload.destination,
        current_warehouse=payload.origin,
        sender=payload.sender,
        recipient_name=payload.recipient_name,
        status=payload.status,
        seal_status="Intact",
        health_level="Optimal"
    )
    db.add(shipment)
    
    v = db.query(Vehicle).filter(Vehicle.vehicle_code == payload.vehicle_id).first()
    if v:
        try:
            assigned = json.loads(v.assigned_shipments) if v.assigned_shipments else []
        except:
            assigned = []
        if payload.id not in assigned:
            assigned.append(payload.id)
            v.assigned_shipments = json.dumps(assigned)
            
    db.commit()
    return {"id": shipment.shipment_code, "title": shipment.title, "vehicle_id": shipment.vehicle_id, "status": shipment.status}


@app.put("/api/shipments/{code}")
def update_shipment(code: str, payload: ShipmentUpdatePayload, db: Session = Depends(get_db), current_user: User = Depends(require_admin)):
    shipment = db.query(Shipment).filter(Shipment.shipment_code == code).first()
    if not shipment:
        raise HTTPException(status_code=404, detail="Shipment not found")

    if payload.title is not None:
        shipment.title = payload.title
    if payload.origin is not None:
        shipment.origin = payload.origin
    if payload.destination is not None:
        shipment.destination = payload.destination
    if payload.current_hub is not None:
        shipment.current_warehouse = payload.current_hub
    if payload.sender is not None:
        shipment.sender = payload.sender
    if payload.recipient_name is not None:
        shipment.recipient_name = payload.recipient_name
    if payload.status is not None:
        shipment.status = payload.status

    db.commit()
    db.refresh(shipment)
    return {
        "id": shipment.shipment_code,
        "title": shipment.title,
        "vehicle_id": shipment.vehicle_id,
        "origin": shipment.origin,
        "destination": shipment.destination,
        "current_hub": shipment.current_warehouse,
        "status": shipment.status,
        "sender": shipment.sender,
        "recipient": shipment.recipient_name
    }


@app.delete("/api/shipments/{code}")
def delete_shipment(code: str, db: Session = Depends(get_db), current_user: User = Depends(require_admin)):
    shipment = db.query(Shipment).filter(Shipment.shipment_code == code).first()
    if not shipment:
        raise HTTPException(status_code=404, detail="Shipment not found")

    # 1. Clean up associated sensor telemetry events and alerts
    db.query(SensorEvent).filter(SensorEvent.shipment_id == shipment.id).delete(synchronize_session=False)
    db.query(ShipmentAlert).filter(ShipmentAlert.shipment_id == shipment.id).delete(synchronize_session=False)

    # 2. Clean up assigned_shipments in Vehicles without affecting co-assigned shipments
    vehicles = db.query(Vehicle).all()
    for v in vehicles:
        if v.assigned_shipments:
            try:
                assigned_list = json.loads(v.assigned_shipments)
                if code in assigned_list:
                    assigned_list = [c for c in assigned_list if c != code]
                    v.assigned_shipments = json.dumps(assigned_list)
            except:
                pass

    # 3. Clean up user assigned_vehicles list
    users = db.query(User).all()
    for u in users:
        if u.assigned_vehicles:
            try:
                u_assigned = json.loads(u.assigned_vehicles)
                if code in u_assigned:
                    u_assigned = [c for c in u_assigned if c != code]
                    u.assigned_vehicles = json.dumps(u_assigned)
            except:
                pass

    # 4. Delete the shipment record itself
    db.delete(shipment)
    db.commit()
    return {"message": f"Shipment {code} deleted successfully", "deleted_code": code}


@app.get("/api/alerts")
def get_alerts(db: Session = Depends(get_db), current_user: User = Depends(require_admin)):
    alerts = db.query(ShipmentAlert).order_by(ShipmentAlert.id.desc()).all()
    result = []
    for a in alerts:
        shipment = db.query(Shipment).filter(Shipment.id == a.shipment_id).first()
        s_code = shipment.shipment_code if shipment else "PRCL-2024-05-21-004"
        result.append({
            "id": a.id,
            "severity": a.severity,
            "alert_type": a.alert_type,
            "shipment_id": s_code,
            "vehicle_id": a.vehicle_id or "TRK-GJ-004",
            "location": a.warehouse_location,
            "timestamp": str(a.created_at)[:19],
            "message": a.message,
            "status": a.status
        })
    return result


@app.put("/api/alerts/{alert_id}/resolve")
def resolve_alert(alert_id: int, db: Session = Depends(get_db), current_user: User = Depends(require_admin)):
    alert = db.query(ShipmentAlert).filter(ShipmentAlert.id == alert_id).first()
    if not alert:
        raise HTTPException(status_code=404, detail="Alert not found")

    alert.status = "Resolved"
    alert.severity = "Resolved"
    db.commit()
    return {"id": alert.id, "status": "Resolved"}


@app.put("/api/alerts/resolve-all")
def resolve_all_alerts(db: Session = Depends(get_db), current_user: User = Depends(require_admin)):
    updated_count = db.query(ShipmentAlert).filter(ShipmentAlert.status == "Active").update(
        {ShipmentAlert.status: "Resolved", ShipmentAlert.severity: "Resolved"},
        synchronize_session=False
    )
    db.commit()
    return {"status": "success", "resolved_count": updated_count}


@app.get("/api/users")
def get_users(db: Session = Depends(get_db), current_user: User = Depends(require_admin)):
    users = db.query(User).all()
    result = []
    for u in users:
        try:
            assigned = json.loads(u.assigned_vehicles) if u.assigned_vehicles else ["PRCL-2024-05-21-001"]
        except:
            assigned = ["PRCL-2024-05-21-001"]
        result.append({
            "id": u.id,
            "name": u.username,
            "email": u.email or f"{u.username.lower().replace(' ', '.')}@safetrack.com",
            "role": u.role.capitalize(),
            "assigned_vehicles": assigned,
            "status": u.status,
            "last_login": u.last_login
        })
    return result


@app.post("/api/users")
def create_user(payload: UserCreatePayload, db: Session = Depends(get_db), current_user: User = Depends(require_admin)):
    existing = db.query(User).filter(User.username == payload.name).first()
    if existing:
        raise HTTPException(status_code=400, detail="Username already exists")
    user = User(
        username=payload.name,
        email=payload.email,
        role=("admin" if payload.role.lower() == "admin" else "user"),
        hashed_password=get_password_hash(payload.password),
        status="Active",
        assigned_vehicles=json.dumps(payload.assigned_vehicles or ["PRCL-2024-05-21-001"])
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    return {"id": user.id, "name": user.username, "email": user.email, "role": payload.role, "status": "Active"}


@app.put("/api/users/{user_id}")
def update_user(user_id: int, payload: UserUpdatePayload, db: Session = Depends(get_db), current_user: User = Depends(require_admin)):
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    if payload.email is not None:
        user.email = payload.email
    if payload.role is not None:
        user.role = payload.role.lower()
    if payload.status is not None:
        user.status = payload.status
    if payload.assigned_vehicles is not None:
        user.assigned_vehicles = json.dumps(payload.assigned_vehicles)

    db.commit()
    db.refresh(user)
    try:
        assigned = json.loads(user.assigned_vehicles) if user.assigned_vehicles else []
    except:
        assigned = []

    return {
        "id": user.id,
        "name": user.username,
        "email": user.email,
        "role": user.role.capitalize(),
        "assigned_vehicles": assigned,
        "status": user.status
    }


@app.put("/api/users/{user_id}/toggle-status")
def toggle_user_status(user_id: int, db: Session = Depends(get_db), current_user: User = Depends(require_admin)):
    user = db.query(User).filter(User.id == user_id).first()
    if user:
        user.status = "Disabled" if user.status == "Active" else "Active"
        db.commit()
        return {"id": user.id, "name": user.username, "status": user.status}
    raise HTTPException(status_code=404, detail="User not found")


@app.get("/api/settings")
def get_system_settings(db: Session = Depends(get_db), current_user: User = Depends(require_admin)):
    settings = db.query(SystemSetting).all()
    res = {
        "system_name": "SafeTrack Logistics & Security Control Center",
        "default_temp_threshold": 8.0,
        "default_alert_threshold": 800.0,
        "language": "English",
        "alert_notifications": True,
        "shipment_updates": True,
        "email_notifications": True,
        "session_timeout": 30
    }
    for s in settings:
        val = s.value
        if s.key in ("default_temp_threshold", "default_alert_threshold"):
            try:
                val = float(val)
            except:
                pass
        elif s.key in ("alert_notifications", "shipment_updates", "email_notifications"):
            val = val.lower() == "true"
        elif s.key == "session_timeout":
            try:
                val = int(val)
            except:
                pass
        res[s.key] = val
    return res


@app.post("/api/settings")
def save_system_settings(payload: SystemSettingsPayload, db: Session = Depends(get_db), current_user: User = Depends(require_admin)):
    data = payload.dict(exclude_unset=True)
    for key, val in data.items():
        record = db.query(SystemSetting).filter(SystemSetting.key == key).first()
        if not record:
            record = SystemSetting(category="general", key=key, value=str(val))
            db.add(record)
        else:
            record.value = str(val)
    db.commit()
    return {"status": "success", "message": "Settings saved successfully"}


@app.post("/api/settings/change-password")
def change_admin_password(payload: ChangePasswordPayload, db: Session = Depends(get_db), current_user: User = Depends(require_admin)):
    if not verify_password(payload.current_password, current_user.hashed_password):
        raise HTTPException(status_code=400, detail="Incorrect current password")

    if len(payload.new_password) < 12 or len(payload.new_password.encode("utf-8")) > 72:
        raise HTTPException(status_code=400, detail="Use at least 12 characters and at most 72 UTF-8 bytes")

    current_user.hashed_password = get_password_hash(payload.new_password)
    db.commit()
    return {"status": "success", "message": "Password updated successfully"}


@app.get("/api/reports/summary")
def get_reports_summary(db: Session = Depends(get_db), current_user: User = Depends(require_admin)):
    total_shipments = db.query(Shipment).count()
    total_vehicles = db.query(Vehicle).count()
    total_events = db.query(SensorEvent).count()
    alerts = db.query(ShipmentAlert).all()
    active_alerts = [a for a in alerts if a.status == "Active"]

    temp_alerts = len([a for a in alerts if "temp" in a.alert_type.lower()])
    tamper_alerts = len([a for a in alerts if "tamper" in a.alert_type.lower() or "seal" in a.alert_type.lower()])
    shock_alerts = len([a for a in alerts if "shock" in a.alert_type.lower() or "impact" in a.alert_type.lower()])

    return {
        "total_shipments": total_shipments,
        "total_vehicles": total_vehicles,
        "total_events": total_events,
        "total_alerts": len(alerts),
        "active_alerts_count": len(active_alerts),
        "compliance_percentage": 96.8,
        "temp_alerts": temp_alerts,
        "tamper_alerts": tamper_alerts,
        "shock_alerts": shock_alerts
    }


def add_active_alert_once(db: Session, shipment: Shipment, vehicle_id: str, severity: str, alert_type: str, location: str, message: str):
    exists = (db.query(ShipmentAlert)
              .filter(ShipmentAlert.shipment_id == shipment.id,
                      ShipmentAlert.alert_type == alert_type,
                      ShipmentAlert.status == "Active")
              .first())
    if not exists:
        db.add(ShipmentAlert(shipment_id=shipment.id, vehicle_id=vehicle_id, severity=severity, alert_type=alert_type, warehouse_location=location, message=message, status="Active"))


@app.post("/api/events")
def ingest_sensor_telemetry(request: Request, data: GPSSensorIngestPayload, x_device_key: Optional[str] = Header(None), db: Session = Depends(get_db)):
    # 1. Physical LDR & Optical Tamper Calibration:
    # Real ESP32 circuit behavior:
    # - Covering LDR (No light / container closed) produces approx 4095 ADC -> INTACT
    # - Exposing LDR to light (Light detected / container exposed) produces approx 100 ADC -> COMPROMISED
    # Threshold 2500 separates closed (> 2500) from exposed (< 2500).
    if data.ldr_raw is not None:
        effective_light = float(data.ldr_raw)
        light_unit = "ADC"
        is_light_detected = (effective_light < 2500.0)
    elif data.light_lux is not None:
        effective_light = float(data.light_lux)
        light_unit = "LUX"
        is_light_detected = (effective_light >= SEAL_TAMPER_LUX_THRESHOLD)
    else:
        effective_light = 0.0
        light_unit = "ADC"
        is_light_detected = False

    # 2. 3-axis accel and scalar accel normalization
    ax = float(data.accel_x_g) if data.accel_x_g is not None else 0.0
    ay = float(data.accel_y_g) if data.accel_y_g is not None else 0.0
    az = float(data.accel_z_g) if data.accel_z_g is not None else 1.0

    if data.accel_g is not None:
        effective_accel = float(data.accel_g)
    elif data.shock_reading_g is not None:
        effective_accel = float(data.shock_reading_g)
    elif data.accel_x_g is not None or data.accel_y_g is not None or data.accel_z_g is not None:
        effective_accel = round(math.sqrt(ax**2 + ay**2 + az**2), 3)
    else:
        effective_accel = 1.0

    # 3. 3-axis gyro and scalar gyro normalization
    gx = float(data.gyro_x_dps) if data.gyro_x_dps is not None else 0.0
    gy = float(data.gyro_y_dps) if data.gyro_y_dps is not None else 0.0
    gz = float(data.gyro_z_dps) if data.gyro_z_dps is not None else 0.0

    if data.gyro_dps is not None:
        effective_gyro = float(data.gyro_dps)
    elif data.gyro_x_dps is not None or data.gyro_y_dps is not None or data.gyro_z_dps is not None:
        effective_gyro = round(math.sqrt(gx**2 + gy**2 + gz**2), 2)
    else:
        effective_gyro = 0.0

    # 4. Realistic Pitch and Roll calculation
    if data.accel_x_g is not None and data.accel_y_g is not None and data.accel_z_g is not None:
        denom = az if az != 0 else 0.0001
        pitch_deg = round(math.atan2(ay, math.sqrt(ax**2 + az**2)) * 180.0 / math.pi, 2)
        roll_deg = round(math.atan2(-ax, denom) * 180.0 / math.pi, 2)
    else:
        deviation = effective_accel - 1.0
        pitch_deg = round(max(-45.0, min(45.0, deviation * 28.0)), 2)
        roll_deg = round(max(-45.0, min(45.0, effective_gyro * 0.5)), 2)

    is_shock = (data.shock_detected is True) or (effective_accel >= 3.0)

    # LIVE PRINT STATEMENT FOR TERMINAL LOGGING (Real Hardware Inspection)
    print(f"\n [ESP32 LIVE READINGS] Device: {data.device_id} | Shipment: {data.shipment_code} | Temp: {data.temperature}°C | Humidity: {data.humidity}% | Light: {effective_light:.0f} {light_unit} ({'LIGHT DETECTED' if is_light_detected else 'NO LIGHT'}) | Accel: {effective_accel}g (X={ax}, Y={ay}, Z={az}) | Gyro: {effective_gyro}°/s | Pitch: {pitch_deg}° | Roll: {roll_deg}° | Shock: {is_shock}\n")

    device = db.query(Device).filter(Device.device_id == data.device_id, Device.status == "active").first()
    if not device:
        device = db.query(Device).filter(Device.device_id.ilike(data.device_id.strip()), Device.status == "active").first()
    if not device:
        print(f"[AUTH ERROR] Device '{data.device_id}' not found in active devices table!")
        raise HTTPException(status_code=401, detail=f"Unknown or inactive device: {data.device_id}")

    provided_key = (
        x_device_key
        or request.headers.get("x-device-key")
        or request.headers.get("x_device_key")
        or request.headers.get("x-api-key")
        or request.headers.get("X-Device-Key")
        or request.headers.get("device-key")
        or request.headers.get("device_key")
        or request.headers.get("api-key")
        or getattr(data, "device_key", None)
        or getattr(data, "api_key", None)
    )

    if not isinstance(provided_key, str) or not hmac.compare_digest(
        provided_key.strip().encode(), device.api_key.strip().encode()
    ):
        # Do not put API keys, JWTs, or request headers into hosted logs.
        print(f"[AUTH ERROR] Invalid key for device {data.device_id}")
        raise HTTPException(status_code=401, detail="Invalid device key")

    if data.event_id:
        previous_event = db.query(SensorEvent).filter(SensorEvent.event_id == data.event_id).first()
        if previous_event:
            if previous_event.device_id != device.device_id:
                raise HTTPException(status_code=409, detail="Event identity already in use")
            return {
                "status": "success",
                "duplicate": True,
                "event_hash": previous_event.record_hash,
                "health_level": previous_event.health_level,
            }

    shipment = db.query(Shipment).filter(Shipment.shipment_code == data.shipment_code).first()
    if not shipment:
        raise HTTPException(status_code=404, detail="Shipment not found")

    # Dynamic recalculation of seal_status (strictly non-latching, reflects current physical state)
    if is_light_detected:
        shipment.seal_status = "COMPROMISED"
        add_active_alert_once(
            db,
            shipment,
            shipment.vehicle_id,
            "Critical",
            "Seal Breach / Light Exposure",
            data.warehouse_location,
            f"CRITICAL TAMPER: Container exposed to light ({effective_light:.0f} {light_unit}) at {data.warehouse_location}!"
        )
    else:
        shipment.seal_status = "INTACT"
        # If light is removed / container closed, mark active seal breach alerts as Resolved without deleting historical records
        active_seal_alerts = db.query(ShipmentAlert).filter(
            ShipmentAlert.shipment_id == shipment.id,
            ShipmentAlert.alert_type == "Seal Breach / Light Exposure",
            ShipmentAlert.status == "Active"
        ).all()
        for alert in active_seal_alerts:
            alert.status = "Resolved"

    # Dynamic health evaluation based on CURRENT state
    if is_light_detected or data.temperature > 15.0 or is_shock:
        calculated_health = "Compromised"
        if data.temperature > 15.0 or is_shock:
            shock_msg = f"Severe impact ({effective_accel}g)" if is_shock else ""
            temp_msg = f"heat ({data.temperature}°C)" if data.temperature > 15.0 else ""
            reason = " and ".join(filter(None, [shock_msg, temp_msg]))
            add_active_alert_once(db, shipment, shipment.vehicle_id, "Critical", "Severe Excursion", data.warehouse_location, f"CRITICAL EXCURSION: {reason}!")
    elif data.temperature > 8.0:
        calculated_health = "Degraded"
    else:
        calculated_health = "Optimal"

    shipment.health_level = calculated_health
    shipment.latest_temperature = data.temperature
    shipment.latest_light = effective_light
    shipment.latest_humidity = data.humidity
    shipment.current_warehouse = data.warehouse_location
    shipment.latest_shock = f"Impact ({effective_accel}g)" if effective_accel >= 2.5 else f"Normal ({effective_accel}g)"

    last_event = db.query(SensorEvent).filter(SensorEvent.shipment_id == shipment.id).order_by(SensorEvent.id.desc()).first()
    prev_hash = last_event.record_hash if last_event else "0" * 64
    payload_str = f"{shipment.id}|{data.device_id}|{effective_light}|{data.temperature}|{data.humidity}|{effective_accel}|{prev_hash}"
    curr_hash = hashlib.sha256(payload_str.encode("utf-8")).hexdigest()

    event = SensorEvent(
        event_id=data.event_id,
        shipment_id=shipment.id,
        device_id=data.device_id,
        light_lux=effective_light,
        temperature=data.temperature,
        humidity=data.humidity,
        accel_g=effective_accel,
        gyro_dps=effective_gyro,
        accel_x=ax,
        accel_y=ay,
        accel_z=az,
        gyro_x=gx,
        gyro_y=gy,
        gyro_z=gz,
        shock_g=effective_accel,
        pitch=pitch_deg,
        roll=roll_deg,
        health_level=calculated_health,
        previous_hash=prev_hash,
        record_hash=curr_hash
    )
    db.add(event)
    db.commit()
    return {
        "status": "success",
        "health_level": calculated_health,
        "seal_status": shipment.seal_status,
        "event_hash": curr_hash,
        "effective_light": effective_light,
        "light_unit": light_unit,
        "is_light_detected": is_light_detected,
        "effective_accel": effective_accel,
        "pitch": pitch_deg,
        "roll": roll_deg
    }
