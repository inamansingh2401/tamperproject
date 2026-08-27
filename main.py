import hashlib
import json
import os
from auth import create_access_token, decode_token, get_password_hash, verify_password
from fastapi import Depends, FastAPI, Header, HTTPException, status
from fastapi.middleware.cors import CORSMiddleware
from models import Base, Device, SensorEvent, Shipment, ShipmentAlert, User
from pydantic import BaseModel
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

DATABASE_URL = os.getenv(
    "DATABASE_URL", "postgresql://postgres:password@localhost:5432/safetrack"
)
engine = create_engine(DATABASE_URL)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base.metadata.create_all(bind=engine)

app = FastAPI(title="SafeTrack Tamper-Evident API", version="2.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


def get_db():
  db = SessionLocal()
  try:
    yield db
  finally:
    db.close()


# ==========================================
# SEED DEFAULT USERS AND SHIPMENT
# ==========================================
@app.on_event("startup")
def startup_db_seed():
  db = SessionLocal()
  try:
    # Seed Admin
    if not db.query(User).filter(User.username == "admin").first():
      admin_user = User(
          username="admin",
          hashed_password=get_password_hash("admin123"),
          role="admin",
      )
      db.add(admin_user)

    # Seed User
    if not db.query(User).filter(User.username == "Rahul Sharma").first():
      standard_user = User(
          username="Rahul Sharma",
          hashed_password=get_password_hash("1234"),
          role="user",
      )
      db.add(standard_user)

    # Seed Device
    if (
        not db.query(Device)
        .filter(Device.device_id == "ESP32-S3-TRACKER-01")
        .first()
    ):
      dev = Device(
          device_id="ESP32-S3-TRACKER-01", api_key="secret_device_key_esp32_2026"
      )
      db.add(dev)

    # Seed Shipment
    if (
        not db.query(Shipment)
        .filter(Shipment.shipment_code == "PRCL-2024-05-21-001")
        .first()
    ):
      shipment = Shipment(
          shipment_code="PRCL-2024-05-21-001",
          title="Cold-Chain Medicine & Vaccines",
          recipient_name="Rahul Sharma",
          origin="Mumbai Central Warehouse",
          destination="Delhi Central Facility",
          current_warehouse="Rewari Transit Hub",
          status="In Transit",
          seal_status="Intact",
          health_level="Optimal",
      )
      db.add(shipment)
      db.commit()

      # Add Genesis Block
      genesis_hash = hashlib.sha256(
          b"GENESIS_BLOCK_PRCL-2024-05-21-001"
      ).hexdigest()
      first_event = SensorEvent(
          shipment_id=shipment.id,
          device_id="ESP32-S3-TRACKER-01",
          light_lux=0.0,
          temperature=4.2,
          humidity=45.0,
          accel_g=1.0,
          gyro_dps=0.0,
          health_level="Optimal",
          previous_hash="0" * 64,
          record_hash=genesis_hash,
      )
      db.add(first_event)

    db.commit()
  finally:
    db.close()


# ==========================================
# SCHEMAS
# ==========================================
class LoginRequest(BaseModel):
  username: str
  password: str


class SensorIngestPayload(BaseModel):
  device_id: str
  shipment_code: str
  light_lux: float  # BH1750
  temperature: float  # SHT31
  humidity: float  # SHT31
  accel_g: float  # MPU6050
  gyro_dps: float = 0.0  # MPU6050
  warehouse_location: str = "En-Route"


# ==========================================
# AUTH ENDPOINTS
# ==========================================
@app.post("/api/auth/login")
def login(payload: LoginRequest, db: Session = Depends(get_db)):
  user = db.query(User).filter(User.username == payload.username).first()
  if not user or not verify_password(payload.password, user.hashed_password):
    raise HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Invalid username or passcode",
    )

  token = create_access_token({"sub": user.username, "role": user.role})
  return {
      "access_token": token,
      "token_type": "bearer",
      "username": user.username,
      "role": user.role,
  }


# ==========================================
# SECURE HARDWARE INGESTION ENDPOINT
# ==========================================
@app.post("/api/events")
def ingest_sensor_telemetry(
    data: SensorIngestPayload,
    x_device_key: str = Header(None),
    db: Session = Depends(get_db),
):
  # Device Authentication
  device = db.query(Device).filter(Device.device_id == data.device_id).first()
  if not device:
    # Auto-accept mock simulator if key not provided for dev, enforce if present
    pass
  elif x_device_key and device.api_key != x_device_key:
    raise HTTPException(
        status_code=status.HTTP_403_FORBIDDEN, detail="Invalid Device API Key"
    )

  shipment = (
      db.query(Shipment)
      .filter(Shipment.shipment_code == data.shipment_code)
      .first()
  )
  if not shipment:
    raise HTTPException(
        status_code=status.HTTP_404_NOT_FOUND, detail="Shipment not found"
    )

  # 3-LEVEL PRODUCT HEALTH EVALUATION LOGIC
  calculated_health = "Optimal"
  alert_messages = []

  # Compromised Conditions (Level 3)
  if data.light_lux >= 50.0:
    calculated_health = "Compromised"
    shipment.seal_status = "BREACHED"
    alert_messages.append(
        f"CRITICAL TAMPER: Optical lid opening detected ({data.light_lux} LUX)!"
    )
  elif data.temperature > 15.0 or data.accel_g >= 3.0:
    calculated_health = "Compromised"
    alert_messages.append(
        f"CRITICAL EXCURSION: Severe shock ({data.accel_g}g) or extreme heat"
        f" ({data.temperature}°C)!"
    )
  # Degraded Conditions (Level 2)
  elif (
      (data.temperature > 8.0 and data.temperature <= 15.0)
      or (data.accel_g >= 1.5 and data.accel_g < 3.0)
      or (data.humidity >= 65.0)
  ):
    calculated_health = "Degraded"
    alert_messages.append(
        f"WARNING: Environmental stress (Temp: {data.temperature}°C, Impact:"
        f" {data.accel_g}g)"
    )

  shipment.health_level = calculated_health

  # Cryptographic Hash Chain Ledger Calculation
  last_event = (
      db.query(SensorEvent)
      .filter(SensorEvent.shipment_id == shipment.id)
      .order_by(SensorEvent.id.desc())
      .first()
  )
  prev_hash = last_event.record_hash if last_event else "0" * 64

  event_payload_str = f"{shipment.id}|{data.device_id}|{data.light_lux}|{data.temperature}|{data.humidity}|{data.accel_g}|{prev_hash}"
  curr_hash = hashlib.sha256(event_payload_str.encode("utf-8")).hexdigest()

  # Persist Sensor Event
  event = SensorEvent(
      shipment_id=shipment.id,
      device_id=data.device_id,
      light_lux=data.light_lux,
      temperature=data.temperature,
      humidity=data.humidity,
      accel_g=data.accel_g,
      gyro_dps=data.gyro_dps,
      health_level=calculated_health,
      previous_hash=prev_hash,
      record_hash=curr_hash,
  )
  db.add(event)

  # Persist Alerts
  for msg in alert_messages:
    db.add(
        ShipmentAlert(
            shipment_id=shipment.id,
            severity=(
                "Critical" if calculated_health == "Compromised" else "Warning"
            ),
            alert_type="Tamper/Environmental Excursion",
            warehouse_location=data.warehouse_location,
            message=msg,
        )
    )

  db.commit()
  return {
      "status": "success",
      "health_level": calculated_health,
      "seal_status": shipment.seal_status,
      "event_hash": curr_hash,
  }


# ==========================================
# SHIPMENT & AUDIT QUERY ENDPOINTS
# ==========================================
@app.get("/api/shipments/{code}")
def get_shipment_details(code: str, db: Session = Depends(get_db)):
  shipment = db.query(Shipment).filter(Shipment.shipment_code == code).first()
  if not shipment:
    raise HTTPException(status_code=404, detail="Shipment not found")

  recent_events = (
      db.query(SensorEvent)
      .filter(SensorEvent.shipment_id == shipment.id)
      .order_by(SensorEvent.id.desc())
      .limit(15)
      .all()
  )
  alerts = (
      db.query(ShipmentAlert)
      .filter(ShipmentAlert.shipment_id == shipment.id)
      .order_by(ShipmentAlert.id.desc())
      .all()
  )

  return {
      "shipment": {
          "code": shipment.shipment_code,
          "title": shipment.title,
          "sender": shipment.sender,
          "recipient": shipment.recipient_name,
          "origin": shipment.origin,
          "destination": shipment.destination,
          "current_warehouse": shipment.current_warehouse,
          "status": shipment.status,
          "seal_status": shipment.seal_status,
          "health_level": shipment.health_level,
      },
      "latest_telemetry": recent_events[0] if recent_events else None,
      "events": recent_events,
      "alerts": alerts,
  }


@app.get("/api/admin/audit-logs")
def get_admin_audit_logs(db: Session = Depends(get_db)):
  events = (
      db.query(SensorEvent).order_by(SensorEvent.id.desc()).limit(50).all()
  )
  alerts = (
      db.query(ShipmentAlert).order_by(ShipmentAlert.id.desc()).limit(50).all()
  )
  return {"events": events, "alerts": alerts}