# Ordered rollout and rollback

These are operator instructions, not actions executed by this change. No hosted database operations or deployments were performed. Keep `REPORT_CACHE_BACKEND=off`. Preserve existing account/password settings and `JWT_SECRET`; this rollout does not require rotating login credentials. Never use demo-reset or recreate the users table on an existing installation.

## Before any push or deployment

Review all pending commits, scan for secrets and large/generated files, and inspect automatic deployments. A connected Git deployment can publish code before its schema/configuration is ready. Disable or pause automatic Git deployments first; do not assume a normal push is deployment-free. Follow the detailed [security operator guide](security/rollout.md) for private connection, ACL backup and policy checks.

## Exact order

1. **Back up and retain queues.** Record the running release and `python -m alembic current`. Pause public ingestion while devices/gateways retain queued evidence. Using a privately loaded owner connection, run `python operations/backup_database.py --output-dir .codex-tools/backups --restore-check`. Require successful archive/restore checks. Also save the schema/ACL/policy backup described in the security guide: the data helper deliberately excludes ACLs. Protect all backups; never commit them.
2. **Migrate before starting the new application.** For an empty database, `python -m alembic upgrade head` applies the existing-schema snapshot, concurrent evidence index, cache revision table, replay state and browser-role isolation in order. For a versioned existing database, the same command applies only missing revisions. The migration chain is `0001_existing_schema` → `0002_evidence_cursor_index` → `0003_report_cache_revision` → `0004_device_replay` → `0005_browser_role_isolation`. Use owner credentials, a direct/session connection, certificate verification and the short lock timeout described in the security guide. Run `python -m alembic check`. Do not blindly stamp an unversioned or auto-created schema; compare it and follow the reviewed adoption procedure in [the migration guide](SUPABASE_ROLLOUT.md). Metadata/RLS changes take locks; the evidence index uses concurrent creation.
3. **Configure gateway environment credentials.** Move the existing credential value into `SAFETRACK_DEVICE_KEY_GATEWAY`, or a dedicated `SAFETRACK_DEVICE_KEY_...` variable referenced by the non-secret JSON field `device_key_env`. Remove the old JSON `device_key` field after provisioning the environment. Moving the value does not rotate it. Do not change account passwords or the JWT secret. Keep cache reads off on every API worker.
4. **Prepare and perform explicit device enrollment.** Start the reviewed API privately/staged after migrations, keeping the public rollout paused; the new enrollment routes cannot run on the old API. Confirm public-key fingerprints independently. New registration uses strict replay policy; existing devices retain compatibility until their firmware sends the signed key epoch, persistent boot/sequence metadata and usable timestamp. Use the security guide's registration/rotation/revocation routes. Rotation requires drained queues and deliberately provisioned replacement device credentials; do not rotate working devices automatically. Assignment-only public-key binding does not itself activate strict replay protection.
5. **Deploy the reviewed application deliberately.** Only after schema, environment and compatible device enrollment are ready, publish the API/gateway release. No dashboard JS changes are required by these security controls. Keep legacy firmware in compatibility mode until updated. Firmware per-item batch ACKs, authenticated custody ACKs and physical counter/power-loss acceptance remain pending.
6. **Verify before resuming normal traffic.** Check existing account login, roles/assignments, ordinary reads, one accepted event, an identical retry, revoked-device rejection, chain verification and browser-role SQL isolation. Confirm queues drain without deleting unacknowledged items. These hosted checks must be performed by the operator: only local behavior was verified here.

## Rollback

Pause ingestion and retain all queues first. Prefer fixing forward with additive schema and restrictive browser policies intact. Revert application code through a new reviewed Git commit; do not force-push or rewrite shared history. The old gateway may need its original private configuration restored, but never publish credentials.

The security guide documents the exact schema rollback command:

```powershell
python -m alembic downgrade 0003_report_cache_revision
```

This discards replay/credential-epoch state and leaves RLS enabled/grants revoked. It cannot reconstruct old ACLs; restore reviewed ACL/policy statements from the private backup if necessary. Do not run an old backend for new digest-only devices: it does not understand those credentials. Do not resume strict devices after discarding replay state without deliberate reconciliation/re-enrollment. Never downgrade to `base` on a real database or restore the users table merely to roll back code. A full restore can lose newer events; recover into a separate database and reconcile accepted IDs first.

Current limits and measured evidence: [README](../README.md), [security](SECURITY.md), [architecture](ARCHITECTURE.md), [benchmarks](benchmarks/README.md).
