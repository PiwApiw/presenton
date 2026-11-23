"""add typography columns

Revision ID: a1c4e7b9d2f5
Revises: 026c0ba8b35c
Create Date: 2026-10-30 00:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "a1c4e7b9d2f5"
down_revision: Union[str, None] = "026c0ba8b35c"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def _has_table(table_name: str) -> bool:
    return table_name in sa.inspect(op.get_bind()).get_table_names()


def _has_column(table_name: str, column_name: str) -> bool:
    columns = sa.inspect(op.get_bind()).get_columns(table_name)
    return column_name in {column["name"] for column in columns}


def upgrade() -> None:
    if _has_table("presentations") and not _has_column("presentations", "typography"):
        op.add_column(
            "presentations", sa.Column("typography", sa.JSON(), nullable=True)
        )
    if _has_table("slides") and not _has_column("slides", "typography"):
        op.add_column("slides", sa.Column("typography", sa.JSON(), nullable=True))


def downgrade() -> None:
    if _has_table("slides") and _has_column("slides", "typography"):
        op.drop_column("slides", "typography")
    if _has_table("presentations") and _has_column("presentations", "typography"):
        op.drop_column("presentations", "typography")
