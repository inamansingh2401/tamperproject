"""Migration metadata, including the index already created by legacy startup."""
from pathlib import Path
import sys
from sqlalchemy import Index, MetaData

sys.path.insert(0, str(Path(__file__).resolve().parents[1]/'Tamper_admin/backend'))
from database import Base
import models  # Register tables without importing application startup.

target_metadata = MetaData()
for table in Base.metadata.sorted_tables:
    table.to_metadata(target_metadata)
Index('ix_events_shipment_time', target_metadata.tables['sensor_events'].c.shipment_id,
      target_metadata.tables['sensor_events'].c.created_at, target_metadata.tables['sensor_events'].c.id)
