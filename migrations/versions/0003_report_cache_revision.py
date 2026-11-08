"""Transactionally fence report caches across application workers."""
from alembic import op
import sqlalchemy as sa

revision = '0003_report_cache_revision'
down_revision = '0002_evidence_cursor_index'
branch_labels = None
depends_on = None


def upgrade():
    op.create_table('cache_revisions',
        sa.Column('namespace',sa.String(32),primary_key=True),
        sa.Column('generation',sa.BigInteger(),nullable=False,server_default=sa.text('0')))
    if op.get_context().dialect.name == 'postgresql':
        op.execute('ALTER TABLE cache_revisions ENABLE ROW LEVEL SECURITY')
        op.execute("""DO $$ BEGIN
            IF EXISTS (SELECT 1 FROM pg_roles WHERE rolname='anon') THEN
                REVOKE ALL ON cache_revisions FROM anon;
            END IF;
            IF EXISTS (SELECT 1 FROM pg_roles WHERE rolname='authenticated') THEN
                REVOKE ALL ON cache_revisions FROM authenticated;
            END IF;
        END $$""")


def downgrade():
    op.drop_table('cache_revisions')
