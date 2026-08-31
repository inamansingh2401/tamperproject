import hashlib
import os
from auth import create_access_token, get_password_hash, verify_password
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
SEAL_TAMPER_LUX_THRESHOLD = 800.0
DEMO_RESET = os.getenv("DEMO_RESET", "false").lower() == "true"
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base.metadata.create_all(bind=engine)

app = FastAPI(title="SafeTrack Unified Cryptographic API", version="2.8.0")

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


@app.on_event("startup")
def startup_db_seed():
    db = SessionLocal()
    try:
        # Seed default Admin
        if not db.query(User).filter(User.username == "admin").first():
            db.add(
                User(
                    username="admin",
                    hashed_password=get_password_hash("admin123"),
                    role="admin",
                )
            )

        # Seed default User
        if not db.query(User).filter(User.username == "Rahul Sharma").first():
            db.add(
                User(
                    username="Rahul Sharma",
                    hashed_password=get_password_hash("1234"),
                    role="user",
                )
            )

        # Seed default Device
        if not db.query(Device).filter(
            Device.device_id == "ESP32-S3-TRACKER-01"
        ).first():
            db.add(
                Device(
                    device_id="ESP32-S3-TRACKER-01",
                    api_key="secret_device_key_esp32_2026",
                )
            )

        db.commit()

        shipment = (
            db.query(Shipment)
            .filter(Shipment.shipment_code == "PRCL-2024-05-21-001")
            .first()
        )

        if not shipment:
            shipment = Shipment(
                shipment_code="PRCL-2024-05-21-001",
                title="Cold-Chain Medicine & Vaccines",
                recipient_name="Rahul Sharma",
                origin="Mumbai Central Hub (18.9696° N, 72.8193° E)",
                destination="Delhi Central Facility (28.6139° N, 77.2090° E)",
                current_warehouse="Rewari Transit Hub, HR",
                status="In Transit",
                seal_status="Intact",
                health_level="Optimal",
            )
            db.add(shipment)
            db.commit()

        # For SIH demo runs, start with a clean incident/telemetry state.
        # This prevents old demo breaches from making the dashboard show
        # stale incident counts such as 110.
        if DEMO_RESET:
            db.query(ShipmentAlert).filter(
                ShipmentAlert.shipment_id == shipment.id
            ).delete(synchronize_session=False)
            db.query(SensorEvent).filter(
                SensorEvent.shipment_id == shipment.id
            ).delete(synchronize_session=False)

            shipment.seal_status = "Intact"
            shipment.health_level = "Optimal"
            shipment.current_warehouse = "Mumbai Central Dispatch Hub"
            db.commit()

        # Ensure a genesis event exists after a reset or first setup.
        if not db.query(SensorEvent).filter(
            SensorEvent.shipment_id == shipment.id
        ).first():
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


class LoginRequest(BaseModel):
  username: str
  password: str
  shipment_code: str = "PRCL-2024-05-21-001"


class GPSSensorIngestPayload(BaseModel):
  device_id: str
  shipment_code: str
  light_lux: float
  temperature: float
  humidity: float
  accel_g: float
  gyro_dps: float = 0.0
  warehouse_location: str = "Rewari Transit Hub, HR"


@app.post("/api/auth/login")
def login(payload: LoginRequest, db: Session = Depends(get_db)):
  user = db.query(User).filter(User.username == payload.username).first()
  if not user or not verify_password(payload.password, user.hashed_password):
    raise HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Invalid username or security passcode",
    )

  shipment = (
      db.query(Shipment)
      .filter(Shipment.shipment_code == payload.shipment_code)
      .first()
  )
  if not shipment:
    raise HTTPException(
        status_code=status.HTTP_404_NOT_FOUND,
        detail=f"Shipment {payload.shipment_code} not found in ledger",
    )

  token = create_access_token({"sub": user.username, "role": user.role})
  return {
      "access_token": token,
      "token_type": "bearer",
      "username": user.username,
      "role": user.role,
      "shipment_code": shipment.shipment_code,
  }


@app.post("/api/events")
def ingest_sensor_telemetry(
    data: GPSSensorIngestPayload,
    x_device_key: str = Header(None),
    db: Session = Depends(get_db),
):
  device = db.query(Device).filter(Device.device_id == data.device_id).first()
  if x_device_key and device and device.api_key != x_device_key:
    raise HTTPException(
        status_code=status.HTTP_403_FORBIDDEN, detail="Invalid Device Key"
    )

  shipment = (
      db.query(Shipment)
      .filter(Shipment.shipment_code == data.shipment_code)
      .first()
  )
  if not shipment:
    raise HTTPException(status_code=404, detail="Shipment not found")

  # 3-Tier Health Engine
  calculated_health = "Optimal"
  alert_messages = []

  if data.light_lux >= SEAL_TAMPER_LUX_THRESHOLD:
    calculated_health = "Compromised"
    shipment.seal_status = "BREACHED"
    alert_messages.append(
        f"CRITICAL TAMPER: Container opened ({data.light_lux} LUX; threshold {SEAL_TAMPER_LUX_THRESHOLD:.0f} LUX) at"
        f" {data.warehouse_location}!"
    )
  elif data.temperature > 15.0 or data.accel_g >= 3.0:
    calculated_health = "Compromised"
    alert_messages.append(
        f"CRITICAL EXCURSION: Severe impact ({data.accel_g}g) or heat"
        f" ({data.temperature}°C)!"
    )
  elif (
      (data.temperature > 8.0 and data.temperature <= 15.0)
      or (data.accel_g >= 1.5 and data.accel_g < 3.0)
      or (data.humidity >= 65.0)
  ):
    calculated_health = "Degraded"
    alert_messages.append(
        f"WARNING: Stress parameter (Temp: {data.temperature}°C, Shock:"
        f" {data.accel_g}g)"
    )

  shipment.health_level = calculated_health
  shipment.current_warehouse = data.warehouse_location

  # SHA-256 Block Chain Calculation
  last_event = (
      db.query(SensorEvent)
      .filter(SensorEvent.shipment_id == shipment.id)
      .order_by(SensorEvent.id.desc())
      .first()
  )
  prev_hash = last_event.record_hash if last_event else "0" * 64

  payload_str = (
      f"{shipment.id}|"
      f"{data.device_id}|"
      f"{data.light_lux}|"
      f"{data.temperature}|"
      f"{data.humidity}|"
      f"{data.accel_g}|"
      f"{prev_hash}"
  )
  curr_hash = hashlib.sha256(payload_str.encode("utf-8")).hexdigest()

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

  for msg in alert_messages:
    db.add(
        ShipmentAlert(
            shipment_id=shipment.id,
            severity=(
                "Critical" if calculated_health == "Compromised" else "Warning"
            ),
            alert_type="Security / Excursion",
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


@app.get("/api/shipments/{code}")
def get_shipment_details(code: str, db: Session = Depends(get_db)):
  shipment = db.query(Shipment).filter(Shipment.shipment_code == code).first()
  if not shipment:
    raise HTTPException(status_code=404, detail="Shipment not found")

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

  return {
      "shipment": {
          "code": shipment.shipment_code,
          "title": shipment.title,
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