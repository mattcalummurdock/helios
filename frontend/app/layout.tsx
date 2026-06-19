import type { Metadata } from "next";
import "./globals.css";

export const metadata: Metadata = {
  title: "Helios — Satellite Surveillance MVP",
  description: "AI-Based Satellite Image Analysis MVP — Phase 1",
};

export default function RootLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <html lang="en">
      <body>{children}</body>
    </html>
  );
}
