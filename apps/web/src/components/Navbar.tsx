"use client";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { removeToken } from "@/lib/auth";

export default function Navbar() {
  const router = useRouter();

  const handleLogout = () => {
    removeToken();
    router.push("/login");
  };

  return (
    <nav className="bg-white border-b border-gray-200 px-6 py-3 flex items-center justify-between">
      <Link href="/dashboard" className="text-lg font-bold text-blue-600">
        Fiyat Kalkanı
      </Link>
      <div className="flex items-center gap-4 text-sm text-gray-600">
        <Link href="/dashboard" className="hover:text-blue-600">Dashboard</Link>
        <Link href="/upload" className="hover:text-blue-600">Yeni Sipariş</Link>
        <Link href="/alerts" className="hover:text-blue-600">Uyarılar</Link>
        <Link href="/settings" className="hover:text-blue-600">Ayarlar</Link>
        <button onClick={handleLogout} className="text-red-500 hover:underline">
          Çıkış
        </button>
      </div>
    </nav>
  );
}
