"""Pydantic schemas for API request/response."""
from datetime import datetime, date
from decimal import Decimal
from typing import Any

from pydantic import BaseModel, EmailStr

from app.models import (
    AlertStatus, AlertType, ActionType, CheckMethod,
    MatchMethod, OrderStatus, UploadStatus,
)


# ---------------------------------------------------------------------------
# Auth
# ---------------------------------------------------------------------------

class UserCreate(BaseModel):
    email: EmailStr
    password: str


class UserLogin(BaseModel):
    email: EmailStr
    password: str


class UserOut(BaseModel):
    id: int
    email: str
    is_active: bool
    created_at: datetime

    model_config = {"from_attributes": True}


class Token(BaseModel):
    access_token: str
    token_type: str = "bearer"


# ---------------------------------------------------------------------------
# Uploads
# ---------------------------------------------------------------------------

class UploadOut(BaseModel):
    id: int
    user_id: int
    file_type: str
    storage_url: str
    original_filename: str | None
    file_size: int | None
    status: UploadStatus
    created_at: datetime

    model_config = {"from_attributes": True}


# ---------------------------------------------------------------------------
# Orders
# ---------------------------------------------------------------------------

class ParsedOrderData(BaseModel):
    """Structured data extracted by the parser."""
    merchant: str | None = None
    merchant_order_no: str | None = None
    product_title_raw: str | None = None
    brand: str | None = None
    model: str | None = None
    variant: str | None = None
    sku: str | None = None
    seller_name: str | None = None
    purchase_price: Decimal | None = None
    currency: str | None = None
    purchased_at: date | None = None
    delivery_date: date | None = None
    return_deadline: date | None = None
    confidence: float = 0.0
    raw_extraction: dict[str, Any] | None = None


class OrderOut(BaseModel):
    id: int
    user_id: int
    upload_id: int | None
    merchant: str | None
    merchant_order_no: str | None
    product_title_raw: str | None
    normalized_title: str | None
    brand: str | None
    model: str | None
    variant: str | None
    sku: str | None
    seller_name: str | None
    purchase_price: Decimal | None
    currency: str | None
    purchased_at: date | None
    delivery_date: date | None
    return_deadline: date | None
    parse_confidence: float | None
    status: OrderStatus
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class OrderVerifyRequest(BaseModel):
    merchant: str | None = None
    merchant_order_no: str | None = None
    product_title_raw: str | None = None
    brand: str | None = None
    model: str | None = None
    variant: str | None = None
    sku: str | None = None
    seller_name: str | None = None
    purchase_price: Decimal | None = None
    currency: str | None = None
    purchased_at: date | None = None
    delivery_date: date | None = None
    return_deadline: date | None = None


# ---------------------------------------------------------------------------
# Product Matches
# ---------------------------------------------------------------------------

class ProductMatchOut(BaseModel):
    id: int
    order_id: int
    canonical_title: str | None
    matched_url: str | None
    merchant: str | None
    seller_name: str | None
    match_method: MatchMethod | None
    match_confidence: float | None
    same_variant_verified: bool
    same_seller_verified: bool
    is_active: bool
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class MatchConfirmRequest(BaseModel):
    match_id: int
    same_variant_verified: bool = True
    same_seller_verified: bool = False


# ---------------------------------------------------------------------------
# Price Checks
# ---------------------------------------------------------------------------

class PriceCheckOut(BaseModel):
    id: int
    product_match_id: int
    checked_at: datetime
    listed_price: Decimal | None
    shipping_price: Decimal | None
    final_price: Decimal | None
    currency: str | None
    seller_name: str | None
    stock_status: str | None
    coupon_detected: bool
    coupon_text: str | None
    check_method: CheckMethod | None
    evidence_image_url: str | None
    success: bool
    error_message: str | None

    model_config = {"from_attributes": True}


# ---------------------------------------------------------------------------
# Alerts
# ---------------------------------------------------------------------------

class AlertOut(BaseModel):
    id: int
    order_id: int
    price_check_id: int | None
    alert_type: AlertType
    amount_saved: Decimal | None
    message: str | None
    status: AlertStatus
    created_at: datetime

    model_config = {"from_attributes": True}


# ---------------------------------------------------------------------------
# Action Recommendations
# ---------------------------------------------------------------------------

class ActionRecommendationOut(BaseModel):
    id: int
    order_id: int
    alert_id: int | None
    action_type: ActionType
    recommended_text: str | None
    target_url: str | None
    estimated_savings: Decimal | None
    confidence: float | None
    created_at: datetime

    model_config = {"from_attributes": True}


# ---------------------------------------------------------------------------
# Dashboard
# ---------------------------------------------------------------------------

class DashboardCard(BaseModel):
    order_id: int
    product_name: str | None
    purchase_price: Decimal | None
    current_price: Decimal | None
    currency: str | None
    savings: Decimal | None
    remaining_return_days: int | None
    status: OrderStatus
    has_alert: bool
