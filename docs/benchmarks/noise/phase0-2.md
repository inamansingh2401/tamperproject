# Phase 0 baseline

Measured 2026-11-08T07:57:47.968082+00:00 at application commit 6d108ca257b4b80b225d5ef17277d85cf764f1f1.

Environment: Windows-11-10.0.26300-SP0, Python 3.13.7, PostgreSQL 18.6 on x86_64-windows, compiled by msvc-19.44.35228, 64-bit.
Dataset counts: {'sensor_events': 100000, 'devices': 110, 'shipments': 110, 'shipment_alerts': 2978}. Database bytes including indexes: 61,544,127.

Synthetic legacy-format, hash-linked events with exposure, shock and temperature excursions. No hardware signatures. Bulk seeding bypasses ingestion.
Serial FastAPI TestClient requests, concurrency 1, three warmups and 30 timed requests per endpoint. JWT authentication, serialization and SQL included. Login excluded. Local PostgreSQL, warm caches, no network/TLS/browser rendering. p50/p95 use nearest-rank percentiles.
API startup also adds its existing demo shipments/devices/vehicles. The seeded benchmark shipment is used for detail/live/evidence reads.

| Endpoint | p50 ms | p95 ms | DB calls/request | Response bytes |
| --- | ---: | ---: | ---: | ---: |
| /api/admin/dashboard | 5.916 | 6.823 | 5 | 127 |
| /api/vehicles | 4.862 | 6.032 | 2 | 35584 |
| /api/shipments | 52.332 | 79.24 | 112 | 56816 |
| /api/alerts | 1035.841 | 1234.611 | 2980 | 726499 |
| /api/shipments/BENCH-SHIP-00000 | 6.589 | 7.904 | 6 | 26201 |
| /api/shipments/BENCH-SHIP-00000/live | 3.1 | 4.207 | 3 | 841 |
| /api/shipments/BENCH-SHIP-00000/evidence?limit=100 | 10.679 | 12.129 | 4 | 70716 |
| /api/reports/summary | 44.98 | 112.09 | 9 | 644 |

## Slow SQL plans

Exact application-generated statements, parameters and PostgreSQL EXPLAIN ANALYZE BUFFERS output follow. Ranking uses mean cursor execution time, excluding ORM hydration and response serialization. Plans run after the timed API requests.

### /api/reports/summary

Mean SQL execution 7.855 ms.

```sql
SELECT count(sensor_events.id) AS count_1 
FROM sensor_events 
WHERE sensor_events.temperature IS NOT NULL
```

Parameters: {}

```json
[
  {
    "Plan": {
      "Node Type": "Aggregate",
      "Strategy": "Plain",
      "Partial Mode": "Simple",
      "Parallel Aware": false,
      "Async Capable": false,
      "Startup Cost": 5796.0,
      "Total Cost": 5796.01,
      "Plan Rows": 1,
      "Plan Width": 8,
      "Actual Startup Time": 10.472,
      "Actual Total Time": 10.473,
      "Actual Rows": 1.0,
      "Actual Loops": 1,
      "Disabled": false,
      "Shared Hit Blocks": 4546,
      "Shared Read Blocks": 0,
      "Shared Dirtied Blocks": 0,
      "Shared Written Blocks": 0,
      "Local Hit Blocks": 0,
      "Local Read Blocks": 0,
      "Local Dirtied Blocks": 0,
      "Local Written Blocks": 0,
      "Temp Read Blocks": 0,
      "Temp Written Blocks": 0,
      "Plans": [
        {
          "Node Type": "Seq Scan",
          "Parent Relationship": "Outer",
          "Parallel Aware": false,
          "Async Capable": false,
          "Relation Name": "sensor_events",
          "Alias": "sensor_events",
          "Startup Cost": 0.0,
          "Total Cost": 5546.0,
          "Plan Rows": 100000,
          "Plan Width": 4,
          "Actual Startup Time": 0.014,
          "Actual Total Time": 7.549,
          "Actual Rows": 100000.0,
          "Actual Loops": 1,
          "Disabled": false,
          "Filter": "(temperature IS NOT NULL)",
          "Rows Removed by Filter": 0,
          "Shared Hit Blocks": 4546,
          "Shared Read Blocks": 0,
          "Shared Dirtied Blocks": 0,
          "Shared Written Blocks": 0,
          "Local Hit Blocks": 0,
          "Local Read Blocks": 0,
          "Local Dirtied Blocks": 0,
          "Local Written Blocks": 0,
          "Temp Read Blocks": 0,
          "Temp Written Blocks": 0
        }
      ]
    },
    "Planning": {
      "Shared Hit Blocks": 0,
      "Shared Read Blocks": 0,
      "Shared Dirtied Blocks": 0,
      "Shared Written Blocks": 0,
      "Local Hit Blocks": 0,
      "Local Read Blocks": 0,
      "Local Dirtied Blocks": 0,
      "Local Written Blocks": 0,
      "Temp Read Blocks": 0,
      "Temp Written Blocks": 0
    },
    "Planning Time": 0.08,
    "Triggers": [],
    "Execution Time": 10.495
  }
]
```

### /api/reports/summary

Mean SQL execution 7.748 ms.

```sql
SELECT count(sensor_events.id) AS count_1 
FROM sensor_events 
WHERE sensor_events.temperature BETWEEN %(temperature_1)s AND %(temperature_2)s
```

Parameters: {"temperature_1": 2.0, "temperature_2": 8.0}

```json
[
  {
    "Plan": {
      "Node Type": "Aggregate",
      "Strategy": "Plain",
      "Partial Mode": "Simple",
      "Parallel Aware": false,
      "Async Capable": false,
      "Startup Cost": 6284.48,
      "Total Cost": 6284.49,
      "Plan Rows": 1,
      "Plan Width": 8,
      "Actual Startup Time": 10.721,
      "Actual Total Time": 10.721,
      "Actual Rows": 1.0,
      "Actual Loops": 1,
      "Disabled": false,
      "Shared Hit Blocks": 4546,
      "Shared Read Blocks": 0,
      "Shared Dirtied Blocks": 0,
      "Shared Written Blocks": 0,
      "Local Hit Blocks": 0,
      "Local Read Blocks": 0,
      "Local Dirtied Blocks": 0,
      "Local Written Blocks": 0,
      "Temp Read Blocks": 0,
      "Temp Written Blocks": 0,
      "Plans": [
        {
          "Node Type": "Seq Scan",
          "Parent Relationship": "Outer",
          "Parallel Aware": false,
          "Async Capable": false,
          "Relation Name": "sensor_events",
          "Alias": "sensor_events",
          "Startup Cost": 0.0,
          "Total Cost": 6046.0,
          "Plan Rows": 95394,
          "Plan Width": 4,
          "Actual Startup Time": 0.013,
          "Actual Total Time": 7.759,
          "Actual Rows": 95761.0,
          "Actual Loops": 1,
          "Disabled": false,
          "Filter": "((temperature >= '2'::double precision) AND (temperature <= '8'::double precision))",
          "Rows Removed by Filter": 4239,
          "Shared Hit Blocks": 4546,
          "Shared Read Blocks": 0,
          "Shared Dirtied Blocks": 0,
          "Shared Written Blocks": 0,
          "Local Hit Blocks": 0,
          "Local Read Blocks": 0,
          "Local Dirtied Blocks": 0,
          "Local Written Blocks": 0,
          "Temp Read Blocks": 0,
          "Temp Written Blocks": 0
        }
      ]
    },
    "Planning": {
      "Shared Hit Blocks": 0,
      "Shared Read Blocks": 0,
      "Shared Dirtied Blocks": 0,
      "Shared Written Blocks": 0,
      "Local Hit Blocks": 0,
      "Local Read Blocks": 0,
      "Local Dirtied Blocks": 0,
      "Local Written Blocks": 0,
      "Temp Read Blocks": 0,
      "Temp Written Blocks": 0
    },
    "Planning Time": 0.115,
    "Triggers": [],
    "Execution Time": 10.742
  }
]
```

### /api/reports/summary

Mean SQL execution 4.873 ms.

```sql
SELECT count(*) AS count_1 
FROM (SELECT sensor_events.id AS sensor_events_id, sensor_events.event_id AS sensor_events_event_id, sensor_events.shipment_id AS sensor_events_shipment_id, sensor_events.device_id AS sensor_events_device_id, sensor_events.orientation_q AS sensor_events_orientation_q, sensor_events.mpu_read_ok AS sensor_events_mpu_read_ok, sensor_events.light_lux AS sensor_events_light_lux, sensor_events.temperature AS sensor_events_temperature, sensor_events.humidity AS sensor_events_humidity, sensor_events.accel_g AS sensor_events_accel_g, sensor_events.gyro_dps AS sensor_events_gyro_dps, sensor_events.accel_x AS sensor_events_accel_x, sensor_events.accel_y AS sensor_events_accel_y, sensor_events.accel_z AS sensor_events_accel_z, sensor_events.gyro_x AS sensor_events_gyro_x, sensor_events.gyro_y AS sensor_events_gyro_y, sensor_events.gyro_z AS sensor_events_gyro_z, sensor_events.shock_g AS sensor_events_shock_g, sensor_events.pitch AS sensor_events_pitch, sensor_events.roll AS sensor_events_roll, sensor_events.health_level AS sensor_events_health_level, sensor_events.previous_hash AS sensor_events_previous_hash, sensor_events.record_hash AS sensor_events_record_hash, sensor_events.evidence_version AS sensor_events_evidence_version, sensor_events.evidence_payload AS sensor_events_evidence_payload, sensor_events.signed_envelope AS sensor_events_signed_envelope, sensor_events.public_key AS sensor_events_public_key, sensor_events.signature_verified AS sensor_events_signature_verified, sensor_events.received_at AS sensor_events_received_at, sensor_events.created_at AS sensor_events_created_at 
FROM sensor_events) AS anon_1
```

Parameters: {}

```json
[
  {
    "Plan": {
      "Node Type": "Aggregate",
      "Strategy": "Plain",
      "Partial Mode": "Simple",
      "Parallel Aware": false,
      "Async Capable": false,
      "Startup Cost": 5796.0,
      "Total Cost": 5796.01,
      "Plan Rows": 1,
      "Plan Width": 8,
      "Actual Startup Time": 7.653,
      "Actual Total Time": 7.653,
      "Actual Rows": 1.0,
      "Actual Loops": 1,
      "Disabled": false,
      "Shared Hit Blocks": 4546,
      "Shared Read Blocks": 0,
      "Shared Dirtied Blocks": 0,
      "Shared Written Blocks": 0,
      "Local Hit Blocks": 0,
      "Local Read Blocks": 0,
      "Local Dirtied Blocks": 0,
      "Local Written Blocks": 0,
      "Temp Read Blocks": 0,
      "Temp Written Blocks": 0,
      "Plans": [
        {
          "Node Type": "Seq Scan",
          "Parent Relationship": "Outer",
          "Parallel Aware": false,
          "Async Capable": false,
          "Relation Name": "sensor_events",
          "Alias": "sensor_events",
          "Startup Cost": 0.0,
          "Total Cost": 5546.0,
          "Plan Rows": 100000,
          "Plan Width": 0,
          "Actual Startup Time": 0.005,
          "Actual Total Time": 4.949,
          "Actual Rows": 100000.0,
          "Actual Loops": 1,
          "Disabled": false,
          "Shared Hit Blocks": 4546,
          "Shared Read Blocks": 0,
          "Shared Dirtied Blocks": 0,
          "Shared Written Blocks": 0,
          "Local Hit Blocks": 0,
          "Local Read Blocks": 0,
          "Local Dirtied Blocks": 0,
          "Local Written Blocks": 0,
          "Temp Read Blocks": 0,
          "Temp Written Blocks": 0
        }
      ]
    },
    "Planning": {
      "Shared Hit Blocks": 0,
      "Shared Read Blocks": 0,
      "Shared Dirtied Blocks": 0,
      "Shared Written Blocks": 0,
      "Local Hit Blocks": 0,
      "Local Read Blocks": 0,
      "Local Dirtied Blocks": 0,
      "Local Written Blocks": 0,
      "Temp Read Blocks": 0,
      "Temp Written Blocks": 0
    },
    "Planning Time": 0.066,
    "Triggers": [],
    "Execution Time": 7.667
  }
]
```

### /api/alerts

Mean SQL execution 1.496 ms.

```sql
SELECT shipment_alerts.id AS shipment_alerts_id, shipment_alerts.shipment_id AS shipment_alerts_shipment_id, shipment_alerts.vehicle_id AS shipment_alerts_vehicle_id, shipment_alerts.severity AS shipment_alerts_severity, shipment_alerts.alert_type AS shipment_alerts_alert_type, shipment_alerts.warehouse_location AS shipment_alerts_warehouse_location, shipment_alerts.message AS shipment_alerts_message, shipment_alerts.status AS shipment_alerts_status, shipment_alerts.created_at AS shipment_alerts_created_at 
FROM shipment_alerts ORDER BY shipment_alerts.id DESC
```

Parameters: {}

```json
[
  {
    "Plan": {
      "Node Type": "Index Scan",
      "Parallel Aware": false,
      "Async Capable": false,
      "Scan Direction": "Backward",
      "Index Name": "ix_shipment_alerts_id",
      "Relation Name": "shipment_alerts",
      "Alias": "shipment_alerts",
      "Startup Cost": 0.28,
      "Total Cost": 140.95,
      "Plan Rows": 2978,
      "Plan Width": 101,
      "Actual Startup Time": 0.011,
      "Actual Total Time": 0.178,
      "Actual Rows": 2978.0,
      "Actual Loops": 1,
      "Disabled": false,
      "Index Searches": 1,
      "Shared Hit Blocks": 59,
      "Shared Read Blocks": 0,
      "Shared Dirtied Blocks": 0,
      "Shared Written Blocks": 0,
      "Local Hit Blocks": 0,
      "Local Read Blocks": 0,
      "Local Dirtied Blocks": 0,
      "Local Written Blocks": 0,
      "Temp Read Blocks": 0,
      "Temp Written Blocks": 0
    },
    "Planning": {
      "Shared Hit Blocks": 0,
      "Shared Read Blocks": 0,
      "Shared Dirtied Blocks": 0,
      "Shared Written Blocks": 0,
      "Local Hit Blocks": 0,
      "Local Read Blocks": 0,
      "Local Dirtied Blocks": 0,
      "Local Written Blocks": 0,
      "Temp Read Blocks": 0,
      "Temp Written Blocks": 0
    },
    "Planning Time": 0.046,
    "Triggers": [],
    "Execution Time": 0.236
  }
]
```

### /api/reports/summary

Mean SQL execution 1.388 ms.

```sql
SELECT shipment_alerts.id AS shipment_alerts_id, shipment_alerts.shipment_id AS shipment_alerts_shipment_id, shipment_alerts.vehicle_id AS shipment_alerts_vehicle_id, shipment_alerts.severity AS shipment_alerts_severity, shipment_alerts.alert_type AS shipment_alerts_alert_type, shipment_alerts.warehouse_location AS shipment_alerts_warehouse_location, shipment_alerts.message AS shipment_alerts_message, shipment_alerts.status AS shipment_alerts_status, shipment_alerts.created_at AS shipment_alerts_created_at 
FROM shipment_alerts
```

Parameters: {}

```json
[
  {
    "Plan": {
      "Node Type": "Seq Scan",
      "Parallel Aware": false,
      "Async Capable": false,
      "Relation Name": "shipment_alerts",
      "Alias": "shipment_alerts",
      "Startup Cost": 0.0,
      "Total Cost": 78.78,
      "Plan Rows": 2978,
      "Plan Width": 101,
      "Actual Startup Time": 0.005,
      "Actual Total Time": 0.108,
      "Actual Rows": 2978.0,
      "Actual Loops": 1,
      "Disabled": false,
      "Shared Hit Blocks": 49,
      "Shared Read Blocks": 0,
      "Shared Dirtied Blocks": 0,
      "Shared Written Blocks": 0,
      "Local Hit Blocks": 0,
      "Local Read Blocks": 0,
      "Local Dirtied Blocks": 0,
      "Local Written Blocks": 0,
      "Temp Read Blocks": 0,
      "Temp Written Blocks": 0
    },
    "Planning": {
      "Shared Hit Blocks": 0,
      "Shared Read Blocks": 0,
      "Shared Dirtied Blocks": 0,
      "Shared Written Blocks": 0,
      "Local Hit Blocks": 0,
      "Local Read Blocks": 0,
      "Local Dirtied Blocks": 0,
      "Local Written Blocks": 0,
      "Temp Read Blocks": 0,
      "Temp Written Blocks": 0
    },
    "Planning Time": 0.022,
    "Triggers": [],
    "Execution Time": 0.166
  }
]
```

## Interpretation and next comparison

These are baseline measurements. No improvement or hosted capacity claim is established. The static admin dashboard loads vehicles, shipments and alerts separately. Its list endpoints must be evaluated together when optimizing query count. Live telemetry uses an existing shipment/time index and evidence already has cursor pagination.
Repeat the same event count, device count, seed, warmups and samples after each change. Raw timings and query plans are in the adjacent JSON file. Measure ingestion and signature-heavy version-2 evidence separately before making claims about those paths.
