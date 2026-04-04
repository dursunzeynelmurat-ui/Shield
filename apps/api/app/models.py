"""All SQLAlchemy models for Fiyat Kalkanı."""
import enum
from datetime import datetime, date
from decimal import Decimal

from sqlalchemy import (
    BigInteger, Boolean, Date, DateTime, Enum, ForeignKey,
    Integer, Numeric, String, Text, func,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


# ---------------------------------------------------------------------------
# Enums
# ---------------------------------------------------------------------------

class UploadStatus(str, enum.Enum):
    pending = "pending"
    processing = "processing"
    parsed = "parsed"
    failed = "failed"


class OrderStatus(str, enum.Enum):
    pending_verification = "pending_verification"
    verified = "verified"
    matching = "matching"
    matched = "matched"
    monitoring = "monitoring"
    completed = "completed"
    failed = "failed"


class AlertStatus(str, enum.Enum):
    new = "new"
    seen = "seen"
    acted = "acted"
    dismissed = "dismissed"


class AlertType(str, enum.Enum):
    price_drop = "price_drop"
    return_deadline_approaching = "return_deadline_approaching"


class ActionType(str, enum.Enum):
    ask_price_match = "ask_price_match"
    return_and_rebuy = "return_and_rebuy"
    manual_review = "manual_review"


class MatchMethod(str, enum.Enum):
    search_api = "search_api"
    scrape_search = "scrape_search"
    manual = "manual"


class CheckMethod(str, enum.Enum):
    selector = "selector"
    rendered = "rendered"
    playwright = "playwright"
    vision = "vision"
    manual = "manual"


# ---------------------------------------------------------------------------
# Models
# ---------------------------------------------------------------------------

class User(Base):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    email: Mapped[str] = mapped_column(String(255), unique=True, nullable=False, index=True)
    password_hash: Mapped[str] = mapped_column(String(255), nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

    uploads: Mapped[list["Upload"]] = relationship(back_populates="user")
    orders: Mapped[list["Order"]] = relationship(back_populates="user")


class Upload(Base):
    __tablename__ = "uploads"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("users.id"), nullable=False)
    file_type: Mapped[str] = mapped_column(String(50), nullable=False)
    storage_url: Mapped[str] = mapped_column(String(1000), nullable=False)
    original_filename: Mapped[str | None] = mapped_column(String(500))
    file_size: Mapped[int | None] = mapped_column(Integer)
    status: Mapped[UploadStatus] = mapped_column(Enum(UploadStatus), default=UploadStatus.pending, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    user: Mapped["User"] = relationship(back_populates="uploads")
    orders: Mapped[list["Order"]] = relationship(back_populates="upload")


class Order(Base):
    __tablename__ = "orders"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("users.id"), nullable=False)
    upload_id: Mapped[int | None] = mapped_column(BigInteger, ForeignKey("uploads.id"))
    merchant: Mapped[str | None] = mapped_column(String(100))
    merchant_order_no: Mapped[str | None] = mapped_column(String(200))
    product_title_raw: Mapped[str | None] = mapped_column(Text)
    normalized_title: Mapped[str | None] = mapped_column(Text)
    brand: Mapped[str | None] = mapped_column(String(200))
    model: Mapped[str | None] = mapped_column(String(200))
    variant: Mapped[str | None] = mapped_column(String(200))
    sku: Mapped[str | None] = mapped_column(String(200))
    seller_name: Mapped[str | None] = mapped_column(String(200))
    purchase_price: Mapped[Decimal | None] = mapped_column(Numeric(12, 2))
    currency: Mapped[str | None] = mapped_column(String(10))
    purchased_at: Mapped[date | None] = mapped_column(Date)
    delivery_date: Mapped[date | None] = mapped_column(Date)
    return_deadline: Mapped[date | None] = mapped_column(Date)
    parse_confidence: Mapped[float | None] = mapped_column(Numeric(4, 3))
    parse_raw: Mapped[str | None] = mapped_column(Text)  # JSON string
    status: Mapped[OrderStatus] = mapped_column(Enum(OrderStatus), default=OrderStatus.pending_verification, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

    user: Mapped["User"] = relationship(back_populates="orders")
    upload: Mapped["Upload"] = relationship(back_populates="orders")
    product_matches: Mapped[list["ProductMatch"]] = relationship(back_populates="order")
    alerts: Mapped[list["Alert"]] = relationship(back_populates="order")
    action_recommendations: Mapped[list["ActionRecommendation"]] = relationship(back_populates="order")


class ProductMatch(Base):
    __tablename__ = "product_matches"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    order_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("orders.id"), nullable=False)
    canonical_title: Mapped[str | None] = mapped_column(Text)
    matched_url: Mapped[str | None] = mapped_column(String(2000))
    merchant: Mapped[str | None] = mapped_column(String(100))
    seller_name: Mapped[str | None] = mapped_column(String(200))
    match_method: Mapped[MatchMethod | None] = mapped_column(Enum(MatchMethod))
    match_confidence: Mapped[float | None] = mapped_column(Numeric(4, 3))
    same_variant_verified: Mapped[bool] = mapped_column(Boolean, default=False)
    same_seller_verified: Mapped[bool] = mapped_column(Boolean, default=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

    order: Mapped["Order"] = relationship(back_populates="product_matches")
    price_checks: Mapped[list["PriceCheck"]] = relationship(back_populates="product_match")


class PriceCheck(Base):
    __tablename__ = "price_checks"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    product_match_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("product_matches.id"), nullable=False)
    checked_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    listed_price: Mapped[Decimal | None] = mapped_column(Numeric(12, 2))
    shipping_price: Mapped[Decimal | None] = mapped_column(Numeric(12, 2))
    final_price: Mapped[Decimal | None] = mapped_column(Numeric(12, 2))
    currency: Mapped[str | None] = mapped_column(String(10))
    seller_name: Mapped[str | None] = mapped_column(String(200))
    stock_status: Mapped[str | None] = mapped_column(String(50))
    coupon_detected: Mapped[bool] = mapped_column(Boolean, default=False)
    coupon_text: Mapped[str | None] = mapped_column(Text)
    check_method: Mapped[CheckMethod | None] = mapped_column(Enum(CheckMethod))
    evidence_image_url: Mapped[str | None] = mapped_column(String(2000))
    raw_payload: Mapped[str | None] = mapped_column(Text)
    success: Mapped[bool] = mapped_column(Boolean, default=False)
    error_message: Mapped[str | None] = mapped_column(Text)

    product_match: Mapped["ProductMatch"] = relationship(back_populates="price_checks")
    alerts: Mapped[list["Alert"]] = relationship(back_populates="price_check")


class Alert(Base):
    __tablename__ = "alerts"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    order_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("orders.id"), nullable=False)
    price_check_id: Mapped[int | None] = mapped_column(BigInteger, ForeignKey("price_checks.id"))
    alert_type: Mapped[AlertType] = mapped_column(Enum(AlertType), nullable=False)
    amount_saved: Mapped[Decimal | None] = mapped_column(Numeric(12, 2))
    message: Mapped[str | None] = mapped_column(Text)
    status: Mapped[AlertStatus] = mapped_column(Enum(AlertStatus), default=AlertStatus.new, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    order: Mapped["Order"] = relationship(back_populates="alerts")
    price_check: Mapped["PriceCheck"] = relationship(back_populates="alerts")
    action_recommendations: Mapped[list["ActionRecommendation"]] = relationship(back_populates="alert")


class ActionRecommendation(Base):
    __tablename__ = "action_recommendations"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    order_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("orders.id"), nullable=False)
    alert_id: Mapped[int | None] = mapped_column(BigInteger, ForeignKey("alerts.id"))
    action_type: Mapped[ActionType] = mapped_column(Enum(ActionType), nullable=False)
    recommended_text: Mapped[str | None] = mapped_column(Text)
    target_url: Mapped[str | None] = mapped_column(String(2000))
    estimated_savings: Mapped[Decimal | None] = mapped_column(Numeric(12, 2))
    confidence: Mapped[float | None] = mapped_column(Numeric(4, 3))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    order: Mapped["Order"] = relationship(back_populates="action_recommendations")
    alert: Mapped["Alert"] = relationship(back_populates="action_recommendations")


class Merchant(Base):
    __tablename__ = "merchants"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    domain: Mapped[str] = mapped_column(String(200), unique=True, nullable=False)
    supports_scraping: Mapped[bool] = mapped_column(Boolean, default=False)
    supports_playwright: Mapped[bool] = mapped_column(Boolean, default=False)
    notes: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    policies: Mapped[list["MerchantPolicy"]] = relationship(back_populates="merchant")


class MerchantPolicy(Base):
    __tablename__ = "merchant_policies"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    merchant_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("merchants.id"), nullable=False)
    policy_type: Mapped[str] = mapped_column(String(100), nullable=False)
    policy_value: Mapped[str | None] = mapped_column(Text)
    source_url: Mapped[str | None] = mapped_column(String(2000))
    effective_from: Mapped[date | None] = mapped_column(Date)
    effective_to: Mapped[date | None] = mapped_column(Date)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    merchant: Mapped["Merchant"] = relationship(back_populates="policies")
