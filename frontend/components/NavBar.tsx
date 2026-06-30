"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";

export function NavBar() {
  const path = usePathname();
  return (
    <nav className="nav-bar">
      <span className="nav-brand">HELIOS</span>
      <div className="nav-links">
        <Link href="/" className={path === "/" ? "active" : ""}>
          Globe
        </Link>
        <Link href="/aois" className={path === "/aois" ? "active" : ""}>
          AOI Manager
        </Link>
      </div>
    </nav>
  );
}
