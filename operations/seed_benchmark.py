"""Deterministic synthetic telemetry, only in an empty local benchmark database."""
import argparse
from datetime import datetime, timedelta
import os
from pathlib import Path
import random
import sys
import time

from sqlalchemy import create_engine, inspect, insert
from sqlalchemy.engine import make_url

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'Tamper_admin/backend'))


def validate_target(url):
    target = make_url(url)
    if (target.drivername != 'postgresql+psycopg'
            or target.host not in ('localhost', '127.0.0.1')
            or target.database != 'safetrack_benchmark'):
        raise ValueError('Use a loopback PostgreSQL database named safetrack_benchmark')
    return target


def seed(url, count=100000, devices=100, random_seed=20261108):
    validate_target(url)
    if not 1 <= devices <= count or count < 1:
        raise ValueError('Require 1 <= devices <= events')
    os.environ['DATABASE_URL'] = url
    # Import only models, never main: importing main creates/migrates tables.
    from database import Base
    from models import Device, SensorEvent, Shipment, ShipmentAlert, Vehicle
    from hashchain import calculate_event_hash
    engine = create_engine(url)
    try:
        if inspect(engine).get_table_names():
            raise ValueError('Refusing to seed a non-empty database')
        Base.metadata.create_all(engine)
        rng = random.Random(random_seed)
        start = datetime(2026, 1, 1)
        previous = ['0' * 64] * devices
        latest = {}
        alerts = []
        started = time.perf_counter()
        with engine.begin() as conn:
            # Same index supplied by existing application startup.
            from sqlalchemy import text
            conn.execute(text('CREATE INDEX ix_events_shipment_time ON sensor_events (shipment_id, created_at, id)'))
            for i in range(devices):
                code = f'BENCH-SHIP-{i:05d}'
                vehicle = f'BENCH-TRUCK-{i:05d}'
                conn.execute(insert(Vehicle), dict(vehicle_code=vehicle, assigned_shipments='["' + code + '"]'))
                conn.execute(insert(Shipment), dict(id=i+1, shipment_code=code, vehicle_id=vehicle))
                # This fixture is read-only. Device authentication is disabled by
                # status, and no device credential is generated or persisted.
                conn.execute(insert(Device), dict(device_id=f'BENCH-DEVICE-{i:05d}', api_key='', status='inactive', shipment_code=code))
            batch = []
            for n in range(count):
                i = n % devices
                exposure = rng.random() < .02
                shock = rng.random() < .01
                temperature = round(rng.gauss(5, 1.2) + (8 if rng.random() < .03 else 0), 3)
                light = float(rng.randint(810, 1000) if exposure else rng.randint(0, 30))
                humidity = round(rng.uniform(35, 65), 3)
                accel = round(rng.uniform(2.6, 4) if shock else rng.uniform(.9, 1.2), 3)
                device = f'BENCH-DEVICE-{i:05d}'
                stamp = start + timedelta(seconds=n // devices)
                digest = calculate_event_hash(i+1, device, light, temperature, humidity, accel, previous[i])
                health = 'Compromised' if exposure or shock else 'Degraded' if temperature > 8 else 'Optimal'
                batch.append(dict(event_id=f'bench-{n:09d}', shipment_id=i+1, device_id=device,
                    light_lux=light, temperature=temperature, humidity=humidity, accel_g=accel,
                    health_level=health, previous_hash=previous[i], record_hash=digest,
                    evidence_version=1, signature_verified=False, created_at=stamp, received_at=stamp))
                previous[i] = digest
                latest[i] = dict(latest_temperature=temperature, latest_light=light, latest_humidity=humidity,
                                 health_level=health, seal_status='COMPROMISED' if exposure else 'INTACT')
                if exposure or shock:
                    alerts.append(dict(shipment_id=i+1, vehicle_id=f'BENCH-TRUCK-{i:05d}',
                        alert_type='Seal Tamper' if exposure else 'Impact Shock', message='SYNTHETIC benchmark incident',
                        status='Active' if n >= count-devices else 'Resolved', created_at=stamp))
                if len(batch) == 2000:
                    conn.execute(insert(SensorEvent), batch)
                    batch.clear()
            if batch:
                conn.execute(insert(SensorEvent), batch)
            if alerts:
                conn.execute(insert(ShipmentAlert), alerts)
            for i, values in latest.items():
                conn.execute(Shipment.__table__.update().where(Shipment.id == i+1).values(**values))
            # Explicit shipment IDs must not collide with normal startup seeds.
            conn.execute(text("SELECT setval(pg_get_serial_sequence('shipments','id'), (SELECT max(id) FROM shipments))"))
            conn.execute(text('ANALYZE'))
        return dict(events=count, devices=devices, shipments=devices, alerts=len(alerts),
                    random_seed=random_seed, seed_seconds=round(time.perf_counter()-started, 3))
    finally:
        engine.dispose()


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--events', type=int, default=100000, choices=range(100000, 500001), metavar='100000..500000')
    parser.add_argument('--devices', type=int, default=100)
    args = parser.parse_args()
    import json
    print(json.dumps(seed(os.environ['BENCHMARK_DATABASE_URL'], args.events, args.devices)))
