# API benchmark run

Measured 2026-11-08T07:58:05.899308+00:00 at application commit e212a312435b7f8634f8cf7b6d91295d9129560b.

Environment: Windows-11-10.0.26300-SP0, Python 3.13.7, PostgreSQL 18.6 on x86_64-windows, compiled by msvc-19.44.35228, 64-bit.
Dataset counts: {'sensor_events': 100000, 'devices': 110, 'shipments': 110, 'shipment_alerts': 2978}. Database bytes including indexes: 64,788,159.

Synthetic legacy-format, hash-linked events with exposure, shock and temperature excursions. No hardware signatures. Bulk seeding bypasses ingestion.
Serial FastAPI TestClient requests, concurrency 1, three warmups and 30 timed requests per endpoint. JWT authentication, serialization and SQL included. Login excluded. Local PostgreSQL, warm caches, no network/TLS/browser rendering. p50/p95 use nearest-rank percentiles.
API startup also adds its existing demo shipments/devices/vehicles. The seeded benchmark shipment is used for detail/live/evidence reads.

| Endpoint | p50 ms | p95 ms | DB calls/request | Response bytes |
| --- | ---: | ---: | ---: | ---: |
| /api/admin/dashboard | 4.244 | 5.204 | 5 | 127 |
| /api/vehicles | 4.005 | 5.111 | 2 | 35584 |
| /api/shipments | 5.954 | 6.973 | 2 | 56816 |
| /api/alerts | 4.513 | 5.018 | 2 | 24432 |
| /api/shipments/BENCH-SHIP-00000 | 7.071 | 7.841 | 6 | 26201 |
| /api/shipments/BENCH-SHIP-00000/live | 3.475 | 4.044 | 3 | 841 |
| /api/shipments/BENCH-SHIP-00000/evidence?limit=100 | 9.002 | 9.944 | 4 | 70716 |
| /api/reports/summary | 16.935 | 18.602 | 8 | 644 |

## Slow SQL plans

Exact application-generated statements, parameters and PostgreSQL EXPLAIN ANALYZE BUFFERS output follow. Ranking uses mean cursor execution time, excluding ORM hydration and response serialization. Plans run after the timed API requests.

### /api/reports/summary

Mean SQL execution 8.709 ms.

```sql
SELECT count(sensor_events.id) AS count_1, count(sensor_events.id) FILTER (WHERE sensor_events.temperature IS NOT NULL) AS anon_1, count(sensor_events.id) FILTER (WHERE sensor_events.temperature BETWEEN %(temperature_1)s AND %(temperature_2)s) AS anon_2 
FROM sensor_events
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
      "Startup Cost": 6796.0,
      "Total Cost": 6796.01,
      "Plan Rows": 1,
      "Plan Width": 24,
      "Actual Startup Time": 11.472,
      "Actual Total Time": 11.473,
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
          "Plan Width": 12,
          "Actual Startup Time": 0.013,
          "Actual Total Time": 5.231,
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
    "Planning Time": 0.079,
    "Triggers": [],
    "Execution Time": 11.497
  }
]
```

### /api/reports/summary

Mean SQL execution 1.962 ms.

```sql
SELECT count(shipment_alerts.id) AS count_1, count(shipment_alerts.id) FILTER (WHERE shipment_alerts.status = %(status_1)s::VARCHAR) AS anon_1, count(shipment_alerts.id) FILTER (WHERE lower(shipment_alerts.alert_type) LIKE '%%' || %(lower_1)s::VARCHAR || '%%') AS anon_2, count(shipment_alerts.id) FILTER (WHERE (lower(shipment_alerts.alert_type) LIKE '%%' || %(lower_2)s::VARCHAR || '%%') OR (lower(shipment_alerts.alert_type) LIKE '%%' || %(lower_3)s::VARCHAR || '%%')) AS anon_3, count(shipment_alerts.id) FILTER (WHERE (lower(shipment_alerts.alert_type) LIKE '%%' || %(lower_4)s::VARCHAR || '%%') OR (lower(shipment_alerts.alert_type) LIKE '%%' || %(lower_5)s::VARCHAR || '%%')) AS anon_4 
FROM shipment_alerts
```

Parameters: {"status_1": "Active", "lower_1": "temp", "lower_2": "tamper", "lower_3": "seal", "lower_4": "shock", "lower_5": "impact"}

```json
[
  {
    "Plan": {
      "Node Type": "Aggregate",
      "Strategy": "Plain",
      "Partial Mode": "Simple",
      "Parallel Aware": false,
      "Async Capable": false,
      "Startup Cost": 197.9,
      "Total Cost": 197.91,
      "Plan Rows": 1,
      "Plan Width": 40,
      "Actual Startup Time": 1.442,
      "Actual Total Time": 1.443,
      "Actual Rows": 1.0,
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
      "Temp Written Blocks": 0,
      "Plans": [
        {
          "Node Type": "Seq Scan",
          "Parent Relationship": "Outer",
          "Parallel Aware": false,
          "Async Capable": false,
          "Relation Name": "shipment_alerts",
          "Alias": "shipment_alerts",
          "Startup Cost": 0.0,
          "Total Cost": 78.78,
          "Plan Rows": 2978,
          "Plan Width": 24,
          "Actual Startup Time": 0.007,
          "Actual Total Time": 0.121,
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
    "Planning Time": 0.065,
    "Triggers": [],
    "Execution Time": 1.455
  }
]
```

### /api/shipments/BENCH-SHIP-00000/evidence?limit=100

Mean SQL execution 0.455 ms.

```sql
SELECT sensor_events.id AS sensor_events_id, sensor_events.event_id AS sensor_events_event_id, sensor_events.shipment_id AS sensor_events_shipment_id, sensor_events.device_id AS sensor_events_device_id, sensor_events.orientation_q AS sensor_events_orientation_q, sensor_events.mpu_read_ok AS sensor_events_mpu_read_ok, sensor_events.light_lux AS sensor_events_light_lux, sensor_events.temperature AS sensor_events_temperature, sensor_events.humidity AS sensor_events_humidity, sensor_events.accel_g AS sensor_events_accel_g, sensor_events.gyro_dps AS sensor_events_gyro_dps, sensor_events.accel_x AS sensor_events_accel_x, sensor_events.accel_y AS sensor_events_accel_y, sensor_events.accel_z AS sensor_events_accel_z, sensor_events.gyro_x AS sensor_events_gyro_x, sensor_events.gyro_y AS sensor_events_gyro_y, sensor_events.gyro_z AS sensor_events_gyro_z, sensor_events.shock_g AS sensor_events_shock_g, sensor_events.pitch AS sensor_events_pitch, sensor_events.roll AS sensor_events_roll, sensor_events.health_level AS sensor_events_health_level, sensor_events.previous_hash AS sensor_events_previous_hash, sensor_events.record_hash AS sensor_events_record_hash, sensor_events.evidence_version AS sensor_events_evidence_version, sensor_events.evidence_payload AS sensor_events_evidence_payload, sensor_events.signed_envelope AS sensor_events_signed_envelope, sensor_events.public_key AS sensor_events_public_key, sensor_events.signature_verified AS sensor_events_signature_verified, sensor_events.received_at AS sensor_events_received_at, sensor_events.created_at AS sensor_events_created_at 
FROM sensor_events 
WHERE sensor_events.shipment_id = %(shipment_id_1)s::INTEGER AND sensor_events.id > %(id_1)s::INTEGER ORDER BY sensor_events.id 
 LIMIT %(param_1)s::INTEGER
```

Parameters: {"shipment_id_1": 1, "id_1": 0, "param_1": 101}

```json
[
  {
    "Plan": {
      "Node Type": "Limit",
      "Parallel Aware": false,
      "Async Capable": false,
      "Startup Cost": 0.29,
      "Total Cost": 368.22,
      "Plan Rows": 101,
      "Plan Width": 443,
      "Actual Startup Time": 0.011,
      "Actual Total Time": 0.071,
      "Actual Rows": 101.0,
      "Actual Loops": 1,
      "Disabled": false,
      "Shared Hit Blocks": 103,
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
          "Node Type": "Index Scan",
          "Parent Relationship": "Outer",
          "Parallel Aware": false,
          "Async Capable": false,
          "Scan Direction": "Forward",
          "Index Name": "ix_events_shipment_id",
          "Relation Name": "sensor_events",
          "Alias": "sensor_events",
          "Startup Cost": 0.29,
          "Total Cost": 3632.21,
          "Plan Rows": 997,
          "Plan Width": 443,
          "Actual Startup Time": 0.011,
          "Actual Total Time": 0.067,
          "Actual Rows": 101.0,
          "Actual Loops": 1,
          "Disabled": false,
          "Index Cond": "((shipment_id = 1) AND (id > 0))",
          "Rows Removed by Index Recheck": 0,
          "Index Searches": 1,
          "Shared Hit Blocks": 103,
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
      "Shared Hit Blocks": 3,
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
    "Planning Time": 0.099,
    "Triggers": [],
    "Execution Time": 0.082
  }
]
```

### /api/shipments

Mean SQL execution 0.449 ms.

```sql
SELECT shipments.shipment_code AS shipments_shipment_code, shipments.title AS shipments_title, shipments.vehicle_id AS shipments_vehicle_id, vehicles.license_plate AS vehicle_registration, shipments.sender AS shipments_sender, shipments.recipient_name AS shipments_recipient_name, shipments.origin AS shipments_origin, shipments.destination AS shipments_destination, shipments.current_warehouse AS shipments_current_warehouse, shipments.status AS shipments_status, shipments.seal_status AS shipments_seal_status, shipments.health_level AS shipments_health_level, shipments.latest_temperature AS shipments_latest_temperature, shipments.latest_light AS shipments_latest_light, shipments.latest_humidity AS shipments_latest_humidity, shipments.latest_shock AS shipments_latest_shock 
FROM shipments LEFT OUTER JOIN vehicles ON vehicles.vehicle_code = shipments.vehicle_id
```

Parameters: {}

```json
[
  {
    "Plan": {
      "Node Type": "Hash Join",
      "Parallel Aware": false,
      "Async Capable": false,
      "Join Type": "Left",
      "Startup Cost": 6.25,
      "Total Cost": 15.52,
      "Plan Rows": 100,
      "Plan Width": 257,
      "Actual Startup Time": 0.025,
      "Actual Total Time": 0.049,
      "Actual Rows": 110.0,
      "Actual Loops": 1,
      "Disabled": false,
      "Inner Unique": true,
      "Hash Cond": "((shipments.vehicle_id)::text = (vehicles.vehicle_code)::text)",
      "Shared Hit Blocks": 12,
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
          "Relation Name": "shipments",
          "Alias": "shipments",
          "Startup Cost": 0.0,
          "Total Cost": 9.0,
          "Plan Rows": 100,
          "Plan Width": 243,
          "Actual Startup Time": 0.005,
          "Actual Total Time": 0.011,
          "Actual Rows": 110.0,
          "Actual Loops": 1,
          "Disabled": false,
          "Shared Hit Blocks": 8,
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
        {
          "Node Type": "Hash",
          "Parent Relationship": "Inner",
          "Parallel Aware": false,
          "Async Capable": false,
          "Startup Cost": 5.0,
          "Total Cost": 5.0,
          "Plan Rows": 100,
          "Plan Width": 32,
          "Actual Startup Time": 0.017,
          "Actual Total Time": 0.017,
          "Actual Rows": 106.0,
          "Actual Loops": 1,
          "Disabled": false,
          "Hash Buckets": 1024,
          "Original Hash Buckets": 1024,
          "Hash Batches": 1,
          "Original Hash Batches": 1,
          "Peak Memory Usage": 15,
          "Shared Hit Blocks": 4,
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
              "Relation Name": "vehicles",
              "Alias": "vehicles",
              "Startup Cost": 0.0,
              "Total Cost": 5.0,
              "Plan Rows": 100,
              "Plan Width": 32,
              "Actual Startup Time": 0.003,
              "Actual Total Time": 0.009,
              "Actual Rows": 106.0,
              "Actual Loops": 1,
              "Disabled": false,
              "Shared Hit Blocks": 4,
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
        }
      ]
    },
    "Planning": {
      "Shared Hit Blocks": 4,
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
    "Planning Time": 0.111,
    "Triggers": [],
    "Execution Time": 0.059
  }
]
```

### /api/alerts

Mean SQL execution 0.394 ms.

```sql
SELECT shipment_alerts.id AS shipment_alerts_id, shipment_alerts.severity AS shipment_alerts_severity, shipment_alerts.alert_type AS shipment_alerts_alert_type, shipments.shipment_code AS shipments_shipment_code, shipment_alerts.vehicle_id AS shipment_alerts_vehicle_id, shipment_alerts.warehouse_location AS shipment_alerts_warehouse_location, shipment_alerts.created_at AS shipment_alerts_created_at, shipment_alerts.message AS shipment_alerts_message, shipment_alerts.status AS shipment_alerts_status 
FROM shipment_alerts LEFT OUTER JOIN shipments ON shipments.id = shipment_alerts.shipment_id ORDER BY shipment_alerts.id DESC 
 LIMIT %(param_1)s::INTEGER
```

Parameters: {"param_1": 100}

```json
[
  {
    "Plan": {
      "Node Type": "Limit",
      "Parallel Aware": false,
      "Async Capable": false,
      "Startup Cost": 0.43,
      "Total Cost": 8.22,
      "Plan Rows": 100,
      "Plan Width": 114,
      "Actual Startup Time": 0.008,
      "Actual Total Time": 0.075,
      "Actual Rows": 100.0,
      "Actual Loops": 1,
      "Disabled": false,
      "Shared Hit Blocks": 137,
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
          "Node Type": "Nested Loop",
          "Parent Relationship": "Outer",
          "Parallel Aware": false,
          "Async Capable": false,
          "Join Type": "Left",
          "Startup Cost": 0.43,
          "Total Cost": 232.43,
          "Plan Rows": 2978,
          "Plan Width": 114,
          "Actual Startup Time": 0.007,
          "Actual Total Time": 0.07,
          "Actual Rows": 100.0,
          "Actual Loops": 1,
          "Disabled": false,
          "Inner Unique": true,
          "Shared Hit Blocks": 137,
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
              "Node Type": "Index Scan",
              "Parent Relationship": "Outer",
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
              "Actual Startup Time": 0.003,
              "Actual Total Time": 0.013,
              "Actual Rows": 100.0,
              "Actual Loops": 1,
              "Disabled": false,
              "Index Searches": 1,
              "Shared Hit Blocks": 5,
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
            {
              "Node Type": "Memoize",
              "Parent Relationship": "Inner",
              "Parallel Aware": false,
              "Async Capable": false,
              "Startup Cost": 0.15,
              "Total Cost": 0.18,
              "Plan Rows": 1,
              "Plan Width": 21,
              "Actual Startup Time": 0.0,
              "Actual Total Time": 0.0,
              "Actual Rows": 1.0,
              "Actual Loops": 100,
              "Disabled": false,
              "Cache Key": "shipment_alerts.shipment_id",
              "Cache Mode": "logical",
              "Cache Hits": 34,
              "Cache Misses": 66,
              "Cache Evictions": 0,
              "Cache Overflows": 0,
              "Peak Memory Usage": 8,
              "Shared Hit Blocks": 132,
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
                  "Node Type": "Index Scan",
                  "Parent Relationship": "Outer",
                  "Parallel Aware": false,
                  "Async Capable": false,
                  "Scan Direction": "Forward",
                  "Index Name": "ix_shipments_id",
                  "Relation Name": "shipments",
                  "Alias": "shipments",
                  "Startup Cost": 0.14,
                  "Total Cost": 0.17,
                  "Plan Rows": 1,
                  "Plan Width": 21,
                  "Actual Startup Time": 0.0,
                  "Actual Total Time": 0.0,
                  "Actual Rows": 1.0,
                  "Actual Loops": 66,
                  "Disabled": false,
                  "Index Cond": "(id = shipment_alerts.shipment_id)",
                  "Rows Removed by Index Recheck": 0,
                  "Index Searches": 66,
                  "Shared Hit Blocks": 132,
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
            }
          ]
        }
      ]
    },
    "Planning": {
      "Shared Hit Blocks": 4,
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
    "Planning Time": 0.072,
    "Triggers": [],
    "Execution Time": 0.087
  }
]
```

## Interpretation and next comparison

These are local measurements. The static admin dashboard loads vehicles, shipments and alerts separately. Its list endpoints must be evaluated together when optimizing query count. Live telemetry uses an existing shipment/time index and evidence already has cursor pagination.
Repeat the same event count, device count, seed, warmups and samples after each change. Raw timings and query plans are in the adjacent JSON file. Measure ingestion and signature-heavy version-2 evidence separately before making claims about those paths.
