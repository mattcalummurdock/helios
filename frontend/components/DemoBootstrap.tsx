"use client";

import { useEffect } from "react";
import { resetDemoStorageIfNeeded } from "@/lib/demo";

/** One-time cleanup for browsers that cached broken demo state. */
export function DemoBootstrap() {
  useEffect(() => {
    resetDemoStorageIfNeeded();
  }, []);
  return null;
}
