"use client";
import { useEffect, useState } from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import Navbar from "@/components/Navbar";
import { getDashboard } from "@/lib/api";
import { isAuthenticated } from "@/lib/auth";
import type { DashboardCard } from "@/types";

const STATUS_CONFIG: Record<string, { label: string; color: string; dot: string }> = {
  pending_verification: { label: "Doğrulama Bekliyor", color: "text-amber-700 bg-amber-50 border-amber-200", dot: "bg-amber-400" },
  verified:             { label: "Doğrulandı",         color: "text-blue-700 bg-blue-50 border-blue-200",    dot: "bg-blue-400" },
  matching:             { label: "Eşleştiriliyor",     color: "text-blue-700 bg-blue-50 border-blue-200",    dot: "bg-blue-400" },
  matched:              { label: "Eşleştirildi",       color: "text-indigo-700 bg-indigo-50 border-indigo-200", dot: "bg-indigo-400" },
  monitoring:           { label: "İzleniyor",          color: "text-emerald-700 bg-emerald-50 border-emerald-200", dot: "bg-emerald-400" },
  completed:            { label: "Tamamlandı",         color: "text-slate-600 bg-slate-50 border-slate-200", dot: "bg-slate-400" },
  failed:               { label: "Başarısız",          color: "text-rose-700 bg-rose-50 border-rose-200",    dot: "bg-rose-400" },
};

function StatBar({ label, value, color }: { label: string; value: string; color: string }) {
  return (
    <div className="flex items-center justify-between py-3 border-b border-slate-100 last:border-0">
      <span className="text-sm text-slate-500">{label}</span>
      <span className={`text-sm font-semibold ${color}`}>{value}</span>
    </div>
  );
}

function OrderCard({ card }: { card: DashboardCard }) {
  const status = STATUS_CONFIG[card.status] ?? { label: card.status, color: "text-slate-600 bg-slate-50 border-slate-200", dot: "bg-slate-400" };
  const hasSavings = card.savings && Number(card.savings) > 0;
  const urgentReturn = card.remaining_return_days !== null && card.remaining_return_days <= 3;

  return (
    <Link
      href={`/orders/${card.order_id}`}
      className="card shadow-card hover:shadow-card-hover transition-all duration-200 block group overflow-hidden"
    >
      {/* Savings highlight bar */}
      {hasSavings && (
        <div className="h-1 w-full bg-green-gradient" />
      )}

      <div className="p-5">
        {/* Header row */}
        <div className="flex items-start justify-between gap-2 mb-4">
          <span className={`badge border ${status.color} text-xs`}>
            <span className={`w-1.5 h-1.5 rounded-full ${status.dot}`} />
            {status.label}
          </span>

          {card.has_alert && (
            <span className="badge bg-rose-100 text-rose-700 border border-rose-200 text-xs animate-pulse">
              🔔 Uyarı
            </span>
          )}
        </div>

        {/* Product name */}
        <p className="text-sm font-semibold text-slate-800 leading-snug line-clamp-2 mb-4 group-hover:text-blue-700 transition-colors">
          {card.product_name || <span className="text-slate-400 italic">Ürün adı bilinmiyor</span>}
        </p>

        {/* Price comparison */}
        <div className="bg-slate-50 rounded-xl p-3 mb-4 space-y-2">
          <div className="flex justify-between items-center">
            <span className="text-xs text-slate-400">Alış fiyatı</span>
            <span className="text-sm font-semibold text-slate-700">
              {card.purchase_price ? `${Number(card.purchase_price).toLocaleString("tr-TR")} ${card.currency}` : "—"}
            </span>
          </div>
          <div className="flex justify-between items-center">
            <span className="text-xs text-slate-400">Güncel fiyat</span>
            <span className={`text-sm font-semibold ${hasSavings ? "text-emerald-600" : "text-slate-700"}`}>
              {card.current_price ? `${Number(card.current_price).toLocaleString("tr-TR")} ${card.currency}` : "—"}
            </span>
          </div>
        </div>

        {/* Savings badge */}
        {hasSavings && (
          <div className="flex items-center justify-between bg-emerald-50 border border-emerald-200 rounded-xl px-3 py-2 mb-3 savings-glow">
            <div className="flex items-center gap-1.5">
              <span className="text-emerald-600 text-base">💰</span>
              <span className="text-xs font-semibold text-emerald-700">Tasarruf fırsatı!</span>
            </div>
            <span className="text-sm font-bold text-emerald-700">
              {Number(card.savings).toLocaleString("tr-TR")} {card.currency}
            </span>
          </div>
        )}

        {/* Footer */}
        <div className="flex items-center justify-between">
          {card.remaining_return_days !== null ? (
            <div className={`flex items-center gap-1 text-xs font-medium ${urgentReturn ? "text-rose-600" : "text-slate-500"}`}>
              {urgentReturn && <span>⚠️</span>}
              <span>{card.remaining_return_days === 0 ? "İade süresi doldu" : `${card.remaining_return_days} gün kaldı`}</span>
            </div>
          ) : (
            <div />
          )}
          <svg className="w-4 h-4 text-slate-300 group-hover:text-blue-500 group-hover:translate-x-0.5 transition-all" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
            <path strokeLinecap="round" strokeLinejoin="round" d="M9 5l7 7-7 7" />
          </svg>
        </div>
      </div>
    </Link>
  );
}

function SkeletonCard() {
  return (
    <div className="card p-5 space-y-3">
      <div className="skeleton h-5 w-24" />
      <div className="skeleton h-4 w-full" />
      <div className="skeleton h-4 w-3/4" />
      <div className="skeleton h-16 w-full rounded-xl" />
    </div>
  );
}

export default function DashboardPage() {
  const router = useRouter();
  const [cards, setCards] = useState<DashboardCard[]>([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    if (!isAuthenticated()) { router.push("/login"); return; }
    getDashboard().then(setCards).finally(() => setLoading(false));
  }, [router]);

  const totalSavings = cards.reduce((sum, c) => sum + (c.savings ? Number(c.savings) : 0), 0);
  const activeMonitoring = cards.filter(c => c.status === "monitoring").length;
  const newAlerts = cards.filter(c => c.has_alert).length;

  return (
    <>
      <Navbar />
      <div className="max-w-6xl mx-auto px-4 sm:px-6 py-8 animate-fade-in">
        {/* Page header */}
        <div className="flex items-center justify-between mb-6">
          <div>
            <h1 className="text-2xl font-bold text-slate-900">Dashboard</h1>
            <p className="text-slate-500 text-sm mt-0.5">Siparişlerini takip et ve tasarruf et.</p>
          </div>
          <Link href="/upload" className="btn-primary flex items-center gap-2">
            <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2.5}>
              <path strokeLinecap="round" strokeLinejoin="round" d="M12 4v16m8-8H4" />
            </svg>
            Yeni Sipariş
          </Link>
        </div>

        {/* Summary stats */}
        {!loading && cards.length > 0 && (
          <div className="grid grid-cols-3 gap-4 mb-8">
            {[
              { label: "Toplam Tasarruf", value: totalSavings > 0 ? `${totalSavings.toLocaleString("tr-TR")} ₺` : "—", accent: "text-emerald-600", bg: "bg-emerald-50 border-emerald-100", icon: "💰" },
              { label: "İzlenen Ürün",    value: `${activeMonitoring}`, accent: "text-blue-600", bg: "bg-blue-50 border-blue-100", icon: "👁" },
              { label: "Yeni Uyarı",      value: `${newAlerts}`, accent: newAlerts > 0 ? "text-rose-600" : "text-slate-500", bg: newAlerts > 0 ? "bg-rose-50 border-rose-100" : "bg-slate-50 border-slate-100", icon: "🔔" },
            ].map(({ label, value, accent, bg, icon }) => (
              <div key={label} className={`card border ${bg} p-4 flex items-center gap-3`}>
                <span className="text-2xl">{icon}</span>
                <div>
                  <p className="text-xs text-slate-500 font-medium">{label}</p>
                  <p className={`text-xl font-bold ${accent}`}>{value}</p>
                </div>
              </div>
            ))}
          </div>
        )}

        {/* Cards grid */}
        {loading ? (
          <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
            {[1, 2, 3].map(i => <SkeletonCard key={i} />)}
          </div>
        ) : cards.length === 0 ? (
          <div className="card shadow-card p-16 text-center">
            <div className="w-16 h-16 rounded-2xl bg-blue-50 flex items-center justify-center mx-auto mb-4">
              <svg className="w-8 h-8 text-blue-500" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={1.5}>
                <path strokeLinecap="round" strokeLinejoin="round" d="M9 12h6m-6 4h6m2 5H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z" />
              </svg>
            </div>
            <h3 className="text-lg font-semibold text-slate-700 mb-2">Henüz sipariş yok</h3>
            <p className="text-slate-400 text-sm mb-6 max-w-xs mx-auto">
              İlk siparişini yükle, biz seni fiyat düşüşlerinde haberdar edelim.
            </p>
            <Link href="/upload" className="btn-primary inline-flex items-center gap-2">
              <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2.5}>
                <path strokeLinecap="round" strokeLinejoin="round" d="M4 16v1a3 3 0 003 3h10a3 3 0 003-3v-1m-4-8l-4-4m0 0L8 8m4-4v12" />
              </svg>
              Sipariş Yükle
            </Link>
          </div>
        ) : (
          <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
            {cards.map(card => <OrderCard key={card.order_id} card={card} />)}
          </div>
        )}
      </div>
    </>
  );
}
