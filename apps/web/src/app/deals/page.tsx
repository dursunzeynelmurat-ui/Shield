"use client";
import { useEffect, useState } from "react";
import Navbar from "@/components/Navbar";
import { getDeals, trackClick } from "@/lib/api";

interface Deal {
  id: number;
  merchant: string;
  title: string;
  description?: string;
  code?: string;
  discount_type?: string;
  discount_value?: number;
  minimum_spend?: number;
  conditions?: string;
  url?: string;
  expires_at?: string;
  confidence?: number;
}

const DISCOUNT_LABELS: Record<string, string> = {
  percentage: "İndirim %",
  fixed_amount: "Sabit İndirim",
  free_shipping: "Ücretsiz Kargo",
  cashback: "Cashback",
};

function timeUntil(iso?: string): string {
  if (!iso) return "";
  const diff = new Date(iso).getTime() - Date.now();
  if (diff < 0) return "Süresi doldu";
  const hours = Math.floor(diff / 3_600_000);
  if (hours < 24) return `${hours} saat kaldı`;
  return `${Math.floor(hours / 24)} gün kaldı`;
}

function DealCard({ deal }: { deal: Deal }) {
  const [copied, setCopied] = useState(false);

  const copyCode = () => {
    if (deal.code) {
      navigator.clipboard.writeText(deal.code);
      setCopied(true);
      setTimeout(() => setCopied(false), 2000);
    }
  };

  const handleGo = async () => {
    try { await trackClick({ offer_id: deal.id, url: deal.url ?? undefined }); } catch { /* noop */ }
    if (deal.url) window.open(deal.url, "_blank", "noopener,noreferrer");
  };

  const expiryText = timeUntil(deal.expires_at);
  const isExpiringSoon = deal.expires_at && (new Date(deal.expires_at).getTime() - Date.now()) < 86_400_000;

  return (
    <div className="bg-white dark:bg-slate-900 rounded-2xl border border-slate-100 dark:border-slate-800 shadow-sm hover:shadow-md transition-all p-5 flex flex-col gap-3">
      {/* Header */}
      <div className="flex items-start justify-between gap-3">
        <div className="flex-1 min-w-0">
          <div className="flex flex-wrap gap-1.5 mb-1.5">
            <span className="badge bg-blue-50 text-blue-700 dark:bg-blue-950 dark:text-blue-300">{deal.merchant}</span>
            {deal.discount_type && (
              <span className="badge bg-slate-50 text-slate-600 dark:bg-slate-800 dark:text-slate-400">
                {DISCOUNT_LABELS[deal.discount_type] ?? deal.discount_type}
              </span>
            )}
          </div>
          <h3 className="text-sm font-semibold text-slate-800 dark:text-slate-100 leading-snug">{deal.title}</h3>
        </div>
        {deal.discount_value != null && (
          <div className="shrink-0 text-right">
            <p className="text-xl font-extrabold text-emerald-600 dark:text-emerald-400">
              {deal.discount_type === "percentage" ? `%${deal.discount_value}` : `${deal.discount_value} ₺`}
            </p>
            <p className="text-xs text-slate-400">indirim</p>
          </div>
        )}
      </div>

      {/* Description */}
      {deal.description && (
        <p className="text-xs text-slate-500 dark:text-slate-400 leading-relaxed">{deal.description}</p>
      )}

      {/* Conditions */}
      {deal.conditions && (
        <p className="text-xs text-amber-700 dark:text-amber-400 bg-amber-50 dark:bg-amber-950/30 rounded-lg px-3 py-2">
          {deal.conditions}
        </p>
      )}

      {/* Minimum spend */}
      {deal.minimum_spend != null && deal.minimum_spend > 0 && (
        <p className="text-xs text-slate-400">Min. harcama: {deal.minimum_spend.toLocaleString("tr-TR")} ₺</p>
      )}

      {/* Expiry */}
      {expiryText && (
        <p className={`text-xs font-medium ${isExpiringSoon ? "text-rose-500" : "text-slate-400"}`}>
          {isExpiringSoon && "⏰ "}{expiryText}
        </p>
      )}

      {/* Code + CTA */}
      <div className="flex items-center gap-2 mt-auto pt-2 border-t border-slate-50 dark:border-slate-800">
        {deal.code ? (
          <button
            onClick={copyCode}
            className="flex-1 flex items-center justify-between gap-2 px-3 py-2 rounded-lg bg-slate-50 dark:bg-slate-800 border border-dashed border-slate-200 dark:border-slate-700 hover:bg-slate-100 dark:hover:bg-slate-700 transition-colors"
          >
            <span className="font-mono text-sm font-bold text-slate-700 dark:text-slate-200 tracking-wider">{deal.code}</span>
            <span className="text-xs text-slate-400">
              {copied ? (
                <span className="text-emerald-500 font-medium">Kopyalandı!</span>
              ) : "Kopyala"}
            </span>
          </button>
        ) : (
          <div className="flex-1" />
        )}
        {deal.url && (
          <button
            onClick={handleGo}
            className="btn-primary px-4 py-2 shrink-0"
          >
            Fırsata Git
            <svg className="w-3.5 h-3.5 inline ml-1" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2.5}>
              <path strokeLinecap="round" strokeLinejoin="round" d="M10 6H6a2 2 0 00-2 2v10a2 2 0 002 2h10a2 2 0 002-2v-4M14 4h6m0 0v6m0-6L10 14" />
            </svg>
          </button>
        )}
      </div>
    </div>
  );
}

const DISCOUNT_TYPES = [
  { value: "", label: "Tüm Tipler" },
  { value: "percentage", label: "İndirim %" },
  { value: "fixed_amount", label: "Sabit İndirim" },
  { value: "free_shipping", label: "Ücretsiz Kargo" },
  { value: "cashback", label: "Cashback" },
];

export default function DealsPage() {
  const [deals, setDeals] = useState<Deal[]>([]);
  const [loading, setLoading] = useState(true);
  const [merchant, setMerchant] = useState("");
  const [discountType, setDiscountType] = useState("");
  const [page, setPage] = useState(1);
  const [total, setTotal] = useState(0);
  const PAGE_SIZE = 12;

  const load = async (p = 1, m = merchant, dt = discountType) => {
    setLoading(true);
    try {
      const data = await getDeals({
        merchant: m || undefined,
        discount_type: dt || undefined,
        page: p,
        page_size: PAGE_SIZE,
      });
      setDeals(data.items);
      setTotal(data.total);
      setPage(p);
    } catch { /* noop */ }
    finally { setLoading(false); }
  };

  useEffect(() => { load(); }, []); // eslint-disable-line react-hooks/exhaustive-deps

  const handleFilter = () => load(1);
  const totalPages = Math.ceil(total / PAGE_SIZE);

  return (
    <div className="min-h-screen bg-slate-50 dark:bg-slate-950">
      <Navbar />
      <main className="max-w-6xl mx-auto px-4 py-8">
        <div className="mb-8 flex flex-col sm:flex-row sm:items-end justify-between gap-4">
          <div>
            <h1 className="text-2xl font-bold text-slate-900 dark:text-white mb-1">Fırsatlar</h1>
            <p className="text-sm text-slate-500 dark:text-slate-400">Aktif kuponlar, indirim kodları ve özel teklifler.</p>
          </div>

          {/* Filters */}
          <div className="flex gap-2 flex-wrap">
            <input
              type="text"
              placeholder="Mağaza filtrele..."
              value={merchant}
              onChange={(e) => setMerchant(e.target.value)}
              onKeyDown={(e) => e.key === "Enter" && handleFilter()}
              className="input w-44 py-2 text-xs"
            />
            <select
              value={discountType}
              onChange={(e) => { setDiscountType(e.target.value); load(1, merchant, e.target.value); }}
              className="input w-40 py-2 text-xs"
            >
              {DISCOUNT_TYPES.map((t) => (
                <option key={t.value} value={t.value}>{t.label}</option>
              ))}
            </select>
            <button onClick={handleFilter} className="btn-secondary py-2 text-xs px-4">Filtrele</button>
          </div>
        </div>

        {loading && (
          <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-4">
            {Array.from({ length: 6 }).map((_, i) => (
              <div key={i} className="bg-white dark:bg-slate-900 rounded-2xl border border-slate-100 dark:border-slate-800 p-5 space-y-3">
                <div className="skeleton h-4 w-1/2" />
                <div className="skeleton h-5 w-3/4" />
                <div className="skeleton h-4 w-full" />
                <div className="skeleton h-10 w-full" />
              </div>
            ))}
          </div>
        )}

        {!loading && deals.length === 0 && (
          <div className="text-center py-20 text-slate-400 dark:text-slate-600">
            <svg className="w-12 h-12 mx-auto mb-3 opacity-40" fill="none" viewBox="0 0 24 24" stroke="currentColor">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} d="M7 7h.01M7 3h5c.512 0 1.024.195 1.414.586l7 7a2 2 0 010 2.828l-7 7a2 2 0 01-2.828 0l-7-7A1.994 1.994 0 013 12V7a4 4 0 014-4z" />
            </svg>
            <p className="font-medium">Aktif fırsat bulunamadı</p>
            <p className="text-sm mt-1">Filtrelerinizi değiştirmeyi deneyin.</p>
          </div>
        )}

        {!loading && deals.length > 0 && (
          <>
            {/* JSON-LD structured data for SEO */}
            <script
              type="application/ld+json"
              suppressHydrationWarning
              dangerouslySetInnerHTML={{
                __html: JSON.stringify({
                  "@context": "https://schema.org",
                  "@type": "ItemList",
                  numberOfItems: deals.length,
                  itemListElement: deals.map((deal, idx) => ({
                    "@type": "ListItem",
                    position: idx + 1,
                    item: {
                      "@type": "Offer",
                      name: deal.title,
                      description: deal.description ?? undefined,
                      url: deal.url ?? undefined,
                      seller: { "@type": "Organization", name: deal.merchant },
                      ...(deal.discount_type === "percentage" && deal.discount_value != null
                        ? { discount: `%${deal.discount_value}` }
                        : {}),
                    },
                  })),
                }),
              }}
            />
            <p className="text-sm text-slate-500 dark:text-slate-400 mb-4">
              <span className="font-semibold text-slate-700 dark:text-slate-200">{total}</span> aktif fırsat
            </p>

            <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-4 mb-8">
              {deals.map((deal) => <DealCard key={deal.id} deal={deal} />)}
            </div>

            {totalPages > 1 && (
              <div className="flex items-center justify-center gap-2">
                <button disabled={page <= 1} onClick={() => load(page - 1)} className="btn-secondary px-3 py-1.5 text-xs disabled:opacity-30">← Önceki</button>
                <span className="text-sm text-slate-500">{page} / {totalPages}</span>
                <button disabled={page >= totalPages} onClick={() => load(page + 1)} className="btn-secondary px-3 py-1.5 text-xs disabled:opacity-30">Sonraki →</button>
              </div>
            )}
          </>
        )}
      </main>
    </div>
  );
}
