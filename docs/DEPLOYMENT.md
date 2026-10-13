# Deployment guide

## Frontend

From `Tamper_admin/frontend`:

```powershell
npm install
npm run build
npx vercel --prod
```

The static site includes the shared login, admin pages, `user/`, `vendor/` and active video assets. Keep Vercel project metadata private. Assign the public alias `safetrack-portal.vercel.app` in the owning Vercel account after deployment; manual aliases must point to the latest release.

## API

Deploy `Tamper_admin/backend` using its existing Vercel configuration. Set `DATABASE_URL`, `JWT_SECRET`, `DEVICE_API_KEY`, `BOOTSTRAP_ADMIN_PASSWORD`, `DEMO_USER_PASSWORD` and `SAFETRACK_ENV` privately. Set `CORS_ORIGINS` to approved frontend origins, including `https://safetrack-portal.vercel.app`. Redeploy after environment changes. The API routes use `/api`; a 404 at the root does not establish an outage.

## Gateway and hardware

Follow `LIVE_GATEWAY_RUNBOOK.md`. Configure private hotspot credentials, device enrollment and the gateway LAN address locally. Firmware sends signed readings to the gateway; the gateway verifies, queues and forwards them to the API. A second laptop can run the gateway on the same LAN. The web portal does not require USB, but fresh readings require the hardware, network and gateway.

## Database recovery and migration status

As of 13 October 2026, the Render free PostgreSQL database is suspended after expiring on 12 October. The Vercel backend fails to connect during startup, and login returns HTTP 500. Supabase PostgreSQL has been selected as the replacement, but migration and the production `DATABASE_URL` change are not complete.

Preserve the suspended database and existing gateway outbox. Export the current PostgreSQL data if Render recovery becomes available; do not assume an expired database can be queried. Historical local SQLite snapshots exist, but the inspected snapshot's latest sensor event is 4 September 2026, so restoring it would omit newer history. The existing `backend/migrate_sqlite_to_postgres.py` supports copying SQLite into an empty PostgreSQL target; do not use `--replace` against existing data without reviewing the target.

Use a private TLS-enabled PostgreSQL connection string for the replacement. Keep existing JWT/device secrets and authorization behavior. Protect application tables from Supabase's public Data API; dashboards continue to use the existing FastAPI API. Redeploy the existing backend after updating its environment, then verify admin/user login, shipment access, live readings, and ledger history before declaring recovery complete. Supabase Free has storage and inactivity limits, so it is not an uptime guarantee.

## Release checks

1. Build the frontend and run `python -m unittest discover -s tests -p test_security.py` in an isolated environment with backend dependencies installed.
2. Verify real admin/user login, role routing, assigned shipment access and logout.
3. Verify Vehicles navigation, fleet search/filter, vehicle details and return navigation.
4. Verify shipment readings, parcel tilt, reset camera, animation playback and mobile layout.
5. Check gateway status, record freshness and delivery acknowledgements separately from webpage availability.

Never publish `.env`, local configuration, passwords, private keys, databases, runtime logs or unpublished presentation files. Ignoring a file does not remove it from prior Git history; rotate credentials if any have previously been exposed.
