import type { Metadata } from "next";

export const metadata: Metadata = {
  title: "Fırsatlar",
  description: "Aktif kuponlar, indirim kodları ve özel teklifler. En iyi fırsatları keşfet.",
  openGraph: {
    title: "Fırsatlar | Fiyat Kalkanı",
    description: "Aktif kuponlar, indirim kodları ve özel teklifler.",
  },
};

export default function DealsLayout({ children }: { children: React.ReactNode }) {
  return <>{children}</>;
}
