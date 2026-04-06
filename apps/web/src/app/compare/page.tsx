"use client";
import { useState, useCallback, useEffect, Suspense } from "react";
import Link from "next/link";
import { useRouter, useSearchParams } from "next/navigation";
import Navbar from "@/components/Navbar";
import { searchCatalog } from "@/lib/api";
import { isAuthenticated } from "@/lib/auth";

interface Product {
  id: number;
  name: string;
  brand?: string;
  model?: string;
  category?: string;
  image_url?: string;
}

interface SearchResult {
  total: number;
  page: number;
  page_size: number;
  items: Product[];
}

function CompareContent() {
  const router = useRouter();
  const searchParams = useSearchParams();
  const [query, setQuery] = useState(searchParams?.get("q") ?? "");
  const [category, setCategory] = useState("");
  const [results, setResults] = useState<SearchResult | null>(null);
  const [loading, setLoading] = useState(false);
  const [page, setPage] = useState(1);

  useEffect(() => {
    if (!isAuthenticated()) { router.replace("/login"); return; }
    const q = searchParams?.get("q");
    if (q) {
      setQuery(q);
      searchCatalog({ q, page: 1 })
        .then((data) => { setResults(data); setPage(1); })
        .catch(() => {});
    }
  }, [router, searchParams]); // eslint-disable-line react-hooks/exhaustive-deps

  const search = useCallback(async (p = 1) => {
    if (!query.trim() && !category.trim()) return;
    setLoading(true);
    try {
      const data = await searchCatalog({ q: query || undefined, category: category || undefined, page: p });
      setResults(data);
      setPage(p);
    } catch {
      // ignore
    } finally {
      setLoading(false);
    }
  }, [query, category]);

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    search(1);
  };

  const totalPages = results ? Math.ceil(results.total / results.page_size) : 0;

  return (
    <main className="max-w-5xl mx-auto px-4 py-8">
      <div className="mb-8">
        <h1 className="text-2xl font-bold text-slate-900 dark:text-white mb-1">Ürün Karşılaştır</h1>
        <p className="text-sm text-slate-500 dark:text-slate-400">Birden fazla mağazanın fiyatlarını karşılaştır, en uygun fırsatı bul.</p>
      </div>

      <form onSubmit={handleSubmit} className="bg-white dark:bg-slate-900 rounded-2xl border border-slate-100 dark:border-slate-800 shadow-sm p-5 mb-8">
        <div className="flex gap-3 flex-col sm:flex-row">
          <input
            type="text"
            placeholder="Ürün adı, marka veya model ara..."
            value={query}
            onChange={(e) => setQuery(e.target.value)}
            className="input flex-1"
          />
          <input
            type="text"
            placeholder="Kategori (isteğe bağlı)"
            value={category}
            onChange={(e) => setCategory(e.target.value)}
            className="input w-full sm:w-48"
          />
          <button type="submit" className="btn-primary whitespace-nowrap">
            {loading ? "Aranıyor…" : "Ara"}
          </button>
        </div>
      </form>

      {loading && (
        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-4">
          {Array.from({ length: 6 }).map((_, i) => (
            <div key={i} className="bg-white dark:bg-slate-900 rounded-2xl border border-slate-100 dark:border-slate-800 p-5">
              <div className="skeleton h-32 w-full mb-4" />
              <div className="skeleton h-4 w-3/4 mb-2" />
              <div className="skeleton h-4 w-1/2" />
            </div>
          ))}
        </div>
      )}

      {!loading && results && results.items.length === 0 && (
        <div className="text-center py-16 text-slate-400 dark:text-slate-600">
          <svg className="w-12 h-12 mx-auto mb-3 opacity-40" fill="none" viewBox="0 0 24 24" stroke="currentColor">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} d="M21 21l-6-6m2-5a7 7 0 11-14 0 7 7 0 0114 0z" />
          </svg>
          <p className="font-medium">Sonuç bulunamadı</p>
          <p className="text-sm mt-1">Farklı bir arama terimi deneyin.</p>
        </div>
      )}

      {!loading && results && results.items.length > 0 && (
        <>
          <p className="text-sm text-slate-500 dark:text-slate-400 mb-4">
            <span className="font-semibold text-slate-700 dark:text-slate-200">{results.total}</span> ürün bulundu
          </p>

          <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-4 mb-8">
            {results.items.map((product) => (
              <Link
                key={product.id}
                href={`/compare/${product.id}`}
                className="bg-white dark:bg-slate-900 rounded-2xl border border-slate-100 dark:border-slate-800 shadow-sm hover:shadow-md hover:border-blue-100 dark:hover:border-blue-900 transition-all p-5 group"
              >
                {product.image_url ? (
                  <img
                    src={product.image_url}
                    alt={product.name}
                    className="w-full h-32 object-contain mb-4 rounded-lg bg-slate-50 dark:bg-slate-800"
                  />
                ) : (
                  <div className="w-full h-32 mb-4 rounded-lg bg-slate-50 dark:bg-slate-800 flex items-center justify-center">
                    <svg className="w-10 h-10 text-slate-300 dark:text-slate-600" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1} d="M20 7l-8-4-8 4m16 0l-8 4m8-4v10l-8 4m0-10L4 7m8 4v10M4 7v10l8 4" />
                    </svg>
                  </div>
                )}
                <p className="text-sm font-semibold text-slate-800 dark:text-slate-100 group-hover:text-blue-600 dark:group-hover:text-blue-400 line-clamp-2 leading-snug mb-2">
                  {product.name}
                </p>
                <div className="flex flex-wrap gap-1.5">
                  {product.brand && (
                    <span className="badge bg-blue-50 text-blue-700 dark:bg-blue-950 dark:text-blue-300">{product.brand}</span>
                  )}
                  {product.category && (
                    <span className="badge bg-slate-50 text-slate-600 dark:bg-slate-800 dark:text-slate-400">{product.category}</span>
                  )}
                </div>
              </Link>
            ))}
          </div>

          {totalPages > 1 && (
            <div className="flex items-center justify-center gap-2">
              <button
                disabled={page <= 1}
                onClick={() => search(page - 1)}
                className="btn-secondary px-3 py-1.5 text-xs disabled:opacity-30"
              >← Önceki</button>
              <span className="text-sm text-slate-500">{page} / {totalPages}</span>
              <button
                disabled={page >= totalPages}
                onClick={() => search(page + 1)}
                className="btn-secondary px-3 py-1.5 text-xs disabled:opacity-30"
              >Sonraki →</button>
            </div>
          )}
        </>
      )}

      {!results && !loading && (
        <div className="text-center py-20 text-slate-400 dark:text-slate-600">
          <svg className="w-14 h-14 mx-auto mb-4 opacity-30" fill="none" viewBox="0 0 24 24" stroke="currentColor">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1} d="M3 6l3 1m0 0l-3 9a5.002 5.002 0 006.001 0M6 7l3 9M6 7l6-2m6 2l3-1m-3 1l-3 9a5.002 5.002 0 006.001 0M18 7l3 9m-3-9l-6-2m0-2v2m0 16V5m0 16H9m3 0h3" />
          </svg>
          <p className="font-medium text-lg">Ürün ara ve fiyatları karşılaştır</p>
          <p className="text-sm mt-1">Arama kutusuna ürün adı veya marka gir.</p>
        </div>
      )}
    </main>
  );
}

export default function ComparePage() {
  return (
    <div className="min-h-screen bg-slate-50 dark:bg-slate-950">
      <Navbar />
      <Suspense fallback={<div className="flex items-center justify-center py-20 text-slate-400">Yükleniyor…</div>}>
        <CompareContent />
      </Suspense>
    </div>
  );
}
