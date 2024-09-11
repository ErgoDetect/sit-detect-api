"""Change User_ID Type

Revision ID: d3d96e47f872
Revises: 291c959204d4
Create Date: 2024-09-10 15:12:20.700057

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'd3d96e47f872'
down_revision: Union[str, None] = '291c959204d4'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Drop foreign key constraint
    op.drop_constraint('oauth_tokens_user_id_fkey', 'oauth_tokens', type_='foreignkey')
    
    # Alter columns
    op.alter_column('oauth_tokens', 'user_id',
               existing_type=sa.INTEGER(),
               type_=sa.String(length=100),
               existing_nullable=False)
    op.drop_index('ix_oauth_tokens_user_id', table_name='oauth_tokens')

    op.alter_column('users', 'user_id',
               existing_type=sa.INTEGER(),
               type_=sa.String(length=100),
               existing_nullable=False,
               existing_server_default=sa.text("nextval('users_user_id_seq'::regclass)"))
    op.drop_index('ix_users_user_id', table_name='users')

    # Recreate foreign key constraint
    op.create_foreign_key('oauth_tokens_user_id_fkey', 'oauth_tokens', 'users', ['user_id'], ['user_id'])


def downgrade() -> None:
    # Drop the new foreign key constraint
    op.drop_constraint('oauth_tokens_user_id_fkey', 'oauth_tokens', type_='foreignkey')
    
    # Revert columns
    op.create_index('ix_users_user_id', 'users', ['user_id'], unique=False)
    op.alter_column('users', 'user_id',
               existing_type=sa.String(length=100),
               type_=sa.INTEGER(),
               existing_nullable=False,
               existing_server_default=sa.text("nextval('users_user_id_seq'::regclass)"))
    
    op.create_index('ix_oauth_tokens_user_id', 'oauth_tokens', ['user_id'], unique=False)
    op.alter_column('oauth_tokens', 'user_id',
               existing_type=sa.String(length=100),
               type_=sa.INTEGER(),
               existing_nullable=False)
    
    # Recreate the foreign key constraint in the downgrade
    op.create_foreign_key('oauth_tokens_user_id_fkey', 'oauth_tokens', 'users', ['user_id'], ['user_id'])
