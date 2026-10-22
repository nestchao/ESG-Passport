"""Track questionnaire edits without rewriting creation history.

Revision ID: 0002_questionnaire_updated_at
"""
from alembic import op
import sqlalchemy as sa

revision = '0002_questionnaire_updated_at'
down_revision = '0001_esg_foundation'
branch_labels = None
depends_on = None


def upgrade():
    op.add_column('questionnaires', sa.Column('updated_at', sa.DateTime(timezone=True), nullable=True))
    op.execute(sa.text('UPDATE questionnaires SET updated_at = created_at'))
    with op.batch_alter_table('questionnaires') as batch:
        batch.alter_column('updated_at', existing_type=sa.DateTime(timezone=True), nullable=False)


def downgrade():
    op.drop_column('questionnaires', 'updated_at')
