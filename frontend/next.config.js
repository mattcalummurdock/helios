const path = require("path");
const fs = require("fs");

/** Load repo-root .env so CESIUM_ION_TOKEN is available when running from frontend/ */
function loadRootEnv() {
  const envPath = path.join(__dirname, "..", ".env");
  if (!fs.existsSync(envPath)) return;
  for (const line of fs.readFileSync(envPath, "utf8").split("\n")) {
    const trimmed = line.trim();
    if (!trimmed || trimmed.startsWith("#")) continue;
    const eq = trimmed.indexOf("=");
    if (eq <= 0) continue;
    const key = trimmed.slice(0, eq).trim();
    const val = trimmed.slice(eq + 1).trim();
    if (process.env[key] === undefined) process.env[key] = val;
  }
}
loadRootEnv();

const cesiumToken =
  process.env.NEXT_PUBLIC_CESIUM_ION_TOKEN || process.env.CESIUM_ION_TOKEN || "";

/** @type {import('next').NextConfig} */
const nextConfig = {
  output: "standalone",
  env: {
    NEXT_PUBLIC_DEMO_MODE: process.env.NEXT_PUBLIC_DEMO_MODE || "",
    NEXT_PUBLIC_CESIUM_ION_TOKEN: cesiumToken,
    NEXT_PUBLIC_API_URL: process.env.NEXT_PUBLIC_API_URL || "http://localhost:8080",
  },
};

module.exports = nextConfig;
