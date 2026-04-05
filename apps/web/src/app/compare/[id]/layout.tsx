import type { Metadata } from "next";

const API_URL = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

export async function generateMetadata(
  { params }: { params: Promise<{ id: string }> }
): Promise<Metadata> {
  const { id } = await params;
  try {
    const res = await fetch(`${API_URL}/catalog/products/${id}`, {
      next: { revalidate: 300 },
    });
    if (res.ok) {
      const product = await res.json();
      const title = product?.name
        ? `${product.name} | Fiyat Kalkanı`
        : "Ürün Detayı | Fiyat Kalkanı";
      return {
        title,
        description: product?.description
          ?? "Ürün fiyatlarını mağazalar arasında karşılaştır ve en iyi teklifi bul.",
        openGraph: { title },
      };
    }
  } catch { /* fall through to default */ }

  return {
    title: "Ürün Detayı | Fiyat Kalkanı",
    description: "Ürün fiyatlarını mağazalar arasında karşılaştır ve en iyi teklifi bul.",
    openGraph: { title: "Ürün Detayı | Fiyat Kalkanı" },
  };
}

export default function ProductDetailLayout({ children }: { children: React.ReactNode }) {
  return <>{children}</>;
}
