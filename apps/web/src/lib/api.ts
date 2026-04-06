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

export const searchCatalog = (params: {
  q?: string;
  category?: string;
  brand?: string;
  page?: number;
  page_size?: number;
}) => api.get("/catalog/search", { params }).then((r) => r.data);

export const getProduct = (id: number) =>
  api.get(`/catalog/products/${id}`).then((r) => r.data);

export const getDeals = (params?: { page?: number; page_size?: number }) =>
  api.get("/catalog/deals", { params }).then((r) => r.data);

export const getWatchlist = () =>
  api.get("/monitoring/watchlist").then((r) => r.data);

export const addToWatchlist = (productId: number) =>
  api.post("/monitoring/watchlist", { product_id: productId }).then((r) => r.data);

export const removeFromWatchlist = (itemId: number) =>
  api.delete(`/monitoring/watchlist/${itemId}`).then((r) => r.data);

export const uploadReceipt = (file: File) => {
  const form = new FormData();
  form.append("file", file);
  return api.post("/uploads/receipt", form).then((r) => r.data);
};

export const getAlerts = () =>
  api.get("/alerts").then((r) => r.data);

// Legacy exports kept for compatibility
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
