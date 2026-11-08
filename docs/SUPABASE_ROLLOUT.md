# Supabase rollout and rollback

These are operator instructions. No hosted database commands were run while preparing or testing this guide. The concurrent-index migration was tested only on disposable local PostgreSQL.

## 1. Prepare the release and a private connection

1. Use the reviewed commit containing the concurrent version of revision 0002. Install the backend requirements in your migration environment.
2. In the Supabase project, open Connect and obtain the direct database connection string for schema migrations. If your network cannot reach the direct IPv6 address, use the session pooler. Keep transaction pooling out of this migration path. Use a database owner or a role that owns sensor_events and can create indexes.
3. Load the URI privately into DATABASE_URL. Use the postgresql:// URI form for compatibility with psql and the Python tools. Set SSL verification using the project's certificate instructions. Keep credentials out of source files and shell history.

```powershell
python -m pip install -r Tamper_admin/backend/requirements.txt
$migrationSecret = Read-Host 'Database URI from Supabase Connect' -AsSecureString
$env:DATABASE_URL = [Net.NetworkCredential]::new('', $migrationSecret).Password
$env:PGSSLMODE = 'verify-full'
$env:PGSSLROOTCERT = Read-Host 'Absolute path to the downloaded project CA certificate'
$env:PGOPTIONS = '-c lock_timeout=5s -c statement_timeout=15min'
$pgBin = 'C:/Program Files/PostgreSQL/18/bin'
```

Append sslmode=verify-full and the appropriate sslrootcert to the connection URI as described by Supabase, so SQLAlchemy/Alembic also verifies the connection. PGSSLMODE/PGSSLROOTCERT additionally configure the native PostgreSQL clients. Never paste the URI into a committed configuration.

Connection selection is based on the [Supabase connection guide](https://supabase.com/docs/guides/database/connecting-to-postgres). The public changelog was checked during preparation. This guide uses PostgreSQL clients and Alembic, so it does not depend on Supabase CLI v2/v3 flag changes.

## 2. Back up and verify before any migration

Create a private custom-format dump of the application's public schema. The helper stores its output under ignored .codex-tools and can restore the archive into its own authenticated local cluster. It never restores over the hosted database.

```powershell
python operations/backup_database.py --output-dir .codex-tools/backups --restore-check --pg-bin "$pgBin"
```

Require archive_readable=true and restore=PASS. Retain the reported dump path privately. If restoration fails because policies depend on roles or extensions absent locally, resolve the restore prerequisites before proceeding. The public-schema archive covers the SafeTrack application tables and policies. Supabase Auth and Storage data outside public need the provider's separate recovery procedure. Record available provider backups/PITR and their retention for your project's actual plan. [Supabase backup documentation](https://supabase.com/docs/guides/platform/backups).

Record the current application release and Alembic revision.

```powershell
git rev-parse HEAD
python -m alembic current
```

## 3. Inspect the index before choosing the migration path

Run the following query in psql using the privately configured URI, or in the project's SQL editor. The query is read-only.

```sql
SELECT n.nspname AS schema_name, c.relname AS index_name,
       i.indisvalid, i.indisready, pg_get_indexdef(i.indexrelid) AS definition
FROM pg_index i
JOIN pg_class c ON c.oid = i.indexrelid
JOIN pg_namespace n ON n.oid = c.relnamespace
WHERE n.nspname = 'public' AND c.relname = 'ix_events_shipment_id';
```

- With no index and no Alembic version, verify the legacy schema using python operations/check_migration_schema.py --baseline, then run python -m alembic stamp 0001_existing_schema. Review any schema differences before stamping.
- With revision 0001 already recorded and no index, proceed to step 4.
- With no Alembic version but an already valid matching Phase 1 index, verify python operations/check_migration_schema.py --phase1 and then stamp 0002_evidence_cursor_index. If additional Phase 2 tables are present, follow the schema-review path in the Phase 2 guide instead of stamping over unexplained differences.
- With revision 0002 recorded and a valid, ready index on sensor_events(shipment_id, id), the index is already installed.
- With a valid matching index but revision 0001, a previous attempt may have finished DDL before recording its version. Verify the full definition and then stamp 0002_evidence_cursor_index. Do not rebuild that valid index merely to change migration history.
- With an invalid or not-ready index, follow the interrupted-build recovery below before retrying. A wrong definition requires review and must not be treated as the intended index.

## 4. Build the index without the ordinary write-blocking table lock

```powershell
python -m alembic upgrade 0002_evidence_cursor_index
```

On PostgreSQL, revision 0002 uses CREATE INDEX CONCURRENTLY inside Alembic's autocommit_block. SQLite uses its normal index operation. Alembic transactions are scoped per migration. Do not wrap the PostgreSQL concurrent statement in BEGIN/COMMIT or paste it into a multi-statement SQL transaction.

Concurrent creation permits normal INSERT/UPDATE/DELETE activity but can wait for existing transactions and competing schema operations. It is not a guarantee of zero latency impact. The timeout options above bound waiting instead of leaving a stalled migration indefinitely. Run only one index migration on this table at a time. [PostgreSQL concurrent index behavior](https://www.postgresql.org/docs/current/sql-createindex.html), [Alembic autocommit blocks](https://alembic.sqlalchemy.org/en/latest/api/runtime.html#alembic.runtime.migration.MigrationContext.autocommit_block).

During the build, inspect progress separately.

```sql
SELECT pid, phase, blocks_done, blocks_total
FROM pg_stat_progress_create_index
WHERE relid = 'public.sensor_events'::regclass;
```

After completion, repeat step 3's index query and require indisvalid=true, indisready=true and the expected column order. Run python -m alembic current and require revision 0002 at this stage. Check authenticated shipment evidence reads and current gateway delivery from the normal application.

## 5. Recover an interrupted build

Concurrent DDL commits independently of the Alembic version update. A timeout, cancellation or connection loss can leave an invalid index. After confirming the failed build is no longer active, drop only the invalid index as its own autocommit statement.

```sql
DROP INDEX CONCURRENTLY IF EXISTS public.ix_events_shipment_id;
```

Then repeat the index inspection and python -m alembic upgrade 0002_evidence_cursor_index. Do not hide this condition with CREATE INDEX IF NOT EXISTS, which can silently retain an invalid index.

## 6. Roll back the index

If the migration is at revision 0002, use the following command.

```powershell
python -m alembic downgrade 0001_existing_schema
```

On PostgreSQL, its downgrade uses DROP INDEX CONCURRENTLY in autocommit mode. This removes the added index and preserves application rows. Verify the index is absent and revision 0001 is recorded. Restore the previous application release only if its code also needs rollback. A data restore is a separate incident procedure and can discard writes made after the backup.

If a newer revision is installed, roll that revision back according to its own instructions before downgrading 0002. Do not downgrade to base on an existing installation, because revision 0001 owns the application tables.

## 7. Finish the deployment

Deploy the API and the cursor-aware admin api.js together, with the API available first. Existing UI filters and counts require the shared client to retrieve all alert pages. Check admin and assigned-user access after deployment.

Keep alembic_version and any internal cache metadata inaccessible to browser Data API roles. For public.alembic_version, the database owner can enable RLS and revoke anon/authenticated privileges. This does not grant any new access to application tables.

```sql
ALTER TABLE public.alembic_version ENABLE ROW LEVEL SECURITY;
REVOKE ALL ON public.alembic_version FROM anon, authenticated;
```

The Reports SET LOCAL max_parallel_workers_per_gather=0 optimization was tuned on the local Windows/PostgreSQL workload. Its benefit is unverified on hosted Supabase. Measure hosted report plans and latency before making a hosted speedup claim.

## 8. Optional Phase 2 cache deployment

Keep REPORT_CACHE_BACKEND=off while installing the Phase 2 release.

```powershell
python -m alembic upgrade head
python -m alembic check
```

Require revision 0003_report_cache_revision. Before deploying the API, verify that the internal table has RLS enabled and that browser roles lack privileges.

```sql
SELECT relrowsecurity FROM pg_class WHERE oid='public.cache_revisions'::regclass;
SELECT has_table_privilege('anon','public.cache_revisions','SELECT') AS anon_select,
       has_table_privilege('authenticated','public.cache_revisions','SELECT') AS authenticated_select;
```

Expected values are true for relrowsecurity and false for both browser privileges. The migration owner should own the table. A separate application backend role needs reviewed table privileges and an RLS policy allowing that role to read and update the reports revision. Do not solve a backend-role permission error by granting browser-role access.

Deploy the new API to every writer process with caching off. Verify ingestion, alert resolution and GET /api/admin/cache-metrics using an admin session. Then set REPORT_CACHE_BACKEND=memory and REPORT_CACHE_TTL_SECONDS=5 on the API host, redeploy and check that the metrics report enabled=true. Check a new event followed immediately by report, alert and live reads.

For cache rollback, first set REPORT_CACHE_BACKEND=off and restart every worker. To remove the revision table, deploy the Phase 1 API to every writer before running the following command with this release's migration tools.

```powershell
python -m alembic downgrade 0002_evidence_cursor_index
```

This leaves the evidence index installed. If index rollback is also needed, step 6 can then remove it concurrently. See [Phase 2 workload limits and direct-write rules](benchmarks/phase2.md) before enabling caching.
