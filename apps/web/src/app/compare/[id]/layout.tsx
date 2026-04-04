import type { Metadata } from "next";

export const metadata: Metadata = {
  title: "Ürün Detayı",
  description: "Ürün fiyatlarını mağazalar arasında karşılaştır ve en iyi teklifi bul.",
  openGraph: {
    title: "Ürün Detayı | Fiyat Kalkanı",
  },
};

export default function ProductDetailLayout({ children }: { children: React.ReactNode }) {
  return <>{children}</>;
}
