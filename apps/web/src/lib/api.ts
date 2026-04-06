import axios from "axios";
import { auth } from "./firebase";

const API_URL = "/api/backend";

export const api = axios.create({
  baseURL: API_URL,
});

api.interceptors.request.use(async (config) => {
  const user = auth.currentUser;
  if (user) {
    const token = await user.getIdToken();
    config.headers.Authorization = `Bearer ${token}`;
  }
  return config;
});

api.interceptors.response.use(
  (r) => r,
  (err) => {
    if (err.response?.status === 401) {
      window.location.href = "/login";
    }
    return Promise.reject(err);
  }
);

// Catalog
export const searchCatalog = (params: {
  q?: string; category?: string; brand?: string; page?: number; page_size?: number;
}) => api.get("/catalog/search", { params }).then((r) => r.data);

export const getProduct = (id: number) =>
  api.get(`/catalog/products/${id}`).then((r) => r.data);

export const getDeals = (params?: Record<string, unknown>) =>
  api.get("/catalog/deals", { params }).then((r) => r.data);

export const trackClick = (offerIdOrPayload: number | { merchant_offer_id?: number; offer_id?: number; url?: string }) => {
  const id = typeof offerIdOrPayload === "number"
    ? offerIdOrPayload
    : (offerIdOrPayload.merchant_offer_id ?? offerIdOrPayload.offer_id ?? 0);
  return api.post(`/catalog/offers/${id}/click`).then((r) => r.data);
};

// Watchlist / monitoring
export const getWatchlist = () =>
  api.get("/monitoring/watchlist").then((r) => r.data);

export const addToWatchlist = (productId: number) =>
  api.post("/monitoring/watchlist", { product_id: productId }).then((r) => r.data);

export const removeFromWatchlist = (itemId: number) =>
  api.delete(`/monitoring/watchlist/${itemId}`).then((r) => r.data);

export const startMonitoring = (orderId: number) =>
  api.post(`/monitoring/orders/${orderId}/start`).then((r) => r.data);

export const stopMonitoring = (orderId: number) =>
  api.post(`/monitoring/orders/${orderId}/stop`).then((r) => r.data);

export const runPriceCheck = (orderId: number) =>
  api.post(`/monitoring/orders/${orderId}/check`).then((r) => r.data);

// Orders
export const getOrder = (id: number) =>
  api.get(`/orders/${id}`).then((r) => r.data);

export const getMatches = (orderId: number) =>
  api.get(`/orders/${orderId}/matches`).then((r) => r.data);

export const getRecommendation = (orderId: number) =>
  api.get(`/orders/${orderId}/recommendation`).then((r) => r.data);

export const verifyOrder = (orderId: number, data?: Record<string, unknown>) =>
  api.post(`/orders/${orderId}/verify`, data).then((r) => r.data);

export const matchOrder = (orderId: number) =>
  api.post(`/orders/${orderId}/match`).then((r) => r.data);

// Uploads
export const uploadFile = (file: File) => {
  const form = new FormData();
  form.append("file", file);
  return api.post("/uploads/receipt", form).then((r) => r.data);
};

export const uploadReceipt = uploadFile;

export const createOrderFromUpload = (uploadId: number) =>
  api.post(`/uploads/${uploadId}/create-order`).then((r) => r.data);

// Alerts
export const getAlerts = () =>
  api.get("/alerts").then((r) => r.data);

export const updateAlertStatus = (alertId: number, status: string) =>
  api.patch(`/alerts/${alertId}`, { status }).then((r) => r.data);

// Dashboard
export const getDashboard = () =>
  api.get("/dashboard").then((r) => r.data);

export const getDashboardSummary = () =>
  api.get("/dashboard/summary").then((r) => r.data);

// Discovery / For You
export const getDiscoveryFeed = (paramsOrPage?: Record<string, unknown> | number) => {
  const params = typeof paramsOrPage === "number" ? { page: paramsOrPage } : paramsOrPage;
  return api.get("/discovery/feed", { params }).then((r) => r.data);
};

export const postInterestEvent = (productIdOrPayload: number | Record<string, unknown>, event?: string) => {
  const payload = typeof productIdOrPayload === "number"
    ? { product_id: productIdOrPayload, event }
    : productIdOrPayload;
  return api.post("/discovery/interest", payload).then((r) => r.data);
};

// User / settings
export const getMe = () =>
  api.get("/auth/me").then((r) => r.data);

export const updateMe = (data: Record<string, unknown>) =>
  api.patch("/auth/me", data).then((r) => r.data);

export const changePassword = (oldPassword: string, newPassword: string) =>
  api.post("/auth/change-password", { old_password: oldPassword, new_password: newPassword }).then((r) => r.data);

export const deleteAccount = () =>
  api.delete("/auth/me").then((r) => r.data);

// Legacy compat
export const login = async (email: string, password: string) => {
  const { loginWithEmail } = await import("./auth");
  const cred = await loginWithEmail(email, password);
  const token = await cred.user.getIdToken();
  return { access_token: token };
};

export const register = async (email: string, password: string) => {
  const { registerWithEmail } = await import("./auth");
  await registerWithEmail(email, password);
};
