"""Add google user column

Revision ID: 59b74feb2ea8
Revises: 003ca7792d9c
Create Date: 2024-10-15 17:42:02.167972

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '59b74feb2ea8'
down_revision: Union[str, None] = '003ca7792d9c'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # ### commands auto generated by Alembic - please adjust! ###
    op.add_column('google_users', sa.Column('verified', sa.Boolean(), nullable=True))
    # ### end Alembic commands ###


def downgrade() -> None:
    # ### commands auto generated by Alembic - please adjust! ###
    op.drop_column('google_users', 'verified')
    # ### end Alembic commands ###