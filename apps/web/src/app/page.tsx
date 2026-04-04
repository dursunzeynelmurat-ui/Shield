"use client";
import { useEffect, useState, useCallback } from "react";
import { useRouter } from "next/navigation";
import Link from "next/link";
import Navbar from "@/components/Navbar";
import { isAuthenticated } from "@/lib/auth";
import { getDashboard, getDeals, getDiscoveryFeed, searchCatalog } from "@/lib/api";
import Onboarding from "@/components/Onboarding";
import type { DashboardCard } from "@/types";

interface Deal {
  id: number;
  merchant: string;
  title: string;
  code?: string;
  discount_type?: string;
  discount_value?: number;
  url?: string;
  expires_at?: string;
}

interface FeedItem {
  id: number;
  product_id: number;
  reason: string;
  score: number;
  product?: { name?: string; brand?: string; image_url?: string; category?: string };
}

interface DashboardData {
  total_orders: number;
  monitoring_count: number;
  alert_count: number;
  total_savings: number;
  currency: string;
  orders: DashboardCard[];
}

const STATUS_COLORS: Record<string, string> = {
  monitoring:  "bg-emerald-400",
  matched:     "bg-indigo-400",
  verified:    "bg-blue-400",
  pending_verification: "bg-amber-400",
  completed:   "bg-slate-400",
  failed:      "bg-rose-400",
};

const STATUS_LABELS: Record<string, string> = {
  monitoring:  "İzleniyor",
  matched:     "Eşleştirildi",
  verified:    "Doğrulandı",
  pending_verification: "Doğrulama Bekliyor",
  completed:   "Tamamlandı",
  failed:      "Başarısız",
};

function fmt(n: number, currency = "TRY") {
  return new Intl.NumberFormat("tr-TR", { style: "currency", currency }).format(n);
}

function StatCard({ label, value, sub, color }: { label: string; value: string; sub?: string; color: string }) {
  return (
    <div className="bg-white dark:bg-slate-900 rounded-2xl border border-slate-100 dark:border-slate-800 shadow-sm p-5">
      <p className="text-xs font-semibold text-slate-400 uppercase tracking-widest mb-1">{label}</p>
      <p className={`text-2xl font-extrabold ${color}`}>{value}</p>
      {sub && <p className="text-xs text-slate-400 mt-0.5">{sub}</p>}
    </div>
  );
}

export default function Home() {
  const router = useRouter();
  const [authed, setAuthed] = useState(false);
  const [dashboard, setDashboard] = useState<DashboardData | null>(null);
  const [deals, setDeals] = useState<Deal[]>([]);
  const [feed, setFeed] = useState<FeedItem[]>([]);
  const [searchQ, setSearchQ] = useState("");
  const [searchResults, setSearchResults] = useState<{ id: number; name: string; brand?: string }[]>([]);
  const [searching, setSearching] = useState(false);

  useEffect(() => {
    if (!isAuthenticated()) { router.replace("/login"); return; }
    setAuthed(true);
    getDashboard().then(setDashboard).catch(() => {});
    getDeals({ page: 1, page_size: 4 }).then((d) => setDeals(d.items)).catch(() => {});
    getDiscoveryFeed(1).then((d) => setFeed(d.items)).catch(() => {});
  }, [router]);

  const handleSearch = useCallback(async () => {
    if (!searchQ.trim()) return;
    setSearching(true);
    try {
      const data = await searchCatalog({ q: searchQ, page: 1, page_size: 5 });
      setSearchResults(data.items);
    } catch { /* noop */ }
    finally { setSearching(false); }
  }, [searchQ]);

  if (!authed) return null;

  const stats = dashboard
    ? [
        { label: "Sipariş", value: String(dashboard.total_orders), color: "text-slate-800 dark:text-white" },
        { label: "İzlenen", value: String(dashboard.monitoring_count), sub: "aktif izleme", color: "text-emerald-600 dark:text-emerald-400" },
        { label: "Uyarı", value: String(dashboard.alert_count), sub: "bekleyen", color: "text-amber-600 dark:text-amber-400" },
        { label: "Tasarruf", value: fmt(dashboard.total_savings || 0, dashboard.currency), sub: "toplam", color: "text-blue-600 dark:text-blue-400" },
      ]
    : [];

  return (
    <div className="min-h-screen bg-slate-50 dark:bg-slate-950">
      <Onboarding />
      <Navbar />

      <main className="max-w-6xl mx-auto px-4 py-8 space-y-10">

        {/* ── SEARCH ── */}
        <section>
          <div className="bg-gradient-to-br from-blue-600 to-blue-800 rounded-2xl px-6 py-8 text-white">
            <h1 className="text-2xl font-bold mb-1">Fiyat Kalkanı</h1>
            <p className="text-blue-200 text-sm mb-5">Ürün fiyatlarını karşılaştır, tasarrufu yakala.</p>
            <div className="flex gap-2">
              <input
                type="text"
                placeholder="Ürün, marka veya model ara..."
                value={searchQ}
                onChange={(e) => setSearchQ(e.target.value)}
                onKeyDown={(e) => e.key === "Enter" && handleSearch()}
                className="flex-1 px-4 py-2.5 rounded-xl bg-white/10 border border-white/20 placeholder-blue-300 text-white text-sm focus:outline-none focus:bg-white/20"
              />
              <button onClick={handleSearch} className="bg-white text-blue-700 font-semibold text-sm px-5 py-2.5 rounded-xl hover:bg-blue-50 transition-colors">
                {searching ? "…" : "Ara"}
              </button>
            </div>
            {searchResults.length > 0 && (
              <div className="mt-3 bg-white rounded-xl overflow-hidden shadow-lg">
                {searchResults.map((r) => (
                  <Link key={r.id} href={`/compare/${r.id}`} className="flex items-center gap-3 px-4 py-3 hover:bg-slate-50 border-b border-slate-50 last:border-0">
                    <span className="text-sm font-medium text-slate-800 flex-1 truncate">{r.name}</span>
                    {r.brand && <span className="text-xs text-slate-400 shrink-0">{r.brand}</span>}
                  </Link>
                ))}
                <Link href={`/compare?q=${encodeURIComponent(searchQ)}`} className="block px-4 py-2.5 text-xs text-center text-blue-600 hover:bg-blue-50">
                  Tüm sonuçları gör →
                </Link>
              </div>
            )}
          </div>
        </section>

        {/* ── STATS ── */}
        {stats.length > 0 && (
          <section>
            <p className="section-title">Özet</p>
            <div className="grid grid-cols-2 lg:grid-cols-4 gap-4">
              {stats.map((s) => <StatCard key={s.label} {...s} />)}
            </div>
          </section>
        )}

        {/* ── ACTION CARDS ── */}
        <section>
          <p className="section-title">Hızlı Eylemler</p>
          <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
            {[
              { href: "/upload", icon: "M7 16a4 4 0 01-.88-7.903A5 5 0 1115.9 6L16 6a5 5 0 011 9.9M15 13l-3-3m0 0l-3 3m3-3v12", label: "Sipariş Ekle", desc: "Makbuz yükle, takibi başlat", color: "text-blue-600", bg: "bg-blue-50 dark:bg-blue-950" },
              { href: "/compare", icon: "M3 6l3 1m0 0l-3 9a5.002 5.002 0 006.001 0M6 7l3 9M6 7l6-2m6 2l3-1m-3 1l-3 9a5.002 5.002 0 006.001 0M18 7l3 9m-3-9l-6-2m0-2v2m0 16V5m0 16H9m3 0h3", label: "Karşılaştır", desc: "Birden fazla mağaza fiyatı", color: "text-indigo-600", bg: "bg-indigo-50 dark:bg-indigo-950" },
              { href: "/deals", icon: "M7 7h.01M7 3h5c.512 0 1.024.195 1.414.586l7 7a2 2 0 010 2.828l-7 7a2 2 0 01-2.828 0l-7-7A1.994 1.994 0 013 12V7a4 4 0 014-4z", label: "Fırsatlar", desc: "Aktif kupon ve indirimler", color: "text-emerald-600", bg: "bg-emerald-50 dark:bg-emerald-950" },
              { href: "/alerts", icon: "M15 17h5l-1.405-1.405A2.032 2.032 0 0118 14.158V11a6.002 6.002 0 00-4-5.659V5a2 2 0 10-4 0v.341C7.67 6.165 6 8.388 6 11v3.159c0 .538-.214 1.055-.595 1.436L4 17h5m6 0v1a3 3 0 11-6 0v-1m6 0H9", label: "Uyarılar", desc: "Fiyat düşüşü bildirimleri", color: "text-amber-600", bg: "bg-amber-50 dark:bg-amber-950" },
            ].map(({ href, icon, label, desc, color, bg }) => (
              <Link key={href} href={href} className="bg-white dark:bg-slate-900 rounded-2xl border border-slate-100 dark:border-slate-800 shadow-sm hover:shadow-md hover:border-blue-100 dark:hover:border-blue-900 transition-all p-5 group">
                <div className={`w-10 h-10 rounded-xl ${bg} flex items-center justify-center mb-3`}>
                  <svg className={`w-5 h-5 ${color}`} fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
                    <path strokeLinecap="round" strokeLinejoin="round" d={icon} />
                  </svg>
                </div>
                <p className="font-semibold text-slate-800 dark:text-slate-100 text-sm group-hover:text-blue-600 dark:group-hover:text-blue-400">{label}</p>
                <p className="text-xs text-slate-400 mt-0.5">{desc}</p>
              </Link>
            ))}
          </div>
        </section>

        {/* ── RECENT ORDERS ── */}
        {dashboard && dashboard.orders.length > 0 && (
          <section>
            <div className="flex items-center justify-between mb-4">
              <p className="section-title mb-0">Son Siparişler</p>
              <Link href="/dashboard" className="text-xs text-blue-600 dark:text-blue-400 hover:underline">Tümü →</Link>
            </div>
            <div className="space-y-3">
              {dashboard.orders.slice(0, 4).map((order) => (
                <Link key={order.id} href={`/orders/${order.id}`}
                  className="flex items-center gap-4 bg-white dark:bg-slate-900 rounded-2xl border border-slate-100 dark:border-slate-800 px-5 py-4 hover:shadow-sm transition-all">
                  <div className={`w-2 h-2 rounded-full shrink-0 ${STATUS_COLORS[order.status] ?? "bg-slate-400"}`} />
                  <div className="flex-1 min-w-0">
                    <p className="text-sm font-medium text-slate-800 dark:text-slate-100 truncate">{order.product_name}</p>
                    <p className="text-xs text-slate-400">{order.merchant_name}</p>
                  </div>
                  <span className="text-xs px-2.5 py-1 rounded-full border bg-slate-50 dark:bg-slate-800 text-slate-600 dark:text-slate-400 border-slate-200 dark:border-slate-700 shrink-0">
                    {STATUS_LABELS[order.status] ?? order.status}
                  </span>
                </Link>
              ))}
            </div>
          </section>
        )}

        {/* ── DEALS PREVIEW ── */}
        {deals.length > 0 && (
          <section>
            <div className="flex items-center justify-between mb-4">
              <p className="section-title mb-0">Öne Çıkan Fırsatlar</p>
              <Link href="/deals" className="text-xs text-blue-600 dark:text-blue-400 hover:underline">Tümü →</Link>
            </div>
            <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
              {deals.map((deal) => (
                <div key={deal.id} className="bg-white dark:bg-slate-900 rounded-2xl border border-slate-100 dark:border-slate-800 shadow-sm p-4">
                  <div className="flex items-start justify-between gap-2 mb-2">
                    <span className="badge bg-blue-50 text-blue-700 dark:bg-blue-950 dark:text-blue-300 text-xs">{deal.merchant}</span>
                    {deal.discount_value != null && (
                      <span className="text-base font-extrabold text-emerald-600 dark:text-emerald-400 shrink-0">
                        {deal.discount_type === "percentage" ? `%${deal.discount_value}` : `${deal.discount_value}₺`}
                      </span>
                    )}
                  </div>
                  <p className="text-xs font-medium text-slate-700 dark:text-slate-300 line-clamp-2 mb-3">{deal.title}</p>
                  {deal.code && (
                    <div className="font-mono text-xs font-bold tracking-widest bg-slate-50 dark:bg-slate-800 text-slate-700 dark:text-slate-200 px-3 py-1.5 rounded-lg border border-dashed border-slate-200 dark:border-slate-700 text-center">
                      {deal.code}
                    </div>
                  )}
                </div>
              ))}
            </div>
          </section>
        )}

        {/* ── RECOMMENDATIONS ── */}
        {feed.length > 0 && (
          <section>
            <p className="section-title">Senin İçin Önerilenler</p>
            <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-4">
              {feed.slice(0, 6).map((item) => (
                <Link key={item.id} href={`/compare/${item.product_id}`}
                  className="flex items-center gap-4 bg-white dark:bg-slate-900 rounded-2xl border border-slate-100 dark:border-slate-800 shadow-sm hover:shadow-md hover:border-blue-100 dark:hover:border-blue-900 transition-all p-4">
                  {item.product?.image_url ? (
                    <img src={item.product.image_url} alt={item.product.name} className="w-14 h-14 object-contain rounded-lg bg-slate-50 dark:bg-slate-800 shrink-0" />
                  ) : (
                    <div className="w-14 h-14 rounded-lg bg-slate-50 dark:bg-slate-800 shrink-0 flex items-center justify-center">
                      <svg className="w-6 h-6 text-slate-300 dark:text-slate-600" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1} d="M20 7l-8-4-8 4m16 0l-8 4m8-4v10l-8 4m0-10L4 7m8 4v10M4 7v10l8 4" />
                      </svg>
                    </div>
                  )}
                  <div className="flex-1 min-w-0">
                    <p className="text-sm font-semibold text-slate-800 dark:text-slate-100 line-clamp-2 leading-snug">{item.product?.name ?? `Ürün #${item.product_id}`}</p>
                    {item.product?.brand && <p className="text-xs text-slate-400 mt-0.5">{item.product.brand}</p>}
                  </div>
                </Link>
              ))}
            </div>
          </section>
        )}

      </main>
    </div>
  );
}
