"use client";
import { useEffect, useState, useCallback } from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import Navbar from "@/components/Navbar";
import { isAuthenticated } from "@/lib/auth";
import { getDiscoveryFeed, postInterestEvent } from "@/lib/api";

interface FeedItem {
  id: number;
  product_id: number;
  reason: string;
  score: number;
  product: {
    name?: string;
    brand?: string;
    image_url?: string;
    category?: string;
  } | null;
}

const REASON_LABELS: Record<string, string> = {
  purchased_product: "Satın aldığın ürüne benzer",
  catalog_match:     "Senin için seçildi",
  interest_match:    "İlgi alanına göre",
  price_drop:        "Fiyat düşüşü var",
  trending:          "Popüler",
};

function FeedCard({ item, onView }: { item: FeedItem; onView: (id: number) => void }) {
  const p = item.product;
  return (
    <Link
      href={`/compare/${item.product_id}`}
      onClick={() => onView(item.product_id)}
      className="bg-white dark:bg-slate-900 rounded-2xl border border-slate-100 dark:border-slate-800 shadow-sm hover:shadow-md hover:border-blue-100 dark:hover:border-blue-900 transition-all flex flex-col"
    >
      {/* Image */}
      {p?.image_url ? (
        <img
          src={p.image_url}
          alt={p.name ?? ""}
          className="w-full h-36 object-contain rounded-t-2xl bg-slate-50 dark:bg-slate-800"
        />
      ) : (
        <div className="w-full h-36 rounded-t-2xl bg-slate-50 dark:bg-slate-800 flex items-center justify-center">
          <svg className="w-10 h-10 text-slate-300 dark:text-slate-600" fill="none" viewBox="0 0 24 24" stroke="currentColor">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1} d="M20 7l-8-4-8 4m16 0l-8 4m8-4v10l-8 4m0-10L4 7m8 4v10M4 7v10l8 4" />
          </svg>
        </div>
      )}

      {/* Content */}
      <div className="p-4 flex-1 flex flex-col gap-2">
        <p className="text-sm font-semibold text-slate-800 dark:text-slate-100 line-clamp-2 leading-snug flex-1">
          {p?.name ?? `Ürün #${item.product_id}`}
        </p>
        <div className="flex items-center justify-between gap-2">
          {p?.brand && (
            <span className="badge bg-blue-50 text-blue-700 dark:bg-blue-950 dark:text-blue-300 text-xs">{p.brand}</span>
          )}
          <span className="text-xs text-slate-400 ml-auto">
            {REASON_LABELS[item.reason] ?? item.reason}
          </span>
        </div>
      </div>
    </Link>
  );
}

export default function ForYouPage() {
  const router = useRouter();
  const [items, setItems] = useState<FeedItem[]>([]);
  const [loading, setLoading] = useState(true);
  const [page, setPage] = useState(1);
  const [hasMore, setHasMore] = useState(true);

  useEffect(() => {
    if (!isAuthenticated()) { router.replace("/login"); return; }
    loadPage(1);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [router]);

  const loadPage = useCallback(async (p: number) => {
    setLoading(true);
    try {
      const data = await getDiscoveryFeed(p);
      if (p === 1) {
        setItems(data.items ?? []);
      } else {
        setItems((prev) => [...prev, ...(data.items ?? [])]);
      }
      setHasMore((data.items ?? []).length >= (data.page_size ?? 20));
      setPage(p);
    } catch {
      // ignore
    } finally {
      setLoading(false);
    }
  }, []);

  const handleView = async (productId: number) => {
    try {
      await postInterestEvent({ event_type: "view", product_id: productId });
    } catch { /* non-blocking */ }
  };

  return (
    <div className="min-h-screen bg-slate-50 dark:bg-slate-950">
      <Navbar />
      <main className="max-w-5xl mx-auto px-4 py-8">
        <div className="mb-8">
          <h1 className="text-2xl font-bold text-slate-900 dark:text-white mb-1">Senin İçin</h1>
          <p className="text-sm text-slate-500 dark:text-slate-400">
            Alışveriş geçmişine ve ilgi alanlarına göre kişiselleştirilmiş öneriler.
          </p>
        </div>

        {/* Skeleton */}
        {loading && items.length === 0 && (
          <div className="grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-4 gap-4">
            {Array.from({ length: 8 }).map((_, i) => (
              <div key={i} className="bg-white dark:bg-slate-900 rounded-2xl border border-slate-100 dark:border-slate-800 overflow-hidden">
                <div className="skeleton h-36 w-full" />
                <div className="p-4 space-y-2">
                  <div className="skeleton h-4 w-3/4" />
                  <div className="skeleton h-3 w-1/2" />
                </div>
              </div>
            ))}
          </div>
        )}

        {!loading && items.length === 0 && (
          <div className="text-center py-20 text-slate-400 dark:text-slate-600">
            <svg className="w-14 h-14 mx-auto mb-4 opacity-30" fill="none" viewBox="0 0 24 24" stroke="currentColor">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1} d="M9.663 17h4.673M12 3v1m6.364 1.636l-.707.707M21 12h-1M4 12H3m3.343-5.657l-.707-.707m2.828 9.9a5 5 0 117.072 0l-.548.547A3.374 3.374 0 0014 18.469V19a2 2 0 11-4 0v-.531c0-.895-.356-1.754-.988-2.386l-.548-.547z" />
            </svg>
            <p className="font-medium text-lg">Henüz öneri yok</p>
            <p className="text-sm mt-1 mb-6">
              Sipariş ekledikçe ve ürünleri inceledikçe sana özel öneriler oluşturulacak.
            </p>
            <div className="flex gap-3 justify-center">
              <Link href="/upload" className="btn-primary">Sipariş Ekle</Link>
              <Link href="/compare" className="btn-secondary">Ürün Ara</Link>
            </div>
          </div>
        )}

        {items.length > 0 && (
          <>
            <div className="grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-4 gap-4 mb-8">
              {items.map((item) => (
                <FeedCard key={item.id} item={item} onView={handleView} />
              ))}
            </div>

            {/* Load more */}
            {hasMore && (
              <div className="text-center">
                <button
                  onClick={() => loadPage(page + 1)}
                  disabled={loading}
                  className="btn-secondary px-8 disabled:opacity-40"
                >
                  {loading ? "Yükleniyor…" : "Daha Fazla Göster"}
                </button>
              </div>
            )}
          </>
        )}
      </main>
    </div>
  );
}
