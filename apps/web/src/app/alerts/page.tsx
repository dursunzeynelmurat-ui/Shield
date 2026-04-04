"use client";
import { useEffect, useState } from "react";
import Link from "next/link";
import Navbar from "@/components/Navbar";
import { getAlerts, updateAlertStatus } from "@/lib/api";
import type { Alert } from "@/types";

const STATUS_LABELS: Record<string, string> = {
  new: "Yeni", seen: "Görüldü", acted: "İşlem Yapıldı", dismissed: "Kapatıldı",
};

const TABS = ["Tümü", "Yeni", "Görüldü", "Kapatıldı"] as const;
type Tab = typeof TABS[number];

function AlertItem({ alert, onDismiss, onSeen }: {
  alert: Alert;
  onDismiss: (id: number) => void;
  onSeen: (id: number) => void;
}) {
  const isNew = alert.status === "new";
  const isDismissed = alert.status === "dismissed";

  return (
    <div
      className={`card transition-all duration-200 overflow-hidden ${
        isNew ? "border-l-4 border-l-emerald-400 shadow-card" : "opacity-60"
      }`}
      onMouseEnter={() => isNew && onSeen(alert.id)}
    >
      <div className="p-5">
        {/* Header */}
        <div className="flex items-start justify-between gap-3 mb-3">
          <div className="flex items-center gap-2 flex-wrap">
            <span className={`badge border text-xs ${
              isNew ? "bg-emerald-50 border-emerald-200 text-emerald-700" :
              isDismissed ? "bg-slate-100 border-slate-200 text-slate-400" :
              "bg-blue-50 border-blue-200 text-blue-700"
            }`}>
              {isNew && <span className="w-1.5 h-1.5 rounded-full bg-emerald-500" />}
              {STATUS_LABELS[alert.status] || alert.status}
            </span>
            {alert.alert_type === "price_drop" && (
              <span className="badge bg-slate-100 border border-slate-200 text-slate-600 text-xs">📉 Fiyat Düşüşü</span>
            )}
          </div>

          {isNew && (
            <button
              onClick={() => onDismiss(alert.id)}
              className="text-slate-300 hover:text-slate-500 transition-colors shrink-0 p-1"
              title="Kapat"
            >
              <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
                <path strokeLinecap="round" strokeLinejoin="round" d="M6 18L18 6M6 6l12 12" />
              </svg>
            </button>
          )}
        </div>

        {/* Savings amount */}
        {alert.amount_saved && (
          <div className="flex items-center gap-2 mb-3">
            <span className="text-2xl font-bold text-emerald-600">
              {Number(alert.amount_saved).toLocaleString("tr-TR")} ₺
            </span>
            <span className="text-sm text-slate-400">tasarruf fırsatı</span>
          </div>
        )}

        {/* Message */}
        <p className="text-sm text-slate-600 leading-relaxed mb-4">{alert.message}</p>

        {/* Footer */}
        <div className="flex items-center justify-between">
          <p className="text-xs text-slate-400">
            {new Date(alert.created_at).toLocaleDateString("tr-TR", {
              day: "numeric", month: "long", hour: "2-digit", minute: "2-digit",
            })}
          </p>
          <Link
            href={`/orders/${alert.order_id}`}
            className="flex items-center gap-1 text-xs font-semibold text-blue-600 hover:underline"
          >
            Siparişi Gör
            <svg className="w-3.5 h-3.5" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2.5}>
              <path strokeLinecap="round" strokeLinejoin="round" d="M9 5l7 7-7 7" />
            </svg>
          </Link>
        </div>
      </div>
    </div>
  );
}

export default function AlertsPage() {
  const [alerts, setAlerts] = useState<Alert[]>([]);
  const [loading, setLoading] = useState(true);
  const [tab, setTab] = useState<Tab>("Tümü");

  useEffect(() => {
    getAlerts().then(setAlerts).finally(() => setLoading(false));
  }, []);

  const handleDismiss = async (id: number) => {
    const updated = await updateAlertStatus(id, "dismissed");
    setAlerts(prev => prev.map(a => a.id === id ? updated : a));
  };

  const handleSeen = async (id: number) => {
    const a = alerts.find(x => x.id === id);
    if (a?.status !== "new") return;
    const updated = await updateAlertStatus(id, "seen");
    setAlerts(prev => prev.map(x => x.id === id ? updated : x));
  };

  const filtered = alerts.filter(a => {
    if (tab === "Tümü")     return true;
    if (tab === "Yeni")     return a.status === "new";
    if (tab === "Görüldü")  return a.status === "seen";
    if (tab === "Kapatıldı") return a.status === "dismissed";
    return true;
  });

  const newCount = alerts.filter(a => a.status === "new").length;

  return (
    <>
      <Navbar />
      <div className="max-w-3xl mx-auto px-4 sm:px-6 py-8 animate-fade-in">

        {/* Header */}
        <div className="flex items-center justify-between mb-6">
          <div>
            <h1 className="text-2xl font-bold text-slate-900 flex items-center gap-2">
              Uyarılar
              {newCount > 0 && (
                <span className="w-6 h-6 rounded-full bg-rose-500 text-white text-xs font-bold flex items-center justify-center">
                  {newCount}
                </span>
              )}
            </h1>
            <p className="text-slate-500 text-sm mt-0.5">Fiyat düşüşleri ve önemli bildirimler.</p>
          </div>
        </div>

        {/* Tabs */}
        <div className="flex gap-1 bg-slate-100 p-1 rounded-xl mb-6 w-fit">
          {TABS.map(t => (
            <button
              key={t}
              onClick={() => setTab(t)}
              className={`px-4 py-1.5 rounded-lg text-sm font-medium transition-all ${
                tab === t ? "bg-white text-slate-900 shadow-sm" : "text-slate-500 hover:text-slate-700"
              }`}
            >
              {t}
            </button>
          ))}
        </div>

        {/* Content */}
        {loading ? (
          <div className="space-y-3">
            {[1, 2].map(i => (
              <div key={i} className="card p-5 space-y-3">
                <div className="skeleton h-4 w-24" />
                <div className="skeleton h-6 w-32" />
                <div className="skeleton h-3 w-full" />
              </div>
            ))}
          </div>
        ) : filtered.length === 0 ? (
          <div className="card p-16 text-center">
            <div className="w-16 h-16 rounded-2xl bg-slate-100 flex items-center justify-center mx-auto mb-4">
              <svg className="w-8 h-8 text-slate-300" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={1.5}>
                <path strokeLinecap="round" strokeLinejoin="round" d="M15 17h5l-1.405-1.405A2.032 2.032 0 0118 14.158V11a6.002 6.002 0 00-4-5.659V5a2 2 0 10-4 0v.341C7.67 6.165 6 8.388 6 11v3.159c0 .538-.214 1.055-.595 1.436L4 17h5m6 0v1a3 3 0 11-6 0v-1m6 0H9" />
              </svg>
            </div>
            <p className="text-slate-500 font-medium">
              {tab === "Tümü" ? "Henüz uyarı yok." : `"${tab}" kategorisinde uyarı yok.`}
            </p>
          </div>
        ) : (
          <div className="space-y-3">
            {filtered.map(alert => (
              <AlertItem
                key={alert.id}
                alert={alert}
                onDismiss={handleDismiss}
                onSeen={handleSeen}
              />
            ))}
          </div>
        )}
      </div>
    </>
  );
}
