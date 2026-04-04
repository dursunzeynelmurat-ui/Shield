"use client";
import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";

const STEPS = [
  {
    icon: (
      <svg className="w-10 h-10 text-blue-600" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={1.5}>
        <path strokeLinecap="round" strokeLinejoin="round" d="M9 12l2 2 4-4m5.618-4.016A11.955 11.955 0 0112 2.944a11.955 11.955 0 01-8.618 3.04A12.02 12.02 0 003 9c0 5.591 3.824 10.29 9 11.622 5.176-1.332 9-6.03 9-11.622 0-1.042-.133-2.052-.382-3.016z" />
      </svg>
    ),
    title: "Fiyat Kalkanı'na Hoş Geldin!",
    body: "Satın aldığın ürünlerin fiyatı düşünce seni anında haberdar ederiz. Fark iadesi, iade & tekrar alım ve kupon takibi — hepsi tek yerde.",
    action: null,
  },
  {
    icon: (
      <svg className="w-10 h-10 text-indigo-600" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={1.5}>
        <path strokeLinecap="round" strokeLinejoin="round" d="M7 16a4 4 0 01-.88-7.903A5 5 0 1115.9 6L16 6a5 5 0 011 9.9M15 13l-3-3m0 0l-3 3m3-3v12" />
      </svg>
    ),
    title: "Makbuzunu Yükle",
    body: "Sipariş onayı e-postası, fatura veya makbuz görseli yeterli. Yapay zeka ürün bilgilerini otomatik okur.",
    action: { label: "Sipariş Ekle", href: "/upload" },
  },
  {
    icon: (
      <svg className="w-10 h-10 text-emerald-600" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={1.5}>
        <path strokeLinecap="round" strokeLinejoin="round" d="M15 17h5l-1.405-1.405A2.032 2.032 0 0118 14.158V11a6.002 6.002 0 00-4-5.659V5a2 2 0 10-4 0v.341C7.67 6.165 6 8.388 6 11v3.159c0 .538-.214 1.055-.595 1.436L4 17h5m6 0v1a3 3 0 11-6 0v-1m6 0H9" />
      </svg>
    ),
    title: "Uyarıları Takip Et",
    body: "Fiyat düşüşü olduğunda veya iade süresi yaklaşınca bildirim alırsın. Her uyarı için yapılabilecek en iyi eylemi öneririz.",
    action: null,
  },
  {
    icon: (
      <svg className="w-10 h-10 text-amber-500" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={1.5}>
        <path strokeLinecap="round" strokeLinejoin="round" d="M7 7h.01M7 3h5c.512 0 1.024.195 1.414.586l7 7a2 2 0 010 2.828l-7 7a2 2 0 01-2.828 0l-7-7A1.994 1.994 0 013 12V7a4 4 0 014-4z" />
      </svg>
    ),
    title: "Fırsatları Kaçırma",
    body: "Aktif kuponlar ve indirim kodlarını Fırsatlar sayfasında takip et. Ürün aramak için Karşılaştır sayfasını kullan.",
    action: { label: "Fırsatlara Bak", href: "/deals" },
  },
];

const STORAGE_KEY = "onboarding_done";

export default function Onboarding() {
  const router = useRouter();
  const [visible, setVisible] = useState(false);
  const [step, setStep] = useState(0);

  useEffect(() => {
    if (typeof window !== "undefined" && !localStorage.getItem(STORAGE_KEY)) {
      setVisible(true);
    }
  }, []);

  const dismiss = () => {
    localStorage.setItem(STORAGE_KEY, "1");
    setVisible(false);
  };

  const next = () => {
    if (step < STEPS.length - 1) {
      setStep(step + 1);
    } else {
      dismiss();
    }
  };

  const goAction = (href: string) => {
    dismiss();
    router.push(href);
  };

  if (!visible) return null;

  const current = STEPS[step];
  const isLast = step === STEPS.length - 1;

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/40 backdrop-blur-sm animate-fade-in px-4">
      <div className="bg-white dark:bg-slate-900 rounded-3xl shadow-2xl w-full max-w-md p-8 relative">
        {/* Skip */}
        <button
          onClick={dismiss}
          className="absolute top-4 right-4 p-2 rounded-lg text-slate-400 hover:text-slate-600 dark:hover:text-slate-300 hover:bg-slate-100 dark:hover:bg-slate-800 transition-all"
          aria-label="Kapat"
        >
          <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
            <path strokeLinecap="round" strokeLinejoin="round" d="M6 18L18 6M6 6l12 12" />
          </svg>
        </button>

        {/* Progress dots */}
        <div className="flex gap-1.5 mb-8">
          {STEPS.map((_, i) => (
            <div
              key={i}
              className={`h-1.5 rounded-full transition-all duration-300 ${
                i === step
                  ? "w-6 bg-blue-600"
                  : i < step
                  ? "w-3 bg-blue-300 dark:bg-blue-700"
                  : "w-3 bg-slate-200 dark:bg-slate-700"
              }`}
            />
          ))}
        </div>

        {/* Icon */}
        <div className="w-16 h-16 rounded-2xl bg-slate-50 dark:bg-slate-800 flex items-center justify-center mb-5">
          {current.icon}
        </div>

        {/* Content */}
        <h2 className="text-lg font-bold text-slate-900 dark:text-white mb-2">{current.title}</h2>
        <p className="text-sm text-slate-500 dark:text-slate-400 leading-relaxed mb-8">{current.body}</p>

        {/* Actions */}
        <div className="flex gap-3">
          {current.action && (
            <button
              onClick={() => goAction(current.action!.href)}
              className="btn-primary flex-1"
            >
              {current.action.label}
            </button>
          )}
          <button
            onClick={next}
            className={current.action ? "btn-secondary" : "btn-primary flex-1"}
          >
            {isLast ? "Başla" : "İleri →"}
          </button>
        </div>

        {/* Skip link */}
        <button onClick={dismiss} className="w-full mt-4 text-xs text-slate-400 hover:text-slate-600 dark:hover:text-slate-400 transition-colors">
          Geç
        </button>
      </div>
    </div>
  );
}
