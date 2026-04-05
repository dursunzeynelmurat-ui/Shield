"use client";
import { useEffect, useState } from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import Navbar from "@/components/Navbar";
import { isAuthenticated } from "@/lib/auth";
import { getWatchlist, removeFromWatchlist } from "@/lib/api";

interface WatchlistEntry {
  id: number;
  product_id: number;
  target_price: number | null;
  created_at: string;
  product: {
    name: string | null;
    brand: string | null;
    image_url: string | null;
    category: string | null;
    lowest_price: number | null;
  } | null;
}

function fmt(val: number | null, currency = "TRY") {
  if (val == null) return "—";
  return new Intl.NumberFormat("tr-TR", { style: "currency", currency }).format(val);
}

function WatchlistCard({
  entry,
  onRemove,
}: {
  entry: WatchlistEntry;
  onRemove: (productId: number) => void;
}) {
  const [removing, setRemoving] = useState(false);

  const handleRemove = async () => {
    setRemoving(true);
    try {
      await removeFromWatchlist(entry.product_id);
      onRemove(entry.product_id);
    } catch {
      setRemoving(false);
    }
  };

  const p = entry.product;
  const belowTarget =
    entry.target_price != null &&
    p?.lowest_price != null &&
    p.lowest_price <= entry.target_price;

  return (
    <div className={`bg-white dark:bg-slate-900 rounded-2xl border shadow-sm p-5 flex gap-4 transition-all ${belowTarget ? "border-emerald-200 dark:border-emerald-800 savings-glow" : "border-slate-100 dark:border-slate-800"}`}>
      {/* Image */}
      {p?.image_url ? (
        <img
          src={p.image_url}
          alt={p.name ?? ""}
          className="w-20 h-20 object-contain rounded-xl bg-slate-50 dark:bg-slate-800 shrink-0"
        />
      ) : (
        <div className="w-20 h-20 rounded-xl bg-slate-50 dark:bg-slate-800 shrink-0 flex items-center justify-center">
          <svg className="w-8 h-8 text-slate-300 dark:text-slate-600" fill="none" viewBox="0 0 24 24" stroke="currentColor">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1} d="M20 7l-8-4-8 4m16 0l-8 4m8-4v10l-8 4m0-10L4 7m8 4v10M4 7v10l8 4" />
          </svg>
        </div>
      )}

      {/* Content */}
      <div className="flex-1 min-w-0">
        <Link href={`/compare/${entry.product_id}`} className="text-sm font-semibold text-slate-800 dark:text-slate-100 hover:text-blue-600 dark:hover:text-blue-400 line-clamp-2 leading-snug">
          {p?.name ?? `Ürün #${entry.product_id}`}
        </Link>
        <div className="flex flex-wrap gap-1.5 mt-1.5 mb-3">
          {p?.brand && <span className="badge bg-blue-50 text-blue-700 dark:bg-blue-950 dark:text-blue-300">{p.brand}</span>}
          {p?.category && <span className="badge bg-slate-50 text-slate-600 dark:bg-slate-800 dark:text-slate-400">{p.category}</span>}
        </div>

        <div className="flex items-end gap-6 flex-wrap">
          <div>
            <p className="text-xs text-slate-400 mb-0.5">Güncel en düşük</p>
            <p className={`text-lg font-bold ${belowTarget ? "text-emerald-600 dark:text-emerald-400" : "text-slate-800 dark:text-slate-100"}`}>
              {fmt(p?.lowest_price ?? null)}
            </p>
          </div>
          {entry.target_price != null && (
            <div>
              <p className="text-xs text-slate-400 mb-0.5">Hedef fiyat</p>
              <p className="text-sm font-semibold text-slate-600 dark:text-slate-400">{fmt(entry.target_price)}</p>
            </div>
          )}
          {belowTarget && (
            <span className="badge bg-emerald-50 text-emerald-700 dark:bg-emerald-950 dark:text-emerald-300 text-xs">
              Hedef fiyata ulaştı!
            </span>
          )}
        </div>
      </div>

      {/* Actions */}
      <div className="flex flex-col items-end justify-between shrink-0 gap-2">
        <button
          onClick={handleRemove}
          disabled={removing}
          className="p-2 rounded-lg text-slate-400 hover:text-rose-500 hover:bg-rose-50 dark:hover:bg-rose-950 transition-all disabled:opacity-40"
          title="Takipten çıkar"
        >
          <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
            <path strokeLinecap="round" strokeLinejoin="round" d="M4.318 6.318a4.5 4.5 0 000 6.364L12 20.364l7.682-7.682a4.5 4.5 0 00-6.364-6.364L12 7.636l-1.318-1.318a4.5 4.5 0 00-6.364 0z" />
          </svg>
        </button>
        <Link href={`/compare/${entry.product_id}`} className="btn-secondary px-3 py-1.5 text-xs">
          Karşılaştır
        </Link>
      </div>
    </div>
  );
}

export default function WatchlistPage() {
  const router = useRouter();
  const [entries, setEntries] = useState<WatchlistEntry[]>([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    if (!isAuthenticated()) { router.replace("/login"); return; }
    getWatchlist()
      .then(setEntries)
      .catch(() => {})
      .finally(() => setLoading(false));
  }, [router]);

  const handleRemove = (productId: number) => {
    setEntries((prev) => prev.filter((e) => e.product_id !== productId));
  };

  const atTargetCount = entries.filter(
    (e) => e.target_price != null && e.product?.lowest_price != null && e.product.lowest_price <= e.target_price
  ).length;

  return (
    <div className="min-h-screen bg-slate-50 dark:bg-slate-950">
      <Navbar />
      <main className="max-w-3xl mx-auto px-4 py-8">
        <div className="mb-8 flex items-end justify-between">
          <div>
            <h1 className="text-2xl font-bold text-slate-900 dark:text-white mb-1">Takip Listesi</h1>
            <p className="text-sm text-slate-500 dark:text-slate-400">
              Hedef fiyata ulaşan ürünlerde bildirim alırsın.
            </p>
          </div>
          {atTargetCount > 0 && (
            <span className="badge bg-emerald-50 text-emerald-700 dark:bg-emerald-950 dark:text-emerald-300">
              {atTargetCount} ürün hedefte
            </span>
          )}
        </div>

        {loading && (
          <div className="space-y-4">
            {Array.from({ length: 3 }).map((_, i) => (
              <div key={i} className="bg-white dark:bg-slate-900 rounded-2xl border border-slate-100 dark:border-slate-800 p-5 flex gap-4">
                <div className="skeleton w-20 h-20 shrink-0 rounded-xl" />
                <div className="flex-1 space-y-3">
                  <div className="skeleton h-4 w-3/4" />
                  <div className="skeleton h-4 w-1/2" />
                  <div className="skeleton h-6 w-1/3" />
                </div>
              </div>
            ))}
          </div>
        )}

        {!loading && entries.length === 0 && (
          <div className="text-center py-20 text-slate-400 dark:text-slate-600">
            <svg className="w-14 h-14 mx-auto mb-4 opacity-30" fill="none" viewBox="0 0 24 24" stroke="currentColor">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1} d="M4.318 6.318a4.5 4.5 0 000 6.364L12 20.364l7.682-7.682a4.5 4.5 0 00-6.364-6.364L12 7.636l-1.318-1.318a4.5 4.5 0 00-6.364 0z" />
            </svg>
            <p className="font-medium text-lg">Takip listesi boş</p>
            <p className="text-sm mt-1 mb-6">Ürün sayfasında "Takip Et" butonuna basarak listeye ekleyebilirsin.</p>
            <Link href="/compare" className="btn-primary">Ürün Ara</Link>
          </div>
        )}

        {!loading && entries.length > 0 && (
          <div className="space-y-4">
            {entries.map((entry) => (
              <WatchlistCard key={entry.id} entry={entry} onRemove={handleRemove} />
            ))}
          </div>
        )}
      </main>
    </div>
  );
}
