"""Remove picture_url col

Revision ID: 291c959204d4
Revises: 9ddd5abe859d
Create Date: 2024-09-06 15:08:21.077030

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '291c959204d4'
down_revision: Union[str, None] = '9ddd5abe859d'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # ### commands auto generated by Alembic - please adjust! ###
    op.drop_column('users', 'picture')
    # ### end Alembic commands ###


def downgrade() -> None:
    # ### commands auto generated by Alembic - please adjust! ###
    op.add_column('users', sa.Column('picture', sa.VARCHAR(length=200), autoincrement=False, nullable=True))
    # ### end Alembic commands ###
