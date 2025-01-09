"""Added number_of_pages column to books table

Revision ID: e3c712417d38
Revises: 6b05c597006a
Create Date: 2025-01-02 15:46:52.924841

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'e3c712417d38'
down_revision = '6b05c597006a'
branch_labels = None
depends_on = None


def upgrade():
    # ### commands auto generated by Alembic - please adjust! ###
    with op.batch_alter_table('books', schema=None) as batch_op:
        batch_op.add_column(sa.Column('number_of_pages', sa.Integer(), nullable=True))

    # ### end Alembic commands ###


def downgrade():
    # ### commands auto generated by Alembic - please adjust! ###
    with op.batch_alter_table('books', schema=None) as batch_op:
        batch_op.drop_column('number_of_pages')

    # ### end Alembic commands ###
