# migrations/002_add_versioning.py
from alembic import op
import sqlalchemy as sa

def upgrade():
    op.add_column('submissions', sa.Column('version', sa.Integer(), nullable=False, server_default='1'))
    op.add_column('submissions', sa.Column('is_latest', sa.Boolean(), nullable=True, server_default='true'))
    op.create_index('idx_submissions_version', 'submissions', ['version'])
    op.create_index('idx_submissions_latest', 'submissions', ['is_latest'])

def downgrade():
    op.drop_index('idx_submissions_latest', table_name='submissions')
    op.drop_index('idx_submissions_version', table_name='submissions')
    op.drop_column('submissions', 'is_latest')
    op.drop_column('submissions', 'version')