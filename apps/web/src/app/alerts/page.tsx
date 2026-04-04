"use client";
import { useEffect, useState } from "react";
import Link from "next/link";
import Navbar from "@/components/Navbar";
import { getAlerts, updateAlertStatus } from "@/lib/api";
import type { Alert } from "@/types";

const STATUS_LABELS: Record<string, string> = {
  new: "Yeni",
  seen: "Görüldü",
  acted: "İşlem Yapıldı",
  dismissed: "Kapatıldı",
};

export default function AlertsPage() {
  const [alerts, setAlerts] = useState<Alert[]>([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    getAlerts().then(setAlerts).finally(() => setLoading(false));
  }, []);

  const dismiss = async (id: number) => {
    const updated = await updateAlertStatus(id, "dismissed");
    setAlerts((prev) => prev.map((a) => (a.id === id ? updated : a)));
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
      <div className="max-w-3xl mx-auto p-6">
        <h1 className="text-2xl font-bold text-gray-800 mb-6">Uyarılar</h1>
        {alerts.length === 0 ? (
          <div className="bg-white rounded-2xl shadow p-12 text-center text-gray-400">
            Henüz uyarı yok.
          </div>
        ) : (
          <div className="space-y-3">
            {alerts.map((alert) => (
              <div
                key={alert.id}
                className={`bg-white rounded-xl shadow p-4 flex items-start justify-between
                  ${alert.status === "new" ? "border-l-4 border-red-400" : "opacity-60"}`}
              >
                <div>
                  <div className="flex gap-2 items-center mb-1">
                    <span className="text-xs font-medium bg-gray-100 text-gray-600 px-2 py-0.5 rounded-full">
                      {STATUS_LABELS[alert.status] || alert.status}
                    </span>
                    {alert.amount_saved && (
                      <span className="text-xs font-bold text-green-600">
                        {alert.amount_saved} TRY tasarruf
                      </span>
                    )}
                  </div>
                  <p className="text-sm text-gray-700">{alert.message}</p>
                  <Link
                    href={`/orders/${alert.order_id}`}
                    className="text-xs text-blue-600 hover:underline mt-1 block"
                  >
                    Siparişe git →
                  </Link>
                </div>
                {alert.status === "new" && (
                  <button
                    onClick={() => dismiss(alert.id)}
                    className="text-xs text-gray-400 hover:text-gray-600 ml-4 flex-shrink-0"
                  >
                    Kapat
                  </button>
                )}
              </div>
            ))}
          </div>
        )}
      </div>
    </>
  );
}
