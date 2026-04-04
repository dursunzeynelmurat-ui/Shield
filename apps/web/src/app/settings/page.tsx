"use client";
import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import Navbar from "@/components/Navbar";
import { getMe, updateMe, changePassword, deleteAccount } from "@/lib/api";
import { removeToken } from "@/lib/auth";

interface UserData { id: number; email: string; is_active: boolean; created_at: string }

function SettingSection({ title, subtitle, children }: { title: string; subtitle?: string; children: React.ReactNode }) {
  return (
    <div className="card p-6">
      <div className="mb-5">
        <h2 className="text-sm font-semibold text-slate-900">{title}</h2>
        {subtitle && <p className="text-xs text-slate-400 mt-0.5">{subtitle}</p>}
      </div>
      {children}
    </div>
  );
}

function Toast({ msg, ok }: { msg: string; ok: boolean }) {
  return (
    <div className={`fixed bottom-5 right-5 z-50 flex items-center gap-2 px-4 py-3 rounded-xl shadow-card-lg text-sm font-medium animate-fade-in ${
      ok ? "bg-emerald-600 text-white" : "bg-rose-600 text-white"
    }`}>
      {ok
        ? <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2.5}><path strokeLinecap="round" strokeLinejoin="round" d="M5 13l4 4L19 7" /></svg>
        : <svg className="w-4 h-4" fill="currentColor" viewBox="0 0 20 20"><path fillRule="evenodd" d="M10 18a8 8 0 100-16 8 8 0 000 16zM8.707 7.293a1 1 0 00-1.414 1.414L8.586 10l-1.293 1.293a1 1 0 101.414 1.414L10 11.414l1.293 1.293a1 1 0 001.414-1.414L11.414 10l1.293-1.293a1 1 0 00-1.414-1.414L10 8.586 8.707 7.293z" clipRule="evenodd" /></svg>}
      {msg}
    </div>
  );
}

export default function SettingsPage() {
  const router = useRouter();
  const [user, setUser] = useState<UserData | null>(null);
  const [email, setEmail] = useState("");
  const [currentPw, setCurrentPw] = useState("");
  const [newPw, setNewPw] = useState("");
  const [confirmPw, setConfirmPw] = useState("");
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [toast, setToast] = useState<{ msg: string; ok: boolean } | null>(null);

  const showToast = (msg: string, ok: boolean) => {
    setToast({ msg, ok });
    setTimeout(() => setToast(null), 3500);
  };

  useEffect(() => {
    getMe()
      .then((u: UserData) => { setUser(u); setEmail(u.email); })
      .finally(() => setLoading(false));
  }, []);

  const handleEmailUpdate = async (e: React.FormEvent) => {
    e.preventDefault();
    setSaving(true);
    try {
      const updated = await updateMe({ email });
      setUser(updated);
      showToast("E-posta başarıyla güncellendi.", true);
    } catch (err: unknown) {
      const msg = (err as { response?: { data?: { detail?: string } } })?.response?.data?.detail;
      showToast(msg || "Güncelleme başarısız.", false);
    } finally { setSaving(false); }
  };

  const handlePasswordChange = async (e: React.FormEvent) => {
    e.preventDefault();
    if (newPw !== confirmPw) { showToast("Şifreler eşleşmiyor.", false); return; }
    setSaving(true);
    try {
      await changePassword(currentPw, newPw);
      setCurrentPw(""); setNewPw(""); setConfirmPw("");
      showToast("Şifre başarıyla değiştirildi.", true);
    } catch (err: unknown) {
      const msg = (err as { response?: { data?: { detail?: string } } })?.response?.data?.detail;
      showToast(msg || "Şifre değiştirme başarısız.", false);
    } finally { setSaving(false); }
  };

  const handleDeleteAccount = async () => {
    if (!confirm("Hesabını silmek istediğinden emin misin? Bu işlem geri alınamaz.")) return;
    await deleteAccount();
    removeToken();
    router.push("/login");
  };

  if (loading) return (
    <>
      <Navbar />
      <div className="max-w-xl mx-auto px-4 py-10 space-y-4">
        {[1, 2, 3].map(i => <div key={i} className="card p-6 space-y-3"><div className="skeleton h-4 w-32" /><div className="skeleton h-10 w-full" /></div>)}
      </div>
    </>
  );

  return (
    <>
      <Navbar />
      <div className="max-w-xl mx-auto px-4 sm:px-6 py-8 space-y-5 animate-fade-in">

        <div>
          <h1 className="text-2xl font-bold text-slate-900">Hesap Ayarları</h1>
          <p className="text-slate-500 text-sm mt-1">Profilini ve güvenlik bilgilerini yönet.</p>
        </div>

        {/* Account overview */}
        <div className="card p-5 flex items-center gap-4">
          <div className="w-12 h-12 rounded-full bg-brand-gradient flex items-center justify-center text-white font-bold text-lg shrink-0">
            {user?.email[0].toUpperCase()}
          </div>
          <div className="min-w-0">
            <p className="font-semibold text-slate-900 truncate">{user?.email}</p>
            <div className="flex items-center gap-2 mt-0.5">
              <span className={`w-1.5 h-1.5 rounded-full ${user?.is_active ? "bg-emerald-500" : "bg-slate-300"}`} />
              <p className="text-xs text-slate-400">
                {user?.is_active ? "Aktif hesap" : "Devre dışı"} · Kayıt: {user?.created_at ? new Date(user.created_at).toLocaleDateString("tr-TR") : "—"}
              </p>
            </div>
          </div>
        </div>

        {/* Email */}
        <SettingSection title="E-posta Adresi" subtitle="Giriş yaparken kullandığın e-posta adresi.">
          <form onSubmit={handleEmailUpdate} className="space-y-3">
            <div>
              <label className="label">E-posta</label>
              <input type="email" required value={email} onChange={e => setEmail(e.target.value)} className="input" />
            </div>
            <button type="submit" disabled={saving || email === user?.email} className="btn-primary">
              Güncelle
            </button>
          </form>
        </SettingSection>

        {/* Password */}
        <SettingSection title="Şifre Değiştir" subtitle="En az 8 karakter kullan.">
          <form onSubmit={handlePasswordChange} className="space-y-3">
            <div>
              <label className="label">Mevcut Şifre</label>
              <input type="password" required minLength={8} value={currentPw} onChange={e => setCurrentPw(e.target.value)} className="input" placeholder="••••••••" />
            </div>
            <div>
              <label className="label">Yeni Şifre</label>
              <input type="password" required minLength={8} value={newPw} onChange={e => setNewPw(e.target.value)} className="input" placeholder="••••••••" />
            </div>
            <div>
              <label className="label">Yeni Şifre (Tekrar)</label>
              <input
                type="password"
                required
                minLength={8}
                value={confirmPw}
                onChange={e => setConfirmPw(e.target.value)}
                className={`input ${confirmPw && confirmPw !== newPw ? "border-rose-400 focus:ring-rose-400" : ""}`}
                placeholder="••••••••"
              />
              {confirmPw && confirmPw !== newPw && (
                <p className="text-xs text-rose-500 mt-1">Şifreler eşleşmiyor.</p>
              )}
            </div>
            <button type="submit" disabled={saving || (!!confirmPw && confirmPw !== newPw)} className="btn-primary">
              Şifreyi Değiştir
            </button>
          </form>
        </SettingSection>

        {/* Account info */}
        <SettingSection title="Hesap Bilgileri">
          <div className="space-y-0 divide-y divide-slate-100">
            {[
              ["Kullanıcı ID", `#${user?.id}`],
              ["Kayıt Tarihi", user?.created_at ? new Date(user.created_at).toLocaleDateString("tr-TR", { day: "numeric", month: "long", year: "numeric" }) : "—"],
              ["Durum", user?.is_active ? "Aktif" : "Devre dışı"],
            ].map(([label, value]) => (
              <div key={label} className="flex justify-between items-center py-3">
                <span className="text-sm text-slate-400">{label}</span>
                <span className="text-sm font-medium text-slate-700">{value}</span>
              </div>
            ))}
          </div>
        </SettingSection>

        {/* Danger zone */}
        <div className="card p-6 border border-rose-100">
          <h2 className="text-sm font-semibold text-slate-900 mb-1">Tehlikeli Alan</h2>
          <p className="text-xs text-slate-400 mb-5">
            Hesabını silerseniz tüm sipariş ve uyarı verilen kalıcı olarak devre dışı kalır. Bu işlem geri alınamaz.
          </p>
          <button onClick={handleDeleteAccount} className="btn-danger">
            Hesabı Sil
          </button>
        </div>
      </div>

      {toast && <Toast msg={toast.msg} ok={toast.ok} />}
    </>
  );
}
