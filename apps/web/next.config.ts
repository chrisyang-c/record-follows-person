import type { NextConfig } from "next";
import path from "node:path";

const nextConfig: NextConfig = {
  // packages/schema/ts is imported via the @schema alias; it lives outside apps/web.
  turbopack: { root: path.join(__dirname, "../..") },
  outputFileTracingRoot: path.join(__dirname, "../.."),
  devIndicators: false,
};

export default nextConfig;
