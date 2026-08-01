"""Initial pre-release hosted-service schema.

The service has not been deployed. This first revision therefore freezes the complete v1 identity,
campaign, robustness-group, reserved-slot, and immutable-run schema rather than preserving the
superseded free-text prototype layout.

Revision ID: 20260718_0001
Revises:
"""

from alembic import op
from gloss_service import models  # noqa: F401
from gloss_service.database import Base

revision = "20260718_0001"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    Base.metadata.create_all(bind=op.get_bind())


def downgrade() -> None:
    Base.metadata.drop_all(bind=op.get_bind())
