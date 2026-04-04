export type OrderStatus =
  | "pending_verification"
  | "verified"
  | "matching"
  | "matched"
  | "monitoring"
  | "completed"
  | "failed";

export type AlertStatus = "new" | "seen" | "acted" | "dismissed";

export type ActionType = "ask_price_match" | "return_and_rebuy" | "manual_review";

export interface DashboardCard {
  order_id: number;
  product_name: string | null;
  purchase_price: number | null;
  current_price: number | null;
  currency: string | null;
  savings: number | null;
  remaining_return_days: number | null;
  status: OrderStatus;
  has_alert: boolean;
}

export interface Order {
  id: number;
  user_id: number;
  upload_id: number | null;
  merchant: string | null;
  merchant_order_no: string | null;
  product_title_raw: string | null;
  normalized_title: string | null;
  brand: string | null;
  model: string | null;
  variant: string | null;
  sku: string | null;
  seller_name: string | null;
  purchase_price: number | null;
  currency: string | null;
  purchased_at: string | null;
  delivery_date: string | null;
  return_deadline: string | null;
  parse_confidence: number | null;
  status: OrderStatus;
  created_at: string;
  updated_at: string;
}

export interface ProductMatch {
  id: number;
  order_id: number;
  canonical_title: string | null;
  matched_url: string | null;
  merchant: string | null;
  seller_name: string | null;
  match_method: string | null;
  match_confidence: number | null;
  same_variant_verified: boolean;
  same_seller_verified: boolean;
  is_active: boolean;
  created_at: string;
  updated_at: string;
}

export interface Alert {
  id: number;
  order_id: number;
  price_check_id: number | null;
  alert_type: string;
  amount_saved: number | null;
  message: string | null;
  status: AlertStatus;
  created_at: string;
}

export interface ActionRecommendation {
  id: number;
  order_id: number;
  alert_id: number | null;
  action_type: ActionType;
  recommended_text: string | null;
  target_url: string | null;
  estimated_savings: number | null;
  confidence: number | null;
  created_at: string;
}
