# Phase 4 operator guide

Prepared and verified locally only. No hosted operations were performed. Keep `REPORT_CACHE_BACKEND=off` in every deployed environment. The migrations are additive, but `ALTER TABLE`/RLS changes take metadata locks: use a maintenance window and a short lock timeout. They are not advertised as non-blocking. The existing Phase 1 index migration remains concurrent.

## 1. Prepare and back up

1. Review this release and `docs/SECURITY.md`. Install backend and gateway requirements in their respective environments. Do not deploy/start the new application before migrating: legacy startup also creates tables, which can conflict with Alembic's creation of the replay table.
2. Pause ingestion and sampling, or make devices/gateways retain their queues during maintenance. Keep operator access available. Record the deployed commit and `python -m alembic current`. This guide assumes the approved Phase 3 revision `0003_report_cache_revision`; follow [the earlier adoption guide](../SUPABASE_ROLLOUT.md) for unversioned databases rather than guessing/stamping.
3. Load the owner connection privately into `DATABASE_URL`, using a direct or session-pooler connection with certificate verification. Never place credentials in a command argument, checked-in file or output log. Follow the existing connection setup in the linked guide.
4. Run `python operations/backup_database.py --output-dir .codex-tools/backups --restore-check`. Require its archive-readability and local restore checks to pass. This existing data backup deliberately excludes ACLs. **Also save schema/ACL state** before changing grants, as shown below; retain both privately.

```powershell
$pgBin = 'C:/Program Files/PostgreSQL/18/bin'
# Privately populate PGHOST/PGPORT/PGDATABASE/PGUSER/PGPASSWORD from the same
# owner connection; use PGSSLMODE=verify-full and PGSSLROOTCERT as appropriate.
& "$pgBin/pg_dump.exe" --schema=public --schema-only --file=.codex-tools/backups/pre-phase4-schema-acl.sql
if ($LASTEXITCODE -ne 0) { throw 'Schema/ACL backup failed' }
$env:PGOPTIONS = '-c lock_timeout=5s -c statement_timeout=5min'
python -m alembic upgrade head
if ($LASTEXITCODE -ne 0) { throw 'Migration failed; keep ingestion paused' }
python -m alembic check
```

The schema dump contains sensitive definitions and possibly privileged functions. Protect it like the data backup. Do not run an entire schema dump over an existing live schema to restore grants; extract/review the original ACL/policy statements first.

## 2. Verify access before resuming

Revision `0005_browser_role_isolation` applies [the exact SQL](../../migrations/sql/0005_browser_role_isolation.sql). It enables RLS on all ten current application/migration tables and revokes browser grants; restrictive deny policies defend against permissive existing policies. It does not change Supabase Auth/Storage schemas, views or security-definer functions. Inspect these separately for indirect access. New application tables must be added to this policy list. Do not grant `anon` or `authenticated` membership in the backend owner/BYPASSRLS role.

Backend database connections must use the trusted table owner or a reviewed backend-only BYPASSRLS role. Never put that credential or a Supabase service key in frontend JavaScript. Existing dashboards call FastAPI; they require no JS changes for these controls.

Run this read-only verification query as owner. Every row must have `rls_enabled=true` and `browser_has_dml=false`, plus the two restrictive policies. Missing browser roles on a plain PostgreSQL installation must be provisioned and the SQL rerun before claiming browser isolation.

```sql
SELECT c.relname, r.rolname, c.relrowsecurity AS rls_enabled,
       (has_table_privilege(r.rolname,c.oid,'SELECT') OR
        has_table_privilege(r.rolname,c.oid,'INSERT') OR
        has_table_privilege(r.rolname,c.oid,'UPDATE') OR
        has_table_privilege(r.rolname,c.oid,'DELETE')) AS browser_has_dml
FROM pg_class c JOIN pg_namespace n ON n.oid=c.relnamespace
CROSS JOIN pg_roles r
WHERE n.nspname='public' AND c.relkind='r'
  AND c.relname IN ('users','devices','shipments','vehicles','sensor_events',
      'shipment_alerts','system_settings','cache_revisions','device_replay_nonces','alembic_version')
  AND r.rolname IN ('anon','authenticated')
ORDER BY c.relname,r.rolname;
SELECT tablename,policyname,permissive,roles,qual,with_check FROM pg_policies
WHERE schemaname='public' AND policyname LIKE 'safetrack_browser_deny_%';
```

Local proof: `tests/test_rls.py` actually assumes both roles and verifies SELECT/INSERT/UPDATE/DELETE fail with SQLSTATE 42501 on every application table; it then restores grants plus permissive policies and verifies restrictive RLS still prevents access. `tests/test_migrations.py` verifies fresh PostgreSQL upgrade, Alembic metadata consistency and downgrade in a separate disposable database. These are **not** hosted Supabase tests. Before resuming production traffic, an operator must repeat browser-role access checks and backend read/write smoke tests on that deployment.

References checked for this guide: [Supabase RLS](https://supabase.com/docs/guides/database/postgres/row-level-security), [PostgreSQL restrictive policies](https://www.postgresql.org/docs/current/sql-createpolicy.html), [Supabase changelog](https://supabase.com/changelog). CLI-v3/Flutter-v3 changes do not affect these native PostgreSQL/Alembic commands.

## 3. Enroll, revoke and rotate

1. Generate a unique 32–256 character high-entropy credential privately for each device. Put it in the gateway and API environments under a dedicated name such as `SAFETRACK_DEVICE_KEY_TRACKER01`. Set the gateway JSON's non-secret `device_key_env` to that name (default `SAFETRACK_DEVICE_KEY_GATEWAY`). The gateway no longer uses a `device_key` stored in JSON: remove that old field from private configs after provisioning the environment. Local-only mode does not need a cloud credential. Do not submit the credential in enrollment JSON. The name cannot reference `JWT_SECRET` or arbitrary environment variables.
2. Independently verify the device's uncompressed P-256 public point. With an admin JWT, POST `/api/devices` with `device_id`, `shipment_code`, `public_key`, `api_key_env`. The server stores a SHA-256 credential digest, an enrolled public point and epoch 1; it returns no secret. New registrations use `counter_v1` replay policy. Device-list responses expose policy/epoch so operators can distinguish legacy devices.
3. Strict signed records require `event_id`, `device_id` matching enrollment exactly, `key_version`, `boot_counter`, `sequence`, `captured_at_ms` and sensor fields. Use the same raw signed bytes and ID on every retry. Current firmware still requires the changes listed in SECURITY.md before strict enrollment; do not silently switch existing devices.
4. POST `/api/devices/{device_id}/revoke` to reject all subsequent uploads, including known retries. A revocation racing an accepted upload is serialized by the device row lock; already committed history remains valid.
5. To rotate or activate strict protection for an existing device, pause sampling and **drain old queues first**. Provision a different credential and the reviewed new public point. POST `/api/devices/{device_id}/rotate` with `shipment_code`, `public_key`, `api_key_env`, `confirm_drained:true`. The epoch increases, replay boot tracking resets and status becomes active. Update firmware/gateway credential, signer and signed epoch together. Old credential/signature uploads fail; historical signatures retain their original public-key snapshot. Admin authorization alone does not independently validate a replacement key's provenance.

Existing bootstrap/assignment flows remain legacy for compatibility. Legacy shared credentials and unsigned records do not gain strict replay protection. Existing plaintext legacy device keys remain until rotation; new/rotated credentials are digest-only. Do not claim every device is protected before completing enrollment.

## 4. Verification and rollback

Admin GET `/api/shipments/{code}/evidence/verify` verifies stored rows in insertion-ID order, returning the first broken ID/index. Optional `expected_count` and `expected_tail_hash` must come from an independently retained checkpoint. Without these, suffix/all-history deletion can appear as a valid shorter chain. This endpoint does not establish physical truth or immutable retention.

If rollout fails, keep ingestion paused and retain queues/backups. Prefer fixing forward while leaving additive columns/ledger and deny policies intact. To remove Phase 4 schema after reviewing the data-loss implications:

```powershell
python -m alembic downgrade 0003_report_cache_revision
```

This drops replay state/credential-epoch columns and removes only the new deny policies. It deliberately **leaves RLS enabled and grants revoked**: downgrade cannot reconstruct prior ACLs. Restore only reviewed grants/policies from the pre-rollout schema/ACL backup if required. Do not resume an old backend for newly registered digest-only devices: the old version does not understand their credentials. Restoring a complete pre-rollout backup loses newer events unless separately recovered; perform recovery in a separate database and reconcile queued/accepted IDs. Resetting counters or discarding the ledger defeats replay guarantees and requires deliberate re-enrollment. Never downgrade to Alembic `base` on a real database.
