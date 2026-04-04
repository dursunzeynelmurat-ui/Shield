"use client";
import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import Navbar from "@/components/Navbar";
import { getMe, updateMe, changePassword, deleteAccount } from "@/lib/api";
import { removeToken } from "@/lib/auth";

interface UserData { id: number; email: string; is_active: boolean; created_at: string }

export default function SettingsPage() {
  const router = useRouter();
  const [user, setUser] = useState<UserData | null>(null);
  const [email, setEmail] = useState("");
  const [emailMsg, setEmailMsg] = useState("");

  const [currentPw, setCurrentPw] = useState("");
  const [newPw, setNewPw] = useState("");
  const [pwMsg, setPwMsg] = useState("");

  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);

  useEffect(() => {
    getMe()
      .then((u: UserData) => { setUser(u); setEmail(u.email); })
      .finally(() => setLoading(false));
  }, []);

  const handleEmailUpdate = async (e: React.FormEvent) => {
    e.preventDefault();
    setSaving(true);
    setEmailMsg("");
    try {
      const updated = await updateMe({ email });
      setUser(updated);
      setEmailMsg("E-posta güncellendi.");
    } catch (err: unknown) {
      const msg = (err as { response?: { data?: { detail?: string } } })?.response?.data?.detail;
      setEmailMsg(msg || "Güncelleme başarısız.");
    } finally {
      setSaving(false);
    }
  };

  const handlePasswordChange = async (e: React.FormEvent) => {
    e.preventDefault();
    setSaving(true);
    setPwMsg("");
    try {
      await changePassword(currentPw, newPw);
      setPwMsg("Şifre başarıyla değiştirildi.");
      setCurrentPw("");
      setNewPw("");
    } catch (err: unknown) {
      const msg = (err as { response?: { data?: { detail?: string } } })?.response?.data?.detail;
      setPwMsg(msg || "Şifre değiştirme başarısız.");
    } finally {
      setSaving(false);
    }
  };

  const handleDeleteAccount = async () => {
    if (!confirm("Hesabını silmek istediğinden emin misin? Bu işlem geri alınamaz.")) return;
    await deleteAccount();
    removeToken();
    router.push("/login");
  };

  if (loading) {
    return (
      <>
        <Navbar />
        <div className="p-8 text-gray-500">Yükleniyor...</div>
      </>
    );
  }

  return (
    <>
      <Navbar />
      <div className="max-w-xl mx-auto p-6 space-y-8">
        <h1 className="text-2xl font-bold text-gray-800">Hesap Ayarları</h1>

        {/* Email */}
        <div className="bg-white rounded-2xl shadow p-5">
          <h2 className="font-semibold text-gray-700 mb-4">E-posta Adresi</h2>
          <form onSubmit={handleEmailUpdate} className="space-y-3">
            <input
              type="email"
              required
              value={email}
              onChange={(e) => setEmail(e.target.value)}
              className="w-full border border-gray-300 rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-blue-500"
            />
            {emailMsg && (
              <p className={`text-sm ${emailMsg.includes("güncellendi") ? "text-green-600" : "text-red-500"}`}>
                {emailMsg}
              </p>
            )}
            <button
              type="submit"
              disabled={saving || email === user?.email}
              className="bg-blue-600 text-white px-4 py-2 rounded-lg text-sm disabled:opacity-50 hover:bg-blue-700"
            >
              Güncelle
            </button>
          </form>
        </div>

        {/* Password */}
        <div className="bg-white rounded-2xl shadow p-5">
          <h2 className="font-semibold text-gray-700 mb-4">Şifre Değiştir</h2>
          <form onSubmit={handlePasswordChange} className="space-y-3">
            <div>
              <label className="block text-xs text-gray-500 mb-1">Mevcut şifre</label>
              <input
                type="password"
                required
                minLength={8}
                value={currentPw}
                onChange={(e) => setCurrentPw(e.target.value)}
                className="w-full border border-gray-300 rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-blue-500"
              />
            </div>
            <div>
              <label className="block text-xs text-gray-500 mb-1">Yeni şifre (min. 8 karakter)</label>
              <input
                type="password"
                required
                minLength={8}
                value={newPw}
                onChange={(e) => setNewPw(e.target.value)}
                className="w-full border border-gray-300 rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-blue-500"
              />
            </div>
            {pwMsg && (
              <p className={`text-sm ${pwMsg.includes("başarıyla") ? "text-green-600" : "text-red-500"}`}>
                {pwMsg}
              </p>
            )}
            <button
              type="submit"
              disabled={saving}
              className="bg-blue-600 text-white px-4 py-2 rounded-lg text-sm disabled:opacity-50 hover:bg-blue-700"
            >
              Şifreyi Değiştir
            </button>
          </form>
        </div>

        {/* Account info */}
        <div className="bg-white rounded-2xl shadow p-5">
          <h2 className="font-semibold text-gray-700 mb-3">Hesap Bilgileri</h2>
          <dl className="space-y-2 text-sm">
            <div className="flex justify-between">
              <dt className="text-gray-400">Kullanıcı ID</dt>
              <dd className="text-gray-700 font-medium">{user?.id}</dd>
            </div>
            <div className="flex justify-between">
              <dt className="text-gray-400">Kayıt tarihi</dt>
              <dd className="text-gray-700 font-medium">
                {user?.created_at ? new Date(user.created_at).toLocaleDateString("tr-TR") : "—"}
              </dd>
            </div>
            <div className="flex justify-between">
              <dt className="text-gray-400">Hesap durumu</dt>
              <dd className={`font-medium ${user?.is_active ? "text-green-600" : "text-red-500"}`}>
                {user?.is_active ? "Aktif" : "Devre dışı"}
              </dd>
            </div>
          </dl>
        </div>

        {/* Danger zone */}
        <div className="bg-white rounded-2xl shadow p-5 border border-red-100">
          <h2 className="font-semibold text-red-600 mb-3">Tehlikeli Alan</h2>
          <p className="text-sm text-gray-500 mb-4">
            Hesabını silersen tüm siparişlerin ve uyarıların kalıcı olarak devre dışı kalır.
          </p>
          <button
            onClick={handleDeleteAccount}
            className="bg-red-50 text-red-600 border border-red-200 px-4 py-2 rounded-lg text-sm hover:bg-red-100"
          >
            Hesabı Sil
          </button>
        </div>
      </div>
    </>
  );
}
