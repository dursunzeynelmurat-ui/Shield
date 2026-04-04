"""initial schema

Revision ID: 0001
Revises:
Create Date: 2026-04-04

"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0001"
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "users",
        sa.Column("id", sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column("email", sa.String(255), nullable=False),
        sa.Column("password_hash", sa.String(255), nullable=False),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.text("true")),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_users_email", "users", ["email"], unique=True)

    op.create_table(
        "uploads",
        sa.Column("id", sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column("user_id", sa.BigInteger(), nullable=False),
        sa.Column("file_type", sa.String(50), nullable=False),
        sa.Column("storage_url", sa.String(1000), nullable=False),
        sa.Column("original_filename", sa.String(500)),
        sa.Column("file_size", sa.Integer()),
        sa.Column("status", sa.String(50), nullable=False, server_default="pending"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"]),
        sa.PrimaryKeyConstraint("id"),
    )

    op.create_table(
        "orders",
        sa.Column("id", sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column("user_id", sa.BigInteger(), nullable=False),
        sa.Column("upload_id", sa.BigInteger()),
        sa.Column("merchant", sa.String(100)),
        sa.Column("merchant_order_no", sa.String(200)),
        sa.Column("product_title_raw", sa.Text()),
        sa.Column("normalized_title", sa.Text()),
        sa.Column("brand", sa.String(200)),
        sa.Column("model", sa.String(200)),
        sa.Column("variant", sa.String(200)),
        sa.Column("sku", sa.String(200)),
        sa.Column("seller_name", sa.String(200)),
        sa.Column("purchase_price", sa.Numeric(12, 2)),
        sa.Column("currency", sa.String(10)),
        sa.Column("purchased_at", sa.Date()),
        sa.Column("delivery_date", sa.Date()),
        sa.Column("return_deadline", sa.Date()),
        sa.Column("parse_confidence", sa.Numeric(4, 3)),
        sa.Column("parse_raw", sa.Text()),
        sa.Column("status", sa.String(50), nullable=False, server_default="pending_verification"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"]),
        sa.ForeignKeyConstraint(["upload_id"], ["uploads.id"]),
        sa.PrimaryKeyConstraint("id"),
    )

    op.create_table(
        "product_matches",
        sa.Column("id", sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column("order_id", sa.BigInteger(), nullable=False),
        sa.Column("canonical_title", sa.Text()),
        sa.Column("matched_url", sa.String(2000)),
        sa.Column("merchant", sa.String(100)),
        sa.Column("seller_name", sa.String(200)),
        sa.Column("match_method", sa.String(50)),
        sa.Column("match_confidence", sa.Numeric(4, 3)),
        sa.Column("same_variant_verified", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        sa.Column("same_seller_verified", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.text("true")),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["order_id"], ["orders.id"]),
        sa.PrimaryKeyConstraint("id"),
    )

    op.create_table(
        "price_checks",
        sa.Column("id", sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column("product_match_id", sa.BigInteger(), nullable=False),
        sa.Column("checked_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("listed_price", sa.Numeric(12, 2)),
        sa.Column("shipping_price", sa.Numeric(12, 2)),
        sa.Column("final_price", sa.Numeric(12, 2)),
        sa.Column("currency", sa.String(10)),
        sa.Column("seller_name", sa.String(200)),
        sa.Column("stock_status", sa.String(50)),
        sa.Column("coupon_detected", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        sa.Column("coupon_text", sa.Text()),
        sa.Column("check_method", sa.String(50)),
        sa.Column("evidence_image_url", sa.String(2000)),
        sa.Column("raw_payload", sa.Text()),
        sa.Column("success", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        sa.Column("error_message", sa.Text()),
        sa.ForeignKeyConstraint(["product_match_id"], ["product_matches.id"]),
        sa.PrimaryKeyConstraint("id"),
    )

    op.create_table(
        "alerts",
        sa.Column("id", sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column("order_id", sa.BigInteger(), nullable=False),
        sa.Column("price_check_id", sa.BigInteger()),
        sa.Column("alert_type", sa.String(50), nullable=False),
        sa.Column("amount_saved", sa.Numeric(12, 2)),
        sa.Column("message", sa.Text()),
        sa.Column("status", sa.String(50), nullable=False, server_default="new"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["order_id"], ["orders.id"]),
        sa.ForeignKeyConstraint(["price_check_id"], ["price_checks.id"]),
        sa.PrimaryKeyConstraint("id"),
    )

    op.create_table(
        "action_recommendations",
        sa.Column("id", sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column("order_id", sa.BigInteger(), nullable=False),
        sa.Column("alert_id", sa.BigInteger()),
        sa.Column("action_type", sa.String(50), nullable=False),
        sa.Column("recommended_text", sa.Text()),
        sa.Column("target_url", sa.String(2000)),
        sa.Column("estimated_savings", sa.Numeric(12, 2)),
        sa.Column("confidence", sa.Numeric(4, 3)),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["order_id"], ["orders.id"]),
        sa.ForeignKeyConstraint(["alert_id"], ["alerts.id"]),
        sa.PrimaryKeyConstraint("id"),
    )

    op.create_table(
        "merchants",
        sa.Column("id", sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column("name", sa.String(200), nullable=False),
        sa.Column("domain", sa.String(200), nullable=False),
        sa.Column("supports_scraping", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        sa.Column("supports_playwright", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        sa.Column("notes", sa.Text()),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("domain"),
    )

    op.create_table(
        "merchant_policies",
        sa.Column("id", sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column("merchant_id", sa.BigInteger(), nullable=False),
        sa.Column("policy_type", sa.String(100), nullable=False),
        sa.Column("policy_value", sa.Text()),
        sa.Column("source_url", sa.String(2000)),
        sa.Column("effective_from", sa.Date()),
        sa.Column("effective_to", sa.Date()),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["merchant_id"], ["merchants.id"]),
        sa.PrimaryKeyConstraint("id"),
    )


def downgrade() -> None:
    op.drop_table("merchant_policies")
    op.drop_table("merchants")
    op.drop_table("action_recommendations")
    op.drop_table("alerts")
    op.drop_table("price_checks")
    op.drop_table("product_matches")
    op.drop_table("orders")
    op.drop_table("uploads")
    op.drop_index("ix_users_email", "users")
    op.drop_table("users")
