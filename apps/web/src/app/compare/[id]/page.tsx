"use client";
import { useEffect, useState } from "react";
import { useParams } from "next/navigation";
import Link from "next/link";
import Navbar from "@/components/Navbar";
import { getProduct, trackClick, addToWatchlist, removeFromWatchlist } from "@/lib/api";

interface MerchantOffer {
  id: number;
  merchant: string;
  seller_name?: string;
  url?: string;
  listed_price?: number;
  shipping_price?: number;
  effective_price?: number;
  currency: string;
  in_stock: boolean;
  last_checked_at?: string;
}

interface Product {
  id: number;
  name: string;
  brand?: string;
  model?: string;
  category?: string;
  description?: string;
  image_url?: string;
  ean?: string;
  offers: MerchantOffer[];
}

function fmt(val?: number, currency = "TRY") {
  if (val == null) return "—";
  return new Intl.NumberFormat("tr-TR", { style: "currency", currency }).format(val);
}

export default function ProductDetailPage() {
  const { id } = useParams<{ id: string }>();
  const [product, setProduct] = useState<Product | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [watchlisted, setWatchlisted] = useState(false);
  const [watchlistLoading, setWatchlistLoading] = useState(false);

  useEffect(() => {
    if (!id) return;
    getProduct(Number(id))
      .then(setProduct)
      .catch(() => setError("Ürün yüklenirken hata oluştu."))
      .finally(() => setLoading(false));
  }, [id]);

  const handleOfferClick = async (offer: MerchantOffer) => {
    try {
      await trackClick({ merchant_offer_id: offer.id, url: offer.url ?? undefined });
    } catch { /* non-blocking */ }
    if (offer.url) window.open(offer.url, "_blank", "noopener,noreferrer");
  };

  const handleWatchlist = async () => {
    if (!product) return;
    setWatchlistLoading(true);
    try {
      if (watchlisted) {
        await removeFromWatchlist(product.id);
        setWatchlisted(false);
      } else {
        await addToWatchlist(product.id);
        setWatchlisted(true);
      }
    } catch { /* non-blocking */ }
    finally { setWatchlistLoading(false); }
  };

  const lowestPrice = product?.offers?.[0]?.effective_price;

  return (
    <div className="min-h-screen bg-slate-50 dark:bg-slate-950">
      <Navbar />
      <main className="max-w-5xl mx-auto px-4 py-8">
        <Link href="/compare" className="inline-flex items-center gap-1.5 text-sm text-slate-500 hover:text-slate-700 dark:hover:text-slate-300 mb-6">
          <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
            <path strokeLinecap="round" strokeLinejoin="round" d="M15 19l-7-7 7-7" />
          </svg>
          Arama sonuçlarına dön
        </Link>

        {loading && (
          <div className="bg-white dark:bg-slate-900 rounded-2xl border border-slate-100 dark:border-slate-800 p-8">
            <div className="flex gap-8 mb-8">
              <div className="skeleton w-48 h-48 shrink-0 rounded-xl" />
              <div className="flex-1 space-y-3">
                <div className="skeleton h-6 w-3/4" />
                <div className="skeleton h-4 w-1/2" />
                <div className="skeleton h-4 w-1/3" />
              </div>
            </div>
            {Array.from({ length: 3 }).map((_, i) => (
              <div key={i} className="skeleton h-16 mb-3 rounded-xl" />
            ))}
          </div>
        )}

        {error && (
          <div className="text-center py-16 text-rose-500">
            <p>{error}</p>
          </div>
        )}

        {!loading && product && (
          <>
            {/* Product header */}
            <div className="bg-white dark:bg-slate-900 rounded-2xl border border-slate-100 dark:border-slate-800 shadow-sm p-6 mb-6">
              <div className="flex gap-6 flex-col sm:flex-row">
                {product.image_url ? (
                  <img
                    src={product.image_url}
                    alt={product.name}
                    className="w-48 h-48 object-contain rounded-xl bg-slate-50 dark:bg-slate-800 shrink-0 self-start"
                  />
                ) : (
                  <div className="w-48 h-48 rounded-xl bg-slate-50 dark:bg-slate-800 shrink-0 flex items-center justify-center">
                    <svg className="w-16 h-16 text-slate-300 dark:text-slate-600" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1} d="M20 7l-8-4-8 4m16 0l-8 4m8-4v10l-8 4m0-10L4 7m8 4v10M4 7v10l8 4" />
                    </svg>
                  </div>
                )}
                <div className="flex-1 min-w-0">
                  <h1 className="text-xl font-bold text-slate-900 dark:text-white mb-2 leading-snug">{product.name}</h1>
                  <div className="flex flex-wrap gap-2 mb-4">
                    {product.brand && <span className="badge bg-blue-50 text-blue-700 dark:bg-blue-950 dark:text-blue-300">{product.brand}</span>}
                    {product.model && <span className="badge bg-slate-50 text-slate-600 dark:bg-slate-800 dark:text-slate-400">{product.model}</span>}
                    {product.category && <span className="badge bg-slate-50 text-slate-600 dark:bg-slate-800 dark:text-slate-400">{product.category}</span>}
                  </div>
                  {product.description && (
                    <p className="text-sm text-slate-500 dark:text-slate-400 leading-relaxed line-clamp-3">{product.description}</p>
                  )}
                  {lowestPrice != null && (
                    <div className="mt-4 inline-flex items-baseline gap-1.5">
                      <span className="text-xs text-slate-400">En düşük:</span>
                      <span className="text-2xl font-bold text-emerald-600 dark:text-emerald-400">{fmt(lowestPrice)}</span>
                    </div>
                  )}
                  <div className="mt-4">
                    <button
                      onClick={handleWatchlist}
                      disabled={watchlistLoading}
                      className={`inline-flex items-center gap-2 px-4 py-2 rounded-xl text-sm font-medium transition-all border disabled:opacity-50 ${
                        watchlisted
                          ? "bg-amber-50 border-amber-200 text-amber-700 dark:bg-amber-950 dark:border-amber-800 dark:text-amber-300"
                          : "bg-slate-50 border-slate-200 text-slate-600 hover:bg-amber-50 hover:border-amber-200 hover:text-amber-700 dark:bg-slate-800 dark:border-slate-700 dark:text-slate-300"
                      }`}
                    >
                      <svg className="w-4 h-4" fill={watchlisted ? "currentColor" : "none"} viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
                        <path strokeLinecap="round" strokeLinejoin="round" d="M4.318 6.318a4.5 4.5 0 000 6.364L12 20.364l7.682-7.682a4.5 4.5 0 00-6.364-6.364L12 7.636l-1.318-1.318a4.5 4.5 0 00-6.364 0z" />
                      </svg>
                      {watchlisted ? "Takip Ediliyor" : "Takip Et"}
                    </button>
                  </div>
                </div>
              </div>
            </div>

            {/* Offers table */}
            <div className="bg-white dark:bg-slate-900 rounded-2xl border border-slate-100 dark:border-slate-800 shadow-sm overflow-hidden">
              <div className="px-6 py-4 border-b border-slate-100 dark:border-slate-800">
                <h2 className="font-semibold text-slate-800 dark:text-slate-100">
                  Satıcı Fiyatları
                  <span className="ml-2 text-xs font-normal text-slate-400">({product.offers.length} satıcı)</span>
                </h2>
              </div>

              {product.offers.length === 0 && (
                <div className="py-12 text-center text-slate-400 dark:text-slate-600 text-sm">
                  Bu ürün için henüz fiyat bilgisi bulunmuyor.
                </div>
              )}

              <div className="divide-y divide-slate-50 dark:divide-slate-800">
                {product.offers.map((offer, idx) => (
                  <div key={offer.id} className={`flex items-center gap-4 px-6 py-4 hover:bg-slate-50 dark:hover:bg-slate-800/50 transition-colors ${idx === 0 ? "bg-emerald-50/40 dark:bg-emerald-950/20" : ""}`}>
                    {/* Rank */}
                    <div className={`w-7 h-7 rounded-full flex items-center justify-center text-xs font-bold shrink-0 ${idx === 0 ? "bg-emerald-100 text-emerald-700 dark:bg-emerald-900 dark:text-emerald-300" : "bg-slate-100 text-slate-500 dark:bg-slate-800 dark:text-slate-400"}`}>
                      {idx + 1}
                    </div>

                    {/* Merchant info */}
                    <div className="flex-1 min-w-0">
                      <p className="text-sm font-semibold text-slate-800 dark:text-slate-100">{offer.merchant}</p>
                      {offer.seller_name && offer.seller_name !== offer.merchant && (
                        <p className="text-xs text-slate-400">{offer.seller_name}</p>
                      )}
                    </div>

                    {/* Stock badge */}
                    <span className={`badge shrink-0 ${offer.in_stock ? "bg-emerald-50 text-emerald-700 dark:bg-emerald-950 dark:text-emerald-300" : "bg-slate-50 text-slate-400 dark:bg-slate-800"}`}>
                      {offer.in_stock ? "Stokta" : "Stok Yok"}
                    </span>

                    {/* Pricing */}
                    <div className="text-right shrink-0">
                      <p className="text-base font-bold text-slate-900 dark:text-white">{fmt(offer.effective_price ?? offer.listed_price, offer.currency)}</p>
                      {offer.shipping_price != null && offer.shipping_price > 0 && (
                        <p className="text-xs text-slate-400">+{fmt(offer.shipping_price, offer.currency)} kargo</p>
                      )}
                      {offer.shipping_price === 0 && (
                        <p className="text-xs text-emerald-500">Ücretsiz kargo</p>
                      )}
                    </div>

                    {/* CTA */}
                    <button
                      onClick={() => handleOfferClick(offer)}
                      disabled={!offer.in_stock || !offer.url}
                      className="btn-primary px-4 py-2 shrink-0 disabled:opacity-40"
                    >
                      Git
                      <svg className="w-3.5 h-3.5 inline ml-1" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2.5}>
                        <path strokeLinecap="round" strokeLinejoin="round" d="M10 6H6a2 2 0 00-2 2v10a2 2 0 002 2h10a2 2 0 002-2v-4M14 4h6m0 0v6m0-6L10 14" />
                      </svg>
                    </button>
                  </div>
                ))}
              </div>
            </div>
          </>
        )}
      </main>
    </div>
  );
}
