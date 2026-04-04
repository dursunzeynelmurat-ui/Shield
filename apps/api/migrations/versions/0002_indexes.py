"""add fk indexes and alert dedup constraint

Revision ID: 0002
Revises: 0001
Create Date: 2026-04-04

"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0002"
down_revision: Union[str, None] = "0001"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # FK indexes
    op.create_index("ix_uploads_user_id", "uploads", ["user_id"])
    op.create_index("ix_orders_user_id", "orders", ["user_id"])
    op.create_index("ix_orders_upload_id", "orders", ["upload_id"])
    op.create_index("ix_product_matches_order_id", "product_matches", ["order_id"])
    op.create_index("ix_price_checks_product_match_id", "price_checks", ["product_match_id"])
    op.create_index("ix_alerts_order_id", "alerts", ["order_id"])
    op.create_index("ix_alerts_price_check_id", "alerts", ["price_check_id"])
    op.create_index("ix_action_recommendations_order_id", "action_recommendations", ["order_id"])
    op.create_index("ix_action_recommendations_alert_id", "action_recommendations", ["alert_id"])
    op.create_index("ix_merchant_policies_merchant_id", "merchant_policies", ["merchant_id"])

    # Unique constraint: one alert per (price_check_id, alert_type) to prevent duplicates
    op.create_unique_constraint(
        "uq_alerts_price_check_type",
        "alerts",
        ["price_check_id", "alert_type"],
    )


def downgrade() -> None:
    op.drop_constraint("uq_alerts_price_check_type", "alerts", type_="unique")
    op.drop_index("ix_merchant_policies_merchant_id", "merchant_policies")
    op.drop_index("ix_action_recommendations_alert_id", "action_recommendations")
    op.drop_index("ix_action_recommendations_order_id", "action_recommendations")
    op.drop_index("ix_alerts_price_check_id", "alerts")
    op.drop_index("ix_alerts_order_id", "alerts")
    op.drop_index("ix_price_checks_product_match_id", "price_checks")
    op.drop_index("ix_product_matches_order_id", "product_matches")
    op.drop_index("ix_orders_upload_id", "orders")
    op.drop_index("ix_orders_user_id", "orders")
    op.drop_index("ix_uploads_user_id", "uploads")
