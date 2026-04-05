import type { Metadata } from "next";

export const metadata: Metadata = {
  title: "Senin İçin",
  description: "Alışveriş geçmişine göre kişiselleştirilmiş ürün önerileri.",
};

export default function ForYouLayout({ children }: { children: React.ReactNode }) {
  return <>{children}</>;
}
