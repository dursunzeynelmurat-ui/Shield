"use client";
import { useState, useCallback } from "react";
import { useRouter } from "next/navigation";
import Navbar from "@/components/Navbar";
import { uploadFile, createOrderFromUpload } from "@/lib/api";

const STEPS = [
  { n: 1, label: "Yükle",      desc: "Ekran görüntüsü veya fatura" },
  { n: 2, label: "Analiz",     desc: "AI otomatik okuyor" },
  { n: 3, label: "Doğrula",    desc: "Bilgileri kontrol et" },
];

export default function UploadPage() {
  const router = useRouter();
  const [file, setFile] = useState<File | null>(null);
  const [preview, setPreview] = useState<string | null>(null);
  const [dragging, setDragging] = useState(false);
  const [step, setStep] = useState<"idle" | "uploading" | "parsing" | "done">("idle");
  const [error, setError] = useState("");
  const [progress, setProgress] = useState(0);

  const selectFile = useCallback((f: File) => {
    setFile(f);
    setError("");
    if (f.type.startsWith("image/")) {
      const reader = new FileReader();
      reader.onload = (e) => setPreview(e.target?.result as string);
      reader.readAsDataURL(f);
    } else {
      setPreview(null);
    }
  }, []);

  const handleDrop = useCallback((e: React.DragEvent) => {
    e.preventDefault();
    setDragging(false);
    const f = e.dataTransfer.files[0];
    if (f) selectFile(f);
  }, [selectFile]);

  const handleSubmit = async () => {
    if (!file) return;
    setError("");

    // Simulate progress steps
    setStep("uploading");
    setProgress(20);
    try {
      const upload = await uploadFile(file);
      setProgress(50);
      setStep("parsing");
      setProgress(70);
      const order = await createOrderFromUpload(upload.id);
      setProgress(100);
      setStep("done");
      setTimeout(() => router.push(`/orders/${order.id}`), 600);
    } catch (err: unknown) {
      const msg = (err as { response?: { data?: { detail?: string } } })?.response?.data?.detail;
      setError(msg || "Yükleme başarısız. Lütfen tekrar deneyin.");
      setStep("idle");
      setProgress(0);
    }
  };

  const busy = step === "uploading" || step === "parsing";

  const stepMessage = {
    idle: "",
    uploading: "Dosya yükleniyor...",
    parsing: "AI analiz ediyor, lütfen bekleyin...",
    done: "Tamamlandı! Yönlendiriliyorsunuz...",
  }[step];

  return (
    <>
      <Navbar />
      <div className="max-w-2xl mx-auto px-4 sm:px-6 py-10 animate-fade-in">

        {/* Header */}
        <div className="mb-8">
          <h1 className="text-2xl font-bold text-slate-900">Sipariş Yükle</h1>
          <p className="text-slate-500 text-sm mt-1">
            Sipariş ekran görüntünü veya faturanı yükle — gerisini biz hallederiz.
          </p>
        </div>

        {/* Step indicator */}
        <div className="flex items-center gap-2 mb-8">
          {STEPS.map((s, i) => {
            const done = (step === "parsing" && s.n === 1) || step === "done";
            const active = (step === "uploading" && s.n === 1) || (step === "parsing" && s.n === 2) || (step === "done" && s.n === 3);
            return (
              <div key={s.n} className="flex items-center gap-2 flex-1 min-w-0">
                <div className="flex items-center gap-2 shrink-0">
                  <div className={`w-7 h-7 rounded-full flex items-center justify-center text-xs font-bold transition-all ${
                    done ? "bg-emerald-500 text-white" :
                    active ? "bg-blue-600 text-white shadow-md" :
                    "bg-slate-200 text-slate-400"
                  }`}>
                    {done
                      ? <svg className="w-3.5 h-3.5" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={3}><path strokeLinecap="round" strokeLinejoin="round" d="M5 13l4 4L19 7" /></svg>
                      : s.n}
                  </div>
                  <div className="hidden sm:block">
                    <p className={`text-xs font-semibold leading-tight ${active ? "text-blue-700" : done ? "text-emerald-600" : "text-slate-400"}`}>{s.label}</p>
                    <p className="text-xs text-slate-400">{s.desc}</p>
                  </div>
                </div>
                {i < STEPS.length - 1 && (
                  <div className={`flex-1 h-px transition-all ${done ? "bg-emerald-400" : "bg-slate-200"}`} />
                )}
              </div>
            );
          })}
        </div>

        {/* Drop zone */}
        <div
          onDragOver={(e) => { e.preventDefault(); setDragging(true); }}
          onDragLeave={() => setDragging(false)}
          onDrop={handleDrop}
          onClick={() => !busy && document.getElementById("file-input")?.click()}
          className={`relative rounded-2xl border-2 border-dashed transition-all duration-200 cursor-pointer overflow-hidden
            ${busy ? "cursor-not-allowed opacity-60" : ""}
            ${dragging ? "border-blue-400 bg-blue-50 scale-[1.01]" : "border-slate-200 bg-white hover:border-blue-300 hover:bg-slate-50"}
          `}
        >
          <input
            id="file-input"
            type="file"
            accept="image/jpeg,image/png,image/webp,application/pdf"
            className="hidden"
            disabled={busy}
            onChange={(e) => e.target.files?.[0] && selectFile(e.target.files[0])}
          />

          <div className="p-10 text-center">
            {preview ? (
              <div className="space-y-3">
                {/* eslint-disable-next-line @next/next/no-img-element */}
                <img src={preview} alt="Preview" className="max-h-48 mx-auto rounded-xl object-contain shadow-sm" />
                <p className="text-sm font-semibold text-slate-700">{file?.name}</p>
                <p className="text-xs text-slate-400">{file ? `${(file.size / 1024).toFixed(0)} KB` : ""}</p>
                {!busy && (
                  <button
                    onClick={(e) => { e.stopPropagation(); setFile(null); setPreview(null); }}
                    className="text-xs text-slate-400 hover:text-rose-500 transition-colors"
                  >
                    Farklı dosya seç
                  </button>
                )}
              </div>
            ) : file ? (
              <div className="space-y-2">
                <div className="w-14 h-14 rounded-xl bg-blue-50 flex items-center justify-center mx-auto">
                  <svg className="w-7 h-7 text-blue-500" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={1.5}>
                    <path strokeLinecap="round" strokeLinejoin="round" d="M9 12h6m-6 4h6m2 5H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z" />
                  </svg>
                </div>
                <p className="text-sm font-semibold text-slate-700">{file.name}</p>
                <p className="text-xs text-slate-400">{(file.size / 1024).toFixed(0)} KB · PDF</p>
              </div>
            ) : (
              <div className="space-y-4">
                <div className="w-16 h-16 rounded-2xl bg-slate-100 flex items-center justify-center mx-auto">
                  <svg className="w-8 h-8 text-slate-400" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={1.5}>
                    <path strokeLinecap="round" strokeLinejoin="round" d="M4 16v1a3 3 0 003 3h10a3 3 0 003-3v-1m-4-8l-4-4m0 0L8 8m4-4v12" />
                  </svg>
                </div>
                <div>
                  <p className="text-slate-700 font-semibold">Sürükle & Bırak</p>
                  <p className="text-slate-400 text-sm mt-1">veya tıkla ve seç</p>
                </div>
                <div className="flex items-center justify-center gap-2 flex-wrap">
                  {["PNG", "JPG", "WebP", "PDF"].map(t => (
                    <span key={t} className="text-xs bg-slate-100 text-slate-500 px-2.5 py-0.5 rounded-full font-medium">{t}</span>
                  ))}
                  <span className="text-xs text-slate-400">· Maks. 20MB</span>
                </div>
              </div>
            )}
          </div>

          {/* Progress bar overlay */}
          {busy && (
            <div className="absolute bottom-0 left-0 right-0 h-1 bg-slate-100">
              <div
                className="h-full bg-blue-500 transition-all duration-700 ease-out"
                style={{ width: `${progress}%` }}
              />
            </div>
          )}
        </div>

        {/* Status message */}
        {stepMessage && (
          <div className="mt-4 flex items-center gap-2 text-sm text-slate-600 bg-blue-50 border border-blue-100 rounded-xl px-4 py-3">
            <svg className="animate-spin w-4 h-4 text-blue-500 shrink-0" viewBox="0 0 24 24" fill="none">
              <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4"/>
              <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4z"/>
            </svg>
            {stepMessage}
          </div>
        )}

        {/* Error */}
        {error && (
          <div className="mt-4 flex items-center gap-2 text-rose-600 bg-rose-50 border border-rose-200 rounded-xl px-4 py-3 text-sm">
            <svg className="w-4 h-4 shrink-0" fill="currentColor" viewBox="0 0 20 20">
              <path fillRule="evenodd" d="M10 18a8 8 0 100-16 8 8 0 000 16zM8.707 7.293a1 1 0 00-1.414 1.414L8.586 10l-1.293 1.293a1 1 0 101.414 1.414L10 11.414l1.293 1.293a1 1 0 001.414-1.414L11.414 10l1.293-1.293a1 1 0 00-1.414-1.414L10 8.586 8.707 7.293z" clipRule="evenodd" />
            </svg>
            {error}
          </div>
        )}

        {/* CTA */}
        <button
          onClick={handleSubmit}
          disabled={!file || busy}
          className="btn-primary w-full mt-6 flex items-center justify-center gap-2 py-3 text-base"
        >
          {busy
            ? <><svg className="animate-spin w-4 h-4" viewBox="0 0 24 24" fill="none"><circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4"/><path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4z"/></svg> {stepMessage}</>
            : <><svg className="w-5 h-5" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}><path strokeLinecap="round" strokeLinejoin="round" d="M9 5H7a2 2 0 00-2 2v12a2 2 0 002 2h10a2 2 0 002-2V7a2 2 0 00-2-2h-2M9 5a2 2 0 002 2h2a2 2 0 002-2M9 5a2 2 0 012-2h2a2 2 0 012 2m-6 9l2 2 4-4" /></svg> Yükle ve Analiz Et</>}
        </button>

        {/* Info */}
        <p className="text-center text-xs text-slate-400 mt-4">
          AI okuması birkaç saniye sürebilir. Bilgileri sonradan düzenleyebilirsin.
        </p>
      </div>
    </>
  );
}
