"""Deny direct browser access to backend-only application tables."""
from pathlib import Path
from alembic import op

revision = '0005_browser_role_isolation'
down_revision = '0004_device_replay'
branch_labels = depends_on = None

def upgrade():
    if op.get_context().dialect.name == 'postgresql':
        sql = (Path(__file__).resolve().parents[1]/'sql/0005_browser_role_isolation.sql').read_text()
        op.execute(sql)

def downgrade():
    # Fail closed: prior grants/policies cannot be inferred. Restore them only
    # from the pre-rollout schema/ACL backup after review.
    if op.get_context().dialect.name == 'postgresql':
        op.execute('''DO $$ DECLARE tab text; BEGIN
        FOREACH tab IN ARRAY ARRAY['users','devices','shipments','vehicles','sensor_events',
          'shipment_alerts','system_settings','cache_revisions','device_replay_nonces','alembic_version'] LOOP
          EXECUTE format('DROP POLICY IF EXISTS safetrack_browser_deny_anon ON public.%I',tab);
          EXECUTE format('DROP POLICY IF EXISTS safetrack_browser_deny_authenticated ON public.%I',tab);
        END LOOP; END $$''')
