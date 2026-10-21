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

As of 13 October 2026, the Render free PostgreSQL database is suspended after expiring on 12 October. The existing Vercel backend now uses Supabase PostgreSQL via a TLS-enabled session pooler. Admin/user login, admin dashboard access, assigned shipment detail/live reads, and the 30-record ledger returned HTTP 200. A user request to the admin users endpoint returned HTTP 403.

Recovery restored 5 users, 11 shipments, 7 vehicles, 10 devices, 15,333 sensor events, 18 alerts, and 1 settings record from the historical SQLite snapshot. Known account credentials and device keys were reconciled with the installation's private configuration. One previously verified/sent real gateway event was replayed through `/api/events` and appeared in the ledger, adding one event; no fresh hardware delivery test was performed. The production API was redeployed from its existing source with only the database environment changed. Private recovery helpers and credentials remain ignored under `.codex-tools/`.

Preserve the suspended database and existing gateway outbox. Export the current PostgreSQL data if Render recovery becomes available; do not assume an expired database can be queried. The restored snapshot's latest sensor event is 4 September 2026, so newer cloud-only history is not yet recovered. The untouched gateway outbox contains 24,832 retained records and may support a separate, reviewed recovery of newer sensor history. The existing `backend/migrate_sqlite_to_postgres.py` supports copying SQLite into an empty PostgreSQL target; do not use `--replace` against existing data without reviewing the target.

Use a private TLS-enabled PostgreSQL connection string for the replacement. The direct IPv6 address was unreachable from Vercel; the session pooler is verified. Keep existing JWT/device secrets and authorization behavior. Application tables have RLS enabled and `anon`/`authenticated` table privileges revoked; access remains through the authenticated FastAPI backend. Redeploy after environment changes and recheck login, shipment access, readings, and ledger history. Supabase Free has storage and inactivity limits, so it is not an uptime guarantee.

## Release checks

### 20 October 2026 — Free-tier inactivity pause and recovery

Supabase automatically paused `Tamper_Project` (`lrkkdbdyrelclmaypazq`) for inactivity. Resuming the existing project through Supabase restored `ACTIVE_HEALTHY`; read-only checks confirmed 15,334 sensor events, 11 shipments, 5 users, and RLS enabled. Existing production admin/user login, shipment detail/live reads and the portal login page returned HTTP 200; both roles received 30 existing ledger records. No database backup was imported, no new project/schema/telemetry was created, and no API/frontend deployment or credential change was required.

A desktop-thread automation, `safetrack-database-availability`, now checks daily at 10:00 AM Asia/Calcutta, issues small read-only database checks and may resume this same Free project if paused. It reports failures/recoveries and does not enable billing or seed missing tables. **This is a best-effort desktop fallback, not an independent cloud scheduler: the computer/app must be available.** It does not guarantee continuous availability or prevent every Free-tier pause. [Supabase's pausing policy](https://supabase.com/docs/guides/platform/free-project-pausing) recommends a paid plan to eliminate automatic inactivity pausing; no upgrade was authorized or performed. Desktop scheduling limitations are documented in [Scheduled tasks](https://learn.chatgpt.com/docs/automations?surface=app).

The 14 October buffering/evidence/assignment API is on a **protected staged deployment**, not the primary alias. Existing admin/user login, assigned shipment detail/live and evidence reads passed; the real shipment returned 30 history records. Additive columns/indexes are present in Supabase, 15,334 events remain, and RLS is retained. Later local report changes were not in that staged deployment. Gateway/frontend updates and explicit public-key enrollment still require controlled rollout. Existing unbound clients remain compatible; do not claim cloud signature enforcement until enrollment is complete. Firmware flashing and physical acceptance are deferred because the ESP32 is unavailable. Do not automatically replay archived outbox history.

### 21 October 2026 — Cloud database availability check

The designated scheduler is now `inamansingh2401/tamperproject`, replacing `abhishekkr10/Tamper_Project` at the operator's request. `.github/workflows/database-availability.yml` runs every eight hours (05:47, 13:47 and 21:47 Asia/Calcutta), with manual dispatch available. A repository guard prevents copies/forks from running the database job. It connects to the existing Supabase session pooler using full TLS certificate/hostname verification and a pinned provider CA. The encrypted Actions secret `SAFETRACK_KEEPALIVE_DATABASE_URL` contains only the dedicated `safetrack_keepalive` account, not the application/admin credential. This account has no role memberships, elevated privileges or record access to the seven existing application tables. Each run issues a tiny read-only connection query; no synthetic events, telemetry, schema changes or application deployments are involved.

This cloud job does not depend on the laptop. The existing desktop automation remains a recovery fallback. Each cloud job is limited to two minutes and three bounded connection attempts. The designated repository is public, so standard hosted Linux runners are free, but GitHub can disable scheduled workflows after 60 days without repository activity. Re-enable the workflow through Actions when needed; do not manufacture commits to bypass the limit. Billing/plan upgrades are not required or enabled. Delayed/disabled schedules, certificate changes, provider policies and outages can still interrupt checks or cause pausing: this is best effort, not an always-on guarantee. Review [current workflow runs](https://github.com/inamansingh2401/tamperproject/actions/workflows/database-availability.yml) for failures; automatic database restoration is not part of this workflow.

Before relocation, the first cloud verification run in the original private repository succeeded in nine seconds, including the restricted read-only database query. Follow-up reads confirmed the existing 5 users, 11 shipments and 15,334 events remained accessible. Relocation requires a successful manual run in the designated repository before disabling the old workflow, so there is no unverified handoff. The current source, tests and documentation are being published to the designated repository; secrets, backups, databases, outboxes and runtime files stay local. The local `origin` remains `inamansingh2401/tamperproject` on branch `main`.

### Private backup and restore drill

`python operations/backup_database.py --env-file .codex-tools/recovery/database-env.local.json --restore-check` exports `public` using native PostgreSQL tools into ignored `.codex-tools/backups` and restores only into its own fresh authenticated loopback cluster. The 14 October drill passed: 5 users, 10 devices, 11 shipments, 15,334 events and 7 vehicles were restored. It never targets production for restoration. Backups contain account/device secrets; keep them private and arrange independent encrypted/offsite retention. Scheduling, monitoring and full service recovery are not yet automated.

`python operations/run_postgres_tests.py` runs regressions in a separate fresh local PostgreSQL cluster. CI uses a fresh service database; tests reject non-empty/non-loopback targets. `operations/verify_cloud.py` reads the existing cloud installation using private local credentials and never posts telemetry. Its `--vercel-curl` option uses the existing account's temporary deployment protection access rather than disabling protection.

1. Build the frontend; run `python -m unittest discover -s tests -p 'test_*.py'`, `node tests/test_evidence.cjs`, `node tests/test_ui_state.cjs`, and `node tests/test_reports.cjs`. Prepared GitHub CI runs isolated SQLite/PostgreSQL and firmware compilation; it has not run remotely yet. Action setup follows [GitHub's PostgreSQL service guidance](https://docs.github.com/en/actions/tutorials/use-containerized-services/create-postgresql-service-containers) and the [Arduino CLI action](https://github.com/arduino/setup-arduino-cli).
2. Verify real admin/user login, role routing, assigned shipment access and logout.
3. Verify Vehicles navigation, fleet search/filter, vehicle details and return navigation.
4. Verify shipment readings, parcel tilt, reset camera, animation playback and mobile layout.
5. Check gateway status, record freshness and delivery acknowledgements separately from webpage availability.

Never publish `.env`, local configuration, passwords, private keys, databases, runtime logs or unpublished presentation files. Ignoring a file does not remove it from prior Git history; rotate credentials if any have previously been exposed.
