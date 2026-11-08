"""Index the measured evidence cursor scan by shipment and insertion ID."""
from alembic import op

revision = '0002_evidence_cursor_index'
down_revision = '0001_existing_schema'
branch_labels = None
depends_on = None


def upgrade():
    op.create_index('ix_events_shipment_id', 'sensor_events', ['shipment_id', 'id'])


def downgrade():
    op.drop_index('ix_events_shipment_id', table_name='sensor_events')
