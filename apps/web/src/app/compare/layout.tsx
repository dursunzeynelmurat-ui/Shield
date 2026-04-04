import type { Metadata } from "next";

export const metadata: Metadata = {
  title: "Ürün Karşılaştır",
  description: "Birden fazla mağazanın fiyatlarını karşılaştır, en uygun teklifi bul.",
  openGraph: {
    title: "Ürün Karşılaştır | Fiyat Kalkanı",
    description: "Birden fazla mağazanın fiyatlarını karşılaştır.",
  },
};

export default function CompareLayout({ children }: { children: React.ReactNode }) {
  return <>{children}</>;
}
