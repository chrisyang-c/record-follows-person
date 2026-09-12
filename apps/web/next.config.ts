import type { NextConfig } from "next";
import path from "node:path";

const nextConfig: NextConfig = {
  // packages/schema/ts is imported via the @schema alias; it lives outside apps/web.
  turbopack: { root: path.join(__dirname, "../..") },
  outputFileTracingRoot: path.join(__dirname, "../.."),
  devIndicators: false,
  async rewrites() {
    const api = (process.env.API_INTERNAL_URL || "http://127.0.0.1:8000").replace(/\/$/, "");
    return [{ source: "/api/:path*", destination: `${api}/:path*` }];
  },
};

export default nextConfig;
