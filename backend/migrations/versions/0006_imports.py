"""Import jobs, rows and deduplication keys.

Revision ID: 0006_imports
Revises: 0005_investments
"""
from alembic import op
import sqlalchemy as sa

revision = "0006_imports"
down_revision = "0005_investments"
branch_labels = None
depends_on = None


def timestamps() -> list[sa.Column]:
    return [
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
    ]


def upgrade() -> None:
    op.create_table(
        "import_jobs",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("user_id", sa.Integer(), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("filename", sa.String(255), nullable=False),
        sa.Column("file_type", sa.String(8), nullable=False),
        sa.Column("sheet_names", sa.JSON(), nullable=False),
        sa.Column("selected_sheet", sa.String(120)),
        sa.Column("headers", sa.JSON(), nullable=False),
        sa.Column("mapping", sa.JSON(), nullable=False),
        sa.Column("default_account_id", sa.Integer(), sa.ForeignKey("accounts.id", ondelete="RESTRICT")),
        sa.Column("positive_is_income", sa.Boolean(), nullable=False),
        sa.Column("status", sa.String(16), nullable=False),
        sa.Column("total_rows", sa.Integer(), nullable=False),
        sa.Column("imported_rows", sa.Integer(), nullable=False),
        sa.Column("skipped_rows", sa.Integer(), nullable=False),
        sa.Column("error_rows", sa.Integer(), nullable=False),
        *timestamps(),
    )
    op.create_index("ix_import_jobs_user", "import_jobs", ["user_id"])
    op.create_table(
        "import_rows",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("user_id", sa.Integer(), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("job_id", sa.Integer(), sa.ForeignKey("import_jobs.id", ondelete="CASCADE"), nullable=False),
        sa.Column("sheet_name", sa.String(120), nullable=False),
        sa.Column("row_number", sa.Integer(), nullable=False),
        sa.Column("raw", sa.JSON(), nullable=False),
        sa.Column("parsed", sa.JSON()),
        sa.Column("error", sa.Text()),
        sa.Column("dedup_key", sa.String(64)),
        sa.Column("status", sa.String(16), nullable=False),
        sa.Column("transaction_id", sa.Integer(), sa.ForeignKey("transactions.id", ondelete="RESTRICT")),
        *timestamps(),
    )
    op.create_index("ix_import_rows_job_sheet", "import_rows", ["job_id", "sheet_name"])
    op.create_table(
        "import_keys",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("user_id", sa.Integer(), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("key", sa.String(64), nullable=False),
        sa.Column("transaction_id", sa.Integer(), sa.ForeignKey("transactions.id", ondelete="RESTRICT"), nullable=False),
        sa.UniqueConstraint("user_id", "key", name="uq_import_key_user_key"),
        *timestamps(),
    )


def downgrade() -> None:
    for table in ("import_keys", "import_rows", "import_jobs"):
        op.drop_table(table)
