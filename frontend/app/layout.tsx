import type { Metadata } from "next";
import "./globals.css";
import { NavBar } from "@/components/NavBar";

export const metadata: Metadata = {
  title: "Helios — Satellite Surveillance",
  description: "AI-Based Satellite Image Analysis — 3D Globe Dashboard",
};

export default function RootLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <html lang="en">
      <body>
        <div className="app-shell">
          <NavBar />
          <div className="app-main">{children}</div>
        </div>
      </body>
    </html>
  );
}
