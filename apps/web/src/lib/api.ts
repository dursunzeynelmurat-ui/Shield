import axios from "axios";
import Cookies from "js-cookie";

const API_URL = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

export const api = axios.create({
  baseURL: API_URL,
});

api.interceptors.request.use((config) => {
  const token = Cookies.get("token");
  if (token) {
    config.headers.Authorization = `Bearer ${token}`;
  }
  return config;
});

api.interceptors.response.use(
  (r) => r,
  (err) => {
    if (err.response?.status === 401) {
      Cookies.remove("token");
      window.location.href = "/login";
    }
    return Promise.reject(err);
  }
);

// Auth
export const register = (email: string, password: string) =>
  api.post("/auth/register", { email, password });

export const login = async (email: string, password: string) => {
  const params = new URLSearchParams();
  params.append("username", email);
  params.append("password", password);
  const res = await api.post("/auth/login", params, {
    headers: { "Content-Type": "application/x-www-form-urlencoded" },
  });
  return res.data;
};

// Dashboard
export const getDashboard = () =>
  api.get("/users/me/dashboard").then((r) => r.data);

// Uploads
export const uploadFile = (file: File) => {
  const form = new FormData();
  form.append("file", file);
  return api.post("/uploads", form).then((r) => r.data);
};

export const getUpload = (id: number) =>
  api.get(`/uploads/${id}`).then((r) => r.data);

// Orders
export const createOrderFromUpload = (uploadId: number) =>
  api.post(`/orders/from-upload/${uploadId}`).then((r) => r.data);

export const getOrder = (id: number) =>
  api.get(`/orders/${id}`).then((r) => r.data);

export const verifyOrder = (id: number, data: Record<string, unknown>) =>
  api.patch(`/orders/${id}/verify`, data).then((r) => r.data);

export const matchOrder = (id: number) =>
  api.post(`/orders/${id}/match`).then((r) => r.data);

export const startMonitoring = (id: number) =>
  api.post(`/orders/${id}/start-monitoring`).then((r) => r.data);

export const stopMonitoring = (id: number) =>
  api.post(`/orders/${id}/stop-monitoring`).then((r) => r.data);

export const getRecommendation = (id: number) =>
  api.get(`/orders/${id}/recommendation`).then((r) => r.data);

export const getMatches = (id: number) =>
  api.get(`/orders/${id}/matches`).then((r) => r.data);

// Price checks
export const runPriceCheck = (orderId: number) =>
  api.post(`/price-checks/run/${orderId}`).then((r) => r.data);

export const getPriceChecks = (orderId: number) =>
  api.get(`/price-checks/${orderId}`).then((r) => r.data);

// Alerts
export const getAlerts = () =>
  api.get("/alerts").then((r) => r.data);

export const updateAlertStatus = (alertId: number, status: string) =>
  api.patch(`/alerts/${alertId}/status`, null, { params: { status } }).then((r) => r.data);

// User profile
export const getMe = () =>
  api.get("/users/me").then((r) => r.data);

export const updateMe = (data: { email?: string }) =>
  api.patch("/users/me", data).then((r) => r.data);

export const changePassword = (current_password: string, new_password: string) =>
  api.post("/users/me/change-password", { current_password, new_password });

export const deleteAccount = () =>
  api.delete("/users/me");

// Catalog
export const searchCatalog = (params: {
  q?: string; category?: string; brand?: string; page?: number; page_size?: number;
}) => api.get("/catalog/search", { params }).then((r) => r.data);

export const getProduct = (id: number) =>
  api.get(`/catalog/products/${id}`).then((r) => r.data);

// Deals
export const getDeals = (params: {
  merchant?: string; discount_type?: string; page?: number; page_size?: number;
}) => api.get("/deals/offers", { params }).then((r) => r.data);

// Discovery
export const getDiscoveryFeed = (page = 1) =>
  api.get("/discovery/feed", { params: { page } }).then((r) => r.data);

export const postInterestEvent = (body: {
  event_type: string; product_id?: number; query?: string; metadata_json?: string;
}) => api.post("/discovery/interest-events", body).then((r) => r.data);

// Affiliate
export const trackClick = (body: {
  merchant_offer_id?: number; offer_id?: number; url?: string;
}) => api.post("/affiliate/click", body).then((r) => r.data);

// Watchlist
export const addToWatchlist = (product_id: number, target_price?: number) =>
  api.post("/watchlist", { product_id, target_price }).then((r) => r.data);

export const removeFromWatchlist = (product_id: number) =>
  api.delete(`/watchlist/${product_id}`).then((r) => r.data);
