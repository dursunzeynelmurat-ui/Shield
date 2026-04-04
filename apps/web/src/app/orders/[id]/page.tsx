"use client";
import { useEffect, useState } from "react";
import { useParams, useRouter } from "next/navigation";
import Navbar from "@/components/Navbar";
import {
  getOrder, verifyOrder, matchOrder, startMonitoring,
  stopMonitoring, getRecommendation, getMatches, runPriceCheck,
} from "@/lib/api";
import type { Order, ProductMatch, ActionRecommendation } from "@/types";

// ─── Flow steps ────────────────────────────────────────────────────────────

const FLOW = [
  { key: "pending_verification", label: "Doğrula" },
  { key: "verified",             label: "Eşleştir" },
  { key: "matched",              label: "İzle" },
  { key: "monitoring",           label: "Aktif" },
];

const STEP_INDEX: Record<string, number> = {
  pending_verification: 0, verified: 1, matching: 1, matched: 2, monitoring: 3, completed: 4, failed: 0,
};

// ─── Recommendation config ─────────────────────────────────────────────────

const REC_CONFIG: Record<string, { label: string; icon: string; style: string }> = {
  ask_price_match:  { label: "Fiyat Eşleştirmesi İste",    icon: "💬", style: "bg-emerald-50 border-emerald-200 text-emerald-800" },
  return_and_rebuy: { label: "İade Et ve Yeniden Satın Al", icon: "🔄", style: "bg-blue-50 border-blue-200 text-blue-800" },
  manual_review:    { label: "Manuel İnceleme",             icon: "🔍", style: "bg-amber-50 border-amber-200 text-amber-800" },
};

// ─── Sub-components ────────────────────────────────────────────────────────

function InfoRow({ label, value, mono = false }: { label: string; value: string | null | undefined; mono?: boolean }) {
  if (!value) return null;
  return (
    <div className="flex items-start justify-between gap-4 py-2.5 border-b border-slate-100 last:border-0">
      <span className="text-xs text-slate-400 shrink-0 pt-0.5">{label}</span>
      <span className={`text-sm font-medium text-slate-700 text-right ${mono ? "font-mono" : ""}`}>{value}</span>
    </div>
  );
}

function SectionCard({ title, children, action }: { title: string; children: React.ReactNode; action?: React.ReactNode }) {
  return (
    <div className="card">
      <div className="flex items-center justify-between px-5 pt-5 pb-3 border-b border-slate-100">
        <p className="text-xs font-semibold text-slate-400 uppercase tracking-widest">{title}</p>
        {action}
      </div>
      <div className="px-5 pb-4">{children}</div>
    </div>
  );
}

// ─── Main component ────────────────────────────────────────────────────────

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
  const [checkDone, setCheckDone] = useState(false);

  const orderId = parseInt(id);

  const fetchAll = async () => {
    const [o, m] = await Promise.all([getOrder(orderId), getMatches(orderId)]);
    setOrder(o);
    setMatches(m);
    if (!["pending_verification"].includes(o.status)) {
      try { setRecommendation(await getRecommendation(orderId)); } catch {}
    }
  };

  useEffect(() => { fetchAll().finally(() => setLoading(false)); }, [orderId]);

  const action = async (fn: () => Promise<unknown>, successRefetch = true) => {
    setSaving(true);
    setError("");
    try {
      await fn();
      if (successRefetch) await fetchAll();
    } catch (e: unknown) {
      const msg = (e as { response?: { data?: { detail?: string } } })?.response?.data?.detail;
      setError(msg || "İşlem başarısız.");
    } finally { setSaving(false); }
  };

  const handleVerify = () => action(async () => {
    const updated = await verifyOrder(orderId, form);
    setOrder(updated);
    setEditMode(false);
    setForm({});
  }, false);

  const handlePriceCheck = () => action(async () => {
    await runPriceCheck(orderId);
    setCheckDone(true);
  });

  if (loading) return (
    <>
      <Navbar />
      <div className="max-w-3xl mx-auto px-4 py-10 space-y-4">
        {[1, 2, 3].map(i => (
          <div key={i} className="card p-5 space-y-3">
            <div className="skeleton h-4 w-32" />
            <div className="skeleton h-3 w-full" />
            <div className="skeleton h-3 w-3/4" />
          </div>
        ))}
      </div>
    </>
  );

  if (!order) return (
    <>
      <Navbar />
      <div className="max-w-3xl mx-auto px-4 py-10">
        <div className="card p-10 text-center text-slate-400">Sipariş bulunamadı.</div>
      </div>
    </>
  );

  const activeMatch = matches.find(m => m.is_active);
  const stepIdx = STEP_INDEX[order.status] ?? 0;
  const rec = recommendation ? REC_CONFIG[recommendation.action_type] : null;

  return (
    <>
      <Navbar />
      <div className="max-w-3xl mx-auto px-4 sm:px-6 py-8 space-y-5 animate-fade-in">

        {/* Breadcrumb */}
        <button onClick={() => router.push("/dashboard")} className="flex items-center gap-1.5 text-sm text-slate-500 hover:text-blue-600 transition-colors">
          <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
            <path strokeLinecap="round" strokeLinejoin="round" d="M15 19l-7-7 7-7" />
          </svg>
          Dashboard
        </button>

        {/* Title + flow indicator */}
        <div className="card p-5">
          <div className="flex items-start justify-between gap-3 mb-5">
            <div className="min-w-0">
              <p className="text-xs text-slate-400 mb-1">Sipariş #{order.id}</p>
              <h1 className="text-base font-bold text-slate-900 leading-snug line-clamp-2">
                {order.product_title_raw || "Ürün adı bilinmiyor"}
              </h1>
            </div>
            {order.merchant && (
              <span className="badge bg-slate-100 text-slate-600 border border-slate-200 shrink-0">{order.merchant}</span>
            )}
          </div>

          {/* Flow steps */}
          <div className="flex items-center gap-1">
            {FLOW.map((s, i) => {
              const done = i < stepIdx;
              const active = i === stepIdx;
              return (
                <div key={s.key} className="flex items-center gap-1 flex-1 min-w-0">
                  <div className={`flex items-center gap-1.5 shrink-0 rounded-full px-2.5 py-1 text-xs font-semibold transition-all ${
                    done   ? "bg-emerald-100 text-emerald-700" :
                    active ? "bg-blue-600 text-white shadow-sm" :
                             "bg-slate-100 text-slate-400"
                  }`}>
                    {done && <svg className="w-3 h-3" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={3}><path strokeLinecap="round" strokeLinejoin="round" d="M5 13l4 4L19 7" /></svg>}
                    {s.label}
                  </div>
                  {i < FLOW.length - 1 && (
                    <div className={`flex-1 h-px ${done ? "bg-emerald-300" : "bg-slate-200"}`} />
                  )}
                </div>
              );
            })}
          </div>
        </div>

        {/* Error */}
        {error && (
          <div className="flex items-center gap-2 text-rose-600 bg-rose-50 border border-rose-200 rounded-xl px-4 py-3 text-sm">
            <svg className="w-4 h-4 shrink-0" fill="currentColor" viewBox="0 0 20 20"><path fillRule="evenodd" d="M10 18a8 8 0 100-16 8 8 0 000 16zM8.707 7.293a1 1 0 00-1.414 1.414L8.586 10l-1.293 1.293a1 1 0 101.414 1.414L10 11.414l1.293 1.293a1 1 0 001.414-1.414L11.414 10l1.293-1.293a1 1 0 00-1.414-1.414L10 8.586 8.707 7.293z" clipRule="evenodd" /></svg>
            {error}
          </div>
        )}

        {/* Recommendation */}
        {rec && recommendation && (
          <div className={`border rounded-2xl p-5 ${rec.style}`}>
            <div className="flex items-center gap-2 mb-2">
              <span className="text-xl">{rec.icon}</span>
              <span className="font-bold text-sm">{rec.label}</span>
              {recommendation.estimated_savings && (
                <span className="ml-auto text-sm font-bold">
                  {Number(recommendation.estimated_savings).toLocaleString("tr-TR")} ₺ tasarruf
                </span>
              )}
            </div>
            <p className="text-sm leading-relaxed">{recommendation.recommended_text}</p>
            {recommendation.target_url && (
              <a href={recommendation.target_url} target="_blank" rel="noopener noreferrer"
                className="inline-flex items-center gap-1 text-xs font-semibold mt-3 underline">
                Ürün sayfasına git
                <svg className="w-3 h-3" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}><path strokeLinecap="round" strokeLinejoin="round" d="M10 6H6a2 2 0 00-2 2v10a2 2 0 002 2h10a2 2 0 002-2v-4M14 4h6m0 0v6m0-6L10 14" /></svg>
              </a>
            )}
          </div>
        )}

        {/* Order info */}
        <SectionCard
          title="Sipariş Bilgileri"
          action={
            order.status === "pending_verification" && !editMode
              ? <button onClick={() => { setEditMode(true); setForm({...order}); }} className="text-xs font-semibold text-blue-600 hover:underline">Düzenle</button>
              : undefined
          }
        >
          {editMode ? (
            <div className="pt-2 space-y-3">
              {([
                ["merchant",          "Mağaza",       "text"],
                ["product_title_raw", "Ürün Adı",     "text"],
                ["brand",             "Marka",        "text"],
                ["model",             "Model",        "text"],
                ["variant",           "Varyant",      "text"],
                ["seller_name",       "Satıcı",       "text"],
                ["purchase_price",    "Fiyat",        "number"],
                ["currency",          "Para Birimi",  "text"],
                ["purchased_at",      "Satın Alım",   "date"],
                ["return_deadline",   "İade Son Tarihi", "date"],
              ] as [keyof Order, string, string][]).map(([field, label, type]) => (
                <div key={field}>
                  <label className="label">{label}</label>
                  <input
                    type={type}
                    value={(form[field] as string) ?? ""}
                    onChange={(e) => setForm(p => ({...p, [field]: e.target.value || undefined}))}
                    className="input"
                  />
                </div>
              ))}
              <div className="flex gap-2 pt-2">
                <button onClick={handleVerify} disabled={saving} className="btn-primary flex items-center gap-2">
                  {saving && <svg className="animate-spin w-3.5 h-3.5" viewBox="0 0 24 24" fill="none"><circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4"/><path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4z"/></svg>}
                  Doğrula ve Kaydet
                </button>
                <button onClick={() => { setEditMode(false); setForm({}); }} className="btn-secondary">İptal</button>
              </div>
            </div>
          ) : (
            <div className="pt-1">
              <InfoRow label="Mağaza"       value={order.merchant} />
              <InfoRow label="Sipariş No"   value={order.merchant_order_no} mono />
              <InfoRow label="Ürün"         value={order.product_title_raw} />
              <InfoRow label="Marka"        value={order.brand} />
              <InfoRow label="Model"        value={order.model} />
              <InfoRow label="Varyant"      value={order.variant} />
              <InfoRow label="SKU"          value={order.sku} mono />
              <InfoRow label="Satıcı"       value={order.seller_name} />
              <InfoRow label="Fiyat"        value={order.purchase_price ? `${Number(order.purchase_price).toLocaleString("tr-TR")} ${order.currency}` : null} />
              <InfoRow label="Satın Alım"   value={order.purchased_at} />
              <InfoRow label="İade Son"     value={order.return_deadline} />
              <InfoRow label="AI Güven"     value={order.parse_confidence ? `${Math.round(Number(order.parse_confidence) * 100)}%` : null} />
            </div>
          )}
        </SectionCard>

        {/* Match */}
        <SectionCard title="Ürün Eşleştirme">
          <div className="pt-1">
            {activeMatch ? (
              <>
                <InfoRow label="Başlık"  value={activeMatch.canonical_title} />
                <InfoRow label="Güven"   value={activeMatch.match_confidence ? `${Math.round(Number(activeMatch.match_confidence) * 100)}%` : null} />
                <InfoRow label="Satıcı"  value={activeMatch.seller_name} />
                {activeMatch.matched_url && (
                  <div className="flex items-start justify-between gap-4 py-2.5">
                    <span className="text-xs text-slate-400 shrink-0 pt-0.5">URL</span>
                    <a href={activeMatch.matched_url} target="_blank" rel="noopener noreferrer"
                      className="text-xs text-blue-600 font-medium hover:underline break-all text-right">
                      {activeMatch.matched_url}
                    </a>
                  </div>
                )}
                <div className="flex gap-2 pt-2 flex-wrap">
                  <span className={`badge border ${activeMatch.same_variant_verified ? "bg-emerald-50 border-emerald-200 text-emerald-700" : "bg-slate-100 border-slate-200 text-slate-500"}`}>
                    {activeMatch.same_variant_verified ? "✓" : "✗"} Varyant
                  </span>
                  <span className={`badge border ${activeMatch.same_seller_verified ? "bg-emerald-50 border-emerald-200 text-emerald-700" : "bg-slate-100 border-slate-200 text-slate-500"}`}>
                    {activeMatch.same_seller_verified ? "✓" : "✗"} Aynı Satıcı
                  </span>
                </div>
              </>
            ) : (
              <p className="text-sm text-slate-400 py-2">Henüz eşleştirme yapılmadı.</p>
            )}

            {(order.status === "verified" || order.status === "matched") && (
              <button onClick={() => action(() => matchOrder(orderId))} disabled={saving} className="btn-primary mt-3 flex items-center gap-2">
                {saving && <svg className="animate-spin w-3.5 h-3.5" viewBox="0 0 24 24" fill="none"><circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4"/><path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4z"/></svg>}
                <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}><path strokeLinecap="round" strokeLinejoin="round" d="M21 21l-6-6m2-5a7 7 0 11-14 0 7 7 0 0114 0z" /></svg>
                Eşleştir
              </button>
            )}
          </div>
        </SectionCard>

        {/* Monitoring actions */}
        {(order.status === "matched" || order.status === "monitoring") && (
          <SectionCard title="İzleme">
            <div className="pt-2 flex flex-wrap gap-3">
              {order.status === "matched" && (
                <button onClick={() => action(() => startMonitoring(orderId))} disabled={saving} className="btn-primary flex items-center gap-2">
                  <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}><path strokeLinecap="round" strokeLinejoin="round" d="M15 12a3 3 0 11-6 0 3 3 0 016 0z" /><path strokeLinecap="round" strokeLinejoin="round" d="M2.458 12C3.732 7.943 7.523 5 12 5c4.478 0 8.268 2.943 9.542 7-1.274 4.057-5.064 7-9.542 7-4.477 0-8.268-2.943-9.542-7z" /></svg>
                  İzlemeyi Başlat
                </button>
              )}

              {order.status === "monitoring" && (
                <>
                  <button onClick={handlePriceCheck} disabled={saving} className="btn-primary flex items-center gap-2">
                    <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}><path strokeLinecap="round" strokeLinejoin="round" d="M4 4v5h.582m15.356 2A8.001 8.001 0 004.582 9m0 0H9m11 11v-5h-.581m0 0a8.003 8.003 0 01-15.357-2m15.357 2H15" /></svg>
                    {saving ? "Kontrol ediliyor..." : "Fiyat Kontrol Et"}
                  </button>
                  {checkDone && (
                    <span className="flex items-center gap-1.5 text-sm text-emerald-600 font-medium">
                      <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2.5}><path strokeLinecap="round" strokeLinejoin="round" d="M5 13l4 4L19 7" /></svg>
                      Kontrol tamamlandı
                    </span>
                  )}
                  <button
                    onClick={() => action(() => stopMonitoring(orderId))}
                    className="btn-secondary flex items-center gap-2"
                  >
                    <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}><path strokeLinecap="round" strokeLinejoin="round" d="M21 12a9 9 0 11-18 0 9 9 0 0118 0z" /><path strokeLinecap="round" strokeLinejoin="round" d="M9 10a1 1 0 011-1h4a1 1 0 011 1v4a1 1 0 01-1 1h-4a1 1 0 01-1-1v-4z" /></svg>
                    İzlemeyi Durdur
                  </button>
                </>
              )}
            </div>
          </SectionCard>
        )}
      </div>
    </>
  );
}
