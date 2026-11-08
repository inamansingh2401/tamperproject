"""Persistent replay identity and device credential epochs."""
from alembic import op
import sqlalchemy as sa

revision = '0004_device_replay'
down_revision = '0003_report_cache_revision'
branch_labels = depends_on = None

def upgrade():
    # Short metadata additions only; no table-wide credential backfill in this DDL.
    for column in [sa.Column('key_hash',sa.String(64)),
                   sa.Column('key_version',sa.Integer(),nullable=False,server_default=sa.text('1')),
                   sa.Column('replay_policy',sa.String(16),nullable=False,server_default=sa.text("'legacy'")),
                   sa.Column('replay_boot',sa.BigInteger(),nullable=False,server_default=sa.text('0'))]:
        op.add_column('devices', column)
    op.create_table('device_replay_nonces',
        sa.Column('device_id',sa.String(64),primary_key=True),
        sa.Column('key_version',sa.Integer(),primary_key=True),
        sa.Column('boot_counter',sa.BigInteger(),primary_key=True),
        sa.Column('sequence',sa.BigInteger(),primary_key=True),
        sa.Column('event_id',sa.String(128),nullable=False))

def downgrade():
    op.drop_table('device_replay_nonces')
    for column in ['replay_boot','replay_policy','key_version','key_hash']:
        op.drop_column('devices',column)
