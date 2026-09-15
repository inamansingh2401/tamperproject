import datetime
from sqlalchemy import (
    Boolean,
    Column,
    DateTime,
    Float,
    ForeignKey,
    Integer,
    String,
    Text,
)
from database import Base
from sqlalchemy.orm import relationship

class User(Base):
    __tablename__ = "users"
    id = Column(Integer, primary_key=True, index=True)
    username = Column(String(64), unique=True, index=True, nullable=False)
    email = Column(String(128), unique=True, index=True, nullable=True)
    hashed_password = Column(String(255), nullable=False)
    role = Column(String(32), default="user", nullable=False)  # 'admin' or 'user'
    status = Column(String(32), default="Active")
    assigned_vehicles = Column(Text, default="[]")  # JSON list of assigned shipment codes (legacy column name)
    created_at = Column(DateTime, default=datetime.datetime.utcnow)
    last_login = Column(String(64), default="Never")

class Device(Base):
    __tablename__ = "devices"
    id = Column(Integer, primary_key=True, index=True)
    device_id = Column(String(64), unique=True, index=True, nullable=False)
    api_key = Column(String(64), nullable=False)
    status = Column(String(32), default="active")
    created_at = Column(DateTime, default=datetime.datetime.utcnow)

class Vehicle(Base):
    __tablename__ = "vehicles"
    id = Column(Integer, primary_key=True, index=True)
    vehicle_code = Column(String(64), unique=True, index=True, nullable=False)
    name = Column(String(128), default="Volvo Cold-Chain Express 01")
    license_plate = Column(String(64), default="MH-04-JK-9021")
    driver = Column(String(128), default="Rajesh Kumar (DRV-882)")
    assigned_shipments = Column(Text, default="[]")  # JSON list of shipment codes
    origin = Column(String(128), default="Mumbai Central Hub, MH")
    destination = Column(String(128), default="Delhi Central Warehouse, ND")
    current_hub = Column(String(128), default="Rewari Transit Hub, HR")
    status = Column(String(32), default="In Transit")  # 'In Transit', 'At Warehouse', 'Delayed', 'Stopped', 'Available'
    created_at = Column(DateTime, default=datetime.datetime.utcnow)
    last_update = Column(String(64), default="Just now")

class Shipment(Base):
    __tablename__ = "shipments"
    id = Column(Integer, primary_key=True, index=True)
    shipment_code = Column(String(64), unique=True, index=True, nullable=False)
    vehicle_id = Column(String(64), default="TRK-MH-001")
    title = Column(String(128), default="Cold-Chain Medicine & Vaccines")
    sender = Column(String(128), default="Serum Bio-Tech Mumbai Hub")
    recipient_name = Column(String(128), default="Rahul Sharma")
    origin = Column(String(128), default="Mumbai Central Hub, MH")
    destination = Column(String(128), default="Delhi Central Warehouse, ND")
    current_warehouse = Column(String(128), default="Rewari Transit Hub, HR")
    status = Column(String(32), default="In Transit")
    seal_status = Column(String(32), default="Intact")  # 'Intact' or 'BREACHED'
    health_level = Column(String(32), default="Optimal")  # 'Optimal', 'Degraded', 'Compromised'
    latest_temperature = Column(Float, default=4.2)
    latest_light = Column(Float, default=0.0)
    latest_humidity = Column(Float, default=45.0)
    latest_shock = Column(String(64), default="Normal (0.2g)")
    created_at = Column(DateTime, default=datetime.datetime.utcnow)

    events = relationship("SensorEvent", back_populates="shipment", cascade="all, delete-orphan")
    alerts = relationship("ShipmentAlert", back_populates="shipment", cascade="all, delete-orphan")

class SensorEvent(Base):
    __tablename__ = "sensor_events"
    id = Column(Integer, primary_key=True, index=True)
    event_id = Column(String(128), unique=True, index=True, nullable=True)
    shipment_id = Column(Integer, ForeignKey("shipments.id"), nullable=False)
    device_id = Column(String(64), nullable=False)
    orientation_q = Column(Text, nullable=True)
    mpu_read_ok = Column(Boolean, nullable=True)
    light_lux = Column(Float, default=0.0)
    temperature = Column(Float, default=4.5)
    humidity = Column(Float, default=45.0)
    accel_g = Column(Float, default=1.0)
    gyro_dps = Column(Float, default=0.0)
    accel_x = Column(Float, nullable=True, default=0.0)
    accel_y = Column(Float, nullable=True, default=0.0)
    accel_z = Column(Float, nullable=True, default=1.0)
    gyro_x = Column(Float, nullable=True, default=0.0)
    gyro_y = Column(Float, nullable=True, default=0.0)
    gyro_z = Column(Float, nullable=True, default=0.0)
    shock_g = Column(Float, nullable=True, default=0.0)
    pitch = Column(Float, nullable=True, default=0.0)
    roll = Column(Float, nullable=True, default=0.0)
    health_level = Column(String(32), default="Optimal")
    previous_hash = Column(String(64), nullable=False)
    record_hash = Column(String(64), nullable=False)
    created_at = Column(DateTime, default=datetime.datetime.utcnow)

    shipment = relationship("Shipment", back_populates="events")

class ShipmentAlert(Base):
    __tablename__ = "shipment_alerts"
    id = Column(Integer, primary_key=True, index=True)
    shipment_id = Column(Integer, ForeignKey("shipments.id"), nullable=False)
    vehicle_id = Column(String(64), default="TRK-MH-001")
    severity = Column(String(32), default="Critical")  # 'Critical', 'Warning', 'Resolved'
    alert_type = Column(String(64), nullable=False)
    warehouse_location = Column(String(128), default="En-Route")
    message = Column(Text, nullable=False)
    status = Column(String(32), default="Active")  # 'Active' or 'Resolved'
    created_at = Column(DateTime, default=datetime.datetime.utcnow)

    shipment = relationship("Shipment", back_populates="alerts")

class SystemSetting(Base):
    __tablename__ = "system_settings"
    id = Column(Integer, primary_key=True, index=True)
    category = Column(String(64), nullable=False)
    key = Column(String(64), nullable=False)
    value = Column(Text, nullable=False)
