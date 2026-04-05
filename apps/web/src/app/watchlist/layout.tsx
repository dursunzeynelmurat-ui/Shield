import type { Metadata } from "next";

export const metadata: Metadata = {
  title: "Takip Listesi",
  description: "Takip ettiğin ürünlerin fiyat değişimlerini izle, hedef fiyata ulaşınca bildirim al.",
};

export default function WatchlistLayout({ children }: { children: React.ReactNode }) {
  return <>{children}</>;
}
