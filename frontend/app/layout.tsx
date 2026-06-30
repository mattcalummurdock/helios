import type { Metadata } from "next";
import "./globals.css";
import { DemoBootstrap } from "@/components/DemoBootstrap";
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
        <DemoBootstrap />
        <div className="app-shell">
          <NavBar />
          <div className="app-main">{children}</div>
        </div>
      </body>
    </html>
  );
}
