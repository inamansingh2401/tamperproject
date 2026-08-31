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
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import relationship

Base = declarative_base()


class User(Base):
  __tablename__ = "users"
  id = Column(Integer, primary_key=True, index=True)
  username = Column(String(50), unique=True, index=True, nullable=False)
  hashed_password = Column(String(255), nullable=False)
  role = Column(String(20), default="user", nullable=False)  # 'admin' or 'user'
  created_at = Column(DateTime, default=datetime.datetime.utcnow)


class Device(Base):
  __tablename__ = "devices"
  id = Column(Integer, primary_key=True, index=True)
  device_id = Column(String(64), unique=True, index=True, nullable=False)
  api_key = Column(String(64), nullable=False)
  status = Column(String(20), default="active")
  created_at = Column(DateTime, default=datetime.datetime.utcnow)


class Shipment(Base):
  __tablename__ = "shipments"
  id = Column(Integer, primary_key=True, index=True)
  shipment_code = Column(String(64), unique=True, index=True, nullable=False)
  title = Column(String(128), default="Cold-Chain Medicine & Vaccines")
  sender = Column(String(128), default="Serum Bio-Tech Mumbai Hub")
  recipient_name = Column(String(128), default="Rahul Sharma")
  origin = Column(String(128), default="Mumbai Central Hub, MH")
  destination = Column(String(128), default="Delhi Central Warehouse, ND")
  current_warehouse = Column(String(128), default="Rewari Transit Hub, HR")
  status = Column(String(32), default="In Transit")
  seal_status = Column(String(32), default="Intact")  # 'Intact' or 'BREACHED'
  health_level = Column(
      String(32), default="Optimal"
  )  # 'Optimal', 'Degraded', 'Compromised'
  created_at = Column(DateTime, default=datetime.datetime.utcnow)

  events = relationship(
      "SensorEvent", back_populates="shipment", cascade="all, delete-orphan"
  )
  alerts = relationship(
      "ShipmentAlert", back_populates="shipment", cascade="all, delete-orphan"
  )


class SensorEvent(Base):
  __tablename__ = "sensor_events"
  id = Column(Integer, primary_key=True, index=True)
  shipment_id = Column(Integer, ForeignKey("shipments.id"), nullable=False)
  device_id = Column(String(64), nullable=False)
  light_lux = Column(Float, default=0.0)  # BH1750
  temperature = Column(Float, default=4.5)  # SHT31
  humidity = Column(Float, default=45.0)  # SHT31
  accel_g = Column(Float, default=1.0)  # MPU6050
  gyro_dps = Column(Float, default=0.0)  # MPU6050
  health_level = Column(String(32), default="Optimal")
  previous_hash = Column(String(64), nullable=False)
  record_hash = Column(String(64), nullable=False)
  created_at = Column(DateTime, default=datetime.datetime.utcnow)

  shipment = relationship("Shipment", back_populates="events")


class ShipmentAlert(Base):
  __tablename__ = "shipment_alerts"
  id = Column(Integer, primary_key=True, index=True)
  shipment_id = Column(Integer, ForeignKey("shipments.id"), nullable=False)
  severity = Column(String(16), default="Critical")
  alert_type = Column(String(64), nullable=False)
  warehouse_location = Column(String(128), default="En-Route")
  message = Column(Text, nullable=False)
  created_at = Column(DateTime, default=datetime.datetime.utcnow)

  shipment = relationship("Shipment", back_populates="alerts")