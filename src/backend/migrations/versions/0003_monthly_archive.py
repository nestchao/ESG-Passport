"""Archive evidence without deleting immutable originals; attribute events to months."""
from alembic import op
import sqlalchemy as sa

revision = '0003_monthly_archive'
down_revision = '0002_questionnaire_updated_at'
branch_labels = None
depends_on = None


def upgrade():
    op.add_column('documents', sa.Column('archived_at', sa.DateTime(timezone=True), nullable=True))
    op.add_column('documents', sa.Column('archived_by', sa.String(255), nullable=True))
    op.add_column('activity_events', sa.Column('period', sa.String(64), nullable=True))
    op.create_index('ix_activity_events_period', 'activity_events', ['period'])
    # Legacy events without a record target remain workspace-level (NULL).
    op.execute(sa.text('UPDATE activity_events SET period = (SELECT documents.period FROM documents WHERE documents.id = activity_events.target AND documents.company_id = activity_events.company_id) WHERE EXISTS (SELECT 1 FROM documents WHERE documents.id = activity_events.target AND documents.company_id = activity_events.company_id)'))
    op.execute(sa.text('UPDATE activity_events SET period = (SELECT questionnaires.period FROM questionnaires WHERE questionnaires.id = activity_events.target AND questionnaires.company_id = activity_events.company_id) WHERE period IS NULL AND EXISTS (SELECT 1 FROM questionnaires WHERE questionnaires.id = activity_events.target AND questionnaires.company_id = activity_events.company_id)'))


def downgrade():
    op.drop_index('ix_activity_events_period', table_name='activity_events')
    op.drop_column('activity_events', 'period')
    op.drop_column('documents', 'archived_by')
    op.drop_column('documents', 'archived_at')
