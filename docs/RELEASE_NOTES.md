# Release notes

## 13 October 2026 — LDR interpretation and database incident

- Raw LDR ADC readings now map to increasing relative brightness while retaining the existing exposure boundary at 2500 ADC. The stored brightness is not calibrated lux.
- Added a regression check for dark/exposed polarity, seal state, and the live API's returned brightness. Eight security tests pass against an isolated temporary database.
- Production login is currently unavailable because the expired Render PostgreSQL instance is suspended and backend startup cannot connect. Supabase migration is pending; no database cutover has occurred.

## 28 September 2026

## Unified portal

- Shared SafeTrack login with cinematic truck video, audio replay and accessible motion fallback.
- Admin/user role routing on one origin with existing server authorization.
- Separate user sections and restored sensor-driven parcel visualization.
- Dedicated Vehicles page and corrected fleet/detail navigation.
- Independent admin data loading so slow alerts do not block the fleet list.
- Local gateway rotating logs and Windows gateway setup helpers.

## Validation

Production browser checks passed for role login, live shipment data, parcel rendering, video controls, mobile fallback and fleet navigation/search/detail flows. Alert API latency remains a known limitation. Demo values and visual summaries must not be presented as validated production fleet metrics.
