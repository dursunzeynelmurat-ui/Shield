"use client";
import { useEffect, useState } from "react";
import { useParams, useRouter } from "next/navigation";
import Navbar from "@/components/Navbar";
import {
  getOrder, verifyOrder, matchOrder, startMonitoring,
  stopMonitoring, getRecommendation, getMatches, runPriceCheck,
} from "@/lib/api";
import type { Order, ProductMatch, ActionRecommendation } from "@/types";

const ACTION_LABELS: Record<string, string> = {
  ask_price_match: "Fiyat Eşleştirmesi İste",
  return_and_rebuy: "İade Et ve Yeniden Satın Al",
  manual_review: "Manuel İnceleme",
};

const ACTION_COLORS: Record<string, string> = {
  ask_price_match: "bg-green-50 border-green-200 text-green-800",
  return_and_rebuy: "bg-blue-50 border-blue-200 text-blue-800",
  manual_review: "bg-yellow-50 border-yellow-200 text-yellow-800",
};

export default function OrderDetailPage() {
  const { id } = useParams<{ id: string }>();
  const router = useRouter();
  const [order, setOrder] = useState<Order | null>(null);
  const [matches, setMatches] = useState<ProductMatch[]>([]);
  const [recommendation, setRecommendation] = useState<ActionRecommendation | null>(null);
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState("");
  const [editMode, setEditMode] = useState(false);
  const [form, setForm] = useState<Partial<Order>>({});

  const orderId = parseInt(id);

  const fetchAll = async () => {
    const [o, m] = await Promise.all([getOrder(orderId), getMatches(orderId)]);
    setOrder(o);
    setMatches(m);
    if (o.status !== "pending_verification") {
      try {
        const rec = await getRecommendation(orderId);
        setRecommendation(rec);
      } catch {}
    }
  };

  useEffect(() => {
    fetchAll().finally(() => setLoading(false));
  }, [orderId]);

  const handleVerify = async () => {
    setSaving(true);
    setError("");
    try {
      const updated = await verifyOrder(orderId, form);
      setOrder(updated);
      setEditMode(false);
      setForm({});
    } catch {
      setError("Doğrulama başarısız.");
    } finally {
      setSaving(false);
    }
  };

  const handleMatch = async () => {
    setSaving(true);
    setError("");
    try {
      await matchOrder(orderId);
      await fetchAll();
    } catch (err: unknown) {
      const msg = (err as { response?: { data?: { detail?: string } } })?.response?.data?.detail;
      setError(msg || "Eşleştirme başarısız.");
    } finally {
      setSaving(false);
    }
  };

  const handleStartMonitoring = async () => {
    setSaving(true);
    try {
      const updated = await startMonitoring(orderId);
      setOrder(updated);
    } catch (err: unknown) {
      const msg = (err as { response?: { data?: { detail?: string } } })?.response?.data?.detail;
      setError(msg || "İzleme başlatılamadı.");
    } finally {
      setSaving(false);
    }
  };

  const handlePriceCheck = async () => {
    setSaving(true);
    try {
      await runPriceCheck(orderId);
      await fetchAll();
    } catch (err: unknown) {
      const msg = (err as { response?: { data?: { detail?: string } } })?.response?.data?.detail;
      setError(msg || "Fiyat kontrolü başarısız.");
    } finally {
      setSaving(false);
    }
  };

  if (loading) {
    return (
      <>
        <Navbar />
        <div className="p-8 text-gray-500">Yükleniyor...</div>
      </>
    );
  }

  if (!order) {
    return (
      <>
        <Navbar />
        <div className="p-8 text-red-500">Sipariş bulunamadı.</div>
      </>
    );
  }

  const activeMatch = matches.find((m) => m.is_active);

  return (
    <>
      <Navbar />
      <div className="max-w-3xl mx-auto p-6 space-y-6">

        {/* Header */}
        <div>
          <button onClick={() => router.push("/dashboard")} className="text-sm text-blue-600 hover:underline mb-3 block">
            ← Dashboard
          </button>
          <h1 className="text-xl font-bold text-gray-800">Sipariş Detayı #{order.id}</h1>
          <span className="text-xs bg-gray-100 text-gray-600 px-2 py-0.5 rounded-full">{order.status}</span>
        </div>

        {error && (
          <div className="bg-red-50 border border-red-200 text-red-700 rounded-lg p-3 text-sm">{error}</div>
        )}

        {/* Recommendation */}
        {recommendation && (
          <div className={`border rounded-xl p-4 ${ACTION_COLORS[recommendation.action_type]}`}>
            <div className="flex items-center justify-between mb-1">
              <span className="font-semibold text-sm">{ACTION_LABELS[recommendation.action_type]}</span>
              {recommendation.estimated_savings && (
                <span className="text-xs font-bold">
                  {recommendation.estimated_savings} {order.currency} tasarruf
                </span>
              )}
            </div>
            <p className="text-sm">{recommendation.recommended_text}</p>
            {recommendation.target_url && (
              <a
                href={recommendation.target_url}
                target="_blank"
                rel="noopener noreferrer"
                className="text-xs underline mt-1 block"
              >
                Ürün sayfasına git
              </a>
            )}
          </div>
        )}

        {/* Order Info */}
        <div className="bg-white rounded-2xl shadow p-5">
          <div className="flex items-center justify-between mb-4">
            <h2 className="font-semibold text-gray-700">Sipariş Bilgileri</h2>
            {order.status === "pending_verification" && !editMode && (
              <button
                onClick={() => { setEditMode(true); setForm({ ...order }); }}
                className="text-sm text-blue-600 hover:underline"
              >
                Düzenle
              </button>
            )}
          </div>

          {editMode ? (
            <div className="space-y-3">
              {(["merchant", "product_title_raw", "brand", "model", "variant", "sku", "seller_name", "purchase_price", "currency", "purchased_at", "return_deadline"] as (keyof Order)[]).map((field) => (
                <div key={field} className="flex gap-3 items-center">
                  <label className="text-xs text-gray-500 w-36 flex-shrink-0">{field}</label>
                  <input
                    type="text"
                    value={(form[field] as string) || ""}
                    onChange={(e) => setForm((prev) => ({ ...prev, [field]: e.target.value }))}
                    className="flex-1 border border-gray-300 rounded px-2 py-1 text-sm"
                  />
                </div>
              ))}
              <div className="flex gap-2 mt-2">
                <button
                  onClick={handleVerify}
                  disabled={saving}
                  className="bg-blue-600 text-white px-4 py-1.5 rounded text-sm disabled:opacity-50"
                >
                  {saving ? "Kaydediliyor..." : "Doğrula ve Kaydet"}
                </button>
                <button
                  onClick={() => setEditMode(false)}
                  className="px-4 py-1.5 text-sm border border-gray-300 rounded hover:bg-gray-50"
                >
                  İptal
                </button>
              </div>
            </div>
          ) : (
            <dl className="grid grid-cols-2 gap-x-4 gap-y-2 text-sm">
              {[
                ["Mağaza", order.merchant],
                ["Sipariş No", order.merchant_order_no],
                ["Ürün", order.product_title_raw],
                ["Marka", order.brand],
                ["Model", order.model],
                ["Varyant", order.variant],
                ["SKU", order.sku],
                ["Satıcı", order.seller_name],
                ["Fiyat", order.purchase_price ? `${order.purchase_price} ${order.currency}` : null],
                ["Satın Alım", order.purchased_at],
                ["İade Son", order.return_deadline],
                ["AI Güven", order.parse_confidence ? `${Math.round(order.parse_confidence * 100)}%` : null],
              ].map(([label, value]) => value ? (
                <div key={label as string}>
                  <dt className="text-gray-400 text-xs">{label}</dt>
                  <dd className="font-medium text-gray-700">{value}</dd>
                </div>
              ) : null)}
            </dl>
          )}
        </div>

        {/* Match */}
        <div className="bg-white rounded-2xl shadow p-5">
          <h2 className="font-semibold text-gray-700 mb-3">Ürün Eşleştirme</h2>
          {activeMatch ? (
            <div className="space-y-2 text-sm">
              <p><span className="text-gray-400 text-xs">Başlık</span><br /><span>{activeMatch.canonical_title || "—"}</span></p>
              <p><span className="text-gray-400 text-xs">Güven</span><br />
                <span>{activeMatch.match_confidence ? `${Math.round(activeMatch.match_confidence * 100)}%` : "—"}</span>
              </p>
              {activeMatch.matched_url && (
                <p>
                  <span className="text-gray-400 text-xs">URL</span><br />
                  <a href={activeMatch.matched_url} target="_blank" rel="noopener noreferrer" className="text-blue-600 hover:underline text-xs break-all">
                    {activeMatch.matched_url}
                  </a>
                </p>
              )}
            </div>
          ) : (
            <p className="text-sm text-gray-400">Henüz eşleştirme yapılmadı.</p>
          )}

          {(order.status === "verified" || order.status === "matched") && (
            <button
              onClick={handleMatch}
              disabled={saving}
              className="mt-3 bg-blue-600 text-white px-4 py-1.5 rounded text-sm disabled:opacity-50"
            >
              {saving ? "..." : "Eşleştir"}
            </button>
          )}
        </div>

        {/* Monitoring Actions */}
        <div className="bg-white rounded-2xl shadow p-5 flex gap-3 flex-wrap">
          {order.status === "matched" && (
            <button
              onClick={handleStartMonitoring}
              disabled={saving}
              className="bg-green-600 text-white px-4 py-2 rounded-lg text-sm disabled:opacity-50"
            >
              İzlemeyi Başlat
            </button>
          )}
          {order.status === "monitoring" && (
            <>
              <button
                onClick={handlePriceCheck}
                disabled={saving}
                className="bg-blue-600 text-white px-4 py-2 rounded-lg text-sm disabled:opacity-50"
              >
                Fiyat Kontrol Et
              </button>
              <button
                onClick={() => stopMonitoring(orderId).then((o) => setOrder(o))}
                className="border border-gray-300 text-gray-600 px-4 py-2 rounded-lg text-sm hover:bg-gray-50"
              >
                İzlemeyi Durdur
              </button>
            </>
          )}
        </div>

      </div>
    </>
  );
}
