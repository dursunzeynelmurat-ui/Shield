"use client";
import { useEffect, useState } from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import Navbar from "@/components/Navbar";
import { getDashboard } from "@/lib/api";
import { isAuthenticated } from "@/lib/auth";
import type { DashboardCard } from "@/types";

const STATUS_LABELS: Record<string, string> = {
  pending_verification: "Doğrulama Bekliyor",
  verified: "Doğrulandı",
  matching: "Eşleştiriliyor",
  matched: "Eşleştirildi",
  monitoring: "İzleniyor",
  completed: "Tamamlandı",
  failed: "Başarısız",
};

const STATUS_COLORS: Record<string, string> = {
  pending_verification: "bg-yellow-100 text-yellow-700",
  verified: "bg-blue-100 text-blue-700",
  matching: "bg-blue-100 text-blue-700",
  matched: "bg-blue-100 text-blue-700",
  monitoring: "bg-green-100 text-green-700",
  completed: "bg-gray-100 text-gray-700",
  failed: "bg-red-100 text-red-700",
};

export default function DashboardPage() {
  const router = useRouter();
  const [cards, setCards] = useState<DashboardCard[]>([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    if (!isAuthenticated()) {
      router.push("/login");
      return;
    }
    getDashboard()
      .then(setCards)
      .finally(() => setLoading(false));
  }, [router]);

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
      <div className="max-w-5xl mx-auto p-6">
        <div className="flex items-center justify-between mb-6">
          <h1 className="text-2xl font-bold text-gray-800">Siparişlerim</h1>
          <Link
            href="/upload"
            className="bg-blue-600 text-white px-4 py-2 rounded-lg text-sm hover:bg-blue-700"
          >
            + Yeni Sipariş
          </Link>
        </div>

        {cards.length === 0 ? (
          <div className="bg-white rounded-2xl shadow p-12 text-center text-gray-400">
            <p className="text-lg mb-4">Henüz sipariş yok.</p>
            <Link href="/upload" className="text-blue-600 hover:underline text-sm">
              İlk siparişini ekle
            </Link>
          </div>
        ) : (
          <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
            {cards.map((card) => (
              <Link
                key={card.order_id}
                href={`/orders/${card.order_id}`}
                className="bg-white rounded-2xl shadow p-5 hover:shadow-md transition block"
              >
                <div className="flex items-start justify-between mb-3">
                  <span className={`text-xs px-2 py-0.5 rounded-full font-medium ${STATUS_COLORS[card.status]}`}>
                    {STATUS_LABELS[card.status] || card.status}
                  </span>
                  {card.has_alert && (
                    <span className="text-xs bg-red-100 text-red-600 px-2 py-0.5 rounded-full font-medium">
                      Uyarı
                    </span>
                  )}
                </div>

                <p className="text-sm font-semibold text-gray-800 line-clamp-2 mb-3">
                  {card.product_name || "Ürün adı bilinmiyor"}
                </p>

                <div className="space-y-1 text-xs text-gray-500">
                  <div className="flex justify-between">
                    <span>Alış fiyatı</span>
                    <span className="font-medium text-gray-700">
                      {card.purchase_price ? `${card.purchase_price} ${card.currency}` : "—"}
                    </span>
                  </div>
                  <div className="flex justify-between">
                    <span>Güncel fiyat</span>
                    <span className={`font-medium ${card.savings ? "text-green-600" : "text-gray-700"}`}>
                      {card.current_price ? `${card.current_price} ${card.currency}` : "—"}
                    </span>
                  </div>
                  {card.savings && (
                    <div className="flex justify-between">
                      <span>Tasarruf</span>
                      <span className="font-bold text-green-600">
                        {card.savings} {card.currency}
                      </span>
                    </div>
                  )}
                  <div className="flex justify-between">
                    <span>İade süresi</span>
                    <span className={`font-medium ${(card.remaining_return_days ?? 0) <= 3 ? "text-orange-500" : "text-gray-700"}`}>
                      {card.remaining_return_days !== null ? `${card.remaining_return_days} gün` : "—"}
                    </span>
                  </div>
                </div>
              </Link>
            ))}
          </div>
        )}
      </div>
    </>
  );
}
