import type { Metadata } from "next";
import "./globals.css";

export const metadata: Metadata = {
  title: "TradeCred | Receivable Trust Infrastructure",
  description: "A permissioned trade-receivables prototype for MSME exporters.",
};

export default function RootLayout({
  children,
}: Readonly<{ children: React.ReactNode }>) {
  return (
    <html lang="en">
      <body>{children}</body>
    </html>
  );
}
