import type { Metadata } from "next";
import "./globals.css";

export const metadata: Metadata = {
  title: { default: "Fiyat Kalkanı", template: "%s — Fiyat Kalkanı" },
  description: "Satın aldığın ürünlerin fiyatı düşünce seni haberdar ederiz.",
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="tr">
      <body className="min-h-screen bg-slate-100">{children}</body>
    </html>
  );
}
