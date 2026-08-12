import type { NextConfig } from "next";
import path from "path";
import { fileURLToPath } from "url";

const rootDir = path.dirname(fileURLToPath(import.meta.url));

const nextConfig: NextConfig = {
  reactStrictMode: true,
  // Required for the production Docker image (next start via standalone server).
  output: "standalone",
  // Isolate this app from parent-folder lockfiles (avoids broken chunk paths).
  outputFileTracingRoot: rootDir,
  turbopack: {
    root: rootDir,
  },
};

export default nextConfig;
