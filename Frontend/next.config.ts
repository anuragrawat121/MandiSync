import type { NextConfig } from "next";
import path from "path";
import { fileURLToPath } from "url";

const rootDir = path.dirname(fileURLToPath(import.meta.url));

const nextConfig: NextConfig = {
  reactStrictMode: true,
  // Isolate this app from parent-folder lockfiles (avoids broken chunk paths).
  outputFileTracingRoot: rootDir,
  turbopack: {
    root: rootDir,
  },
};

// GitHub Pages is static HTML. Docker needs standalone. Vercel uses its runtime.
if (process.env.GITHUB_PAGES === "true") {
  const repoBase = process.env.NEXT_PUBLIC_BASE_PATH || "/MandiSync";
  nextConfig.output = "export";
  nextConfig.trailingSlash = true;
  nextConfig.images = { unoptimized: true };
  nextConfig.basePath = repoBase;
  nextConfig.assetPrefix = repoBase;
} else if (!process.env.VERCEL) {
  nextConfig.output = "standalone";
}

export default nextConfig;
