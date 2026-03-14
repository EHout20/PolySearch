import type { Metadata } from "next";
import "./globals.css";

export const metadata: Metadata = {
  title: "PolyLens | Market Intelligence",
  description: "AI-powered prediction market research dashboard.",
};

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    <html lang="en">
      <body>
        {children}
      </body>
    </html>
  );
}
