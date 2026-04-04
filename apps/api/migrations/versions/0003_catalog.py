"""catalog, deals, discovery tables

Revision ID: 0003
Revises: 0002
Create Date: 2026-04-04
"""
from typing import Sequence, Union
import sqlalchemy as sa
from alembic import op

revision: str = "0003"
down_revision: Union[str, None] = "0002"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "products",
        sa.Column("id", sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column("name", sa.String(500), nullable=False),
        sa.Column("normalized_name", sa.String(500)),
        sa.Column("brand", sa.String(200)),
        sa.Column("model", sa.String(200)),
        sa.Column("category", sa.String(200)),
        sa.Column("description", sa.Text()),
        sa.Column("image_url", sa.String(2000)),
        sa.Column("ean", sa.String(50)),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_products_normalized_name", "products", ["normalized_name"])
    op.create_index("ix_products_brand", "products", ["brand"])
    op.create_index("ix_products_category", "products", ["category"])
    op.create_index("ix_products_ean", "products", ["ean"])

    op.create_table(
        "merchant_offers",
        sa.Column("id", sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column("product_id", sa.BigInteger(), nullable=False),
        sa.Column("merchant", sa.String(100), nullable=False),
        sa.Column("seller_name", sa.String(200)),
        sa.Column("url", sa.String(2000)),
        sa.Column("listed_price", sa.Numeric(12, 2)),
        sa.Column("shipping_price", sa.Numeric(12, 2)),
        sa.Column("effective_price", sa.Numeric(12, 2)),
        sa.Column("currency", sa.String(10), server_default="TRY"),
        sa.Column("in_stock", sa.Boolean(), server_default=sa.text("true")),
        sa.Column("last_checked_at", sa.DateTime(timezone=True)),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["product_id"], ["products.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("product_id", "merchant", "seller_name", name="uq_merchant_offer"),
    )
    op.create_index("ix_merchant_offers_product_id", "merchant_offers", ["product_id"])
    op.create_index("ix_merchant_offers_merchant", "merchant_offers", ["merchant"])

    op.create_table(
        "price_history",
        sa.Column("id", sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column("product_id", sa.BigInteger(), nullable=False),
        sa.Column("merchant", sa.String(100), nullable=False),
        sa.Column("price", sa.Numeric(12, 2), nullable=False),
        sa.Column("currency", sa.String(10), server_default="TRY"),
        sa.Column("recorded_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["product_id"], ["products.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_price_history_product_id", "price_history", ["product_id"])
    op.create_index("ix_price_history_recorded_at", "price_history", ["recorded_at"])

    op.create_table(
        "offers",
        sa.Column("id", sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column("merchant", sa.String(100), nullable=False),
        sa.Column("product_id", sa.BigInteger()),
        sa.Column("title", sa.String(500), nullable=False),
        sa.Column("description", sa.Text()),
        sa.Column("code", sa.String(100)),
        sa.Column("discount_type", sa.String(50)),
        sa.Column("discount_value", sa.Numeric(10, 2)),
        sa.Column("minimum_spend", sa.Numeric(12, 2)),
        sa.Column("conditions", sa.Text()),
        sa.Column("url", sa.String(2000)),
        sa.Column("expires_at", sa.DateTime(timezone=True)),
        sa.Column("last_seen_at", sa.DateTime(timezone=True)),
        sa.Column("confidence", sa.Numeric(4, 3), server_default="1.0"),
        sa.Column("status", sa.String(20), server_default="active"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["product_id"], ["products.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_offers_merchant", "offers", ["merchant"])
    op.create_index("ix_offers_status", "offers", ["status"])
    op.create_index("ix_offers_expires_at", "offers", ["expires_at"])

    op.create_table(
        "watchlists",
        sa.Column("id", sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column("user_id", sa.BigInteger(), nullable=False),
        sa.Column("product_id", sa.BigInteger(), nullable=False),
        sa.Column("target_price", sa.Numeric(12, 2)),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"]),
        sa.ForeignKeyConstraint(["product_id"], ["products.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("user_id", "product_id", name="uq_watchlist_user_product"),
    )
    op.create_index("ix_watchlists_user_id", "watchlists", ["user_id"])
    op.create_index("ix_watchlists_product_id", "watchlists", ["product_id"])

    op.create_table(
        "user_interest_events",
        sa.Column("id", sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column("user_id", sa.BigInteger(), nullable=False),
        sa.Column("event_type", sa.String(30), nullable=False),
        sa.Column("product_id", sa.BigInteger()),
        sa.Column("query", sa.String(500)),
        sa.Column("metadata_json", sa.Text()),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"]),
        sa.ForeignKeyConstraint(["product_id"], ["products.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_user_interest_events_user_id", "user_interest_events", ["user_id"])
    op.create_index("ix_user_interest_events_created_at", "user_interest_events", ["created_at"])

    op.create_table(
        "recommendation_items",
        sa.Column("id", sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column("user_id", sa.BigInteger(), nullable=False),
        sa.Column("product_id", sa.BigInteger(), nullable=False),
        sa.Column("reason", sa.String(200)),
        sa.Column("score", sa.Numeric(6, 4), server_default="0"),
        sa.Column("generated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True)),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"]),
        sa.ForeignKeyConstraint(["product_id"], ["products.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_recommendation_items_user_id", "recommendation_items", ["user_id"])

    op.create_table(
        "affiliate_clicks",
        sa.Column("id", sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column("user_id", sa.BigInteger()),
        sa.Column("merchant_offer_id", sa.BigInteger()),
        sa.Column("offer_id", sa.BigInteger()),
        sa.Column("url", sa.String(2000)),
        sa.Column("ip_hash", sa.String(64)),
        sa.Column("clicked_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"]),
        sa.ForeignKeyConstraint(["merchant_offer_id"], ["merchant_offers.id"]),
        sa.ForeignKeyConstraint(["offer_id"], ["offers.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_affiliate_clicks_user_id", "affiliate_clicks", ["user_id"])


def downgrade() -> None:
    op.drop_table("affiliate_clicks")
    op.drop_table("recommendation_items")
    op.drop_table("user_interest_events")
    op.drop_table("watchlists")
    op.drop_table("offers")
    op.drop_table("price_history")
    op.drop_table("merchant_offers")
    op.drop_table("products")
