import type { Metadata } from "next";
import "./globals.css";

export const metadata: Metadata = {
  title: { default: "Fiyat Kalkanı — Akıllı Fiyat Takip", template: "%s | Fiyat Kalkanı" },
  description: "Satın aldığın ürünlerin fiyatı düşünce seni haberdar ederiz. Fırsat karşılaştırma, kupon takibi ve akıllı öneriler.",
  icons: { icon: "/favicon.svg", apple: "/icon.svg" },
  openGraph: {
    siteName: "Fiyat Kalkanı",
    type: "website",
    locale: "tr_TR",
  },
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="tr" suppressHydrationWarning>
      <body className="min-h-screen bg-slate-100 dark:bg-slate-950 transition-colors">{children}</body>
    </html>
  );
}
